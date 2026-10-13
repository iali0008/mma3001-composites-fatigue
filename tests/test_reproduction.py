"""Check recorded scientific results and specimen/target leakage boundaries."""

import copy
import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from reproduce_results import evaluate, read_checkpoints

BASELINE = ROOT / 'results/baseline'


class ReproductionTests(unittest.TestCase):
    def test_reproduces_recorded_metrics_and_predictions(self):
        metrics, predictions, _ = evaluate(read_checkpoints(BASELINE / 'checkpoint_features.csv'))
        with (BASELINE / 'metrics.csv').open(newline='') as f:
            expected = {(r['train_specimen'], r['model']): r for r in csv.DictReader(f)}
        self.assertEqual(len(metrics), 6)
        self.assertEqual(len(expected), 6)
        for actual in metrics:
            row = expected[(actual['train_specimen'], actual['model'])]
            np.testing.assert_allclose(
                [actual['MAE'], actual['RMSE']],
                [float(row['MAE']), float(row['RMSE'])],
                atol=1e-10,
                rtol=1e-9,
            )
        with (BASELINE / 'predictions.csv').open(newline='') as f:
            expected_p = {
                (r['train_specimen'], r['model'], int(r['cycles'])): float(r['predicted_index'])
                for r in csv.DictReader(f)
            }
        self.assertEqual(len(predictions), 75)
        self.assertEqual(len(expected_p), 75)
        for actual in predictions:
            key = (actual['train_specimen'], actual['model'], actual['cycles'])
            self.assertNotEqual(actual['cycles'], 1)
            self.assertAlmostEqual(actual['predicted_index'], expected_p[key], places=10)

    def test_reference_targets_do_not_affect_fit_or_scores(self):
        rows = read_checkpoints(BASELINE / 'checkpoint_features.csv')
        original = evaluate(rows)
        changed = copy.deepcopy(rows)
        for row in changed:
            if row['is_reference']:
                row['published_index'] = 9999
        self.assertEqual(evaluate(changed), original)

    def test_test_targets_do_not_affect_predictions(self):
        for test_specimen in ('L1S11', 'L1S12'):
            with self.subTest(test_specimen=test_specimen):
                rows = read_checkpoints(BASELINE / 'checkpoint_features.csv')
                _, original, _ = evaluate(rows)
                changed = copy.deepcopy(rows)
                for row in changed:
                    if row['specimen'] == test_specimen and not row['is_reference']:
                        row['published_index'] += 10
                _, recomputed, _ = evaluate(changed)
                before = [
                    r['predicted_index'] for r in original if r['test_specimen'] == test_specimen
                ]
                after = [
                    r['predicted_index'] for r in recomputed if r['test_specimen'] == test_specimen
                ]
                np.testing.assert_array_equal(before, after)

    def test_duplicate_checkpoint_rejected(self):
        with (BASELINE / 'checkpoint_features.csv').open(newline='') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'duplicated.csv'
            with path.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows + [rows[1]])
            with self.assertRaisesRegex(ValueError, 'Duplicate checkpoint'):
                read_checkpoints(path)


if __name__ == '__main__':
    unittest.main()
