"""Compare active header-read probe execution with restored native instructions.

Same MAC/filesystem API models on both sides. This proves observer transparency
within those explicit boundaries; no real filesystem or MAC policy is executed.
"""
import argparse,hashlib,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('read_fixture',ROOT/'scripts/test-read-boundaries.py');F=importlib.util.module_from_spec(spec);sys.modules[spec.name]=F;spec.loader.exec_module(F)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT/'reports'):raise ValueError('Evidence must stay under reports')
    if a.output.exists():raise ValueError('Fresh evidence destination required')
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert F.B.sha(raw)==b['candidate']['sha256']
    original=F.B.INPUT.read_bytes();assert F.B.sha(original)==F.B.EXPECTED
    # Pin each restored instruction to the actual fixed native input, rather
    # than trusting the report's before-values as the reference oracle.
    m=F.B.macho(original);sites={F.R.FIRST,F.R.FIRST+4}|{pc+off for pc,_,_ in F.R.CALLS for off in (0,4)}
    for pc in sites:
        item=next(x for x in b['patches'] if x.get('va')==hex(pc));assert bytes.fromhex(item['before'])==original[F.B.backed(m,pc):F.B.backed(m,pc)+4]
    checks=[]
    for mode in F.MODES:
        candidate=[];reference=[]
        F.run(raw,b,mode,capture=candidate);F.run(raw,b,mode,reference=True,capture=reference)
        assert len(candidate)==len(reference)
        for i,(actual,expected) in enumerate(zip(candidate,reference)):
            assert actual==expected,(mode,i+1,{k:dict(candidate=actual[k],native=expected[k]) for k in actual if actual[k]!=expected[k]})
        checks.append(dict(name=mode,passed=True,attempts=len(candidate),snapshots=candidate))
    # Deliberately leak a caller register at the active MAC boundary, in memory
    # only. The old x0/SP assertions still pass; the new comparison must reject.
    replay=int(b['probe']['symbols']['probe_dense_7466acc_replay'],16)
    mutation_pc=replay-44;offset=F.B.backed(F.B.macho(raw),mutation_pc)
    assert struct.unpack_from('<I',raw,offset)[0]==0xa9402be9 # ldp x9,x10,[sp]
    mutated=bytearray(raw);struct.pack_into('<I',mutated,offset,0xa9402be8) # x8 instead of x9
    bad=[];native=[]
    F.run(bytes(mutated),b,'mac-pending',capture=bad)
    F.run(raw,b,'mac-pending',reference=True,capture=native)
    different={k:dict(mutated=bad[0][k],native=native[0][k]) for k in bad[0] if bad[0][k]!=native[0][k]}
    assert set(different)=={'registers'},different
    negative=[dict(name='active MAC caller-register leak rejected',passed=True,scope='in-memory negative fixture; delivered kernel file unchanged',mutation_pc=hex(mutation_pc),before='e92b40a9',after='e82b40a9',different=different)]
    out=dict(scope=__doc__,candidate_sha256=b['candidate']['sha256'],build_report_sha256=F.B.sha(a.build.read_bytes()),native_input_sha256=F.B.EXPECTED,fixture_source_sha256=F.B.sha(Path(F.__file__).read_bytes()),observer_source_sha256=F.B.sha((ROOT/'scripts/read_boundary_sites.py').read_bytes()),test_source_sha256=F.B.sha(Path(__file__).read_bytes()),negative_controls=negative,restored_sites=[hex(pc) for pc in sorted(sites)],checks=checks,device_accessed=False,real_mac_policy_executed=False,real_filesystem_body_executed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',newline='\n');print(json.dumps(dict(checks=len(checks),attempt_pairs=sum(c['attempts'] for c in checks),negative_controls=len(negative),passed=True)))
if __name__=='__main__':main()