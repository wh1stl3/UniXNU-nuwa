"""Minimal increment checks for the frozen continuation outer wrapper; no rebuild/device."""
import argparse
import importlib.util
import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

spec = importlib.util.spec_from_file_location(
    'owner_continuation_outer', Path(__file__).with_name('build-owner-continuation-vendor-boot.py'))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
V = B.V

BASE = STOCK = LOADER = LAYOUT = CANDIDATE = BUILT = WORK = None


class ContinuationOuterTests(unittest.TestCase):
    def test_01_wrong_profile_fat_arguments_and_evidence_rejected(self):
        ctx = B.validate_inputs(CANDIDATE, STOCK, LOADER, LAYOUT)
        for record in [dict(ctx.source, profile=P.DIAGNOSTIC_PROFILE),
                       dict(ctx.source, execution_mode='diagnostic-stop'),
                       dict(ctx.source, continuation_only=False),
                       dict(ctx.source, device_release=True)]:
            with self.assertRaises(ValueError):
                B.check_record(record)
        for raw, record in [(b'\0' * len(ctx.fat), ctx.source),
                            (ctx.fat, dict(ctx.source, payload_sha256='0' * 64)),
                            (ctx.fat + b'\0', ctx.source)]:
            with self.assertRaises(ValueError):
                B.check_fat(raw, record)
        for arguments in (['-v', 'serial=3', 'sheng-platform-stage=5'],
                          ['-v', 'serial=3', 'sheng-smp=1'], ['-v', 'serial=3', 'reset=1'],
                          ['-v', 'serial=3', 'panic_screen=0'],
                          ['-v', 'serial=3', 'entry_probe_reset_delay=6'],
                          ['-v', 'serial=3', 'native-ufs-root=1'], ['-v']):
            board = dict(ctx.board)
            board['payload'] = dict(ctx.board['payload'], kernel_args=arguments)
            with self.assertRaises(ValueError):
                B.check_args(board, ctx.source)
        B.check_args(ctx.board, ctx.source)
        for cont in [dict(ctx.source['continuation'], diff_byte_count=4),
                     dict(ctx.source['continuation'], source_diagnostic_sha256='0' * 64),
                     dict(ctx.source['continuation'], target_sha256='0' * 64),
                     dict(ctx.source['continuation'], renderer_span={'fileoff': '0x3ee5c0', 'bytes': 2608})]:
            with self.assertRaises(ValueError):
                B.check_continuation(cont)
        with self.assertRaisesRegex(ValueError, 'independent continuation verifier candidate'):
            B.validate_inputs(O.ROOT / 'out/owner-pmap-ret-package-verifier-final-20261111',
                              STOCK, LOADER, LAYOUT)

    def test_02_input_binding_and_stock_distinction(self):
        ctx = B.validate_inputs(CANDIDATE, STOCK, LOADER, LAYOUT)
        self.assertEqual(O.sha(ctx.fat), B.FAT_SHA)
        self.assertEqual(O.sha(ctx.adt), B.ADT_SHA)
        self.assertEqual(O.sha(ctx.record_path.read_bytes()), B.RECORD_SHA)
        self.assertEqual(O.sha(ctx.kernel), B.KERNEL_SHA)
        self.assertEqual(ctx.artifact, {'profile': P.CONTINUATION_PROFILE,
                                        'kernel_sha256': B.KERNEL_SHA, 'kernel_bytes': 55386112})
        self.assertEqual(ctx.source['effective_kernel_args'], '-v serial=3')
        self.assertEqual(ctx.board['payload']['kernel_args'], P.CONTINUATION_ARGS)
        self.assertEqual(ctx.source['owner_record_sha256'], B.RECORD_SHA)
        self.assertTrue(ctx.source['readback_complete'])
        self.assertFalse(ctx.source['device_release'])
        self.assertTrue(set(ctx.source['input_hashes']) ==
                        {'Payloads/kernel.macho', 'Payloads/kernel.macho.trustcache',
                         'Payloads/kernel.macho.adt', 'unixnu.toml'})
        self.assertTrue(ctx.kwargs['trust'] and not ctx.kwargs['data'] and
                        not ctx.kwargs['addon'] and not ctx.kwargs['root_policies'])
        self.assertEqual(ctx.layout['candidate'], str(ctx.candidate))
        self.assertTrue(ctx.layout['relative_ranges_disjoint'])
        self.assertEqual(ctx.layout['runtime_ret_executed'], 'not observed')
        self.assertFalse(ctx.layout['device_release'])
        comparison = B.current_backup_comparison(ctx.stock)
        self.assertTrue(comparison['present'])
        self.assertEqual(comparison['sha256'], B.CURRENT_BACKUP_SHA)
        self.assertFalse(comparison['same_object_as_template'])
        self.assertNotEqual(comparison['dtb_bytes'][0], comparison['dtb_bytes'][1])
        self.assertFalse(comparison['dtb_equal'])
        self.assertFalse(comparison['vbmeta_equal'])
        self.assertTrue(comparison['bootconfig_equal'])

    def test_03_outer_preserved_regions_and_tampering(self):
        ctx = B.validate_inputs(CANDIDATE, STOCK, LOADER, LAYOUT)
        image = (BUILT / 'vendor_boot.img').read_bytes()
        result = V.compare(ctx.stock, image, ctx.fat, len(ctx.stock))
        self.assertTrue(result['header_outside_ramdisk_fields_equal'])
        self.assertTrue(result['table_outside_size_offset_equal'])
        self.assertTrue(result['footer_outside_retarget_equal'])
        self.assertTrue(result['zero_padding_checked'])
        self.assertFalse(result['avb_authentication_claimed'])
        parsed = V.parse(image)
        self.assertEqual(parsed['ramdisk'], ctx.fat)
        self.assertEqual((BUILT / 'actual-vendor-ramdisk.img').read_bytes(), ctx.fat)
        self.assertEqual(parsed['address'], 0x01000000)
        self.assertEqual(parsed['dtb'], V.parse(ctx.stock)['dtb'])
        tb = parsed['offsets']['bootconfig']
        db = parsed['offsets']['dtb']
        vb = parsed['offsets']['vbmeta']
        dtb_end = db + len(parsed['dtb'])
        table_start = parsed['offsets']['table']
        self.assertLess(dtb_end, table_start)
        mutations = {
            'header': 120, 'table': parsed['offsets']['table'] + 16, 'dtb': db, 'bootconfig': tb,
            'vbmeta': vb, 'footer': len(image) - 24, 'padding': dtb_end, 'ramdisk': 4096}
        rejected = []
        for name, offset in mutations.items():
            changed = bytearray(image)
            changed[offset] ^= 1
            try:
                V.compare(ctx.stock, bytes(changed), ctx.fat, len(ctx.stock))
            except ValueError:
                rejected.append(name)
            else:
                raise ValueError('Outer tamper accepted: ' + name)
        self.assertEqual(sorted(rejected), sorted(mutations))

    def test_04_full_chain_entries_and_manifest(self):
        ctx = B.validate_inputs(CANDIDATE, STOCK, LOADER, LAYOUT)
        expected = {'Payloads/kernel.macho': ctx.kernel, 'Payloads/kernel.macho.adt': ctx.adt,
                    'Payloads/kernel.macho.trustcache': (ctx.candidate / 'inputs/kernel.macho.trustcache').read_bytes(),
                    'unixnu.toml': (ctx.candidate / 'extracted/EFI/UniXNU/unixnu.toml').read_bytes()}
        hashes = P.verify_extracted(BUILT / 'extracted', expected, ctx.adt, ctx.record_path,
                                    SimpleNamespace(board=ctx.board), ' '.join(P.CONTINUATION_ARGS), ctx.artifact)
        self.assertEqual(hashes, ctx.source['fat_hashes'])
        config = tomllib.loads(expected['unixnu.toml'].decode())
        self.assertEqual(len(config['entry']), 4)
        self.assertEqual(sum(e['type'] == 'xnu' for e in config['entry']), 1)
        self.assertEqual(sum(e['type'] == 'action' for e in config['entry']), 3)
        self.assertEqual(config['boot']['default'], 'xnu')
        self.assertEqual(config['entry'][0]['args'], '-v serial=3')
        self.assertNotIn('sheng-platform-stage', config['entry'][0]['args'])
        outer = O.read_json(BUILT / 'outer-record.json')
        image = (BUILT / 'vendor_boot.img').read_bytes()
        self.assertEqual(outer['vendor_boot_sha256'], O.sha(image))
        self.assertEqual(outer['vendor_ramdisk_sha256'], B.FAT_SHA)
        self.assertEqual(outer['kernel_sha256'], B.KERNEL_SHA)
        self.assertEqual(outer['adt_sha256'], B.ADT_SHA)
        self.assertEqual(outer['owner_record_sha256'], B.RECORD_SHA)
        self.assertEqual(outer['profile'], P.CONTINUATION_PROFILE)
        self.assertEqual(outer['args_exact'], '-v serial=3')
        self.assertFalse(outer['device_release'])
        self.assertFalse(outer['auth_verified'])
        self.assertEqual(outer['authentication'], 'NOT REACHED')
        self.assertFalse(outer['payload_generated'])
        self.assertFalse(outer['new_bnch_drawn'])
        self.assertFalse(outer['native_rebuilt'])
        self.assertFalse(outer['stock_template_is_current_device_backup'])
        self.assertFalse(outer['executor']['old_r4_boot_claim_reused'])
        self.assertFalse(outer['executor']['device_authorized'])
        self.assertTrue(outer['readback_complete'])


def main():
    global BASE, STOCK, LOADER, LAYOUT, CANDIDATE, BUILT, WORK
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'candidate', 'stock', 'loader', 'layout', 'built', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    BASE, STOCK = a.base.resolve(), a.stock.resolve()
    LOADER, LAYOUT = a.loader.resolve(), a.layout.resolve()
    CANDIDATE, BUILT = a.candidate.resolve(), a.built.resolve()
    WORK = P.reserve(a.output)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ContinuationOuterTests))
    O.write_json(WORK / 'tests.json', {'status': 'self-checked', 'command': sys.argv,
                                       'cwd': str(Path.cwd()), 'tests': result.testsRun,
                                       'errors': len(result.errors), 'failures': len(result.failures),
                                       'device_commands': 0})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
