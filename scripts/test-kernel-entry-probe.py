"""Execute the fixed cold-boot instruction path in Unicorn; not a hardware test.

Two modes, both pinned to the real candidate bytes:

  * default model state: the cold path is executed up to the SCTLR write. Unicorn
    starts with SCR_EL3=0/HCR_EL2=0, so arm_el_is_aa64() is false and the page
    walk takes the AArch32 branch (T0SZ & 7), which is why the real T0SZ=26
    tables cannot translate here. This stay is kept as the negative control.
  * AArch64 high-EL state (SCR_EL3.NS|RW, HCR_EL2.RW): the same run continues
    through the MMU switch and reaches the arm_init hook at its KVA. Nothing in
    the kernel, its TCR/tables or the candidate file is changed, and the page
    tables are compared before and after.
"""
import argparse, hashlib, importlib.util, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
PA=0x8c01c8000;FB=0xb8000000;ROW=5760;ARGS=PA+0x10000000
PRESERVED=list(range(9))+list(range(18,31))
FB_DESCRIPTOR=0x006000008000040d
SCR_EL3_AARCH64=(1<<10)|1      # NS | RW
HCR_EL2_RW=1<<31
# Kernel-built bootstrap page tables after the diagnostic slot is installed. Independent
# reviewers reproduced this exact digest for the same candidate and the same AArch64 state.
PINNED_TABLES_SHA256='682cb477a6574e9e107de81570e339336eb60c81a156cf1bb1bdf6eff4d1bfa8'


def snapshot(uc):return {str(i):uc.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}')) for i in PRESERVED}


