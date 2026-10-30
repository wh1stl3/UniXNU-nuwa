"""Compile the fixed real UFS provider; no personality or hardware activation."""
import json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def class_size(text,name):
    matches=[]
    for die in re.split(r'\n0x[0-9a-f]+:',text):
        if 'DW_TAG_class_type' not in die:continue
        if not re.search(r'DW_AT_name\s+\("'+re.escape(name)+r'"\)',die):continue
        size=re.search(r'DW_AT_byte_size\s+\((0x[0-9a-f]+)\)',die)
        if size:matches.append(int(size[1],16))
    if len(matches)!=1:raise ValueError('Missing/ambiguous production class size: '+name)
    return matches[0]

def build(work,base,llvm,h,late,record,out,reports,report,run):
    source=base/'drivers/NativeUfs'
    pin=json.loads((ROOT/'config/kernel-merged-profile.json').read_bytes())['modules']['drivers/NativeUfs']
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=pin:raise ValueError('UFS revision differs')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():raise ValueError('Dirty UFS source')
    cmd=h.driver_command(record,source/'NativeUfs.cpp',out/'NativeUfs.o',work)
    cmd+=['-I',str(out/'include'),'-include',str(ROOT/'include/nuwa/UfsCompilePrelude.h'),'-DNATIVE_VERIFIED_BLOCK=0']
    run(cmd,record['directory']);h.inspect_object(out/'NativeUfs.o')
    sizes={}
    for name in ('NativeUfs','NativeUfsBlock'):
        index=len(report['commands'])
        run([str(llvm/'llvm-dwarfdump'),'--debug-info','--name='+name,str(out/'NativeUfs.o')])
        sizes[name]=class_size((reports/f'command-{index}.stdout').read_text(),name)
    if not (0x88<=sizes['NativeUfs']<0x10000 and 0x90<=sizes['NativeUfsBlock']<0x10000):raise ValueError('Invalid provider layout')
    assembly=cmd[:];assembly[assembly.index('-c')]='-S';assembly[assembly.index('-o')+1]=str(out/'ufs.s')
    run(assembly,record['directory'])
    init='__GLOBAL__sub_I_NativeUfs.cpp'
    (out/'ufs-explicit.s').write_bytes((out/'ufs.s').read_bytes()+('\n.globl '+init+'\n').encode())
    run([record['arguments'][0],'-target','arm64-apple-ios16.0','-c',str(out/'ufs-explicit.s'),'-o',str(out/'ufs-explicit.o')])
    run([str(llvm/'llvm-objcopy'),'--strip-debug',str(out/'NativeUfs.o'),str(out/'ufs-baseline.o')])
    run([str(llvm/'llvm-objcopy'),'--strip-debug']+['--remove-section='+n for n in sorted(late['REMOVED'])]+[str(out/'ufs-explicit.o'),str(out/'NativeUfs.late.o')])
    baseline=(out/'ufs-baseline.o').read_bytes();removed=set(late['inspect'](baseline)[0])&late['REMOVED']
    if '__DATA,__mod_init_func' not in removed:raise ValueError('Missing original UFS initializer')
    sections,relocs=late['verify'](baseline,(out/'NativeUfs.late.o').read_bytes(),removed,init=init)
    wrapper=out/'NativeUfsLateInit.o'
    cmd=h.driver_command(record,ROOT/'package/NativeUfsLateInit.cpp',wrapper,work)
    cmd+=['-DNUWA_UFS_CLASS_SIZE='+str(sizes['NativeUfs']),'-DNUWA_UFS_BLOCK_CLASS_SIZE='+str(sizes['NativeUfsBlock'])]
    run(cmd,record['directory']);h.inspect_object(wrapper)
    if set(late['inspect'](wrapper.read_bytes())[0])&late['REMOVED']:raise ValueError('Automatic provider wrapper initializer')
    _,symbols=late['inspect']((out/'NativeUfs.late.o').read_bytes())
    expected=json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())['allowed_weak']
    if any(n not in symbols or symbols[n][0]&14!=14 for n in expected):raise ValueError('Real UFS exports missing')
    report['ufs_provider']=dict(source_revision=pin,class_sizes=sizes,retained_sections=sections,retained_relocations=relocs,
        exports=expected,initializer=init,hardware_enabled=False,personality_enabled=False,verified_root_enabled=False)
    for p in [Path(__file__),ROOT/'package/NativeUfsLateInit.cpp',ROOT/'include/nuwa/UfsCompilePrelude.h']:(reports/p.name).write_bytes(p.read_bytes())
    return [out/'NativeUfs.late.o',wrapper]
