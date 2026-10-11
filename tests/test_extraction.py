"""Unit tests for feature extraction, eligibility, label-blind references and guards.

These tests use synthetic MAT-like structures, so they run without the NASA data.
"""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from common import load_experiment_v1, require, scalar, waveform_features
from exploratory_regression import (LABEL_REASON, assess_recording, build_checkpoints,
                                    check_integrity, evaluate_transfer, select_reference)

EXPERIMENT = load_experiment_v1()


def sine(amplitude, offset=0.0, n=2000, periods=25):
    """Sampled sine whose samples include the exact positive and negative peaks."""
    t = np.arange(n) / n
    return offset + amplitude * np.sin(2 * np.pi * periods * t)


def coupon(cycles=1000.0, label=0.1, load=4.0, condition='Loaded', gain=33, amplitude=65,
           sampling_rate=1200000, length=2000, receiver_amplitude=100.0, spike=0.0, paths=None):
    """Minimal L1S11-like coupon with one 1 -> 7 at 150 kHz path.

    ``spike`` is added to the first receiver sample so RMS and PTP can vary
    independently (for a pure sine they are exactly proportional).
    """
    if paths is None:
        receiver = sine(receiver_amplitude, n=length)
        receiver[0] += spike
        paths = [dict(actuator=1, sensor=7, frequency=150, gain=gain, amplitude=amplitude,
                      sampling_rate=sampling_rate, signal_actuator=sine(1.0, n=length),
                      signal_sensor=receiver),
                 dict(actuator=2, sensor=8, frequency=150, gain=gain, amplitude=amplitude,
                      sampling_rate=sampling_rate, signal_actuator=sine(1.0),
                      signal_sensor=sine(5.0))]
    return dict(cycles=cycles, load=load, condition=condition, path_data=paths,
                straingage_data=dict(stiffness_degradation=[] if label is None else label))


def assess(name='x.mat', specimen='L1S11', **kwargs):
    return assess_recording(coupon(**kwargs), specimen, name, EXPERIMENT)


class FeatureTests(unittest.TestCase):
    def test_sine_rms_and_peak_to_peak(self):
        for amplitude in (0.5, 3.0, 250.0):
            rms, ptp = waveform_features(sine(amplitude))
            self.assertAlmostEqual(rms, amplitude / np.sqrt(2), places=9)
            self.assertAlmostEqual(ptp, 2 * amplitude, places=9)

    def test_features_ignore_constant_offset(self):
        np.testing.assert_allclose(waveform_features(sine(2.0, offset=40.0)),
                                   waveform_features(sine(2.0)), rtol=1e-12)

    def test_scalar_keeps_missing_values_missing(self):
        self.assertEqual(scalar(0.25), 0.25)
        for missing in ([], [0.0, 0.0], 'Loaded', float('nan'), float('inf'), None):
            self.assertIsNone(scalar(missing))


class EligibilityTests(unittest.TestCase):
    def test_valid_recording_is_eligible_with_features(self):
        r = assess()
        self.assertTrue(r['eligible'] and r['_acquisition_eligible'])
        self.assertEqual(r['exclusion_reasons'], '')
        self.assertAlmostEqual(r['mean_centred_rms'], 100 / np.sqrt(2), places=9)
        self.assertAlmostEqual(r['peak_to_peak'], 200.0, places=9)

    def test_each_acquisition_rule_excludes(self):
        cases = {'not a positive-cycle checkpoint': dict(cycles=0.0),
                 'condition is not Loaded': dict(condition='Clamped'),
                 'load outside 3.95-4.05 kips': dict(load=4.06),
                 'gain != 33': dict(gain=35),
                 'amplitude != 65': dict(amplitude=50),
                 'sampling_rate != 1200000': dict(sampling_rate=12000000),
                 'signal_sensor length != 2000': dict(length=1999)}
        for reason, kwargs in cases.items():
            with self.subTest(reason=reason):
                r = assess(**kwargs)
                self.assertFalse(r['eligible'] or r['_acquisition_eligible'])
                self.assertIn(reason, r['exclusion_reasons'])
                self.assertIsNone(r['mean_centred_rms'])

    def test_condition_text_is_normalised_and_load_bounds_inclusive(self):
        for kwargs in (dict(condition='  loaded '), dict(load=3.95), dict(load=4.05)):
            self.assertTrue(assess(**kwargs)['eligible'], kwargs)

    def test_missing_or_ambiguous_path_excludes(self):
        base = coupon()['path_data']
        for paths in ([base[1]], [base[0], copy.deepcopy(base[0])]):
            r = assessment = assess_recording(coupon(paths=paths), 'L1S11', 'p.mat', EXPERIMENT)
            self.assertIn('requested path missing or ambiguous', assessment['exclusion_reasons'])
            self.assertFalse(r['_acquisition_eligible'])

    def test_missing_label_is_not_filled_and_does_not_affect_acquisition(self):
        unlabelled, labelled = assess(label=None), assess(label=0.2)
        self.assertIsNone(unlabelled['published_index'])
        self.assertEqual(unlabelled['exclusion_reasons'], LABEL_REASON)
        self.assertFalse(unlabelled['eligible'])
        self.assertTrue(unlabelled['_acquisition_eligible'])
        self.assertIsNone(unlabelled['mean_centred_rms'])  # historical export unchanged
        self.assertEqual((unlabelled['_rms'], unlabelled['_ptp']), (labelled['_rms'], labelled['_ptp']))

    def test_specimen_specific_settings_come_from_config(self):
        self.assertTrue(assess(specimen='L1S12', gain=35, amplitude=50)['eligible'])
        self.assertFalse(assess(specimen='L1S12', gain=33, amplitude=65)['eligible'])


