"""Re-run the historical workflows into a scratch folder and compare with recorded results.

The recorded folders (``results/baseline``, ``results/repeat_sensitivity``,
``results/model_comparison`` and its ``coverage``) are never written. Each
workflow is rerun into ``--work`` and every output file is classified:

* ``identical`` - byte-for-byte equal to the recorded file;
* ``equal_content`` - JSON with equal content after removing volatile fields
  (timestamps, the protected-file list, the hash of an edited script) or a
  text file that differs only in line endings;
* ``equal_except_environment`` - JSON equal once data-location, git-check and
  checkout-dependent byte-hash fields (``ENVIRONMENT_KEYS``) are also removed;
  expected in a fresh clone with the data outside the repository;
* ``skipped`` - nondeterministic (timing samples) or environment-specific
  (environment description, plots rendered by a different Matplotlib);
* ``DIFFERENT`` - a reproduction failure.

The run fails if any file is ``DIFFERENT``. A JSON report is written to
``--report``.

Example
-------
``python scripts/verify_reproduction.py --data-root "data/2.+Composites/2. Composites"``
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import matplotlib

from common import RECORDED_RESULTS, ROOT, load_json, require, require_not_recorded, save_json

RESULTS = ROOT / 'results'
VOLATILE_KEYS = {
    'started_utc',
    'completed_utc',
    'historical_outputs_hashes_unchanged',
    'existing_artifact_hashes_unchanged',
}
ENVIRONMENT_KEYS = {
    'data_root',
    'git_exclusions',
    'baseline_hashes_unchanged',
    'checkpoint_table_sha256',
    'recorded_references_sha256',
}
"""Fields that legitimately depend on where the data and checkout live: the data path, the
git-exclusion check (which reports an external data folder differently), and byte hashes of
recorded CSV files (which change with checkout line endings while their content is equal)."""
TIMING_FILES = {'timing_samples.csv', 'timing_summary.csv'}


def _overlaps(a, b):
    """Return whether path ``a`` is, contains or sits inside path ``b``."""
    return a == b or b in a.parents or a in b.parents


def check_work_folder(work, data_root, root=ROOT):
    """Validate a scratch folder before anything inside it is deleted.

    The folder is replaced on every run, so a wrong path would destroy data.
    Only a folder strictly inside ``<root>/results/rebuilt/`` is accepted, and
    it must not overlap the repository root, ``data/``, any recorded results
    folder or the raw-data root. Symlinks are resolved first.

    Parameters
    ----------
    work : pathlib.Path
        Proposed scratch folder.
    data_root : pathlib.Path
        The raw-data root passed as ``--data-root``.
    root : pathlib.Path, optional
        Repository root (a temporary tree in tests).

    Returns
    -------
    pathlib.Path
        The resolved, accepted scratch folder.

    Raises
    ------
    ValueError
        If the folder is not strictly inside ``results/rebuilt/`` or overlaps a
        protected location. Nothing has been deleted when this is raised.
    """
    root = Path(root).resolve()
    work = Path(work).resolve()
    rebuilt = root / 'results' / 'rebuilt'
    require(
        rebuilt in work.parents,
        f'--work must be a folder strictly inside {rebuilt}; refusing {work}',
    )
    protected = [root, root / 'data', Path(data_root).resolve()]
    protected += [root / 'results' / name for name in RECORDED_RESULTS]
    for folder in protected:
        # The root is always an ancestor of an accepted folder; only equality
        # or containment of the root is dangerous.
        if folder == root:
            require(work != root and work not in root.parents, f'--work overlaps {root}')
            continue
        require(not _overlaps(work, folder), f'--work overlaps protected folder {folder}')
    require(not work.exists() or work.is_dir(), f'--work exists and is not a folder: {work}')
    return work


def strip_volatile(value, extra=frozenset()):
    """Remove volatile keys from nested JSON values.

    Parameters
    ----------
    value : object
        Decoded JSON.

    Returns
    -------
    object
        Copy without keys listed in ``VOLATILE_KEYS`` or ``extra``.
    """
    if isinstance(value, dict):
        return {
            k: strip_volatile(v, extra)
            for k, v in value.items()
            if k not in VOLATILE_KEYS and k not in extra
        }
    if isinstance(value, list):
        return [strip_volatile(v, extra) for v in value]
    return value


def classify(new, recorded, same_plot_environment):
    """Compare one regenerated file with its recorded counterpart.

    Parameters
    ----------
    new, recorded : pathlib.Path
        Regenerated and recorded files.
    same_plot_environment : bool
        Whether Matplotlib matches the version that rendered the recorded plots.

    Returns
    -------
    str
        One of ``identical``, ``equal_content``, ``equal_except_environment``,
        ``skipped`` or ``DIFFERENT``.
    """
    if not new.is_file():
        return 'DIFFERENT'
    if new.read_bytes() == recorded.read_bytes():
        return 'identical'
    if new.name in TIMING_FILES or new.name == 'environment.json':
        return 'skipped'
    if new.suffix == '.png':
        return 'DIFFERENT' if same_plot_environment else 'skipped'
    if new.suffix == '.json':
        new_json, old_json = load_json(new), load_json(recorded)
        if strip_volatile(new_json) == strip_volatile(old_json):
            return 'equal_content'
        same = strip_volatile(new_json, ENVIRONMENT_KEYS) == strip_volatile(
            old_json, ENVIRONMENT_KEYS
        )
        return 'equal_except_environment' if same else 'DIFFERENT'
    if new.suffix in ('.csv', '.txt', '.md'):
        a = new.read_text(encoding='utf-8').replace('\r\n', '\n')
        b = recorded.read_text(encoding='utf-8').replace('\r\n', '\n')
        return 'equal_content' if a == b else 'DIFFERENT'
    return 'DIFFERENT'


def compare_folder(new_dir, recorded_dir, same_plot_environment, overrides=None, exclude=()):
    """Classify every recorded file in a folder tree.

    Parameters
    ----------
    new_dir, recorded_dir : pathlib.Path
        Regenerated and recorded folders.
    same_plot_environment : bool
        Passed to :func:`classify`.
    overrides : dict, optional
        ``{relative_name: alternative_recorded_path}`` for files whose
        same-environment reference lives elsewhere.
    exclude : iterable of str, optional
        Recorded relative paths (or top-level folders) not produced by this run.

    Returns
    -------
    dict
        ``{relative_path: status}``.
    """
    overrides = overrides or {}
    status = {}
    for recorded in sorted(p for p in recorded_dir.rglob('*') if p.is_file()):
        rel = recorded.relative_to(recorded_dir).as_posix()
        if rel.split('/')[0] in exclude or rel in exclude:
            continue
        status[rel] = classify(new_dir / rel, overrides.get(rel, recorded), same_plot_environment)
    return status


def run(script, *args):
    """Run a repository script with the current interpreter, failing on error.

    Parameters
    ----------
    script : str
        File name inside ``scripts/``.
    *args : str
        Command-line arguments.
    """
    subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / script), *args],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main(argv=None):
    """Re-run baseline, repeat sensitivity, model comparison and coverage, then compare.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If any regenerated file differs from its recorded counterpart.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument(
        '--work',
        type=Path,
        default=RESULTS / 'rebuilt' / 'verification',
        help='Scratch folder strictly inside results/rebuilt/ (deleted and recreated each run).',
    )
    parser.add_argument(
        '--report',
        type=Path,
        default=RESULTS / 'rebuilt' / 'reproduction_check' / 'report.json',
        help='Report file; never inside a recorded results folder.',
    )
    args = parser.parse_args(argv)
    # Validate the scratch path completely before the destructive rmtree below.
    work = check_work_folder(args.work, args.data_root)
    report_path = require_not_recorded(args.report)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    data = str(args.data_root)
    recorded_env = load_json(RESULTS / 'model_comparison' / 'environment.json')
    same_plots = matplotlib.__version__ == recorded_env['matplotlib']

    run('exploratory_regression.py', '--data-root', data, '--output', str(work / 'baseline'))
    run('repeat_sensitivity.py', '--data-root', data, '--output', str(work / 'repeat_sensitivity'))
    run('model_comparison.py', '--data-root', data, '--output', str(work / 'model_comparison'))
    run('feature_coverage.py', '--output', str(work / 'coverage'))

    # results/baseline predates this environment: its plot is compared with the
    # same-environment rebuild recorded inside results/repeat_sensitivity.
    plot = RESULTS / 'repeat_sensitivity' / 'median_rebuild' / 'predicted_vs_observed.png'
    sections = {
        'baseline': compare_folder(
            work / 'baseline', RESULTS / 'baseline', same_plots, {'predicted_vs_observed.png': plot}
        ),
        'repeat_sensitivity': compare_folder(
            work / 'repeat_sensitivity', RESULTS / 'repeat_sensitivity', same_plots
        ),
        'model_comparison': compare_folder(
            work / 'model_comparison',
            RESULTS / 'model_comparison',
            same_plots,
            exclude=('coverage', 'raw_benchmark', 'raw_profile', 'INTERPRETATION.md'),
        ),
        'coverage': compare_folder(
            work / 'coverage', RESULTS / 'model_comparison' / 'coverage', same_plots
        ),
    }
    counts = {}
    for statuses in sections.values():
        for value in statuses.values():
            counts[value] = counts.get(value, 0) + 1
    report = dict(
        checked_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(),
        matplotlib=matplotlib.__version__,
        recorded_matplotlib=recorded_env['matplotlib'],
        plots_compared=same_plots,
        counts=counts,
        files=sections,
        not_rerun=[
            'raw_profile and raw_benchmark (timing evidence; rerun separately)',
            'INTERPRETATION.md (hand-written)',
        ],
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(report_path, report)
    print(json.dumps(dict(counts=counts, report=str(report_path)), indent=2))
    require('DIFFERENT' not in counts, 'Reproduction failed: see the report for DIFFERENT files')


if __name__ == '__main__':
    main()
