"""Bind current offline input conclusions without changing the PROBE40 package."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--directory',type=Path,required=True);args=cli.parse_args()
    folder=args.directory.resolve();require(folder.is_relative_to(ROOT/'reports'),'Reports path required')
    output=folder/'qualification.json';require(not output.exists(),'Fresh qualification required')
    a=json.loads((folder/'audit.json').read_bytes());t=json.loads((folder/'tests.json').read_bytes())
    require(a['script_sha256']==t['audit_script_sha256']==sha(ROOT/'scripts/audit-userland-closure.py'),'Audit source changed')
    require(t['script_sha256']==sha(ROOT/'scripts/test-userland-closure.py') and len(t['checks'])==11 and all(c['passed'] for c in t['checks']),'Test evidence mismatch')
    require(a['mount_cleaned_up'] and not a['device_accessed'] and not a['userland_executed'] and not a['release_guard_changed'],'Scope mismatch')
    parsed={k:v for k,v in a['files'].items() if v['status']=='parsed'}
    for name,record in parsed.items():
        m=record['macho'];require(m['cpu']=='0x100000c' and m['subtype']=='0x0',f'Architecture: {name}')
        require(m['code_directories'] and all(c['page_integrity']=='matched' for c in m['code_directories']),f'Code pages: {name}')
        require(all(s['vmaddr']%16384==0 and s['vmsize']%16384==0 and s['fileoff']%16384==0 for s in m['segments']),f'16K segment alignment: {name}')
    unresolved=[]
    for name,record in a['files'].items():
        if record['status']=='parsed':continue
        incoming=[e for e in a['edges'] if e['path']==name]
        require(incoming and all(e['weak'] for e in incoming),f'Missing required file: {name}')
        unresolved.append(dict(path=name,all_incoming_weak=True,edges=incoming))
    launch=parsed['/sbin/launchd']['macho'];dyld=parsed['/usr/lib/dyld']['macho']
    require(launch['filetype']==2 and launch['dylinker']=='/usr/lib/dyld' and len(launch['entries'])==1 and launch['entries'][0]['kind']=='LC_MAIN','Launchd loader contract')
    require(dyld['filetype']==7 and len(dyld['entries'])==1 and dyld['entries'][0]['kind']=='LC_UNIXTHREAD' and not dyld['dependencies'],'Dyld entry contract')
    services=[]
    for service in a['services']:
        p=service['properties']
        services.append(dict(path=service['path'],label=p.get('Label'),disabled_declared=p.get('Disabled',False),run_at_load=p.get('RunAtLoad',False),keep_alive=p.get('KeepAlive',False),socket_names=list(p.get('Sockets',{})),mach_services=list(p.get('MachServices',{})),program=service['program'],program_file=service.get('program_file'),approved_for_execution=False))
    source=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
    sources={name:sha(source/name) for name in ('bsd/kern/mach_loader.c','osfmk/mach/arm/_structs.h','osfmk/kern/cs_blobs.h','EXTERNAL_HEADERS/mach-o/loader.h')}
    package_path=ROOT/'reports/xnu-first-entry/entry-probe-40.json';package=json.loads(package_path.read_bytes())
    require(sha(ROOT/package['image_path'])==package['image_sha256'],'Package image changed')
    require(sha(ROOT/'out/root-mainline-v29/restore/restore-payload.bin')==a['image_sha256'],'Root image changed')
    build_path=ROOT/'reports/kernel-entry-probe/2026-10-27-v48/build.json';build=json.loads(build_path.read_bytes())
    require(build['exec_trace']['release_checkpoint']==239 and build['root_mount_diagnostic']['conditional_boundary_only'],'Release guard changed')
    require(sha(ROOT/build['candidate']['path'])==package['kernel_sha256']==build['candidate']['sha256'],'Kernel changed')
    result=dict(parsed_files=len(parsed),dependency_edges=len(a['edges']),code_pages=sum(c['code_slots'] for r in parsed.values() for c in r['macho']['code_directories']),unresolved_weak_dependencies=unresolved,all_required_declared_dependency_files_present=True,all_parsed_code_page_hashes_match=True,all_parsed_architectures_arm64_all=True,segment_alignment_16k=True,initial_user_entry=dict(image='/usr/lib/dyld',unslid_pc=hex(dyld['entries'][0]['pc']),runtime_pc='Requires actual dyld slide; not measured',launchd_lc_main_offset=hex(launch['entries'][0]['file_offset']),source='mach_loader.c load_dylinker assigns myresult->entry_point; LC_MAIN is consumed by dyld'),services=services,release_checkpoint=239,release_approved=False,package_unchanged=True,image_sha256=package['image_sha256'],evidence={p.name:sha(p) for p in (folder/'audit.json',folder/'tests.json',package_path,build_path)},source_sha256=sources,qualification_script_sha256=sha(Path(__file__)),device_accessed=False,limitations=a['limitations']+['No dynamic symbol resolution, binding or initializer execution','Declared weak dependency is not proof that all application uses tolerate absence','Service plist inventory is not complete binary side-effect review'])
    output.write_bytes(json.dumps(result,indent=2).encode()+b'\n');print(json.dumps({k:result[k] for k in ('parsed_files','dependency_edges','code_pages','initial_user_entry','package_unchanged','release_approved')}))
if __name__=='__main__':main()
