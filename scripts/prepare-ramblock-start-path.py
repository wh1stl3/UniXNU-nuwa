"""Prepare a default-off storage init patch and audit fixed candidate imports.

Reconstructs the relevant successful CI sources in memory. Does not modify
upstream checkouts, build selection, the kernel or any device.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from virtual_patch import Tree, parse
import read_dispatch_audit as A

ROOT=A.ROOT
BASE=Path('D:/Code/UniXNU-integration')
XNU=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
CI=ROOT/'out/upstream-kernel-40015845083-final/nuwa-8796-merged-40015845083/nuwa-8796-source/reports/build.json'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('Fresh report directory required')
    recipe=module('recipe',ROOT/'scripts/ci/build-8796-source.py')
    ci=json.loads(CI.read_bytes())
    # Current candidates may intentionally supersede old CI inputs. Resolve
    # historical bytes by the CI digest, never use the current recipe blindly.
    candidates=[]
    for directory in [ROOT/'patches',BASE/'patches',BASE/'kits/NativePrelink/patches']:
        candidates.extend(directory.rglob('*.patch'))
    patches=[]
    for row in ci['patches']:
        matches=[p for p in candidates if p.name==row['name'] and sha(p.read_bytes().replace(b'\r\n',b'\n'))==row['sha256']]
        if not matches:raise ValueError('Historical CI patch unavailable: '+row['name'])
        patches.append(matches[0])
    if ci['xnu_commit']!=recipe.XNU_COMMIT:raise ValueError('CI source differs')
    paths=['iokit/bsddev/IOKitBSDInit.cpp','iokit/KernelConfigTables.cpp','libkern/c++/OSKext.cpp','libkern/c++/OSRuntime.cpp','bsd/kern/bsd_init.c']
    tree=Tree(ROOT/'out/nonexistent-ramblock-start-source')
    hashes={};applications=[]
    for path in paths:
        raw=subprocess.check_output(['git','--no-optional-locks','-C',str(XNU),'show',recipe.XNU_COMMIT+':'+path]).replace(b'\r\n',b'\n')
        tree.files[path]=raw.decode();hashes[path]=dict(base_lf_sha256=sha(raw))
    for patch in patches:
        for block in re.split(r'(?=^--- )',patch.read_text(encoding='utf-8'),flags=re.M):
            if block.startswith('--- ') and parse(block)[0][0] in paths:
                applications.append(dict(patch=patch.name,hunks=tree.apply(block)))
    for path in paths:hashes[path]['merged_lf_sha256']=sha(tree.read(path).encode())
    path=paths[0];before=tree.read(path)
    marker='kern_return_t\nIOKitBSDInit( void )\n{\n\tIOService::publishResource("IOBSD");'
    if before.count(marker)!=1:raise ValueError('Init entry drift')
    addition='''#if defined(XNU_NATIVE_RAM_BLOCK_LATE_INIT) && XNU_NATIVE_RAM_BLOCK_LATE_INIT
#if !defined(XNU_NATIVE_RAM_BLOCK) || !XNU_NATIVE_RAM_BLOCK
#error Late RamBlock initialization requires its driver and personality
#endif
#include <libkern/c++/OSKext.h>
extern "C" OSReturn native_ramblock_register_late(void);
#endif

kern_return_t
IOKitBSDInit( void )
{
#if defined(XNU_NATIVE_RAM_BLOCK_LATE_INIT) && XNU_NATIVE_RAM_BLOCK_LATE_INIT
\t/* Finish normal storage constructors/start before entering our own
\t * metaclass transaction. Do not defer a boot dependency to userspace.
\t */
\tOSReturn storageResult = OSKext::loadKextWithIdentifier(
\t    "com.apple.iokit.IOStorageFamily", false, false,
\t    kOSKextExcludeNone, kOSKextExcludeNone, NULL);
\tif (storageResult != kOSReturnSuccess) return storageResult;
\tOSReturn ramblockResult = native_ramblock_register_late();
\tif (ramblockResult != kOSReturnSuccess) return ramblockResult;
#endif
\tIOService::publishResource("IOBSD");'''
    after=before.replace(marker,addition)
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    tree.apply(patch)
    if tree.read(path)!=after:raise ValueError('Patch reconstruction failed')
    # The native top-level caller discards bsd_autoconf's result. Returning an
    # error before IOBSD publication alone would turn a concrete error into a
    # later resource/root wait. Fail explicitly only when this candidate is on.
    bsd=tree.read(paths[4]); old='\tbsd_autoconf();'
    if bsd.count(old)!=1:raise ValueError('BSD caller drift')
    replacement='''#if defined(XNU_NATIVE_RAM_BLOCK_LATE_INIT) && XNU_NATIVE_RAM_BLOCK_LATE_INIT
\tkern_return_t ramblockBootResult = bsd_autoconf();
\tif (ramblockBootResult != KERN_SUCCESS) {
\t\tpanic("RamBlock boot dependency failed: 0x%x", ramblockBootResult);
\t}
#else
\tbsd_autoconf();
#endif'''
    bsd_after=bsd.replace(old,replacement)
    error_patch=''.join(difflib.unified_diff(bsd.splitlines(True),bsd_after.splitlines(True),fromfile='a/'+paths[4],tofile='b/'+paths[4]))
    tree.apply(error_patch);patch+=error_patch
    if tree.read(paths[4])!=bsd_after:raise ValueError('Error patch reconstruction failed')
    kext=tree.read(paths[2]); runtime=tree.read(paths[3]); personality=tree.read(paths[1])
    start=kext[kext.index('OSKext::start(bool'):kext.index('OSKext::canUnloadKextWithIdentifier(')]
    tokens=['dependency->start(startDependenciesFlag)','result = OSRuntimeInitializeCPP(this);','result = startfunc(kmod_info, kmodStartData);','flags.started = 1;']
    positions=[start.index(t) for t in tokens]
    if positions!=sorted(positions):raise ValueError('Native start ordering changed')
    if 'OSMetaClass::postModLoad' not in runtime:raise ValueError('Runtime transaction missing')
    if 'IORecursiveLockUnlock(sKextLock);\n\n\treturn result;' not in kext:
        raise ValueError('Loader lock release changed')
    if 'result == kOSReturnSuccess && startMatchingOpt == kOSKextExcludeNone' not in kext or 'sendPersonalitiesToCatalog(true, personalityNames)' not in kext:
        raise ValueError('Storage personality publication changed')
    rt=runtime[runtime.index('OSRuntimeInitializeCPP(\n'):]
    if rt.index('result = OSMetaClass::postModLoad(metaHandle);')>rt.index('theKext->setCPPInitialized(true);'):
        raise ValueError('Runtime completion ordering changed')
    if "'IOClass'         = NativeRamBlock;" not in personality or "'IOResourceMatch' = IOBSD;" not in personality:raise ValueError('Personality changed')

    kernel=ROOT/'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho'
    raw=kernel.read_bytes()
    if sha(raw)!='2bceb55856bf1a6159855c1de7783261275a9949562d6adc549281df3245fad1':raise ValueError('Kernel drift')
    symbols=A.B.macho(raw)['symbols']
    inspect=runpy.run_path(str(ROOT/'scripts/build-ramblock-late-analysis.py'))['inspect']
    late=ROOT/'out/ramblock-ios16-late-20261029-r6'
    qual=json.loads((late/'qualification.json').read_bytes())
    definitions=set();imports={}
    for name,key in [('NativeRamBlock.late.o','object_sha256'),('NativeRamBlockLateInit.o','wrapper_object_sha256')]:
        data=(late/name).read_bytes()
        if sha(data)!=qual[key]:raise ValueError('Object drift')
        _,syms=inspect(data)
        for n,(kind,section,desc,value) in syms.items():
            if kind&0xe: definitions.add(n)
            elif kind&1: imports[n]=bool(desc&0x40)
    aliases=json.loads((ROOT/'reports/desktop-readiness/2026-10-29-storage-dispatch-r3/audit.json').read_bytes())['analysis_only_import_map']
    resolved=[];missing=[]
    for name,weak in sorted(imports.items()):
        if name in definitions:source='archive'
        elif name in symbols:source='kernel-symbol'
        elif name in aliases:source='original-storage-binding'
        else:source='unresolved'
        row=dict(name=name,weak=weak,source=source)
        if source=='kernel-symbol':row['address']=hex(symbols[name])
        elif source=='original-storage-binding':row['address']=aliases[name]
        resolved.append(row)
        if source=='unresolved' and not weak:missing.append(name)
    # Identify the exact overload from actual kernel names, not a guessed mangling.
    load_symbols=[n for n in symbols if 'OSKext' in n and 'loadKextWithIdentifierEPKc' in n]
    if len(load_symbols)!=1:raise ValueError('Expected one C-string loader overload')
    out.mkdir(parents=True)
    (out/'native-ramblock-late-init.patch').write_text(patch,encoding='utf-8',newline='\n')
    report=dict(scope='Static merged-source candidate and import closure; not final linked or runtime qualified',
        enabled=False,deployable=False,kernel_sha256=sha(raw),ci_run=40015845083,
        source_commit=recipe.XNU_COMMIT,source_hashes=hashes,applied_existing_patches=applications,
        patch_sha256=sha(patch.encode()),archive_sha256=qual['archive_sha256'],
        import_resolution=resolved,missing_strong=missing,loader_overload=load_symbols[0],
        selected_order=['Normal IOStorageFamily load/start and storage personality publication; no userspace deferral',
                        'Loader returns after releasing its lock','Explicit RamBlock registration',
                        'Publish IOBSD for existing personality matching'],
        checks=dict(patch_roundtrip=True,normal_storage_start_order=True,late_archive_strong_imports_closed=not missing,
                    native_bsd_autoconf_result_discarded=True,candidate_error_consumed_by_explicit_panic=True),
        remaining=['Compile whole patched IOKitBSDInit under production private headers',
                   'Compile and exercise guarded BSD error propagation',
                   'Final link relocations, alias rebinding and absent duplicate constructors',
                   'Provider execution and loader ownership'],device_accessed=False)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'audit-script.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(missing_strong=missing,loader_overload=load_symbols[0],patch_sha256=report['patch_sha256'],enabled=False)))

if __name__=='__main__':main()
