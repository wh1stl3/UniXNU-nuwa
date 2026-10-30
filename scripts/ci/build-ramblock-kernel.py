"""Opt-in real XNU make/link with production late RamBlock and init caller.

Fixed donor addresses are external dependencies, NOT a deployable prelink.
No synthetic class implementation, global undefined allowance or device action.
"""
import argparse, hashlib, json, os, platform, re, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def definitions(arguments):
    result=[]
    for i,arg in enumerate(arguments):
        if arg=='-D':result.append(arguments[i+1])
        elif arg.startswith('-D'):result.append(arg[2:])
    return result

def personality(raw,names,segments):
    def offset(address,length=1):
        va,size,off=next(s for s in segments if s[0]<=address and address+length<=s[0]+s[1])
        return off+address-va
    pointer=struct.unpack_from('<Q',raw,offset(names['_gIOKernelConfigTables']['value'],8))[0]
    start=offset(pointer);end=raw.index(b'\0',start)
    offset(pointer,end-start+1)
    table=raw[start:end].decode()
    matches=[block for block in re.findall(r'\{[^{}]*\}',table) if re.search(r"'IOClass'\s*=\s*NativeRamBlock;",block)]
    if len(matches)!=1:raise ValueError('Missing or duplicate linked RamBlock personality')
    for key,value in [('IOMatchCategory','NativeRamBlock'),('IOProviderClass','IOResources'),('IOResourceMatch','IOBSD')]:
        if not re.search("'"+key+r"'\s*=\s*"+value+';',matches[0]):raise ValueError('Linked personality mismatch: '+key)
    return matches[0]

def vtable(path,classname):
    raw=path.read_bytes()
    if struct.unpack_from('<4I',raw)!=(0xfeedfacf,0x100000c,0,1):raise ValueError('Expected ARM64 object')
    at=32;sections=[];table=None
    for _ in range(struct.unpack_from('<I',raw,16)[0]):
        cmd,n=struct.unpack_from('<II',raw,at)
        if cmd==2:table=struct.unpack_from('<4I',raw,at+8)
        if cmd==0x19:
            for i in range(struct.unpack_from('<I',raw,at+64)[0]):
                sec=at+72+80*i;va,size=struct.unpack_from('<QQ',raw,sec+32);rel,count=struct.unpack_from('<II',raw,sec+56)
                sections.append((va,size,rel,count))
        at+=n
    if table is None:raise ValueError('Missing object symbols')
    off,count,strings,length=table;sy=[]
    for i in range(count):
        ix,kind,sec,desc,value=struct.unpack_from('<IBBHQ',raw,off+16*i)
        name=raw[strings+ix:raw.index(b'\0',strings+ix,strings+length)].decode();sy.append((name,value))
    start=next(v for n,v in sy if n=='__ZTV'+str(len(classname))+classname)
    va,size,rel,count=next(s for s in sections if s[0]<=start<s[0]+s[1]);refs={}
    for i in range(count):
        addr,word=struct.unpack_from('<II',raw,rel+8*i)
        if word>>27&1 and word>>28==0 and word>>25&3==3:refs[va+addr]=sy[word&0xffffff][0]
    methods=[]
    while start+16+8*len(methods) in refs:methods.append(refs[start+16+8*len(methods)])
    return methods

def symbols(raw):
    if struct.unpack_from('<4I',raw)!=(0xfeedfacf,0x100000c,0,2):raise ValueError('Not ARM64 kernel')
    at=32;result={};segments=[]
    for _ in range(struct.unpack_from('<I',raw,16)[0]):
        cmd,n=struct.unpack_from('<II',raw,at)
        if n<8 or at+n>len(raw):raise ValueError('Command bounds')
        if cmd==0x19:
            va,size,off,length=struct.unpack_from('<4Q',raw,at+24);segments.append((va,length,off))
        if cmd==2:
            off,count,strings,length=struct.unpack_from('<4I',raw,at+8)
            for i in range(count):
                index,kind,sec,desc,value=struct.unpack_from('<IBBHQ',raw,off+16*i)
                if index and not kind&0xe0:
                    name=raw[strings+index:raw.index(b'\0',strings+index,strings+length)].decode()
                    result[name]=dict(value=value,kind=kind,desc=desc)
        at+=n
    return result,segments

