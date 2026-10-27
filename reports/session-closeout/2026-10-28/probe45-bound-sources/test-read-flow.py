"""Exact scoped progress records, native replay preservation and negative gates."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_flow_sites as P
import resource_dispatch_checks as DISPATCH_CHECKS
import resource_handler_checks as HANDLER_CHECKS
import resource_chain_checks as CHAIN_CHECKS
import resource_cluster_checks as CLUSTER_CHECKS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flow_deep_model',ROOT/'scripts/test-read-deep.py')
D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
T=D.T;B=D.B;MASK=(1<<64)-1
EXTRA=('inactive-result','null-result','pending-result','foreign-result-frame')
GATES=(P.points()[0]['site'],P.D.DECODE,P.D.DECODE+P.D.DECODE_CALLS[0]+4,P.D.DECODE_RET)
RMODES=('normal','no-video','foreign-thread','foreign-frame','wrong-lr','outer-unpaired','inactive','wrong-target','unpaired','parent-unpaired','resource-inactive','resource-frame','resource-lr','null-result')
def required_names():
    return {hex(p['site'])+':'+mode for p in P.points() for mode in D.MODES}|{hex(site)+':'+mode for site in GATES for mode in EXTRA}|{'missing-active-gate-negative'}|{'resource:'+hex(p['site'])+':'+mode for p in P.RESOURCE.points() for mode in RMODES}|{'resource-parent:'+str(n) for n in range(4)}|DISPATCH_CHECKS.required_names()|HANDLER_CHECKS.required_names()|CHAIN_CHECKS.required_names()|CLUSTER_CHECKS.required_names()

def resource_setup(raw,b,p,mode,parent=2):
    special=('unpaired','parent-unpaired','resource-inactive','resource-frame','resource-lr','null-result','wrong-lr')
    u,m,sy=D.setup(raw,b,P.D.DECODE+0x1bc,'normal' if mode in special else mode)
    cb,decode,resource=(T.STACK+x for x in (0xf000,0xa800,0x9800))
    lr,bit=P.RESOURCE.PARENTS[parent]
    u.mem_write(resource,struct.pack('<QQ',decode,lr))
    u.reg_write(T.UC_ARM64_REG_X29,decode if p['phase'] in ('entry','return') else resource)
    u.reg_write(T.UC_ARM64_REG_LR,lr)
    u.reg_write(T.UC_ARM64_REG_SP,resource+16 if p['phase'] in ('entry','return') else resource-0x70)
    u.reg_write(T.UC_ARM64_REG_X0,0x11223344)
    if mode=='wrong-lr':
        if p['phase'] in ('entry','return'):u.reg_write(T.UC_ARM64_REG_LR,T.STOP)
        else:u.mem_write(resource+8,struct.pack('<Q',T.STOP))
    u.mem_write(sy['probe_deep_state']+40,struct.pack('<Q',0 if mode=='parent-unpaired' else 1<<bit))
    state=[cb,40,0x12340000,0 if mode=='null-result' else 0x12340000,7,9,0,1]
    own=[decode+(16 if mode=='resource-frame' else 0),0 if mode=='unpaired' else 1023,lr+(4 if mode=='resource-lr' else 0),0 if mode=='resource-inactive' else 1]
    u.mem_write(sy['probe_result_state'],struct.pack('<8Q',*state));u.mem_write(sy['probe_resource_state'],struct.pack('<4Q',*own))
    return u,m,sy,state,own

def resource_execute(raw,b,p,mode,original,om,parent=2):
    site=p['site'];ref,_,_,_,_=resource_setup(raw,b,p,mode,parent);at=B.backed(om,site);ref.mem_write(site,original[at:at+4]);stores=[]
    ref.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:stores.append((pos,n)));ref.emu_start(site,0,count=1);expected=D.snapshot(ref)
    u,m,sy,state,own=resource_setup(raw,b,p,mode,parent);writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,pos,n,v,d:writes.append((pos,n)) if T.FB<=pos<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None);u.emu_start(site,0,count=3000000)
    assert D.snapshot(u)==expected,(hex(site),mode,'resource native state')
    for pos,n in stores:assert bytes(u.mem_read(pos,n))==bytes(ref.mem_read(pos,n))
    hit=mode in ('normal','no-video','unpaired') or p['phase']=='entry' and mode in ('resource-inactive','resource-frame','resource-lr')
    if mode=='unpaired' and p['phase']=='continuation':hit=False
    if hit:
        state[4:6]=[site,0x11223344 if p['phase'] in ('continuation','return') else MASK]
        if p['phase']=='entry':own=[T.STACK+0xa800,0,P.RESOURCE.PARENTS[parent][0],1]
        if p['phase']=='call':own[1]|=1<<p['pair']
        if p['phase']=='continuation':own[1]&=~(1<<p['pair'])
        if p['phase']=='return':own[3]=0
    assert list(struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64)))==state,(hex(site),mode,'resource result')
    assert list(struct.unpack('<4Q',u.mem_read(sy['probe_resource_state'],32)))==own,(hex(site),mode,'resource own state')
    for pos,n in writes:
        y,x=divmod(pos-T.FB,T.ROW);assert (980<=y<1000 or 1008<=y<1028) and 1024<=x and x+n<=2944
    assert sum(n for _,n in writes)==(76800 if hit and mode!='no-video' else 0),(hex(site),mode,'resource pixels')
    return dict(name='resource:'+hex(site)+':'+mode,passed=True)

def setup(raw,b,site,mode):
    u,m,sy=D.setup(raw,b,site,'normal' if mode in EXTRA else mode)
    state=[T.STACK+0xf000,40,0x12340000,0x12340000,7,9,0,1]
    if mode=='inactive-result':state[7]=0
    if mode=='null-result':state[3]=0
    if mode=='pending-result':state[3]=MASK
    if mode=='foreign-result-frame':state[0]+=16
    u.mem_write(sy['probe_result_state'],struct.pack('<8Q',*state))
    u.reg_write(T.UC_ARM64_REG_X0,0x11223344)
    return u,m,sy,state

def execute(raw,b,site,mode,original,om):
    ref,_,_,_=setup(raw,b,site,mode);at=B.backed(om,site);ref.mem_write(site,original[at:at+4])
    stores=[];ref.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:stores.append((p,n)))
    ref.emu_start(site,0,count=1);expected=D.snapshot(ref)
    u,m,sy,state=setup(raw,b,site,mode);p=next(p for p in P.points() if p['site']==site)
    hit=mode in ('normal','no-video','unpaired') and not(mode=='unpaired' and p['phase']=='continuation')
    if hit:state[4]=site;state[5]=0x11223344 if p['phase'] in ('continuation','return') else MASK
    writes=[]
    u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)) if T.FB<=p<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==expected['pc'] else None)
    u.emu_start(site,0,count=3000000)
    assert D.snapshot(u)==expected,(hex(site),mode,'native state')
    for pos,n in stores:assert bytes(u.mem_read(pos,n))==bytes(ref.mem_read(pos,n))
    assert list(struct.unpack('<8Q',u.mem_read(sy['probe_result_state'],64)))==state,(hex(site),mode,'record')
    field_bytes=0
    for pos,n in writes:
        y,x=divmod(pos-T.FB,T.ROW)
        if y>=980 and 1024<=x<2944:
            assert 980<=y<1000 or 1008<=y<1028
            assert x+n<=2944;field_bytes+=n
    lit=hit and mode!='no-video'
    assert field_bytes==(76800 if lit else 0),(hex(site),mode,field_bytes)
    if lit:assert T.field(u,0xa03d)==state[4] and T.field(u,0xa03e)==state[5]
    return dict(name=hex(site)+':'+mode,passed=True)

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--build',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();assert not a.output.exists()
    b=json.loads(a.build.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes()
    assert b['probe_revision']==49 and b['read_flow']==P.plan() and B.sha(raw)==b['candidate']['sha256']
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED;om=B.macho(original)
    checks=[execute(raw,b,p['site'],mode,original,om) for p in P.points() for mode in D.MODES]
    checks += [execute(raw,b,site,mode,original,om) for site in GATES for mode in EXTRA]
    checks += [resource_execute(raw,b,p,mode,original,om) for p in P.RESOURCE.points() for mode in RMODES]
    for n in range(4):
        resource_execute(raw,b,P.RESOURCE.points()[0],'normal',original,om,n)
        checks.append(dict(name='resource-parent:'+str(n),passed=True))
    site=GATES[0];m=B.macho(raw);sy={k:int(v,16) for k,v in b['probe']['symbols'].items()}
    start=sy[f'probe_dense_{site&0xffffffff:x}'];end=sy[f'probe_dense_{site&0xffffffff:x}_replay']
    ins=list(T.A.disasm(raw,m,start,end-start));index=next(i for i,v in enumerate(ins[:-2]) if v.mnemonic=='ldr' and v.op_str=='x10, [x9, #0x38]' and ins[i+1].mnemonic=='cbz' and ins[i+2].mnemonic=='ldr' and ins[i+2].op_str=='x10, [x9, #0x18]')
    assert ins[index+1].mnemonic=='cbz'
    bad=bytearray(raw);at=B.backed(m,ins[index+1].address);bad[at:at+4]=bytes.fromhex('1f2003d5');rejected=False
    try:execute(bytes(bad),b,site,'inactive-result',original,om)
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='missing-active-gate-negative',passed=True))
    checks += DISPATCH_CHECKS.run(sys.modules[__name__],raw,b,original,om)
    checks += HANDLER_CHECKS.run(sys.modules[__name__],raw,b,original,om)
    checks += CHAIN_CHECKS.run(sys.modules[__name__],raw,b,original,om)
    checks += CLUSTER_CHECKS.run(sys.modules[__name__],raw,b,original,om)
    assert {c['name'] for c in checks}==required_names()
    a.output.write_bytes(json.dumps(dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),dispatch_checks_sha256=DISPATCH_CHECKS.source_sha256(),handler_checks_sha256=HANDLER_CHECKS.source_sha256(),chain_checks_sha256=CHAIN_CHECKS.source_sha256(),cluster_checks_sha256=CLUSTER_CHECKS.source_sha256(),checks=checks,device_accessed=False,limitations=['Isolated native instruction replay and scoped observer execution; not complete decoding or hardware timing','A03D is observed checkpoint, not sampled stopped PC; A03E is raw x0, not always errno']),indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
