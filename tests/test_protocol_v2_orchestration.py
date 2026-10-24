"""Mocked tests of the protocol v2 orchestration (findings R2, C8 / R8).

* the v1 reproduction gate in ``protocol_v2_validation.py`` must be one-to-one;
* the once-only guard of ``protocol_v2_test.py`` must stop before anything is read;
* L2S11 predictions must be written before any L2S11 label is read.

All raw-data access is mocked with synthetic checkpoints and every output goes to
a temporary folder. No real L2S11 file, and no recorded result, is touched.
"""

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import protocol_v2_test as pt  # noqa: E402
import protocol_v2_validation as v2v  # noqa: E402


def recorded_rows():
    """Return the recorded v1 predictions as the gate receives them (floats, int cycles)."""
    with v2v.V1_PREDICTIONS.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    for r in rows:
        r['cycles'] = int(r['cycles'])
        r['observed'] = float(r['observed'])
        r['predicted'] = float(r['predicted'])
    return rows


class ReproductionGateTests(unittest.TestCase):
    """The v1 reproduction gate must match the recorded predictions one-to-one."""

    def setUp(self):
        """Load the recorded v1 predictions."""
        self.rows = recorded_rows()

    def test_exact_record_passes(self):
        """Known answer: the record itself passes with zero difference and the summary keys."""
        gate = v2v.reproduction_gate(self.rows)
        self.assertEqual(gate['compared_predictions'], len(self.rows))
        self.assertEqual(gate['max_abs_difference'], 0.0)
        self.assertEqual(set(gate), {'compared_predictions', 'max_abs_difference', 'rtol', 'atol'})

    def test_recorded_v2_run_passes_the_stricter_gate(self):
        """The saved v2 single-path rows pass the gate and give the recorded gate summary."""
        # The saved v2 single-path rows (controls are relabelled single_path_1_7 there)
        # must satisfy the one-to-one gate and give the recorded gate summary.
        with (v2v.OUT / 'predictions.csv').open(newline='', encoding='utf-8') as stream:
            rows = [r for r in csv.DictReader(stream) if r['input_set'] == 'single_path_1_7']
        for r in rows:
            r['observed'], r['predicted'] = float(r['observed']), float(r['predicted'])
        recorded = json.loads((v2v.OUT / 'reproduction_gate.json').read_text())
        self.assertEqual(v2v.reproduction_gate(rows), recorded)

    def test_duplicate_row_replacing_another_fails(self):
        """Guard: a duplicate row standing in for a missing one fails instead of being counted."""
        rows = self.rows[:-1] + [dict(self.rows[0])]
        with self.assertRaisesRegex(ValueError, 'Duplicate prediction row'):
            v2v.reproduction_gate(rows)

    def test_missing_row_fails(self):
        """Guard: a missing recorded prediction fails the gate."""
        with self.assertRaisesRegex(ValueError, 'not reproduced'):
            v2v.reproduction_gate(self.rows[:-1])

    def test_extra_row_fails(self):
        """Guard: a prediction with no recorded counterpart fails the gate."""
        extra = dict(self.rows[0], cycles=123456789)
        with self.assertRaisesRegex(ValueError, 'No recorded v1 prediction'):
            v2v.reproduction_gate(self.rows + [extra])

    def test_changed_target_fails(self):
        """Guard: a changed observed value fails the gate."""
        rows = [dict(r) for r in self.rows]
        rows[5]['observed'] = 999.0
        with self.assertRaisesRegex(ValueError, 'observed'):
            v2v.reproduction_gate(rows)

    def test_changed_specimen_fails(self):
        """Guard: a changed specimen field fails the gate."""
        for field in ('evaluation_specimen', 'specimen'):
            rows = [dict(r) for r in self.rows]
            rows[3][field] = 'L2S11'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                v2v.reproduction_gate(rows)

    def test_changed_prediction_fails(self):
        """Guard: a prediction changed by 1e-6 fails the gate."""
        rows = [dict(r) for r in self.rows]
        rows[7]['predicted'] += 1e-6
        with self.assertRaisesRegex(ValueError, 'predicted'):
            v2v.reproduction_gate(rows)


def checkpoint(cycles, index, rng, reference=False):
    """One synthetic checkpoint whose features fall with the index."""
    return dict(
        cycles=cycles,
        log10_cycles=float(np.log10(cycles)),
        is_reference=reference,
        published_index=None if index is None else float(index),
        relative_rms=1.0 if reference else float(1 - 0.8 * (index or 0) + rng.normal(0, 0.01)),
        relative_ptp=1.0 if reference else float(1 - 0.4 * (index or 0) + rng.normal(0, 0.01)),
    )


def synthetic_checkpoints():
    """Synthetic L1S11 (13 labelled), L1S12 (12 labelled) and blind L2S11 checkpoints."""
    rng = np.random.default_rng(0)
    l1s11 = [checkpoint(1, 0.0, rng, reference=True)]
    l1s11 += [checkpoint(c, 0.01 * k, rng) for k, c in enumerate(range(1000, 14000, 1000))]
    l1s11 += [checkpoint(100000, 0.12, rng)]
    l1s11 += [checkpoint(c, None, rng) for c in (125000, 150000, 175000, 177000, 227000)]
    l1s11 = [c for c in l1s11 if not (c['cycles'] == 13000)]  # keep 13 labelled
    l1s12 = [checkpoint(1, 0.0, rng, reference=True)]
    l1s12 += [checkpoint(c, 0.02 * k, rng) for k, c in enumerate(range(2000, 26000, 2000))]
    l2s11 = [checkpoint(3, None, rng, reference=True)]
    l2s11 += [checkpoint(c, None, rng) for c in (10, 1000, 10000, 20000, 30000)]
    return dict(L1S11=l1s11, L1S12=l1s12, L2S11=l2s11)