def link_command(original,work,archives):
    if original[:4]!=['make','-C','.cache/xnu-work','build']:raise ValueError('Unknown make command')
    if [v for v in original if v.startswith('OBJROOT=')]!=['OBJROOT='+str(work/'build/xnu/ios-obj')]:raise ValueError('Wrong output tree')
    if any(v.startswith(('LD_KERNEL_ARCHIVES=','XNU_EXTERNAL_KERNEL_ARCHIVES=')) for v in original):raise ValueError('Unexpected existing archive override')
    if len(archives)!=4 or any(not p.is_relative_to(work/'build') or any(c in str(p) for c in ' ,\n') for p in archives):raise ValueError('Archive paths')
    flags={'KernelConfigTables.cpo_CFLAGS_ADD': ['XNU_NATIVE_RAM_BLOCK=1'],
           'IOKitBSDInit.cpo_CFLAGS_ADD':['XNU_NATIVE_RAM_BLOCK=1','XNU_NATIVE_RAM_BLOCK_LATE_INIT=1'],
           'bsd_init.o_CFLAGS_ADD':['XNU_NATIVE_RAM_BLOCK_LATE_INIT=1']}
    command=list(original)
    for key,defs in flags.items():
        found=[i for i,v in enumerate(command) if v.startswith(key+'=')]
        if len(found)!=1:raise ValueError('Missing or repeated object flags: '+key)
        if any(d.split('=')[0] in command[found[0]] for d in defs):raise ValueError('Existing feature override')
        command[found[0]]+=''.join(' -D'+d for d in defs)
    libs='-L'+str(work/'.cache/fakeroot/usr/local/lib/kernel')+' -lfirehose_kernel'
    libs+=''.join(' -Wl,-force_load,'+str(p) for p in archives)
    return command+['LD_KERNEL_ARCHIVES='+libs,'XNU_EXTERNAL_KERNEL_ARCHIVES='+' '.join(map(str,archives))]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);a=ap.parse_args();work=a.work.resolve()
    if platform.system()!='Darwin' or os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Actual macOS Actions build required')
    if not work.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()):raise ValueError('Temporary build only')
    contract_path=ROOT/'config/ramblock-ios16-link-contract.json';contract=json.loads(contract_path.read_bytes())
    for key in ('abi_report','patch'):
        ref=contract[key]
        if sha(ROOT/ref['path'])!=ref['sha256']:raise ValueError('Contract input drift: '+key)
    if len(contract['bindings'])!=11 or len(contract['allowed_weak'])!=6:raise ValueError('Binding/weak scope drift')
    source=work/'.cache/xnu-work'
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=contract['xnu_commit']:raise ValueError('XNU identity')
    archive_report=json.loads((work/'reports/ramblock-archive/audit.json').read_bytes())
    archive=work/archive_report['archive']
    if not archive_report['passed'] or sha(archive)!=archive_report['archive_sha256']:raise ValueError('Production archive changed')
    if vtable(work/'build/ramblock-archive/NativeRamBlock.o','NativeRamBlock')!=contract['production_vtable']:raise ValueError('Current private driver ABI differs')
    if vtable(work/'build/ramblock-archive/IOBlockStorageReference.o','IOBlockStorageDevice')!=contract['reference_vtable']:raise ValueError('Current private reference ABI differs')
    target=work/'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837';kernel=target/'mach.development.bcm2837.unstripped'
    platform_report=json.loads((work/'reports/platform-link/audit.json').read_bytes())
    if not platform_report['passed'] or sha(kernel)!=platform_report['kernel_sha256']:raise ValueError('Platform kernel changed')
    original=json.loads((work/'reports/kernel-make-command.json').read_bytes())
    out=work/'build/ramblock-link';out.mkdir(exist_ok=False)
    evidence=work/'reports/ramblock-link';evidence.mkdir(exist_ok=False)
    report=dict(passed=False,final_source_link=False,prelinked=False,deployable=False,device_accessed=False,baseline_sha256=sha(kernel),contract_sha256=sha(contract_path),commands=[])
    def run(cmd):
        n=len(report['commands']);report['commands'].append(list(map(str,cmd)))
        r=subprocess.run(cmd,cwd=work,capture_output=True,env=dict(os.environ,KERNEL_SDKROOT=str(work/'.cache/fakeroot'),XNU_AVAILABILITY_PL=str(work/'.cache/fakeroot/usr/local/libexec/availability.pl')))
        (evidence/f'{n}.stdout').write_bytes(r.stdout);(evidence/f'{n}.stderr').write_bytes(r.stderr)
        if r.returncode:raise RuntimeError(f'Command {n} failed: '+r.stderr.decode(errors='replace')[-4000:])
    try:
        before,_=symbols(kernel.read_bytes())
        if any(name in before for name in contract['bindings']):raise ValueError('Original class symbol collision')
        asm=out/'donor-storage-bindings.S'
        asm.write_text(''.join('.globl '+name+'\n.set '+name+', '+value+'\n' for name,value in sorted(contract['bindings'].items())))
        run(['xcrun','--sdk','iphoneos','clang','-target','arm64-apple-ios16.0','-c',str(asm),'-o',str(out/'bindings.o')])
        run(['xcrun','ar','rcs',str(out/'libStorageBindings.a'),str(out/'bindings.o')])
        archives=[work/'build/driver-archives'/('lib'+name+'.a') for name in ('ArmCpu','ArmDTPlatform')]+[archive,out/'libStorageBindings.a']
        for path in archives:
            if not path.is_file():raise ValueError('Missing archive')
        for item in platform_report['archives']:
            if sha(work/item['path'])!=item['sha256']:raise ValueError('Platform archive drift')
        patch=ROOT/contract['patch']['path']
        run(['git','-C',str(source),'apply','--check',str(patch)])
        run(['git','-C',str(source),'apply',str(patch)])
        # Per-file make overrides are not themselves source dependencies.
        # Only invalidate the three caller/personality units in the temporary tree.
        run(['touch']+[str(source/p) for p in ('iokit/KernelConfigTables.cpp','iokit/bsddev/IOKitBSDInit.cpp','bsd/kern/bsd_init.c')])
        command=link_command(original,work,archives);report['make_arguments']=command
        run(command)
        report['compile_records']={}
        for obj,expected in {'KernelConfigTables.cpo':['XNU_NATIVE_RAM_BLOCK=1'],
                             'IOKitBSDInit.cpo':['XNU_NATIVE_RAM_BLOCK=1','XNU_NATIVE_RAM_BLOCK_LATE_INIT=1'],
                             'bsd_init.o':['XNU_NATIVE_RAM_BLOCK_LATE_INIT=1']}.items():
            records=list(target.rglob(obj+'.json'))
            if len(records)!=1:raise ValueError('Ambiguous compiler record: '+obj)
            record=json.loads(records[0].read_text().strip().rstrip(','));defs=definitions(record['arguments'])
            for define in expected:
                if [d for d in defs if d.split('=')[0]==define.split('=')[0]]!=[define]:raise ValueError('Stale/conflicting compiler flag: '+obj+' '+define)
            (evidence/(obj+'.json')).write_bytes(records[0].read_bytes())
            report['compile_records'][obj]={'sha256':sha(records[0]),'expected':expected}
        raw=kernel.read_bytes();names,segments=symbols(raw)
        report['linked_personality']=personality(raw,names,segments)
        undefined=[n for n,v in names.items() if v['kind']&0xe==0]
        if undefined:raise ValueError('Final undefined symbols: '+str(undefined))
        for name,value in contract['bindings'].items():
            if names.get(name,{}).get('value')!=int(value,16):raise ValueError('Final donor binding differs: '+name)
        required=['_native_ramblock_register_late','__GLOBAL__sub_I_NativeRamBlock.cpp','__ZN14NativeRamBlock10gMetaClassE','_native_ram_block_volume_seed','_native_ram_block_ready','_armcpu_registered','_armdt_platform_configured']
        if any(n not in names for n in required):raise ValueError('Final required definition missing')
        def calls(name):
            start=names[name]['value'];end=min(v['value'] for v in names.values() if v['kind']&0xe==0xe and v['value']>start)
            va,length,off=next(s for s in segments if s[0]<=start< s[0]+s[1]);data=raw[off+start-va:off+end-va];outcalls=[]
            for i in range(0,len(data)-3,4):
                word=struct.unpack_from('<I',data,i)[0]
                if word>>26==0x25:
                    imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;outcalls.append(start+i+imm*4)
            return outcalls
        init_calls=calls('_IOKitBSDInit')
        loader='__ZN6OSKext22loadKextWithIdentifierEPKcbbhhP7OSArray'
        wrapper=names['_native_ramblock_register_late']['value']
        if names[loader]['value'] not in init_calls or wrapper not in init_calls or init_calls.index(names[loader]['value'])>=init_calls.index(wrapper):raise ValueError('Storage/late-init call order absent')
        publish=names['__ZN9IOService15publishResourceEPKcP8OSObject']['value']
        if publish not in init_calls or init_calls.index(wrapper)>=init_calls.index(publish):raise ValueError('IOBSD publication precedes registration')
        if names['__GLOBAL__sub_I_NativeRamBlock.cpp']['value'] not in calls('_native_ramblock_register_late'):raise ValueError('Explicit constructor call missing')
        # The late initializer must never also appear in an automatic init table.
        at=32;ctor=names['__GLOBAL__sub_I_NativeRamBlock.cpp']['value']
        for _ in range(struct.unpack_from('<I',raw,16)[0]):
            cmd,n=struct.unpack_from('<II',raw,at)
            if cmd==0x19:
                for i in range(struct.unpack_from('<I',raw,at+64)[0]):
                    sec=at+72+80*i
                    if raw[sec:sec+16].split(b'\0')[0]==b'__mod_init_func':
                        size=struct.unpack_from('<Q',raw,sec+40)[0];off=struct.unpack_from('<I',raw,sec+48)[0]
                        if size%8 or off+size>len(raw):raise ValueError('Initializer table bounds')
                        if ctor in [v[0] for v in struct.iter_unpack('<Q',raw[off:off+size])]:raise ValueError('Duplicate automatic RamBlock initializer')
            at+=n
        if sha(kernel)==report['baseline_sha256']:raise ValueError('Stale kernel output')
        report.update(passed=True,final_source_link=True,kernel_sha256=sha(kernel),kernel_bytes=len(raw),required_symbols={n:hex(names[n]['value']) for n in required},init_direct_calls=[hex(v) for v in init_calls],donor_bindings=contract['bindings'],allowed_weak=contract['allowed_weak'],limitations=['Fixed donor external addresses require final donor prelink verification','No native mount, provider matching, metaclass execution or device proof'])
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        report['script_sha256']=sha(Path(__file__));(evidence/'audit.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
