"""Input-integrity and false-success regression checks, independent of a target SDK."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import wsl_kernel_adapter as adapter


MATCHING_IR = '''
@s1 = private constant [2 x i8] c"1\\00"
@s2 = private constant [2 x i8] c"2\\00"
@s12 = private constant [3 x i8] c"12\\00"
@s3 = private constant [2 x i8] c"3\\00"
@s11 = private constant [3 x i8] c"11\\00"
@nuwa_sig_ptr = global ptr @s1
@nuwa_sig_data = global ptr @s2
@nuwa_sig_mixed = global ptr @s12
@nuwa_sig_overlap = global ptr @s3
@nuwa_sig_annotated = global ptr @s1
@nuwa_sig_array = global ptr @s11
@nuwa_sum_ptr = global i32 2
@nuwa_sum_data = global i32 4
@nuwa_sum_mixed = global i32 6
@nuwa_sum_overlap = global i32 8
@nuwa_sum_annotated = global i32 2
@nuwa_sum_array = global i32 2
@nuwa_cmp_same = global i32 1
@nuwa_cmp_layout = global i32 1
@nuwa_cmp_different = global i32 0
@nuwa_cmp_wildcard = global i32 1
'''


class IrChecks(unittest.TestCase):
    def test_empty_success_output_is_rejected(self):
        self.assertEqual(adapter.inspect_ir('')['state'], 'sample-mismatch')

    def test_expected_sample_shape_is_accepted(self):
        self.assertEqual(adapter.inspect_ir(MATCHING_IR)['state'], 'sample-match')

    def test_wrong_union_summary_is_rejected(self):
        ir = MATCHING_IR.replace('@nuwa_sum_overlap = global i32 8', '@nuwa_sum_overlap = global i32 4')
        result = adapter.inspect_ir(ir)
        self.assertEqual(result['state'], 'sample-mismatch')
        self.assertTrue(any(row['case'] == 'overlap' and not row['matches'] for row in result['checks']))

    def test_missing_global_cannot_reuse_another_signature(self):
        ir = MATCHING_IR.replace('@nuwa_sig_array = global ptr @s11', '')
        self.assertEqual(adapter.inspect_ir(ir)['state'], 'sample-mismatch')


class InputChecks(unittest.TestCase):
    def setUp(self):
        parent = adapter.output_path(adapter.ROOT / 'out/wsl-adapter-tests')
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_output_cannot_write_readonly_source(self):
        with self.assertRaises(ValueError):
            adapter.output_path(adapter.ROOT.parent / 'PortingiOS/illegal.json')

    def test_empty_sysroot_manifest_does_not_qualify(self):
        manifest = self.directory / 'manifest.json'
        manifest.write_text('{"files":{}}')
        result = adapter.sysroot_probe(dict(path=str(self.directory), file_manifest=str(manifest)))
        self.assertEqual(result['state'], 'rejected')

    def test_sysroot_traversal_is_rejected(self):
        manifest = self.directory / 'manifest.json'
        manifest.write_text('{"files":{"../escape":"' + '0' * 64 + '"}}')
        result = adapter.sysroot_probe(dict(path=str(self.directory), file_manifest=str(manifest)))
        self.assertEqual(result['state'], 'rejected')

    def test_changed_tool_hash_is_rejected(self):
        tool = self.directory / 'tool'
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o755)
        result = adapter.identity(dict(path=str(tool), sha256='0' * 64), require_elf=False)
        self.assertEqual(result['state'], 'rejected')

    def test_shell_compiler_is_not_a_native_elf_compiler(self):
        tool = self.directory / 'compiler'
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o755)
        digest = hashlib.sha256(tool.read_bytes()).hexdigest()
        result = adapter.identity(dict(path=str(tool), sha256=digest))
        self.assertEqual(result['state'], 'rejected')


if __name__ == '__main__':
    unittest.main()
