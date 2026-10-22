"""Check the exact CI patch sequence in memory against a read-only XNU tree."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', required=True, type=Path)
parser.add_argument('--xnu', required=True, type=Path)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('source_builder', ROOT / 'scripts/ci/build-8796-source.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
patches, _, _ = builder.inputs(args.base.resolve())
xnu = [p for p in patches if not p.name.startswith('xnu-10063.')]
prelink = [p for p in patches if p.name.startswith('xnu-10063.')]
tree = Tree(args.xnu.resolve())
hunks = 0
for patch in sorted(xnu, key=lambda p: p.name) + sorted(prelink, key=lambda p: p.name):
    hunks += len(tree.apply(patch.read_text(encoding='utf-8')))
flags = tree.read('makedefs/MakeInc.def')
if '-ftrivial-auto-var-init=zero' not in flags:
    raise ValueError('Auto-variable zero initialization must stay enabled')
if '-enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang' in flags:
    raise ValueError('Legacy clang flag still present')
uio_header = tree.read('bsd/sys/uio_internal.h')
if 'char name[UIO_SIZEOF(niov)] __attribute__((aligned(_Alignof(union iovecs))))' not in uio_header:
    raise ValueError('UIO declaration must preserve byte size and explicit original alignment')
if tree.read('iokit/DriverKit/IORPC.h') != (args.xnu / 'iokit/DriverKit/IORPC.h').read_text(encoding='utf-8'):
    raise ValueError('CI compatibility patches must not widen the original IORPC ABI')
if '#  PERF_DBG_BASE =  [ mach_kdp config_serial_kdp ]' not in tree.read('config/MASTER.arm64.bcm2837'):
    raise ValueError('Public source CI must not select unavailable ARM64 KPC or dependent KPERF')
rules = tree.read('makedefs/MakeInc.rule')
if rules.count('-MJ $@.json') != 2:
    raise ValueError('C and C++ compilation must emit separate records while still compiling')
if 'LD\t= $(KC++) -nostdlib' not in flags or '-MJ' in flags:
    raise ValueError('Record generation must not alter compiler variables or linker invocation')
print(json.dumps({'patch_count': len(patches), 'hunks': hunks,
                  'in_memory_sequence': 'passed', 'zero_initialization_retained': True,
                  'iorpc_header_unchanged': True,
                  'kernel_build': 'not executed by this check', 'source_written': False}, indent=2))
