"""Post-hoc two-feature coverage diagnostic; never fits or changes regressors.

Hull half-space membership is independently checked by exhaustive triangle
barycentric membership, which does not use Qhull or its hull vertices.
"""
import argparse
from itertools import combinations
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import ConvexHull
from sklearn.preprocessing import StandardScaler

from common import ROOT, digest, load_experiment_v1, require, write_csv
from reproduce_results import read_checkpoints

RECORDED = ROOT/'results/model_comparison'
EXPERIMENT = load_experiment_v1()
FEATURES = ('relative_rms', 'relative_ptp')
TOLERANCE = 1e-10


def triangle_membership(training, queries, tolerance=TOLERANCE):
    """A point in a 2D convex hull belongs to a triangle of input points.

Test all nondegenerate training triples independently of Qhull. Boundaries count
as inside. The tolerance here applies to dimensionless barycentric weights.
"""
    inside = np.zeros(len(queries), dtype=bool)
    valid_triangles = 0
    for indices in combinations(range(len(training)), 3):
        a, b, c = training[list(indices)]
        edges = np.column_stack((b-a, c-a))
        if abs(np.linalg.det(edges)) <= np.finfo(float).eps * max(1, np.linalg.norm(edges)**2):
            continue
        valid_triangles += 1
        weights = np.linalg.solve(edges, (queries-a).T).T
        third = 1-weights.sum(axis=1)
        inside |= (weights >= -tolerance).all(axis=1) & (third >= -tolerance)
    require(valid_triangles > 0, 'Training features do not span a 2D hull')
    return inside


def diagnose(training, evaluation, tolerance=TOLERANCE):
    """Only training rows fit the scaler and define the support region."""
    training, evaluation = np.asarray(training, float), np.asarray(evaluation, float)
    require(training.ndim == 2 and training.shape[1] == 2 and
            evaluation.ndim == 2 and evaluation.shape[1] == 2, 'Expected two features')
    require(np.isfinite(training).all() and np.isfinite(evaluation).all(), 'Nonfinite features')
    scaler = StandardScaler().fit(training)
    require(np.all(scaler.var_ > 0), 'Constant training feature')
    z_train, z_eval = scaler.transform(training), scaler.transform(evaluation)
    hull = ConvexHull(z_train)
    queries = np.vstack((z_train, z_eval))
    signed_halfspaces = queries @ hull.equations[:, :-1].T + hull.equations[:, -1]
    inside = (signed_halfspaces <= tolerance).all(axis=1)
    independent = triangle_membership(z_train, queries, tolerance)
    require(np.array_equal(inside, independent), 'Hull and independent triangle classifications disagree')
    require(inside[:len(training)].all(), 'A training point was classified outside its own hull')
    # A nonsingular affine transform preserves mathematical hull membership.
    raw_independent = triangle_membership(training, np.vstack((training, evaluation)), tolerance)
    require(np.array_equal(inside, raw_independent), 'Raw/scaled hull classifications disagree')
    sweeps = []
    for tol in (1e-12, 1e-10, 1e-8):
        primary = (signed_halfspaces <= tol).all(axis=1)
        secondary = triangle_membership(z_train, queries, tol)
        require(np.array_equal(primary, inside) and np.array_equal(secondary, inside),
                'Coverage flags are sensitive to numerical tolerance; investigate before reporting')
        sweeps.append(dict(tolerance=tol, evaluation_outside=int((~primary[len(training):]).sum())))
    return dict(scaler=scaler, hull=hull, z_train=z_train, z_eval=z_eval,
                inside=inside, independent=independent, tolerance_sweep=sweeps)


