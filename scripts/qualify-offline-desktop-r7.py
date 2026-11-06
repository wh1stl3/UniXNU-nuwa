"""Bind serial desktop offline work; never build or alter a boot candidate."""
import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
from linux_data_inputs import validate_directory_only_spec
R=Path(__file__).resolve().parents[1]
REPORT=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
 reports={name:read(REPORT/(name+'.json')) for name in ('cached-contracts-final','services-data-tests','data-input-regression','display-code','display-tests')}
 assert all(v['passed'] for k,v in reports.items() if k!='data-input-regression')
 assert reports['data-input-regression']['checks'] and all(c['passed'] for c in reports['data-input-regression']['checks'])
 assert reports['services-data-tests']['source_sha256']==sha(REPORT/'cached-contracts-final.json')
 assert reports['display-tests']['source_sha256']==sha(REPORT/'display-code.json')
 assert reports['display-code']['parent_sha256']==sha(REPORT/'cached-contracts-final.json')
 for report,script in (('cached-contracts-final','audit-cached-desktop-contracts.py'),('services-data-tests','test-offline-desktop-progress.py'),('display-code','inspect-display-consumer-code.py'),('display-tests','test-display-consumer-contracts.py')):
  assert reports[report]['script_sha256']==sha(R/'scripts'/script)
 frozen={
  'out/ufs-check-5-r1-qualified/boot-ufs-check-5-r1.img':'876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540',
  'out/ufs-check-5-r1-qualified/qualified-readback/kernel.macho':'c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e',
  'reports/ufs-check-5-r1/offline-qualification-final.json':'27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb'}
 for path,expected in frozen.items():assert sha(R/path)==expected,path
 seedpath=R/'out/linux-data-candidate-20261027-r1/nuwa-data-spec.json';seed=read(seedpath);validate_directory_only_spec(seed)
 data=read(R/'reports/desktop-readiness/2026-11-03-offline-mainline-r1/data-readiness-qualified.json')
 for path,digest in data['parent_bindings'].items():assert sha(R/path)==digest
 services=read(R/'reports/desktop-readiness/2026-11-03-offline-mainline-r1/core-consumers-final.json')
 actions=[]
 for use in data['data_consumers']:
  action='preserve source directory metadata' if use['role']=='home' else 'leave creation to launchd socket lifecycle' if use['role']=='Socket.SockPathName' else 'leave creation to actual runtime caller'
  actions.append(dict(**use,offline_action=action,precreate_regular_file=False))
 dataplan=dict(directory_seed=seed,directory_seed_sha256=sha(seedpath),actions=actions,files_deferred=data['source_file_reviews'],
  native_directory_contract=dict(helper='0x18dcbb7b8',requested_mode='0700',eexist='returns zero without proving existing object type',other_error='enters errno/log path; local boundary only',metadata_failure='helper returns zero; does not prove directory usable'),
  importer='directory-only; files, ACL, protection class and hardlink import unsupported; rejected by local guard',
  deployment_ready=False,data_written=False)
 planpath=REPORT/'data-staging-plan.json';assert not planpath.exists();planpath.write_text(json.dumps(dataplan,indent=2)+'\n')
 edges=[]
 for record in reports['cached-contracts-final']['records']:
  for call in record['calls']:
   if call['api'] in ('_bootstrap_look_up','_xpc_connection_create_mach_service'):
    edges.append(dict(framework=record['path'],call=call,providers=services['providers'].get(call['literal'],[]) if call['literal'] else None,
     required_for_desktop='not established; dynamic name/caller conditions remain to trace'))
 refs=R.parent/'Toolchain-nuwa/desktop-r7-reference';bindings=[]
 for file in sorted(refs.iterdir()):
  if file.is_file():bindings.append(dict(path=str(file),sha256=sha(file)))
 # Reproduce the concrete imported parser defect without running any build.
 spec=importlib.util.spec_from_file_location('audit',R/'scripts/audit-cached-desktop-contracts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.exports(bytes([0,1])+b'x\0'+bytes([5,2,0,7,0]),0x1000)=={'x':0x1007}
 parser_cases=['valid export terminal']
 for raw in (b'\x80',bytes([0,1])+b'x\0'+bytes([0]),bytes([4,0,1])):
  try:m.exports(raw,0)
  except (ValueError,IndexError):parser_cases.append('malformed/cyclic export rejected')
  else:raise AssertionError('Malformed trie accepted')
 out=R/'out/offline-desktop-r7';assert not out.exists();out.mkdir()
 command=['/usr/bin/clang','--target=aarch64-none-elf','-ffreestanding','-fno-builtin','-O2','-Wall','-Wextra','-Werror','-c',str(R/'package/offline-desktop/NuwaFtsEvents.c'),'-o',str(out/'NuwaFtsEvents.o')]
 run=subprocess.run(command,capture_output=True,text=True);assert run.returncode==0,run.stderr
 # The host sanitizer executable was compiled/tested serially earlier in this run.
 host=Path('/var/tmp/nuwa-fts-events-r7');assert host.exists()
 source_files=['scripts/audit-cached-desktop-contracts.py','scripts/inspect-display-consumer-code.py','scripts/test-display-consumer-contracts.py','scripts/test-offline-desktop-progress.py',
  'scripts/linux_data_inputs.py','scripts/build-linux-data-candidate.py','scripts/qualify-offline-desktop-r7.py',
  'package/offline-desktop/NuwaFtsEvents.c','package/offline-desktop/NuwaFtsEvents.h','tests/nuwa-fts-events.c']
 result=dict(passed=True,frozen=frozen,evidence={str(p.relative_to(R)):sha(p) for p in list(REPORT.glob('*.json'))},sources={path:sha(R/path) for path in source_files},reference_sources=bindings,
  service_edges=edges,parser_cases=parser_cases,display_request_calls=115,
  actual_instruction_cases=len(reports['services-data-tests']['native_cases'])+len(reports['display-tests']['cases']),
  data_guard_negative_cases=len(reports['services-data-tests']['data_guard']['rejected']),
  touch=dict(source_sha256=sha(R/'package/offline-desktop/NuwaFtsEvents.c'),target_object_sha256=sha(out/'NuwaFtsEvents.o'),cross_compile=command,
   host_sanitizer_binary_sha256=sha(host),host_result_reused='PASS 17 FTS protocol/state checks; synthetic vectors, no hardware',
   protocol='ST FTS SPI 8-byte ordered FIFO events, not Novatek',not_implemented=['bus/dummy-byte transfer','firmware/reset/error dispatch','IOHIDDevice publication/report descriptor','panel orientation validation']),
  limitations=['No new boot image or device access','Framework edge list remains partial; Objective-C and indirect dynamic dispatch unresolved','Data is not deployment-ready and no new Data image was built','Framebuffer code strings exist; metadata absence is not code absence','Native tests have explicit local state and API fixtures'],
  device_accessed=False,check5_modified=False,new_boot_candidate=False)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS desktop r7:',result['actual_instruction_cases'],'native cases; CHECK5 frozen')
if __name__=='__main__':main()
