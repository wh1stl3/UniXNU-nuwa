"""Reconstruct selected merged XNU source in memory and audit initialization order.

No source checkout, image, configuration or device is modified.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

from native_prelink_inputs import ROOT, inputs
from virtual_patch import Tree, parse

XNU = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
BASE = Path('D:/Code/UniXNU-integration')
ARTIFACT = ROOT / 'out/upstream-kernel-40015845083-final/nuwa-8796-merged-40015845083/nuwa-8796-source'
PATHS = ('osfmk/arm64/arm_vm_init.c', 'osfmk/arm64/machine_routines.c',
         'osfmk/kern/startup.c', 'security/mac_base.c',
         'libkern/c++/OSKext.cpp', 'libsa/bootstrap.cpp')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-C', str(repo), *args])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', required=True, type=Path)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Require a fresh report under reports/')
    profile, native, _, _ = inputs(ROOT / 'config/native-prelink-merged-analysis-profile.json')
    merged = json.loads((ROOT / 'config/kernel-merged-profile.json').read_text())
    if git(BASE, 'rev-parse', 'HEAD').decode().strip() != merged['commit']:
        raise ValueError('Integration source pin changed')
    spec = importlib.util.spec_from_file_location('kernel_recipe', ROOT / 'scripts/ci/build-8796-source.py')
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    patches, _, _ = recipe.inputs(BASE, 'merged')
    build = json.loads((ARTIFACT / 'reports/build.json').read_text())
    observed = [dict(name=p.name, sha256=sha(p.read_bytes())) for p in patches]
    if observed != build['patches'] or build['xnu_commit'] != recipe.XNU_COMMIT:
        raise ValueError('Patch sequence differs from actual successful CI artifact')
    tree = Tree(ROOT / 'out/nonexistent-phase-audit-source')
    source_hashes = {}
    for path in PATHS:
        raw = git(XNU, 'show', recipe.XNU_COMMIT + ':' + path).replace(b'\r\n', b'\n')
        tree.files[path] = raw.decode('utf-8')
        source_hashes[path] = dict(original_lf_sha256=sha(raw))
    applications = []
    for patch in patches:
        # Keep original file hunks, including context and line numbers; do not
        # manufacture snippets that could accidentally match a different block.
        for block in re.split(r'(?=^--- )', patch.read_text(encoding='utf-8'), flags=re.M):
            if not block.startswith('--- '):
                continue
            parsed = parse(block)
            if len(parsed) != 1:
                raise ValueError('Unexpected patch file grouping')
            if parsed[0][0] in PATHS:
                applications.append(dict(patch=patch.name, hunks=tree.apply(block)))
    for path in PATHS:
        source_hashes[path]['reconstructed_lf_sha256'] = sha(tree.read(path).encode())
    checks = []
    evidence = []

    def require(name, condition):
        if not condition:
            raise ValueError('Phase audit failed: ' + name)
        checks.append(dict(name=name, passed=True))

    def ordered(path, label, tokens, start=0, end=None):
        text = tree.read(path)
        positions = [text.index(token, start, end) for token in tokens]
        require(label, positions == sorted(set(positions)))
        evidence.append(dict(path=path, claim=label, sites=[dict(
            line=text[:position].count('\n') + 1, token=token)
            for position, token in zip(positions, tokens)]))

    vm = 'osfmk/arm64/arm_vm_init.c'
    ordered(vm, 'Coalesced DATA_CONST starts RWNX and finalizes RNX', [
        'arm_vm_page_granular_RWNX(segPLKDATACONSTB, segSizePLKDATACONST,',
        'arm_vm_prot_finalize(boot_args *',
        'arm_vm_page_granular_RNX(segPLKDATACONSTB, segSizePLKDATACONST,'])
    startup = 'osfmk/kern/startup.c'
    ordered(startup, 'Bootstrap security policy phase precedes machine lockdown',
            ['mac_policy_initmach();', 'machine_lockdown();'])
    machine = tree.read('osfmk/arm64/machine_routines.c')
    require('Machine lockdown calls platform VM protection finalizer',
            'arm_vm_prot_finalize(PE_state.bootArgs);' in machine[machine.index('machine_lockdown(void)'):])
    mac = 'security/mac_base.c'
    ordered(mac, 'Security extensions load before mac_late is set',
            ['load_security_extensions_function();', 'mac_late = 1;'],
            tree.read(mac).index('mac_policy_initmach(void)'))
    bootstrap = 'libsa/bootstrap.cpp'
    require('Bootstrap installs real security extension callback',
            'load_security_extensions_function = &bootstrapLoadSecurityExtensions;' in tree.read(bootstrap))
    require('Security extension selection uses AppleSecurityExtension property',
            'theKext->getPropertyForHostArch(kAppleSecurityExtensionKey)' in tree.read(bootstrap))
    require('Security extensions use normal OSKext loading',
            'OSKext::loadKextWithIdentifier(bundleID->getCStringNoCopy(),' in tree.read(bootstrap))
    require('Installed callback invokes actual security extension loader',
            'sBootstrapObject.loadSecurityExtensions();' in tree.read(bootstrap))
    kext = 'libkern/c++/OSKext.cpp'
    ordered(kext, 'Optional initializer follows constructors and successful kmod start',
            ['result = OSRuntimeInitializeCPP(this);',
             'result = startfunc(kmod_info, kmodStartData);',
             'getPropertyForHostArch("_NativePrelinkEarlySecurityInit")',
             '((void (*)(void))target)();'], tree.read(kext).index('OSKext::start(bool'))
    require('Optional initializer refuses late MAC phase',
            '!earlyInit || !isPrelinked() || mac_late ||' in tree.read(kext))
    require('Split prelinked kext protections defer to platform path',
            'LC_SEGMENT_SPLIT_INFO' in tree.read(kext)[tree.read(kext).index('OSKext::setVMAttributes(bool'):])
    require('Initializer mapping remains empty and loadable remains false',
            profile['early_security_initializers'] == {} and profile['loadable'] is False)
    report = dict(scope='Offline source-order audit, not a runtime page-table or complete CFG proof',
        source_commit=recipe.XNU_COMMIT, merged_commit=merged['commit'],
        kernel_sha256=sha(native), ci_run=40015845083,
        actual_ci_patch_sequence_sha256=sha(json.dumps(observed, sort_keys=True).encode()),
        patch_count=len(patches), selected_source_hashes=source_hashes,
        relevant_patch_applications=applications, checks=checks, evidence=evidence,
        finding='Mach-O initprot=READ alone does not imply DATA_CONST is unwritable during early security start; platform initially maps coalesced DATA_CONST RWNX and lockdown follows MAC early load',
        remaining=['Donor constructor/start/indirect registration and once-guard complete control flow',
                   'Full donor/native mac_policy_ops and C++ ABI',
                   'Actual runtime page-table attributes and stage completion',
                   'Qualified ADT, allocated OS window and large-file transport'],
        initializer_adopted=False, configuration_changed=False, device_accessed=False,
        public_sources=[
          'https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm64/arm_vm_init.c',
          'https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/libkern/c%2B%2B/OSKext.cpp',
          'https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/kern/startup.c',
          'https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/security/mac_base.c'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(checks=len(checks), patches=len(patches), finding=report['finding'])))


if __name__ == '__main__':
    main()
