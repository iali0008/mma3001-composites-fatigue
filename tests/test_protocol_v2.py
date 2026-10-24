"""Unit tests for protocol v2 eligibility, aggregation, label isolation and selection."""

import copy
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from protocol_v2 import (
    FAMILIES,
    INPUT_SETS,
    build_checkpoints,
    eligibility_reasons,
    load_protocol,
    pairs,
    select_final,
    setting_vector,
    summarise_file,
)

PROTOCOL = load_protocol()
L1S11 = PROTOCOL['specimens']['L1S11']


def sine(amplitude, n=2000, periods=25):
    """Sampled sine of the given amplitude whose samples include the exact peaks."""
    t = np.arange(n) / n
    return amplitude * np.sin(2 * np.pi * periods * t)


def coupon(
    cycles=10.0,
    load=4.0,
    condition='Loaded',
    label=0.1,
    scale=1.0,
    gain=33,
    amplitude=65,
    drop=None,
    extra=None,
    bad=None,
):
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
        records.append(
            dict(
                actuator=a,
                sensor=s,
                frequency=150,
                gain=gain,
                amplitude=amplitude,
                sampling_rate=1200000,
                signal_actuator=sine(1.0),
                signal_sensor=x,
            )
        )
    if extra:
        records.append(copy.deepcopy(records[0]))
    records.append(
        dict(
            actuator=1,
            sensor=7,
            frequency=300,
            gain=1,
            amplitude=1,
            sampling_rate=1,
            signal_actuator=np.zeros(5),
            signal_sensor=np.zeros(5),
        )
    )
    return dict(
        cycles=cycles,
        load=load,
        condition=condition,
        path_data=records,
        straingage_data=dict(stiffness_degradation=[] if label is None else label),
    )


def summary(name='f.mat', read_labels=True, **kwargs):
    """Summarise one synthetic L1S11 coupon; keyword arguments go to `coupon`."""
    return summarise_file(coupon(**kwargs), 'L1S11', name, PROTOCOL, read_labels)


def screened(summaries):
    """Apply the v2 eligibility rules in place, using the default coupon as the modal setting."""
    modal = setting_vector(summarise_file(coupon(), 'L1S11', 'm.mat', PROTOCOL, True), PROTOCOL)
    for s in summaries:
        reasons = eligibility_reasons(s, L1S11, modal, PROTOCOL)
        s['eligible'], s['exclusion_reasons'] = not reasons, '; '.join(reasons)
    return summaries


