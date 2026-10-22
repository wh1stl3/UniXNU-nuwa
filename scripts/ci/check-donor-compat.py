"""Check the VFS donor bridge against actual upstream code, in memory only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree


def function(text, signature):
    start = text.index(signature)
    begin = text.index('{', start)
    depth = 0
    for end in range(begin, len(text)):
        depth += (text[end] == '{') - (text[end] == '}')
        if depth == 0:
            return text[start:end + 1]
    raise ValueError('Unterminated reference function')


def normalized(text):
    return re.sub(r'\s+', '', text)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--base', type=Path, required=True)
    cli.add_argument('--xnu', type=Path, required=True)
    cli.add_argument('--reference-xnu', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports'):
        raise ValueError('Output must be a report in this device repository')
    spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/ci/build-8796-source.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    patches, _, _ = builder.inputs(args.base.resolve())
    candidate = ROOT / 'patches/xnu-8796-donor-candidates/vfs-getvfs-with-vfsops.patch'
    if candidate not in patches:
        patches.append(candidate)
    xnu = [p for p in patches if not p.name.startswith('xnu-10063.')]
    native = [p for p in patches if p.name.startswith('xnu-10063.')]
    tree = Tree(args.xnu.resolve())
    hunks = 0
    for patch in sorted(xnu, key=lambda p: p.name) + sorted(native, key=lambda p: p.name):
        hunks += len(tree.apply(patch.read_text(encoding='utf-8')))
    relative = 'bsd/vfs/vfs_subr.c'
    original = (args.xnu / relative).read_text()
    reference = (args.reference_xnu / relative).read_text()
    signature = 'vfs_getvfs_with_vfsops(fsid_t *fsid, const struct vfsops * const ops)'
    candidate_function = function(tree.read(relative), signature)
    reference_function = function(reference, signature)
    if normalized(candidate_function) != normalized(reference_function):
        raise ValueError('Bridge differs from the real upstream implementation')
    helper = 'mount_list_lookupby_fsid(fsid_t *fsid, int locked, int withref)'
    if normalized(function(original, helper)) != normalized(function(reference, helper)):
        raise ValueError('Underlying lookup lock/reference semantics differ')
    if tree.read('config/BSDKernel.exports').splitlines().count('_vfs_getvfs_with_vfsops') != 1:
        raise ValueError('Need exactly one export entry')
    declaration = 'mount_t vfs_getvfs_with_vfsops(fsid_t *fsid, const struct vfsops *ops);'
    if tree.read('bsd/sys/mount.h').count(declaration) != 1:
        raise ValueError('Need the matching declaration')
    result = {'scope': 'static patch and upstream semantic comparison only',
              'patch_count': len(patches), 'hunks': hunks,
              'patch_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
              'reference_file': str(args.reference_xnu / relative),
              'reference_sha256': hashlib.sha256((args.reference_xnu / relative).read_bytes()).hexdigest(),
              'reference_definition_line': reference[:reference.index(signature)].count('\n') + 1,
              'implementation_matches_upstream': True, 'lookup_helper_matches_upstream': True,
              'lookup_arguments': ['fsid', 0, 0],
              'semantics': 'Return the actual mount on matching ops; absent or mismatched returns NULL; no extra reference',
              'source_written': False, 'kernel_compiled': False,
              'donor_abi': 'not runtime qualified', 'device_verified': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
