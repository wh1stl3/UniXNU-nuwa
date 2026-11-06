"""Decode the fixed OS DMG and verify raw-file bytes and a read-only FS view.

No SHNGROOT image, Data filesystem, payload or boot package is generated.
"""
import argparse, importlib.util, json, os, shutil, subprocess, time
from pathlib import Path
import udif_raw_decode as U
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_system',ROOT/'scripts/audit-desktop-system.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A); C = A.A.C


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--library',type=Path,required=True); p.add_argument('--work',type=Path,required=True); p.add_argument('--mount',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a = p.parse_args()
    work = a.work.resolve(); mount = a.mount.resolve(); output = a.output.resolve(); lib = a.library.resolve()
    U.D.need(os.name != 'nt' and work.is_relative_to(ROOT/'out') and not work.exists(),'Fresh host output path required')
    U.D.need(mount.parent == Path('/var/tmp') and not mount.exists() and output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh mount/report required')
    parent_path = ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json'; parent_raw = parent_path.read_bytes(); parent = json.loads(parent_raw)
    qualification_path = ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/qualification-r2.json'; qual_raw = qualification_path.read_bytes(); qual = json.loads(qual_raw)
    U.D.need(any(v['sha256'] == C.sha(parent_raw) and U.evidence_path(v['path']) == str(parent_path.relative_to(ROOT)) for v in qual['evidence']),'Parent binding differs')
    tests_path = ROOT/'reports/desktop-readiness/2026-10-27-raw-os-r1/tests-r2.json'; tests_raw = tests_path.read_bytes(); tests = json.loads(tests_raw)
    U.D.need(len(tests['checks']) == 14 and all(v['passed'] for v in tests['checks']) and C.sha(lib.read_bytes()) == tests['library_sha256'],'Decoder tests/library mismatch')
    for source in tests['sources']:
        U.D.need(C.sha((ROOT/source['path']).read_bytes()) == source['sha256'],'Decoder source changed')
    record = next(v for v in parent['inputs'] if v['component']=='OS'); image = Path(record['path']); before = A.digests(image)
    U.D.need(before == record['before'] == record['after'],'Fixed OS image differs')
    U.D.need(shutil.disk_usage(work.parent).free > record['geometry']['raw_bytes']+512*1024*1024,'Insufficient host output space')
    U.D.need(C.sha(C.TOOL.read_bytes()) == C.TOOL_SHA,'APFS reader changed')
    work.mkdir(); mount.mkdir(); commands = []; error = None; result = {}; mounted = False; start = time.monotonic()
    def run(argv):
        child = subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=child.returncode,stdout=child.stdout,stderr=child.stderr)); child.check_returncode()
    try:
        raw = work/'os.raw.img'; result['decode'] = U.decode_to_file(image,raw,U.Lzfse(lib),progress=lambda v:print(json.dumps(v),flush=True))
        run([C.TOOL,'-o','ro',raw,mount]); mounted = True; run(['mountpoint','-q',mount])
        root = mount/'root' if (mount/'root').is_dir() else mount; reference_path = ROOT/'reports/desktop-readiness/2026-10-27-system-r1/audit.json'; reference_raw = reference_path.read_bytes(); reference = json.loads(reference_raw)
        os_ref = reference['images'][0]; comparisons = []
        for name,value in os_ref['binaries'].items():
            path = A.A.ITEMS[name]; data = C.rooted(root,path).read_bytes(); U.D.need(C.sha(data) == value['sha256'],'Raw filesystem executable differs: '+path)
            comparisons.append(dict(path=path,sha256=C.sha(data),bytes=len(data),matches_fixed_inventory=True))
        path = '/System/Library/xpc/launchd.plist'; data = C.rooted(root,path).read_bytes()
        U.D.need(C.sha(data) == parent['main_launch_config']['sha256'],'Raw launch config differs')
        comparisons.append(dict(path=path,sha256=C.sha(data),bytes=len(data),matches_fixed_inventory=True))
        result['filesystem_comparisons'] = comparisons; result['inventory_reference'] = dict(path=str(reference_path.relative_to(ROOT)),sha256=C.sha(reference_raw))
        print(json.dumps(dict(raw_bytes=result['decode']['raw_bytes'],raw_sha256=result['decode']['raw_sha256'],filesystem_comparisons=len(comparisons))),flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mounted:
            run(['fusermount','-u',mount])
        U.D.need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode != 0,'Mount remains active')
        after = A.digests(image); U.D.need(after == before,'Original OS image changed')
    result.update(error=error,source=dict(path=str(image),before=before,after=after),commands=commands,mount_cleanup_complete=True,elapsed_seconds=time.monotonic()-start,
                  parents=[dict(path=str(path.relative_to(ROOT)),sha256=C.sha(raw)) for path,raw in ((parent_path,parent_raw),(qualification_path,qual_raw),(tests_path,tests_raw))],
                  sources=[dict(path='scripts/'+name,sha256=C.sha((ROOT/'scripts'/name).read_bytes())) for name in ('udif_raw_decode.py','prepare-desktop-raw-os.py','desktop_root_contract.py','audit-desktop-system.py','audit-desktop-root.py','audit-userland-closure.py')],
                  raw_path=str((work/'os.raw.img').relative_to(ROOT)),device_accessed=False,root_image_assembled=False,data_seed_created=False,release_guard_changed=False,
                  limitations=['Raw host disk bytes only; target capacity, root UUID matching and provider/OS ABI unqualified','No native mount/exec/EL0, CMS trust or desktop acceptance'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    U.D.need(error is None,'Raw OS preparation failed: '+str(error))


if __name__ == '__main__': main()
