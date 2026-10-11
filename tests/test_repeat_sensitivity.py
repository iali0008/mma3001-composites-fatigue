"""Focused checks for frozen experiment boundaries and repeat selection."""

import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from repeat_sensitivity import build_variants, order_repeats, read_csv, compare_tables
from reproduce_results import read_checkpoints, evaluate

BASELINE = ROOT / 'results/baseline'
RESULTS = ROOT / 'results/repeat_sensitivity'


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.repeats = [
            dict(specimen='S', filename=name, cycles='10', condition='Loaded')
            for name in ('a.mat', 'z.mat')
        ]
        self.logs = {
            ('S', name): dict(acquired_at=stamp, log_cycle=10, log_condition='loaded')
            for name, stamp in [('a.mat', '2011-09-01 12:01:00'), ('z.mat', '2011-09-01 12:00:00')]
        }

    def test_timestamp_order_overrides_filename(self):
        ordered, basis, _ = order_repeats(self.repeats, self.logs)
        self.assertEqual([r['filename'] for r in ordered], ['z.mat', 'a.mat'])
        self.assertEqual(basis, 'logbook_timestamp')

    def test_missing_and_tied_timestamps_are_explicit_fallback(self):
        for logs in (
            {},
            {
                key: dict(value, acquired_at='2011-09-01 12:00:00')
                for key, value in self.logs.items()
            },
        ):
            ordered, basis, reason = order_repeats(self.repeats, logs)
            self.assertEqual(basis, 'filename_ordered')
            self.assertTrue(reason)
            self.assertEqual(ordered[0]['filename'], 'a.mat')

    def test_logbook_cycle_conflict_fails(self):
        self.logs[('S', 'a.mat')]['log_cycle'] = 20
        with self.assertRaisesRegex(ValueError, 'cycle mismatch'):
            order_repeats(self.repeats, self.logs)


class SensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = read_checkpoints(BASELINE / 'checkpoint_features.csv')
        cls.recordings = read_csv(BASELINE / 'recordings.csv')
        cls.refs = read_csv(BASELINE / 'references.csv')
        cls.variants, cls.provenance = build_variants(cls.recordings, cls.baseline, cls.refs, {})

    def test_median_features_and_predictions_reproduce_baseline(self):
        compare_tables(
            self.variants['median'],
            self.baseline,
            ('specimen', 'cycles'),
            ('mean_centred_rms', 'peak_to_peak', 'relative_rms', 'relative_ptp'),
        )
        for a, b in zip(evaluate(self.variants['median']), evaluate(self.baseline)):
            self.assertEqual(a, b)

    def test_membership_targets_references_and_cycle_model_fixed(self):
        fixed = ('specimen', 'cycles', 'published_index', 'is_reference', 'log10_cycles')
        expected_cycle = [r for r in evaluate(self.baseline)[0] if r['model'] == 'log10_cycles']
        for rows in self.variants.values():
            self.assertEqual(
                [tuple(r[f] for f in fixed) for r in rows],
                [tuple(r[f] for f in fixed) for r in self.baseline],
            )
            for actual, baseline in zip(rows, self.baseline):
                if actual['is_reference']:
                    for field in (
                        'filenames',
                        'mean_centred_rms',
                        'peak_to_peak',
                        'relative_rms',
                        'relative_ptp',
                    ):
                        if field == 'filenames':
                            self.assertEqual(actual[field], baseline[field])
                        else:
                            self.assertEqual(float(actual[field]), float(baseline[field]))
            self.assertEqual(
                [r for r in evaluate(rows)[0] if r['model'] == 'log10_cycles'], expected_cycle
            )

    def test_membership_and_target_changes_rejected(self):
        changed = copy.deepcopy(self.recordings)
        eligible = next(r for r in changed if r['eligible'] == 'True')
        eligible['published_index'] = '999'
        with self.assertRaisesRegex(ValueError, 'targets'):
            build_variants(changed, self.baseline, self.refs, {})
        changed = [
            r
            for r in self.recordings
            if not (r['specimen'] == 'L1S11' and float(r['cycles']) == 10)
        ]
        with self.assertRaisesRegex(ValueError, 'membership'):
            build_variants(changed, self.baseline, self.refs, {})

    def test_no_reference_or_test_target_leakage_in_any_variant(self):
        for rows in self.variants.values():
            original = evaluate(rows)
            changed = copy.deepcopy(rows)
            for row in changed:
                if row['is_reference']:
                    row['published_index'] = 999
            self.assertEqual(original, evaluate(changed))
            for specimen in ('L1S11', 'L1S12'):
                changed = copy.deepcopy(rows)
                for row in changed:
                    if row['specimen'] == specimen:
                        row['published_index'] += 100
                before = [
                    r['predicted_index'] for r in original[1] if r['test_specimen'] == specimen
                ]
                after = [
                    r['predicted_index']
                    for r in evaluate(changed)[1]
                    if r['test_specimen'] == specimen
                ]
                np.testing.assert_array_equal(before, after)

    def test_saved_results_and_selection_provenance(self):
        self.assertTrue(
            (RESULTS / 'verification.json').is_file(), 'Run repeat_sensitivity.py first'
        )
        verification = json.loads((RESULTS / 'verification.json').read_text())
        self.assertTrue(verification['baseline_reproduced'])
        self.assertTrue(verification['mat_hashes_match_baseline'])
        self.assertEqual(verification['git_exclusions']['tracked_raw_files'], 0)
        self.assertEqual(verification['git_exclusions']['staged_raw_files'], 0)
        self.assertTrue(verification['git_exclusions']['data_readme_tracked'])
        provenance = read_csv(RESULTS / 'selection_provenance.csv')
        recordings = {(r['specimen'], r['filename']): r for r in self.recordings}
        metrics = read_csv(RESULTS / 'metrics.csv')
        predictions = read_csv(RESULTS / 'predictions.csv')
        for variant in ('median', 'first', 'last'):
            rows = read_checkpoints(RESULTS / f'{variant}_checkpoint_features.csv')
            compare_tables(
                rows,
                self.baseline,
                ('specimen', 'cycles'),
                ('published_index', 'is_reference', 'reference_cycles', 'log10_cycles'),
            )
            compare_tables(
                [r for r in rows if r['is_reference']],
                [r for r in self.baseline if r['is_reference']],
                ('specimen',),
                ('filenames', 'mean_centred_rms', 'peak_to_peak', 'relative_rms', 'relative_ptp'),
            )
            actual, estimated, _ = evaluate(rows)
            compare_tables(
                actual,
                [r for r in metrics if r['variant'] == variant],
                ('train_specimen', 'model'),
                ('MAE', 'RMSE'),
            )
            # Recalculate scores directly from exported residuals, independently of evaluate.
            for metric in actual:
                ps = [
                    p
                    for p in predictions
                    if p['variant'] == variant
                    and p['train_specimen'] == metric['train_specimen']
                    and p['model'] == metric['model']
                ]
                errors = np.array(
                    [float(p['predicted_index']) - float(p['observed_index']) for p in ps]
                )
                np.testing.assert_allclose(
                    [metric['MAE'], metric['RMSE']],
                    [abs(errors).mean(), np.sqrt((errors**2).mean())],
                )
            if variant == 'median':
                continue
            for row in rows:
                if row['is_reference']:
                    continue
                group = [
                    r
                    for r in provenance
                    if r['specimen'] == row['specimen'] and int(r['cycles']) == row['cycles']
                ]
                ordered = sorted(group, key=lambda r: int(r['ordinal']))
                if all(r['order_basis'] == 'logbook_timestamp' for r in group):
                    stamps = [r['acquired_at'] for r in ordered]
                    self.assertEqual(stamps, sorted(set(stamps)))
                selected = ordered[0 if variant == 'first' else -1]
                self.assertEqual(row['filenames'], selected['filename'])
                raw = recordings[(row['specimen'], selected['filename'])]
                ref = next(r for r in self.refs if r['specimen'] == row['specimen'])
                self.assertEqual(
                    row['relative_rms'],
                    float(raw['mean_centred_rms']) / float(ref['rms_denominator']),
                )
                self.assertEqual(
                    row['relative_ptp'], float(raw['peak_to_peak']) / float(ref['ptp_denominator'])
                )


if __name__ == '__main__':
    unittest.main()
