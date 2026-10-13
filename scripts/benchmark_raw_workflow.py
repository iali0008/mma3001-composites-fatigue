"""Unprofiled original-vs-prefetch timings with full output-equivalence gates."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from common import ROOT, digest, require, require_not_recorded, write_csv
from profile_raw_workflow import check_output


def main(argv=None):
    """Time serial and prefetch raw workflows in alternating fresh processes.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If serial and prefetch outputs are not byte-identical.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results/rebuilt/raw_benchmark',
        help='New output folder; the recorded results folder is refused.',
    )
    args = parser.parse_args(argv)
    out = require_not_recorded(args.output)
    recorded = ROOT / 'results/model_comparison/raw_benchmark'
    require(
        out != recorded and recorded not in out.parents,
        'Recorded results are immutable; choose a new output folder',
    )
    out.mkdir(parents=True, exist_ok=True)
    # Declared before timings: one warm-up per mode, then three alternating pairs.
    # Alternate the order of serial and prefetch runs so slow drift (caches, thermal
    # state) does not favour one mode. Unprofiled: cProfile overhead would distort it.
    plan = [(1, -1), (4, -1), (1, 0), (4, 0), (4, 1), (1, 1), (1, 2), (4, 2)]
    rows = []
    for workers, repeat in plan:
        destination = out / f'workers_{workers}'
        with (out / f'workers_{workers}_stdout.txt').open('w', encoding='utf-8') as log:
            start = time.perf_counter()
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / 'scripts/exploratory_regression.py'),
                    '--data-root',
                    str(args.data_root),
                    '--output',
                    str(destination),
                    '--workers',
                    str(workers),
                ],
                stdout=log,
                check=True,
            )
            elapsed = time.perf_counter() - start
        check_output(destination)
        rows.append(
            dict(
                workers=workers,
                repetition=repeat,
                warmup=repeat < 0,
                elapsed_seconds=elapsed,
                numerical_outputs_match_baseline=True,
            )
        )
        print(rows[-1], flush=True)
    # CSVs/README/source hashes should be byte-identical; image pixels are also
    # checked via file hash.
    equivalents = {
        p.name: digest(p) == digest(out / 'workers_4' / p.name)
        for p in (out / 'workers_1').iterdir()
        if p.is_file()
    }
    require(all(equivalents.values()), 'Serial/prefetch artifacts differ')
    write_csv(out / 'timings.csv', rows)
    serial = float(
        np.median([r['elapsed_seconds'] for r in rows if r['workers'] == 1 and not r['warmup']])
    )
    parallel = float(
        np.median([r['elapsed_seconds'] for r in rows if r['workers'] == 4 and not r['warmup']])
    )
    result = dict(
        serial_median_seconds=serial,
        prefetch_median_seconds=parallel,
        speedup=serial / parallel,
        artifact_hash_equivalence=equivalents,
        method=(
            'Separate fresh processes; imports, extraction, hash checks, modelling and plot '
            'included. One warm-up each, three alternating measured pairs. OS caches not '
            'flushed. No profiler.'
        ),
    )
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
