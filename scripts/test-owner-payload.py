"""Incremental host payload checks; does not run old BNCH/ledger tests or device tools."""
import argparse
import copy
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import owner_bnch as O
import owner_payload as P

BASE = SOC = WORK = KERNEL = IDENTITY = TRUST = None


class PayloadTests(unittest.TestCase):
    def build(self, name, **options):
        return P.build_candidate(BASE, SOC, KERNEL, O.KERNEL_SHA, IDENTITY, WORK / name,
                                 trust=TRUST, **options)

    def test_01_sources_ast_and_isolation(self):
        base, blobs = P.sources(BASE)
        P.adapt_payload(blobs['payload'])
        for before, after in [(b'root_policies=bool(policies)', b'root_policies=False'),
                              (b'dtb, ctx.board,', b'dtb, copy(ctx.board),'),
                              (b'.write_bytes(generate(', b'.write_bytes(other('),
                              (b'dtb = compile_hardware(ctx)', b'dtb = previous_dtb')]:
            with self.assertRaises(ValueError):
                P.adapt_payload(blobs['payload'].replace(before, after))
        for name, raw in blobs.items():
            with self.assertRaises(ValueError):
                P.validate_blob(name, raw + b'\n# drift', raw)
            with self.assertRaises(ValueError):
                P.validate_blob(name, raw, b'# wrong revision content')
        official = {k: v for k, v in sys.modules.items() if k == 'unixnu' or k.startswith('unixnu.')}
        path_before = list(sys.path)
        missing = dict(blobs)
        del missing['ipsw']
        with self.assertRaises(ValueError):
            with P.private_payload(base, missing, None):
                pass
        with P.private_payload(base, blobs, None) as modules:
            for name, module in modules.items():
                self.assertEqual(Path(module.__file__), base / 'scripts/unixnu' / (name + '.py'))
                self.assertEqual(module.__package__, modules['payload'].__package__)
            self.assertIsNotNone(modules['devicetree'].generate)
        self.assertEqual(path_before, sys.path)
        self.assertEqual(official, {k: v for k, v in sys.modules.items() if k == 'unixnu' or k.startswith('unixnu.')})
        self.assertFalse(any(k.startswith('_nuwa_owner_payload_') for k in sys.modules))

    def test_02_output_gates(self):
        old = WORK / 'old-output'
        old.mkdir()
        for path in (old, O.ROOT.parent / 'escape-output', WORK / '..' / 'traversal'):
            with self.assertRaises(ValueError):
                P.reserve(path)
        link = WORK / 'linked-output'
        link.symlink_to(old, target_is_directory=True)
        with self.assertRaises(ValueError):
            P.reserve(link / 'child')
        if str(WORK).startswith('/mnt/'):
            native_link = WORK / 'junction-output'
            windows = lambda p: p.parts[2].upper() + ':\\' + '\\'.join(p.parts[3:])
            code = ("$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path '" +
                    windows(native_link).replace("'", "''") + "' -Target '" +
                    windows(old).replace("'", "''") + "' | Out-Null")
            r = subprocess.run([shutil.which('powershell.exe'), '-NoProfile', '-NonInteractive',
                                '-Command', code], capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr.decode(errors='replace'))
            with self.assertRaises(ValueError):
                P.reserve(native_link / 'child')
        with self.assertRaises(ValueError):
            P.build_candidate(BASE, SOC, KERNEL, '0' * 64, IDENTITY, WORK / 'unsupported-kernel')

    def test_03_actual_disabled_enabled_reuse(self):
        entered, commands = set(), []

        def observe(frame, event, arg):
            if event == 'call':
                filename = Path(frame.f_code.co_filename)
                if filename.parent == BASE / 'scripts/unixnu':
                    entered.add((filename.stem, frame.f_code.co_name))
                    if filename.stem == 'util' and frame.f_code.co_name == 'run':
                        commands.append([str(x) for x in frame.f_locals['command']])

        prior_profile = sys.getprofile()
        try:
            # Read-only test observation, not an import hook, module/RNG replacement or production patch.
            sys.setprofile(observe)
            disabled = self.build('disabled')
            enabled = self.build('enabled', enabled=True)
            reused = self.build('reused', enabled=True, reuse=WORK / 'enabled/adt-generation/record.json')
        finally:
            sys.setprofile(prior_profile)
        self.assertIn(('devicetree', 'compile_hardware'), entered)
        self.assertIn(('payload', 'write_volume'), entered)
        self.assertNotIn(('payload', 'skip_setup_seed'), entered)
        self.assertNotIn(('feeds', 'fetch'), entered)
        self.assertNotIn(('config', '_save_state'), entered)
        self.assertFalse(any(module in ('kernel', 'patches', 'ipsw') and name not in ('<module>', 'RangeFile', 'Ipsw')
                             for module, name in entered))
        self.assertTrue(all(Path(c[0]).name in ('dtc', 'mformat', 'mcopy') for c in commands))
        O.write_json(WORK / 'observed-build-calls.json', {'functions': sorted([list(x) for x in entered]),
                                                       'commands': commands})
        self.assertFalse((WORK / 'disabled/adt-generation/record.json').exists())
        self.assertTrue(disabled['readback_complete'] and enabled['readback_complete'] and reused['readback_complete'])
        first = O.read_json(WORK / 'enabled/adt-generation/record.json')
        second = O.read_json(WORK / 'reused/adt-generation/record.json')
        self.assertEqual(first['token_hex'], second['token_hex'])
        self.assertEqual(disabled['bridge_calls'], enabled['bridge_calls'])
        O.semantic_equal((WORK / 'disabled/adt-generation/final.adt').read_bytes(),
                         (WORK / 'enabled/adt-generation/final.adt').read_bytes(), allow_bnch=True)
        for label in ('disabled', 'enabled', 'reused'):
            record = O.read_json(WORK / label / 'payload-record.json')
            self.assertEqual(len(record['bridge_calls']), 1)
            self.assertFalse(record['future_probe_hash_approved'])
            work = Path(record['work'])
            self.assertFalse((work / 'tree').exists())
            self.assertFalse((work / '.config').exists())
            self.assertEqual(sorted(p.name for p in (work / 'logs').iterdir()), ['device-tree.log'])
            self.assertEqual(record['overrides']['panic_screen']['after'], False)
            self.assertEqual(record['overrides']['entry_probe_reset_delay']['after'], 0)
            self.assertEqual(record['prepared_kernel_sha256'], O.KERNEL_SHA)
        self.assertFalse(any(k.startswith('_nuwa_owner_payload_') for k in sys.modules))

    def test_04_reuse_mismatch_no_redraw(self):
        previous = WORK / 'enabled/adt-generation/record.json'
        raw_record = previous.read_bytes()
        board = O.read_json(WORK / 'enabled/runtime-board.json')
        kwargs = O.read_json(WORK / 'enabled/adt-generation/keywords.json')
        dtb = (WORK / 'enabled/adt-generation/input.dtb').read_bytes()
        changed = copy.deepcopy(board)
        changed['payload']['size_mib'] += 1
        for binding in [O.binding(dtb + b'\0', board, kwargs), O.binding(dtb, changed, kwargs),
                        O.binding(dtb, board, dict(kwargs, unique_chip_id='1')),
                        O.binding(dtb, board, dict(kwargs, trust=False))]:
            with self.assertRaises(ValueError):
                O.load_record(previous, binding)
        wrong = WORK / 'different-identity.json'
        O.write_json(wrong, {'unique_chip_id': '1' if P.identity(IDENTITY) != '1' else '2'})
        with self.assertRaisesRegex(ValueError, 'Record actual input binding mismatch'):
            P.build_candidate(BASE, SOC, KERNEL, O.KERNEL_SHA, wrong, WORK / 'mismatched-reuse',
                              enabled=True, reuse=previous, trust=TRUST)
        self.assertFalse((WORK / 'mismatched-reuse/adt-generation').exists())
        self.assertFalse((WORK / 'mismatched-reuse/payload-record.json').exists())
        self.assertEqual(previous.read_bytes(), raw_record)
        self.assertEqual(O.read_json(WORK / 'mismatched-reuse/failure.json')['bridge_calls'], 1)
        self.assertFalse(any(k.startswith('_nuwa_owner_payload_') for k in sys.modules))

    def test_05_fat_negative_readbacks(self):
        root = WORK / 'enabled'
        record = O.read_json(root / 'payload-record.json')
        original = Path(record['payload_path'])
        board = O.read_json(root / 'runtime-board.json')
        ctx = argparse.Namespace(board=board)
        expected = {str(p.relative_to(root / 'extracted/EFI/UniXNU')): p.read_bytes()
                    for p in (root / 'extracted/EFI/UniXNU').rglob('*') if p.is_file()}
        final = (root / 'adt-generation/final.adt').read_bytes()
        line = ' '.join(board['payload']['kernel_args'])
        outcomes = []
        for label in ('missing', 'replaced', 'corrupted'):
            directory = WORK / ('fat-' + label)
            directory.mkdir()
            image = directory / 'payload.img'
            shutil.copyfile(original, image)
            if label == 'missing':
                P.capture(['mdel', '-i', image, '::/EFI/UniXNU/Payloads/kernel.macho.adt'], directory / 'modify.json')
            elif label == 'replaced':
                replacement = directory / 'wrong-kernel'
                replacement.write_bytes(b'wrong kernel')
                P.capture(['mcopy', '-o', '-i', image, replacement, '::/EFI/UniXNU/Payloads/kernel.macho'],
                          directory / 'modify.json')
            else:
                with image.open('r+b') as stream:
                    stream.write(bytes(512))
            extraction = directory / 'extracted'
            extraction.mkdir()
            with self.assertRaises(ValueError):
                P.capture(['mcopy', '-s', '-i', image, '::/EFI', extraction], directory / 'extract.json')
                P.verify_extracted(extraction, expected, final, root / 'adt-generation/record.json', ctx, line)
            outcomes.append({'case': label, 'rejected': True})
        O.write_json(WORK / 'fat-negative-checks.json', outcomes)


def main():
    global BASE, SOC, WORK, KERNEL, IDENTITY, TRUST
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'soc', 'kernel', 'identity-keywords', 'trust-cache', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    BASE, SOC, KERNEL, TRUST = a.base.resolve(), a.soc.resolve(), a.kernel.resolve(), a.trust_cache.resolve()
    WORK = P.reserve(a.output)
    IDENTITY = WORK / 'explicit-identity.json'
    O.write_json(IDENTITY, {'unique_chip_id': O.read_json(a.identity_keywords)['unique_chip_id']})
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PayloadTests))
    O.write_json(WORK / 'tests.json', {'status': 'self-checked', 'command': sys.argv,
        'cwd': str(Path.cwd()), 'tests': result.testsRun, 'errors': len(result.errors),
        'failures': len(result.failures), 'device_commands': 0})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
