"""Create a local OS-var source bundle and non-deployable root/Data contract."""
import argparse, importlib.util, json, os, plistlib, subprocess
from pathlib import Path
import desktop_data_source as E
import desktop_root_contract as D
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_system',ROOT/'scripts/audit-desktop-system.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A); C = A.A.C


def main():
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--work',type=Path,required=True); cli.add_argument('--mount',type=Path,required=True); cli.add_argument('--output',type=Path,required=True); a = cli.parse_args()
    work = a.work.resolve(); mount = a.mount.resolve(); output = a.output.resolve()
    D.need(os.name != 'nt' and mount.parent == Path('/var/tmp') and not mount.exists(),'Fresh WSL mount required')
    D.need(work.is_relative_to(ROOT/'out') and not work.exists() and output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh output paths required')
    parent = ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json'; parent_raw = parent.read_bytes(); audit = json.loads(parent_raw)
    D.need(audit['error'] is None and audit['mount_cleanup_complete'],'Contract audit incomplete')
    for item in audit['sources']:
        D.need(C.sha((ROOT/item['path']).read_bytes()) == item['sha256'],'Contract source changed')
    record = next(i for i in audit['inputs'] if i['component']=='OS'); image = Path(record['path'])
    D.need(C.sha(C.TOOL.read_bytes()) == C.TOOL_SHA,'APFS reader changed')
    before = A.digests(image); D.need(before == record['before'] == record['after'],'Fixed OS component differs')
    work.mkdir(); mount.mkdir(); commands = []; mounted = False; error = None; result = {}
    def run(argv):
        child = subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=child.returncode,stdout=child.stdout,stderr=child.stderr)); child.check_returncode()
    try:
        run([C.TOOL,'-o','ro',image,mount]); mounted = True; run(['mountpoint','-q',mount])
        root = mount/'root' if (mount/'root').is_dir() else mount
        archive = work/'os-var-source.tar'; result['data_source'] = E.export_tree(C.rooted(root,'/private/var'),archive,excluded_prefixes=('private/var/staged_system_apps',))
        config = C.rooted(root,'/System/Library/xpc/launchd.plist').read_bytes()
        D.need(C.sha(config) == audit['main_launch_config']['sha256'],'Launch config changed')
        refs = E.feature_references(plistlib.loads(config)); defaults = {}
        for ref in refs:
            feature = ref['feature']
            if not isinstance(feature,str) or '/' not in feature:
                continue
            domain, key = feature.split('/',1)
            D.need(domain and all(c.isalnum() or c in '._-' for c in domain),'Feature domain path')
            path = '/System/Library/FeatureFlags/Domain/'+domain+'.plist'
            if path not in defaults:
                try:
                    raw = C.rooted(root,path).read_bytes()
                except FileNotFoundError:
                    defaults[path] = dict(path=path,present=False)
                else:
                    D.need(len(raw) <= 4*1024*1024,'Feature defaults too large')
                    defaults[path] = dict(path=path,present=True,sha256=C.sha(raw),value=D.plist_value(plistlib.loads(raw)))
        result['feature_flags'] = dict(references=D.plist_value(refs),default_files=list(defaults.values()),runtime_values_resolved=False,
                                       scope='Defaults and conditional declarations only; runtime override/argument interpreter unqualified')
        plan = dict(root_windows=audit['root_window_preview'],
                    filesystem_components='Preserve original disk contents; UDIF must be decoded before raw-window assembly',
                    data_source=dict(path=str(archive.relative_to(ROOT)),sha256=result['data_source']['archive_sha256'],purpose='OS /private/var source material, not an APFS seed'),
                    candidate_data_paths=audit['data_contract']['candidate_paths'],
                    selected_services=audit['selected_services'],feature_conditions=D.plist_value(refs),
                    jobs_enabled=False,root_assembled=False,deployable=False,
                    excluded_data_source=result['data_source']['excluded'],
                    pending=['Decoded OS window hash, nuwa provider/root UUID and storage capacity','APFS Data seed creation/metadata/protection and volatile/persistent ABI','Staged system application provisioning outside the initial directory-source archive','Service feature-flag interpreter, identities, IPC consumers and runtime-created state','ResourceFork completion, native exec/EL0, platform and display/HID qualification'])
        (work/'assembly-contract.json').write_bytes(json.dumps(plan,indent=2).encode()+b'\n')
        result['assembly_contract'] = dict(path=str((work/'assembly-contract.json').relative_to(ROOT)),sha256=C.sha((work/'assembly-contract.json').read_bytes()))
        print(json.dumps(dict(source_entries=len(result['data_source']['entries']),file_bytes=result['data_source']['file_bytes'],archive_sha256=result['data_source']['archive_sha256'],feature_conditions=len(refs),deployable=False)),flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mounted:
            run(['fusermount','-u',mount])
        D.need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode != 0,'Mount remains active')
        after = A.digests(image); D.need(after == before,'Source OS changed')
    result.update(parent=dict(path=str(parent.relative_to(ROOT)),sha256=C.sha(parent_raw)),input=dict(path=str(image),before=before,after=after),
                  sources=[dict(path='scripts/'+name,sha256=C.sha((ROOT/'scripts'/name).read_bytes())) for name in ('desktop_data_source.py','prepare-desktop-data-source.py','desktop_root_contract.py','audit-desktop-system.py','audit-desktop-root.py','audit-userland-closure.py')],
                  commands=commands,error=error,mount_cleanup_complete=True,device_accessed=False,filesystem_seed_created=False,jobs_enabled=False,release_guard_changed=False)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    D.need(error is None,'Data preparation failed: '+str(error))


if __name__ == '__main__':
    main()
