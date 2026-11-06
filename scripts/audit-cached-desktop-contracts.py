"""Read real 20H392 cached framework code; no loading or target mutation."""
import argparse, hashlib, importlib.util, json, struct, subprocess
from pathlib import Path
import capstone as CS
from desktop_cache import CacheSet, need
from payload_cache_slide import parse_v2, rebase_page

R = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core', R/'scripts/audit-desktop-core-services.py')
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def exports(raw, base):
    result = {}; visited = set()
    def uleb(at):
        value = 0
        for shift in range(0, 70, 7):
            need(at < len(raw), 'Truncated ULEB'); byte = raw[at]; at += 1
            value |= (byte & 127) << shift
            if not byte & 128: return value, at
        raise ValueError('Oversized ULEB')
    def walk(at, prefix, active):
        need(at not in active and len(active) < 256 and len(prefix) < 4096, 'Export trie cycle/depth')
        need((at, prefix) not in visited, 'Repeated export edge'); visited.add((at, prefix))
        size, pos = uleb(at); end = pos + size; need(end < len(raw), 'Export terminal bounds')
        if size:
            flags, cursor = uleb(pos)
            if not flags & 8:  # Reexports carry an ordinal, not a code offset.
                offset, cursor = uleb(cursor); need(cursor <= end, 'Export payload bounds')
                if flags & 3 == 0: result[prefix] = base + offset
        children = raw[end]; pos = end + 1
        for _ in range(children):
            stop = raw.index(b'\0', pos); edge = raw[pos:stop].decode(); child, pos = uleb(stop+1)
            walk(child, prefix+edge, active | {at})
    if raw: walk(0, '', set())
    return result

def image(cache, path):
    base = cache.images[path]; head = cache.vmread(base, 32)
    count, size = struct.unpack_from('<II', head, 16); need(size <= 1024*1024, 'Command budget')
    raw = cache.vmread(base, 32+size); pos = 32; segments = []; sections = []; exp = None
    for _ in range(count):
        cmd, length = struct.unpack_from('<II', raw, pos); need(length >= 8 and pos+length <= len(raw), 'Command bounds')
        if cmd == 0x19:
            va, vs, off, fs = struct.unpack_from('<4Q', raw, pos+24); segments.append((va, vs, off, fs))
            ns = struct.unpack_from('<I', raw, pos+64)[0]; need(72+80*ns <= length, 'Section bounds')
            for i in range(ns):
                at = pos+72+80*i; name = raw[at:at+16].split(b'\0')[0].decode()
                addr, n = struct.unpack_from('<QQ', raw, at+32)
                sections.append(dict(name=name, address=addr, size=n))
        elif cmd == 0x80000033: exp = struct.unpack_from('<II', raw, pos+8)
        elif cmd in (0x22, 0x80000022) and exp is None: exp = struct.unpack_from('<II', raw, pos+40)
        pos += length
    need(pos == len(raw), 'Commands extent')
    symbols = {}
    if exp and exp[1]:
        off, n = exp; matches = [s for s in segments if s[2] <= off and off+n <= s[2]+s[3]]
        need(len(matches) == 1, 'Export mapping'); s = matches[0]
        symbols = exports(cache.vmread(s[0]+off-s[2], n), base)
    return dict(path=path, base=base, sections=sections, symbols=symbols, header_sha256=sha(raw))

APIS = {'_xpc_connection_create_mach_service':0, '_bootstrap_look_up':1,
        '_IOServiceMatching':0, '_IOServiceNameMatching':0, '_IOServiceOpen':2,
        '_IOConnectCallMethod':1, '_IOConnectCallScalarMethod':1, '_IOConnectCallStructMethod':1,
        '_open':0, '_openat':1, '_mkdir':0, '_mkdirat':1, '_access':0, '_stat':0}

