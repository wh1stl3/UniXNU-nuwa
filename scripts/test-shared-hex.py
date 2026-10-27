"""Pixel/result-cache equivalence and native dispatch preservation, offline only."""
import argparse
import importlib.util
import json
import struct
import sys
import subprocess
from pathlib import Path
import probe_shared_hex as P

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
S=module('shared_single','scripts/test-single-pass-hex.py');T=S.T;B=T.B
F=module('shared_boundary','scripts/test-read-boundaries.py')


def data(path):
    b=json.loads(path.read_bytes());raw=(ROOT/b['candidate']['path']).read_bytes();assert B.sha(raw)==b['candidate']['sha256']
    m=B.macho(raw);sy={k:int(v,16) for k,v in b['probe']['symbols'].items()}
    start,end=sy['probe_dense_746c688'],sy['probe_dense_746c688_replay']
    ins=T.A.disasm(raw,m,start,end-start)
    label='x24, #0x6a0' if b['probe_revision']>=43 else 'x23, #0xa035'
    idx=next(n for n,i in enumerate(ins) if i.mnemonic=='mov' and i.op_str==label)
    entry=next(i.address for i in reversed(ins[:idx]) if i.mnemonic=='adr' and i.op_str.startswith('x15, '))
    stop=next(i.address for i in ins[idx+1:] if i.mnemonic=='adr' and i.op_str.startswith('x9, '))
    return b,raw,m,sy,entry,stop


def render(d,values,video=True):
    b,raw,m,sy,entry,stop=d;u=T.machine(raw,m,b'',0,[],False)
    u.mem_write(sy['probe_scratch'],struct.pack('<QQ',T.FB if video else 0,T.ROW))
    base=T.FB+755*T.ROW;u.mem_write(base,b'\xa5'*(22*T.ROW))
    writes=[];u.hook_add(T.U.UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,d:writes.append((p,n)) if T.FB<=p<T.FB+0x1200000 else None)
    u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    preserved={reg:u.reg_read(reg) for reg in (T.UC_ARM64_REG_X20,T.UC_ARM64_REG_X29,T.UC_ARM64_REG_LR,T.UC_ARM64_REG_SP)}
    out=[]
    for value in values:
        writes.clear();u.reg_write(T.UC_ARM64_REG_X23,value);u.emu_start(entry,0,count=100000)
        assert u.reg_read(T.UC_ARM64_REG_PC)==stop and all(u.reg_read(reg)==v for reg,v in preserved.items())
        assert all(756<=(p-T.FB)//T.ROW<776 and 1024<=(p-T.FB)%T.ROW and (p-T.FB)%T.ROW+n<=2944 for p,n in writes)
        if video:assert T.field(u,0xa035)==value
        out.append((bytes(u.mem_read(base,22*T.ROW)),sum(n for p,n in writes)))
    return out


def reset(d):
    b,raw,m,sy,entry,stop=d;u=T.machine(raw,m,b'',0,[],False)
    u.mem_write(sy['probe_scratch'],struct.pack('<QQ',T.FB,T.ROW))
    u.mem_write(sy['probe_hex_result_cache'],struct.pack('<QQ',(1<<64)-1,1))
    if b['probe_revision']>=48:u.mem_write(sy['probe_hex_delta_cache']+304,struct.pack('<QQ',(1<<64)-1,1))
    u.mem_write(T.FB+756*T.ROW,b'\xa5'*(20*T.ROW))
    stop=m['symbols']['_vn_rdwr'];u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==stop else None)
    u.emu_start(P.PREVIOUS.PREVIOUS.FIRST,0,count=2000000)
    assert u.reg_read(T.UC_ARM64_REG_PC)==stop and T.field(u,0xa035)==(1<<64)-1


