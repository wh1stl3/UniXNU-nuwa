"""Source-bound host import and fail-closed metadata checks, no device writes."""
import argparse,copy,hashlib,json,stat
from pathlib import Path
from data_stage_import import prepare,import_stage
R=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 source=R/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json';d=json.loads(source.read_bytes());archive=R/'out/desktop-root-contract-20261027-r2/os-var-source.tar'
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==d['data_source']['archive_sha256']
 selected=['private/var/mobile/Library/Preferences/.GlobalPreferences.plist'];records=d['data_source']['entries'];cases=[]
 for name,mutate in [('content',lambda x:x.update(sha256='0'*64)),('acl',lambda x:x.update(xattrs=[dict(name='com.apple.system.Security')])),('unknown_metadata',lambda x:x.update(xattr_query='reader_not_supported')),('mode',lambda x:x.update(mode='0o777')),('special',lambda x:x.update(type='symlink'))]:
  bad=copy.deepcopy(records);mutate(next(r for r in bad if r['path']==selected[0]))
  try:prepare(archive,bad,selected)
  except ValueError:cases.append(name)
  else:raise AssertionError(name)
 result=import_stage(archive,records,selected,a.destination)
 path=a.destination/selected[0];r=next(r for r in records if r['path']==selected[0]);st=path.stat()
 assert st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns']
 try:import_stage(archive,records,selected,a.destination)
 except ValueError:cases.append('existing destination refused')
 else:raise AssertionError('overwrite allowed')
 result.update(passed=True,negative_cases=cases,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
  module_sha256=hashlib.sha256((R/'scripts/data_stage_import.py').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  selection_purpose='One conditional source preference file exercises importer; not selected for deployment or activation',device_accessed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',result['directories'],'directories, source file import/readback,',len(cases),'negative cases')
if __name__=='__main__':main()
