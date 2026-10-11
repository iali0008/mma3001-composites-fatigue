"""Re-run the historical workflows into a scratch folder and compare with recorded results.

The recorded folders (``results/baseline``, ``results/repeat_sensitivity``,
``results/model_comparison`` and its ``coverage``) are never written. Each
workflow is rerun into ``--work`` and every output file is classified:

* ``identical`` - byte-for-byte equal to the recorded file;
* ``equal_content`` - JSON with equal content after removing volatile fields
  (timestamps, the protected-file list, the hash of an edited script) or a
  text file that differs only in line endings;
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

from common import ROOT, load_json, require, save_json

RESULTS = ROOT / 'results'
VOLATILE_KEYS = {'started_utc', 'completed_utc', 'historical_outputs_hashes_unchanged',
                 'existing_artifact_hashes_unchanged'}
TIMING_FILES = {'timing_samples.csv', 'timing_summary.csv'}


def strip_volatile(value):
    """Remove volatile keys from nested JSON values.

    Parameters
    ----------
    value : object
        Decoded JSON.

    Returns
    -------
    object
        Copy without keys listed in ``VOLATILE_KEYS``.
    """
    if isinstance(value, dict):
        return {k: strip_volatile(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
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
        One of ``identical``, ``equal_content``, ``skipped`` or ``DIFFERENT``.
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
        same = strip_volatile(load_json(new)) == strip_volatile(load_json(recorded))
        return 'equal_content' if same else 'DIFFERENT'
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
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args], check=True,
                   stdout=subprocess.DEVNULL)


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
    parser.add_argument('--work', type=Path, default=RESULTS / 'rebuilt' / 'verification',
                        help='Scratch folder for regenerated outputs (replaced on each run).')
    parser.add_argument('--report', type=Path, default=RESULTS / 'reproduction_check' / 'report.json')
    args = parser.parse_args(argv)
    work = args.work.resolve()
    for recorded in ('baseline', 'repeat_sensitivity', 'model_comparison', 'protocol_v2_audit'):
        folder = RESULTS / recorded
        require(work != folder and folder not in work.parents and work not in folder.parents,
                'The work folder must not overlap recorded results')
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
        'baseline': compare_folder(work / 'baseline', RESULTS / 'baseline', same_plots,
                                   {'predicted_vs_observed.png': plot}),
        'repeat_sensitivity': compare_folder(work / 'repeat_sensitivity',
                                             RESULTS / 'repeat_sensitivity', same_plots),
        'model_comparison': compare_folder(
            work / 'model_comparison', RESULTS / 'model_comparison', same_plots,
            exclude=('coverage', 'raw_benchmark', 'raw_profile', 'INTERPRETATION.md')),
        'coverage': compare_folder(work / 'coverage', RESULTS / 'model_comparison' / 'coverage',
                                   same_plots),
    }
    counts = {}
    for statuses in sections.values():
        for value in statuses.values():
            counts[value] = counts.get(value, 0) + 1
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
                  python=platform.python_version(), matplotlib=matplotlib.__version__,
                  recorded_matplotlib=recorded_env['matplotlib'],
                  plots_compared=same_plots, counts=counts, files=sections,
                  not_rerun=['raw_profile and raw_benchmark (timing evidence; rerun separately)',
                             'INTERPRETATION.md (hand-written)'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    save_json(args.report, report)
    print(json.dumps(dict(counts=counts, report=str(args.report)), indent=2))
    require('DIFFERENT' not in counts, 'Reproduction failed: see the report for DIFFERENT files')


if __name__ == '__main__':
    main()
