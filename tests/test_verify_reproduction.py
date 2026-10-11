"""Safety tests for the scratch-folder guard in verify_reproduction.py (finding R1).

Every test builds a throw-away repository tree in a temporary folder; no real
data, results or repository folders are touched.
"""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_reproduction as vr  # noqa: E402


class WorkFolderGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'repo'
        self.data = self.root / 'data' / '2.+Composites' / '2. Composites'
        self.data.mkdir(parents=True)
        for name in vr.RECORDED_RESULTS + ('rebuilt',):
            (self.root / 'results' / name).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def check(self, work, data=None):
        return vr.check_work_folder(work, data or self.data, root=self.root)

    def test_accepts_folder_inside_rebuilt(self):
        work = self.root / 'results' / 'rebuilt' / 'verification'
        self.assertEqual(self.check(work), work.resolve())

    def test_refuses_rebuilt_itself_and_anything_outside_it(self):
        for work in (
            self.root / 'results' / 'rebuilt',
            self.root / 'results',
            self.root,
            self.root.parent,
            Path(self.temp.name) / 'elsewhere',
        ):
            with self.subTest(work=work), self.assertRaisesRegex(ValueError, 'strictly inside'):
                self.check(work)

    def test_refuses_data_and_every_recorded_results_folder(self):
        targets = [self.root / 'data', self.data]
        targets += [self.root / 'results' / name for name in vr.RECORDED_RESULTS]
        targets.append(self.root / 'results' / 'protocol_v2' / 'test_L2S11')
        for work in targets:
            with self.subTest(work=work), self.assertRaises(ValueError):
                self.check(work)

    def test_refuses_data_root_inside_rebuilt(self):
        data = self.root / 'results' / 'rebuilt' / 'raw'
        data.mkdir()
        for work in (data, data / 'sub', self.root / 'results' / 'rebuilt' / 'raw'):
            with self.subTest(work=work), self.assertRaisesRegex(ValueError, 'protected'):
                self.check(work, data=data)

    def test_refuses_existing_file(self):
        work = self.root / 'results' / 'rebuilt' / 'a_file'
        work.write_text('x')
        with self.assertRaisesRegex(ValueError, 'not a folder'):
            self.check(work)

    def test_main_refuses_before_deleting_anything(self):
        victim = Path(self.temp.name) / 'precious'
        victim.mkdir()
        (victim / 'keep.txt').write_text('must survive')
        with self.assertRaisesRegex(ValueError, 'strictly inside'):
            vr.main(['--data-root', str(self.data), '--work', str(victim)])
        self.assertEqual((victim / 'keep.txt').read_text(), 'must survive')

    def test_recorded_folders_cover_every_tracked_results_folder(self):
        tracked = {p.name for p in (ROOT / 'results').iterdir() if p.is_dir()} - {'rebuilt'}
        self.assertLessEqual(tracked, set(vr.RECORDED_RESULTS))


if __name__ == '__main__':
    unittest.main()
