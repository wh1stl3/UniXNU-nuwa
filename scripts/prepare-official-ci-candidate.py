"""Create a review-only workflow diff from verified API evidence, entirely in memory.

Does not write a workflow, upstream tree, Git metadata or build output.
"""
import difflib
import hashlib
import json
from pathlib import Path

from virtual_patch import Tree

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'e95b37d97875bd8b30c976fcdef44d35d9c27bf3'
WORKFLOW = '.github/workflows/macos.yml'


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Expected exactly one context: {before!r}')
    return text.replace(before, after, 1)


def main():
    audit = json.loads((ROOT / 'reports/official-ci-plan/remote-audit.json').read_text(encoding='utf-8'))
    if audit['commit'] != COMMIT:
        raise ValueError('Candidate must be reviewed again for a different upstream commit')
    changes = audit['comparison']['files']
    entry = next(item for item in changes if item['path'] == WORKFLOW)
    if entry['status'] != 'added':
        raise ValueError('Expected a new workflow relative to the old baseline')
    original = ''.join(line[1:] + '\n' for line in entry['patch'].splitlines()
                       if line.startswith('+') and not line.startswith('+++'))
    evidence = next(item for item in audit['files'] if item['path'] == WORKFLOW)
    if hashlib.sha256(original.encode()).hexdigest() != evidence['sha256']:
        raise ValueError('API diff cannot reconstruct the verified complete workflow')
    candidate = replace_once(original, '        default: kernel userdata\n', '        default: kernel\n')
    candidate = replace_once(candidate, '  HOMEBREW_NO_INSTALL_CLEANUP: 1\n',
                             '  HOMEBREW_NO_INSTALL_CLEANUP: 1\n'
                             '  DEVELOPER_DIR: /Applications/Xcode_16.4.app/Contents/Developer\n')
    candidate = replace_once(candidate, '    runs-on: macos-latest\n', '    runs-on: macos-15-intel\n')
    candidate = replace_once(candidate, '          sw_vers\n',
                             '          test -d "$DEVELOPER_DIR"\n'
                             '          echo "ImageOS=$ImageOS ImageVersion=$ImageVersion"\n'
                             '          sw_vers\n')
    candidate = replace_once(candidate, '          xcode-select -p\n',
                             '          xcode-select -p\n'
                             '          echo "DEVELOPER_DIR=$DEVELOPER_DIR"\n'
                             '          xcrun --sdk iphoneos --show-sdk-version\n'
                             '          xcrun --sdk iphoneos --show-sdk-path\n'
                             '          xcrun --sdk iphoneos clang --version\n'
                             '          xcrun --sdk iphoneos --find iig\n')
    candidate = replace_once(candidate, '      - name: Upload kernel and payload\n',
                             '      - name: Upload kernel and payload\n'
                             '        if: always()\n')
    candidate = replace_once(candidate, '            out/*/logs/**\n',
                             '            out/*/logs/**\n'
                             '            out/*/tree/build/xnu/ios-obj/**/mach.development.bcm2837*\n'
                             '            out/*/tree/build/xnu/ios-obj/**/*.json\n')
    patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True),
                                        candidate.splitlines(keepends=True),
                                        fromfile='a/' + WORKFLOW, tofile='b/' + WORKFLOW))
    virtual = Tree(ROOT / 'out/unused-ci-source')
    virtual.files[WORKFLOW] = original
    hunks = virtual.apply(patch)
    if virtual.files[WORKFLOW] != candidate:
        raise ValueError('In-memory reconstruction did not match the intended candidate')
    destination = ROOT / 'patches/base-ci-candidates/official-macos-observability.patch'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(patch, encoding='utf-8', newline='\n')
    result = {
        'upstream_commit': COMMIT,
        'source_workflow_sha256': evidence['sha256'],
        'patch': destination.relative_to(ROOT).as_posix(),
        'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
        'validation': 'strict in-memory context and exact resulting text only',
        'hunks': hunks,
        'git_commands_executed': [],
        'yaml_actions_execution': 'not verified',
        'kernel_built': False,
        'workflow_installed': False,
        'workflow_dispatched': False,
    }
    (ROOT / 'reports/official-ci-plan/candidate-check.json').write_text(
        json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
