"""Safety tests for the scratch-folder guard in verify_reproduction.py (finding R1).

Every test builds a throw-away repository tree in a temporary folder; no real
data, results or repository folders are touched.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_reproduction as vr  # noqa: E402


class WorkFolderGuardTests(unittest.TestCase):
    """``check_work_folder`` accepts only folders strictly inside ``results/rebuilt``."""

    def setUp(self):
        """Build a throw-away repository with a data folder and every recorded results folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'repo'
        self.data = self.root / 'data' / '2.+Composites' / '2. Composites'
        self.data.mkdir(parents=True)
        for name in vr.RECORDED_RESULTS + ('rebuilt',):
            (self.root / 'results' / name).mkdir(parents=True)

    def tearDown(self):
        """Remove the throw-away repository."""
        self.temp.cleanup()

    def check(self, work, data=None):
        """Run ``check_work_folder`` against the throw-away repository."""
        return vr.check_work_folder(work, data or self.data, root=self.root)

    def test_accepts_folder_inside_rebuilt(self):
        """A subfolder of ``results/rebuilt`` is accepted and returned resolved."""
        work = self.root / 'results' / 'rebuilt' / 'verification'
        self.assertEqual(self.check(work), work.resolve())

    def test_refuses_rebuilt_itself_and_anything_outside_it(self):
        """Guard: ``results/rebuilt`` itself and every folder outside it are refused."""
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
        """Guard: the raw data and every recorded results folder are refused."""
        targets = [self.root / 'data', self.data]
        targets += [self.root / 'results' / name for name in vr.RECORDED_RESULTS]
        targets.append(self.root / 'results' / 'protocol_v2' / 'test_L2S11')
        for work in targets:
            with self.subTest(work=work), self.assertRaises(ValueError):
                self.check(work)

    def test_refuses_data_root_inside_rebuilt(self):
        """Guard: a data root placed inside ``results/rebuilt`` is protected from deletion."""
        data = self.root / 'results' / 'rebuilt' / 'raw'
        data.mkdir()
        for work in (data, data / 'sub', self.root / 'results' / 'rebuilt' / 'raw'):
            with self.subTest(work=work), self.assertRaisesRegex(ValueError, 'protected'):
                self.check(work, data=data)

    def test_refuses_existing_file(self):
        """Guard: an existing file at the work path is refused."""
        work = self.root / 'results' / 'rebuilt' / 'a_file'
        work.write_text('x')
        with self.assertRaisesRegex(ValueError, 'not a folder'):
            self.check(work)

    def test_main_refuses_before_deleting_anything(self):
        """Guard: ``main`` refuses an outside folder before deleting any of its contents."""
        victim = Path(self.temp.name) / 'precious'
        victim.mkdir()
        (victim / 'keep.txt').write_text('must survive')
        with self.assertRaisesRegex(ValueError, 'strictly inside'):
            vr.main(['--data-root', str(self.data), '--work', str(victim)])
        self.assertEqual((victim / 'keep.txt').read_text(), 'must survive')

    def test_recorded_folders_cover_every_tracked_results_folder(self):
        """Every tracked results folder is listed as recorded, so none can be overwritten."""
        listed = subprocess.check_output(['git', 'ls-files', 'results'], cwd=ROOT, text=True)
        tracked = {line.split('/')[1] for line in listed.splitlines() if line.count('/') >= 2}
        self.assertTrue(tracked)
        self.assertLessEqual(tracked, set(vr.RECORDED_RESULTS))


class RecordedOutputGuardTests(unittest.TestCase):
    """Every script with an output option refuses recorded folders before reading data (R5)."""

    def test_require_not_recorded(self):
        """Refuses recorded folders, their files and ``results``; allows ``results/rebuilt``."""
        import common

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ok = common.require_not_recorded(root / 'results' / 'rebuilt' / 'x', root=root)
            self.assertEqual(ok.name, 'x')
            for name in common.RECORDED_RESULTS:
                for target in (root / 'results' / name, root / 'results' / name / 'f.json'):
                    with self.subTest(target=target), self.assertRaises(ValueError):
                        common.require_not_recorded(target, root=root)
            with self.assertRaises(ValueError):
                common.require_not_recorded(root / 'results', root=root)

    def test_scripts_refuse_recorded_outputs(self):
        """Guard: each script refuses a recorded output before reading its (missing) data root."""
        import audit_acquisition_v2
        import dataset_facts
        import post_hoc_logbook_l1s11
        import post_hoc_step4

        missing = str(ROOT / 'no-such-data-root')  # never read: the guard fires first
        results = ROOT / 'results'
        cases = [
            (
                audit_acquisition_v2.main,
                ['--data-root', missing, '--output', str(results / 'protocol_v2_audit')],
            ),
            (
                dataset_facts.main,
                ['--data-root', missing, '--output', str(results / 'dataset_facts')],
            ),
            (
                post_hoc_logbook_l1s11.main,
                [
                    '--data-root',
                    missing,
                    '--output',
                    str(results / 'protocol_v2' / 'post_hoc_step4'),
                ],
            ),
            (post_hoc_step4.main, ['--output', str(results / 'protocol_v2' / 'post_hoc_step4')]),
            (
                vr.main,
                [
                    '--data-root',
                    missing,
                    '--report',
                    str(results / 'reproduction_check' / 'report.json'),
                ],
            ),
        ]
        for main, argv in cases:
            with self.subTest(script=main.__module__):
                with self.assertRaisesRegex(ValueError, 'immutable'):
                    main(argv)


if __name__ == '__main__':
    unittest.main()
