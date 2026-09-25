"""Refit the first experiment from exported checkpoint features, without MAT files.

Reference features are permitted at deployment. Their targets are never used
for model fitting or scoring. The recorded experiment is exploratory, not an
independent estimate of population-level performance.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    'log10_cycles': ('log10_cycles',),
    'relative_rms': ('relative_rms',),
    'relative_rms_and_ptp': ('relative_rms', 'relative_ptp'),
}


def read_checkpoints(path: Path) -> list[dict]:
    """Load a checkpoint table and reject ambiguous or malformed observations."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        numeric = ('cycles', 'published_index', 'relative_rms', 'relative_ptp', 'log10_cycles')
        required = {'specimen', 'is_reference', *numeric}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f'Missing columns: {sorted(required - set(reader.fieldnames or ()))}')
        rows = []
        seen = set()
        for row in reader:
            for field in numeric:
                row[field] = float(row[field])
            if not np.isfinite([row[f] for f in numeric]).all():
                raise ValueError('Checkpoint values must be finite.')
            if row['cycles'] <= 0 or not row['cycles'].is_integer():
                raise ValueError('Cycle count must be a positive integer.')
            row['cycles'] = int(row['cycles'])
            key = (row['specimen'], row['cycles'])
            if key in seen:
                raise ValueError(f'Duplicate checkpoint: {key}')
            seen.add(key)
            flag = row['is_reference'].strip().lower()
            if flag not in ('true', 'false'):
                raise ValueError('is_reference must be True or False.')
            row['is_reference'] = flag == 'true'
            rows.append(row)
    if {r['specimen'] for r in rows} != {'L1S11', 'L1S12'}:
        raise ValueError('This experiment requires exactly L1S11 and L1S12.')
    for specimen in ('L1S11', 'L1S12'):
        local = [r for r in rows if r['specimen'] == specimen]
        refs = [r for r in local if r['is_reference']]
        if len(refs) != 1 or refs[0]['cycles'] != min(r['cycles'] for r in local):
            raise ValueError('Each specimen must have one earliest-checkpoint reference.')
        if not np.allclose([refs[0]['relative_rms'], refs[0]['relative_ptp']], 1):
            raise ValueError('Reference feature ratios must equal one.')
        if not np.allclose([r['log10_cycles'] for r in local], np.log10([r['cycles'] for r in local])):
            raise ValueError('log10_cycles disagrees with cycle counts.')
    return sorted(rows, key=lambda r: (r['specimen'], r['cycles']))


def evaluate(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Fit each direction independently; use training-only centering and scaling.

    Centered QR is numerically equivalent to OLS with an intercept, and provides
    a separate calculation from the original unscaled least-squares script.
    """
    metrics, predictions, coefficients = [], [], []
    for train_name, test_name in (('L1S11', 'L1S12'), ('L1S12', 'L1S11')):
        train = [r for r in rows if r['specimen'] == train_name and not r['is_reference']]
        test = [r for r in rows if r['specimen'] == test_name and not r['is_reference']]
        if not train or not test:
            raise ValueError('Both specimens need non-reference checkpoints.')
        y = np.array([r['published_index'] for r in train])
        observed = np.array([r['published_index'] for r in test])
        for model, fields in MODELS.items():
            x = np.array([[r[f] for f in fields] for r in train])
            xt = np.array([[r[f] for f in fields] for r in test])
            center, scale = x.mean(axis=0), x.std(axis=0)
            if (scale == 0).any():
                raise ValueError(f'Constant training feature: {model}')
            z = (x-center)/scale
            if np.linalg.matrix_rank(z) != len(fields):
                raise ValueError(f'Rank-deficient training features: {model}')
            q, upper = np.linalg.qr(z, mode='reduced')
            slopes = np.linalg.solve(upper, q.T @ (y-y.mean())) / scale
            intercept = float(y.mean() - center @ slopes)
            estimated = intercept + xt @ slopes
            residual = estimated-observed
            metrics.append(dict(train_specimen=train_name, test_specimen=test_name,
                                model=model, train_checkpoints=len(train), test_checkpoints=len(test),
                                MAE=float(np.abs(residual).mean()),
                                RMSE=float(np.sqrt(np.mean(residual**2)))))
            coefficients.append(dict(train_specimen=train_name, test_specimen=test_name,
                                     model=model, intercept=intercept, terms='; '.join(fields),
                                     slopes='; '.join(format(v, '.17g') for v in slopes)))
            for row, value, error in zip(test, estimated, residual):
                predictions.append(dict(train_specimen=train_name, test_specimen=test_name,
                                        model=model, cycles=row['cycles'],
                                        observed_index=row['published_index'],
                                        predicted_index=float(value), residual=float(error)))
    return metrics, predictions, coefficients


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, default=ROOT/'results/baseline/checkpoint_features.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'results/reproduced')
    args = parser.parse_args()
    output = args.output.resolve()
    baseline = ROOT/'results/baseline'
    if output == baseline or baseline in output.parents:
        parser.error('Preserve the recorded baseline; choose a different output folder.')
    metrics, predictions, coefficients = evaluate(read_checkpoints(args.features))
    output.mkdir(parents=True, exist_ok=True)
    for filename, values in [('metrics.csv', metrics), ('predictions.csv', predictions),
                             ('coefficients.csv', coefficients)]:
        write_csv(output/filename, values)
    for row in metrics:
        print(f"{row['train_specimen']} -> {row['test_specimen']} | {row['model']}: "
              f"MAE {row['MAE']:.6f}; RMSE {row['RMSE']:.6f}")
    print(f'Outputs: {output}')


if __name__ == '__main__':
    main()
