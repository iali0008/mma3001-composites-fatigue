"""Tests for the protocol v2 validation replay (findings C1 / R5).

The recorded validation is only read, and copied into temporary folders; no raw
data is opened and no recorded file is written.
"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import protocol_v2_validation as v2v  # noqa: E402


class CompareReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.replay = Path(self.temp.name) / 'replay'
        shutil.copytree(v2v.OUT, self.replay / 'validation')
        shutil.copy(v2v.SELECTION, self.replay / 'selection.json')

    def tearDown(self):
        self.temp.cleanup()

    def edit_selection(self, **changes):
        path = self.replay / 'selection.json'
        selection = json.loads(path.read_text())
        selection.update(changes)
        path.write_text(json.dumps(selection))

    def test_copy_of_record_matches_when_only_run_fields_differ(self):
        self.edit_selection(decided_utc='2030-01-01T00:00:00+00:00', validation_git_commit='0' * 40)
        result = v2v.compare_replay(self.replay)
        self.assertNotIn('DIFFERENT', result['counts'])
        self.assertIn('validation/predictions.csv', result['files'])
        self.assertNotIn('validation/receipt.json', result['files'])

    def test_changed_prediction_is_reported(self):
        path = self.replay / 'validation' / 'candidates.csv'
        text = path.read_text(encoding='utf-8')
        path.write_text(text.replace('0.0505', '0.0506', 1), encoding='utf-8')
        self.assertEqual(
            v2v.compare_replay(self.replay)['files']['validation/candidates.csv'], 'DIFFERENT'
        )

    def test_missing_output_is_reported(self):
        (self.replay / 'validation' / 'metrics.csv').unlink()
        self.assertEqual(
            v2v.compare_replay(self.replay)['files']['validation/metrics.csv'], 'DIFFERENT'
        )

    def test_changed_decision_is_reported(self):
        self.edit_selection(selected=dict(model='MLPRegressor', input_set='multi_path_36'))
        self.assertEqual(v2v.compare_replay(self.replay)['files']['selection.json'], 'DIFFERENT')


class ReplayGuardTests(unittest.TestCase):
    def test_replay_folder_outside_rebuilt_is_refused_before_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / 'precious'
            outside.mkdir()
            (outside / 'keep.txt').write_text('keep')
            with mock.patch.object(v2v, 'REPLAY', outside):
                with self.assertRaisesRegex(ValueError, 'strictly inside'):
                    v2v.main(['--data-root', temp, '--replay'])
            self.assertTrue((outside / 'keep.txt').is_file())

    def test_recorded_run_still_refuses_while_the_record_exists(self):
        with mock.patch.object(v2v, 'git_state', return_value=dict(commit='x', clean=True)):
            with self.assertRaisesRegex(ValueError, 'already exist'):
                v2v.main(['--data-root', str(ROOT)])


if __name__ == '__main__':
    unittest.main()