def run(raw,report,video=True,start=None,fault=False,stub=None,preoccupy=None):
    m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);first=m['symbols']['_start_first_cpu'];uc=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
    uc.mem_map(PA,B.align(end-base));uc.mem_map(ARGS,0x1000);uc.mem_map(FB,0x1200000);uc.mem_map(0x80000000,0x1000)
    for s in m['segments']:
        if s['filesize']:uc.mem_write(PA+s['va']-base,bytes(raw[s['fileoff']:s['fileoff']+s['filesize']]))
    args=bytearray(4096);struct.pack_into('<HH',args,0,2,2);struct.pack_into('<4Q',args,8,base,PA,0x40000000,ARGS+0x10000);struct.pack_into('<6Q',args,0x28,FB if video else 0,1,ROW,1440,3200,32);uc.mem_write(ARGS,bytes(args))
    uc.reg_write(UC_ARM64_REG_X0,ARGS);uc.reg_write(UC_ARM64_REG_X20,ARGS);uc.reg_write(UC_ARM64_REG_PSTATE,0x3c5)
    values=dict(ESR_EL1=0x96000040,ELR_EL1=PA+first+0x2d0-base,FAR_EL1=0x40000040)
    if fault:
        for name,reg in (('ESR_EL1',UC_ARM64_REG_ESR_EL1),('ELR_EL1',UC_ARM64_REG_ELR_EL1),('FAR_EL1',UC_ARM64_REG_FAR_EL1)):uc.reg_write(reg,values[name])
    mmu=PA+first+0x318-base # actual MSR SCTLR_EL1, not the first MOVK
    stop=PA+int(report['probe']['symbols']['fault_stop'],16)-base
    trace=[];bad=[];state={};stub_state={}
    def code(uc,addr,size,_):
        if addr==mmu or (fault and addr==stop):state['stop']='fault-stop' if fault else 'before-sctlr';uc.emu_stop()
        if stub and addr==stub_state.get('replay'):stub_state['reached_replay']=True;uc.emu_stop()
        if addr in (PA+first-base,PA+first+0x22c-base,PA+first+0x2d0-base,mmu):trace.append(hex(addr))
        if stub and addr==stub_state.get('entry'):trace.append('stub:'+stub)
    def invalid(uc,access,addr,size,value,_):bad.append(dict(access=access,address=hex(addr),size=size,pc=hex(uc.reg_read(UC_ARM64_REG_PC))));return False
    uc.hook_add(U.UC_HOOK_CODE,code);uc.hook_add(U.UC_HOOK_MEM_INVALID,invalid)
    if preoccupy is not None:
        # Occupy V=P L1 slot 2 just after the bootstrap tables exist (x25 holds their
        # physical address) and before the magenta hook installs anything.
        tables_site=PA+first+0x22c-base
        def plant(uc,addr,size,_):
            if addr==tables_site:
                table=uc.reg_read(UC_ARM64_REG_X25)
                uc.mem_write(table+16,struct.pack('<Q',preoccupy))
        uc.hook_add(U.UC_HOOK_CODE,plant)
    begin=PA+(start if start is not None else m['entry'])-base
    try:uc.emu_start(begin,0,count=12000000)
    except U.UcError as e:state['error']=str(e)
    state.update(trace=trace,bad_memory=bad,pc=hex(uc.reg_read(UC_ARM64_REG_PC)),boot_args_unchanged=bytes(uc.mem_read(ARGS,4096))==bytes(args))
    table=uc.reg_read(UC_ARM64_REG_X25) if not fault else 0
    table_bytes=bytes(uc.mem_read(table,0x10000)) if not fault and state.get('stop') else None
    if stub and table_bytes:
        symbols=report['probe']['symbols']
        stub_state.update(entry=PA+int(symbols[stub],16)-base,replay=PA+int(symbols[stub+'_replay'],16)-base,
                          before=snapshot(uc),scratch=struct.unpack('<2Q',uc.mem_read(PA+int(symbols['probe_scratch'],16)-base,16)))
        uc.reg_write(UC_ARM64_REG_PC,stub_state['entry'])
        try:uc.emu_start(stub_state['entry'],0,count=200000)
        except U.UcError as e:stub_state['error']=str(e)
        stub_state.update(reached=stub_state.get('reached_replay',False),after=snapshot(uc),
                          pc=hex(uc.reg_read(UC_ARM64_REG_PC)),bad_memory=list(bad))
    registers=snapshot(uc)
    pixels={str(y):struct.unpack('<I',uc.mem_read(FB+y*ROW,4))[0] for y in (256,288,320,352,384,416,448,480,512,544,576,608,640,1056,1088,1120,1152)}
    if fault:
        # Independent glyph sampling from the rendered pixels, not from font bytes.
        font=['11111001100110011111','00100110001000100111','11110001111110001111','11110001111100011111','10011001111100010001','11111000111100011111','11111000111110011111','11110001001001000100','11111001111110011111','11111001111100011111','11111001111110011001','11101001111010011110','11111000100010001111','11101001100110011110','11111000111110001111','11111000111110001000']
        lookup={bits:format(i,'X') for i,bits in enumerate(font)};decoded={}
        for name,y in (('ESR_EL1',1152),('ELR_EL1',1184),('FAR_EL1',1216)):
            text=''
            for digit in range(16):
                bits=''.join('1' if struct.unpack('<I',uc.mem_read(FB+(y+r*4)*ROW+digit*24*4+c*16,4))[0]==0xffffffff else '0' for r in range(5) for c in range(4))
                text+=lookup.get(bits,'?')
            decoded[name]=text
        state['decoded_hex']=decoded;state['expected_hex']={k:f'{v:016X}' for k,v in values.items()}
    tables=None
    if table_bytes is not None:
        masked=bytearray(table_bytes);masked[16:24]=bytes(8)
        tables=dict(sha256=hashlib.sha256(table_bytes).hexdigest(),masked_sha256=hashlib.sha256(bytes(masked)).hexdigest(),
                    slot2=hex(struct.unpack_from('<Q',table_bytes,16)[0]),ttbr0=hex(uc.reg_read(UC_ARM64_REG_TTBR0_EL1)))
    return state,registers,pixels,tables,stub_state