def make_plot(directions, output, standardised=False):
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.7), layout='constrained')
    all_points = np.vstack([d[k] for d in directions for k in
                           (('z_train', 'z_eval') if standardised else ('training', 'evaluation'))])
    lo, hi = all_points.min(axis=0), all_points.max(axis=0)
    pad = (hi-lo)*0.08
    for ax, direction in zip(axes, directions):
        train = direction['z_train'] if standardised else direction['training']
        evaluation = direction['z_eval'] if standardised else direction['evaluation']
        polygon = train[direction['hull'].vertices]
        polygon = np.vstack((polygon, polygon[0]))
        inside = direction['inside'][len(train):]
        ax.fill(polygon[:, 0], polygon[:, 1], facecolor='#24628a', alpha=0.10)
        ax.plot(polygon[:, 0], polygon[:, 1], color='#24628a', lw=1.5, label='Training convex hull')
        ax.scatter(train[:, 0], train[:, 1], s=40, marker='o', facecolors='none', edgecolors='#24628a',
                   linewidths=1.5, label=f'Training ({len(train)})', zorder=3)
        ax.scatter(evaluation[~inside, 0], evaluation[~inside, 1], s=48, marker='x', color='#b45e13',
                   linewidths=1.6, label=f'Evaluation outside ({int((~inside).sum())})', zorder=4)
        if inside.any():
            ax.scatter(evaluation[inside, 0], evaluation[inside, 1], s=52, marker='D', color='#5d6d35',
                       edgecolors='white', linewidths=0.6, label=f'Evaluation inside ({int(inside.sum())})', zorder=5)
        suffix = ' (training-standardised)' if standardised else ''
        ax.set(xlim=(lo[0]-pad[0], hi[0]+pad[0]), ylim=(lo[1]-pad[1], hi[1]+pad[1]),
               xlabel='Relative RMS'+suffix, ylabel='Relative peak-to-peak'+suffix,
               title=f"{direction['train_specimen']} -> {direction['evaluation_specimen']}\n"
                     f"{int((~inside).sum())}/{len(evaluation)} evaluation checkpoints outside")
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, color='#dddddd', linewidth=0.5)
        ax.legend(fontsize=8, loc='best')
    fig.suptitle('Two-feature support: non-reference checkpoint medians\n'
                 'Hull/scaler fitted to training specimen only; outside membership is not extrapolation distance.', fontsize=12)
    fig.savefig(output, dpi=170)
    plt.close(fig)


