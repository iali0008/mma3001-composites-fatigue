"""Unprofiled original-vs-prefetch timings with full output-equivalence gates."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from profile_raw_workflow import check_output
from repeat_sensitivity import digest, require
from reproduce_results import write_csv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True, type=Path)
    args = parser.parse_args()
    out = ROOT/'results/model_comparison/raw_benchmark'
    out.mkdir(parents=True, exist_ok=True)
    # Declared before timings: one warm-up per mode, then three alternating pairs.
    plan = [(1, -1), (4, -1), (1, 0), (4, 0), (4, 1), (1, 1), (1, 2), (4, 2)]
    rows = []
    for workers, repeat in plan:
        destination = out/f'workers_{workers}'
        with (out/f'workers_{workers}_stdout.txt').open('w', encoding='utf-8') as log:
            start = time.perf_counter()
            subprocess.run([sys.executable, str(ROOT/'scripts/exploratory_regression.py'),
                            '--data-root', str(args.data_root), '--output', str(destination),
                            '--workers', str(workers)], stdout=log, check=True)
            elapsed = time.perf_counter()-start
        check_output(destination)
        rows.append(dict(workers=workers, repetition=repeat, warmup=repeat < 0,
                         elapsed_seconds=elapsed, numerical_outputs_match_baseline=True))
        print(rows[-1], flush=True)
    # CSVs/README/source hashes should be byte-identical; image pixels are also checked via file hash.
    equivalents = {p.name: digest(p) == digest(out/'workers_4'/p.name)
                   for p in (out/'workers_1').iterdir() if p.is_file()}
    require(all(equivalents.values()), 'Serial/prefetch artifacts differ')
    write_csv(out/'timings.csv', rows)
    serial = float(np.median([r['elapsed_seconds'] for r in rows if r['workers'] == 1 and not r['warmup']]))
    parallel = float(np.median([r['elapsed_seconds'] for r in rows if r['workers'] == 4 and not r['warmup']]))
    result = dict(serial_median_seconds=serial, prefetch_median_seconds=parallel,
                  speedup=serial/parallel, artifact_hash_equivalence=equivalents,
                  method='Separate fresh processes; imports, extraction, hash checks, modelling and plot included. '
                         'One warm-up each, three alternating measured pairs. OS caches not flushed. No profiler.')
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
