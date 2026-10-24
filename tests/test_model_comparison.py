"""Scientific boundary checks for the predeclared specimen-held-out experiment."""

import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from model_comparison import (
    CONFIG,
    MODEL_NAMES,
    build_model,
    fit_direction,
    fitted_parts,
    matrix,
    select_reference_candidates,
    split_rows,
)
from reproduce_results import read_checkpoints
from repeat_sensitivity import read_csv, digest

BASE = ROOT / 'results/baseline'
OUT = ROOT / 'results/model_comparison'


class ModelComparisonTests(unittest.TestCase):
    """Specimen separation, training-only preprocessing and agreement with recorded v1 outputs."""

    @classmethod
    def setUpClass(cls):
        """Load the recorded baseline checkpoints and limit BLAS to one thread."""
        cls.rows = read_checkpoints(BASE / 'checkpoint_features.csv')
        cls.threads = threadpool_limits(limits=1)

    @classmethod
    def tearDownClass(cls):
        """Restore the original BLAS thread limits."""
        cls.threads.restore_original_limits()

    def test_specimen_separation_and_reference_exclusion(self):
        """Leakage: train and evaluation sets are different specimens and exclude the reference."""
        for train_name, eval_name in CONFIG['directions']:
            train, evaluation = split_rows(self.rows, train_name, eval_name)
            self.assertEqual({r['specimen'] for r in train}, {train_name})
            self.assertEqual({r['specimen'] for r in evaluation}, {eval_name})
            self.assertFalse(any(r['is_reference'] or r['cycles'] == 1 for r in train + evaluation))
            self.assertEqual(len(train) + len(evaluation), 25)
        with self.assertRaisesRegex(ValueError, 'must differ'):
            split_rows(self.rows, 'L1S11', 'L1S11')

    def test_training_only_input_and_target_scaling(self):
        """Leakage: scalers are fitted on training rows only; predictions return in index units."""
        for train_name, eval_name in CONFIG['directions']:
            for name in MODEL_NAMES:
                seed = CONFIG['mlp_seeds'][0] if name == 'MLPRegressor' else None
                model, train, _, _, _, _ = fit_direction(
                    self.rows, train_name, eval_name, name, seed
                )
                pipeline, target = fitted_parts(model)
                scaler = pipeline.named_steps['scale']
                if scaler != 'passthrough':
                    x = matrix(train, name)
                    np.testing.assert_allclose(scaler.mean_, x.mean(axis=0))
                    np.testing.assert_allclose(scaler.var_, x.var(axis=0))
                    self.assertEqual(scaler.n_samples_seen_, len(train))
                if target is not None:
                    y = np.array([r['published_index'] for r in train])
                    np.testing.assert_allclose(target.mean_, [y.mean()])
                    np.testing.assert_allclose(target.var_, [y.var()])
                    self.assertEqual(target.n_samples_seen_, len(train))
                    manual = target.inverse_transform(
                        pipeline.predict(matrix(train, name)).reshape(-1, 1)
                    ).ravel()
                    np.testing.assert_allclose(model.predict(matrix(train, name)), manual)

    def test_evaluation_targets_and_reference_targets_cannot_change_predictions(self):
        """Leakage: changing evaluation or reference targets changes no model's predictions."""
        for train_name, eval_name in CONFIG['directions']:
            changed = copy.deepcopy(self.rows)
            for row in changed:
                if row['specimen'] == eval_name or row['is_reference']:
                    row['published_index'] = 1000 + row['cycles']
            for name in MODEL_NAMES:
                seeds = CONFIG['mlp_seeds'] if name == 'MLPRegressor' else [None]
                for seed in seeds:
                    before = fit_direction(self.rows, train_name, eval_name, name, seed)
                    after = fit_direction(changed, train_name, eval_name, name, seed)
                    np.testing.assert_array_equal(before[3], after[3])
                    np.testing.assert_array_equal(before[4], after[4])

    def test_evaluation_features_do_not_enter_fitted_scalers(self):
        """Leakage: shifted evaluation features change neither training predictions nor scalers."""
        changed = copy.deepcopy(self.rows)
        for row in changed:
            if row['specimen'] == 'L1S12':
                row['relative_rms'] += 1000
                row['relative_ptp'] -= 1000
        for name in ('LinearRegression', 'SVR', 'MLPRegressor'):
            seed = 7 if name == 'MLPRegressor' else None
            before = fit_direction(self.rows, 'L1S11', 'L1S12', name, seed)
            after = fit_direction(changed, 'L1S11', 'L1S12', name, seed)
            np.testing.assert_array_equal(before[3], after[3])
            np.testing.assert_array_equal(
                fitted_parts(before[0])[0].named_steps['scale'].mean_,
                fitted_parts(after[0])[0].named_steps['scale'].mean_,
            )

    def test_sklearn_linear_predictions_match_existing_ols(self):
        """Known answer: sklearn linear and log-cycle predictions match the recorded v1 OLS."""
        expected = read_csv(BASE / 'predictions.csv')
        for train_name, eval_name in CONFIG['directions']:
            for name, old_name in [
                ('LinearRegression', 'relative_rms_and_ptp'),
                ('log_cycle_OLS', 'log10_cycles'),
            ]:
                _, _, evaluation, _, pred, _ = fit_direction(self.rows, train_name, eval_name, name)
                lookup = {
                    int(r['cycles']): float(r['predicted_index'])
                    for r in expected
                    if r['train_specimen'] == train_name and r['model'] == old_name
                }
                np.testing.assert_allclose(
                    pred, [lookup[r['cycles']] for r in evaluation], rtol=1e-9, atol=1e-10
                )

    def test_reference_selection_does_not_read_targets(self):
        """Leakage: dropping label fields keeps the reference; an earlier unlabelled file wins."""
        records = read_csv(BASE / 'recordings.csv')
        original, _ = select_reference_candidates(records)
        altered = copy.deepcopy(records)
        for r in altered:
            r.pop('published_index')
            r.pop('eligible')
            r.pop('exclusion_reasons')
        modified, candidates = select_reference_candidates(altered)
        for specimen in original:
            self.assertEqual(
                [r['filename'] for r in original[specimen]],
                [r['filename'] for r in modified[specimen]],
            )
        # Unlabelled acquisition-eligible 20,000-cycle L1S12 recordings remain candidates.
        self.assertTrue(
            any(r['specimen'] == 'L1S12' and float(r['cycles']) == 20000 for r in candidates)
        )
        # An artificial earlier unlabelled acquisition is selected, instead of
        # silently using labelled data.
        earlier = copy.deepcopy(modified['L1S11'][0])
        earlier.update(cycles='0.5', filename='unlabelled_earlier.mat')
        selected, _ = select_reference_candidates(altered + [earlier])
        self.assertEqual(selected['L1S11'][0]['filename'], 'unlabelled_earlier.mat')

    def test_all_declared_seeds_no_internal_split_and_saved_metrics(self):
        """All MLP seeds ran without early stopping; saved metrics and hashes recompute."""
        metrics = read_csv(OUT / 'metrics.csv')
        predicted = read_csv(OUT / 'predictions.csv')
        for seed in CONFIG['mlp_seeds']:
            estimator = build_model('MLPRegressor', seed).regressor.named_steps['model']
            self.assertFalse(estimator.early_stopping)
            self.assertEqual(estimator.solver, 'lbfgs')
            self.assertEqual(estimator.random_state, seed)
        for train_name, _ in CONFIG['directions']:
            self.assertEqual(
                {
                    int(r['seed'])
                    for r in metrics
                    if r['train_specimen'] == train_name and r['model'] == 'MLPRegressor'
                },
                set(CONFIG['mlp_seeds']),
            )
        for metric in metrics:
            group = [
                r
                for r in predicted
                if all(r[k] == metric[k] for k in ('train_specimen', 'model', 'seed', 'split'))
            ]
            y = np.array([float(r['observed']) for r in group])
            p = np.array([float(r['predicted']) for r in group])
            residual = p - y
            independent = [
                np.abs(residual).mean(),
                np.sqrt((residual**2).mean()),
                1 - (residual**2).sum() / ((y - y.mean()) ** 2).sum(),
            ]
            np.testing.assert_allclose(
                [float(metric[k]) for k in ('MAE', 'RMSE', 'R2')], independent
            )
        receipt = json.loads((OUT / 'protocol_receipt.json').read_text())
        self.assertEqual(
            receipt['protocol_sha256'], digest(ROOT / 'docs/model_comparison_protocol.md')
        )
        self.assertEqual(receipt['config_sha256'], digest(ROOT / 'config/model_comparison.json'))


if __name__ == '__main__':
    unittest.main()