def main(argv=None):
    """Classify checkpoints against each direction's training hull and export results.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If the recorded scalers or counts disagree, or protected files change.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, default=RECORDED,
                        help='Model-comparison folder whose preprocessing audit is checked.')
    parser.add_argument('--output', type=Path, default=ROOT/'results/rebuilt/coverage',
                        help='New output folder; the recorded coverage folder is refused.')
    args = parser.parse_args(argv)
    comparison, out = args.comparison.resolve(), args.output.resolve()
    require(out != RECORDED/'coverage' and RECORDED/'coverage' not in out.parents,
            'The recorded coverage folder is immutable; choose a new output folder')
    out.mkdir(parents=True, exist_ok=True)
    # All pre-existing numerical/model artifacts remain protected. The requested
    # interpretation update is edited separately; this script never writes it.
    protected = [p for directory in (ROOT/'results/baseline', ROOT/'results/repeat_sensitivity', comparison)
                 for p in directory.rglob('*') if p.is_file() and not p.is_relative_to(out)
                 and p != comparison/'INTERPRETATION.md']
    protected += [ROOT/'config/model_comparison.json', ROOT/'docs/model_comparison_protocol.md',
                  ROOT/'scripts/model_comparison.py']
    before = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
    checkpoints = read_checkpoints(ROOT/'results/baseline/checkpoint_features.csv')
    recorded_scalers = json.loads((comparison/'preprocessing_audit.json').read_text())
    flags, summaries, vertices, directions = [], [], [], []
    reported_counts = EXPERIMENT['coverage_reported_outside']
    for train_name, evaluation_name in EXPERIMENT['directions']:
        reported = reported_counts[train_name]
        train_rows = [r for r in checkpoints if r['specimen'] == train_name and not r['is_reference']]
        evaluation_rows = [r for r in checkpoints if r['specimen'] == evaluation_name and not r['is_reference']]
        train = np.array([[r[f] for f in FEATURES] for r in train_rows])
        evaluation = np.array([[r[f] for f in FEATURES] for r in evaluation_rows])
        result = diagnose(train, evaluation)
        scaler = result['scaler']
        recorded = next(r for r in recorded_scalers if r['train_specimen'] == train_name and r['model'] == 'LinearRegression')
        require([r['cycles'] for r in train_rows] == recorded['training_cycles'] and
                [r['cycles'] for r in evaluation_rows] == recorded['evaluation_cycles'], 'Comparison membership changed')
        np.testing.assert_array_equal(scaler.mean_, recorded['input_mean'])
        np.testing.assert_array_equal(scaler.scale_, recorded['input_scale'])
        require(int(scaler.n_samples_seen_) == recorded['input_n'], 'Scaler training count changed')
        rows = train_rows+evaluation_rows
        standardised = np.vstack((result['z_train'], result['z_eval']))
        for i, (r, z) in enumerate(zip(rows, standardised)):
            flags.append(dict(train_specimen=train_name, evaluation_specimen=evaluation_name,
                split='training' if i < len(train) else 'evaluation', specimen=r['specimen'], cycles=r['cycles'],
                relative_rms=r['relative_rms'], relative_ptp=r['relative_ptp'],
                standardised_rms=float(z[0]), standardised_ptp=float(z[1]),
                inside_or_on_training_hull=bool(result['inside'][i]),
                outside_training_hull=bool(not result['inside'][i]),
                triangle_check_inside=bool(result['independent'][i])))
        for order, index in enumerate(result['hull'].vertices):
            vertices.append(dict(train_specimen=train_name, evaluation_specimen=evaluation_name,
                                 vertex_order=order, cycles=train_rows[index]['cycles'],
                                 relative_rms=float(train[index, 0]), relative_ptp=float(train[index, 1]),
                                 standardised_rms=float(result['z_train'][index, 0]),
                                 standardised_ptp=float(result['z_train'][index, 1])))
        outside = int((~result['inside'][len(train):]).sum())
        summary = dict(train_specimen=train_name, evaluation_specimen=evaluation_name,
            training_checkpoints=len(train), evaluation_checkpoints=len(evaluation), evaluation_outside=outside,
            evaluation_inside_or_on=len(evaluation)-outside, reported_outside=reported, reported_count_matches=outside == reported,
            evaluation_inside_cycles=[r['cycles'] for i, r in enumerate(evaluation_rows) if result['inside'][len(train)+i]],
            input_mean=scaler.mean_.tolist(), input_scale=scaler.scale_.tolist(), training_only_scaler_matches_recorded=True,
            independent_methods_agree=True, raw_scaled_classifications_agree=True, tolerance_sweep=result['tolerance_sweep'])
        summaries.append(summary)
        directions.append(dict(train_specimen=train_name, evaluation_specimen=evaluation_name,
                               training=train, evaluation=evaluation, **result))
    write_csv(out/'checkpoint_coverage.csv', flags)
    write_csv(out/'training_hull_vertices.csv', vertices)
    make_plot(directions, out/'feature_coverage.png')
    make_plot(directions, out/'feature_coverage_standardised.png', standardised=True)
    after = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
    require(before == after, 'Existing experiment artifacts changed')
    verification = dict(directions=summaries, boundary_policy='Boundary included inside; no distances reported',
        primary_method='scipy ConvexHull half-space inequalities in training-standardised coordinates',
        independent_method='Exhaustive nondegenerate training triples with barycentric containment; no Qhull calls',
        halfspace_tolerance=TOLERANCE, barycentric_weight_tolerance=TOLERANCE,
        no_models_fitted=True, existing_artifact_hashes_unchanged=before)
    (out/'verification.json').write_text(json.dumps(verification, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