class EligibilityTests(unittest.TestCase):
    """v2 eligibility: each rule excludes on its own, and labels play no part."""

    def test_valid_file_is_eligible(self):
        """The default synthetic file passes every v2 rule."""
        self.assertEqual(screened([summary()])[0]['exclusion_reasons'], '')

    def test_each_rule_excludes(self):
        """Each v2 rule alone excludes a file and names its reason; so does a duplicated pair."""
        cases = {
            'not a positive-cycle checkpoint': dict(cycles=0.0),
            'condition is not loaded': dict(condition='Traction Free'),
            'load outside 3.95-4.05 kips': dict(load=4.58),
            '36-pair grid incomplete or duplicated': dict(drop=(3, 10)),
            'baseline path missing or ambiguous': dict(drop=(1, 7)),
            'baseline gain/amplitude mismatch': dict(gain=35),
            'setting vector differs from specimen modal vector': dict(amplitude=50),
            'invalid signal (length, nonfinite or constant)': dict(bad=(2, 9)),
        }
        for reason, kwargs in cases.items():
            with self.subTest(reason=reason):
                s = screened([summary(**kwargs)])[0]
                self.assertFalse(s['eligible'])
                self.assertIn(reason, s['exclusion_reasons'])
        self.assertIn('duplicated', screened([summary(extra=True)])[0]['exclusion_reasons'])

    def test_sampling_rate_and_signal_length_exclude(self):
        """A wrong stored sampling rate, or 1,999 or 2,001 samples on a pair, excludes the file."""
        cases = (
            ('sampling_rate', 12_000_000, 'stored sampling rate mismatch'),
            ('signal_sensor', sine(1.0, n=1999), 'invalid signal'),
            ('signal_actuator', sine(1.0, n=2001), 'invalid signal'),
        )
        for field, value, reason in cases:
            c = coupon()
            c['path_data'][5][field] = value
            s = screened([summarise_file(c, 'L1S11', 'f.mat', PROTOCOL, True)])[0]
            with self.subTest(field=field):
                self.assertFalse(s['eligible'])
                self.assertIn(reason, s['exclusion_reasons'])

    def test_l2s11_load_window_bounds_are_inclusive(self):
        """L2S11's 4.53-4.63 kip window is inclusive; nearby values and Layup 1's load fail."""
        rules = PROTOCOL['specimens']['L2S11']
        self.assertEqual(rules['load_window_kips'], [4.53, 4.63])
        make = dict(gain=35, amplitude=50)
        modal = setting_vector(
            summarise_file(coupon(**make), 'L2S11', 'm.mat', PROTOCOL, False), PROTOCOL
        )
        for load, inside in (
            (4.53, True),
            (4.63, True),
            (4.529, False),
            (4.631, False),
            (4.0, False),
        ):
            s = summarise_file(coupon(load=load, **make), 'L2S11', 'f.mat', PROTOCOL, False)
            reasons = eligibility_reasons(s, rules, modal, PROTOCOL)
            with self.subTest(load=load):
                self.assertEqual(reasons == [], inside, reasons)

    def test_nonfinite_or_constant_signal_on_either_channel_excludes(self):
        """Nonfinite or constant signals on either channel exclude the file (stricter than v1)."""
        # Stricter than historical v1, which only flags these (test_extraction.py).
        for field in ('signal_actuator', 'signal_sensor'):
            for name, values in (('nonfinite', np.full(2000, np.nan)), ('constant', np.ones(2000))):
                c = coupon()
                c['path_data'][5][field] = values
                s = screened([summarise_file(c, 'L1S11', 'f.mat', PROTOCOL, True)])[0]
                with self.subTest(field=field, name=name):
                    self.assertFalse(s['eligible'])
                    self.assertIn('invalid signal', s['exclusion_reasons'])

    def test_labels_are_not_read_when_disabled(self):
        """Leakage: with ``read_labels=False`` the label field is deleted before any reading."""
        c = coupon(label=0.3)
        s = summarise_file(c, 'L1S11', 'x.mat', PROTOCOL, read_labels=False)
        self.assertIsNone(s['published_index'])
        self.assertNotIn('straingage_data', c)  # deleted before anything else is read

    def test_label_does_not_change_eligibility(self):
        """Leakage: a file's label cannot change its eligibility or exclusion reasons."""
        a, b = screened([summary(label=None), summary(label=0.2)])
        self.assertEqual(
            (a['eligible'], a['exclusion_reasons']), (b['eligible'], b['exclusion_reasons'])
        )


