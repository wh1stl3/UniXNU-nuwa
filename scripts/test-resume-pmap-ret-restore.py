#!/usr/bin/env python3
"""Host-only continuation tests; no real subprocess or device commands."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resume', HERE / 'resume-pmap-ret-restore.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)
ex = resume.load_executor()
SOURCE = resume.REPO / 'out' / ('pmap-ret-run-' + resume.RUN_ID)


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = ex.Run(self.tmp.name, resume.RUN_ID, 'adb', 'fastboot', profile=resume.PROFILE)
        self.run.directory.mkdir(parents=True)
        self.run.runner = Mock(side_effect=AssertionError('real process forbidden'))
        self.put('run-identity.json', self.run.identity())
        self.put('restore.claim', {'phase': 'restore', 'authorized': True})
        self.put('boot-attempt.claim', {'consumed_before_boot': True})
        self.put('prepare-writer-closed.json', {'dd_returncode': 0})
        self.put('staging-created.json', {'path': self.run.remote, 'owner': 2000})
        previous = None
        for state in ex.STATES[:6]:
            self.put('state-' + state + '.json', {'state': state, 'previous': previous})
            previous = state
        for i in range(68):
            path = self.run.directory / ('event-%04d.json' % i)
            path.write_bytes((SOURCE / path.name).read_bytes() if i >= 63 else b'{}\n')
        self.run.backup.write_bytes(b'synthetic')
        self.run.check_file = Mock()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, value):
        (self.run.directory / name).write_text(json.dumps(value), encoding='utf-8')

    def stop(self):
        with self.assertRaises((ex.Stop, ValueError)):
            resume.resume(self.run, ex, True)
        self.run.runner.assert_not_called()

    def test_default_stop(self):
        self.assertTrue(resume.resume(self.run, ex)['dry_run'])
        self.run.runner.assert_not_called()
        self.assertFalse((self.run.directory / 'restore-attempt-02.claim').exists())

    def test_wrong_run_and_identity(self):
        self.run.run_id = 'wrong'
        self.stop()
        self.run.run_id = resume.RUN_ID
        self.put('run-identity.json', {})
        self.stop()

    def test_bad_backup(self):
        self.run.check_file = lambda path, size, expected: ex.Run.check_file(self.run, path, size, expected)
        self.stop()

    def test_writer_states_attempt_and_lock(self):
        for name in ('restore-writer.claim', 'state-set_A_accepted.json',
                     'state-android_A_confirmed.json', 'restore-attempt-02.claim', 'active.lock'):
            path = self.run.directory / name
            path.write_text('{}')
            self.stop()
            path.unlink()

    def test_failure_evidence_changed(self):
        (self.run.directory / 'event-0067.json').write_text('{}')
        self.stop()

    def test_failure_consumes_attempt_and_cannot_replay(self):
        self.run.restore = Mock(side_effect=ex.Stop('synthetic failure'))
        with self.assertRaises(ex.Stop):
            resume.resume(self.run, ex, True)
        self.assertTrue((self.run.directory / 'restore-attempt-02.claim').exists())
        self.stop()
        self.run.restore.assert_called_once()

    def test_original_current_slot_rejection(self):
        def runner(argv, **kwargs):
            args = argv[1:]
            if args == ['devices', '-l']:
                return subprocess.CompletedProcess(argv, 0, 'List of devices attached\n', '')
            if args == ['devices']:
                return subprocess.CompletedProcess(argv, 0, 'OTHER\tfastboot\nSYNTHETIC\tfastboot\n', '')
            if args[2:] == ['getvar', 'product']:
                product = 'nuwa' if args[1] == 'SYNTHETIC' else 'enuma'
                return subprocess.CompletedProcess(argv, 0, '', 'product: ' + product + '\n')
            self.assertEqual(args, ['-s', 'SYNTHETIC', 'getvar', 'current-slot'])
            return subprocess.CompletedProcess(argv, 0, '',
                "getvar:current-slot FAILED (remote: 'unknown command')\nFinished. Total time: 0.000s\n")
        self.run.runner = Mock(side_effect=runner)
        with self.assertRaises(ex.Stop):
            resume.resume(self.run, ex, True)
        self.assertEqual(self.run.runner.call_count, 5)
        self.assertTrue((self.run.directory / 'event-0072.json').exists())
        self.assertFalse((self.run.directory / 'event-0073.json').exists())
        self.assertEqual(self.run.state(), 'boot_attempt_consumed')
        self.assertTrue((self.run.directory / 'restore-attempt-02.claim').exists())

    def test_original_restore_success_path(self):
        self.run.identify = Mock(return_value='SYNTHETIC')
        self.run.android_a = Mock()
        self.run.geometry = Mock()
        self.run.clear_writer = Mock()
        self.run.staging = Mock(return_value=[])
        self.run.confirm = Mock()
        self.run.call = Mock()
        self.run.adb_call = Mock()
        self.run.device_hash = Mock(return_value=self.run.stock_sha256)
        self.run.readback = Mock()
        self.run.cleanup = Mock()
        result = resume.resume(self.run, ex, True)
        self.assertEqual(result['state'], 'B_restored_verified')
        self.assertTrue((self.run.directory / 'restore-writer.claim').exists())
        self.assertTrue((self.run.directory / 'restore-writer-closed.json').exists())
        self.run.geometry.assert_called_once()
        self.run.clear_writer.assert_called_once()
        self.run.readback.assert_called_once()
        self.assertTrue(any('dd if=' in str(c) and ' of=' in str(c)
                            for c in self.run.adb_call.call_args_list))
        self.run.cleanup.assert_called_once()
        self.assertTrue((self.run.directory / 'restore.claim').exists())

    def test_original_fastboot_restore_success_path(self):
        self.run.identify = Mock(side_effect=[None, 'SYNTHETIC'])
        self.run.wait_transport = Mock(return_value='SYNTHETIC')
        self.run.android_a = Mock()
        self.run.geometry = Mock()
        self.run.clear_writer = Mock()
        self.run.staging = Mock(return_value=[])
        self.run.confirm = Mock()
        self.run.adb_call = Mock()
        self.run.device_hash = Mock(return_value=self.run.stock_sha256)
        self.run.readback = Mock()
        self.run.cleanup = Mock()

        def call(tool, args, **kwargs):
            if args[2:] == ['getvar', 'current-slot']:
                return {'stdout': 'current-slot: a\n', 'stderr': '', 'returncode': 0}, True
            if args[2:] == ['set_active', 'a']:
                return {'stdout': '', 'stderr': 'OKAY\nFinished. Total time: 0.01s\n',
                        'returncode': 0}, True
            return {}, True

        self.run.call = Mock(side_effect=call)
        result = resume.resume(self.run, ex, True)
        self.assertEqual(result['state'], 'B_restored_verified')
        self.assertTrue((self.run.directory / 'state-set_A_accepted.json').exists())
        self.assertEqual(sum(c.args[1][2:] == ['getvar', 'current-slot']
                             for c in self.run.call.call_args_list), 2)
        self.run.readback.assert_called_once()


if __name__ == '__main__':
    with patch('subprocess.run', side_effect=AssertionError('real subprocess forbidden')):
        unittest.main()