def inline_control(b,output):
    """Compile the same observer set with inline HEX, without a bootable image."""
    source_dir=(ROOT/b['candidate']['path']).parent
    source=(source_dir/'probe.S').read_text(encoding='utf-8')
    lines=source.splitlines(True)
    while lines and lines[0].startswith('.equ '):lines.pop(0)
    assert B.sha(''.join(lines).encode())==b['source_sha256']
    start=source.index('.macro HEXROW_VAL y');end=source.index('.endm',start)+len('.endm')
    control=source[:start]+'.macro HEXROW_VAL y\n    HEXROW_STACKLESS \\y\n.endm'+source[end:]
    # Every observation, scope, data object and even the unused shared helper
    # remains present. Only ordinary HEX macro expansion differs.
    work=ROOT/'out'/('hex-inline-control-'+output.parent.name);work.mkdir(exist_ok=False)
    payload=None
    for name,text in (('baseline',source),('inline',control)):
        target=work/name;target.mkdir()
        (target/'probe.S').write_text(text,encoding='utf-8',newline='\n')
        old,new=B.linux(source_dir),B.linux(target)
        rsp=(source_dir/'linker.rsp').read_text().replace(old,new)
        (target/'linker.rsp').write_text(rsp,encoding='utf-8',newline='\n')
        commands=[]
        for item in b['commands']:
            command=[v.replace(old,new) for v in item['argv']]
            result=subprocess.run(command,capture_output=True,text=True,timeout=120)
            commands.append(dict(argv=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
            (target/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8')
            result.check_returncode()
        payload=(target/'probe.bin').read_bytes()
        if name=='baseline':
            candidate=(ROOT/b['candidate']['path']).read_bytes()
            at=b['probe']['file_offset']
            assert payload==candidate[at:at+b['probe']['code_bytes']]
    return dict(scope='same observation set; inline HEX control; shared helper retained in both',
                code_bytes=len(payload),source_sha256=B.sha(control.encode()),code_sha256=B.sha(payload),
                work=work.relative_to(ROOT).as_posix(),bootable_image_created=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    d=data(a.build);b,raw,m,sy,entry,stop=d;assert b['probe_revision'] in (43,44,45,46,47,48,49) and b['shared_hex']==P.plan()
    old=data(ROOT/'reports/kernel-entry-probe/2026-10-26-v42-r2/build.json')
    values=((1<<64)-1,(1<<64)-1,0,0,5,(1<<64)-1)
    actual=render(d,values);reference=render(old,values)
    assert all(x[0]==y[0] for x,y in zip(actual,reference))
    assert [x[1] for x in actual]==([38400,0,30720,0,1920,30720] if b['probe_revision']>=48 else [38400,0,38400,0,38400,38400])
    checks=[dict(name=n,passed=True) for n in ('field-pixels','unchanged-result-no-write','changed-result-redraw')]
    assert render(d,values,False)==render(old,values,False);checks.append(dict(name='no-video',passed=True))
    reset(d);checks.append(dict(name='header-reset',passed=True))
    first=sy['probe_dense_769bf90'];end=sy['probe_dense_769bf90_replay']
    store=next(i for i in T.A.disasm(raw,m,first,end-first) if i.mnemonic=='str' and i.op_str=='xzr, [x12, #8]')
    bad=bytearray(raw);at=B.backed(m,store.address);bad[at:at+4]=bytes.fromhex('1f2003d5')
    rejected=False
    try:reset((b,bytes(bad),m,sy,entry,stop))
    except AssertionError:rejected=True
    assert rejected;checks.append(dict(name='omitted-reset-negative',passed=True))
    comparison=inline_control(b,a.output) if b['probe_revision']>=45 else dict(code_bytes=old[0]['probe']['code_bytes'],scope='revision42 observation set baseline')
    assert b['probe']['code_bytes']<comparison['code_bytes']
    checks.append(dict(name='code-size-reduction',passed=True,old_bytes=comparison['code_bytes'],new_bytes=b['probe']['code_bytes'],comparison=comparison))
    actual_state=[];reference_state=[]
    F.run(raw,b,'dispatch-pending',capture=actual_state)
    F.run(raw,b,'dispatch-pending',reference=True,capture=reference_state)
    assert actual_state==reference_state
    checks.append(dict(name='dispatch-native-equivalence',passed=True))
    out=dict(candidate_sha256=B.sha(raw),source_sha256=P.plan()['source_sha256'],test_sha256=B.sha(Path(__file__).read_bytes()),checks=checks,
             result_sequence=[hex(v) for v in values],framebuffer_bytes=[x[1] for x in actual],reference_bytes=[x[1] for x in reference],
             device_accessed=False,hardware_timing_measured=False,limitations=['Flat model; no IRQ, cache or scanout timing','No native filesystem body execution; not a proven PROBE34 root-cause fix'])
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True,code_bytes=b['probe']['code_bytes'],result_bytes=out['framebuffer_bytes'])))


if __name__=='__main__':main()
