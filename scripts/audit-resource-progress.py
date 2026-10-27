"""Bounded static paths at the ResourceFork boundary; no runtime target claim."""
import argparse,hashlib,json,struct
from pathlib import Path
import read_dispatch_audit as A
ROOT=A.ROOT;MASK=(1<<64)-1

def require(ok,message):
    if not ok:raise ValueError(message)

def walk(decode,start,end,resolve=lambda x:dict(target=hex(x)),limit=2048):
    require(start%4==0 and end>start and end%4==0,'Invalid code window')
    todo=[start];seen={};edges=[];calls=[];boundaries=[]
    while todo:
        pc=todo.pop()
        if pc in seen:continue
        if not start<=pc<end:
            boundaries.append(dict(pc=hex(pc),reason='outside declared window'));continue
        require(len(seen)<limit,'Instruction budget exhausted')
        ins=decode(pc)
        if ins is None:
            boundaries.append(dict(pc=hex(pc),reason='undecodable'));continue
        require(ins.size==4,'Non-ARM64 instruction width')
        seen[pc]=dict(pc=hex(pc),bytes=bytes(ins.bytes).hex(),instruction=ins.mnemonic+' '+ins.op_str)
        name=ins.mnemonic;nextpc=pc+4;targets=[]
        if name in ('ret','retab','retaa','eret','brk','hlt','udf'):continue
        if name in ('br','braa','brab'):
            boundaries.append(dict(pc=hex(pc),reason='indirect branch',instruction=ins.op_str));continue
        if name=='bl':
            target=ins.operands[0].imm&MASK;calls.append(dict(pc=hex(pc),kind='call',**resolve(target)));targets=[nextpc]
        elif name in ('blr','blraa','blrab'):
            calls.append(dict(pc=hex(pc),kind='indirect call',register=ins.op_str));targets=[nextpc]
        elif name=='b':targets=[ins.operands[0].imm&MASK]
        elif name.startswith('b.') or name in ('cbz','cbnz','tbz','tbnz'):targets=[ins.operands[-1].imm&MASK,nextpc]
        else:targets=[nextpc]
        for target in targets:
            edges.append(dict(source=hex(pc),target=hex(target),back_edge=target<=pc))
            if start<=target<end:todo.append(target)
            else:boundaries.append(dict(pc=hex(pc),target=hex(target),reason='edge outside declared window'))
    return dict(start=hex(start),end=hex(end),instructions=[seen[x] for x in sorted(seen)],calls=calls,edges=edges,boundaries=boundaries,scope='Conservative reachability in declared window; callees not traversed, indirect edges unresolved, not complete function or runtime trace')

def audit():
    raw,m,origin=A.audit();sy=m['symbols'];reverse={v:k for k,v in sy.items()}
    def decode(pc):
        try:ins=A.disasm(raw,m,pc,4)
        except (StopIteration,ValueError):return None
        return ins[0] if ins else None
    def resolve(target):
        stub=A.stub(raw,m,target);dest=stub['target'] if stub else target
        return dict(direct_target=hex(target),target=hex(dest),name=reverse.get(dest))
    graphs=[]
    for name in ('_uio_create','_uio_addiov','_VNOP_GETXATTR','_vfs_op_init'):
        start=sy[name];end=min(v for v in sy.values() if v>start)
        end=min(end,start+0x4000)
        graphs.append(dict(name=name,**walk(decode,start,end,resolve)))
    graphs.append(dict(name='APFS getxattr static candidate',runtime_target_known=False,**walk(decode,0xfffffff00519cb28,0xfffffff00519db28,resolve)))
    table=sy['_vfs_op_descs'];desc=sy['_vnop_getxattr_desc'];entries=[]
    for i in range(256):
        address=struct.unpack_from('<Q',raw,A.B.backed(m,table+i*8,8))[0]
        if address==0:break
        entries.append(dict(index=i,address=hex(address),name=reverse.get(address)))
    else:raise ValueError('VFS descriptor table missing terminator')
    matches=[e for e in entries if int(e['address'],16)==desc];require(len(matches)==1,'getxattr descriptor membership differs')
    flags=struct.unpack_from('<I',raw,A.B.backed(m,desc+16,4))[0]
    nameptr=struct.unpack_from('<Q',raw,A.B.backed(m,desc+8,8))[0];at=A.B.backed(m,nameptr,64)
    require(raw[at:at+64].split(b'\0')[0]==b'vnop_getxattr','Descriptor name differs')
    sources=[]
    for rel in ('bsd/kern/kern_subr.c','bsd/vfs/kpi_vfs.c','bsd/vfs/vfs_init.c','bsd/vfs/vnode_if.c'):
        p=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')/rel;sources.append(dict(path=str(p),sha256=A.B.sha(p.read_bytes())))
    return dict(input_sha256=A.B.sha(raw),script_sha256=A.B.sha(Path(__file__).read_bytes()),apfs_executable_sha256=origin['apfs_executable_sha256'],graphs=graphs,
                descriptor=dict(address=hex(desc),table=hex(table),table_entries=len(entries),membership=matches[0],flags=hex(flags),disk_offset=struct.unpack_from('<I',raw,A.B.backed(m,desc,4))[0],runtime_index_known=False),
                local_source_references=sources,device_accessed=False,kernel_modified=False,
                limitations=['Static APFS candidate is not captured live v_op target','No lock state, scheduler/timer health, successful allocation or actual filesystem IO inferred','Descriptor table membership does not prove runtime initialization completed'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();dest=a.output.resolve()
    require(dest.is_relative_to(ROOT/'reports') and not dest.exists(),'Fresh reports output required')
    report=audit();dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print(json.dumps(dict(descriptor=report['descriptor'],graphs=[dict(name=g['name'],instructions=len(g['instructions']),calls=g['calls'],boundaries=g['boundaries'][:5]) for g in report['graphs']])))

if __name__=='__main__':main()
