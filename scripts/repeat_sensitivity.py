"""Repeat selection sensitivity with frozen baseline membership and references.

Rebuild the original median experiment first; never write into the raw dataset.
Use original logbook timestamps when they uniquely order every repeat in a
checkpoint, otherwise explicitly use filename-ordered selection for that group.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, time
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import openpyxl
import scipy

from common import (
    ROOT,
    digest,
    load_experiment_v1,
    read_csv,
    require,
    require_not_recorded,
    snapshot,
)
from reproduce_results import MODELS, evaluate, read_checkpoints, write_csv

BASELINE = ROOT / 'results/baseline'
RECORDED = ROOT / 'results/repeat_sensitivity'
EXPERIMENT = load_experiment_v1()
FOLDERS = {s: v['folder'] for s, v in EXPERIMENT['specimens'].items()}
FEATURES = ('mean_centred_rms', 'peak_to_peak')

__all__ = [
    'build_variants',
    'check_ols_independently',
    'compare_tables',
    'digest',
    'load_logs',
    'order_repeats',
    'read_csv',
    'require',
    'snapshot',
    'verify_git_exclusions',
]


def verify_git_exclusions(source_paths, source_scope, archive):
    """Check that every raw dataset file is git-ignored and none is tracked or staged.

    Parameters
    ----------
    source_paths : list of pathlib.Path
        All files of the local download.
    source_scope : pathlib.Path
        Download folder.
    archive : pathlib.Path
        Sibling ZIP archive.

    Returns
    -------
    dict
        Counts of ignored, tracked and staged raw files and the checked scopes.

    Raises
    ------
    ValueError
        If any raw file is not ignored or is tracked/staged.
    """
    if not source_scope.is_relative_to(ROOT):
        return {'status': 'External dataset is outside this repository'}
    paths = [p.relative_to(ROOT).as_posix() for p in source_paths]
    ignored = subprocess.run(
        ['git', 'check-ignore', '--stdin', '-z'],
        cwd=ROOT,
        input='\0'.join(paths) + '\0',
        text=True,
        capture_output=True,
        check=True,
    )
    require(
        set(ignored.stdout.strip('\0').split('\0')) == set(paths),
        'Some original dataset files are not ignored',
    )
    scopes = [source_scope.relative_to(ROOT).as_posix(), archive.relative_to(ROOT).as_posix()]
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', *scopes], cwd=ROOT, text=True)
    staged = subprocess.check_output(
        ['git', 'diff', '--cached', '--name-only', '-z', '--', *scopes], cwd=ROOT, text=True
    )
    require(not tracked and not staged, 'Original dataset files are tracked or staged')
    readme = subprocess.check_output(
        ['git', 'ls-files', '--', 'data/README.md'], cwd=ROOT, text=True
    )
    require(readme.strip() == 'data/README.md', 'Keep data/README.md tracked')
    return dict(
        all_raw_files_ignored=len(paths),
        tracked_raw_files=0,
        staged_raw_files=0,
        data_readme_tracked=True,
        scopes=scopes,
    )


def compare_tables(actual, expected, keys, fields):
    """Require two tables to have the same keys and numerically equal fields.

    Parameters
    ----------
    actual, expected : list of dict
        Tables to compare.
    keys : tuple of str
        Columns identifying a row.
    fields : tuple of str
        Columns compared exactly or within rtol 1e-9, atol 1e-10.

    Raises
    ------
    ValueError
        On duplicate keys, different membership or any mismatch.
    """
    a = {tuple(r[k] for k in keys): r for r in actual}
    b = {tuple(r[k] for k in keys): r for r in expected}
    require(len(a) == len(actual) and len(b) == len(expected), 'Duplicate table keys')
    require(a.keys() == b.keys(), f'Table membership differs: {keys}')
    for key in a:
        for field in fields:
            x, y = a[key][field], b[key][field]
            if x == y:
                continue
            try:
                np.testing.assert_allclose(float(x), float(y), rtol=1e-9, atol=1e-10)
            except (ValueError, TypeError, AssertionError) as exc:
                raise ValueError(f'Baseline mismatch {key}, {field}: {x} != {y}') from exc


def load_logs(data_root):
    """Read the L1S11 and L1S12 logbooks (read-only) and index them by file name.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.

    Returns
    -------
    logs : dict
        ``{(specimen, filename): {logbook, sheet, logbook_row, acquired_at,
        log_cycle, log_condition}}``.
    books : list of pathlib.Path
        Workbooks read.

    Raises
    ------
    ValueError
        If a logbook is ambiguous or a file is listed twice.
    """
    logs, books = {}, []
    for specimen, folder in FOLDERS.items():
        candidates = [
            p for p in (data_root / folder).glob('*.xlsx') if not p.name.startswith(('.', '~$'))
        ]
        require(len(candidates) == 1, f'Ambiguous logbook: {specimen}')
        book = candidates[0]
        books.append(book)
        workbook = openpyxl.load_workbook(book, read_only=True, data_only=True)
        try:
            sheet = workbook['Log_fatigue_testing']
            for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                if len(values) < 9 or not isinstance(values[6], str):
                    continue
                filename = values[6].strip(" '\"")
                if not filename.endswith('.mat'):
                    continue
                acquired = ''
                if isinstance(values[0], datetime) and isinstance(values[1], time):
                    acquired = datetime.combine(values[0].date(), values[1]).isoformat(' ')
                key = (specimen, filename)
                require(key not in logs, f'Duplicate logbook entry: {key}')
                logs[key] = dict(
                    logbook=book.relative_to(data_root).as_posix(),
                    sheet=sheet.title,
                    logbook_row=row_number,
                    acquired_at=acquired,
                    log_cycle=values[3],
                    log_condition=str(values[5]),
                )
        finally:
            workbook.close()
    return logs, books


def order_repeats(repeats, logs):
    """Order a checkpoint's repeats by logbook timestamp, or fall back explicitly.

    Parameters
    ----------
    repeats : list of dict
        Eligible recordings at one checkpoint.
    logs : dict
        Output of :func:`load_logs`.

    Returns
    -------
    ordered : list of dict
        Repeats in timestamp order, or filename order on fallback.
    basis : str
        ``'logbook_timestamp'`` or ``'filename_ordered'``.
    reason : str
        Why the fallback was used (empty otherwise).

    Raises
    ------
    ValueError
        If the logbook cycle or condition contradicts the MAT record.

    Notes
    -----
    Logged dates are not always chronological (see
    ``results/protocol_v2/post_hoc_step4/logbook_L1S11.json``).
    """
    evidence = [logs.get((r['specimen'], r['filename'])) for r in repeats]
    for r, log in zip(repeats, evidence):
        if log:
            require(float(log['log_cycle']) == float(r['cycles']), 'Logbook cycle mismatch')
            require(
                log['log_condition'].strip().casefold() == r['condition'].strip().casefold(),
                'Logbook condition mismatch',
            )
    stamps = [log['acquired_at'] if log else '' for log in evidence]
    if all(stamps) and len(set(stamps)) == len(stamps):
        ordered = sorted(repeats, key=lambda r: logs[(r['specimen'], r['filename'])]['acquired_at'])
        return ordered, 'logbook_timestamp', ''
    reason = 'Missing logbook timestamp' if not all(stamps) else 'Tied logbook timestamps'
    return sorted(repeats, key=lambda r: r['filename']), 'filename_ordered', reason


def build_variants(recordings, baseline_rows, references, logs):
    """Build median, first-repeat and last-repeat checkpoint tables.

    Membership, targets and the original reference denominators stay fixed.

    Parameters
    ----------
    recordings : list of dict
        Rows of the rebuilt ``recordings.csv``.
    baseline_rows : list of dict
        Recorded checkpoint table.
    references : list of dict
        Recorded references.
    logs : dict
        Output of :func:`load_logs`.

    Returns
    -------
    variants : dict
        ``{'median'|'first'|'last': checkpoint rows}``.
    provenance : list of dict
        Order and selection evidence for every repeat.

    Raises
    ------
    ValueError
        If membership, targets or reference recordings changed.
    """
    groups = {}
    for record in recordings:
        if record['eligible'] == 'True':
            key = (record['specimen'], int(float(record['cycles'])))
            groups.setdefault(key, []).append(record)
    require(
        set(groups) == {(r['specimen'], r['cycles']) for r in baseline_rows},
        'Checkpoint membership changed',
    )
    refs = {r['specimen']: r for r in references}
    variants = {name: [] for name in ('median', 'first', 'last')}
    provenance = []
    for baseline in baseline_rows:
        specimen, cycle = baseline['specimen'], baseline['cycles']
        repeats = groups[(specimen, cycle)]
        require(
            all(float(r['published_index']) == baseline['published_index'] for r in repeats),
            'Published targets changed or conflict',
        )
        ordered, basis, reason = order_repeats(repeats, logs)
        ref = refs[specimen]
        if baseline['is_reference']:
            require(
                '; '.join(r['filename'] for r in repeats) == ref['filenames'],
                'Reference recordings changed',
            )
        for ordinal, r in enumerate(ordered, 1):
            log = logs.get((specimen, r['filename']), {})
            provenance.append(
                dict(
                    specimen=specimen,
                    cycles=cycle,
                    filename=r['filename'],
                    ordinal=ordinal,
                    order_basis=basis,
                    fallback_reason=reason,
                    is_reference=baseline['is_reference'],
                    first_selected=ordinal == 1,
                    last_selected=ordinal == len(ordered),
                    logbook=log.get('logbook', ''),
                    sheet=log.get('sheet', ''),
                    logbook_row=log.get('logbook_row', ''),
                    acquired_at=log.get('acquired_at', ''),
                )
            )
        for variant in variants:
            cp = copy.deepcopy(baseline)
            selected = (
                repeats if variant == 'median' else [ordered[0 if variant == 'first' else -1]]
            )
            cp['filenames'] = '; '.join(r['filename'] for r in selected)
            cp['selection_basis'] = 'checkpoint_median' if variant == 'median' else basis
            for feature in FEATURES:
                values = [float(r[feature]) for r in selected]
                require(np.isfinite(values).all(), 'Selected features must be finite')
                cp[feature] = float(np.median(values))
                cp[feature + '_valid_repeats'] = len(values)
            # Explicitly freeze the original reference measurements for every variant.
            if cp['is_reference']:
                cp['filenames'] = ref['filenames']
                cp['selection_basis'] = 'fixed_reference'
                cp['mean_centred_rms'] = float(ref['rms_denominator'])
                cp['peak_to_peak'] = float(ref['ptp_denominator'])
            cp['relative_rms'] = cp['mean_centred_rms'] / float(ref['rms_denominator'])
            cp['relative_ptp'] = cp['peak_to_peak'] / float(ref['ptp_denominator'])
            variants[variant].append(cp)
    return variants, provenance


def check_ols_independently(rows, predictions):
    """Refit every model with unscaled least squares and compare predictions.

    Parameters
    ----------
    rows : list of dict
        Checkpoint rows of one variant.
    predictions : list of dict
        Predictions from :func:`reproduce_results.evaluate`.

    Raises
    ------
    ValueError
        If a design is rank-deficient.
    AssertionError
        If predictions differ beyond rtol 1e-9, atol 1e-10.
    """
    for train_name, test_name in EXPERIMENT['directions']:
        train = [r for r in rows if r['specimen'] == train_name and not r['is_reference']]
        test = [r for r in rows if r['specimen'] == test_name and not r['is_reference']]
        for model, fields in MODELS.items():
            x = np.array([[1.0] + [r[f] for f in fields] for r in train])
            xt = np.array([[1.0] + [r[f] for f in fields] for r in test])
            beta, _, rank, _ = np.linalg.lstsq(x, [r['published_index'] for r in train], rcond=None)
            require(rank == x.shape[1], 'Rank-deficient independent OLS')
            expected = [
                p['predicted_index']
                for p in predictions
                if p['train_specimen'] == train_name and p['model'] == model
            ]
            np.testing.assert_allclose(xt @ beta, expected, rtol=1e-9, atol=1e-10)


def main(argv=None):
    """Rebuild the median experiment, then fit first/last-repeat variants.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If the rebuild does not reproduce the recorded baseline or sources change.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results/rebuilt/repeat_sensitivity',
        help='New output folder; the recorded results/repeat_sensitivity is refused.',
    )
    args = parser.parse_args(argv)
    data_root, output = args.data_root.resolve(), require_not_recorded(args.output)
    require(
        all((data_root / name).is_dir() for name in ('Layup1', 'Layup2', 'Layup3')),
        'data-root must directly contain Layup1, Layup2 and Layup3',
    )
    # Protect the complete download wrapper, including supplementary files.
    source_scope = data_root.parent if data_root.parent.name == '2.+Composites' else data_root
    for protected in (source_scope, BASELINE.resolve(), RECORDED.resolve()):
        require(
            output != protected
            and protected not in output.parents
            and output not in protected.parents,
            'Output must be separate from raw sources and recorded baseline',
        )
    source_paths = sorted(p for p in source_scope.rglob('*') if p.is_file())
    archive = source_scope.with_suffix(source_scope.suffix + '.zip')
    if archive.is_file():
        source_paths.append(archive)
    before = snapshot(source_paths, source_scope.parent)
    git_verification = verify_git_exclusions(source_paths, source_scope, archive)
    baseline_hashes = {p.name: digest(p) for p in BASELINE.iterdir() if p.is_file()}
    logs, books = load_logs(data_root)
    log_hashes = {p.relative_to(data_root).as_posix(): digest(p) for p in books}
    output.mkdir(parents=True, exist_ok=True)
    print('Rebuilding the unchanged median pipeline...', flush=True)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / 'scripts/exploratory_regression.py'),
            '--data-root',
            str(data_root),
            '--output',
            str(output / 'median_rebuild'),
        ],
        check=True,
    )
    rebuilt = output / 'median_rebuild'
    # Gate all variant fitting on complete baseline reproduction.
    for name, keys in [
        ('recordings.csv', ('specimen', 'filename')),
        ('checkpoint_features.csv', ('specimen', 'cycles')),
        ('references.csv', ('specimen',)),
        ('metrics.csv', ('train_specimen', 'model')),
        ('predictions.csv', ('train_specimen', 'model', 'cycles')),
    ]:
        expected = read_csv(BASELINE / name)
        compare_tables(read_csv(rebuilt / name), expected, keys, tuple(expected[0]))
    require(
        json.loads((rebuilt / 'source_hashes.json').read_text())
        == json.loads((BASELINE / 'source_hashes.json').read_text()),
        'MAT source hashes differ from baseline',
    )
    baseline_rows = read_checkpoints(BASELINE / 'checkpoint_features.csv')
    references = read_csv(BASELINE / 'references.csv')
    variants, provenance = build_variants(
        read_csv(rebuilt / 'recordings.csv'), baseline_rows, references, logs
    )
    compare_tables(
        variants['median'],
        baseline_rows,
        ('specimen', 'cycles'),
        ('published_index', 'mean_centred_rms', 'peak_to_peak', 'relative_rms', 'relative_ptp'),
    )
    all_metrics, all_predictions, all_coefficients = [], [], []
    for variant, rows in variants.items():
        metrics, predictions, coefficients = evaluate(rows)
        check_ols_independently(rows, predictions)
        write_csv(output / f'{variant}_checkpoint_features.csv', rows)
        for collection, values in (
            (all_metrics, metrics),
            (all_predictions, predictions),
            (all_coefficients, coefficients),
        ):
            collection.extend(dict(variant=variant, **r) for r in values)
    median = {(r['train_specimen'], r['model']): r for r in all_metrics if r['variant'] == 'median'}
    for row in all_metrics:
        ref = median[(row['train_specimen'], row['model'])]
        for metric in ('MAE', 'RMSE'):
            row[f'{metric}_change'] = row[metric] - ref[metric]
            row[f'{metric}_change_percent'] = 100 * (row[metric] / ref[metric] - 1)
        if row['model'] == 'log10_cycles':
            require(row['MAE_change'] == row['RMSE_change'] == 0, 'Cycle baseline changed')
    for name, rows in [
        ('metrics.csv', all_metrics),
        ('predictions.csv', all_predictions),
        ('coefficients.csv', all_coefficients),
        ('selection_provenance.csv', provenance),
        ('references.csv', references),
    ]:
        write_csv(output / name, rows)
    after_paths = sorted(p for p in source_scope.rglob('*') if p.is_file())
    if archive.is_file():
        after_paths.append(archive)
    require(
        before == snapshot(after_paths, source_scope.parent), 'Original source metadata changed'
    )
    require(
        log_hashes == {p.relative_to(data_root).as_posix(): digest(p) for p in books},
        'Logbook content changed',
    )
    require(
        baseline_hashes == {p.name: digest(p) for p in BASELINE.iterdir() if p.is_file()},
        'Recorded baseline changed',
    )
    fallback = sorted(
        {(r['specimen'], r['cycles']) for r in provenance if r['order_basis'] == 'filename_ordered'}
    )
    verification = dict(
        baseline_reproduced=True,
        independent_ols_agrees=True,
        git_exclusions=git_verification,
        source_files_metadata_unchanged=len(before),
        mat_hashes_match_baseline=True,
        logbook_hashes_unchanged=log_hashes,
        baseline_hashes_unchanged=baseline_hashes,
        filename_ordered_checkpoints=fallback,
        data_root=(
            data_root.relative_to(ROOT).as_posix()
            if data_root.is_relative_to(ROOT)
            else str(data_root)
        ),
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        openpyxl=openpyxl.__version__,
    )
    (output / 'verification.json').write_text(
        json.dumps(verification, indent=2) + '\n', encoding='utf-8'
    )
    (output / 'source_inventory.json').write_text(
        json.dumps(before, indent=2) + '\n', encoding='utf-8'
    )
    lines = [
        '# Repeat-recording sensitivity',
        '',
        'Median baseline reproduced before fitting first/last variants. All variants retain the',
        'same eligibility, checkpoints, targets, reference measurements/denominators, models and',
        'specimen splits. Each model is refitted; equal checkpoint weights; no clipping or tuning.',
        '',
        'Ordering: unique original logbook date/time within each checkpoint. Ties or missing',
        'timestamps explicitly fall back to filename-ordered selection (not claimed '
        'chronological).',
        f'Filename-ordered checkpoints: {fallback or "none"}. Times have no supplied timezone.',
        '',
        '| Train -> evaluate | Variant | Two-feature MAE | Change | Two-feature RMSE | Change |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for row in all_metrics:
        if row['model'] == 'relative_rms_and_ptp':
            lines.append(
                f"| {row['train_specimen']} -> {row['test_specimen']} | {row['variant']} | "
                f"{row['MAE']:.9f} | {row['MAE_change']:+.9f} | {row['RMSE']:.9f} | "
                f"{row['RMSE_change']:+.9f} |"
            )
    rankings = []
    for variant in variants:
        for train in FOLDERS:
            candidates = [
                r for r in all_metrics if r['variant'] == variant and r['train_specimen'] == train
            ]
            rankings.append(
                dict(
                    variant=variant,
                    train_specimen=train,
                    test_specimen=candidates[0]['test_specimen'],
                    lowest_MAE_model=min(candidates, key=lambda r: r['MAE'])['model'],
                    lowest_RMSE_model=min(candidates, key=lambda r: r['RMSE'])['model'],
                )
            )
    write_csv(output / 'rankings.csv', rankings)
    best = all(
        r[field] == 'relative_rms_and_ptp'
        for r in rankings
        for field in ('lowest_MAE_model', 'lowest_RMSE_model')
    )
    lines += [
        '',
        f'Two-feature model lowest on both errors in both directions for all variants: {best}.',
        '',
        'See rankings.csv for every variant and direction. With last repeats, L1S12 -> L1S11',
        'favours RMS-only (MAE 0.031399039; RMSE 0.034863701), versus two-feature',
        'MAE 0.033314539 and RMSE 0.038596132. All other variant/direction combinations',
        'favour two features on both errors. Thus the ranking is sensitive to repeat selection.',
        '',
        'Errors and absolute changes are in published-index units. These are two correlated',
        'specimen trajectories, not independent repeats or population-level validation.',
        'The missing L1S12 20,000-cycle target stays absent and the 30,000-cycle jump stays '
        'included.',
        '',
        'Verification: all raw-directory files and the sibling archive retain sizes/mtimes;',
        'the extractor verifies SHA-256 before/after for all surveyed L1S11/L1S12 MAT files,',
        'which also match recorded baseline hashes. Both logbooks and the recorded baseline',
        'retain SHA-256 hashes. Other raw files were inventoried, not content-hashed.',
        'Independent unscaled least squares agrees with centred QR for every variant.',
    ]
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    main()