class OnceOnlyGuardTests(unittest.TestCase):
    """The L2S11 scorer stops before reading anything if it ran before or the tree is dirty."""

    def setUp(self):
        """Point both output folders at a temporary directory and mock data and label reading."""
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.test_dir, self.sanity_dir = base / 'test_L2S11', base / 'sanity_L1S11'
        self.patches = [
            mock.patch.object(pt, 'TEST', self.test_dir),
            mock.patch.object(pt, 'SANITY', self.sanity_dir),
        ]
        for p in self.patches:
            p.start()
        self.extract = mock.patch.object(pt, 'extract_specimen').start()
        self.labels = mock.patch.object(pt, 'read_published_labels').start()

    def tearDown(self):
        """Stop all patches and remove the temporary directory."""
        mock.patch.stopall()
        self.temp.cleanup()

    def test_refuses_when_either_output_folder_exists(self):
        """Guard: an existing output folder stops the run before git, extraction or labels."""
        for folder in (self.test_dir, self.sanity_dir):
            folder.mkdir()
            git = mock.patch.object(pt, 'git_state').start()
            with self.subTest(folder=folder.name):
                with self.assertRaisesRegex(ValueError, 'never rerun'):
                    pt.main(['--data-root', self.temp.name])
                git.assert_not_called()
            folder.rmdir()
        self.extract.assert_not_called()
        self.labels.assert_not_called()

    def test_refuses_dirty_tree_before_creating_or_reading_anything(self):
        """Guard: uncommitted changes stop the run before any folder is created or data read."""
        mock.patch.object(pt, 'git_state', return_value=dict(commit='x', clean=False)).start()
        with self.assertRaisesRegex(ValueError, 'Commit all changes'):
            pt.main(['--data-root', self.temp.name])
        self.assertFalse(self.test_dir.exists() or self.sanity_dir.exists())
        self.extract.assert_not_called()
        self.labels.assert_not_called()


class LabelOrderTests(unittest.TestCase):
    """Run the whole scorer on synthetic data and check when labels are read."""

    def test_predictions_are_written_before_labels_are_read(self):
        """Leakage: L2S11 is extracted label-blind; labels are read once, after blind predictions.

        Notes
        -----
        Extraction, checkpoint building and label reading are replaced by the nested
        helpers below, which record the call order. The cycle-1 label is reported, not scored.
        """
        cps = synthetic_checkpoints()
        events = []
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            test_dir, sanity_dir, selection = base / 'test', base / 'sanity', base / 'sel.json'
            selection.write_text(
                json.dumps(
                    dict(selected=dict(model='LinearRegression', input_set='single_path_1_7'))
                )
            )
            blind = test_dir / 'predictions_before_labels.csv'

            def extract(data_root, specimen, protocol, read_labels, workers):
                """Record the call and return one placeholder summary."""
                events.append(('extract', specimen, read_labels))
                return [dict(specimen=specimen)], {}

            def build(summaries, protocol):
                """Return the synthetic checkpoints of the summary's specimen."""
                rows = [dict(c) for c in cps[summaries[0]['specimen']]]
                return rows, [], next(r for r in rows if r['is_reference'])

            def read_labels(data_root, specimen, protocol, workers):
                """Record the call, check the blind files exist, and return synthetic labels."""
                # The blind predictions and their hash must already be on disk.
                events.append(('labels', specimen, blind.is_file()))
                self.assertTrue((test_dir / 'predictions_before_labels.sha256.json').is_file())
                values = {1: -0.012, 10: 0.01, 1000: 0.009, 10000: 0.011, 20000: 0.03}
                return {f'L2S11_{c}.mat': (c, v) for c, v in values.items()}

            def attach(rows, labels):
                """Attach labels to checkpoints by cycle."""
                by_cycle = {c: lab for c, lab in labels.values()}
                return [dict(r, published_index=by_cycle.get(r['cycles'])) for r in rows]

            with (
                mock.patch.object(pt, 'TEST', test_dir),
                mock.patch.object(pt, 'SANITY', sanity_dir),
                mock.patch.object(pt, 'SELECTION', selection),
                mock.patch.object(pt, 'git_state', return_value=dict(commit='x', clean=True)),
                mock.patch.object(pt, 'extract_specimen', side_effect=extract),
                mock.patch.object(pt, 'build_checkpoints', side_effect=build),
                mock.patch.object(pt, 'read_published_labels', side_effect=read_labels),
                mock.patch.object(pt, 'attach_labels', side_effect=attach),
                mock.patch.object(pt, 'plot_test'),
                mock.patch.object(pt, 'plot_coverage'),
                mock.patch('builtins.print'),
            ):
                pt.main(['--data-root', temp])
            result = json.loads((test_dir / 'result.json').read_text())

        self.assertEqual(
            events,
            [
                ('extract', 'L1S11', True),
                ('extract', 'L1S12', True),
                ('extract', 'L2S11', False),  # L2S11 features are extracted label-blind
                ('labels', 'L2S11', True),  # labels read once, after the blind file exists
            ],
        )
        self.assertEqual(result['scored_cycles'], [10, 1000, 10000, 20000])
        self.assertEqual(result['unlabelled_non_reference_cycles'], [30000])
        self.assertEqual(result['cycle_1_label_reported_not_scored'], [-0.012])


if __name__ == '__main__':
    unittest.main()
