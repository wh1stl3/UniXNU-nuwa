"""Host-only adapter tests and optional real nuwa ADT preparation; no device access."""
import argparse
import copy
import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import owner_bnch as O

BASE = None
WORK = None
DTB = None
CONFIG = None
KWARGS = None


def prepare(base, output):
    """Use formal profiles.load's merge routine/order, not a copied generator."""
    import tomllib
    sys.path.insert(0, str(base / 'scripts'))
    try:
        profiles = importlib.import_module('unixnu.profiles')
        require_path = (base / 'scripts/unixnu/profiles.py').resolve()
        O.require(Path(profiles.__file__).resolve() == require_path, 'Formal profiles origin')
        # Configuration preparation only; never used to override generator dependencies.
        O.require(require_path.read_bytes().replace(b'\r\n', b'\n') ==
                  O.git(base, 'show', O.REVISION + ':scripts/unixnu/profiles.py').replace(b'\r\n', b'\n'),
                  'Formal profiles revision mismatch')
        paths = [base / 'profiles/arch/arm64/profile.toml',
                 O.ROOT.parent / 'UniXNU-sm8550-common/soc.toml',
                 base / 'profiles/os/ios-16.7.16-20H392/profile.toml', O.ROOT / 'board.toml']
        config = {}
        for path in paths:
            config = profiles.merge(config, tomllib.loads(path.read_text(encoding='utf-8')))
        os_name = config['board']['os_profile']
        overrides = config.pop('os_overrides', {}).get(os_name, {})
        O.require('remove' not in overrides, 'Preparation requires formal removal handling')
        config = profiles.merge(config, overrides)
    finally:
        sys.path.pop(0)
    identity = tomllib.loads((base / 'unixnu.local.toml').read_text())['build']['unique_chip_id']
    kwargs = dict(unique_chip_id=str(identity), data=False, trust=True, addon=False, root_policies=False)
    O.validate_config(config, kwargs)
    dtb = base / 'out/nuwa/ios-16.7.16-20H392/nuwa/device-tree/hardware.dtb'
    O.write_json(output / 'resolved-config.json', config)
    O.write_json(output / 'generate-keywords.json', kwargs)
    return dtb, config, kwargs


