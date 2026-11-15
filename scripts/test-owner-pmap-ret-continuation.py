"""Increment-only checks for the explicit PMAP continuation profile; no native build, no device."""
import argparse
import importlib.util
import shutil
import struct
import sys
import tomllib
import unittest
from pathlib import Path

import owner_bnch as O
import owner_payload as P

spec = importlib.util.spec_from_file_location(
    'owner_pmap_ret_continuation_audit', Path(__file__).with_name('audit-owner-pmap-ret-continuation-package.py'))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
L = A.D  # Frozen diagnostic audit module; reused only for its layout helpers/constants.

BASE = SOC = WORK = KERNEL = DIAG = PRISTINE = IDENTITY = TRUST = LOADER = None


class ContinuationTests(unittest.TestCase):
    def build(self, name, **options):
        options.setdefault('continuation_reference', DIAG)
        return P.build_candidate(BASE, SOC, KERNEL, P.PROFILES[P.CONTINUATION_PROFILE][0], IDENTITY, WORK / name,
                                 trust=TRUST, profile=P.CONTINUATION_PROFILE, **options)

    def test_01_profile_gate_and_strict_arguments(self):
        raw, sha = KERNEL.read_bytes(), P.PROFILES[P.CONTINUATION_PROFILE][0]
        self.assertEqual(P.PROFILES[P.CONTINUATION_PROFILE],
                         ('7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4', 55386112))
        for data, supplied, profile in [
            (raw, sha, P.BASELINE_PROFILE), (raw, '0' * 64, P.CONTINUATION_PROFILE),
            (raw + b'\0', sha, P.CONTINUATION_PROFILE),
            (DIAG.read_bytes(), P.PROFILES[P.DIAGNOSTIC_PROFILE][0], P.CONTINUATION_PROFILE),
            (PRISTINE.read_bytes(), sha, P.CONTINUATION_PROFILE)]:
            with self.assertRaises(ValueError):
                P.qualify_prepared(data, supplied, profile)
        P.qualify_prepared(raw, sha, P.CONTINUATION_PROFILE)
        with self.assertRaisesRegex(ValueError, 'requires explicit owner BNCH'):
            P.build_candidate(BASE, SOC, KERNEL, sha, IDENTITY, WORK / 'disabled-continuation',
                              profile=P.CONTINUATION_PROFILE)
        self.assertFalse((WORK / 'disabled-continuation').exists())
        with self.assertRaisesRegex(ValueError, 'Continuation reference is required'):
            P.build_candidate(BASE, SOC, KERNEL, sha, IDENTITY, WORK / 'missing-reference',
                              enabled=True, profile=P.CONTINUATION_PROFILE)
        self.assertFalse((WORK / 'missing-reference').exists())
        with self.assertRaisesRegex(ValueError, 'only for the continuation profile'):
            P.build_candidate(BASE, SOC, KERNEL, sha, IDENTITY, WORK / 'unexpected-reference',
                              enabled=True, profile=P.BASELINE_PROFILE, continuation_reference=DIAG)
        self.assertFalse((WORK / 'unexpected-reference').exists())
        self.assertEqual(P.CONTINUATION_ARGS, ['-v', 'serial=3'])
        self.assertNotIn('sheng-platform-stage=5', P.CONTINUATION_ARGS)
        P.check_profile_arguments(P.CONTINUATION_PROFILE, P.CONTINUATION_ARGS, [])
        for arguments, extra in [(P.DIAGNOSTIC_ARGS, []), (P.CONTINUATION_ARGS + ['extra=1'], []),
                                 (P.CONTINUATION_ARGS, ['extra=1'])]:
            with self.assertRaisesRegex(ValueError, 'exactly the reviewed serial-only'):
                P.check_profile_arguments(P.CONTINUATION_PROFILE, arguments, extra)
        with self.assertRaisesRegex(ValueError, 'exactly reviewed kernel arguments'):
            P.check_profile_arguments(P.DIAGNOSTIC_PROFILE, P.CONTINUATION_ARGS, [])

    def test_02_exact_inverse_difference(self):
        raw, source = KERNEL.read_bytes(), DIAG.read_bytes()
        facts = P.continuation_analysis(raw, source)
        self.assertEqual(facts['diff_byte_count'], 8)
        self.assertTrue(facts['other_bytes_identical'])
        self.assertTrue(facts['pmap_ret_restored'] and facts['observer_unhooked'] and facts['renderer_retained'])
        self.assertEqual([(p['fileoff'], p['diagnostic_word'], p['restored_word']) for p in facts['inverse_patches']],
                         [('0x19acf00', '0x14ca9d0e', '0xd65f03c0'), ('0x98d340', '0x17e984a0', '0x14000000')])
        self.assertEqual(facts['renderer_span'], {'fileoff': '0x3ee5c0', 'bytes': 2607})
        for mutate in (
                lambda data: data.__setitem__(0x1000, data[0x1000] ^ 0xff),
                lambda data: struct.pack_into('<I', data, 0x19acf00, 0x14ca9d0e),
                lambda data: struct.pack_into('<I', data, 0x98d340, 0x14000001),
                lambda data: data.__setitem__(0x3ee5c0 + 100, data[0x3ee5c0 + 100] ^ 0xff)):
            changed = bytearray(raw)
            mutate(changed)
            with self.assertRaises(ValueError):
                P.continuation_analysis(bytes(changed), source)
        with self.assertRaisesRegex(ValueError, 'source diagnostic kernel hash/size'):
            P.continuation_analysis(raw, raw)  # Already restored, so not the frozen diagnostic source.
        with self.assertRaisesRegex(ValueError, 'source diagnostic kernel hash/size'):
            P.continuation_analysis(raw, b'\0' * 10)
        broken_source = bytearray(source)
        broken_source[0x1000] ^= 0xff
        with self.assertRaisesRegex(ValueError, 'source diagnostic kernel hash/size'):
            P.continuation_analysis(raw, bytes(broken_source))
        artifact, qualified = P.qualify_continuation(raw, P.PROFILES[P.CONTINUATION_PROFILE][0], DIAG)
        self.assertEqual(artifact, {'profile': P.CONTINUATION_PROFILE,
                                    'kernel_sha256': P.PROFILES[P.CONTINUATION_PROFILE][0],
                                    'kernel_bytes': 55386112})
        self.assertEqual(qualified['source_diagnostic_path'], str(DIAG))
        with self.assertRaises(ValueError):
            P.qualify_continuation(raw, '0' * 64, DIAG)
        repatched = bytearray(raw)  # Re-applying the reviewed diagnostic words is not a continuation image.
        for offset, _, branch, _ in P.CONTINUATION_SITES:
            struct.pack_into('<I', repatched, offset, branch)
        with self.assertRaisesRegex(ValueError, 'Frozen profile kernel hash/size mismatch'):
            P.qualify_continuation(bytes(repatched), P.PROFILES[P.CONTINUATION_PROFILE][0], DIAG)
        with self.assertRaisesRegex(ValueError, 'restored word drift'):
            P.continuation_analysis(bytes(repatched), source)

    def test_03_real_continuation_package(self):
        artifact = WORK / 'continuation'
        report = self.build('continuation', enabled=True)
        self.assertEqual(report['profile'], P.CONTINUATION_PROFILE)
        self.assertFalse(report['diagnostic_only'])
        self.assertTrue(report['continuation_only'] and report['readback_complete'])
        self.assertEqual(report['execution_mode'], 'continue-original')
        self.assertTrue(report['pmap_ret_restored'] and report['observer_unhooked'] and report['renderer_retained'])
        self.assertFalse(report['new_kernel_initializer_validated'] or report['device_release'])
        self.assertEqual(report['artifact_binding'], {'profile': P.CONTINUATION_PROFILE,
                                                      'kernel_sha256': P.PROFILES[P.CONTINUATION_PROFILE][0],
                                                      'kernel_bytes': 55386112})
        self.assertEqual(report['prepared_kernel_sha256'], P.PROFILES[P.CONTINUATION_PROFILE][0])
        self.assertEqual(report['effective_kernel_args'], '-v serial=3')
        self.assertEqual(report['overrides']['kernel_args'],
                         {'before': P.DIAGNOSTIC_ARGS, 'after': P.CONTINUATION_ARGS})
        self.assertEqual(report['continuation'], O.read_json(artifact / 'continuation.json'))
        self.assertEqual(report['continuation']['diff_byte_count'], 8)
        record = O.read_json(artifact / 'adt-generation/record.json')
        self.assertEqual(record['schema_version'], 2)
        self.assertEqual(record['input_binding']['artifact'], report['artifact_binding'])
        self.assertEqual(record['input_binding']['generator_validation_baseline_kernel_sha256'], O.KERNEL_SHA)
        self.assertNotIn('kernel_sha256', {k: v for k, v in record['input_binding'].items() if k != 'artifact'})
        self.assertEqual(len(bytes.fromhex(record['token_hex'])), 48)
        O.inspect_adt((artifact / 'adt-generation/final.adt').read_bytes(), bytes.fromhex(record['token_hex']))
        board = O.read_json(artifact / 'runtime-board.json')
        self.assertEqual(board['payload']['kernel_args'], P.CONTINUATION_ARGS)
        self.assertFalse(board['payload']['panic_screen'])
        self.assertEqual(board['payload']['entry_probe_reset_delay'], 0)
        self.assertEqual((artifact / 'extracted/EFI/UniXNU/Payloads/kernel.macho').read_bytes(), KERNEL.read_bytes())
        config = tomllib.loads((artifact / 'extracted/EFI/UniXNU/unixnu.toml').read_text())
        self.assertEqual(config['entry'][0]['args'], '-v serial=3')
        self.assertNotIn('sheng-platform-stage=5', config['entry'][0]['args'])
        self.assertTrue(report['diagnostic_adt_facts']['memory_map_DeviceTree_present'] is False)
        self.assertEqual(set(report['input_hashes']),
                         {'Payloads/kernel.macho', 'Payloads/kernel.macho.trustcache',
                          'Payloads/kernel.macho.adt', 'unixnu.toml'})
        self.assertEqual(report['input_hashes']['Payloads/kernel.macho.trustcache'], O.sha(TRUST.read_bytes()))

    def test_04_record_profile_kernel_boundaries(self):
        root = WORK / 'continuation/adt-generation'
        dtb = (root / 'input.dtb').read_bytes()
        board, kwargs = O.read_json(root / 'config.json'), O.read_json(root / 'keywords.json')
        actual = O.read_json(root / 'record.json')['input_binding']['artifact']
        for candidate in [dict(actual, profile=P.DIAGNOSTIC_PROFILE),
                          dict(actual, kernel_sha256=P.PROFILES[P.DIAGNOSTIC_PROFILE][0]),
                          dict(actual, kernel_bytes=55357440)]:
            with self.assertRaisesRegex(ValueError, 'binding mismatch'):
                O.load_record(root / 'record.json', O.binding(dtb, board, kwargs, candidate))
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            O.load_record(root / 'record.json', O.binding(dtb, board, kwargs))
        legacy = O.ROOT / 'out/owner-payload-verifier-final-20261111/adt-generation/record.json'
        legacy_hash = O.sha(legacy.read_bytes())
        O.load_record(legacy)  # Version1 stays readable, never implicitly migrated to this profile.
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            O.load_record(legacy, O.binding(dtb, board, kwargs, actual))
        frozen = O.ROOT / 'out/owner-pmap-ret-package-20261111-final/adt-generation/record.json'
        frozen_hash = O.sha(frozen.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Record actual input binding mismatch'):
            self.build('frozen-reuse-rejected', enabled=True, reuse=frozen)
        self.assertFalse((WORK / 'frozen-reuse-rejected/adt-generation').exists())
        self.assertFalse((WORK / 'frozen-reuse-rejected/payload-record.json').exists())
        self.assertEqual(O.sha(frozen.read_bytes()), frozen_hash)
        self.assertEqual(O.sha(legacy.read_bytes()), legacy_hash)
        wrong = O.read_json(root / 'record.json')
        wrong['schema_version'] = 3
        O.write_json(WORK / 'wrong-schema.json', wrong)
        with self.assertRaises(ValueError):
            O.load_record(WORK / 'wrong-schema.json')

    def test_05_package_audit_and_tampering(self):
        result = A.audit(WORK / 'continuation', BASE, LOADER, DIAG, WORK / 'layout')
        self.assertTrue(result['relative_ranges_disjoint'])
        self.assertFalse(result['absolute_conflicts_cleared'] or result['device_release'])
        self.assertEqual(result['runtime_ret_executed'], 'not observed')
        self.assertEqual(result['kernel_sha256'], P.PROFILES[P.CONTINUATION_PROFILE][0])
        self.assertEqual(result['adt_bytes'], len((WORK / 'continuation/adt-generation/final.adt').read_bytes()))
        self.assertLessEqual(result['layout']['Used'], result['layout']['limit'])
        self.assertNotEqual(result['kernel_file_bytes'], result['layout']['kernel_vm_span'])
        self.assertIsNone(result['layout']['window_base_physical'])
        self.assertFalse(result['layout']['guard_is_proven_stack_reservation'])
        self.assertEqual(result['continuation']['diff_byte_count'], 8)
        with self.assertRaisesRegex(ValueError, 'Not a frozen diagnostic package'):
            L.audit(WORK / 'continuation', BASE, LOADER, WORK / 'diagnostic-audit-rejected')
        self.assertFalse((WORK / 'diagnostic-audit-rejected/layout.json').exists())
        with self.assertRaisesRegex(ValueError, 'Not a frozen continuation package'):
            A.audit(O.ROOT / 'out/owner-pmap-ret-package-20261111-final', BASE, LOADER, DIAG,
                    WORK / 'continuation-audit-rejected')
        self.assertFalse((WORK / 'continuation-audit-rejected/layout.json').exists())
        tampered = WORK / 'tampered'
        shutil.copytree(WORK / 'continuation', tampered)
        report = O.read_json(tampered / 'payload-record.json')
        image = tampered / Path(report['payload_path']).relative_to(WORK / 'continuation')
        report['payload_path'] = str(image)
        P.capture(['mcopy', '-o', '-i', image, DIAG, '::/EFI/UniXNU/Payloads/kernel.macho'],
                  WORK / 'tamper-command.json')
        (tampered / 'payload-record.json').write_bytes(O.canonical(report))
        with self.assertRaisesRegex(ValueError, 'FAT image hash mismatch'):
            A.audit(tampered, BASE, LOADER, DIAG, WORK / 'tamper-hash-rejected')
        report['payload_sha256'] = O.sha(image.read_bytes())
        (tampered / 'payload-record.json').write_bytes(O.canonical(report))
        with self.assertRaisesRegex(ValueError, 'FAT member content mismatch'):
            A.audit(tampered, BASE, LOADER, DIAG, WORK / 'tamper-kernel-rejected')
        self.assertFalse((WORK / 'tamper-kernel-rejected/layout.json').exists())
        report['profile'] = P.DIAGNOSTIC_PROFILE
        (tampered / 'payload-record.json').write_bytes(O.canonical(report))
        with self.assertRaisesRegex(ValueError, 'Not a frozen continuation package'):
            A.audit(tampered, BASE, LOADER, DIAG, WORK / 'tamper-profile-rejected')
        self.assertFalse((WORK / 'tamper-profile-rejected/layout.json').exists())


def main():
    global BASE, SOC, WORK, KERNEL, DIAG, PRISTINE, IDENTITY, TRUST, LOADER
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'soc', 'continuation-kernel', 'continuation-reference', 'diagnostic-pristine',
                 'identity-file', 'trust-cache', 'loader-image', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    BASE, SOC = a.base.resolve(), a.soc.resolve()
    KERNEL, DIAG = a.continuation_kernel.resolve(), a.continuation_reference.resolve()
    PRISTINE = a.diagnostic_pristine.resolve()
    IDENTITY, TRUST, LOADER = a.identity_file.resolve(), a.trust_cache.resolve(), a.loader_image.resolve()
    WORK = P.reserve(a.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContinuationTests))
    O.write_json(WORK / 'tests.json', {'status': 'self-checked', 'command': sys.argv, 'cwd': str(Path.cwd()),
                                       'tests': result.testsRun, 'errors': len(result.errors),
                                       'failures': len(result.failures), 'device_commands': 0})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
