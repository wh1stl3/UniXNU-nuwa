"""Concrete Data metadata/consumer plan; no files imported and no device writes."""
import argparse,collections,hashlib,json,posixpath
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(path):
 if path=='/var' or path.startswith('/var/'):path='/private'+path
 return posixpath.normpath(path)
def classify(path):
 if '/com_apple_MobileAsset_CarExperienceAssets/' in path:return 'conditional','CarExperience asset bundle; enable/import only for its consumer, not demonstrated PID1 prerequisite'
 if '/com_apple_MobileAsset_SoundScapesPickerAssets/' in path:return 'conditional','SoundScapes picker resources and media; no demonstrated initial desktop dependency'
 if '/com_apple_MobileAsset_CoreAS/' in path:return 'unknown','CoreAS consumer and failure behavior not traced; do not assume optional or boot-critical'
 if '/db/sysdiagnose/' in path:return 'conditional','Diagnostic service placeholder; no selected startup requirement established'
 if path.endswith('/.GlobalPreferences.plist'):return 'conditional','Source preferences exist; actual CFPreferences default/migration policy must decide import, not blindly overwrite'
 if path.endswith('/.localized'):return 'conditional','Localization marker; no mandatory initial-service consumer established'
 return 'unknown','No verified first consumer or creation/failure contract in current scope'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--services',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 services=read(a.services);assert services['passed']
 previous=R/'reports/desktop-readiness/2026-10-30-core-services-r1/plan.json';prior=read(previous)
 sourcepath=R/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json';source=read(sourcepath)
 specpath=R/'out/linux-data-candidate-20261027-r1/nuwa-data-spec.json';spec=read(specpath)
 expected=next(x['sha256'] for x in prior['parents'] if x['path']==str(specpath.relative_to(R)));assert sha(specpath)==expected
 entries={'/'+e['path']:e for e in source['data_source']['entries']}
 directories={'/private/var':dict(uid=0,gid=0,mode=0o755)}
 for path,uid,gid,mode in spec['directories']:
  key='/private/var/'+path;entry=entries[key];actual=dict(uid=uid,gid=gid,mode=int(mode,8))
  assert actual==dict(uid=entry['uid'],gid=entry['gid'],mode=int(entry['mode'],8));directories[key]=actual
 assert len(directories)==161
 omissions=[]
 for entry in services['data_files']:
  classification,reason=classify('/'+entry['path']);omissions.append(dict(entry,classification=classification,rationale=reason,import_selected=False,
   metadata_status='uid/gid/mode/hash bound; host xattrs do not prove APFS protection class/ACL completeness'))
 assert len(omissions)==36 and {e['path'] for e in omissions}=={e['path'] for e in prior['source_files_absent_from_directory_seed']}
 paths=[]
 def use(path,consumer,evidence,role,creator):
  key=canonical(path)
  if not key.startswith('/private/var/'):return
  parent=key if key in directories else posixpath.dirname(key)
  while parent not in directories and parent!='/':parent=posixpath.dirname(parent)
  paths.append(dict(path=path,canonical=key,consumer=consumer,evidence=evidence,role=role,creator=creator,
   exact_seed_directory=directories.get(key),nearest_seed_parent=parent if parent in directories else None,
   parent_metadata=directories.get(parent),runtime_writable=False,creation_and_error_policy='must bind actual call flags/branch or declared socket lifecycle; presence alone insufficient'))
 for service in prior['services']:
  if service['home']:use(service['home'],service['label'],'fixed passwd lookup + launchd identity','home','Data provisioning, with original identity')
 for ref in services['path_references']:use(ref['path'],ref['label'],'exact original launch plist '+ref['role'],ref['role'],'launchd socket setup' if ref['role']=='Socket.SockPathName' else 'unresolved')
 for binary in services['binaries']:
  for call in binary['constant_calls']:
   if call['literal'].startswith(('/var/','/private/var/')):use(call['literal'],binary['path'],call['pc']+' '+call['api'],'actual file API constant','runtime code; not a file to preseed automatically')
 hardlinks=collections.defaultdict(list)
 for e in entries.values():
  if e['type']=='file':hardlinks[e['source_inode']].append(e['path'])
 helpers=[];contract=read(R/'reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json')
 for edge in services['client_edges']:
  providers=edge['declared_providers'];jobs=[]
  for provider in providers:
   jobs += [j for j in contract['services']['jobs'] if j['id']==provider['job']]
  helpers.append(dict(client=edge['program'],endpoint=edge['literal'],callsite=edge['pc'],providers=jobs,
   acceptance=('client callsite plus provider declaration; conditional execution, helper dependencies and response remain unverified' if providers else 'client callsite exists but no provider in audited main launch config; not proof of absence in every bootstrap domain or a mandatory startup dependency')))
 result=dict(passed=True,parent_bindings={str(x.resolve().relative_to(R)):sha(x) for x in (a.services,previous,sourcepath,specpath)},
  directory_count=len(directories),directories=directories,source_file_reviews=omissions,classification_counts=dict(collections.Counter(e['classification'] for e in omissions)),
  data_consumers=paths,additional_service_dependencies=helpers,hardlink_groups_visible_in_source=[v for v in hardlinks.values() if len(v)>1],
  metadata_gaps=['APFS protection classes/keybag lifecycle','ACL semantics not established by host-reader xattrs','hardlinks must preserve source groups if present; no cross-image inode equivalence',
  'Data role, OS/Data pairing and mount placement must be validated on real provider','initialization policy and parent ownership for framework-generated paths remain to trace'],
  provisioning_contract=['verify approved isolated UFS window, capacity and non-overlap with OS/SystemOS/policy/log extents before any write',
  'use a separately created APFS Data volume with qualified metadata importer; existing directory-only image is not deployment-ready',
  'preserve numeric identities and complete parent chain; do not synthesize keybags, trust DBs, signed assets or protected-store success',
  'classify optional source assets before import; preserve source provenance, no blanket copy of all 36 files',
  'runtime creator owns sockets/transient logs; do not precreate socket files as ordinary files',
  'physical acceptance requires writer/sync/recovery/readback of unique boot id, length and checksum in authorized range; power-loss semantics separate'],
  device_accessed=False,data_image_built=False,deployment_ready=False,script_sha256=sha(Path(__file__)))
 a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS Data review',result['classification_counts'],len(paths),'consumer paths',len(helpers),'helper edges')
if __name__=='__main__':main()