def trace(cache, info, addresses):
    md = CS.Cs(CS.CS_ARCH_ARM64, CS.CS_MODE_ARM); md.detail = True
    calls = []; unresolved = {}; spans = []; resolved = {}; pages = {}; slide_info = {}
    def pointer(addr):
        page = addr & ~4095
        if page not in pages:
            mapping = next(m for m in cache.mappings if m['address'] <= addr < m['address']+m['size'])
            reader = mapping['reader']; key = (str(reader.path), mapping['address'])
            if key not in slide_info:
                h=reader.read(0,0x200); off,count=struct.unpack_from('<II',h,0x138)
                rows=reader.read(off,count*56)
                row=next(struct.unpack_from('<6Q2I',rows,i*56) for i in range(count) if struct.unpack_from('<Q',rows,i*56)[0]==mapping['address'])
                slide_info[key]=parse_v2(reader.read(row[3],row[4]),mapping['size']) if row[4] else None
            raw=cache.vmread(page,4096); si=slide_info[key]
            pages[page]=rebase_page(raw,(page-mapping['address'])//4096,si,0)[0] if si else raw
        return struct.unpack_from('<Q',pages[page],addr-page)[0]
    def resolve(addr):
        if addr in addresses: return addresses[addr]
        if addr in resolved: return resolved[addr]
        regs={}; names=[]; chain=[]
        try:
            for ins in md.disasm(cache.vmread(addr,12),addr):
                op=ins.operands; chain.append(ins.mnemonic+' '+ins.op_str)
                if ins.mnemonic=='adrp': regs[op[0].reg]=op[1].imm
                elif ins.mnemonic=='add' and op[1].reg in regs and op[2].type==CS.arm64.ARM64_OP_IMM:
                    regs[op[0].reg]=regs[op[1].reg]+(op[2].imm<<op[2].shift.value)
                elif ins.mnemonic=='ldr' and op[1].type==CS.arm64.ARM64_OP_MEM and op[1].mem.base in regs:
                    regs[op[0].reg]=pointer(regs[op[1].mem.base]+op[1].mem.disp)
                elif ins.mnemonic=='br': names=addresses.get(regs.get(op[0].reg),[])
                elif ins.mnemonic=='b': names=addresses.get(op[0].imm,[])
                else: break
        except (ValueError,StopIteration): pass
        resolved[addr]=names
        return names
    def literal(addr):
        if addr is None: return None
        try: raw = cache.vmread(addr, 256).split(b'\0',1)[0]
        except ValueError: return None
        return raw.decode() if raw and all(32 <= v < 127 for v in raw) else None
    for sec in info['sections']:
        if sec['name'] != '__text': continue
        code = cache.vmread(sec['address'], sec['size']); spans.append(dict(**sec, sha256=sha(code)))
        insns = list(md.disasm(code, sec['address']))
        targets = {i.operands[-1].imm for i in insns if i.operands and i.operands[-1].type == CS.arm64.ARM64_OP_IMM and i.group(CS.CS_GRP_JUMP)}
        constants = {}
        for ix, ins in enumerate(insns):
            if ins.address in targets: constants.clear()
            op = ins.operands; pending = {}
            def reg(o): return ins.reg_name(o.reg).replace('w','x',1)
            if ins.mnemonic in ('adr','adrp') and len(op)==2: pending[reg(op[0])] = op[1].imm
            elif ins.mnemonic=='add' and len(op)==3 and op[2].type==CS.arm64.ARM64_OP_IMM and reg(op[1]) in constants:
                pending[reg(op[0])] = constants[reg(op[1])] + (op[2].imm << op[2].shift.value)
            elif ins.mnemonic=='mov' and len(op)==2:
                if op[1].type==CS.arm64.ARM64_OP_IMM: pending[reg(op[0])] = op[1].imm
                elif op[1].type==CS.arm64.ARM64_OP_REG and reg(op[1]) in constants: pending[reg(op[0])] = constants[reg(op[1])]
            if ins.mnemonic in ('bl','b') and op and op[0].type==CS.arm64.ARM64_OP_IMM:
                names = resolve(op[0].imm)
                for name in names:
                    if name not in APIS: continue
                    arg = 'x'+str(APIS[name]); value = constants.get(arg)
                    calls.append(dict(pc=hex(ins.address), api=name, target=hex(op[0].imm), argument=value,
                        literal=literal(value) if name not in ('_IOServiceOpen','_IOConnectCallMethod','_IOConnectCallScalarMethod','_IOConnectCallStructMethod') else None,
                        known_registers={k:hex(v) for k,v in constants.items()},
                        following=[dict(pc=hex(j.address),instruction=j.mnemonic+' '+j.op_str) for j in insns[ix+1:ix+9]],
                        evidence='branch to cached export or decoded ADRP/ADD/BR or rebased ADRP/LDR/BR stub; arguments only within basic block'))
                    if value is None: unresolved[name] = unresolved.get(name,0)+1
            for r in ins.regs_access()[1]: constants.pop(ins.reg_name(r).replace('w','x',1), None)
            constants.update(pending)
            if ins.group(CS.CS_GRP_JUMP) or ins.group(CS.CS_GRP_CALL) or ins.group(CS.CS_GRP_RET): constants.clear()
    return dict(path=info['path'], header_sha256=info['header_sha256'], code_spans=spans, calls=calls, unresolved_argument_counts=unresolved,
        exports={k:hex(v) for k,v in info['symbols'].items()},
        limitation='No Objective-C dispatch, indirect branches, pointer rebasing or interprocedural value propagation; following instructions are evidence, not automatic fatality classification')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    need(a.work.parent==Path('/var/tmp') and not a.work.exists() and not a.output.exists(),'Fresh output/mount')
    priorpath=R/'reports/desktop-readiness/2026-11-02-payload-code-integrity-r1/audit.json'; prior=json.loads(priorpath.read_bytes())
    need(prior['passed'],'Parent qualification'); item=next(v for v in prior['inputs'] if v['component']=='Cryptex1,SystemOS')
    source=Path(item['path']); need(source.stat().st_size==item['after']['bytes'],'Image size drift')
    need(sha(core.C.TOOL.read_bytes())==core.C.TOOL_SHA,'Reader drift')
    a.work.mkdir(); mounted=False; cache=None; result={}; error=None
    try:
        subprocess.run([str(core.C.TOOL),'-o','ro',str(source),str(a.work)],check=True,capture_output=True); mounted=True
        root=a.work/'root' if (a.work/'root').is_dir() else a.work
        cache=CacheSet(root/'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64')
        suffixes=('/BackBoardServices','/FrontBoardServices','/RunningBoardServices','/SpringBoardServices','/IOKit','/IOSurface','/IOMobileFramebuffer','/libxpc.dylib','/libsystem_kernel.dylib','/libsystem_c.dylib','/libsystem_coreservices.dylib')
        selected=[path for path in cache.images if path.endswith(suffixes)]
        infos=[image(cache,path) for path in selected]; addresses={}
        for info in infos:
            for name,addr in info['symbols'].items(): addresses.setdefault(addr,[]).append(name)
        records=[]
        for info in infos:
            if info['path'].endswith(('/libsystem_kernel.dylib','/libsystem_c.dylib','/libxpc.dylib')): continue
            record=trace(cache,info,addresses); records.append(record); print(info['path'],len(record['calls']),'direct API calls',flush=True)
        windows=[]; md=CS.Cs(CS.CS_ARCH_ARM64,CS.CS_MODE_ARM)
        for addr,size in ((0x18dcc7c50,0x180),(0x191518950,0x90),(0x1937a0c10,0x130),(0x18dcbb760,0x160)):
            raw=cache.vmread(addr,size)
            windows.append(dict(address=hex(addr),bytes=raw.hex(),sha256=sha(raw),instructions=[dict(pc=hex(i.address),instruction=i.mnemonic+' '+i.op_str) for i in md.disasm(raw,addr)]))
        result=dict(records=records, code_windows=windows,api_exports={k:[hex(addr) for addr,names in addresses.items() if k in names] for k in APIS},cache_reads=cache.report()['reads'])
    except BaseException as exc: error=dict(type=type(exc).__name__,message=str(exc))
    finally:
        if cache: cache.close()
        if mounted: subprocess.run(['fusermount','-u',str(a.work)],check=True,capture_output=True)
        cleaned=subprocess.run(['mountpoint','-q',str(a.work)],capture_output=True).returncode!=0
    result.update(passed=error is None and cleaned,error=error,mount_cleanup_complete=cleaned,parent_sha256=sha(priorpath.read_bytes()),
        source_image=item,input_binding='Prior full image digest reused; current size, subcache UUIDs and read/code digests checked',script_sha256=sha(Path(__file__).read_bytes()),device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n'); need(result['passed'],str(error))

if __name__=='__main__': main()
