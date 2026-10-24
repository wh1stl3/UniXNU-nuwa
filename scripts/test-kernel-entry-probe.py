"""Execute the fixed cold-boot instruction path in Unicorn; not a hardware test."""
import argparse, hashlib, importlib.util, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
PA=0x8c01c8000;FB=0xb8000000;ROW=5760;ARGS=PA+0x10000000

def run(raw,report,video=True,start=None,fault=False):
    m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);first=m['symbols']['_start_first_cpu'];uc=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
    uc.mem_map(PA,B.align(end-base));uc.mem_map(ARGS,0x1000);uc.mem_map(FB,0x1200000)
    for s in m['segments']:
        if s['filesize']:uc.mem_write(PA+s['va']-base,bytes(raw[s['fileoff']:s['fileoff']+s['filesize']]))
    args=bytearray(4096);struct.pack_into('<HH',args,0,2,2);struct.pack_into('<4Q',args,8,base,PA,0x40000000,ARGS+0x10000);struct.pack_into('<6Q',args,0x28,FB if video else 0,1,ROW,1440,3200,32);uc.mem_write(ARGS,bytes(args))
    uc.reg_write(UC_ARM64_REG_X0,ARGS);uc.reg_write(UC_ARM64_REG_X20,ARGS);uc.reg_write(UC_ARM64_REG_PSTATE,0x3c5)
    values=dict(ESR_EL1=0x96000040,ELR_EL1=PA+first+0x2d0-base,FAR_EL1=0x40000040)
    if fault:
        for name,reg in (('ESR_EL1',UC_ARM64_REG_ESR_EL1),('ELR_EL1',UC_ARM64_REG_ELR_EL1),('FAR_EL1',UC_ARM64_REG_FAR_EL1)):uc.reg_write(reg,values[name])
    mmu=PA+first+0x318-base # actual MSR SCTLR_EL1, not the first MOVK
    stop=PA+int(report['probe']['symbols']['fault_stop'],16)-base
    trace=[];bad=[];state={}
    def code(uc,addr,size,_):
        if addr==mmu or (fault and addr==stop):state['stop']='fault-stop' if fault else 'before-sctlr';uc.emu_stop()
        if addr in (PA+first-base,PA+first+0x22c-base,PA+first+0x2d0-base,mmu):trace.append(hex(addr))
    def invalid(uc,access,addr,size,value,_):bad.append(dict(access=access,address=hex(addr),size=size,pc=hex(uc.reg_read(UC_ARM64_REG_PC))));return False
    uc.hook_add(U.UC_HOOK_CODE,code);uc.hook_add(U.UC_HOOK_MEM_INVALID,invalid)
    begin=PA+(start if start is not None else m['entry'])-base
    try:uc.emu_start(begin,0,count=2000000)
    except U.UcError as e:state['error']=str(e)
    state.update(trace=trace,bad_memory=bad,pc=hex(uc.reg_read(UC_ARM64_REG_PC)),boot_args_unchanged=bytes(uc.mem_read(ARGS,4096))==bytes(args))
    registers={str(i):uc.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}')) for i in list(range(9))+list(range(18,31))}
    pixels={str(y):struct.unpack('<I',uc.mem_read(FB+y*ROW,4))[0] for y in (256,352,448,544)}
    if fault:
        # Independent glyph sampling from the rendered pixels, not from font bytes.
        font=['11111001100110011111','00100110001000100111','11110001111110001111','11110001111100011111','10011001111100010001','11111000111100011111','11111000111110011111','11110001001001000100','11111001111110011111','11111001111100011111','11111001111110011001','11101001111010011110','11111000100010001111','11101001100110011110','11111000111110001111','11111000111110001000']
        lookup={bits:format(i,'X') for i,bits in enumerate(font)};decoded={}
        for name,y in (('ESR_EL1',608),('ELR_EL1',640),('FAR_EL1',672)):
            text=''
            for digit in range(16):
                bits=''.join('1' if struct.unpack('<I',uc.mem_read(FB+(y+r*4)*ROW+digit*24*4+c*16,4))[0]==0xffffffff else '0' for r in range(5) for c in range(4))
                text+=lookup.get(bits,'?')
            decoded[name]=text
        state['decoded_hex']=decoded;state['expected_hex']={k:f'{v:016X}' for k,v in values.items()}
    table=uc.reg_read(UC_ARM64_REG_X25) if not fault else 0
    table_sha=hashlib.sha256(uc.mem_read(table,0x10000)).hexdigest() if not fault and state.get('stop') else None
    return state,registers,pixels,table_sha

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();report=json.loads(a.build.read_text());raw=B.INPUT.read_bytes();candidate=(ROOT/report['candidate']['path']).read_bytes();checks=[]
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise AssertionError(name)
    check('Pinned baseline',B.sha(raw)==B.EXPECTED);check('Candidate digest',B.sha(candidate)==report['candidate']['sha256'])
    baseline,_,_,_=run(raw,report);check('Baseline reaches BCM-only unmapped write',baseline['bad_memory'][0]['address']=='0x40000040')
    reference=bytearray(raw);bcm=next(p for p in report['patches'] if 'Suppress BCM' in p['reason']);at=bcm['file_offset'];reference[at:at+4]=bytes.fromhex(bcm['after'])
    corrected,regs0,_,tables0=run(reference,report);check('Single-store correction reaches MMU enable instruction',corrected.get('stop')=='before-sctlr' and not corrected['bad_memory'])
    probed,regs1,pixels,tables1=run(candidate,report);check('Instrumented kernel reaches MMU enable instruction',probed.get('stop')=='before-sctlr' and not probed['bad_memory']);check('Live registers preserved',regs0==regs1);check('Bootstrap tables match minimal corrected kernel',tables0==tables1);check('Boot args untouched',probed['boot_args_unchanged'])
    check('Entry blue band',pixels['256']==0xff0080ff);check('Tables yellow band',pixels['352']==0xffffff00);check('Pre-MMU magenta band',pixels['448']==0xffff00ff)
    null,_,nullpixels,_=run(candidate,report,video=False);check('Missing framebuffer still reaches MMU',null.get('stop')=='before-sctlr' and not null['bad_memory']);check('Missing framebuffer writes no bands',all(v==0 for v in nullpixels.values()))
    fault,_,faultpixels,_=run(candidate,report,start=B.macho(candidate)['symbols']['_LowExceptionVectorBase']+0x200,fault=True);check('Early vector enters fault logger',fault.get('stop')=='fault-stop' and not fault['bad_memory']);check('Fault red band',faultpixels['544']==0xffff0000);check('ESR ELR FAR glyphs independently decode',fault['decoded_hex']==fault['expected_hex'])
    result=dict(scope='Unicorn ARM64 instruction execution with sparse RAM/framebuffer model; stops before SCTLR MMU enable, no actual translation/cache/device/interrupt model and no nuwa execution',unicorn_version=U.__version__,candidate_sha256=B.sha(candidate),checks=checks,baseline=baseline,minimal_corrected=corrected,instrumented=probed,pixels={k:hex(v) for k,v in pixels.items()},fault_injection=fault,live_registers_equal=regs0==regs1,bootstrap_table_sha256=tables1)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(checks=len(checks),passed=True,candidate=report['candidate']['sha256'])))
if __name__=='__main__':main()
