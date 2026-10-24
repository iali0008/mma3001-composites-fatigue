"""Peak traced memory of the raw extraction and of model fit+predict, per fresh process.

Each repetition runs in a new Python process. Modules are imported, and for the
fit+predict workloads the saved baseline features are loaded, before
``tracemalloc.start()``, so the peak covers only the measured workload. The
figure is the peak of allocations registered with ``tracemalloc`` (Python
objects and NumPy array buffers); it is not total process RAM and need not
include every native-library allocation (for example BLAS work buffers).

Workloads
---------
``extraction``
    ``exploratory_regression.main`` with its serial default, writing into a
    temporary folder. Its outputs are checked against ``results/baseline``
    after measurement.
``fit_predict_selected``
    The selected model's settings (LinearRegression on path 1 -> 7) fitted on
    one Layup 1 specimen and predicting both, in both validation directions.
``fit_predict_v1_all``
    All six v1 comparators (five MLP seeds) in both validation directions.

Fit+predict includes the in-pipeline, training-only scaling and the conversion
of rows to arrays; it excludes reading the CSV. No L2S11 file is read.

Example
-------
``python scripts/memory_profile.py --data-root "data/2.+Composites/2. Composites"``
"""

import argparse
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile

from common import ROOT, require, require_not_recorded, write_csv

WORKLOADS = ('extraction', 'fit_predict_selected', 'fit_predict_v1_all')
BASELINE = ROOT / 'results' / 'baseline'


def fit_predict_runs(names):
    """Return the ``(train, evaluation, model, seed)`` runs for the given models.

    Parameters
    ----------
    names : sequence of str
        Model names from ``config/model_comparison.json``.

    Returns
    -------
    list of tuple
        One entry per direction, model and (for the MLP) declared seed.
    """
    from model_comparison import CONFIG

    runs = []
    for train_name, evaluation_name in CONFIG['directions']:
        for name in names:
            seeds = CONFIG['mlp_seeds'] if name == 'MLPRegressor' else [None]
            runs += [(train_name, evaluation_name, name, seed) for seed in seeds]
    return runs


def measure(workload, data_root):
    """Run one workload in this process and return its peak traced allocation.

    Parameters
    ----------
    workload : str
        One of ``WORKLOADS``.
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory (used by ``extraction`` only).

    Returns
    -------
    dict
        ``peak_bytes`` and ``current_bytes_at_end`` from ``tracemalloc``.

    Raises
    ------
    ValueError
        If the workload is unknown, or if the extraction outputs differ from
        the recorded baseline.
    """
    import tracemalloc

    require(workload in WORKLOADS, f'Unknown workload {workload}')
    if workload == 'extraction':
        import contextlib
        import os

        import exploratory_regression
        from profile_raw_workflow import check_output

        with tempfile.TemporaryDirectory() as temp, open(os.devnull, 'w') as sink:
            out = Path(temp) / 'extraction'
            argv = ['--data-root', str(data_root), '--output', str(out)]
            # The extractor prints its summary; keep it out of the child's JSON stdout.
            with contextlib.redirect_stdout(sink):
                tracemalloc.start()
                exploratory_regression.main(argv)
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            check_output(out)
    else:
        from threadpoolctl import threadpool_limits

        from model_comparison import CONFIG, MODEL_NAMES, fit_direction
        from reproduce_results import read_checkpoints

        rows = read_checkpoints(BASELINE / 'checkpoint_features.csv')
        names = ['LinearRegression'] if workload == 'fit_predict_selected' else MODEL_NAMES
        runs = fit_predict_runs(names)
        # Same fixed thread limit as the recorded v1 timings.
        with threadpool_limits(limits=CONFIG['timing']['threads']):
            tracemalloc.start()
            for train_name, evaluation_name, name, seed in runs:
                fit_direction(rows, train_name, evaluation_name, name, seed)
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
    return dict(peak_bytes=peak, current_bytes_at_end=current)


def main(argv=None):
    """Measure every workload in fresh processes and write the results.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If the output folder is a recorded results folder or lies inside the
        dataset, or if a child measurement fails.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results' / 'rebuilt' / 'memory_profile',
        help='New output folder; recorded results folders are refused.',
    )
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--child', choices=WORKLOADS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    data_root = args.data_root.expanduser().resolve()
    if args.child:
        print(json.dumps(measure(args.child, data_root)))
        return
    out = require_not_recorded(args.output.expanduser())
    require(
        data_root not in out.parents and out != data_root,
        'Output must be outside the original dataset.',
    )
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for workload in WORKLOADS:
        for repetition in range(1, args.repeats + 1):
            # A fresh interpreter per repetition, so no cache or allocator state
            # carries over from an earlier measurement.
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                '--data-root',
                str(data_root),
                '--child',
                workload,
            ]
            done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
            require(done.returncode == 0, f'{workload} failed:\n{done.stderr}')
            result = json.loads(done.stdout.strip().splitlines()[-1])
            rows.append(
                dict(
                    workload=workload,
                    repetition=repetition,
                    peak_bytes=result['peak_bytes'],
                    peak_MiB=result['peak_bytes'] / 2**20,
                    current_bytes_at_end=result['current_bytes_at_end'],
                )
            )
            print(f'{workload} #{repetition}: {rows[-1]["peak_MiB"]:.3f} MiB')
    write_csv(out / 'measurements.csv', rows)
    import numpy
    import scipy
    import sklearn

    summary = dict(
        measure='peak traced allocations (tracemalloc), per fresh process',
        caveat=(
            'Includes allocations registered with tracemalloc; not total process RAM, '
            'and not necessarily all native-library allocations.'
        ),
        excluded=(
            'Module imports and, for fit+predict, reading checkpoint_features.csv '
            'happen before tracemalloc.start().'
        ),
        preprocessing_in_fit_predict=(
            'Included: rows to arrays and training-only scaling inside the model pipeline.'
        ),
        extraction_outputs_match_baseline=True,
        median_peak_bytes={
            w: statistics.median(r['peak_bytes'] for r in rows if r['workload'] == w)
            for w in WORKLOADS
        },
        repeats=args.repeats,
        python=platform.python_version(),
        platform=platform.platform(),
        numpy=numpy.__version__,
        scipy=scipy.__version__,
        scikit_learn=sklearn.__version__,
    )
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
