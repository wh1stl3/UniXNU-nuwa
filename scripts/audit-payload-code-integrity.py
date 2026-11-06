"""Bind first-exec/core binaries and every runtime cache file to original trust entries.
Read-only donor mounts; never changes images, trust entries, kernel or device.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
from payload_code_integrity import inspect, trust_entries

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core', ROOT/'scripts/audit-desktop-core-services.py')
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); work = a.work.resolve(); output = a.output.resolve()
    core.need(os.name != 'nt' and work.parent == Path('/var/tmp') and not work.exists(), 'Fresh WSL work required')
    core.need(output.is_relative_to(ROOT/'reports') and not output.exists(), 'Fresh report required')
    parent = ROOT/'reports/desktop-readiness/2026-10-30-core-services-r1/audit.json'
    prior = json.loads(parent.read_bytes())
    core.need(prior['error'] is None and prior['mount_cleanup_complete'], 'Parent qualification')
    core.need(core.C.sha(core.C.TOOL.read_bytes()) == core.C.TOOL_SHA, 'Reader drift')
    bundle_path = ROOT/'out/payload-s1-r1/kernel.macho.trustcache'
    bundle = bundle_path.read_bytes()
    core.need(core.C.sha(bundle) == 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3', 'Original trust bundle drift')
    entries = trust_entries(bundle)
    work.mkdir(); mounted = []; inputs = []; roots = {}; records = []; controls = []; error = None; cache = None
    def run(argv):
        subprocess.run(list(map(str, argv)), check=True, capture_output=True, timeout=120)
    try:
        for index, item in enumerate(prior['inputs']):
            if item['component'] not in ('OS', 'Cryptex1,SystemOS'):
                continue
            image = Path(item['path']); before = core.A.digests(image)
            core.need(before == item['before'], 'Donor drift')
            inputs.append(dict(component=item['component'], path=str(image), before=before))
            mount = work/str(index); mount.mkdir()
            run([core.C.TOOL, '-o', 'ro', image, mount]); mounted.append(mount)
            run(['mountpoint', '-q', mount])
            roots[item['component']] = mount/'root' if (mount/'root').is_dir() else mount
            print('Read-only input bound:', item['component'], flush=True)
        old = {r['path']:r for r in prior['namespace']['selected_paths']}
        for name in prior['dependency_closure']['entries']:
            path = core.C.rooted(roots['OS'], name)
            raw = path.read_bytes()
            core.need(core.C.sha(raw) == old[name]['sha256'], 'Selected binary drift')
            result = inspect(io.BytesIO(raw), len(raw), entries)
            # Validate genuine standalone Mach-O entry/segment bounds as well.
            macho = core.C.macho(raw)
            records.append(dict(path=name, component='OS', sha256=core.C.sha(raw),
                macho=macho, **result))
            if name == '/sbin/launchd':
                bad = bytearray(raw); bad[0x1000] ^= 1
                try:
                    inspect(io.BytesIO(bad), len(bad), entries)
                except ValueError as exc:
                    core.need('Code page mismatch' in str(exc), 'Wrong mutation rejection')
                    controls.append(dict(case='changed-launchd-code-page', rejected=True))
                else:
                    raise AssertionError('Changed code accepted')
                stripped = inspect(io.BytesIO(raw), len(raw), {})
                core.need(not stripped['original_trust_covered'], 'Missing trust accepted')
                controls.append(dict(case='empty-trust-membership', covered=False))
            print('Code pages checked:', name, 'trust=', result['original_trust_covered'], flush=True)
        directory = roots['Cryptex1,SystemOS']/'System/Library/Caches/com.apple.dyld'
        cache = core.CacheSet(directory/'dyld_shared_cache_arm64')
        for item in cache.files:
            path = directory/item['name']
            with path.open('rb') as stream:
                result = inspect(stream, path.stat().st_size, entries)
            records.append(dict(path='/System/Library/Caches/com.apple.dyld/'+path.name,
                component='SystemOS', uuid=item['uuid'], **result))
            print('Cache pages checked:', path.name, 'trust=', result['original_trust_covered'], flush=True)
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
            if item['before'] != item['after']:
                error = error or dict(type='InputChanged', message=item['path'])
        missing = [r['path'] for r in records if not r['original_trust_covered']]
        report = dict(error=error, passed=error is None and cleanup, mount_cleanup_complete=cleanup,
            parent_sha256=core.C.sha(parent.read_bytes()), inputs=inputs,
            trust_bundle_sha256=core.C.sha(bundle), records=records, negative_controls=controls,
            missing_original_trust_entries=missing, all_selected_original_trust_covered=not missing and bool(records),
            code_pages=sum(d['code_pages'] for r in records for d in r['directories']),
            sources={n:core.C.sha((ROOT/'scripts'/n).read_bytes()) for n in
                ('audit-payload-code-integrity.py','payload_code_integrity.py','audit-userland-closure.py','desktop_cache.py')},
            device_accessed=False, cms_verified=False, native_amfi_acceptance=False,
            limits=['Selected donor bytes, not runtime union lookup', 'No CMS certificate/policy or external special-slot validation',
                    'Trust membership does not prove module loaded or AMFI acceptance',
                    'Runtime cache files checked; symbols sidecar is not an executable mapping',
                    'No fixup/symbol resolution, user execution, Data or service qualification'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2)+'\n')
    core.need(error is None and cleanup, 'Audit failed: '+str(error))
    print('RESULT', len(records), 'files;', report['code_pages'], 'code pages;', len(missing), 'without original trust match')


if __name__ == '__main__':
    main()