class AggregationTests(unittest.TestCase):
    """Checkpoint aggregation: reference choice, per-pair normalisation and label isolation."""

    def build(self, first_label=None):
        """Build checkpoints from five synthetic files; the earliest has label ``first_label``."""
        files = [
            summary('a.mat', cycles=1.0, label=first_label, scale=1.0),
            summary('b.mat', cycles=10.0, label=0.05, scale=0.8),
            summary('c.mat', cycles=10.0, label=0.05, scale=0.9),
            summary('d.mat', cycles=100.0, label=None, scale=0.5),
            summary('e.mat', cycles=0.5, label=0.0, condition='Clamped'),
        ]
        return build_checkpoints(screened(files), PROTOCOL)

    def test_reference_is_earliest_eligible_even_if_unlabelled(self):
        """Leakage: the earliest eligible checkpoint is the reference; missing labels stay None."""
        cps, _, ref = self.build(first_label=None)
        self.assertEqual((ref['cycles'], ref['filenames']), (1, 'a.mat'))
        self.assertEqual([c['cycles'] for c in cps], [1, 10, 100])
        self.assertTrue(cps[0]['is_reference'])
        self.assertIsNone(cps[0]['published_index'])
        self.assertIsNone(cps[2]['published_index'])  # missing label stays missing

    def test_labels_cannot_change_features_or_reference(self):
        """Leakage: a label on the earliest checkpoint changes no feature and not the reference."""
        a, _, ra = self.build(first_label=None)
        b, _, rb = self.build(first_label=0.7)
        self.assertEqual(ra, rb)
        for x, y in zip(a, b):
            for f in ('relative_rms', 'relative_ptp', 'mp_relative_rms', 'mp_relative_ptp'):
                self.assertEqual(x[f], y[f])

    def test_per_pair_normalisation_then_median_over_pairs(self):
        """Known answer: repeats at scales 0.8 and 0.9 give 0.85 on both inputs, from 36 ratios."""
        cps, ratios, _ = self.build()
        ten = cps[1]
        self.assertAlmostEqual(ten['relative_ptp'], 0.85, places=12)  # median(0.8, 0.9)
        self.assertAlmostEqual(ten['mp_relative_ptp'], 0.85, places=12)
        self.assertAlmostEqual(ten['mp_relative_rms'], 0.85, places=12)
        self.assertEqual(len([r for r in ratios if r['cycles'] == 10]), 36)

    def test_aggregation_order_with_heterogeneous_pairs_and_repeats(self):
        """Known answer: the declared aggregation order is used, not a plausible alternative."""
        # Each pair has its own reference level and its own change, and the two
        # repeats differ, so the three plausible orders give different answers.
        rng = np.random.default_rng(7)
        grid = pairs(PROTOCOL)
        ref = {p: rng.uniform(1, 100) for p in grid}
        change = {p: rng.uniform(0.3, 1.0) for p in grid}
        repeats = [{p: ref[p] * change[p] * rng.uniform(0.8, 1.2) for p in grid} for _ in range(2)]
        files = screened(
            [
                summary('r.mat', cycles=1.0),
                summary('x.mat', cycles=10.0),
                summary('y.mat', cycles=10.0),
            ]
        )
        for s, values in zip(files, [ref] + repeats):
            s['rms'] = dict(values)
            s['ptp'] = {p: 2 * v for p, v in values.items()}
        got = build_checkpoints(files, PROTOCOL)[0][1]

        per_pair = [np.median([r[p] for r in repeats]) / ref[p] for p in grid]
        declared = np.median(per_pair)  # repeat median, per-pair ratio, median over pairs
        ratio_of_medians = np.median(
            [np.median([r[p] for r in repeats]) for p in grid]
        ) / np.median(list(ref.values()))
        median_of_recordings = np.median(
            [np.median([r[p] / ref[p] for p in grid]) for r in repeats]
        )
        self.assertGreater(abs(declared - ratio_of_medians), 1e-3)
        self.assertGreater(abs(declared - median_of_recordings), 1e-4)
        for field in ('mp_relative_rms', 'mp_relative_ptp'):
            self.assertAlmostEqual(got[field], declared, places=12)

    def test_multi_path_feature_ignores_pair_labelling(self):
        """Permuting pair IDs leaves the multi-path median unchanged."""
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
        """Guard: repeats with different labels at one checkpoint raise an error."""
        files = screened(
            [
                summary('a.mat', cycles=1.0),
                summary('b.mat', cycles=10.0, label=0.1),
                summary('c.mat', cycles=10.0, label=0.2),
            ]
        )
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            build_checkpoints(files, PROTOCOL)


