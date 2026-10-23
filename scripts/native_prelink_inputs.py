"""Read pinned NativePrelink tools in memory; never edit or vendor the source tree."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from virtual_patch import Tree

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/Code/PortingiOS/common/sources/UniXNU')
NATIVE=ROOT/'out/kernel-ci/39793231214/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped'
DONOR=Path('D:/Code/PortingiOS/nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho')
SELECTION=Path('D:/Code/PortingiOSWithUniXNU/.work/kernel-prelinked.json')

def sha(data):return hashlib.sha256(data).hexdigest()

def inputs():
    profile=json.loads((ROOT/'config/native-prelink-analysis-profile.json').read_text())
    native,donor,selection=NATIVE.read_bytes(),DONOR.read_bytes(),SELECTION.read_bytes()
    for raw,key in ((native,'native_sha256'),(donor,'donor_sha256'),(selection,'reference_selection_sha256')):
        if sha(raw)!=profile[key]:raise ValueError('Pinned input changed: '+key)
    return profile,native,donor,json.loads(selection)

@contextmanager
def tools(patched=False):
    profile=json.loads((ROOT/'config/native-prelink-analysis-profile.json').read_text())
    tree=Tree(ROOT/'out/nonexistent-source')
    module=profile.get('source_module')
    source=Path('D:/Code/UniXNU-integration') if module else BASE
    if module:
        actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()
        if actual!=profile['source_commit']:raise ValueError('Merged source pin changed')
    for path,expected in profile['source_sha256'].items():
        repo=source/module['path'] if module else source
        revision=module['commit'] if module else profile['source_commit']
        relative=path.removeprefix(module['path']+'/') if module else path
        raw=subprocess.check_output(['git','--no-optional-locks','-c',f'safe.directory={repo}','-C',str(repo),'show',revision+':'+relative]).replace(b'\r\n',b'\n')
        if sha(raw)!=expected:raise ValueError('Pinned tool source changed')
        tree.files[path]=raw.decode()
    if patched:
        item=profile['patch'];raw=(ROOT/item['path']).read_bytes()
        if sha(raw)!=item['sha256']:raise ValueError('Patch changed')
        tree.apply(raw.decode())
        if sha(tree.read('kits/NativePrelink/emit_prelink.py').encode())!=item['post_sha256']:raise ValueError('Patched tool hash mismatch')
    previous=sys.modules.get('native_prelink')
    parser=types.ModuleType('native_prelink')
    exec(compile(tree.read('kits/NativePrelink/native_prelink.py'),'pinned-native-prelink','exec'),parser.__dict__)
    sys.modules['native_prelink']=parser
    emitter=types.ModuleType('pinned_emitter')
    try:
        exec(compile(tree.read('kits/NativePrelink/emit_prelink.py'),'pinned-emit-prelink','exec'),emitter.__dict__)
        yield parser,emitter
    finally:
        if previous is None:sys.modules.pop('native_prelink',None)
        else:sys.modules['native_prelink']=previous

def components(parser,donor,selection):
    parent=parser.macho(donor)['segments']
    info=next(s for s in parent if s['name']=='__PRELINK_INFO')
    at=parser.backed_offset(parent,info['va'],info['filesize'],len(donor))
    metadata=parser.unserialize_xml(donor[at:at+info['filesize']])
    entries={e['CFBundleIdentifier']:e for e in metadata['_PrelinkInfoDictionary']}
    modules={name:parser.macho(donor,parser.backed_offset(parent,entries[name]['_PrelinkExecutableLoadAddr'],32,len(donor))) for name in selection['components']}
    return parent,metadata,modules
