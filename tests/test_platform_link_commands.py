"""Protect the original compiler/runtime flags when auditing archive integration."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/ci' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


link = module('platform_link', 'platform-link-audit.py')
build = module('source_build', 'build-8796-source.py')


class LinkCommands(unittest.TestCase):
    def setUp(self):
        self.work = Path('/runner/temporary/source-build')
        self.original = ['make', '-C', '.cache/xnu-work', 'build',
                         'OBJROOT=' + str(self.work / 'build/xnu/ios-obj'),
                         'CFLAGS_EXTRA=-DVALUE=two words -DXNU_BOOT_PROGRESS=0',
                         'start.o_SFLAGS_ADD=-DXNU_NATIVE_ARCH_TIMER=0',
                         'prng_random.o_CFLAGS_ADD=', 'IIG=/real/iig']
        self.archives = [self.work / 'build/driver-archives' / ('lib' + name + '.a')
                         for name in ('ArmCpu', 'ArmDTPlatform')]

    def test_preserves_every_original_argument_and_input_list(self):
        before = list(self.original)
        result = link.link_command(self.original, self.work, self.archives)
        self.assertEqual(result[:-2], before)
        self.assertEqual(self.original, before)
        self.assertTrue(result[-2].endswith('-Wl,-force_load,' + str(self.archives[-1])))
        self.assertNotIn('ArmVirtPlatform', ' '.join(result))

    def test_refuses_existing_provider_override_and_wrong_output_tree(self):
        for extra in ('LD_KERNEL_ARCHIVES=-lother', 'XNU_EXTERNAL_KERNEL_ARCHIVES=old.a'):
            with self.assertRaises(ValueError):
                link.link_command(self.original + [extra], self.work, self.archives)
        self.original[4] = 'OBJROOT=/unrelated/build'
        with self.assertRaises(ValueError):
            link.link_command(self.original, self.work, self.archives)

    def test_captured_shell_executes_identical_expanded_make_arguments(self):
        bash = 'C:/Program Files/Git/bin/bash.exe' if Path('C:/Program Files/Git/bin/bash.exe').exists() else shutil.which('bash')
        self.assertIsNotNone(bash)
        fixture = ('\nmake -C .cache/xnu-work "${XNU_BUILD_TARGET:-build}" \\\n'
                   ' CFLAGS_EXTRA="$EXTRA_CFLAGS" "${EXTRA_MAKE_ARGS[@]}" \\\n'
                   ' OBJROOT="$ROOT/build/xnu/ios-obj" SYMROOT="$ROOT/build/xnu/ios-sym" DSTROOT="$ROOT/build/xnu/ios-dst"\n')
        setup = ('ROOT="/runner/path with space"; EXTRA_CFLAGS="-DVALUE=two words"; '
                 'EXTRA_MAKE_ARGS=("empty=" "-DOTHER=more words"); '
                 'make(){ printf "<%s>\\n" "$@"; }; python3(){ :; };\n')
        actual = subprocess.check_output([bash, '-c', setup + build.capture_kernel_make(fixture)])
        expected = subprocess.check_output([bash, '-c', setup + fixture])
        self.assertEqual(actual, expected)
        self.assertIn(b'<CFLAGS_EXTRA=-DVALUE=two words>', actual)


if __name__ == '__main__':
    unittest.main()
