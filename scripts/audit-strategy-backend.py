"""Read-only call/import audit of the sealed PROBE59 image; no runtime claims."""
import hashlib, importlib.util, json, struct, sys
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R/'scripts'), str(R/'out/python-tools')]
import capstone

def main():
    output = Path(sys.argv[1])
    if output.exists():
        raise SystemExit('Refusing to overwrite evidence')
    spec = importlib.util.spec_from_file_location('backend_builder', R/'scripts/build-kernel-entry-probe.py')
    B = importlib.util.module_from_spec(spec); sys.modules[spec.name] = B; spec.loader.exec_module(B)
    build = R/'reports/kernel-entry-probe/2026-10-30-probe59-root-progress-r1/build.json'
    j = json.loads(build.read_bytes()); raw = (R/j['candidate']['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == j['candidate']['sha256']
    m = B.macho(raw)
    def get(va, size):
        for s in m['segments']:
            if s['va'] <= va and va+size <= s['va']+s['filesize']:
                off = s['fileoff']+va-s['va']; return raw[off:off+size]
        raise ValueError(hex(va))
    reverse = {}
    for k,v in m['symbols'].items(): reverse.setdefault(v, []).append(k)
    cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    def resolve(va):
        result = dict(target=hex(va), symbols=reverse.get(va, []))
        ins = list(cs.disasm(get(va,12), va))
        if len(ins)==3 and [i.mnemonic for i in ins]==['adrp','ldr','br'] and ins[0].op_str.startswith('x16,') and ins[1].op_str.startswith('x16, [x16') and ins[2].op_str=='x16':
            page = int(ins[0].op_str.split('#')[1],16)
            delta = int(ins[1].op_str.split('#')[1].rstrip(']'),0) if '#' in ins[1].op_str else 0
            slot = page+delta; target = struct.unpack('<Q',get(slot,8))[0]
            result.update(slot=hex(slot), bound_target=hex(target), bound_symbols=reverse.get(target, []))
        return result
    selected = {k:v for k,v in m['symbols'].items() if k.startswith(('_mdev','_spec_strategy','_buf_biodone','_buf_biowait','_buf_strategy','_buf_setfilter'))}
    windows = [('strategy-target-window',0xfffffff005194248,0x600),('internal-5197098-window',0xfffffff005197098,0x90),('internal-5197128-window',0xfffffff005197128,0x200),('filter-5198638-window',0xfffffff005198638,0x198)]
    for name,va in selected.items():
        if any(x in name for x in ('strategy','biodone','biowait','setfilter')):
            end = min((v for v in reverse if v>va),default=va+0x400)
            windows.append((name,va,min(end-va,0x2000)))
    result = []
    for name,va,size in windows:
        instructions=[]; calls=[]
        for i in cs.disasm(get(va,size),va):
            instructions.append(dict(pc=hex(i.address),bytes=i.bytes.hex(),asm=i.mnemonic+' '+i.op_str))
            if i.mnemonic in ('bl','blr'):
                call = dict(pc=hex(i.address),asm=i.mnemonic+' '+i.op_str)
                if i.mnemonic=='bl': call.update(resolve(int(i.op_str.lstrip('#'),16)))
                calls.append(call)
        result.append(dict(name=name,start=hex(va),size=size,calls=calls,instructions=instructions))
    report = dict(kernel_sha256=j['candidate']['sha256'],build_sha256=hashlib.sha256(build.read_bytes()).hexdigest(),scope='Static windows, not established function extents or execution trace',symbols={k:hex(v) for k,v in selected.items()},windows=result,limitations=['No runtime vnode, mount, device or request identity','Static import slots do not establish runtime contents','No same-request completion or hardware proof'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(report=str(output),symbols=report['symbols'],calls=[dict(name=w['name'],calls=w['calls']) for w in result])))

if __name__ == '__main__': main()
