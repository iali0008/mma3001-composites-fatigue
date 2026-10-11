"""Unit tests for protocol v2 eligibility, aggregation, label isolation and selection."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from protocol_v2 import (FAMILIES, INPUT_SETS, build_checkpoints, eligibility_reasons, load_protocol,
                         pairs, select_final, setting_vector, summarise_file)

PROTOCOL = load_protocol()
L1S11 = PROTOCOL['specimens']['L1S11']


def sine(amplitude, n=2000, periods=25):
    t = np.arange(n) / n
    return amplitude * np.sin(2 * np.pi * periods * t)


def coupon(cycles=10.0, load=4.0, condition='Loaded', label=0.1, scale=1.0, gain=33, amplitude=65,
           drop=None, extra=None, bad=None):
    """Synthetic coupon with the full 36-pair grid at 150 kHz plus one 300 kHz record.

    Pair (a, s) has receiver amplitude ``scale * (a + s)``; 1 -> 7 uses the
    specimen baseline gain/amplitude.
    """
    records = []
    for a, s in pairs(PROTOCOL):
        if (a, s) == drop:
            continue
        x = sine(scale * (a + s))
        if (a, s) == bad:
            x = np.zeros(2000)
        records.append(dict(actuator=a, sensor=s, frequency=150, gain=gain, amplitude=amplitude,
                            sampling_rate=1200000, signal_actuator=sine(1.0), signal_sensor=x))
    if extra:
        records.append(copy.deepcopy(records[0]))
    records.append(dict(actuator=1, sensor=7, frequency=300, gain=1, amplitude=1, sampling_rate=1,
                        signal_actuator=np.zeros(5), signal_sensor=np.zeros(5)))
    return dict(cycles=cycles, load=load, condition=condition, path_data=records,
                straingage_data=dict(stiffness_degradation=[] if label is None else label))


def summary(name='f.mat', read_labels=True, **kwargs):
    return summarise_file(coupon(**kwargs), 'L1S11', name, PROTOCOL, read_labels)


def screened(summaries):
    modal = setting_vector(summarise_file(coupon(), 'L1S11', 'm.mat', PROTOCOL, True), PROTOCOL)
    for s in summaries:
        reasons = eligibility_reasons(s, L1S11, modal, PROTOCOL)
        s['eligible'], s['exclusion_reasons'] = not reasons, '; '.join(reasons)
    return summaries


class EligibilityTests(unittest.TestCase):
    def test_valid_file_is_eligible(self):
        self.assertEqual(screened([summary()])[0]['exclusion_reasons'], '')

    def test_each_rule_excludes(self):
        cases = {'not a positive-cycle checkpoint': dict(cycles=0.0),
                 'condition is not loaded': dict(condition='Traction Free'),
                 'load outside 3.95-4.05 kips': dict(load=4.58),
                 '36-pair grid incomplete or duplicated': dict(drop=(3, 10)),
                 'baseline path missing or ambiguous': dict(drop=(1, 7)),
                 'baseline gain/amplitude mismatch': dict(gain=35),
                 'setting vector differs from specimen modal vector': dict(amplitude=50),
                 'invalid signal (length, nonfinite or constant)': dict(bad=(2, 9))}
        for reason, kwargs in cases.items():
            with self.subTest(reason=reason):
                s = screened([summary(**kwargs)])[0]
                self.assertFalse(s['eligible'])
                self.assertIn(reason, s['exclusion_reasons'])
        self.assertIn('duplicated', screened([summary(extra=True)])[0]['exclusion_reasons'])

    def test_labels_are_not_read_when_disabled(self):
        c = coupon(label=0.3)
        s = summarise_file(c, 'L1S11', 'x.mat', PROTOCOL, read_labels=False)
        self.assertIsNone(s['published_index'])
        self.assertNotIn('straingage_data', c)  # deleted before anything else is read

    def test_label_does_not_change_eligibility(self):
        a, b = screened([summary(label=None), summary(label=0.2)])
        self.assertEqual((a['eligible'], a['exclusion_reasons']), (b['eligible'], b['exclusion_reasons']))


class AggregationTests(unittest.TestCase):
    def build(self, first_label=None):
        files = [summary('a.mat', cycles=1.0, label=first_label, scale=1.0),
                 summary('b.mat', cycles=10.0, label=0.05, scale=0.8),
                 summary('c.mat', cycles=10.0, label=0.05, scale=0.9),
                 summary('d.mat', cycles=100.0, label=None, scale=0.5),
                 summary('e.mat', cycles=0.5, label=0.0, condition='Clamped')]
        return build_checkpoints(screened(files), PROTOCOL)

    def test_reference_is_earliest_eligible_even_if_unlabelled(self):
        cps, _, ref = self.build(first_label=None)
        self.assertEqual((ref['cycles'], ref['filenames']), (1, 'a.mat'))
        self.assertEqual([c['cycles'] for c in cps], [1, 10, 100])
        self.assertTrue(cps[0]['is_reference'])
        self.assertIsNone(cps[0]['published_index'])
        self.assertIsNone(cps[2]['published_index'])  # missing label stays missing

    def test_labels_cannot_change_features_or_reference(self):
        a, _, ra = self.build(first_label=None)
        b, _, rb = self.build(first_label=0.7)
        self.assertEqual(ra, rb)
        for x, y in zip(a, b):
            for f in ('relative_rms', 'relative_ptp', 'mp_relative_rms', 'mp_relative_ptp'):
                self.assertEqual(x[f], y[f])

    def test_per_pair_normalisation_then_median_over_pairs(self):
        cps, ratios, _ = self.build()
        ten = cps[1]
        self.assertAlmostEqual(ten['relative_ptp'], 0.85, places=12)  # median(0.8, 0.9)
        self.assertAlmostEqual(ten['mp_relative_ptp'], 0.85, places=12)
        self.assertAlmostEqual(ten['mp_relative_rms'], 0.85, places=12)
        self.assertEqual(len([r for r in ratios if r['cycles'] == 10]), 36)

    def test_multi_path_feature_ignores_pair_labelling(self):
        files = screened([summary('a.mat', cycles=1.0), summary('b.mat', cycles=10.0, scale=0.6)])
        permuted = copy.deepcopy(files)
        order = pairs(PROTOCOL)
        shuffled = order[1:] + order[:1]
        for s in permuted:
            for key in ('rms', 'ptp'):
                s[key] = {new: s[key][old] for old, new in zip(order, shuffled)}
        a = build_checkpoints(files, PROTOCOL)[0][1]
        b = build_checkpoints(permuted, PROTOCOL)[0][1]
        self.assertEqual(a['mp_relative_rms'], b['mp_relative_rms'])
        self.assertEqual(a['mp_relative_ptp'], b['mp_relative_ptp'])

    def test_conflicting_labels_rejected(self):
        files = screened([summary('a.mat', cycles=1.0), summary('b.mat', cycles=10.0, label=0.1),
                          summary('c.mat', cycles=10.0, label=0.2)])
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            build_checkpoints(files, PROTOCOL)


class SelectionTests(unittest.TestCase):
    def rows(self, values):
        return [dict(model=m, input_set=i, worst_direction_MAE=values.get((m, i), 0.2))
                for m in FAMILIES for i in INPUT_SETS]

    def test_lowest_worst_direction_mae_wins(self):
        result = select_final(self.rows({('SVR', 'multi_path_36'): 0.05}), PROTOCOL)
        self.assertEqual(result['selected']['model'], 'SVR')
        self.assertEqual(result['selected']['input_set'], 'multi_path_36')

    def test_ties_prefer_simpler_model_then_single_path(self):
        result = select_final(self.rows({('MLPRegressor', 'multi_path_36'): 0.0500,
                                         ('LinearRegression', 'multi_path_36'): 0.0504,
                                         ('LinearRegression', 'single_path_1_7'): 0.0506}), PROTOCOL)
        self.assertEqual((result['selected']['model'], result['selected']['input_set']),
                         ('LinearRegression', 'multi_path_36'))
        result = select_final(self.rows({('DecisionTreeRegressor', 'multi_path_36'): 0.05,
                                         ('DecisionTreeRegressor', 'single_path_1_7'): 0.05}), PROTOCOL)
        self.assertEqual(result['selected']['input_set'], 'single_path_1_7')

    def test_outside_tolerance_is_not_a_tie(self):
        result = select_final(self.rows({('MLPRegressor', 'single_path_1_7'): 0.0500,
                                         ('LinearRegression', 'single_path_1_7'): 0.0506}), PROTOCOL)
        self.assertEqual(result['selected']['model'], 'MLPRegressor')

    def test_candidate_set_must_be_complete(self):
        with self.assertRaisesRegex(ValueError, 'candidate set'):
            select_final(self.rows({})[:-1], PROTOCOL)

    def test_protocol_models_identical_to_v1(self):
        self.assertEqual(PROTOCOL['models']['mlp_seeds'], [7, 23, 42, 71, 101])
        self.assertEqual(PROTOCOL['selection_rule']['tie_tolerance_mae'], 0.0005)


if __name__ == '__main__':
    unittest.main()


class TestStageHelpers(unittest.TestCase):
    """Label attachment after blind prediction, and sanity criteria C1-C3."""

    def test_attach_labels_uses_eligible_files_and_keeps_missing(self):
        from protocol_v2 import attach_labels
        cps = [dict(cycles=3, filenames='a.mat; b.mat', published_index=None),
               dict(cycles=10, filenames='c.mat', published_index=None)]
        labels = {'a.mat': (3.0, None), 'b.mat': (3.0, None), 'c.mat': (10.0, 0.04),
                  'z.mat': (1.0, -0.012)}
        out = attach_labels(cps, labels)
        self.assertIsNone(out[0]['published_index'])
        self.assertEqual(out[1]['published_index'], 0.04)
        self.assertIsNone(cps[1]['published_index'])  # inputs are not modified

    def test_attach_labels_rejects_conflicts_and_unknown_files(self):
        from protocol_v2 import attach_labels
        cp = [dict(cycles=10, filenames='a.mat; b.mat', published_index=None)]
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            attach_labels(cp, {'a.mat': (10.0, 0.1), 'b.mat': (10.0, 0.2)})
        with self.assertRaisesRegex(ValueError, 'Unknown file'):
            attach_labels(cp, {'a.mat': (10.0, 0.1)})

    def test_sanity_criteria(self):
        from protocol_v2 import sanity_criteria
        ok = sanity_criteria([0.20, 0.22], 0.19, [0.04, 0.25], PROTOCOL)
        self.assertTrue(ok['pass'])
        self.assertEqual(ok['C3']['bounds'], [0.04 - 0.105, 0.25 + 0.105])
        self.assertFalse(sanity_criteria([0.10, 0.12], 0.19, [0.04, 0.25], PROTOCOL)['C1']['pass'])
        self.assertFalse(sanity_criteria([-0.06, 0.3], 0.0, [0.04, 0.25], PROTOCOL)['C2']['pass'])
        self.assertFalse(sanity_criteria([0.4], 0.19, [0.04, 0.25], PROTOCOL)['C3']['pass'])