class ReferenceTests(unittest.TestCase):
    def rows(self, earliest_label=None):
        return [assess('a.mat', cycles=1.0, label=earliest_label, receiver_amplitude=50.0),
                assess('b.mat', cycles=10.0, label=0.05, receiver_amplitude=40.0),
                assess('c.mat', cycles=10.0, label=0.05, receiver_amplitude=44.0),
                assess('d.mat', cycles=100.0, label=0.07, receiver_amplitude=30.0),
                assess('e.mat', cycles=0.5, label=0.0, condition='Clamped')]

    def test_earliest_unlabelled_eligible_checkpoint_is_reference(self):
        ref = select_reference(self.rows(earliest_label=None))
        self.assertEqual((ref['cycles'], ref['filenames']), (1, 'a.mat'))
        self.assertAlmostEqual(ref['ptp_denominator'], 100.0, places=9)

    def test_labels_cannot_change_reference(self):
        self.assertEqual(select_reference(self.rows(None)), select_reference(self.rows(0.3)))
        relabelled = self.rows(None)
        for r in relabelled:
            r['published_index'] = 99.0
        self.assertEqual(select_reference(relabelled), select_reference(self.rows(None)))

    def test_reference_uses_median_over_repeats(self):
        rows = [r for r in self.rows() if r['filename'] in ('b.mat', 'c.mat', 'd.mat')]
        ref = select_reference(rows)
        self.assertEqual((ref['cycles'], ref['filenames']), (10, 'b.mat; c.mat'))
        self.assertAlmostEqual(ref['ptp_denominator'], 84.0, places=9)

    def test_no_eligible_reference_or_zero_denominator_fails(self):
        with self.assertRaisesRegex(ValueError, 'No acquisition-eligible'):
            select_reference([assess(condition='Clamped')])
        with self.assertRaisesRegex(ValueError, 'Invalid reference denominator'):
            select_reference([assess(receiver_amplitude=0.0)])

    def test_unlabelled_reference_is_kept_but_never_scored(self):
        cps, ref = build_checkpoints('L1S11', self.rows(None), EXPERIMENT)
        self.assertEqual([c['cycles'] for c in cps], [1, 10, 100])
        self.assertTrue(cps[0]['is_reference'])
        self.assertIsNone(cps[0]['published_index'])
        self.assertEqual(cps[0]['relative_ptp'], 1.0)
        self.assertAlmostEqual(cps[1]['relative_ptp'], 84.0 / 100.0, places=12)
        self.assertEqual(ref['specimen'], 'L1S11')

    def test_unlabelled_non_reference_checkpoint_stays_missing(self):
        rows = self.rows(0.01) + [assess('f.mat', cycles=50.0, label=None)]
        cps, _ = build_checkpoints('L1S11', rows, EXPERIMENT)
        self.assertNotIn(50, [c['cycles'] for c in cps])

    def test_conflicting_labels_are_rejected(self):
        rows = [assess('a.mat', cycles=1.0, label=0.0), assess('b.mat', cycles=10.0, label=0.05),
                assess('c.mat', cycles=10.0, label=0.06)]
        with self.assertRaisesRegex(ValueError, 'Conflicting published labels'):
            build_checkpoints('L1S11', rows, EXPERIMENT)

    def test_transfer_ignores_references_and_unlabelled_rows(self):
        checkpoints = []
        for specimen, gain, amp, scale in (('L1S11', 33, 65, 1.0), ('L1S12', 35, 50, 1.3)):
            rows = [assess(f'{specimen}_{c}.mat', specimen=specimen, cycles=float(c), label=label,
                           gain=gain, amplitude=amp, receiver_amplitude=a, spike=b)
                    for c, label, a, b in [(1, None, 100.0, 0.0), (10, 0.05 * scale, 95.0, 30.0),
                                           (100, 0.08 * scale, 90.0, 5.0),
                                           (1000, 0.1 * scale, 70.0, 60.0),
                                           (10000, 0.12 * scale, 60.0, 20.0)]]
            checkpoints += build_checkpoints(specimen, rows, EXPERIMENT)[0]
        predictions, metrics, _ = evaluate_transfer(checkpoints, EXPERIMENT)
        self.assertNotIn(1, {p['cycles'] for p in predictions})
        self.assertTrue(all(m['train_checkpoints'] == 4 and m['test_checkpoints'] == 4 for m in metrics))


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.recordings = [dict(specimen='L1S12', cycles=20000.0, published_index=None)]
        self.checkpoints = [dict(specimen='L1S12', cycles=30000, published_index=0.233175942)]
        self.references = [dict(specimen='L1S11', cycles=1), dict(specimen='L1S12', cycles=1)]
        self.predictions = [dict(test_specimen='L1S12', cycles=30000)]

    def run_check(self):
        check_integrity(self.recordings, self.checkpoints, self.references, self.predictions,
                        EXPERIMENT)

    def test_valid_tables_pass(self):
        self.run_check()

    def test_filled_missing_label_fails(self):
        self.recordings[0]['published_index'] = 0.1
        with self.assertRaisesRegex(ValueError, 'gained a label'):
            self.run_check()

    def test_dropped_or_changed_jump_fails(self):
        self.checkpoints[0]['published_index'] = 0.2
        with self.assertRaisesRegex(ValueError, 'jump not retained'):
            self.run_check()

    def test_scored_reference_fails(self):
        self.predictions.append(dict(test_specimen='L1S11', cycles=1))
        with self.assertRaisesRegex(ValueError, 'reference checkpoint was scored'):
            self.run_check()


