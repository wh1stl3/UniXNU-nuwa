"""Compare declared payload namespaces against pinned iOS16 components, read-only.

No device access or image changes. Cache-assisted closure runs only when the
cache is visible in the selected namespace; mounted media is not a mount policy.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core', ROOT/'scripts/audit-desktop-core-services.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    core.need(os.name != 'nt' and work.parent == Path('/var/tmp') and not work.exists(), 'Fresh WSL work required')
    core.need(output.is_relative_to(ROOT/'reports') and not output.exists(), 'Fresh report required')
    prior_path = ROOT/'reports/desktop-readiness/2026-10-30-core-services-r1/audit.json'
    prior_bytes = prior_path.read_bytes()
    prior = json.loads(prior_bytes)
    core.need(prior['error'] is None and prior['mount_cleanup_complete'], 'Invalid parent')
    core.need(core.C.sha(core.C.TOOL.read_bytes()) == core.C.TOOL_SHA, 'Reader drift')
    work.mkdir()
    mounted, inputs, commands, variants = [], [], [], []
    roots = {}
    cache = None
    error = None

    def run(argv):
        child = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=120)
        commands.append(dict(argv=[str(x) for x in argv], exit_code=child.returncode,
                             stdout=child.stdout, stderr=child.stderr))
        child.check_returncode()

    try:
        # Only OS and SystemOS: absence of AppOS must not be hidden by a third mount.
        for index, item in enumerate(prior['inputs']):
            if item['component'] not in ('OS', 'Cryptex1,SystemOS'):
                continue
            image = Path(item['path'])
            before = core.A.digests(image)
            core.need(before == item['before'], 'Component drift')
            inputs.append(dict(component=item['component'], path=str(image), before=before))
            mount = work/str(index)
            mount.mkdir()
            run([core.C.TOOL, '-o', 'ro', image, mount])
            mounted.append(mount)
            run(['mountpoint', '-q', mount])
            roots[item['component']] = mount/'root' if (mount/'root').is_dir() else mount
            print('Verified and mounted read-only:', item['component'], flush=True)
        cache_dir = '/System/Library/Caches/com.apple.dyld'
        cache_root = roots['Cryptex1,SystemOS']/cache_dir.lstrip('/')
        cache = core.CacheSet(cache_root/'dyld_shared_cache_arm64')
        entries = prior['dependency_closure']['entries']
        basic = [dict(prefix='/', component='OS', root=roots['OS'])]
        system = basic + [dict(prefix='/System/Cryptexes/OS', component='Cryptex1,SystemOS', root=roots['Cryptex1,SystemOS'])]
        graft = system + [dict(prefix=cache_dir, component='Cryptex1,SystemOS', root=cache_root)]
        old_paths = {r['path']: r for r in prior['namespace']['selected_paths']}
        for name, layers in [('os-only', basic), ('system-at-cryptex', system), ('system-with-cache-graft', graft)]:
            ns = core.Namespace(layers)
            paths = []
            for path in entries + [cache_dir+'/dyld_shared_cache_arm64']:
                try:
                    record = ns.resolve(path)
                except FileNotFoundError:
                    record = dict(path=path, present=False)
                else:
                    record.update(present=True, sha256=core.C.sha(Path(record['physical']).read_bytes()))
                    core.need(record['sha256'] == old_paths[path]['sha256'], 'Selected binary drift')
                paths.append(record)
            visible = paths[-1]['present']
            result = dict(name=name, layers=[dict(v, root=str(v['root'])) for v in layers], paths=paths,
                          cache_visible=visible, closure_evaluated=False, deployed=False)
            if visible:
                dependency = core.closure(ns, cache, entries)
                core.need(not dependency['required_missing'] and not dependency['unresolved_contextual'], 'Closure incomplete')
                result.update(closure_evaluated=True, dependency_closure=dependency)
            variants.append(result)
        core.need([v['cache_visible'] for v in variants] == [False, False, True], 'Exposure assumptions changed')
        print('PASS: OS/SystemOS-only cache exposure and core closure; AppOS not mounted', flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
    finally:
        if cache:
            cache.close()
        for mount in reversed(mounted):
            try:
                run(['fusermount', '-u', mount])
            except BaseException as exc:
                error = error or dict(type=type(exc).__name__, message=str(exc))
        cleanup = all(subprocess.run(['mountpoint', '-q', str(m)], capture_output=True).returncode != 0 for m in mounted)
        for item in inputs:
            item['after'] = core.A.digests(Path(item['path']))
            if item['after'] != item['before']:
                error = error or dict(type='InputChanged', message=item['path'])
        report = dict(parent=dict(path=str(prior_path.relative_to(ROOT)), sha256=core.C.sha(prior_bytes)),
                      inputs=inputs, variants=variants, commands=commands, error=error,
                      mount_cleanup_complete=cleanup, device_accessed=False, userland_executed=False,
                      sources={name: core.C.sha((ROOT/'scripts'/name).read_bytes()) for name in
                               ('audit-payload-exposure.py', 'audit-desktop-core-services.py', 'desktop_namespace.py', 'desktop_cache.py')},
                      limitations=['Virtual mount proposals only; no runtime graft or mount implementation proven',
                                   'Core static load-command closure excludes dynamic dlopen, signatures, fixups and IPC',
                                   'No AppOS requirement for this closure does not prove AppOS dispensable for the full OS'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2)+'\n')
    core.need(error is None and cleanup, 'Exposure audit failed: '+str(error))


if __name__ == '__main__':
    main()
