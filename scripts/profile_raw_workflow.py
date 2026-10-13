"""Attribute raw workflow cost with cProfile, independently of model timings."""

import argparse
import csv
import io
import json
from pathlib import Path
import pstats
import subprocess
import sys

from common import ROOT, digest, read_csv, require, require_not_recorded
from repeat_sensitivity import compare_tables


def check_output(output, baseline=ROOT / 'results/baseline'):
    """Check a rebuilt baseline folder against the recorded baseline.

    Parameters
    ----------
    output : pathlib.Path
        Folder written by ``exploratory_regression.py``.
    baseline : pathlib.Path, optional
        Recorded baseline folder.

    Raises
    ------
    ValueError
        If any table differs beyond rtol 1e-9, atol 1e-10, or source hashes differ.
    """
    tables = {
        'recordings.csv': ('specimen', 'filename'),
        'checkpoint_features.csv': ('specimen', 'cycles'),
        'references.csv': ('specimen',),
        'metrics.csv': ('train_specimen', 'model'),
        'predictions.csv': ('train_specimen', 'model', 'cycles'),
        'coefficients.csv': ('train_specimen', 'model'),
        'exclusion_counts.csv': ('specimen', 'reason'),
    }
    for name, keys in tables.items():
        expected = read_csv(baseline / name)
        compare_tables(read_csv(output / name), expected, keys, tuple(expected[0]))
    require(
        json.loads((output / 'source_hashes.json').read_text())
        == json.loads((baseline / 'source_hashes.json').read_text()),
        'Raw hash discrepancy',
    )


def main(argv=None):
    """Profile the raw extraction workflow with cProfile and export summaries.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results/rebuilt/raw_profile',
        help='New output folder; the recorded results folder is refused.',
    )
    args = parser.parse_args(argv)
    out = require_not_recorded(args.output)
    recorded = ROOT / 'results/model_comparison/raw_profile'
    require(
        out != recorded and recorded not in out.parents,
        'Recorded results are immutable; choose a new output folder',
    )
    out.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        '-m',
        'cProfile',
        '-o',
        str(out / 'workflow.prof'),
        str(ROOT / 'scripts/exploratory_regression.py'),
        '--data-root',
        str(args.data_root),
        '--output',
        str(out / 'rebuilt'),
    ]
    # Profile in a subprocess so the profiler sees the unmodified script exactly as
    # users run it; its outputs are then checked against the baseline.
    with (out / 'stdout.txt').open('w', encoding='utf-8') as log:
        subprocess.run(command, check=True, stdout=log)
    check_output(out / 'rebuilt')
    stats = pstats.Stats(str(out / 'workflow.prof'))
    for sort in ('cumulative', 'tottime'):
        stream = io.StringIO()
        stats.stream = stream
        stats.sort_stats(sort).print_stats(40)
        (out / f'{sort}.txt').write_text(stream.getvalue(), encoding='utf-8')
    rows = []
    for (file, line, function), (primitive, calls, own, cumulative, _) in stats.stats.items():
        rows.append(
            dict(
                file=file,
                line=line,
                function=function,
                primitive_calls=primitive,
                calls=calls,
                self_seconds=own,
                cumulative_seconds=cumulative,
            )
        )
    rows.sort(key=lambda r: r['cumulative_seconds'], reverse=True)
    with (out / 'functions.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / 'verification.json').write_text(
        json.dumps(
            dict(
                baseline_equivalent=True,
                instrumented_total_seconds=stats.total_tt,
                original_script_sha256=digest(ROOT / 'scripts/exploratory_regression.py'),
            ),
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    print((out / 'cumulative.txt').read_text())


if __name__ == '__main__':
    main()
