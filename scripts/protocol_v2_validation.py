"""Protocol v2, step 3: validation on L1S11 <-> L1S12 and the frozen model selection.

Only the two development specimens are read; the held-out L2S11 is never
opened by this script. The workflow follows ``docs/protocol_v2.md``:

1. write a receipt (protocol hashes, git commit) before any fit;
2. extract both input sets with joint, label-blind eligibility;
3. fit the six v1 comparators (five MLP seeds) on each input set, both directions;
4. reproduction gate: ``single_path_1_7`` predictions must reproduce
   ``results/model_comparison/predictions.csv`` before any multi-path score is
   written;
5. apply the predeclared worst-direction-MAE selection rule and write
   ``results/protocol_v2/selection.json``.

The recorded run happened once (commit ``6ccee92``). ``--replay`` repeats the
same computation into ``results/rebuilt/protocol_v2_replay/`` and compares every
output with the record, which it never writes; it needs no clean tree.

Examples
--------
``python scripts/protocol_v2_validation.py --data-root "data/2.+Composites/2. Composites"``

``python scripts/protocol_v2_validation.py --data-root "..." --replay``
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import warnings

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

from common import ROOT, digest, load_json, read_csv, require, save_json, write_csv
from model_comparison import build_model
from protocol_v2 import (
    CONTROLS,
    FAMILIES,
    INPUT_SETS,
    PROTOCOL_DOC,
    PROTOCOL_PATH,
    build_checkpoints,
    extract_specimen,
    input_columns,
    load_protocol,
    select_final,
)
from verify_reproduction import check_work_folder, compare_folder, strip_volatile

OUT = ROOT / 'results' / 'protocol_v2' / 'validation'
SELECTION = ROOT / 'results' / 'protocol_v2' / 'selection.json'
REPLAY = ROOT / 'results' / 'rebuilt' / 'protocol_v2_replay'
REPLAY_NOT_COMPARED = {
    'README.md': 'hand-written notes',
    'receipt.json': 'provenance of the run (commit, time, versions), not a computed output',
}
SELECTION_RUN_KEYS = frozenset({'decided_utc', 'validation_git_commit'})
"""Fields of ``selection.json`` that identify the run rather than the decision."""
V1_PREDICTIONS = ROOT / 'results' / 'model_comparison' / 'predictions.csv'
COLOURS = {'single_path_1_7': '#2a78d6', 'multi_path_36': '#eb6834', 'control': '#6b6b6b'}
MARKERS = {'single_path_1_7': 'o', 'multi_path_36': '^', 'control': 's'}


def git_state():
    """Return the current commit and whether tracked files have uncommitted changes.

    Returns
    -------
    dict
        ``commit`` (hex) and ``clean`` (bool; ignored files do not count).
    """
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    # --porcelain ignores git-ignored files, so scratch output under results/rebuilt/
    # does not count as an uncommitted change.
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    return dict(commit=commit, clean=not status.strip())


def design(rows, model, input_set, protocol):
    """Build the feature matrix for one model and input set.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows.
    model : str
        Model name; ``log_cycle_OLS`` uses ``log10_cycles`` regardless of input set.
    input_set : str
        Input-set name.
    protocol : dict
        Output of :func:`protocol_v2.load_protocol`.

    Returns
    -------
    numpy.ndarray
        ``(n_rows, n_features)`` matrix.
    """
    columns = ['log10_cycles'] if model == 'log_cycle_OLS' else input_columns(input_set, protocol)
    return np.array([[r[c] for c in columns] for r in rows], dtype=float)


def fit_predict(model, seed, input_set, train, evaluation, protocol):
    """Fit one predeclared model on training checkpoints and predict both splits.

    Parameters
    ----------
    model : str
        Model name from the v1 configuration.
    seed : int or None
        MLP seed (``None`` for other models).
    input_set : str
        Input-set name.
    train, evaluation : list of dict
        Non-reference labelled checkpoints of the training and evaluation specimens.
    protocol : dict
        Output of :func:`protocol_v2.load_protocol`.

    Returns
    -------
    train_prediction, evaluation_prediction : numpy.ndarray
        Predictions in published-index units.
    convergence_warnings : int
        Number of ``ConvergenceWarning`` raised during the fit.
    """
    # Fit on the training specimen's targets only; evaluation targets are used
    # solely for scoring, after prediction.
    estimator = build_model(model, seed)
    y = np.array([r['published_index'] for r in train])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        estimator.fit(design(train, model, input_set, protocol), y)
    return (
        estimator.predict(design(train, model, input_set, protocol)),
        estimator.predict(design(evaluation, model, input_set, protocol)),
        sum(issubclass(w.category, ConvergenceWarning) for w in caught),
    )


def scores(y, predicted):
    """Return MAE, RMSE, R2 and mean residual (prediction minus observation).

    Parameters
    ----------
    y, predicted : numpy.ndarray
        Observations and predictions.

    Returns
    -------
    dict
        Metric values as floats.
    """
    residual = predicted - y
    return dict(
        MAE=float(np.mean(np.abs(residual))),
        RMSE=float(np.sqrt(np.mean(residual**2))),
        R2=float(1 - np.sum(residual**2) / np.sum((y - y.mean()) ** 2)),
        mean_residual=float(residual.mean()),
    )


def _gate_key(row):
    """Return the key that identifies one v1 prediction (direction, model, seed, split, cycle)."""
    return (row['train_specimen'], row['model'], str(row['seed']), row['split'], int(row['cycles']))


def reproduction_gate(predictions, recorded_path=V1_PREDICTIONS):
    """Check single-path predictions against the recorded v1 model comparison.

    The match must be one-to-one: every recorded row appears exactly once, no
    extra or duplicated row is accepted, and each row has the same evaluation
    specimen, row specimen, observed target and prediction as the record.

    Parameters
    ----------
    predictions : list of dict
        Prediction rows for ``single_path_1_7`` (all models, seeds and splits).
    recorded_path : pathlib.Path, optional
        Recorded v1 ``predictions.csv`` (a temporary copy in tests).

    Returns
    -------
    dict
        Number of compared predictions and the maximum absolute prediction difference.

    Raises
    ------
    ValueError
        If a row is duplicated, missing or extra, if a specimen differs, or if an
        observation or prediction differs beyond rtol 1e-9, atol 1e-10.
    """
    recorded = {}
    for r in read_csv(recorded_path):
        require(_gate_key(r) not in recorded, f'Duplicate recorded v1 row {_gate_key(r)}')
        recorded[_gate_key(r)] = r
    seen, worst = set(), 0.0
    for p in predictions:
        key = _gate_key(p)
        # Matching values alone is not enough: a duplicated row could stand in for
        # a missing one, so each key must be used once and the key sets must agree.
        require(key not in seen, f'Duplicate prediction row {key}')
        require(key in recorded, f'No recorded v1 prediction for {key}')
        seen.add(key)
        expected = recorded[key]
        for field in ('evaluation_specimen', 'specimen'):
            require(p[field] == expected[field], f'{field} differs for {key}')
        for field in ('observed', 'predicted'):
            require(
                np.isclose(p[field], float(expected[field]), rtol=1e-9, atol=1e-10),
                f'Reproduction gate failed for {key}: {field} {p[field]} != {expected[field]}',
            )
        worst = max(worst, abs(p['predicted'] - float(expected['predicted'])))
    missing = set(recorded) - seen
    require(not missing, f'{len(missing)} recorded v1 predictions were not reproduced')
    return dict(compared_predictions=len(seen), max_abs_difference=worst, rtol=1e-9, atol=1e-10)


def plot_direction(predictions, train_name, evaluation_name, path):
    """Plot evaluation predictions against observations for one direction.

    Parameters
    ----------
    predictions : list of dict
        All prediction rows.
    train_name, evaluation_name : str
        Direction to plot.
    path : pathlib.Path
        Destination PNG.
    """
    rows = [
        p for p in predictions if p['train_specimen'] == train_name and p['split'] == 'evaluation'
    ]
    values = [
        p[k] for p in predictions if p['split'] == 'evaluation' for k in ('observed', 'predicted')
    ]
    span = max(values) - min(values)
    limits = (min(values) - 0.06 * span, max(values) + 0.06 * span)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 9.5), layout='constrained')
    for ax, model in zip(axes.flat, FAMILIES + CONTROLS):
        ax.plot(limits, limits, '--', color='#9a9a9a', lw=1)
        groups = ['control'] if model in CONTROLS else list(INPUT_SETS)
        for group in groups:
            input_set = 'single_path_1_7' if group == 'control' else group
            ps = [p for p in rows if p['model'] == model and p['input_set'] == input_set]
            label = {
                'control': 'control (no PZT input)',
                'single_path_1_7': 'single path 1→7',
                'multi_path_36': 'multi-path (36 pairs)',
            }[group]
            ax.scatter(
                [p['observed'] for p in ps],
                [p['predicted'] for p in ps],
                s=36,
                marker=MARKERS[group],
                color=COLOURS[group],
                edgecolors='white',
                linewidths=0.8,
                alpha=0.75 if model == 'MLPRegressor' else 1.0,
                label=label + (' (all 5 seeds)' if model == 'MLPRegressor' else ''),
            )
        ax.set(
            xlim=limits,
            ylim=limits,
            title=model,
            xlabel='Observed published index',
            ylabel='Predicted index',
        )
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, color='#e3e3e3', lw=0.5)
        ax.legend(fontsize=8, loc='upper left', frameon=False)
    fig.suptitle(
        f'Protocol v2 validation, {train_name} → {evaluation_name}: evaluation '
        'checkpoints only\nReference checkpoints excluded; dashed line = perfect agreement; '
        'no clipping',
        fontsize=12,
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)


def compare_replay(replay_root, recorded_out=OUT, recorded_selection=SELECTION):
    """Compare a replayed validation with the recorded one, without writing the record.

    Parameters
    ----------
    replay_root : pathlib.Path
        Replay folder holding ``validation/`` and ``selection.json``.
    recorded_out, recorded_selection : pathlib.Path, optional
        Recorded validation folder and selection file (temporary copies in tests).

    Returns
    -------
    dict
        ``{'files': {name: status}, 'counts': {status: n}, 'not_compared': {...}}``,
        with statuses as in :func:`verify_reproduction.classify`.
    """
    recorded_env = load_json(ROOT / 'results' / 'model_comparison' / 'environment.json')
    same_plots = matplotlib.__version__ == recorded_env['matplotlib']
    files = {
        'validation/' + k: v
        for k, v in compare_folder(
            replay_root / 'validation', recorded_out, same_plots, exclude=REPLAY_NOT_COMPARED
        ).items()
    }
    # The decision must match exactly; only the run's own time and commit may differ.
    new_selection = replay_root / 'selection.json'
    same = new_selection.is_file() and strip_volatile(
        load_json(new_selection), SELECTION_RUN_KEYS
    ) == strip_volatile(load_json(recorded_selection), SELECTION_RUN_KEYS)
    files['selection.json'] = 'equal_content' if same else 'DIFFERENT'
    counts = {}
    for value in files.values():
        counts[value] = counts.get(value, 0) + 1
    return dict(files=files, counts=counts, not_compared=REPLAY_NOT_COMPARED)


def main(argv=None):
    """Run protocol v2 validation and write the frozen selection (or replay it).

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If the tree is dirty (recorded run only), outputs already exist, an
        integrity check fails, the reproduction gate fails, or a replayed
        output differs from the record.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 4), default=4)
    parser.add_argument(
        '--replay',
        action='store_true',
        help='Recompute into results/rebuilt/protocol_v2_replay/ and compare with the record.',
    )
    args = parser.parse_args(argv)
    data_root = args.data_root.resolve()
    protocol = load_protocol()
    state = git_state()
    if args.replay:
        # A replay is a check, not a decision: it may run on a dirty tree, and it
        # replaces only its own scratch folder, validated before deletion.
        replay_root = check_work_folder(REPLAY, data_root)
        if replay_root.exists():
            shutil.rmtree(replay_root)
        out, selection_path = replay_root / 'validation', replay_root / 'selection.json'
    else:
        # The recorded run must identify its code by a clean commit and may run once.
        require(state['clean'], 'Commit all changes first so the receipt identifies the code')
        require(
            not OUT.exists() and not SELECTION.exists(),
            'Protocol v2 validation outputs already exist; they are not overwritten',
        )
        out, selection_path = OUT, SELECTION
    out.mkdir(parents=True)
    development = [s for s, v in protocol['specimens'].items() if v['role'] == 'development']
    # L2S11 is never in this list, so the validation cannot open the held-out specimen.
    require(development == ['L1S11', 'L1S12'], 'Validation uses exactly L1S11 and L1S12')
    save_json(
        out / 'receipt.json',
        dict(
            started_utc=datetime.now(timezone.utc).isoformat(),
            git=state,
            protocol_config_sha256=digest(PROTOCOL_PATH),
            protocol_doc_sha256=digest(PROTOCOL_DOC),
            specimens_read=development,
            held_out_specimen_read=False,
            replay=args.replay,
            python=platform.python_version(),
            numpy=np.__version__,
            sklearn=sklearn.__version__,
        ),
    )

    summaries, checkpoints, ratios, references, hashes = [], [], [], [], {}
    for specimen in development:
        local, local_hashes = extract_specimen(
            data_root, specimen, protocol, read_labels=True, workers=args.workers
        )
        cps, pair_rows, reference = build_checkpoints(local, protocol)
        require(
            reference['cycles'] == protocol['reference']['expected_from_audit'][specimen],
            f'Reference for {specimen} differs from the audit expectation',
        )
        summaries += local
        checkpoints += cps
        ratios += pair_rows
        references.append(reference)
        hashes.update(local_hashes)
    # Re-hash every source after extraction: the raw files must be unchanged.
    for file, value in hashes.items():
        require(digest(data_root / file) == value, f'Source file changed: {file}')

    usable = {
        s: [
            r
            for r in checkpoints
            if r['specimen'] == s and not r['is_reference'] and r['published_index'] is not None
        ]
        for s in development
    }
    expected = protocol['validation']['expected_counts_from_v1']
    require(all(len(usable[s]) == expected[s] for s in development), 'Checkpoint counts changed')

    seeds = protocol['models']['mlp_seeds']
    predictions, metrics, convergence = [], [], 0
    # One BLAS thread, as in v1, so MLP and SVR fits are bit-reproducible.
    with threadpool_limits(limits=protocol['models']['threads']):
        for train_name, evaluation_name in protocol['validation']['directions']:
            train, evaluation = usable[train_name], usable[evaluation_name]
            for input_set in INPUT_SETS:
                for model in FAMILIES + CONTROLS:
                    if model in CONTROLS and input_set != 'single_path_1_7':
                        continue  # controls do not use PZT inputs; fit once per direction
                    for seed in (seeds if model == 'MLPRegressor' else ['']):
                        train_pred, eval_pred, warned = fit_predict(
                            model, seed or None, input_set, train, evaluation, protocol
                        )
                        convergence += warned
                        info = dict(
                            train_specimen=train_name,
                            evaluation_specimen=evaluation_name,
                            input_set='none' if model in CONTROLS else input_set,
                            model=model,
                            seed=seed,
                        )
                        for split, rows, predicted in (
                            ('training', train, train_pred),
                            ('evaluation', evaluation, eval_pred),
                        ):
                            y = np.array([r['published_index'] for r in rows])
                            metrics.append(
                                dict(**info, split=split, n=len(rows), **scores(y, predicted))
                            )
                            for r, value in zip(rows, predicted):
                                predictions.append(
                                    dict(
                                        **info,
                                        split=split,
                                        specimen=r['specimen'],
                                        cycles=r['cycles'],
                                        observed=r['published_index'],
                                        predicted=float(value),
                                        residual=float(value - r['published_index']),
                                    )
                                )

    # Reproduction gate, before any multi-path score is written: if the single-path
    # rows (controls included; v1 recorded them in the same run) do not reproduce
    # the v1 predictions exactly, nothing new is reported.
    gate_rows = [
        dict(p, input_set='single_path_1_7')
        for p in predictions
        if p['input_set'] in ('single_path_1_7', 'none')
    ]
    gate = reproduction_gate(gate_rows)
    save_json(out / 'reproduction_gate.json', gate)
    for p in predictions:  # plotting label: controls drawn once
        p['input_set'] = 'single_path_1_7' if p['input_set'] == 'none' else p['input_set']

    summary = []
    for train_name, evaluation_name in protocol['validation']['directions']:
        for input_set in INPUT_SETS + ('none',):
            for model in (CONTROLS if input_set == 'none' else FAMILIES):
                for split in ('training', 'evaluation'):
                    group = [
                        m
                        for m in metrics
                        if m['train_specimen'] == train_name
                        and m['input_set'] == input_set
                        and m['model'] == model
                        and m['split'] == split
                    ]
                    row = dict(
                        train_specimen=train_name,
                        evaluation_specimen=evaluation_name,
                        input_set=input_set,
                        model=model,
                        split=split,
                        fits=len(group),
                    )
                    for field in ('MAE', 'RMSE', 'R2', 'mean_residual'):
                        values = [g[field] for g in group]
                        # MLP: median over the five seeds per direction; no seed is selected.
                        row[field], row[field + '_min'], row[field + '_max'] = (
                            float(np.median(values)),
                            min(values),
                            max(values),
                        )
                    summary.append(row)

    candidates = []
    for model in FAMILIES:
        for input_set in INPUT_SETS:
            mae = {
                r['train_specimen']: r['MAE']
                for r in summary
                if r['model'] == model
                and r['input_set'] == input_set
                and r['split'] == 'evaluation'
            }
            candidates.append(
                dict(
                    model=model,
                    input_set=input_set,
                    MAE_L1S11_to_L1S12=mae['L1S11'],
                    MAE_L1S12_to_L1S11=mae['L1S12'],
                    worst_direction_MAE=max(mae.values()),
                    mean_direction_MAE=float(np.mean(list(mae.values()))),
                )
            )
    decision = select_final(candidates, protocol)

    flat = [
        {
            k: v
            for k, v in s.items()
            if k not in ('pair_counts', 'settings', 'rms', 'ptp', 'bad_pairs')
        }
        for s in summaries
    ]
    for name, rows in [
        ('recordings.csv', flat),
        ('checkpoint_features.csv', checkpoints),
        ('pair_ratios.csv', ratios),
        ('references.csv', references),
        ('metrics.csv', metrics),
        ('summary.csv', summary),
        ('predictions.csv', predictions),
        ('candidates.csv', candidates),
    ]:
        write_csv(out / name, rows, list(dict.fromkeys(k for r in rows for k in r)))
    save_json(out / 'source_hashes.json', hashes)
    for train_name, evaluation_name in protocol['validation']['directions']:
        plot_direction(
            predictions,
            train_name,
            evaluation_name,
            out / f'predictions_{train_name}_to_{evaluation_name}.png',
        )
    selection = dict(
        rule=protocol['selection_rule'],
        candidates=candidates,
        minimum_worst_direction_MAE=decision['minimum'],
        tied_within_tolerance=[(c['model'], c['input_set']) for c in decision['tied']],
        selected=dict(
            model=decision['selected']['model'], input_set=decision['selected']['input_set']
        ),
        final_model_training=protocol['final_model'],
        convergence_warnings=convergence,
        reproduction_gate=gate,
        validation_git_commit=state['commit'],
        decided_utc=datetime.now(timezone.utc).isoformat(),
        status='frozen: L2S11 has not been opened; commit this file before step 4',
    )
    save_json(selection_path, selection)
    print(
        json.dumps(
            dict(
                selected=selection['selected'],
                candidates=candidates,
                gate=gate,
                convergence_warnings=convergence,
            ),
            indent=2,
        )
    )
    if args.replay:
        comparison = compare_replay(replay_root)
        save_json(replay_root / 'comparison.json', comparison)
        print(json.dumps(dict(counts=comparison['counts']), indent=2))
        require(
            'DIFFERENT' not in comparison['counts'],
            f'Replay differs from the record: see {replay_root / "comparison.json"}',
        )


if __name__ == '__main__':
    main()