class SelectionTests(unittest.TestCase):
    """The predeclared final-model selection rule and its tie handling."""

    def rows(self, values):
        """Candidate table: every family and input set at MAE 0.2, except the given overrides."""
        return [
            dict(model=m, input_set=i, worst_direction_MAE=values.get((m, i), 0.2))
            for m in FAMILIES
            for i in INPUT_SETS
        ]

    def test_lowest_worst_direction_mae_wins(self):
        """The candidate with the lowest worst-direction MAE is selected."""
        result = select_final(self.rows({('SVR', 'multi_path_36'): 0.05}), PROTOCOL)
        self.assertEqual(result['selected']['model'], 'SVR')
        self.assertEqual(result['selected']['input_set'], 'multi_path_36')

    def test_ties_prefer_simpler_model_then_single_path(self):
        """Within the 0.0005 tolerance the simpler model wins, then the single-path input."""
        result = select_final(
            self.rows(
                {
                    ('MLPRegressor', 'multi_path_36'): 0.0500,
                    ('LinearRegression', 'multi_path_36'): 0.0504,
                    ('LinearRegression', 'single_path_1_7'): 0.0506,
                }
            ),
            PROTOCOL,
        )
        self.assertEqual(
            (result['selected']['model'], result['selected']['input_set']),
            ('LinearRegression', 'multi_path_36'),
        )
        result = select_final(
            self.rows(
                {
                    ('DecisionTreeRegressor', 'multi_path_36'): 0.05,
                    ('DecisionTreeRegressor', 'single_path_1_7'): 0.05,
                }
            ),
            PROTOCOL,
        )
        self.assertEqual(result['selected']['input_set'], 'single_path_1_7')

    def test_outside_tolerance_is_not_a_tie(self):
        """A gap of 0.0006 exceeds the tolerance, so the lower-MAE MLP is kept."""
        result = select_final(
            self.rows(
                {
                    ('MLPRegressor', 'single_path_1_7'): 0.0500,
                    ('LinearRegression', 'single_path_1_7'): 0.0506,
                }
            ),
            PROTOCOL,
        )
        self.assertEqual(result['selected']['model'], 'MLPRegressor')

    def test_candidate_set_must_be_complete(self):
        """Guard: a missing candidate raises instead of selecting from a partial table."""
        with self.assertRaisesRegex(ValueError, 'candidate set'):
            select_final(self.rows({})[:-1], PROTOCOL)

    def test_protocol_models_identical_to_v1(self):
        """The v2 config keeps the v1 MLP seeds and the declared tie tolerance."""
        self.assertEqual(PROTOCOL['models']['mlp_seeds'], [7, 23, 42, 71, 101])
        self.assertEqual(PROTOCOL['selection_rule']['tie_tolerance_mae'], 0.0005)


if __name__ == '__main__':
    unittest.main()


class TestStageHelpers(unittest.TestCase):
    """Label attachment after blind prediction, and sanity criteria C1-C3."""

    def test_attach_labels_uses_eligible_files_and_keeps_missing(self):
        """Labels attach through each checkpoint's own files; missing stays None, inputs unchanged.

        Notes
        -----
        ``z.mat`` stands for the cycle-1 label (-0.012): it belongs to no checkpoint, so it is
        never attached.
        """
        from protocol_v2 import attach_labels

        cps = [
            dict(cycles=3, filenames='a.mat; b.mat', published_index=None),
            dict(cycles=10, filenames='c.mat', published_index=None),
        ]
        labels = {
            'a.mat': (3.0, None),
            'b.mat': (3.0, None),
            'c.mat': (10.0, 0.04),
            'z.mat': (1.0, -0.012),
        }
        out = attach_labels(cps, labels)
        self.assertIsNone(out[0]['published_index'])
        self.assertEqual(out[1]['published_index'], 0.04)
        self.assertIsNone(cps[1]['published_index'])  # inputs are not modified

    def test_attach_labels_rejects_conflicts_and_unknown_files(self):
        """Guard: conflicting labels in a checkpoint, or an unknown file, raise errors."""
        from protocol_v2 import attach_labels

        cp = [dict(cycles=10, filenames='a.mat; b.mat', published_index=None)]
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            attach_labels(cp, {'a.mat': (10.0, 0.1), 'b.mat': (10.0, 0.2)})
        with self.assertRaisesRegex(ValueError, 'Unknown file'):
            attach_labels(cp, {'a.mat': (10.0, 0.1)})

    def test_sanity_criteria(self):
        """Known answers for C1 (late mean >= 100k value), C2 ([-0.05, 1] range) and C3."""
        from protocol_v2 import sanity_criteria

        ok = sanity_criteria([0.20, 0.22], 0.19, [0.04, 0.25], PROTOCOL)
        self.assertTrue(ok['pass'])
        self.assertEqual(ok['C3']['bounds'], [0.04 - 0.105, 0.25 + 0.105])
        self.assertFalse(sanity_criteria([0.10, 0.12], 0.19, [0.04, 0.25], PROTOCOL)['C1']['pass'])
        self.assertFalse(sanity_criteria([-0.06, 0.3], 0.0, [0.04, 0.25], PROTOCOL)['C2']['pass'])
        self.assertFalse(sanity_criteria([0.4], 0.19, [0.04, 0.25], PROTOCOL)['C3']['pass'])
