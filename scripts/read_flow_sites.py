"""Revision49: readable progress through existing post-allocation/decode sites."""
import hashlib
from pathlib import Path
import read_result_sites as PREVIOUS
import read_resource_sites as RESOURCE
import resource_dispatch_sites as DISPATCH
import resource_handler_sites as HANDLER
import resource_chain_sites as CHAIN
import resource_cluster_sites as CLUSTER
D=PREVIOUS.PREVIOUS

def points():
    return [dict(p) for p in D.points() if p['kind'] in ('post','decode')]

def plan():
    return dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),points=points(),
                fields={'A03A':'second allocation request retained','A03B':'allocator return retained','A03C':'caller return retained','A03D':'latest scoped post-allocation/decode checkpoint PC, not stopped CPU PC','A03E':'raw x0 at paired continuation or decode RET; F at entry/call/checkpoint'},
                state_bytes=304,new_sites=43+len(CHAIN.points())+len(CLUSTER.points()),resource=RESOURCE.plan(),resource_dispatch=DISPATCH.plan(),resource_handler=HANDLER.plan(),resource_chain=CHAIN.plan(),resource_cluster=CLUSTER.plan(),native_policy_changed=False,
                scope='Existing header/thread/target/frame/parent-call gates plus active second-allocation record, nonzero non-sentinel caller return and matching callback FP')

def observe(site):
    p=next((p for p in points() if p['site']==site),None)
    if p is None:
        s=PREVIOUS.observe(site)+RESOURCE.observe(site)+DISPATCH.observe(site)+HANDLER.observe(site)+CHAIN.observe(site)+CLUSTER.observe(site)
        if site==D.PREVIOUS.DECOMP.PREVIOUS.FIRST:s+=RESOURCE.reset()+DISPATCH.reset()+HANDLER.reset()+CHAIN.reset()+CLUSTER.reset()
        return s
    done=f'.Lflow_done_{site:x}'
    # Run before the original observer consumes the continuation pairing bit.
    scoped=dict(p,id=p['id']+1000)
    s=D.scope(scoped,done)
    if p['pair'] is not None and p['phase']=='continuation':
        s+=f'    ldr x10, [x14, #8]\n    tbz x10, #{p["pair"]}, {done}\n'
    s+='    adr x9, probe_result_state\n    ldr x10, [x9, #56]\n'
    s+=f'    cbz x10, {done}\n    ldr x10, [x9, #24]\n    cbz x10, {done}\n    cmn x10, #1\n    b.eq {done}\n'
    if p['kind']=='decode' and p['phase'] not in ('entry','return'):
        s+='    ldr x12, [x29]\n'
    else:s+='    mov x12, x29\n'
    s+=f'    ldr x10, [x9]\n    cmp x10, x12\n    b.ne {done}\n'
    s+=f'    LOADABS x10, {site:#x}\n    str x10, [x9, #32]\n'
    s+=('    str x0, [x9, #40]\n' if p['phase'] in ('continuation','return') else '    mov x10, #-1\n    str x10, [x9, #40]\n')
    s+=PREVIOUS.draw((32,40))+done+':\n'
    return s+PREVIOUS.observe(site)
