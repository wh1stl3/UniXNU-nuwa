"""Record the fixed native read entry reached by PROBE29; no device access."""
import argparse,json
from pathlib import Path
import read_dispatch_audit as A

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists() or not a.output.resolve().is_relative_to(A.ROOT/'reports'):raise ValueError('Fresh report required')
 raw,m,provenance=A.audit()
 instructions=[A.record(i) for i in A.disasm(raw,m,A.ENTRY,A.WRITE-A.ENTRY)]
 result=dict(provenance=provenance,observed_entry='0xfffffff0051a5858',observation='reports/xnu-entry-probe-trial/2026-10-26-v37/screen.json',instructions=instructions,device_accessed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 for i in instructions:print(i['pc'],i['bytes'],i['instruction'])
if __name__=='__main__':main()
