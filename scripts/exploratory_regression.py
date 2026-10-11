"""Rebuild the two-specimen experiment from the external NASA dataset.
Dependencies: numpy, scipy, matplotlib. No tuning, imputation, or source writes.
Reference measurements are chronological anchors, not undamaged baselines.

The reference checkpoint is chosen label-blind: it is the earliest checkpoint
with an acquisition-eligible recording, whether or not that checkpoint carries
a published label. Fitting and scoring use only labelled, non-reference
checkpoints. Specimen constants come from ``config/experiment_v1.json``.

Example
-------
``python scripts/exploratory_regression.py --data-root "data/2.+Composites/2. Composites"``
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from common import ROOT, load_experiment_v1, require, scalar, waveform_features, write_csv
from raw_loading import iter_coupons

LABEL_REASON = 'missing/nonfinite/nonscalar published index'
"""Exclusion reason for a missing label; the only reason that is not acquisition-related."""

MODELS = {
    'log10_cycles': ['log10_cycles'],
    'relative_rms': ['relative_rms'],
    'relative_rms_and_ptp': ['relative_rms', 'relative_ptp'],
}
"""The three fixed OLS predictor sets of the first experiment."""

FEATURES = ('mean_centred_rms', 'peak_to_peak')
SIGNAL_FLAGS = (
    'signal_actuator_nonfinite',
    'signal_actuator_constant',
    'signal_sensor_nonfinite',
    'signal_sensor_constant',
)


def is_jump(specimen, cycle, experiment):
    """Return whether a checkpoint is the retained published-label jump.

    Parameters
    ----------
    specimen : str
        Specimen name.
    cycle : float or None
        Cycle count.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    bool
        ``True`` for the configured jump checkpoint (L1S12 at 30,000 cycles).
    """
    jump = experiment['integrity']['retained_jump']
    return specimen == jump['specimen'] and cycle == jump['cycles']


def assess_recording(coupon, specimen, filename, experiment):
    """Screen one PZT recording and compute its receiver features.

    Parameters
    ----------
    coupon : dict
        The ``coupon`` structure of one MAT file (``simplify_cells=True``).
    specimen : str
        Specimen name, a key of ``experiment['specimens']``.
    filename : str
        MAT file name, recorded for provenance.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    dict
        Exported fields (historical column order) plus private fields starting
        with ``_``: ``_acquisition_eligible`` (all rules except the label rule)
        and ``_rms``/``_ptp`` (features of any acquisition-eligible recording).
        ``eligible`` keeps its historical meaning: acquisition-eligible *and*
        labelled. Public ``peak_to_peak``/``mean_centred_rms`` are filled only for
        ``eligible`` rows, as in the recorded tables.

    Notes
    -----
    The acquisition decision never depends on the label; the label is read only
    to report it and to add the label reason to ``exclusion_reasons``.
    """
    settings = experiment['specimens'][specimen]
    path_rule = experiment['path']
    cycle, load = scalar(coupon.get('cycles', [])), scalar(coupon.get('load', []))
    label = scalar(coupon.get('straingage_data', {}).get('stiffness_degradation', []))
    r = dict(
        specimen=specimen,
        filename=filename,
        cycles=cycle,
        load_kips=load,
        published_index=label,
        condition=coupon.get('condition', ''),
        published_jump_flag=is_jump(specimen, cycle, experiment),
        peak_to_peak=None,
        mean_centred_rms=None,
    )
    reasons = []
    if cycle is None or cycle <= 0:
        reasons.append('not a positive-cycle checkpoint')
    if label is None:
        reasons.append(LABEL_REASON)
    if str(r['condition']).strip().casefold() != experiment['condition']:
        reasons.append('condition is not Loaded')
    low, high = experiment['load_window_kips']
    if load is None or not low <= load <= high:
        reasons.append(f'load outside {low}-{high} kips')
    paths = coupon.get('path_data', [])
    if isinstance(paths, dict):
        paths = [paths]
    wanted = (path_rule['actuator'], path_rule['sensor'], path_rule['frequency'])
    matches = [
        p for p in paths if (p.get('actuator'), p.get('sensor'), p.get('frequency')) == wanted
    ]
    sensor = None
    if len(matches) != 1:
        reasons.append('requested path missing or ambiguous')
    else:
        p = matches[0]
        for field, required in [
            ('gain', settings['gain']),
            ('amplitude', settings['amplitude']),
            ('sampling_rate', experiment['sampling_rate']),
        ]:
            r[field] = scalar(p.get(field, []))
            if r[field] != required:
                reasons.append(f'{field} != {required}')
        for field in ('signal_actuator', 'signal_sensor'):
            x = np.asarray(p.get(field, []), dtype=float).ravel()
            r[field + '_length'] = len(x)
            r[field + '_nonfinite'] = bool(not np.isfinite(x).all())
            r[field + '_constant'] = bool(len(x) and np.isfinite(x).all() and np.all(x == x[0]))
            if len(x) != experiment['signal_length']:
                reasons.append(f"{field} length != {experiment['signal_length']}")
        sensor = np.asarray(p.get('signal_sensor', []), dtype=float).ravel()
    acquisition_ok = not [s for s in reasons if s != LABEL_REASON]
    r['_acquisition_eligible'] = acquisition_ok
    r['_rms'] = r['_ptp'] = None
    if acquisition_ok and np.isfinite(sensor).all():
        r['_rms'], r['_ptp'] = waveform_features(sensor)
        if not reasons:
            r['mean_centred_rms'], r['peak_to_peak'] = r['_rms'], r['_ptp']
    r['eligible'] = not reasons
    r['exclusion_reasons'] = '; '.join(reasons)
    return r


def exclusion_counts(specimen, rows):
    """Count exclusion reasons for one specimen, in order of first appearance.

    Parameters
    ----------
    specimen : str
        Specimen name.
    rows : list of dict
        Outputs of :func:`assess_recording` for that specimen.

    Returns
    -------
    list of dict
        ``{'specimen', 'reason', 'count'}`` rows.
    """
    counts = Counter(s for r in rows for s in r['exclusion_reasons'].split('; ') if s)
    return [dict(specimen=specimen, reason=k, count=v) for k, v in counts.items()]


def select_reference(rows):
    """Choose the reference checkpoint without reading labels.

    Parameters
    ----------
    rows : list of dict
        Outputs of :func:`assess_recording` for one specimen, in file order.

    Returns
    -------
    dict
        ``cycles`` (int), ``filenames`` (``'; '``-joined, file order),
        ``rms_denominator`` and ``ptp_denominator`` (medians across the
        reference checkpoint's acquisition-eligible recordings).

    Raises
    ------
    ValueError
        If no recording is acquisition-eligible or a denominator is not positive.

    Notes
    -----
    Only ``_acquisition_eligible``, ``cycles`` and the private features are read,
    so an earlier unlabelled checkpoint would be chosen over a labelled one.
    """
    candidates = [r for r in rows if r['_acquisition_eligible'] and r['_rms'] is not None]
    require(bool(candidates), 'No acquisition-eligible reference recording')
    first = min(r['cycles'] for r in candidates)
    group = [r for r in candidates if r['cycles'] == first]
    reference = dict(
        cycles=int(first),
        filenames='; '.join(r['filename'] for r in group),
        rms_denominator=float(np.median([r['_rms'] for r in group])),
        ptp_denominator=float(np.median([r['_ptp'] for r in group])),
    )
    require(
        reference['rms_denominator'] > 0 and reference['ptp_denominator'] > 0,
        'Invalid reference denominator',
    )
    return reference


def summarise_checkpoint(specimen, cycle, repeats, experiment):
    """Combine the eligible repeats of one labelled checkpoint.

    Parameters
    ----------
    specimen : str
        Specimen name.
    cycle : float
        Cycle count shared by ``repeats``.
    repeats : list of dict
        Eligible (labelled) recordings at that checkpoint.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    dict
        Checkpoint row with the feature medians across repeats.

    Raises
    ------
    ValueError
        If the repeats carry conflicting labels; labels are never averaged.
    """
    settings = experiment['specimens'][specimen]
    labels = set(r['published_index'] for r in repeats)
    require(len(labels) == 1, f'Conflicting published labels: {specimen}, {cycle}')
    cp = dict(
        specimen=specimen,
        cycles=int(cycle),
        published_index=labels.pop(),
        eligible_repeats=len(repeats),
        filenames='; '.join(r['filename'] for r in repeats),
        load_min_kips=min(r['load_kips'] for r in repeats),
        load_max_kips=max(r['load_kips'] for r in repeats),
        gain=settings['gain'],
        excitation_setting=settings['amplitude'],
        sampling_rate_Hz=experiment['sampling_rate'],
        sample_start=0,
        sample_end_inclusive=experiment['signal_length'] - 1,
        published_jump_flag=any(r['published_jump_flag'] for r in repeats),
    )
    for feature in FEATURES:
        values = [r[feature] for r in repeats if r[feature] is not None]
        cp[feature] = float(np.median(values)) if values else None
        cp[feature + '_valid_repeats'] = len(values)
    return cp


def build_checkpoints(specimen, rows, experiment):
    """Build labelled checkpoint rows and their label-blind reference.

    Parameters
    ----------
    specimen : str
        Specimen name.
    rows : list of dict
        Outputs of :func:`assess_recording` for that specimen.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    checkpoints : list of dict
        Labelled checkpoints in cycle order with relative features. A reference
        checkpoint without a label is included with ``published_index=None``.
    reference : dict
        Output of :func:`select_reference` plus ``specimen``.

    Raises
    ------
    ValueError
        If there are no labelled checkpoints or a checkpoint feature is missing.
    """
    groups = defaultdict(list)
    for r in rows:
        if r['eligible']:
            groups[r['cycles']].append(r)
    cps = [
        summarise_checkpoint(specimen, c, reps, experiment) for c, reps in sorted(groups.items())
    ]
    require(bool(cps), f'No eligible checkpoints: {specimen}')
    ref = select_reference(rows)
    reference = dict(specimen=specimen, **ref)
    if not any(cp['cycles'] == ref['cycles'] for cp in cps):
        # Unlabelled reference: keep its features for normalisation, never for scoring.
        group = [r for r in rows if r['_acquisition_eligible'] and r['cycles'] == ref['cycles']]
        cp = summarise_checkpoint(
            specimen,
            ref['cycles'],
            [
                dict(r, published_index=None, mean_centred_rms=r['_rms'], peak_to_peak=r['_ptp'])
                for r in group
            ],
            experiment,
        )
        cps = sorted(cps + [cp], key=lambda c: c['cycles'])
    for cp in cps:
        require(
            cp['mean_centred_rms'] is not None and cp['peak_to_peak'] is not None,
            'Nonfinite checkpoint features',
        )
        cp['is_reference'] = cp['cycles'] == ref['cycles']
        cp['reference_cycles'] = ref['cycles']
        cp['relative_rms'] = cp['mean_centred_rms'] / ref['rms_denominator']
        cp['relative_ptp'] = cp['peak_to_peak'] / ref['ptp_denominator']
        cp['log10_cycles'] = float(np.log10(cp['cycles']))
    return cps, reference


def fit_ols(train, test, fields):
    """Fit OLS with an intercept on ``train`` and predict ``test``.

    Parameters
    ----------
    train, test : list of dict
        Checkpoint rows; ``published_index`` is read from ``train`` only.
    fields : list of str
        Predictor columns.

    Returns
    -------
    beta : numpy.ndarray
        Intercept followed by slopes.
    prediction : numpy.ndarray
        Unclipped predictions for ``test``.
    condition_number : float
        Ratio of the largest to smallest singular value of the design matrix.

    Raises
    ------
    ValueError
        If the design matrix is rank-deficient.
    AssertionError
        If the least-squares solution disagrees with an independent QR solve
        (``numpy.testing`` checks are not removed by ``python -O``).
    """
    X = np.array([[1.0] + [r[f] for f in fields] for r in train])
    y = np.array([r['published_index'] for r in train])
    Xtest = np.array([[1.0] + [r[f] for f in fields] for r in test])
    beta, _, rank, singular = np.linalg.lstsq(X, y, rcond=None)
    require(rank == X.shape[1], 'Rank-deficient design')
    q, upper = np.linalg.qr(X, mode='reduced')
    np.testing.assert_allclose(beta, np.linalg.solve(upper, q.T @ y), rtol=1e-9, atol=1e-10)
    return beta, Xtest @ beta, float(singular[0] / singular[-1])


def evaluate_transfer(checkpoints, experiment):
    """Fit every model on one specimen and score it on the other, both directions.

    Parameters
    ----------
    checkpoints : list of dict
        Output of :func:`build_checkpoints` for both specimens.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    predictions, metrics, coefficients : list of dict
        Per-checkpoint predictions, MAE/RMSE per model and direction, and fitted
        coefficients. Reference and unlabelled checkpoints are never used.
    """
    predictions, metrics, coefficients = [], [], []
    usable = [r for r in checkpoints if not r['is_reference'] and r['published_index'] is not None]
    for train_name, test_name in experiment['directions']:
        train = [r for r in usable if r['specimen'] == train_name]
        test = [r for r in usable if r['specimen'] == test_name]
        for model, fields in MODELS.items():
            beta, pred, condition = fit_ols(train, test, fields)
            observed = np.array([r['published_index'] for r in test])
            residual = pred - observed
            metrics.append(
                dict(
                    train_specimen=train_name,
                    test_specimen=test_name,
                    model=model,
                    train_checkpoints=len(train),
                    test_checkpoints=len(test),
                    MAE=float(np.mean(abs(residual))),
                    RMSE=float(np.sqrt(np.mean(residual**2))),
                )
            )
            coefficients.append(
                dict(
                    train_specimen=train_name,
                    test_specimen=test_name,
                    model=model,
                    intercept=float(beta[0]),
                    terms='; '.join(fields),
                    slopes='; '.join(format(b, '.17g') for b in beta[1:]),
                    design_condition_number=condition,
                )
            )
            for r, prediction in zip(test, pred):
                predictions.append(
                    dict(
                        train_specimen=train_name,
                        test_specimen=test_name,
                        model=model,
                        cycles=r['cycles'],
                        observed_index=r['published_index'],
                        predicted_index=float(prediction),
                        residual=float(prediction - r['published_index']),
                        published_jump_flag=r['published_jump_flag'],
                    )
                )
    return predictions, metrics, coefficients


def check_integrity(recordings, checkpoints, references, predictions, experiment):
    """Check the configured label exclusion, retained jump and reference exclusion.

    Parameters
    ----------
    recordings, checkpoints, references, predictions : list of dict
        Workflow outputs.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Raises
    ------
    ValueError
        If the missing label was filled, the jump was dropped or changed, or a
        reference checkpoint was scored.
    """
    missing = experiment['integrity']['missing_label']
    jump = experiment['integrity']['retained_jump']
    key = (missing['specimen'], missing['cycles'])
    require(
        not any(
            (r['specimen'], r['cycles']) == key and r['published_index'] is not None
            for r in checkpoints
        ),
        'A missing label was filled',
    )
    require(
        all(
            r['published_index'] is None for r in recordings if (r['specimen'], r['cycles']) == key
        ),
        'Missing-label recordings gained a label',
    )
    require(
        any(
            r['specimen'] == jump['specimen']
            and r['cycles'] == jump['cycles']
            and r['published_index'] == jump['published_index']
            for r in checkpoints
        ),
        'Published jump not retained',
    )
    ref_cycles = {r['specimen']: r['cycles'] for r in references}
    require(
        all(p['cycles'] != ref_cycles[p['test_specimen']] for p in predictions),
        'A reference checkpoint was scored',
    )


def extract(data_root, experiment, workers=1):
    """Read, screen and summarise the PZT files of both specimens.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.
    workers : int, optional
        MAT prefetch workers (1 = serial).

    Returns
    -------
    recordings, checkpoints, references, exclusions : list of dict
        Workflow tables.
    hashes : dict
        SHA-256 of every MAT file read, keyed relative to ``data_root``.
    """
    recordings, checkpoints, references, hashes, exclusions = [], [], [], {}, []
    for specimen, settings in experiment['specimens'].items():
        files = sorted((data_root / settings['folder'] / 'PZT-data').glob(specimen + '_*.mat'))
        local = []
        for path, source_digest, coupon in iter_coupons(files, workers):
            hashes[path.relative_to(data_root).as_posix()] = source_digest
            local.append(assess_recording(coupon, specimen, path.name, experiment))
        recordings.extend(local)
        exclusions.extend(exclusion_counts(specimen, local))
        cps, reference = build_checkpoints(specimen, local, experiment)
        references.append(reference)
        checkpoints.extend(cps)
    return recordings, checkpoints, references, exclusions, hashes


def public(rows):
    """Drop private (``_``-prefixed) fields before export.

    Parameters
    ----------
    rows : list of dict
        Rows possibly containing private fields.

    Returns
    -------
    list of dict
        Copies without private fields.
    """
    return [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]


def save(out, name, rows):
    """Write rows with the union of their keys, in first-appearance order.

    Parameters
    ----------
    out : pathlib.Path
        Output directory.
    name : str
        File name.
    rows : list of dict
        Rows to write.
    """
    keys = list(dict.fromkeys(k for r in rows for k in r))
    write_csv(out / name, rows, keys)


def plot_predictions(predictions, metrics, experiment, path):
    """Plot held-out predictions against observations for every model and direction.

    Parameters
    ----------
    predictions, metrics : list of dict
        Outputs of :func:`evaluate_transfer`.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.
    path : pathlib.Path
        Destination PNG.
    """
    fig, axes = plt.subplots(2, 3, figsize=(14, 9), sharex=True, sharey=True)
    all_values = [p[k] for p in predictions for k in ('observed_index', 'predicted_index')]
    lo, hi = min(all_values), max(all_values)
    pad = (hi - lo) * 0.09
    limits = (lo - pad, hi + pad)
    titles = ['log10(cycle count)', 'Relative RMS', 'Relative RMS + relative peak-to-peak']
    for row, (train_name, test_name) in enumerate(experiment['directions']):
        for col, (model, title) in enumerate(zip(MODELS, titles)):
            ax = axes[row, col]
            ps = [
                p for p in predictions if p['train_specimen'] == train_name and p['model'] == model
            ]
            ax.plot(limits, limits, '--', color='#777777', lw=1, label='Perfect agreement')
            ax.scatter(
                [p['observed_index'] for p in ps],
                [p['predicted_index'] for p in ps],
                color='#24628a',
                s=30,
            )
            for p in ps:
                if p['published_jump_flag']:
                    ax.scatter(
                        p['observed_index'],
                        p['predicted_index'],
                        marker='D',
                        s=65,
                        facecolors='none',
                        edgecolors='#b45e13',
                        linewidths=1.5,
                    )
            m = next(
                m for m in metrics if m['train_specimen'] == train_name and m['model'] == model
            )
            ax.set(
                title=f'{train_name} -> {test_name}\n{title}',
                xlim=limits,
                ylim=limits,
                xlabel='Observed published index',
                ylabel='Predicted index',
            )
            ax.text(
                0.04,
                0.96,
                f"MAE {m['MAE']:.4f}\nRMSE {m['RMSE']:.4f}",
                transform=ax.transAxes,
                va='top',
                fontsize=9,
            )
            ax.grid(True, color='#e0e0e0', lw=0.5)
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_aspect('equal', adjustable='box')
    fig.suptitle('Exploratory two-specimen OLS comparison | held-out checkpoints only', fontsize=14)
    fig.text(
        0.07,
        0.02,
        'Each model includes an intercept. References are excluded from fitting and '
        'scoring; early reference measurements are required.\n'
        'Dashed line: perfect agreement. Orange diamond: retained L1S12 30,000-cycle index jump. '
        'No clipping or label interpolation.',
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def summary_text(recordings, checkpoints, references, metrics, experiment):
    """Compose the plain-text run summary written to ``README.txt``.

    Parameters
    ----------
    recordings, checkpoints, references, metrics : list of dict
        Workflow outputs.
    experiment : dict
        Configuration from :func:`common.load_experiment_v1`.

    Returns
    -------
    str
        Summary text ending with a newline.
    """
    path, (low, high) = experiment['path'], experiment['load_window_kips']
    settings = '; '.join(
        f"{s} gain {v['gain']} / excitation {v['amplitude']}"
        for s, v in experiment['specimens'].items()
    )
    lines = [
        'Exploratory two-specimen comparison requiring an early reference measurement.',
        f"Actuator {path['actuator']} -> receiver {path['sensor']}, nominal {path['frequency']} "
        f"kHz; "
        f'Loaded, {low:.2f}-{high:.2f} kips inclusive.',
        f'{settings}.',
        'Stored sampling rate 1.2e6 unchanged; both signal lengths 2000; samples 0-1999.',
        'Received PTP=max(x)-min(x); RMS=sqrt(mean((x-mean(x))**2)); then median across eligible '
        'repeats.',
        'Relative features = checkpoint median / earliest eligible checkpoint median, selected by '
        'cycle order.',
        'Reference targets are never used in fitting, scoring, or calibration; references are not '
        'assumed undamaged.',
        'All three models use an intercept and equal checkpoint weights. No tuning on the test '
        'specimen.',
        'Missing labels remain missing (including L1S12 20,000); the 30,000-cycle published jump '
        'is retained.',
        'No prediction clipping, filtering, alignment, gain correction, or label interpolation.',
        'Raw waveform units unknown; relative features dimensionless; MAE/RMSE in published-index '
        'units.',
        'Two specimens cannot establish broad transfer performance or distinguish specimen '
        'effects from acquisition-setting effects.',
        'OLS coefficients checked against QR; source SHA-256 hashes verified unchanged.',
        '',
        'References:',
        *[str(r) for r in references],
        '',
        'Coverage:',
    ]
    for specimen in experiment['specimens']:
        rs = [r for r in recordings if r['specimen'] == specimen]
        cps = [r for r in checkpoints if r['specimen'] == specimen]
        flagged = sum(any(r.get(k, False) for k in SIGNAL_FLAGS) for r in rs if r['eligible'])
        lines.append(
            f'{specimen}: {sum(r["eligible"] for r in rs)} eligible recordings; '
            f'{len(cps)} checkpoints; {len(cps)-1} fit/score checkpoints; '
            f'{flagged} eligible recordings with signal flags.'
        )
    lines += ['', 'Held-out metrics:', *[str(m) for m in metrics]]
    return '\n'.join(lines) + '\n'


def parse_args(argv=None):
    """Parse and validate command-line arguments.

    Parameters
    ----------
    argv : list of str, optional
        Arguments; defaults to ``sys.argv[1:]``.

    Returns
    -------
    data_root, output : pathlib.Path
        Resolved dataset root and output directory.
    workers : int
        MAT prefetch workers.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--data-root',
        required=True,
        type=Path,
        help='The extracted 2. Composites directory containing Layup1.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results' / 'rebuilt',
        help='Separate output folder (default: results/rebuilt).',
    )
    parser.add_argument(
        '--workers',
        type=int,
        choices=(1, 4),
        default=1,
        help='MAT prefetch workers; serial remains the default.',
    )
    args = parser.parse_args(argv)
    data_root = args.data_root.expanduser().resolve()
    out = args.output.expanduser().resolve()
    if not (data_root / 'Layup1').is_dir():
        parser.error(f"Cannot find {data_root / 'Layup1'}. Pass the directory containing Layup1.")
    if out == data_root or data_root in out.parents:
        parser.error('Choose an output folder outside the original dataset.')
    baseline = ROOT / 'results' / 'baseline'
    if out == baseline or baseline in out.parents:
        parser.error(
            'results/baseline is the recorded first experiment; choose a new output folder.'
        )
    return data_root, out, args.workers


