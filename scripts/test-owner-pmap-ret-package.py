"""Incremental frozen-profile/evidence/FAT/layout checks, not native or initializer tests."""
import argparse
import importlib.util
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import owner_bnch as O
import owner_payload as P

spec = importlib.util.spec_from_file_location('owner_frozen_layout', Path(__file__).with_name('audit-owner-pmap-ret-package.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
BASE = SOC = WORK = FINAL = IDENTITY = TRUST = LOADER = None


class FrozenPackageTests(unittest.TestCase):
    def test_01_explicit_profile_only(self):
        raw = FINAL.read_bytes()
        sha = P.PROFILES[P.DIAGNOSTIC_PROFILE][0]
        with self.assertRaises(ValueError):
            P.qualify_prepared(raw, sha)  # Default remains baseline-only.
        P.qualify_prepared(raw, sha, P.DIAGNOSTIC_PROFILE)
        baseline = O.ROOT / 'out/mix-n-match-20261110/audit-final/new/kernel.macho'
        P.qualify_prepared(baseline.read_bytes(), O.KERNEL_SHA)
        for data, supplied, profile in [
            (raw, '0' * 64, P.DIAGNOSTIC_PROFILE), (raw, sha, 'arbitrary-profile'),
            (baseline.read_bytes(), O.KERNEL_SHA, P.DIAGNOSTIC_PROFILE),
            (raw + b'\0', sha, P.DIAGNOSTIC_PROFILE),
            ((FINAL.parent / 'pristine.macho').read_bytes(), sha, P.DIAGNOSTIC_PROFILE),
            ((FINAL.parent / 'renderer-baseline.macho').read_bytes(), sha, P.DIAGNOSTIC_PROFILE),
            (raw[:0x98d340] + bytes(4) + raw[0x98d344:], sha, P.DIAGNOSTIC_PROFILE)]:
            with self.assertRaises(ValueError):
                P.qualify_prepared(data, supplied, profile)
        with self.assertRaisesRegex(ValueError, 'requires explicit owner BNCH'):
            P.build_candidate(BASE, SOC, FINAL, sha, IDENTITY, WORK / 'disabled-diagnostic',
                              profile=P.DIAGNOSTIC_PROFILE)
        self.assertFalse((WORK / 'disabled-diagnostic').exists())

    def test_02_real_diagnostic_package(self):
        artifact = WORK / 'diagnostic'
        report = P.build_candidate(BASE, SOC, FINAL, P.PROFILES[P.DIAGNOSTIC_PROFILE][0],
                                   IDENTITY, artifact, enabled=True, trust=TRUST, profile=P.DIAGNOSTIC_PROFILE)
        self.assertTrue(report['readback_complete'] and report['diagnostic_only'])
        self.assertFalse(report['new_kernel_initializer_validated'] or report['device_release'])
        record = O.read_json(artifact / 'adt-generation/record.json')
        self.assertEqual(record['schema_version'], 2)
        self.assertEqual(record['input_binding']['artifact'], report['artifact_binding'])
        self.assertEqual(record['input_binding']['generator_validation_baseline_kernel_sha256'], O.KERNEL_SHA)
        self.assertNotIn('kernel_sha256', {k: v for k, v in record['input_binding'].items() if k != 'artifact'})
        self.assertEqual(len(bytes.fromhex(record['token_hex'])), 48)
        O.inspect_adt((artifact / 'adt-generation/final.adt').read_bytes(), bytes.fromhex(record['token_hex']))
        board = O.read_json(artifact / 'runtime-board.json')
        self.assertEqual(board['payload']['kernel_args'], P.DIAGNOSTIC_ARGS)
        self.assertFalse(board['payload']['panic_screen'])
        self.assertEqual(board['payload']['entry_probe_reset_delay'], 0)
        self.assertEqual((artifact / 'extracted/EFI/UniXNU/Payloads/kernel.macho').read_bytes(), FINAL.read_bytes())

    def test_03_record_profile_kernel_boundaries(self):
        root = WORK / 'diagnostic/adt-generation'
        dtb = (root / 'input.dtb').read_bytes()
        board, kwargs = O.read_json(root / 'config.json'), O.read_json(root / 'keywords.json')
        actual = O.read_json(root / 'record.json')['input_binding']['artifact']
        for artifact in [dict(actual, profile=P.BASELINE_PROFILE), dict(actual, kernel_sha256=O.KERNEL_SHA),
                         dict(actual, kernel_bytes=55357440)]:
            with self.assertRaisesRegex(ValueError, 'binding mismatch'):
                O.load_record(root / 'record.json', O.binding(dtb, board, kwargs, artifact))
        legacy = O.ROOT / 'out/owner-payload-verifier-final-20261111/adt-generation/record.json'
        legacy_hash = O.sha(legacy.read_bytes())
        O.load_record(legacy)  # Version1 still readable; never implicitly migrated to profile2.
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            O.load_record(legacy, O.binding(dtb, board, kwargs, actual))
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            O.load_record(root / 'record.json', O.binding(dtb, board, kwargs))
        with self.assertRaisesRegex(ValueError, 'Record actual input binding mismatch'):
            P.build_candidate(BASE, SOC, FINAL, P.PROFILES[P.DIAGNOSTIC_PROFILE][0], IDENTITY,
                              WORK / 'legacy-reuse-rejected', enabled=True, trust=TRUST,
                              profile=P.DIAGNOSTIC_PROFILE, reuse=legacy)
        self.assertFalse((WORK / 'legacy-reuse-rejected/adt-generation').exists())
        self.assertEqual(O.sha(legacy.read_bytes()), legacy_hash)
        wrong = O.read_json(root / 'record.json')
        wrong['schema_version'] = 3
        O.write_json(WORK / 'wrong-schema.json', wrong)
        with self.assertRaises(ValueError):
            O.load_record(WORK / 'wrong-schema.json')

    def test_04_actual_layout_and_boundaries(self):
        result = L.audit(WORK / 'diagnostic', BASE, LOADER, WORK / 'layout')
        self.assertTrue(result['relative_ranges_disjoint'])
        self.assertFalse(result['absolute_conflicts_cleared'] or result['device_release'])
        self.assertLessEqual(result['layout']['Used'], result['layout']['limit'])
        self.assertNotEqual(result['kernel_file_bytes'], result['layout']['kernel_vm_span'])
        self.assertIsNone(result['layout']['window_base_physical'])
        self.assertFalse(result['layout']['guard_is_proven_stack_reservation'])
        self.assertFalse(result['adt_facts']['chosen_boot_manifest_hash_present'])
        L.relative_layout(0x10000000, 0x10000000 + 0x10000000 - 0x200000 - 0x20000, 14000, 66272, 0x10000000)
        with self.assertRaises(ValueError):
            L.relative_layout(0x10000000, 0x20000000 - 0x200000, 14000, 66272, 0x10000000)

    def test_05_actual_fat_tampering(self):
        original = WORK / 'diagnostic'
        tampered = WORK / 'tampered'
        shutil.copytree(original, tampered)
        report = O.read_json(tampered / 'payload-record.json')
        image = tampered / Path(report['payload_path']).relative_to(original)
        report['payload_path'] = str(image)
        replacement = WORK / 'wrong-kernel'
        replacement.write_bytes(b'wrong kernel; not the frozen prepared artifact')
        P.capture(['mcopy', '-o', '-i', image, replacement, '::/EFI/UniXNU/Payloads/kernel.macho'],
                  WORK / 'tamper-command.json')
        (tampered / 'payload-record.json').write_bytes(O.canonical(report))
        with self.assertRaisesRegex(ValueError, 'FAT image hash mismatch'):
            L.audit(tampered, BASE, LOADER, WORK / 'tamper-hash-rejected')
        report['payload_sha256'] = O.sha(image.read_bytes())
        (tampered / 'payload-record.json').write_bytes(O.canonical(report))
        with self.assertRaisesRegex(ValueError, 'FAT member content mismatch'):
            L.audit(tampered, BASE, LOADER, WORK / 'tamper-kernel-rejected')
        self.assertFalse((WORK / 'tamper-kernel-rejected/layout.json').exists())


def main():
    global BASE, SOC, WORK, FINAL, IDENTITY, TRUST, LOADER
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'soc', 'final', 'identity-file', 'trust-cache', 'loader-image', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    BASE, SOC, FINAL = a.base.resolve(), a.soc.resolve(), a.final.resolve()
    IDENTITY, TRUST, LOADER = a.identity_file.resolve(), a.trust_cache.resolve(), a.loader_image.resolve()
    WORK = P.reserve(a.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrozenPackageTests))
    O.write_json(WORK / 'tests.json', {'status': 'self-checked', 'command': sys.argv, 'cwd': str(Path.cwd()),
                                    'tests': result.testsRun, 'errors': len(result.errors), 'failures': len(result.failures)})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
