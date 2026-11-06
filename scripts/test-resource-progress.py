"""CFG controls for bounds, conditional paths, indirect exits and loops."""
import argparse,importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location('resource_progress',Path(__file__).with_name('audit-resource-progress.py'));P=importlib.util.module_from_spec(s);s.loader.exec_module(P)

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();assert not a.output.exists();checks=[]
    def run(words,end=None,limit=2048):
        raw=b''.join(int(v).to_bytes(4,'little') for v in words)
        def decode(pc):
            found=list(P.A.CS.disasm(raw[pc-0x1000:pc-0x1000+4],pc));return found[0] if found else None
        return P.walk(decode,0x1000,end or 0x1000+len(raw),limit=limit)
    r=run([0x54000040,0xd503201f,0xd65f03c0]);assert len(r['instructions'])==3;checks.append('conditional paths both visited')
    r=run([0x14000008,0xd65f03c0]);assert len(r['instructions'])==1 and r['boundaries'][0]['reason']=='edge outside declared window';checks.append('out of window branch bounded')
    r=run([0xd61f0100,0xd65f03c0]);assert len(r['instructions'])==1 and r['boundaries'][0]['reason']=='indirect branch';checks.append('indirect branch remains unresolved')
    r=run([0x14000000]);assert len(r['instructions'])==1 and r['edges'][0]['back_edge'];checks.append('loop terminates static traversal')
    r=run([0x94000008,0xd65f03c0]);assert r['calls'][0]['target']=='0x1020' and len(r['instructions'])==2;checks.append('callee not treated as inlined path')
    try:run([0xd503201f,0xd65f03c0],limit=1)
    except ValueError:pass
    else:raise AssertionError('Budget missing')
    checks.append('instruction budget enforced')
    result=dict(checks=[dict(name=c,passed=True) for c in checks],script_sha256=P.A.B.sha((P.ROOT/'scripts/audit-resource-progress.py').read_bytes()),test_sha256=P.A.B.sha(Path(__file__).read_bytes()),device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(json.dumps(result,indent=2).encode()+b'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
