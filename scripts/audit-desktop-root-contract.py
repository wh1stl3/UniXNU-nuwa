"""Read-only root geometry, declared services, identities and Data path survey.

Emits a non-deployable assembly contract. Does not create a Data seed, write a
root image, change jobs/policy, execute image programs or contact a device.
"""
import argparse, importlib.util, json, os, plistlib, posixpath, subprocess
from pathlib import Path
import desktop_root_contract as D
from desktop_namespace import Namespace
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_system', ROOT/'scripts/audit-desktop-system.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A); C = A.A.C


def inspect_path(ns, path):
    if not path.startswith('/'):
        return dict(path=path, status='context_required')
    candidate = path; suffix = []
    while True:
        try:
            record = ns.resolve(candidate)
        except FileNotFoundError:
            parent, name = posixpath.split(candidate.rstrip('/'))
            D.need(name and parent != candidate, 'No existing namespace ancestor')
            suffix.insert(0, name); candidate = parent or '/'
        else:
            canonical = posixpath.join(record['canonical'], *suffix)
            return dict(path=path, status='missing' if suffix else 'present', canonical=canonical,
                        existing_ancestor=record, missing_components=suffix,
                        desired_metadata=None if suffix else {k:record[k] for k in ('mode','uid','gid')},
                        data_path=canonical == '/private/var' or canonical.startswith('/private/var/'))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--mount', type=Path, required=True); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    mount = a.mount.resolve(); output = a.output.resolve()
    D.need(os.name != 'nt' and mount.parent == Path('/var/tmp') and not mount.exists(), 'Fresh WSL mount required')
    D.need(output.is_relative_to(ROOT/'reports') and not output.exists(), 'Fresh report required')
    D.need(C.sha(C.TOOL.read_bytes()) == C.TOOL_SHA, 'APFS reader changed')
    prior_path = ROOT/'reports/desktop-readiness/2026-10-27-system-r1/audit.json'; prior_raw = prior_path.read_bytes(); prior = json.loads(prior_raw)
    cache_path = ROOT/'reports/desktop-readiness/2026-10-27-cache-r1/audit-r3.json'; cache_raw = cache_path.read_bytes(); cache = json.loads(cache_raw)
    qualification_path = ROOT/'reports/desktop-readiness/2026-10-27-cache-r1/qualification.json'; qualification_raw = qualification_path.read_bytes(); qualification = json.loads(qualification_raw)
    expected = next(e['sha256'] for e in qualification['evidence'] if e['path'].endswith('/audit-r3.json'))
    D.need(C.sha(cache_raw) == expected and cache['error'] is None, 'Cache evidence binding differs')
    cache_paths = {i['path'] for i in cache['cache']['images']}; inputs = []; commands = []; mounted = False; error = None; result = {}
    def run(argv):
        child = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=120)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=child.returncode,stdout=child.stdout,stderr=child.stderr)); child.check_returncode()
    try:
        for record in prior['images']:
            path = Path(record['path']); before = A.digests(path)
            D.need(all(before[k] == record[k] for k in ('sha256','sha384','bytes')), 'Fixed component differs')
            inputs.append(dict(component=record['component'],path=str(path),before=before,geometry=D.geometry(path)))
            print(json.dumps(dict(component=record['component'],geometry=inputs[-1]['geometry'])),flush=True)
        required = [dict(name='OS' if item['component']=='OS' else 'SystemOS',component=item['component'],raw_bytes=item['geometry']['raw_bytes']) for item in inputs if item['component'] in ('OS','Cryptex1,SystemOS')]
        preview = D.windows(required)
        for window in preview['windows']:
            source = next(i for i in inputs if i['component'] == window['source_component'])
            if source['geometry']['format'] == 'raw_disk_without_koly':
                window['decoded_sha256'] = source['before']['sha256']
        result['root_window_preview'] = preview
        result['appos_geometry'] = next(i['geometry'] for i in inputs if i['component']=='Cryptex1,AppOS')
        mount.mkdir(); run([C.TOOL,'-o','ro',inputs[0]['path'],mount]); mounted = True; run(['mountpoint','-q',mount])
        root = mount/'root' if (mount/'root').is_dir() else mount; ns = Namespace([dict(prefix='/',component='OS',root=root)])
        main_path = ns.resolve('/System/Library/xpc/launchd.plist'); config_raw = Path(main_path['physical']).read_bytes()
        D.need(len(config_raw) <= 8*1024*1024 and C.sha(config_raw) == prior['images'][0]['inventory']['main_launch_config']['sha256'], 'Launch config differs')
        services = D.contract(plistlib.loads(config_raw)); users = {}; groups = {}; identity_sources = []
        for path, group in (('/etc/passwd',False),('/etc/group',True)):
            try:
                record = ns.resolve(path)
            except FileNotFoundError:
                identity_sources.append(dict(path=path,present=False)); continue
            raw = Path(record['physical']).read_bytes(); D.need(len(raw) < 4*1024*1024, 'Identity input too large')
            parsed = D.identities(raw.decode('utf-8'),group=group)
            identity_sources.append(dict(path=path,present=True,sha256=C.sha(raw),canonical=record['canonical'],rejected_lines=parsed['rejected_lines']))
            if group:
                groups = parsed['records']
            else:
                users = parsed['records']
        selected_labels = {'com.apple.SpringBoard','com.apple.backboardd','com.apple.runningboardd','com.apple.logd','com.apple.notifyd','com.apple.cfprefsd.xpc.daemon','com.apple.containermanagerd','com.apple.lsd','com.apple.securityd','com.apple.trustd','com.apple.amfid'}
        labels = {j['label'] for j in services['jobs']}; selected = []
        for job in services['jobs']:
            program = job['program']
            job['program_path'] = inspect_path(ns,program) if isinstance(program,str) else dict(status='unspecified_or_bundle_program')
            job['cache_member'] = program in cache_paths if isinstance(program,str) else False
            username = job['declared'].get('UserName'); groupname = job['declared'].get('GroupName')
            job['user_lookup'] = dict(declared=username,record=users.get(username),status='declared_in_passwd' if username in users else 'unresolved' if username else 'launchd_default_unspecified')
            job['group_lookup'] = dict(declared=groupname,record=groups.get(groupname),status='declared_in_group' if groupname in groups else 'unresolved' if groupname else 'launchd_default_unspecified')
            if job['label'] in selected_labels:
                selected.append(job)
        for condition in services['explicit_job_conditions']:
            condition['other_label_declared'] = condition['other_label'] in labels
        path_records = []
        for ref in services['path_references']:
            # Socket/output files are created by runtime owners; inspect the parent.
            path = posixpath.dirname(ref['path']) if ref['role'] in ('Socket.SockPathName','StandardOutPath','StandardErrorPath') else ref['path']
            path_records.append(dict(**ref,inspection=inspect_path(ns,path),requires_creation_policy=ref['role'] in ('Socket.SockPathName','StandardOutPath','StandardErrorPath')))
        candidates = ['/private/var','/private/var/run','/private/var/tmp','/private/var/log','/private/var/db','/private/var/root','/private/var/mobile','/private/var/mobile/Library','/private/var/mobile/Library/Preferences','/private/var/containers','/private/var/mobile/Containers','/private/var/preferences','/private/var/keybags']
        for job in selected:
            user = job['user_lookup']['record']
            if user and user['home'].startswith('/'):
                candidates.append(user['home'])
        data = [inspect_path(ns,path) for path in sorted(set(candidates))]
        result.update(main_launch_config=dict(path=main_path['path'],sha256=C.sha(config_raw)),services=services,
                      selected_services=selected,selected_labels_not_found=sorted(selected_labels-labels),
                      identities=dict(sources=identity_sources,users=users,groups=groups,scope='Static flat-file identities; not a running directory-service lookup'),
                      declared_path_inspections=path_records,
                      data_contract=dict(candidate_paths=data,seed_input=None,seed_created=False,persistence_enabled=False,
                                         missing_metadata_policy='No inherited UID/GID/mode guessed for missing paths',
                                         scope='OS placeholders and declarations, not a Data seed inventory or complete write-set',
                                         pending=['Qualified iOS16 Data seed and its APFS metadata/protection','Driver/ADT ownership and sparse/dense seed ABI','Explicit volatile/persistent policy and target allocation','Runtime-created directories, database contents, IPC and device consumers']))
        print(json.dumps(dict(jobs=len(services['jobs']),mach_services=len(services['providers']),declared_paths=len(path_records),selected=len(selected),data_candidates=len(data))),flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mounted:
            run(['fusermount','-u',mount])
        D.need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode != 0,'Mount remains active')
        for item in inputs:
            item['after'] = A.digests(Path(item['path'])); D.need(item['after'] == item['before'],'Source image changed')
    result.update(inputs=inputs,commands=commands,error=error,mount_cleanup_complete=True,
                  sources=[dict(path='scripts/'+name,sha256=C.sha((ROOT/'scripts'/name).read_bytes())) for name in ('desktop_root_contract.py','audit-desktop-root-contract.py','desktop_namespace.py','audit-desktop-system.py','audit-desktop-root.py','audit-userland-closure.py')],
                  parents=[dict(path=str(path.relative_to(ROOT)),sha256=C.sha(raw)) for path,raw in ((prior_path,prior_raw),(cache_path,cache_raw),(qualification_path,qualification_raw))],
                  device_accessed=False,root_assembled=False,jobs_enabled=False,release_guard_changed=False)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    D.need(error is None,'Audit failed: '+str(error))


if __name__ == '__main__':
    main()
