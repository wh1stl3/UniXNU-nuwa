"""Qualify a complete donor-specific Libm data pool; keep unknown code rejection."""
import argparse
import json
from pathlib import Path
import struct
from native_prelink_inputs import ROOT,sha,inputs,tools,components

def qualify():
    profile,native,donor,selection=inputs()
    pool=profile['literal_pool'];start=int(pool['start'],0);end=int(pool['end_exclusive'],0)
    with tools() as (parser,original),tools(True) as (_,emitter):
        parent,metadata,modules=components(parser,donor,selection)
        off=parser.backed_offset(parent,start,end-start,len(donor));data=donor[off:off+end-start]
        if sha(data)!=pool['sha256'] or len(data)!=1224:raise ValueError('Full literal identity mismatch')
        module=modules[pool['module']];segment=next(s for s in module['segments'] if s['name']=='__TEXT_EXEC')
        at=parser.backed_offset(parent,segment['va'],segment['filesize'],len(donor));blob=donor[at:at+segment['filesize']]
        if blob.count(data)!=1:raise ValueError('Literal interval not unique within Libm')
        if original.MATH_LITERAL_POOLS!=emitter.MATH_LITERAL_POOLS[1:] or len(emitter.MATH_LITERAL_POOLS)!=len(original.MATH_LITERAL_POOLS)+1:
            raise ValueError('Patch changes more than one fingerprint')
        if donor[off-4:off]!=bytes.fromhex('c0035fd6'):raise ValueError('Pool is not preceded by RET')
        following=parser.backed_offset(parent,end,12,len(donor))
        if donor[following:following+12]!=bytes.fromhex('00000000fd7bbfa9fd030091'):
            raise ValueError('Padding/next function boundary differs')
        # Fixed donor instruction evidence, not assumptions based on absent function symbols.
        expected={
          0xfffffff005b8be68:('e1120010','ADR x1 -> indexed table 0xfffffff005b8c0c4'),
          0xfffffff005b8be6c:('2010008b','ADD x0,x1,x0,LSL4'),
          0xfffffff005b8be70:('0414406d','LDP d4,d5,[x0]'),
          0xfffffff005b8bf5c:('422b005c','LDR d2 -> scalar at 0xfffffff005b8c4c4'),
          0xfffffff005b8bf78:('a12a0010','ADR x1 -> coefficient block 0xfffffff005b8c4cc'),
        }
        evidence=[]
        for address,(word,role) in expected.items():
            index=parser.backed_offset(parent,address,4,len(donor));actual=donor[index:index+4].hex()
            evidence.append(dict(address=hex(address),bytes=actual,role=role))
            if actual!=word:raise ValueError('Data reference instruction changed: '+hex(address)+' '+actual)
        old=json.loads((ROOT/'reports/donor-compat/pc-relative-inventory.json').read_text())
        sites=old['unqualified_sites']
        if len(sites)!=12 or any(not start<=int(s['va'],0)<end for s in sites):raise ValueError('External-site set differs')
        inventory=emitter.instruction_inventory(donor,parent,modules)
        ranges=inventory['known_inline_data']
        if not any(x['module']==pool['module'] and x['va']==start and x['size']==end-start and x['sha256']==pool['sha256'] for x in ranges):raise ValueError('Exact new pool not recognized')
        branch_hits=[]
        for name,image in modules.items():
            for s in image['segments']:
                if s['name']!='__TEXT_EXEC' or not s['filesize']:continue
                begin=parser.backed_offset(parent,s['va'],s['filesize'],len(donor))
                for i in range(0,s['filesize']-3,4):
                    pc=s['va']+i
                    if any(x['module']==name and x['va']<=pc<x['va']+x['size'] for x in ranges):continue
                    word=struct.unpack_from('<I',donor,begin+i)[0]
                    # Direct branch encodings only. ADR/ADRP/literal loads are data references.
                    branch=(word&0x7c000000==0x14000000 or word&0xff000010==0x54000000 or word&0x7e000000 in (0x34000000,0x36000000))
                    target=emitter.pc_relative_target(word,pc)
                    if branch and target and start<=target[0]<end:branch_hits.append(dict(pc=hex(pc),word=hex(word),target=hex(target[0])))
        packed=metadata['_PrelinkLinkKASLROffsets'];count=struct.unpack_from('<I',packed)[0]
        if len(packed)!=4+count*4:raise ValueError('Pointer table size mismatch')
        base=next(s['va'] for s in parent if s['name']=='__PRELINK_TEXT');pointer_hits=[]
        for offset in struct.unpack_from(f'<{count}I',packed,4):
            site=base+offset;pos=parser.backed_offset(parent,site,8,len(donor));target=struct.unpack_from('<Q',donor,pos)[0]
            if start<=target<end:pointer_hits.append(dict(site=hex(site),target=hex(target)))
        if branch_hits or pointer_hits:raise ValueError('Possible code entry/pointer into the data pool')
        return dict(scope='Static complete-pool qualification only; not runtime or full donor ABI',native_sha256=sha(native),donor_sha256=sha(donor),pool=pool,
          boundary=dict(previous_instruction='RET',padding_bytes=4,next_prologue='STP X29,X30; MOV X29,SP'),data_references=evidence,
          layout=dict(scalar_and_coefficients_bytes=112,indexed_table_start='0xfffffff005b8c0c4',indexed_table_entries=64,indexed_entry_bytes=16,indexed_table_bytes=1024,scalar_tail_bytes=8,vector_coefficients_start='0xfffffff005b8c4cc',vector_coefficients_bytes=80),
          external_sites_resolved=len(sites),selected_module_direct_branches_into_pool=branch_hits,relocation_pointer_targets_into_pool=pointer_hits,
          complete_hash_required=True,unknown_external_instruction_policy='unchanged: reject',patched_instruction_inventory=inventory,
          limitations=['No LC_DATA_IN_CODE or function-start command in this module','Direct branch/pointer scans do not prove every indirect control-flow target','No component code bytes rewritten; ABI and actual execution remain unqualified'])

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'reports') or output.exists():raise ValueError('Fresh repository report required')
    report=qualify();output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(pool=report['pool'],external_sites_resolved=report['external_sites_resolved'])))
if __name__=='__main__':main()