class AdapterTests(unittest.TestCase):
    def destination(self, label):
        return WORK / label

    def generate(self, label, **options):
        return O.generate_candidate(BASE, DTB, CONFIG, KWARGS, self.destination(label), **options)

    def test_01_manifest_interface(self):
        for value in [None, (), [('BNCH', bytearray(48))], [('BNCH', bytes(47))],
                      [('BNCH', bytes(49))], [('OTHER', bytes(48))],
                      [('BNCH', bytes(48)), ('BNCH', bytes(48))], [['BNCH', bytes(48)]]]:
            with self.subTest(kind=repr(type(value))):
                with self.assertRaises(ValueError):
                    O.manifest_properties(value)
        self.assertEqual(O.manifest_properties([]), [])
        self.assertEqual(O.manifest_properties([('BNCH', bytes(48))]), [('BNCH', bytes(48))])

    def test_02_ast_drift(self):
        _, sources = O.verified_sources(BASE)
        raw = sources['devicetree.py']
        O.adapt(raw)
        for before, after in [(b"node('manifest-properties')", b"node('manifest-properties', [])"),
                              (b"node('manifest-properties')", b"node('manifest-properties', properties=[])"),
                              (b"node('manifest-properties')", b"node('other')"),
                              (b'children = [node(\'chosen\'', b'other_children = [node(\'chosen\'')]:
            with self.subTest(after=after):
                self.assertNotEqual(raw.replace(before, after), raw)
                with self.assertRaises(ValueError):
                    O.adapt(raw.replace(before, after))

    def test_03_typed_duplicate_and_automatic(self):
        for table in [{'string': {'x': 'x'}, 'u32': {'x': 0}}, {'u32': {'name': 0}},
                      {'bytes': {'random-seed': '00'}}, {'u64': {'chip-id': 1}},
                      {'manifest-properties': {'bytes': {'BNCH': '00' * 48}}}]:
            c = copy.deepcopy(CONFIG)
            c['adt']['chosen'] = table
            with self.assertRaises(ValueError):
                O.validate_config(c, KWARGS)
        for kw in [dict(KWARGS, data=1), {'data': False}]:
            with self.assertRaises(ValueError):
                O.validate_config(CONFIG, kw)
        with self.assertRaises(ValueError):
            O.unique_pairs([('x', 1), ('x', 2)])

    def test_04_ordered_duplicate_parser(self):
        with O.generator(BASE, []) as m:
            duplicate_prop = m.node('device-tree', [('x', b''), ('x', b'')])
            duplicate_child = m.node('device-tree', children=[m.node('chosen'), m.node('chosen')])
        for raw in (duplicate_prop, duplicate_child):
            with self.assertRaises(ValueError):
                O.parse(raw)

    def test_05_generation_reuse_no_residue(self):
        before = {k: v for k, v in sys.modules.items() if k.startswith('_nuwa_owner_adt_')}
        self.generate('enabled', enabled=True)
        self.generate('disabled')
        first = O.read_json(WORK / 'enabled/record.json')
        self.generate('reused', enabled=True, reuse=WORK / 'enabled/record.json')
        second = O.read_json(WORK / 'reused/record.json')
        self.assertEqual(first['token_hex'], second['token_hex'])
        self.assertFalse((WORK / 'disabled/record.json').exists())
        enabled = (WORK / 'enabled/final.adt').read_bytes()
        disabled = (WORK / 'disabled/final.adt').read_bytes()
        O.inspect_adt(enabled, bytes.fromhex(first['token_hex']))
        O.inspect_adt(disabled)
        O.semantic_equal(enabled, disabled, allow_bnch=True)
        self.assertEqual(before, {k: v for k, v in sys.modules.items() if k.startswith('_nuwa_owner_adt_')})
        # Explicit negative policies must reject before reserving an output.
        with self.assertRaises(ValueError):
            self.generate('disabled-with-record', reuse=WORK / 'enabled/record.json')
        self.assertFalse((WORK / 'disabled-with-record').exists())
        with self.assertRaises(ValueError):
            self.generate('enabled', enabled=True)
        self.assertEqual(first, O.read_json(WORK / 'enabled/record.json'))

    def test_06_actual_content_binding(self):
        record = WORK / 'enabled/record.json'
        c = copy.deepcopy(CONFIG)
        c['payload']['adt']['chip_id'] = '12345678'
        with self.assertRaises(ValueError):
            O.generate_candidate(BASE, DTB, c, KWARGS, WORK / 'config-mismatch', True, record)
        with self.assertRaises(ValueError):
            O.generate_candidate(BASE, DTB, CONFIG, dict(KWARGS, trust=False),
                                 WORK / 'kw-mismatch', True, record)
        changed_dtb = WORK / 'changed.dtb'
        changed_dtb.write_bytes(DTB.read_bytes() + b'\0')
        with self.assertRaises(ValueError):
            O.generate_candidate(BASE, changed_dtb, CONFIG, KWARGS, WORK / 'dtb-mismatch', True, record)
        for label in ('config-mismatch', 'kw-mismatch', 'dtb-mismatch'):
            self.assertFalse((WORK / label).exists())
        wrong = O.read_json(record)
        wrong['token_hex'] = '00' * 48
        O.write_json(WORK / 'wrong-record.json', wrong)
        token = bytes.fromhex(wrong['token_hex'])
        with self.assertRaises(ValueError):
            O.inspect_adt((WORK / 'enabled/final.adt').read_bytes(), token)

    def test_07_generation_exception_retains_record(self):
        bad = WORK / 'invalid.dtb'
        bad.write_bytes(b'not an FDT')
        destination = WORK / 'generation-failure'
        with self.assertRaises(Exception):
            O.generate_candidate(BASE, bad, CONFIG, KWARGS, destination, enabled=True)
        record = O.read_json(destination / 'record.json')
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(len(bytes.fromhex(record['token_hex'])), 48)
        self.assertFalse((destination / 'final.adt').exists())
        with self.assertRaises(ValueError):
            O.generate_candidate(BASE, bad, CONFIG, KWARGS, destination, enabled=True)
        with self.assertRaises(ValueError):
            O.generate_candidate(BASE, bad, CONFIG, KWARGS, WORK / 'failed-reuse', True,
                                 destination / 'record.json')
        self.assertEqual(record, O.read_json(destination / 'record.json'))

    def test_08_revision_source_util_drift(self):
        # Local miniature Git repo is only for rejection tests, never an alternate generator.
        fake = WORK / 'wrong-base'
        fake.mkdir()
        subprocess.run(['git', 'init', '-q', str(fake)], check=True)
        (fake / '.git/HEAD').write_text('0' * 40 + '\n')
        with self.assertRaisesRegex(ValueError, 'revision drift'):
            O.verified_sources(fake)
        # Fixed revision commit with a drifted working source, using a shared read-only object store.
        (fake / '.git/objects/info/alternates').write_text(str(BASE / '.git/objects') + '\n')
        (fake / '.git/HEAD').write_text(O.REVISION + '\n')
        directory = fake / 'scripts/unixnu'
        directory.mkdir(parents=True)
        for filename in ('devicetree.py', 'util.py'):
            (directory / filename).write_bytes((BASE / 'scripts/unixnu' / filename).read_bytes())
        (directory / 'devicetree.py').write_bytes(b'# drift\n')
        with self.assertRaisesRegex(ValueError, 'SHA drift: devicetree'):
            O.verified_sources(fake)
        (directory / 'devicetree.py').write_bytes((BASE / 'scripts/unixnu/devicetree.py').read_bytes())
        (directory / 'util.py').write_bytes(b'# drift\n')
        with self.assertRaisesRegex(ValueError, 'SHA drift: util'):
            O.verified_sources(fake)

    def test_09_semantic_difference_rejected(self):
        raw = (WORK / 'enabled/final.adt').read_bytes()
        # Same length corruption of a non-random property is not normalized away.
        changed = raw.replace(b'mix-n-match-prevention-status', b'mix-n-match-prevention-statuX')
        self.assertNotEqual(raw, changed)
        with self.assertRaises(ValueError):
            O.semantic_equal(raw, changed, allow_bnch=True)
        with self.assertRaises(ValueError):
            O.inspect_adt(changed, bytes.fromhex(O.read_json(WORK / 'enabled/record.json')['token_hex']))

    def test_10_final_checker(self):
        candidate = WORK / 'enabled'
        final = candidate / 'final.adt'
        expected = O.sha(final.read_bytes())
        kernel = O.ROOT / 'out/mix-n-match-20261110/audit-final/new/kernel.macho'
        command = ['/usr/bin/python3', '-B', str(O.ROOT / 'scripts/check-owner-boot-artifact-bnch.py'),
                   '--kernel', str(kernel), '--adt', str(final), '--record', str(candidate / 'record.json'),
                   '--adt-sha256', expected, '--output', str(WORK / 'initializer'), '--failure-controls']
        original_hash = O.sha(final.read_bytes())
        completed = subprocess.run(command, capture_output=True, text=True)
        (WORK / 'initializer-command.json').write_bytes(O.canonical({
            'command': command, 'cwd': str(Path.cwd()), 'exit': completed.returncode,
            'stdout': completed.stdout, 'stderr': completed.stderr}))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(O.sha(final.read_bytes()), original_hash)
        result = O.read_json(WORK / 'initializer/initializer.json')
        self.assertEqual(result['initialization']['bnch_errno'], 0)
        self.assertEqual(result['initialization']['bnch_output_length'], 48)
        self.assertTrue(result['initialization']['bnch_canaries_intact'])
        self.assertEqual(result['failure_controls']['missing']['bnch_errno'], 2)
        self.assertEqual(result['failure_controls']['oversized49']['bnch_errno'], 84)
        rejected = []
        for label, option, value, reason in [
            ('adt-mismatch', '--adt-sha256', '0' * 64, 'Final ADT SHA mismatch'),
            ('record-mismatch', '--record', str(WORK / 'wrong-record.json'), 'Record must belong'),
            ('existing-output', '--output', str(WORK / 'initializer'), 'Output already exists')]:
            negative = list(command)
            negative[negative.index(option) + 1] = value
            if option != '--output':
                negative[negative.index('--output') + 1] = str(WORK / label)
            r = subprocess.run(negative, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn(reason, r.stderr)
            rejected.append({'case': label, 'exit': r.returncode, 'expected_reason': reason})
            if option != '--output':
                self.assertFalse((WORK / label).exists())
        O.write_json(WORK / 'initializer-negative-checks.json', rejected)

    def test_11_manifest_policy(self):
        with O.generator(BASE, []) as m:
            def blob(value, extra=(), manifest_extra=()):
                return m.node('device-tree', children=[m.node('chosen', [
                    ('random-seed', bytes(256)), ('mix-n-match-prevention-status', bytes(4)), *extra],
                    [m.node('manifest-properties', [('BNCH', value), *manifest_extra])])])
            for raw in [blob(bytes(47)), blob(bytes(49)), blob(bytes(48), [('BNCH', bytes(48))]),
                        blob(bytes(48), manifest_extra=[('CHMH', b'')])]:
                with self.assertRaises(ValueError):
                    O.inspect_adt(raw, bytes(48))


def main():
    global BASE, WORK, DTB, CONFIG, KWARGS
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    BASE = a.base.resolve()
    O.verified_sources(BASE)
    WORK = O.reserve(a.output)
    DTB, CONFIG, KWARGS = prepare(BASE, WORK)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AdapterTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    O.write_json(WORK / 'tests.json', {'status': 'self-checked', 'tests': result.testsRun,
                 'errors': len(result.errors), 'failures': len(result.failures),
                 'command': sys.argv, 'cwd': str(Path.cwd())})
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