def run_continuous(raw,report,model='aarch64',preoccupy=None):
    """Run the real cold path right through the MMU switch to the arm_init hook.

    model='aarch64' sets the high-EL execution state the kernel actually runs in
    (SCR_EL3.NS|RW and HCR_EL2.RW). model='default' leaves Unicorn's initial
    SCR_EL3=0/HCR_EL2=0 as the negative control.
    """
    m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments']);first=m['symbols']['_start_first_cpu'];uc=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
    uc.mem_map(PA,B.align(end-base)+0x200000);uc.mem_map(ARGS,0x1000);uc.mem_map(FB,0x1200000);uc.mem_map(0x80000000,0x1000)
    for s in m['segments']:
        if s['filesize']:uc.mem_write(PA+s['va']-base,bytes(raw[s['fileoff']:s['fileoff']+s['filesize']]))
    args=bytearray(4096);struct.pack_into('<HH',args,0,2,2);struct.pack_into('<4Q',args,8,base,PA,0x40000000,ARGS+0x10000);struct.pack_into('<6Q',args,0x28,FB,1,ROW,1440,3200,32);uc.mem_write(ARGS,bytes(args))
    uc.reg_write(UC_ARM64_REG_X0,ARGS);uc.reg_write(UC_ARM64_REG_X20,ARGS);uc.reg_write(UC_ARM64_REG_PSTATE,0x3c5)
    if model=='aarch64':
        uc.cpr_write(3,6,1,1,0,SCR_EL3_AARCH64)
        uc.cpr_write(3,4,1,1,0,HCR_EL2_RW)
    stop_va=int(report['probe']['symbols']['probe_arm_init_replay'],16)
    tables_hook=PA+first+0x22c-base
    st={'count':0,'reached':False,'tables_pa':None,'tables_before':None};bad=[]
    def code(uc,addr,size,_):
        st['count']+=1
        if addr==tables_hook:
            st['tables_pa']=uc.reg_read(UC_ARM64_REG_X25)
            st['tables_before']=bytes(uc.mem_read(st['tables_pa'],0x10000))
        if preoccupy is not None and addr==tables_hook:
            uc.mem_write(st['tables_pa']+16,struct.pack('<Q',preoccupy))
        if addr==stop_va:
            st['reached']=True;uc.emu_stop()
    def invalid(uc,access,addr,size,value,_):
        bad.append(dict(access=access,address=hex(addr),size=size,pc=hex(uc.reg_read(UC_ARM64_REG_PC))));return False
    uc.hook_add(U.UC_HOOK_CODE,code);uc.hook_add(U.UC_HOOK_MEM_INVALID,invalid)
    error=None
    try:uc.emu_start(PA+m['entry']-base,0,count=12000000)
    except U.UcError as e:error=str(e)
    after_tables=None
    if st['tables_pa'] is not None:
        after_tables=bytes(uc.mem_read(st['tables_pa'],0x10000))
    def sr(op0,op1,crn,crm,op2):
        try:return hex(uc.cpr_read(op0,op1,crn,crm,op2))
        except Exception:return None
    return {'model':model,'error':error,'reached':st['reached'],'instructions':st['count'],
            'pc':hex(uc.reg_read(UC_ARM64_REG_PC)),'bad_memory':bad,
            'sctlr':sr(3,0,1,0,0),'tcr':sr(3,0,2,0,2),'ttbr0':sr(3,0,2,0,0),'ttbr1':sr(3,0,2,0,1),
            'scr_el3':sr(3,6,1,1,0),'hcr_el2':sr(3,4,1,1,0),
            'mair':sr(3,0,10,2,0),
            'tables_pa':hex(st['tables_pa']) if st['tables_pa'] else None,
            'tables_before_sha256':hashlib.sha256(st['tables_before']).hexdigest() if st['tables_before'] else None,
            'tables_after_sha256':hashlib.sha256(after_tables).hexdigest() if after_tables else None,
            'tables_before_bytes':st['tables_before'],'tables_after_bytes':after_tables,
            'tables_slot2':hex(struct.unpack_from('<Q',after_tables,16)[0]) if after_tables else None,
            'pixels':{str(y):hex(struct.unpack('<I',uc.mem_read(FB+y*ROW,4))[0]) for y in (256,288,320,352,384,416,448,480,512,544,576,608,640,1056,1088,1120,1152)}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();report=json.loads(a.build.read_text());raw=B.INPUT.read_bytes();candidate=(ROOT/report['candidate']['path']).read_bytes();checks=[]
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise AssertionError(name)
    check('Pinned baseline',B.sha(raw)==B.EXPECTED);check('Candidate digest',B.sha(candidate)==report['candidate']['sha256'])
    baseline,_,_,_,_=run(raw,report);check('Baseline reaches BCM-only unmapped write',baseline['bad_memory'][0]['address']=='0x40000040')
    reference=bytearray(raw);bcm=next(p for p in report['patches'] if 'Suppress BCM' in p['reason']);at=bcm['file_offset'];reference[at:at+4]=bytes.fromhex(bcm['after'])
    corrected,regs0,_,tables0,_=run(reference,report);check('Single-store correction reaches MMU enable instruction',corrected.get('stop')=='before-sctlr' and not corrected['bad_memory'])
    check('Minimal corrected kernel installs no framebuffer mapping',tables0['slot2']=='0x0')
    probed,regs1,pixels,tables1,_=run(candidate,report);check('Instrumented kernel reaches MMU enable instruction',probed.get('stop')=='before-sctlr' and not probed['bad_memory']);check('Live registers preserved',regs0==regs1)
    check('Bootstrap tables match minimal corrected kernel outside the added slot',tables0['masked_sha256']==tables1['masked_sha256'])
    check('Diagnostic framebuffer 1 GiB block installed in L1 slot 2',tables1['slot2']==hex(FB_DESCRIPTOR));check('Boot args untouched',probed['boot_args_unchanged'])
    check('Entry blue band',pixels['256']==0xff0080ff);check('Tables yellow band',pixels['288']==0xffffff00);check('Pre-MMU magenta band',pixels['320']==0xffff00ff)
    cyan,_,cyanpixels,_,cyanstub=run(candidate,report,stub='probe_mmu_on')
    check('Post-SCTLR hook executes to its replay point',cyanstub.get('reached') and not cyanstub.get('error') and not cyanstub['bad_memory'])
    check('Geometry snapshot matches boot_args',cyanstub['scratch']==(FB,ROW))
    check('Cyan post-MMU band',cyanpixels['352']==0xff00ffff)
    check('Post-SCTLR hook preserves live registers',cyanstub['before']==cyanstub['after'])
    check('Post-SCTLR hook leaves earlier bands intact',(cyanpixels['256'],cyanpixels['320'])==(0xff0080ff,0xffff00ff))
    white,_,whitepixels,_,whitestub=run(candidate,report,stub='probe_arm_init')
    check('arm_init hook executes to its replay point',whitestub.get('reached') and not whitestub.get('error') and not whitestub['bad_memory'])
    check('White arm_init band',whitepixels['384']==0xffffffff)
    check('arm_init hook preserves live registers',whitestub['before']==whitestub['after'])
    probe_off=report['probe']['file_offset'];probe_va=int(report['probe']['va'],16)
    on_off=probe_off+int(report['probe']['symbols']['probe_mmu_on'],16)-probe_va
    check('Cyan hook replays the original isb before anything is drawn',
          struct.unpack_from('<I',candidate,on_off)[0]==0xd5033fdf)
    sentinel=0x8c3000403
    occ,_,occpixels,occtables,occstub=run(candidate,report,preoccupy=sentinel,stub='probe_mmu_on')
    check('Pre-occupied L1 slot 2 is left untouched',occtables['slot2']==hex(sentinel))
    check('Pre-occupied slot yields no geometry snapshot',occstub.get('scratch')==(0,0))
    cont=run_continuous(candidate,report,'aarch64')
    check('Continuous run crosses the SCTLR write with AArch64 high-EL state',
          cont['error'] is None and cont['reached'] and not cont['bad_memory'])
    check('Continuous run draws cyan and white under real translation',
          (cont['pixels']['352'],cont['pixels']['384'])==('0xff00ffff','0xffffffff'))
    check('Continuous run used the kernel own TCR/TTBR/MAIR/SCTLR values',
          (cont['tcr'],cont['ttbr0'],cont['ttbr1'],cont['mair'],cont['sctlr'])==
          ('0x22a51a251a','0x8c355e000','0x8c355f000','0xc08044f00bb44ff','0x3454593d'))
    km=B.macho(candidate);kbase=min(s['va'] for s in km['segments'] if s['size'])
    negative=run_continuous(candidate,report,'default')
    check('Default SCR/HCR state remains the negative control (stops right after the SCTLR write)',
          bool(negative['error']) and not negative['reached']
          and negative['pc']==hex(PA+km['symbols']['_start_first_cpu']+0x31c-kbase))
    check('Continuous run executes in the AArch64 high-EL state (SCR_EL3=0x431 = NS|RW, HCR_EL2=0x80000000)',
          (cont['scr_el3'],cont['hcr_el2'])==('0x431','0x80000000'))
    check('Continuous run ends exactly at the white replay point',
          cont['pc']==report['probe']['symbols']['probe_arm_init_replay'])
    check('Continuous run reproduces the pinned kernel page-table digest',
          cont['tables_after_sha256']==PINNED_TABLES_SHA256)
    check('Negative control keeps SCR_EL3/HCR_EL2 at the model default',
          (negative['scr_el3'],negative['hcr_el2']) in (('0x0','0x0'),(None,None)))
    check('Continuous run leaves only the diagnostic L1 slot changed',
          cont['tables_slot2']==hex(FB_DESCRIPTOR) and cont['tables_before_sha256']!=cont['tables_after_sha256']
          and cont['tables_before_bytes'] is not None
          and cont['tables_before_bytes'][:16]==cont['tables_after_bytes'][:16]
          and cont['tables_before_bytes'][24:]==cont['tables_after_bytes'][24:])
    occ2=run_continuous(candidate,report,'aarch64',preoccupy=sentinel)
    check('With a pre-occupied slot the continuous run still reaches arm_init and paints nothing',
          occ2['error'] is None and occ2['reached'] and not occ2['bad_memory']
          and (occ2['pixels']['352'],occ2['pixels']['384'])==('0x0','0x0')
          and occ2['tables_slot2']==hex(sentinel))
    null,_,nullpixels,nulltables,_=run(candidate,report,video=False);check('Missing framebuffer still reaches MMU',null.get('stop')=='before-sctlr' and not null['bad_memory']);check('Missing framebuffer writes no bands',all(v==0 for v in nullpixels.values()))
    check('Missing framebuffer still installs the diagnostic mapping only',nulltables['slot2']==hex(FB_DESCRIPTOR))
    novideo,_,novideopixels,_,novideostub=run(candidate,report,video=False,stub='probe_mmu_on')
    check('Post-MMU hook sees an empty snapshot without a framebuffer',novideostub.get('scratch')==(0,0))
    check('Post-MMU hook draws nothing without a snapshot',novideostub.get('reached') and not novideostub['bad_memory'] and all(v==0 for v in novideopixels.values()))
    fault,_,faultpixels,_,_=run(candidate,report,start=B.macho(candidate)['symbols']['_LowExceptionVectorBase']+0x200,fault=True);check('Early vector enters fault logger',fault.get('stop')=='fault-stop' and not fault['bad_memory']);check('Fault red band',faultpixels['1120']==0xffff0000);check('ESR ELR FAR glyphs independently decode',fault['decoded_hex']==fault['expected_hex'])
    result=dict(scope='Unicorn ARM64 instruction execution with sparse RAM/framebuffer model. An AArch64 high-EL model state (SCR_EL3.NS|RW, HCR_EL2.RW) lets the real cold path cross the SCTLR write and reach the arm_init hook; the default state stays as the negative control. No hardware cache/device model and no nuwa execution',unicorn_version=U.__version__,candidate_sha256=B.sha(candidate),checks=checks,baseline=baseline,minimal_corrected=corrected,instrumented=probed,post_sctlr_stub=cyanstub,arm_init_stub=whitestub,continuous={k:v for k,v in cont.items() if not k.endswith('_bytes')},negative_control={k:v for k,v in negative.items() if not k.endswith('_bytes')},pixels={k:hex(v) for k,v in pixels.items()},pixels_after_stubs=dict(post_sctlr={k:hex(v) for k,v in cyanpixels.items()},arm_init={k:hex(v) for k,v in whitepixels.items()},no_video={k:hex(v) for k,v in novideopixels.items()},null={k:hex(v) for k,v in nullpixels.items()}),fault_injection=fault,live_registers_equal=regs0==regs1,bootstrap_tables=tables1,framebuffer_descriptor=hex(FB_DESCRIPTOR))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(checks=len(checks),passed=True,candidate=report['candidate']['sha256'])))
if __name__=='__main__':main()
