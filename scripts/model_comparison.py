"""Run the predeclared exploratory specimen-held-out regression comparison."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time
import warnings

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.io import loadmat
import sklearn
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor
from threadpoolctl import threadpool_info, threadpool_limits

from common import (
    require_not_recorded,
    ROOT,
    digest,
    load_experiment_v1,
    read_csv,
    require,
    save_json,
    snapshot,
    write_csv as save_csv,
)
from reproduce_results import read_checkpoints
from repeat_sensitivity import verify_git_exclusions

BASELINE = ROOT / 'results/baseline'
RECORDED = ROOT / 'results/model_comparison'
CONFIG_PATH = ROOT / 'config/model_comparison.json'
PROTOCOL_PATH = ROOT / 'docs/model_comparison_protocol.md'
CONFIG = json.loads(CONFIG_PATH.read_text())
EXPERIMENT = load_experiment_v1()
MODEL_NAMES = tuple(CONFIG['models'])


def acquisition_eligible(record):
    """Return whether a recorded recording row passes the v1 acquisition gate.

    The gate deliberately never reads the target, its availability or the
    historical target-dependent ``eligible`` flag.

    Parameters
    ----------
    record : dict
        One row of ``results/baseline/recordings.csv`` (string values).

    Returns
    -------
    bool
        ``True`` if cycles are positive, the condition is Loaded, the load, path
        settings, sampling rate and signal lengths match ``config/experiment_v1.json``
        and both signals are finite and nonconstant; ``False`` otherwise, including
        for malformed rows.
    """
    settings = EXPERIMENT['specimens'][record['specimen']]
    low, high = EXPERIMENT['load_window_kips']
    try:
        valid = (
            float(record['cycles']) > 0
            and record['condition'].strip().casefold() == EXPERIMENT['condition']
            and low <= float(record['load_kips']) <= high
            and float(record['gain']) == settings['gain']
            and float(record['amplitude']) == settings['amplitude']
            and float(record['sampling_rate']) == EXPERIMENT['sampling_rate']
        )
        # These fields in the original inventory describe the unique requested 1/7/150 path.
        for channel in ('signal_actuator', 'signal_sensor'):
            valid = valid and float(record[channel + '_length']) == EXPERIMENT['signal_length']
            valid = valid and str(record[channel + '_nonfinite']) == 'False'
            valid = valid and str(record[channel + '_constant']) == 'False'
        return bool(valid)
    except (ValueError, KeyError, TypeError):
        return False


def select_reference_candidates(recordings):
    """Select each specimen's earliest acquisition-eligible checkpoint, label-blind.

    Parameters
    ----------
    recordings : list of dict
        Rows of ``results/baseline/recordings.csv``.

    Returns
    -------
    references : dict
        ``{specimen: [rows at the earliest eligible cycle, sorted by filename]}``.
    candidates : list of dict
        Every acquisition-eligible row.

    Raises
    ------
    ValueError
        If a specimen has no acquisition-eligible recording.
    """
    # Label-blind audit: candidates come from acquisition rules alone, so a match
    # with the baseline shows the recorded references did not depend on labels.
    candidates = [r for r in recordings if acquisition_eligible(r)]
    references = {}
    for specimen in EXPERIMENT['specimens']:
        local = [r for r in candidates if r['specimen'] == specimen]
        require(bool(local), f'No acquisition-eligible reference: {specimen}')
        earliest = min(float(r['cycles']) for r in local)
        references[specimen] = sorted(
            [r for r in local if float(r['cycles']) == earliest], key=lambda r: r['filename']
        )
    return references, candidates


def audit_references(data_root, output):
    """Recheck the selected reference recordings directly from the MAT files.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.
    output : pathlib.Path
        Folder for ``reference_audit.csv`` and ``reference_candidates.csv``.

    Returns
    -------
    list of dict
        One audit row per specimen comparing the label-blind selection with the
        recorded references and denominators.

    Raises
    ------
    ValueError
        If a reference waveform or its settings are invalid, or the label-blind
        references differ from the recorded ones (the run halts; history is kept).
    """
    records = read_csv(BASELINE / 'recordings.csv')
    selected, candidates = select_reference_candidates(records)
    rows = []
    refs = {r['specimen']: r for r in read_csv(BASELINE / 'references.csv')}
    for specimen, group in selected.items():
        features = []
        folder = EXPERIMENT['specimens'][specimen]['folder']
        path_rule = EXPERIMENT['path']
        wanted = (path_rule['actuator'], path_rule['sensor'], path_rule['frequency'])
        low, high = EXPERIMENT['load_window_kips']
        for r in group:
            coupon = loadmat(data_root / folder / 'PZT-data' / r['filename'], simplify_cells=True)[
                'coupon'
            ]
            paths = coupon['path_data']
            if isinstance(paths, dict):
                paths = [paths]
            matches = [p for p in paths if (p['actuator'], p['sensor'], p['frequency']) == wanted]
            require(len(matches) == 1, 'Ambiguous reference path')
            p = matches[0]
            require(
                float(coupon['cycles']) == float(r['cycles'])
                and str(coupon['condition']).strip().casefold() == EXPERIMENT['condition']
                and low <= float(coupon['load']) <= high,
                'Reference acquisition mismatch',
            )
            require(
                all(float(p[f]) == float(r[f]) for f in ('gain', 'amplitude', 'sampling_rate')),
                'Reference settings mismatch',
            )
            for channel in ('signal_actuator', 'signal_sensor'):
                x = np.asarray(p[channel], dtype=float).ravel()
                require(
                    len(x) == EXPERIMENT['signal_length']
                    and np.isfinite(x).all()
                    and np.ptp(x) > 0,
                    'Invalid reference waveform',
                )
            x = np.asarray(p['signal_sensor'], dtype=float).ravel()
            features.append([float(np.sqrt(np.mean((x - x.mean()) ** 2))), float(np.ptp(x))])
        rms, ptp = np.median(features, axis=0)
        reference = refs[specimen]
        filenames = '; '.join(r['filename'] for r in group)
        preserved = (
            filenames == reference['filenames']
            and float(group[0]['cycles']) == float(reference['cycles'])
            and rms == float(reference['rms_denominator'])
            and ptp == float(reference['ptp_denominator'])
        )
        rows.append(
            dict(
                specimen=specimen,
                cycles=int(float(group[0]['cycles'])),
                selected_files=filenames,
                rms_denominator=rms,
                ptp_denominator=ptp,
                baseline_files=reference['filenames'],
                baseline_rms=reference['rms_denominator'],
                baseline_ptp=reference['ptp_denominator'],
                matches_baseline=preserved,
                target_used_for_selection=False,
            )
        )
    save_csv(output / 'reference_audit.csv', rows)
    fields = (
        'specimen',
        'filename',
        'cycles',
        'condition',
        'load_kips',
        'gain',
        'amplitude',
        'sampling_rate',
    )
    save_csv(output / 'reference_candidates.csv', [{f: r[f] for f in fields} for r in candidates])
    require(
        all(r['matches_baseline'] for r in rows),
        'Target-independent references differ: see reference_audit.csv; historical data unchanged',
    )
    return rows


def build_model(name, seed=None):
    """Construct one predeclared, unfitted comparator from ``config/model_comparison.json``.

    Parameters
    ----------
    name : str
        Model name (a key of ``CONFIG['models']``).
    seed : int, optional
        MLP random seed; must be one of the predeclared seeds.

    Returns
    -------
    sklearn.base.RegressorMixin
        A ``Pipeline`` (input scaler or passthrough, then the model). SVR and MLP
        are wrapped in ``TransformedTargetRegressor`` with a target ``StandardScaler``.

    Raises
    ------
    ValueError
        If an MLP seed is not predeclared.
    """
    params = dict(CONFIG['models'][name])
    classes = {
        'LinearRegression': LinearRegression,
        'log_cycle_OLS': LinearRegression,
        'DecisionTreeRegressor': DecisionTreeRegressor,
        'SVR': SVR,
        'MLPRegressor': MLPRegressor,
        'DummyRegressor': DummyRegressor,
    }
    if name == 'MLPRegressor':
        require(seed in CONFIG['mlp_seeds'], 'Use only predeclared MLP seeds')
        params['hidden_layer_sizes'] = tuple(params['hidden_layer_sizes'])
        params['random_state'] = seed
    # Trees and the mean predictor are scale-invariant. For the others the scaler is
    # a pipeline step, so it is fitted on the training specimen only.
    scale = (
        'passthrough' if name in ('DecisionTreeRegressor', 'DummyRegressor') else StandardScaler()
    )
    pipeline = Pipeline([('scale', scale), ('model', classes[name](**params))])
    # SVR and MLP also see a standardised target (fitted on training targets only);
    # predictions are transformed back to published-index units.
    return (
        TransformedTargetRegressor(regressor=pipeline, transformer=StandardScaler())
        if name in ('SVR', 'MLPRegressor')
        else pipeline
    )


def split_rows(rows, train_name, evaluation_name):
    """Split checkpoints into training and evaluation specimens, excluding references.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows of both specimens.
    train_name, evaluation_name : str
        Training and evaluation specimen names.

    Returns
    -------
    train, evaluation : list of dict
        Non-reference checkpoints of each specimen.

    Raises
    ------
    ValueError
        If the specimens are equal, the specimen set is unexpected, or the counts
        differ from ``config/experiment_v1.json``.
    """
    require(train_name != evaluation_name, 'Training and evaluation specimens must differ')
    specimens = EXPERIMENT['specimens']
    require({r['specimen'] for r in rows} == set(specimens), 'Unexpected specimen set')
    # A whole specimen on each side; reference checkpoints never enter fit or score.
    train = [r for r in rows if r['specimen'] == train_name and not r['is_reference']]
    evaluation = [r for r in rows if r['specimen'] == evaluation_name and not r['is_reference']]
    require(
        len(train) == specimens[train_name]['non_reference_checkpoints']
        and len(evaluation) == specimens[evaluation_name]['non_reference_checkpoints'],
        'Checkpoint count changed',
    )
    return train, evaluation


def matrix(rows, name):
    """Build the input matrix for a model.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows.
    name : str
        Model name; ``log_cycle_OLS`` uses ``log10_cycles``, all others the
        configured relative RMS and relative peak-to-peak.

    Returns
    -------
    numpy.ndarray
        ``(n_rows, n_inputs)`` float matrix.
    """
    fields = ['log10_cycles'] if name == 'log_cycle_OLS' else CONFIG['inputs']
    return np.array([[r[f] for f in fields] for r in rows], dtype=float)


def fitted_parts(model):
    """Return the fitted input pipeline and target scaler of a model.

    Parameters
    ----------
    model : sklearn estimator
        Output of :func:`build_model` after fitting.

    Returns
    -------
    pipeline : sklearn.pipeline.Pipeline
        Fitted input pipeline.
    target_scaler : sklearn.preprocessing.StandardScaler or None
        Fitted target scaler for SVR/MLP, otherwise ``None``.
    """
    if isinstance(model, TransformedTargetRegressor):
        return model.regressor_, model.transformer_
    return model, None


def fit_direction(rows, train_name, evaluation_name, name, seed=None):
    """Fit one comparator on one specimen and predict both specimens.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows of both specimens.
    train_name, evaluation_name : str
        Training and evaluation specimens.
    name : str
        Model name.
    seed : int, optional
        MLP seed.

    Returns
    -------
    tuple
        ``(model, train_rows, evaluation_rows, train_predictions,
        evaluation_predictions, caught_warnings)``.
    """
    train, evaluation = split_rows(rows, train_name, evaluation_name)
    x, xt = matrix(train, name), matrix(evaluation, name)
    y = np.array([r['published_index'] for r in train])
    model = build_model(name, seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model.fit(x, y)
    return model, train, evaluation, model.predict(x), model.predict(xt), caught


def scores(y, predicted):
    """Compute evaluation metrics in published-index units.

    Parameters
    ----------
    y : numpy.ndarray
        Observed targets.
    predicted : numpy.ndarray
        Predictions.

    Returns
    -------
    dict
        ``MAE``, ``RMSE``, ``R2``, ``mean_residual`` (prediction minus
        observation), ``min_prediction`` and ``max_abs_residual``.
    """
    residual = predicted - y
    return dict(
        MAE=float(mean_absolute_error(y, predicted)),
        RMSE=float(np.sqrt(mean_squared_error(y, predicted))),
        R2=float(r2_score(y, predicted)),
        mean_residual=float(residual.mean()),
        min_prediction=float(min(predicted)),
        max_abs_residual=float(max(abs(residual))),
    )


def warning_rows(caught, info, phase, repetition):
    """Convert caught warnings into export rows.

    Parameters
    ----------
    caught : list of warnings.WarningMessage
        Warnings recorded during a fit.
    info : dict
        Direction, model and seed identifiers copied into each row.
    phase : str
        ``'reported_fit'``, ``'warmup'`` or ``'timed_fit_predict'``.
    repetition : int
        Repetition index (negative for warm-ups).

    Returns
    -------
    list of dict
        One row per warning, flagging convergence warnings.
    """
    return [
        dict(
            **info,
            phase=phase,
            repetition=repetition,
            category=w.category.__name__,
            is_convergence=issubclass(w.category, ConvergenceWarning),
            message=str(w.message),
        )
        for w in caught
    ]


def benchmark(name, seed, train, evaluation, info):
    """Time fresh fits and batch predictions for one model, direction and seed.

    Parameters
    ----------
    name : str
        Model name.
    seed : int or None
        MLP seed.
    train, evaluation : list of dict
        Training and evaluation checkpoints.
    info : dict
        Identifiers copied into each row.

    Returns
    -------
    samples : list of dict
        Raw per-repetition fit and per-batch prediction times (ms).
    summary : dict
        Median, 25th and 75th percentiles of both timings.
    notices : list of dict
        Warnings raised during warm-up and timed fits.
    """
    x, xt = matrix(train, name), matrix(evaluation, name)
    y = np.array([r['published_index'] for r in train])
    samples, notices = [], []
    timing = CONFIG['timing']
    # Negative repetitions are untimed warm-ups (imports, caches). Every repetition
    # fits a fresh estimator so no state carries over between samples.
    for rep in range(-timing['warmups'], timing['repetitions']):
        estimator = build_model(name, seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            start = time.perf_counter()
            estimator.fit(x, y)
            fit_ms = 1000 * (time.perf_counter() - start)
            start = time.perf_counter()
            # A single predict on about 12 rows is near timer resolution; average many calls.
            for _ in range(timing['prediction_calls_per_repeat']):
                estimator.predict(xt)
            predict_ms = (
                1000 * (time.perf_counter() - start) / timing['prediction_calls_per_repeat']
            )
        notices.extend(
            warning_rows(caught, info, 'warmup' if rep < 0 else 'timed_fit_predict', rep)
        )
        if rep >= 0:
            samples.append(
                dict(
                    **info,
                    repetition=rep,
                    train_n=len(train),
                    evaluation_batch_n=len(evaluation),
                    fit_ms=fit_ms,
                    predict_batch_ms=predict_ms,
                )
            )
    summary = dict(info)
    for field in ('fit_ms', 'predict_batch_ms'):
        values = [r[field] for r in samples]
        for suffix, percentile in (('median', 50), ('q25', 25), ('q75', 75)):
            summary[f'{field}_{suffix}'] = float(np.percentile(values, percentile))
    return samples, summary, notices


def plot_results(predictions, output):
    """Save prediction and residual plots for both directions.

    Parameters
    ----------
    predictions : list of dict
        Prediction rows for every model, seed and split.
    output : pathlib.Path
        Folder for ``predictions_*.png`` and ``residuals_*.png``.
    """
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    markers = ['o', 's', '^', 'D', 'v']
    colours = ['#24628a', '#af681b', '#5d6d35', '#91546d', '#555555']
    values = [r[k] for r in predictions for k in ('observed', 'predicted')]
    span = max(values) - min(values)
    limits = (min(values) - 0.06 * span, max(values) + 0.06 * span)
    residual_max = max(abs(r['residual']) for r in predictions) * 1.08
    for train, evaluation in CONFIG['directions']:
        local = [r for r in predictions if r['train_specimen'] == train]
        for kind in ('predictions', 'residuals'):
            fig, axes = plt.subplots(2, 3, figsize=(14, 9), layout='constrained')
            for ax, name in zip(axes.flat, MODEL_NAMES):
                ps = [r for r in local if r['model'] == name]
                seeds = CONFIG['mlp_seeds'] if name == 'MLPRegressor' else ['']
                for i, seed in enumerate(seeds):
                    for split in ('training', 'evaluation'):
                        selected = [r for r in ps if r['seed'] == seed and r['split'] == split]
                        ax.scatter(
                            [
                                r['observed' if kind == 'predictions' else 'cycles']
                                for r in selected
                            ],
                            [
                                r['predicted' if kind == 'predictions' else 'residual']
                                for r in selected
                            ],
                            marker=markers[i],
                            s=27,
                            alpha=0.65,
                            facecolors='none' if split == 'training' else colours[i],
                            edgecolors=colours[i],
                            label=f'{split}' + (f' seed {seed}' if seed != '' else ''),
                        )
                ax.set_title(name)
                ax.grid(True, color='#dddddd', linewidth=0.5)
                if kind == 'predictions':
                    ax.plot(limits, limits, '--', color='#555555', lw=1)
                    ax.set(
                        xlim=limits,
                        ylim=limits,
                        xlabel='Observed published index',
                        ylabel='Predicted index',
                    )
                    ax.set_aspect('equal', adjustable='box')
                else:
                    ax.axhline(0, color='#555555', linestyle='--', linewidth=1)
                    ax.set(
                        xscale='log',
                        ylim=(-residual_max, residual_max),
                        xlabel='Cycles (log scale)',
                        ylabel='Prediction - observation',
                    )
                if name == 'MLPRegressor':
                    ax.legend(fontsize=7, ncol=2, loc='best')
                elif name == 'LinearRegression':
                    ax.legend(fontsize=8)
            fig.suptitle(
                f'{train} -> {evaluation}: exploratory specimen-held-out validation\n'
                'Hollow = training; filled = evaluation. Reference checkpoints excluded. All MLP '
                'seeds shown.',
                fontsize=12,
            )
            fig.savefig(output / f'{kind}_{train}_to_{evaluation}.png', dpi=150)
            plt.close(fig)


def main(argv=None):
    """Run the reference audit, all predeclared fits, timings, plots and exports.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If any integrity, reproduction or preservation check fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results/rebuilt/model_comparison',
        help='New output folder; recorded results folders are refused.',
    )
    args = parser.parse_args(argv)
    data_root = args.data_root.resolve()
    out = require_not_recorded(args.output)
    require(
        all((data_root / p).is_dir() for p in ('Layup1', 'Layup2', 'Layup3')), 'Invalid data root'
    )
    recorded = [BASELINE, ROOT / 'results/repeat_sensitivity', RECORDED]
    require(
        not any(out == d or d in out.parents or out in d.parents for d in recorded)
        and data_root not in out.parents,
        'Choose a new output folder outside recorded results and data',
    )
    out.mkdir(parents=True, exist_ok=True)
    protected = [p for directory in recorded for p in directory.rglob('*') if p.is_file()]
    # Hash every recorded file now and again at the end: the run must leave the
    # record untouched.
    preserved = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
    scope = data_root.parent
    source_paths = sorted(p for p in scope.rglob('*') if p.is_file())
    archive = scope.parent / (scope.name + '.zip')
    if archive.exists():
        source_paths.append(archive)
    inventory = snapshot(source_paths, scope.parent)
    git_checks = verify_git_exclusions(source_paths, scope, archive)
    receipt = dict(
        started_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=digest(PROTOCOL_PATH),
        config_sha256=digest(CONFIG_PATH),
        checkpoint_table_sha256=digest(BASELINE / 'checkpoint_features.csv'),
        recorded_references_sha256=digest(BASELINE / 'references.csv'),
        configuration=CONFIG,
    )
    save_json(out / 'protocol_receipt.json', receipt)  # Before any model fit or score.
    source_hashes = json.loads((BASELINE / 'source_hashes.json').read_text())
    require(
        all(digest(data_root / p) == h for p, h in source_hashes.items()),
        'Source MAT hashes changed',
    )
    audit_references(data_root, out)
    print(
        'Target-independent references match baseline. Starting predeclared model fits.', flush=True
    )
    rows = read_checkpoints(BASELINE / 'checkpoint_features.csv')
    old_predictions = read_csv(BASELINE / 'predictions.csv')
    metrics, predictions, notices, fits, timing_samples, timing_summary, preprocessing = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    resolved = {}
    # One numerical-library thread: fits are reproducible and timings do not depend
    # on the core count.
    with threadpool_limits(limits=CONFIG['timing']['threads']):
        environment = dict(
            python=platform.python_version(),
            platform=platform.platform(),
            processor=platform.processor(),
            numpy=np.__version__,
            scipy=scipy.__version__,
            sklearn=sklearn.__version__,
            matplotlib=matplotlib.__version__,
            numerical_threadpools=threadpool_info(),
        )
        for train_name, evaluation_name in CONFIG['directions']:
            for name in MODEL_NAMES:
                for seed in (CONFIG['mlp_seeds'] if name == 'MLPRegressor' else [None]):
                    info = dict(
                        train_specimen=train_name,
                        evaluation_specimen=evaluation_name,
                        model=name,
                        seed='' if seed is None else seed,
                    )
                    model, train, evaluation, train_pred, eval_pred, caught = fit_direction(
                        rows, train_name, evaluation_name, name, seed
                    )
                    notices.extend(warning_rows(caught, info, 'reported_fit', 0))
                    resolved[f'{name}:{seed}'] = build_model(name, seed).get_params(deep=True)
                    pipeline, target_scaler = fitted_parts(model)
                    scaler = pipeline.named_steps['scale']
                    learner = pipeline.named_steps['model']
                    preprocessing.append(
                        dict(
                            **info,
                            training_cycles=[r['cycles'] for r in train],
                            evaluation_cycles=[r['cycles'] for r in evaluation],
                            input_mean=None if scaler == 'passthrough' else scaler.mean_.tolist(),
                            input_scale=None if scaler == 'passthrough' else scaler.scale_.tolist(),
                            input_n=(
                                None if scaler == 'passthrough' else int(scaler.n_samples_seen_)
                            ),
                            target_mean=(
                                None if target_scaler is None else target_scaler.mean_.tolist()
                            ),
                            target_scale=(
                                None if target_scaler is None else target_scaler.scale_.tolist()
                            ),
                            target_n=(
                                None
                                if target_scaler is None
                                else int(target_scaler.n_samples_seen_)
                            ),
                        )
                    )
                    fits.append(
                        dict(
                            **info,
                            iterations=getattr(learner, 'n_iter_', ''),
                            loss=getattr(learner, 'loss_', ''),
                            convergence_warnings=sum(
                                issubclass(w.category, ConvergenceWarning) for w in caught
                            ),
                        )
                    )
                    for split, observations, estimated in [
                        ('training', train, train_pred),
                        ('evaluation', evaluation, eval_pred),
                    ]:
                        y = np.array([r['published_index'] for r in observations])
                        metrics.append(
                            dict(**info, split=split, n=len(observations), **scores(y, estimated))
                        )
                        for r, p in zip(observations, estimated):
                            predictions.append(
                                dict(
                                    **info,
                                    split=split,
                                    specimen=r['specimen'],
                                    cycles=r['cycles'],
                                    observed=r['published_index'],
                                    predicted=float(p),
                                    residual=float(p - r['published_index']),
                                )
                            )
                    # sklearn OLS must reproduce the baseline's own OLS predictions exactly before
                    # the other model families are trusted on the same inputs.
                    if name in ('LinearRegression', 'log_cycle_OLS'):
                        old_name = (
                            'relative_rms_and_ptp' if name == 'LinearRegression' else 'log10_cycles'
                        )
                        lookup = {
                            int(r['cycles']): float(r['predicted_index'])
                            for r in old_predictions
                            if r['train_specimen'] == train_name and r['model'] == old_name
                        }
                        np.testing.assert_allclose(
                            eval_pred,
                            [lookup[r['cycles']] for r in evaluation],
                            rtol=1e-9,
                            atol=1e-10,
                        )
                    samples, summary, timed_warnings = benchmark(
                        name, seed, train, evaluation, info
                    )
                    timing_samples.extend(samples)
                    timing_summary.append(summary)
                    notices.extend(timed_warnings)
    summary = []
    for train_name, evaluation_name in CONFIG['directions']:
        for name in MODEL_NAMES:
            for split in ('training', 'evaluation'):
                selected = [
                    r
                    for r in metrics
                    if r['train_specimen'] == train_name
                    and r['model'] == name
                    and r['split'] == split
                ]
                row = dict(
                    train_specimen=train_name,
                    evaluation_specimen=evaluation_name,
                    model=name,
                    split=split,
                    seeds=len(selected),
                    n=selected[0]['n'],
                )
                for field in ('MAE', 'RMSE', 'R2', 'mean_residual'):
                    values = [r[field] for r in selected]
                    row[field] = float(np.median(values))
                    row[field + '_min'] = min(values)
                    row[field + '_max'] = max(values)
                summary.append(row)
    for filename, values in [
        ('metrics.csv', metrics),
        ('summary.csv', summary),
        ('predictions.csv', predictions),
        ('fit_diagnostics.csv', fits),
        ('timing_samples.csv', timing_samples),
        ('timing_summary.csv', timing_summary),
    ]:
        save_csv(out / filename, values)
    save_csv(
        out / 'warnings.csv',
        notices,
        [
            'train_specimen',
            'evaluation_specimen',
            'model',
            'seed',
            'phase',
            'repetition',
            'category',
            'is_convergence',
            'message',
        ],
    )
    save_json(out / 'preprocessing_audit.json', preprocessing)
    save_json(out / 'resolved_parameters.json', resolved)
    save_json(out / 'environment.json', environment)
    plot_results(predictions, out)
    require(
        preserved == {p.relative_to(ROOT).as_posix(): digest(p) for p in protected},
        'Historical outputs changed',
    )
    after_paths = sorted(p for p in scope.rglob('*') if p.is_file())
    if archive.exists():
        after_paths.append(archive)
    require(inventory == snapshot(after_paths, scope.parent), 'Source metadata changed')
    require(
        all(digest(data_root / p) == h for p, h in source_hashes.items()),
        'Source MAT contents changed',
    )
    require(
        receipt['protocol_sha256'] == digest(PROTOCOL_PATH)
        and receipt['config_sha256'] == digest(CONFIG_PATH),
        'Protocol changed during execution',
    )
    save_json(
        out / 'verification.json',
        dict(
            git_exclusions=git_checks,
            source_metadata_unchanged=len(inventory),
            surveyed_mat_hashes_unchanged=len(source_hashes),
            historical_outputs_hashes_unchanged=preserved,
            target_independent_references_preserved=True,
            sklearn_ols_matches_baseline=True,
            convergence_warnings=sum(r['is_convergence'] for r in notices),
            completed_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )
    lines = [
        '# Exploratory specimen-held-out model comparison',
        '',
        'MAE is primary. Both specimens have been used in development; neither is an untouched '
        'final test set.',
        'MLP entries are the median [minimum, maximum] across all five predeclared seeds, not an '
        'ensemble.',
        '',
        '| Train -> evaluate | Model | Evaluation MAE | RMSE | R2 | Training MAE |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for r in summary:
        if r['split'] != 'evaluation':
            continue
        training = next(
            s
            for s in summary
            if s['split'] == 'training'
            and s['model'] == r['model']
            and s['train_specimen'] == r['train_specimen']
        )
        cells = []
        for field in ('MAE', 'RMSE', 'R2'):
            cell = f'{r[field]:.6f}'
            if r['model'] == 'MLPRegressor':
                cell += f" [{r[field+'_min']:.6f}, {r[field+'_max']:.6f}]"
            cells.append(cell)
        lines.append(
            f"| {r['train_specimen']} -> {r['evaluation_specimen']} | {r['model']} | "
            + ' | '.join(cells)
            + f" | {training['MAE']:.6f} |"
        )
    lines += [
        '',
        'Full training/evaluation MAE, RMSE and R2 for every seed: metrics.csv. Residual = '
        'prediction - observation.',
        'Reference selection ignores target values/availability and reproduces both original '
        'cycle-1 references exactly.',
        f"Convergence warning records (reported, warm-up and timed fits): "
        f"{sum(r['is_convergence'] for r in notices)}.",
        'Timing: one warm-up, 15 fresh fits; each prediction timing averages 100 complete '
        'held-out-batch calls.',
        'Reported timing medians/IQRs are local warm-process measurements with one '
        'numerical-library thread.',
        'Raw-workflow cProfile results are separately stored under raw_profile; they are not '
        'model runtimes.',
        '',
        'Limitations: two correlated specimen trajectories, few checkpoints, acquisition '
        'differences,',
        'unvalidated published stiffness index and prior development exposure. No '
        'evaluation-based tuning.',
        'Negative R2 or predictions are retained. Seed ranges are not confidence intervals.',
    ]
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    main()
