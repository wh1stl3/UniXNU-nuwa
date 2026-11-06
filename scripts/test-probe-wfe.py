"""Execute real wfe configuration, parser and init; retain v20 as a negative control."""
import argparse, importlib.util, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('b',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
STACK=0xf00000;FB=0xb8000000

def run(report,command):
    raw=(ROOT/report['candidate']['path']).read_bytes();assert B.sha(raw)==report['candidate']['sha256']
    m=B.macho(raw);syms=m['symbols'];base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments'])
    u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(FB,0x1200000);u.mem_map(STACK,0x10000)
    for s in m['segments']:
        if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
    u.mem_write(int(report['probe']['symbols']['probe_scratch'],16),struct.pack('<QQ',FB,5760))
    u.mem_write(syms['_gPEClockFrequencyInfo']+0x48,struct.pack('<Q',19200000))
    u.mem_write(syms['_PE_state']+0xa0,struct.pack('<Q',syms['_const_boot_args']))
    u.mem_write(syms['_const_boot_args']+0x6c,command.encode()+b'\0')
    trace=[]
    def code(u,a,s,d):
        if a in (STACK,syms['_panic']):u.emu_stop()
        if a in (0xfffffff0073cae30,0xfffffff0073cae7c,0xfffffff0073cadb8):trace.append(dict(pc=hex(a),x0=u.reg_read(UC_ARM64_REG_X0),x8=u.reg_read(UC_ARM64_REG_X8),x9=u.reg_read(UC_ARM64_REG_X9)))
    u.hook_add(U.UC_HOOK_CODE,code);pcs=[]
    for name in ('_wfe_timeout_configure','_wfe_timeout_init'):
        u.reg_write(UC_ARM64_REG_SP,STACK+0x8000);u.reg_write(UC_ARM64_REG_LR,STACK)
        u.emu_start(syms[name],0,count=2000000);pcs.append(u.reg_read(UC_ARM64_REG_PC))
    return dict(eventi=struct.unpack('<I',u.mem_read(syms['_arm64_eventi'],4))[0],pcs=[hex(x) for x in pcs],trace=trace)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--negative-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=json.loads(a.build.read_text());checks=[];cases={}
    for command,expected,eps in [('-v',4,1000000),('-v wfe_events_sec=0',24,1),('-v wfe_events_sec=19200',9,19200),('-v wfe_events_sec=2000000',4,1000000)]:
        result=run(report,command);assert result['eventi']==expected and result['pcs']==['0xf00000']*2,result
        assert result['trace'][1]['x8']==eps and result['trace'][1]['x9']==19200000,result
        assert result['trace'][2]['x8']==expected,result
        cases[command]=result;checks.append(dict(name='configure-init '+command,passed=True))
    negative=run(json.loads(a.negative_build.read_text()),'-v')
    assert negative['eventi']==4 and negative['pcs'][1]=='0xfffffff007938000' and negative['trace'][2]['x8']==0x5f006570,negative
    checks.append(dict(name='v20 negative control reaches panic despite eventi=4',passed=True))
    out=dict(scope='Isolated actual candidate functions, planted 19.2MHz and package command line; not full cold boot or hardware',candidate_sha256=report['candidate']['sha256'],checks=checks,cases=cases,negative=negative)
    a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
