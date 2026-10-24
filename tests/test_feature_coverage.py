"""Geometric boundary cases and isolation of the coverage scaler."""

from pathlib import Path
import sys
import unittest
import csv

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from feature_coverage import diagnose, triangle_membership
from reproduce_results import read_checkpoints


class FeatureCoverageTests(unittest.TestCase):
    """Convex-hull coverage diagnostic: known geometry and training-only scaling."""

    def test_known_square_interior_boundary_and_exterior(self):
        """Known answer: unit-square interior and edge points are inside; both methods agree."""
        training = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        evaluation = np.array([[0.5, 0.5], [1.0, 0.5], [0.0, 0.0], [1.1, 0.5], [-0.1, 0.5]])
        result = diagnose(training, evaluation)
        np.testing.assert_array_equal(result['inside'][4:], [True, True, True, False, False])
        np.testing.assert_array_equal(result['independent'], result['inside'])

    def test_scaler_and_hull_use_only_training_points(self):
        """Leakage: an extreme evaluation point changes neither the scaler nor the hull."""
        training = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 4.0], [0.0, 4.0]])
        first = diagnose(training, np.array([[1.0, 2.0]]))
        changed = diagnose(training, np.array([[1e6, -1e6], [1.0, 2.0]]))
        np.testing.assert_array_equal(first['scaler'].mean_, training.mean(axis=0))
        np.testing.assert_array_equal(first['scaler'].scale_, training.std(axis=0))
        np.testing.assert_array_equal(first['scaler'].mean_, changed['scaler'].mean_)
        np.testing.assert_array_equal(first['hull'].vertices, changed['hull'].vertices)
        self.assertEqual(changed['scaler'].n_samples_seen_, 4)

    def test_triangle_method_handles_duplicate_points_without_hull_library(self):
        """The independent triangle check copes with a repeated training point."""
        training = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
        np.testing.assert_array_equal(
            triangle_membership(training, np.array([[0.2, 0.2], [0.8, 0.8]])), [True, False]
        )

    def test_saved_flags_preserve_checkpoint_membership_and_verified_counts(self):
        """Saved flags cover all non-reference checkpoints and match the 12/11 outside counts."""
        checkpoints = read_checkpoints(ROOT / 'results/baseline/checkpoint_features.csv')
        expected = {(r['specimen'], r['cycles']) for r in checkpoints if not r['is_reference']}
        with (ROOT / 'results/model_comparison/coverage/checkpoint_coverage.csv').open(
            newline=''
        ) as stream:
            flags = list(csv.DictReader(stream))
        self.assertEqual(len(flags), 50)
        for train, outside in [('L1S11', 12), ('L1S12', 11)]:
            local = [r for r in flags if r['train_specimen'] == train]
            self.assertEqual({(r['specimen'], int(r['cycles'])) for r in local}, expected)
            self.assertEqual(
                sum(
                    r['outside_training_hull'] == 'True'
                    for r in local
                    if r['split'] == 'evaluation'
                ),
                outside,
            )
            self.assertTrue(
                all(
                    r['outside_training_hull'] == 'False' for r in local if r['split'] == 'training'
                )
            )
            self.assertTrue(
                all(r['inside_or_on_training_hull'] == r['triangle_check_inside'] for r in local)
            )


if __name__ == '__main__':
    unittest.main()