class GuardTests(unittest.TestCase):
    def test_require_raises_value_error(self):
        require(True, 'unused')
        with self.assertRaisesRegex(ValueError, 'boom'):
            require(False, 'boom')

    def test_require_survives_optimised_python(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); from common import require; '
                "require(False, 'still checked')")
        result = subprocess.run([sys.executable, '-O', '-c', code, str(ROOT/'scripts')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still checked', result.stderr)

    def test_historical_constants_unchanged(self):
        s = EXPERIMENT['specimens']
        self.assertEqual((s['L1S11']['gain'], s['L1S11']['amplitude']), (33, 65))
        self.assertEqual((s['L1S12']['gain'], s['L1S12']['amplitude']), (35, 50))
        self.assertEqual((s['L1S11']['non_reference_checkpoints'],
                          s['L1S12']['non_reference_checkpoints']), (13, 12))
        self.assertEqual(EXPERIMENT['load_window_kips'], [3.95, 4.05])
        self.assertEqual(EXPERIMENT['integrity']['retained_jump']['published_index'], 0.233175942)
        self.assertEqual(EXPERIMENT['coverage_reported_outside'], {'L1S11': 12, 'L1S12': 11})

    def test_scripts_refuse_to_overwrite_recorded_results(self):
        import model_comparison
        import repeat_sensitivity
        with tempfile.TemporaryDirectory() as temp:
            data_root = Path(temp)/'2. Composites'
            for layup in ('Layup1', 'Layup2', 'Layup3'):
                (data_root/layup).mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'outside recorded results'):
                model_comparison.main(['--data-root', str(data_root),
                                       '--output', str(ROOT/'results/model_comparison')])
            with self.assertRaisesRegex(ValueError, 'separate'):
                repeat_sensitivity.main(['--data-root', str(data_root),
                                         '--output', str(ROOT/'results/repeat_sensitivity')])

    def test_importing_extractor_has_no_side_effects(self):
        result = subprocess.run([sys.executable, '-c', 'import exploratory_regression'],
                                cwd=ROOT/'scripts', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
