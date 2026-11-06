"""Audit successful CI private RamBlock objects against the fixed iOS16 native class."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import read_dispatch_audit as A

ROOT=A.ROOT
spec=importlib.util.spec_from_file_location('storage_macho','D:/Code/PortingiOSLegacy/common/sources/UniXNU/kits/NativePrelink/native_prelink.py')
NP=importlib.util.module_from_spec(spec);spec.loader.exec_module(NP)

def require(v,message):
    if not v:raise ValueError(message)

def object_table(path,classname):
    raw=path.read_bytes();image=NP.macho(raw)
    require(image['kind']==1,'Expected object')
    version=next(at for cmd,at,size in image['commands'] if cmd==0x32)
    require(struct.unpack_from('<II',raw,version+8)==(2,0x100000),'Expected iOS16 deployment')
    at=next(at for cmd,at,size in image['commands'] if cmd==2)
    sy,count,st,sz=struct.unpack_from('<4I',raw,at+8)
    symbols=[]
    for i in range(count):
        ix,kind,sec,desc,value=struct.unpack_from('<IBBHQ',raw,sy+i*16)
        name=raw[st+ix:raw.index(b'\0',st+ix)].decode()
        symbols.append(dict(name=name,value=value,kind=kind,desc=desc))
    v=next(s['value'] for s in symbols if s['name']=='__ZTV'+str(len(classname))+classname)
    rel={}
    for seg in image['segments']:
        for section in seg['sections']:
            if section['va']<=v<section['va']+section['size']:
                ro,rc=struct.unpack_from('<II',raw,section['command_offset']+56)
                for i in range(rc):
                    addr,word=struct.unpack_from('<II',raw,ro+i*8)
                    if word>>27&1 and word>>28==0 and word>>25&3==3:
                        rel[section['va']+addr]=symbols[word&0xffffff]['name']
    methods=[]
    while v+16+len(methods)*8 in rel:methods.append(rel[v+16+len(methods)*8])
    return methods,symbols

def compare(reference,transport,native,readable):
    require(len(reference)==len(transport)==len(native)==190,'Dispatch length')
    matches=0;overrides=0
    for i,(expected,actual,row) in enumerate(zip(reference,transport,native)):
        if row['native_names']:
            require(expected in row['native_names'],'Native/reference mismatch at '+str(i));matches+=1
        own=actual.startswith(('__ZN14NativeRamBlock','__ZNK14NativeRamBlock'))
        if expected=='___cxa_pure_virtual':require(own,'Missing concrete transport implementation')
        elif actual!=expected:
            require(own,'Unexpected transport inherited target')
            if i not in (0,1):
                suffix=lambda s:readable[s].split('::',1)[1]
                require(suffix(expected)==suffix(actual),'Override signature mismatch at '+str(i))
        overrides+=own
    require('___cxa_pure_virtual' not in transport,'Abstract transport')
    return matches,overrides

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    out=args.output.resolve();require(not out.exists() and out.is_relative_to(ROOT/'reports'),'Fresh reports directory')
    ci=ROOT/'out/ci-ramblock-40870837215/nuwa-8796-merged-40870837215/nuwa-8796-source'
    objdir=ci/'build/ramblock-archive'
    buildpath=ci/'reports/ramblock-archive/audit.json'; build=json.loads(buildpath.read_bytes())
    require(build['passed'] and build['private_definitions_preserved'],'Production build incomplete')
    require(hashlib.sha256((objdir/'libNativeRamBlock.late.a').read_bytes()).hexdigest()==build['archive_sha256'],'Production archive drift')
    reference,_=object_table(objdir/'IOBlockStorageReference.o','IOBlockStorageDevice')
    transport,symbols=object_table(objdir/'NativeRamBlock.o','NativeRamBlock')
    nativepath=ROOT/'reports/desktop-readiness/2026-10-29-storage-class-r1/audit.json'
    native=json.loads(nativepath.read_bytes())
    raw=(ROOT/'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho').read_bytes()
    require(hashlib.sha256(raw).hexdigest()==native['kernel_sha256'],'Kernel identity')
    kernel=A.B.macho(raw)['symbols']
    allnames=list(dict.fromkeys(reference+transport+['__ZN14NativeRamBlock4initEv']))
    demangle=subprocess.run(['wsl','-d','Ubuntu-22.04','--','c++filt'],input=('\n'.join(n[1:] for n in allnames)+'\n').encode(),capture_output=True,check=True)
    readable=dict(zip(allnames,demangle.stdout.decode('utf-8').splitlines()))
    require(len(readable)==len(allnames),'Demangler output incomplete')
    matches,overrides=compare(reference,transport,native['methods'],readable)
    negatives=[]
    for name,index,value in [('wrong-signature',21,'__ZN14NativeRamBlock4initEv'),('abstract-slot',170,'___cxa_pure_virtual')]:
        changed=transport.copy();changed[index]=value
        try:compare(reference,changed,native['methods'],readable)
        except ValueError as e:negatives.append(dict(name=name,rejected=True,reason=str(e)))
        else:raise ValueError('Mutation was accepted')
    imports=[s for s in symbols if s['kind']==1]
    absent=[dict(name=s['name'],weak=bool(s['desc']&0x40)) for s in imports if s['name'] not in kernel]
    binding_map={name:row['target'] for name,row in zip(reference,native['methods']) if not row['native_names']}
    binding_map.update({'__ZN20IOBlockStorageDevice10gMetaClassE':native['metaclass'],
        '__ZTV20IOBlockStorageDevice':native['vtable'],
        '__ZN20IOBlockStorageDeviceC2EPK11OSMetaClass':native['protected_constructor']['pc'],
        '__ZN20IOBlockStorageDeviceD2Ev':native['base_destructor']['pc']})
    strong=[r['name'] for r in absent if not r['weak']]
    require(all(n in binding_map for n in strong),'Unexplained strong imports')
    result=dict(native_named_slots_matched=matches,method_count=len(reference),concrete_overrides=overrides,
        original_methods=[dict(slot=i,reference_name=name,target=native['methods'][i]['target']) for i,name in enumerate(reference) if not native['methods'][i]['native_names']],
        unresolved_by_kernel_name=absent,negative_tests=negatives,
        analysis_only_import_map={n:binding_map[n] for n in strong},
        inherited_header_methods_matched=True,complete_abi_qualified=False,deployable=False,
        limitations=['Actual private compiler objects; reference headers still require native slot comparison',
                    'No live metaclass initialization or instance-size observation',
                    'No final link, native import aliases, mount or device execution'],
        evidence=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (nativepath,buildpath,objdir/'IOBlockStorageReference.o',objdir/'NativeRamBlock.o',objdir/'libNativeRamBlock.late.a',Path(__file__))])
    out.mkdir(parents=True);(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'demangler-stderr.bin').write_bytes(demangle.stderr)
    (out/'check-script.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(matches=matches,overrides=overrides,unresolved=absent)))

if __name__=='__main__':main()
