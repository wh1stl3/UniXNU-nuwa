#!/usr/bin/env python3
"""Apply the device bridge to an isolated frozen 8796 source and compile it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TREE = Path('/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree')
SOURCE = TREE / '.cache/xnu-work'
RECORD = TREE / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT/vfs_subr.o.json'

p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
p.add_argument('--source-copy', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
copy = a.source_copy.resolve()
assert out.is_relative_to(ROOT / 'out') and not out.exists()
assert copy.is_relative_to(Path('/root')) and not copy.exists()
out.mkdir(parents=True)
shutil.copytree(SOURCE, copy, symlinks=True)
patch = ROOT / 'patches/xnu/8796-vfs-getvfs-with-vfsops.patch'
commands = []
def run(args, cwd, label):
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / (label + '.log')).write_bytes(result.stdout)
    commands.append({'argv': list(map(str, args)), 'cwd': str(cwd), 'exit': result.returncode})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    if result.returncode:
        print(result.stdout.decode(errors='replace')[-4000:])
        raise SystemExit(result.returncode)
run(['patch', '-p1', '-i', str(patch)], copy, 'patch')
rec = json.loads(RECORD.read_text().strip().rstrip(','))
args = [s.replace(str(SOURCE), str(copy)) for s in rec['arguments']]
args[args.index('-o') + 1] = str(out / 'vfs_subr.o')
run(args, Path(rec['directory']), 'compile')
obj = out / 'vfs_subr.o'
run(['/usr/bin/llvm-nm', '--defined-only', '--extern-only', str(obj)], ROOT, 'nm')
assert any(line.split()[-1:] == ['_vfs_getvfs_with_vfsops'] for line in (out / 'nm.log').read_text().splitlines())
assert '_vfs_getvfs_with_vfsops\n' in (copy / 'config/BSDKernel.exports').read_text()
header = (copy / 'bsd/sys/mount.h').read_text()
assert 'mount_t vfs_getvfs_with_vfsops(fsid_t *fsid, const struct vfsops * const ops);' in header
source = (copy / 'bsd/vfs/vfs_subr.c').read_text()
def function(name):
    import re
    m = re.search(r'(?m)^(?:struct mount \*|mount_t)\n' + name + r'\([^\n]*\)\n\{', source)
    assert m, name
    start = m.start()
    pos = m.end() - 1
    depth = 0
    for i in range(pos, len(source)):
        if source[i] == '{': depth += 1
        if source[i] == '}':
            depth -= 1
            if not depth: return source[start:i+1]
    raise AssertionError(name)
helper = function('mount_list_lookupby_fsid')
bridge = function('vfs_getvfs_with_vfsops')
original = (SOURCE / 'bsd/vfs/vfs_subr.c').read_text()
assert source.replace(bridge + '\n\n', '', 1) == original
assert helper in original
harness = r'''
#include <stddef.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int val[2]; } fsid_t;
struct vfsops { int marker; };
struct mount { struct { fsid_t f_fsid; } mnt_vfsstat; const struct vfsops *mnt_op; struct mount *next; };
typedef struct mount *mount_t;
static mount_t mountlist;
static int locks, unlocks, refs;
static void mount_list_lock(void) { ++locks; }
static void mount_list_unlock(void) { ++unlocks; }
static int mount_iterref(mount_t m, int x) { (void)m; (void)x; ++refs; return 0; }
#define TAILQ_FOREACH(var, head, field) for ((var) = *(head); (var); (var) = (var)->next)
''' + helper + '\n' + bridge + r'''
static void check(fsid_t id, const struct vfsops *ops, mount_t expected) {
    int l = locks, u = unlocks, r = refs;
    assert(vfs_getvfs_with_vfsops(&id, ops) == expected);
    assert(locks == l + 1 && unlocks == u + 1 && refs == r);
}
int main(void) {
    struct vfsops a = {1}, b = {2};
    struct mount second = {{{{3, 4}}}, &b, NULL};
    struct mount first = {{{{1, 2}}}, &a, &second};
    mountlist = &first;
    check((fsid_t){{1, 2}}, &a, &first);
    check((fsid_t){{3, 4}}, &b, &second);
    check((fsid_t){{1, 2}}, &b, NULL);
    check((fsid_t){{9, 2}}, &a, NULL);
    check((fsid_t){{1, 9}}, &a, NULL);
    mountlist = NULL;
    check((fsid_t){{1, 2}}, &a, NULL);
    puts("six cases: two matches, ops mismatch, each fsid word mismatch, empty; lock/unlock once, no iterref");
}
'''
(out / 'source-contract.c').write_text(harness)
run(['/usr/bin/cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(out / 'source-contract.c'), '-o', str(out / 'source-contract')], ROOT, 'contract-compile')
run([str(out / 'source-contract')], ROOT, 'contract-run')
(out / 'result.json').write_text(json.dumps({'object_bytes': obj.stat().st_size,
    'object_sha256': hashlib.sha256(obj.read_bytes()).hexdigest(),
    'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
    'helper_sha256': hashlib.sha256(helper.encode()).hexdigest(),
    'bridge_sha256': hashlib.sha256(bridge.encode()).hexdigest(),
    'defined_global_symbol': '_vfs_getvfs_with_vfsops',
    'declaration_and_export_list': True, 'source_contract_cases': 6,
    'source_copy': str(copy)}, indent=2) + '\n')