def main(argv=None):
    """Run extraction, OLS transfer evaluation, integrity checks and exports.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If any integrity check fails, including a changed source MAT file.
    """
    data_root, out, workers = parse_args(argv)
    experiment = load_experiment_v1()
    out.mkdir(parents=True, exist_ok=True)
    recordings, checkpoints, references, exclusions, hashes = extract(
        data_root, experiment, workers
    )
    predictions, metrics, coefficients = evaluate_transfer(checkpoints, experiment)
    check_integrity(recordings, checkpoints, references, predictions, experiment)
    for file, source_digest in hashes.items():
        require(
            hashlib.sha256((data_root / file).read_bytes()).hexdigest() == source_digest,
            f'Source file changed during the run: {file}',
        )
    for name, rows in [
        ('recordings.csv', public(recordings)),
        ('checkpoint_features.csv', checkpoints),
        ('references.csv', references),
        ('predictions.csv', predictions),
        ('metrics.csv', metrics),
        ('coefficients.csv', coefficients),
        ('exclusion_counts.csv', exclusions),
    ]:
        save(out, name, rows)
    (out / 'source_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    plot_predictions(predictions, metrics, experiment, out / 'predicted_vs_observed.png')
    text = summary_text(recordings, checkpoints, references, metrics, experiment)
    (out / 'README.txt').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
