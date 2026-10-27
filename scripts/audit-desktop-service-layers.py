"""Resolve declared cryptex service programs against fixed read-only components."""
import argparse, importlib.util, json, os, subprocess
from pathlib import Path
from desktop_namespace import Namespace
from desktop_cache import need
from desktop_service_macho import inspect
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_system',ROOT/'scripts/audit-desktop-system.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A); C = A.A.C


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--work',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a = p.parse_args()
    work = a.work.resolve(); output = a.output.resolve()
    need(os.name != 'nt' and work.parent == Path('/var/tmp') and not work.exists(),'Fresh WSL work directory required')
    need(output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh report required')
    parent = ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json'; parent_raw = parent.read_bytes(); audit = json.loads(parent_raw)
    need(audit['error'] is None and audit['mount_cleanup_complete'],'Parent incomplete')
    for source in audit['sources']:
        need(C.sha((ROOT/source['path']).read_bytes()) == source['sha256'],'Parent source changed')
    need(C.sha(C.TOOL.read_bytes()) == C.TOOL_SHA,'APFS reader changed')
    cache_path = ROOT/'reports/desktop-readiness/2026-10-27-cache-r1/audit-r3.json'; cache_raw = cache_path.read_bytes()
    need(any(e['sha256'] == C.sha(cache_raw) and e['path'] == str(cache_path.relative_to(ROOT)) for e in audit['parents']),'Cache evidence changed')
    cache_paths = {v['path'] for v in json.loads(cache_raw)['cache']['images']}
    work.mkdir(); inputs = []; mounts = []; layers = []; commands = []; records = []; error = None
    def run(argv):
        child = subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=child.returncode,stdout=child.stdout,stderr=child.stderr)); child.check_returncode()
    try:
        for i, component in enumerate(('Cryptex1,SystemOS','Cryptex1,AppOS')):
            source = next(v for v in audit['inputs'] if v['component']==component); path = Path(source['path']); before = A.digests(path)
            need(before == source['before'] == source['after'],'Fixed component differs')
            inputs.append(dict(component=component,path=str(path),before=before))
            mount = work/str(i); mount.mkdir(); run([C.TOOL,'-o','ro',path,mount]); mounts.append(mount); run(['mountpoint','-q',mount])
            root = mount/'root' if (mount/'root').is_dir() else mount
            layers.append(dict(prefix='/System/Cryptexes/'+('OS' if i==0 else 'App'),component=component,root=root))
        # Synthetic root is a host directory used only for declared mount ancestors.
        base = work/'virtual-root'; base.mkdir(); ns = Namespace(layers+[dict(prefix='/',component='empty_virtual_root',root=base)])
        remaining = []
        for job in audit['services']['jobs']:
            if job['program_path']['status'] != 'missing':
                continue
            path = job['program']
            if not path.startswith('/System/Cryptexes/'):
                remaining.append(dict(label=job['label'],program=path,scope='Absent from OS inventory; applicability not inferred')); continue
            try:
                resolved = ns.resolve(path)
            except FileNotFoundError:
                records.append(dict(label=job['label'],program=path,present=False)); continue
            need(resolved['regular'],'Service program is not regular'); data = Path(resolved['physical']).read_bytes()
            info = inspect(data); selected = info['selected']; deps = selected['dependencies'] if selected else []
            records.append(dict(label=job['label'],program=path,present=True,namespace=resolved,sha256=C.sha(data),macho=info,
                                dependencies_in_cache=[v for v in deps if v['path'] in cache_paths],
                                other_dependency_paths=[v for v in deps if v['path'] not in cache_paths],
                                enabled=False))
        print(json.dumps(dict(cryptex_programs=len(records),present=sum(v['present'] for v in records),remaining_os_only=len(remaining))),flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__,message=str(exc)); remaining = []
    finally:
        for mount in reversed(mounts):
            run(['fusermount','-u',mount])
        for mount in mounts:
            need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode != 0,'Mount remains active')
        for source in inputs:
            source['after'] = A.digests(Path(source['path'])); need(source['after'] == source['before'],'Source changed')
    report = dict(parents=[dict(path=str(parent.relative_to(ROOT)),sha256=C.sha(parent_raw)),dict(path=str(cache_path.relative_to(ROOT)),sha256=C.sha(cache_raw))],
                  programs=records,remaining_os_only=remaining,inputs=inputs,commands=commands,error=error,mount_cleanup_complete=True,
                  sources=[dict(path='scripts/'+name,sha256=C.sha((ROOT/'scripts'/name).read_bytes())) for name in ('audit-desktop-service-layers.py','desktop_service_macho.py','desktop_namespace.py','desktop_cache.py','audit-desktop-system.py','audit-desktop-root.py','audit-userland-closure.py')],
                  device_accessed=False,root_assembled=False,jobs_enabled=False,
                  limitations=['Declared program provenance, not service enablement, IPC consumers or execution','Other dependency paths are not evaluated as missing; no recursive service dependency closure'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    need(error is None,'Service component audit failed: '+str(error))


if __name__ == '__main__':
    main()
