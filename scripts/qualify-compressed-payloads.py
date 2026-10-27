"""Bind independent compressed payload checks to original bytes and PROBE40."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--directory',type=Path,required=True);cli.add_argument('--work',type=Path,required=True);args=cli.parse_args()
    folder=args.directory.resolve();work=args.work.resolve();output=folder/'qualification.json'
    require(folder.is_relative_to(ROOT/'reports') and work.is_relative_to(ROOT/'out') and not output.exists(),'Fresh local qualification')
    ap=folder/'audit.json';tp=folder/'tests.json';a=json.loads(ap.read_bytes());t=json.loads(tp.read_bytes())
    require(a['script_sha256']==t['audit_source_sha256']==sha(ROOT/'scripts/audit-compressed-payloads.py'),'Audit source binding')
    require(t['test_source_sha256']==sha(ROOT/'scripts/test-compressed-payloads.py') and len(t['checks'])==19 and all(c['passed'] for c in t['checks']),'Test source or coverage')
    require(len(a['records'])==38 and all(r['compressed'] and r['kind']==4 and r['matches_prior_host_read'] for r in a['records']),'Actual type4 coverage')
    require(sha(ROOT/'out/root-mainline-v29/restore/restore-payload.bin')==a['image_sha256'],'Original image changed')
    require(sha(ROOT/'out/apfs-resource-export-build-r1/nuwa-resource-export')==a['export_binary_sha256'],'Exporter changed')
    require(sha(ROOT/'scripts/apfs-resource-export/main.cpp')==a['export_adapter_sha256'] and sha(ROOT/'scripts/apfs-resource-export/CMakeLists.txt')==a['cmake_sha256'],'Adapter changed')
    source=Path('D:/Code/PortingiOSLegacy/common/sources/apfs-fuse')
    for name,digest in a['source_manifest'].items():require(sha(source/name)==digest,'Upstream read-only source changed: '+name)
    for i,r in enumerate(a['records'],1):
        require(sha(work/'attributes'/f'{i}.decmpfs')==r['header_sha256'] and sha(work/'attributes'/f'{i}.rsrc')==r['resource_sha256'],'Exported original attributes changed')
    closure=ROOT/'reports/userland-closure/2026-10-27-r1/audit.json';require(sha(closure)==a['closure_evidence_sha256'],'Closure changed')
    package_path=ROOT/'reports/xnu-first-entry/entry-probe-40.json';package=json.loads(package_path.read_bytes())
    require(sha(ROOT/package['image_path'])==package['image_sha256'],'PROBE40 changed')
    blocks=[b for r in a['records'] for b in r['blocks']]
    require(len(blocks)==188,'Actual block count')
    log=ROOT/'out/apfs-resource-export-build-r1/build-console.txt'
    failure=ROOT/'reports/compressed-payloads/2026-10-27-r1/audit-console.txt'
    result=dict(files=38,type4_blocks=len(blocks),decoded_bytes=sum(r['expanded_bytes'] for r in a['records']),window_cases=sum(len(r['windows']) for r in a['records']),checks=19,all_decoded_files_match=True,blocks_with_unused_suffix=sum(b['unused_suffix_bytes']>0 for b in blocks),unused_suffix_bytes=sum(b['unused_suffix_bytes'] for b in blocks),code_directory_evidence='reports/userland-closure/2026-10-27-r1/qualification.json',evidence={ap.name:sha(ap),tp.name:sha(tp)},source_files_bound=len(a['source_manifest']),build_log_sha256=sha(log),build_clock_skew_warning='Clock skew detected' in log.read_text(encoding='utf-8-sig'),build_scope='Fresh local build directory; serial target build; warning retained; output independently compared against fixed host-read file digests',prior_failure=dict(path=failure.relative_to(ROOT).as_posix(),sha256=sha(failure),cause='Auditor required no unused suffix after Z_STREAM_END; actual wrapper permits suffix; fixed after comparing read-only Util.cpp decoder semantics',source_at_failure_sha256=sha(ROOT/'out/compressed-payloads-20261027-r1/audit-script-at-failure.py')),package_unchanged=True,package_sha256=sha(package_path),image_sha256=package['image_sha256'],device_accessed=False,kernel_changed=False,release_guard_changed=False,qualification_script_sha256=sha(Path(__file__)),limitations=a['limitations'])
    output.write_bytes(json.dumps(result,indent=2).encode()+b'\n');print(json.dumps({k:result[k] for k in ('files','type4_blocks','decoded_bytes','window_cases','checks','blocks_with_unused_suffix','build_clock_skew_warning','package_unchanged')}))
if __name__=='__main__':main()
