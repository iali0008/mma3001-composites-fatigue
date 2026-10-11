"""Protocol v2, step 4: score the frozen model on L2S11 once, plus the L1S11 sanity check.

Order of operations (``docs/protocol_v2.md`` sections 8-9):

1. refuse to run if the test receipt exists or tracked files are uncommitted;
   write the receipt with the commit hash before anything else;
2. refit the frozen model from ``results/protocol_v2/selection.json`` and the two
   fixed controls on the pooled non-reference L1S11 + L1S12 checkpoints;
3. extract L2S11 features **without labels**, predict, and write the
   predictions and their hash;
4. only then read the L2S11 labels and score (MAE primary);
5. L2S11 coverage diagnostic and the L1S11 125k-227k plausibility check.

The script never reruns: a second invocation stops at step 1.

Example
-------
``python scripts/protocol_v2_test.py --data-root "data/2.+Composites/2. Composites"``
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from threadpoolctl import threadpool_limits

from common import ROOT, digest, load_json, require, save_json, write_csv
from feature_coverage import diagnose
from model_comparison import build_model
from protocol_v2 import (
    PROTOCOL_DOC,
    PROTOCOL_PATH,
    attach_labels,
    build_checkpoints,
    extract_specimen,
    input_columns,
    load_protocol,
    read_published_labels,
    sanity_criteria,
)
from protocol_v2_validation import git_state, scores

BASE = ROOT / 'results' / 'protocol_v2'
TEST = BASE / 'test_L2S11'
SANITY = BASE / 'sanity_L1S11'
SELECTION = BASE / 'selection.json'
CONTROLS = ('log_cycle_OLS', 'DummyRegressor')


def matrix(rows, model, input_set, protocol):
    """Feature matrix: ``log10_cycles`` for log-cycle OLS, else the input-set columns.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows.
    model : str
        Model name.
    input_set : str
        Selected input set.
    protocol : dict
        Output of :func:`protocol_v2.load_protocol`.

    Returns
    -------
    numpy.ndarray
        ``(n_rows, n_features)`` matrix.
    """
    cols = ['log10_cycles'] if model == 'log_cycle_OLS' else input_columns(input_set, protocol)
    return np.array([[r[c] for c in cols] for r in rows], dtype=float)


def write_rows(path, rows):
    """Write rows with the union of their keys as header.

    Parameters
    ----------
    path : pathlib.Path
        Destination CSV.
    rows : list of dict
        Rows to write.
    """
    write_csv(path, rows, list(dict.fromkeys(k for r in rows for k in r)))


def plot_test(rows, metrics, path):
    """Plot L2S11 predictions against observations and residuals against cycles.

    Parameters
    ----------
    rows : list of dict
        Scored prediction rows.
    metrics : list of dict
        One metric row per model.
    path : pathlib.Path
        Destination PNG.
    """
    colours = {'frozen': '#2a78d6', 'log_cycle_OLS': '#eb6834', 'DummyRegressor': '#6b6b6b'}
    markers = {'frozen': 'o', 'log_cycle_OLS': '^', 'DummyRegressor': 's'}
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, (left, right) = plt.subplots(1, 2, figsize=(13, 5.8), layout='constrained')
    values = [r[k] for r in rows for k in ('observed', 'predicted')]
    span = max(values) - min(values)
    lim = (min(values) - 0.08 * span, max(values) + 0.08 * span)
    left.plot(lim, lim, '--', color='#9a9a9a', lw=1)
    for role in colours:
        rs = [r for r in rows if r['role'] == role]
        m = next(m for m in metrics if m['role'] == role)
        label = f"{m['model']} ({'frozen' if role == 'frozen' else 'control'}), MAE {m['MAE']:.4f}"
        left.scatter(
            [r['observed'] for r in rs],
            [r['predicted'] for r in rs],
            s=46,
            marker=markers[role],
            color=colours[role],
            edgecolors='white',
            label=label,
        )
        right.scatter(
            [r['cycles'] for r in rs],
            [r['residual'] for r in rs],
            s=46,
            marker=markers[role],
            color=colours[role],
            edgecolors='white',
            label=label,
        )
    left.set(
        xlim=lim,
        ylim=lim,
        xlabel='Observed published index (L2S11)',
        ylabel='Predicted index',
        title='Predicted vs observed',
    )
    left.set_aspect('equal', adjustable='box')
    right.axhline(0, color='#9a9a9a', ls='--', lw=1)
    right.set(
        xscale='log',
        xlabel='Cycles (log scale)',
        ylabel='Prediction − observation',
        title='Residuals',
    )
    for ax in (left, right):
        ax.grid(True, color='#e3e3e3', lw=0.5)
        ax.legend(fontsize=8, frameon=False, loc='best')
    fig.suptitle(
        'Protocol v2 held-out test on L2S11 (scored once; cross-layup)\n'
        'Trained on pooled L1S11 + L1S12; reference (cycle 3) excluded; no clipping',
        fontsize=12,
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_coverage(result, train, test, scored, path):
    """Plot pooled-training hull and L2S11 checkpoints in relative-feature axes.

    Parameters
    ----------
    result : dict
        Output of :func:`feature_coverage.diagnose`.
    train, test : numpy.ndarray
        Training and L2S11 feature matrices (relative RMS, relative PTP).
    scored : list of bool
        Whether each L2S11 row is a scored (labelled) checkpoint.
    path : pathlib.Path
        Destination PNG.
    """
    fig, ax = plt.subplots(figsize=(7, 6), layout='constrained')
    poly = train[result['hull'].vertices]
    poly = np.vstack((poly, poly[0]))
    ax.fill(poly[:, 0], poly[:, 1], color='#2a78d6', alpha=0.10)
    ax.plot(poly[:, 0], poly[:, 1], color='#2a78d6', lw=1.5, label='Pooled training hull')
    ax.scatter(
        train[:, 0],
        train[:, 1],
        s=36,
        facecolors='none',
        edgecolors='#2a78d6',
        label=f'Training L1S11 + L1S12 ({len(train)})',
    )
    inside = result['inside'][len(train) :]
    scored = np.array(scored)
    for mask, marker, label in ((scored, 'D', 'L2S11 scored'), (~scored, 'x', 'L2S11 unlabelled')):
        if mask.any():
            ax.scatter(
                test[mask, 0],
                test[mask, 1],
                marker=marker,
                s=48,
                color='#eb6834',
                label=f'{label} ({int(mask.sum())}; {int((~inside[mask]).sum())} outside)',
            )
    ax.set(
        xlabel='Relative RMS (path 1→7)',
        ylabel='Relative peak-to-peak (path 1→7)',
        title='L2S11 coverage by the pooled training hull\n'
        'Outside-hull membership is not an extrapolation distance',
    )
    ax.grid(True, color='#e3e3e3', lw=0.5)
    ax.legend(fontsize=8, frameon=False)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None):
    """Run the single guarded L2S11 test and the L1S11 sanity check.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If the test already ran, the tree is dirty, the selection is not
        committed, or an integrity check fails.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 4), default=4)
    args = parser.parse_args(argv)
    data_root = args.data_root.resolve()

    # 1. Guards and receipt, before anything is read.
    require(
        not TEST.exists() and not SANITY.exists(),
        'The L2S11 test has already been run; it is never rerun',
    )
    state = git_state()
    require(state['clean'], 'Commit all changes first; the receipt must identify the code')
    protocol = load_protocol()
    selection = load_json(SELECTION)
    model, input_set = selection['selected']['model'], selection['selected']['input_set']
    TEST.mkdir(parents=True)
    SANITY.mkdir(parents=True)
    save_json(
        TEST / 'receipt.json',
        dict(
            started_utc=datetime.now(timezone.utc).isoformat(),
            git=state,
            protocol_config_sha256=digest(PROTOCOL_PATH),
            protocol_doc_sha256=digest(PROTOCOL_DOC),
            selection_sha256=digest(SELECTION),
            frozen_model=model,
            input_set=input_set,
            controls=list(CONTROLS),
            runs_allowed=protocol['test']['runs_allowed'],
        ),
    )

    # 2. Pooled training data and fits.
    train_rows, l1s11 = [], []
    for specimen in ('L1S11', 'L1S12'):
        summaries, _ = extract_specimen(data_root, specimen, protocol, True, args.workers)
        cps, _, _ = build_checkpoints(summaries, protocol)
        train_rows += [c for c in cps if not c['is_reference'] and c['published_index'] is not None]
        if specimen == 'L1S11':
            l1s11 = cps
    require(
        len(train_rows) == 25, f'Expected 25 pooled training checkpoints, got {len(train_rows)}'
    )
    y_train = np.array([r['published_index'] for r in train_rows])
    fitted = {}
    with threadpool_limits(limits=protocol['models']['threads']):
        for name in (model,) + CONTROLS:
            require(name != 'MLPRegressor', 'MLP handling is not needed for this selection')
            estimator = build_model(name)
            estimator.fit(matrix(train_rows, name, input_set, protocol), y_train)
            fitted[name] = estimator

    # 3. L2S11 features without labels; predictions written before labels are read.
    summaries, hashes = extract_specimen(data_root, 'L2S11', protocol, False, args.workers)
    l2, _, reference = build_checkpoints(summaries, protocol)
    require(
        reference['cycles'] == protocol['reference']['expected_from_audit']['L2S11'],
        f"L2S11 reference is cycle {reference['cycles']}, not the declared cycle 3",
    )
    targets = [c for c in l2 if not c['is_reference']]
    blind = []
    for name in (model,) + CONTROLS:
        for c, value in zip(
            targets, fitted[name].predict(matrix(targets, name, input_set, protocol))
        ):
            blind.append(
                dict(
                    role='frozen' if name == model else name,
                    model=name,
                    cycles=c['cycles'],
                    predicted=float(value),
                )
            )
    write_rows(TEST / 'predictions_before_labels.csv', blind)
    save_json(
        TEST / 'predictions_before_labels.sha256.json',
        dict(
            sha256=digest(TEST / 'predictions_before_labels.csv'),
            written_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )

    # 4. Labels, then scoring.
    labels = read_published_labels(data_root, 'L2S11', protocol, args.workers)
    for file, value in hashes.items():
        require(digest(data_root / file) == value, f'Source file changed: {file}')
    l2 = attach_labels(l2, labels)
    scored = [c for c in l2 if not c['is_reference'] and c['published_index'] is not None]
    by_cycle = {c['cycles']: c for c in scored}
    rows, metrics = [], []
    for name in (model,) + CONTROLS:
        role = 'frozen' if name == model else name
        preds = {b['cycles']: b['predicted'] for b in blind if b['model'] == name}
        y = np.array([by_cycle[c]['published_index'] for c in sorted(by_cycle)])
        p = np.array([preds[c] for c in sorted(by_cycle)])
        metrics.append(
            dict(
                role=role,
                model=name,
                input_set=input_set if role == 'frozen' else 'none',
                n=len(y),
                **scores(y, p),
                min_prediction=float(p.min()),
                max_prediction=float(p.max()),
            )
        )
        for c, obs, pred in zip(sorted(by_cycle), y, p):
            rows.append(
                dict(
                    role=role,
                    model=name,
                    cycles=c,
                    observed=float(obs),
                    predicted=float(pred),
                    residual=float(pred - obs),
                    relative_rms=by_cycle[c]['relative_rms'],
                    relative_ptp=by_cycle[c]['relative_ptp'],
                )
            )
    cycle_one = sorted({lab for cyc, lab in labels.values() if cyc == 1 and lab is not None})
    frozen = next(m for m in metrics if m['role'] == 'frozen')
    beats = {m['model']: frozen['MAE'] < m['MAE'] for m in metrics if m['role'] != 'frozen'}
    # Persist the scores immediately, so nothing after this point can lose the single run.
    write_rows(TEST / 'checkpoint_features.csv', l2)
    write_rows(TEST / 'predictions.csv', rows)
    write_rows(TEST / 'metrics.csv', metrics)
    write_rows(
        TEST / 'recordings.csv',
        [
            {
                k: v
                for k, v in s.items()
                if k not in ('pair_counts', 'settings', 'rms', 'ptp', 'bad_pairs')
            }
            for s in summaries
        ],
    )
    save_json(TEST / 'source_hashes.json', hashes)
    result = dict(
        scored_utc=datetime.now(timezone.utc).isoformat(),
        git_commit=state['commit'],
        reference=reference,
        scored_cycles=sorted(by_cycle),
        scored_n=len(by_cycle),
        expected_scored_n=8,
        unlabelled_non_reference_cycles=[
            c['cycles'] for c in targets if c['cycles'] not in by_cycle
        ],
        cycle_1_label_reported_not_scored=cycle_one,
        metrics=metrics,
        frozen_beats_control=beats,
    )
    save_json(TEST / 'result.json', result)

    # 5a. Coverage of L2S11 by the pooled training hull (descriptive only).
    cols = input_columns(input_set, protocol)
    train_x = np.array([[r[c] for c in cols] for r in train_rows])
    test_x = np.array([[c[k] for k in cols] for c in targets])
    is_scored = [c['cycles'] in by_cycle for c in targets]
    try:
        cover = diagnose(train_x, test_x)
        inside = cover['inside'][len(train_x) :]
        coverage = [
            dict(
                cycles=c['cycles'],
                scored=flag,
                relative_rms=c[cols[0]],
                relative_ptp=c[cols[1]],
                inside_or_on_training_hull=bool(i),
            )
            for c, flag, i in zip(targets, is_scored, inside)
        ]
        write_rows(TEST / 'coverage.csv', coverage)
        result['coverage'] = dict(
            scored_outside=sum(
                r['scored'] and not r['inside_or_on_training_hull'] for r in coverage
            ),
            scored_total=len(by_cycle),
            all_outside=int((~inside).sum()),
            all_total=len(inside),
            outside_scored_cycles=[
                r['cycles'] for r in coverage if r['scored'] and not r['inside_or_on_training_hull']
            ],
            tolerance_sweep=cover['tolerance_sweep'],
        )
        plot_coverage(cover, train_x, test_x, is_scored, TEST / 'coverage_L2S11.png')
    except Exception as exc:  # recorded, not hidden; scores are already saved
        result['coverage'] = dict(error=repr(exc))
    try:
        plot_test(rows, metrics, TEST / 'predictions_L2S11.png')
    except Exception as exc:
        result['plot_error'] = repr(exc)
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    save_json(TEST / 'result.json', result)

    # 5b. Unlabelled L1S11 plausibility check.
    late_cycles = protocol['sanity_check']['checkpoints_cycles']
    l1 = {c['cycles']: c for c in l1s11}
    require(all(c in l1 for c in late_cycles + [100000]), 'Missing L1S11 sanity checkpoints')
    late = [l1[c] for c in late_cycles]
    late_pred = fitted[model].predict(matrix(late, model, input_set, protocol))
    at_100k = float(fitted[model].predict(matrix([l1[100000]], model, input_set, protocol))[0])
    criteria = sanity_criteria(late_pred, at_100k, y_train, protocol)
    slope = float(np.polyfit(late_cycles, late_pred, 1)[0])
    ranges = {
        c: [float(train_x[:, i].min()), float(train_x[:, i].max())] for i, c in enumerate(cols)
    }
    sanity = dict(
        model=model,
        input_set=input_set,
        late_cycles=late_cycles,
        late_predictions=[float(v) for v in late_pred],
        prediction_at_100k=at_100k,
        criteria=criteria,
        descriptive=dict(
            slope_per_cycle=slope,
            late_features=[{c: l1[k][c] for c in ['cycles'] + cols} for k in late_cycles],
            training_feature_ranges=ranges,
        ),
    )
    save_json(SANITY / 'result.json', sanity)
    print(
        json.dumps(
            dict(
                test=result,
                sanity=dict(
                    criteria=criteria, slope=slope, late_predictions=sanity['late_predictions']
                ),
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == '__main__':
    main()
