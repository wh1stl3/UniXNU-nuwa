"""Qualify cache references and selected desktop dependency paths, read-only.

Virtual cryptex/cache bindings are an explicit composition proposal, never a
deployed mount policy. No image programs, device commands or kernel changes.
"""
import argparse, importlib.util, json, os, posixpath, stat, subprocess
from pathlib import Path
from desktop_cache import CacheSet, macho_dependencies, need
from desktop_namespace import Namespace
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_system', ROOT/'scripts/audit-desktop-system.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A); C = A.A.C


def closure(ns, cache, entries):
    queue = list(entries); nodes = {}; edges = []; unresolved = []; missing = []
    while queue:
        path = queue.pop(0)
        if path in nodes:
            continue
        need(len(nodes) < 10000, 'Dependency budget exhausted')
        if path in cache.images and path not in entries:
            info = cache.dependencies(path); origin = dict(kind='cache', address=hex(cache.images[path]))
        else:
            record = ns.resolve(path); need(record['regular'], 'Dependency is not a regular file')
            physical = Path(record['physical'])
            with physical.open('rb') as f:
                head = f.read(32); need(len(head) == 32, 'Short standalone Mach-O')
                size = __import__('struct').unpack_from('<I', head, 20)[0]
                need(size <= 1024*1024, 'Standalone load command size'); raw = head+f.read(size)
            info = macho_dependencies(raw); origin = dict(kind='standalone', namespace=record, command_bytes_sha256=C.sha(raw))
        nodes[path] = dict(path=path, origin=origin, **info)
        for dep in info['dependencies']:
            target = dep['path']
            if target.startswith('@loader_path/'):
                target = posixpath.normpath(posixpath.dirname(path)+'/'+target[len('@loader_path/'):])
            if not target.startswith('/'):
                unresolved.append(dict(source=path, **dep, reason='Contextual dyld token/rpath not evaluated'))
                continue
            edge = dict(source=path, target=target, weak=dep['weak'], command=dep['command']); edges.append(edge)
            if target in cache.images and target not in entries:
                edge['resolution'] = 'cache'; queue.append(target)
            else:
                try:
                    present = ns.resolve(target)
                except FileNotFoundError:
                    edge['resolution'] = 'missing'; missing.append(edge.copy())
                else:
                    need(present['regular'], 'Non-file dependency'); edge['resolution'] = 'standalone'; queue.append(target)
    return dict(entries=entries, nodes=list(nodes.values()), edges=edges, missing=missing,
                unresolved_contextual=unresolved, required_missing=[e for e in missing if not e['weak']],
                scope='Load-command path closure only; not symbols, fixups, dlopen, service IPC, signatures or execution')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--work', type=Path, required=True); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    work = a.work.resolve(); output = a.output.resolve()
    need(os.name != 'nt' and work.parent == Path('/var/tmp') and not work.exists(), 'Fresh WSL /var/tmp work path required')
    need(output.is_relative_to(ROOT/'reports') and not output.exists(), 'Fresh report path required')
    need(C.sha(C.TOOL.read_bytes()) == C.TOOL_SHA, 'APFS reader changed')
    prior_path = ROOT/'reports/desktop-readiness/2026-10-27-system-r1/audit.json'
    prior_raw = prior_path.read_bytes(); prior = json.loads(prior_raw)
    need(prior['donor']['identity']['build'] == '20H392', 'Donor build differs')
    work.mkdir(); mounted = []; inputs = []; roots = {}; commands = []; cache = None; error = None; result = {}
    def run(argv):
        child = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=120)
        commands.append(dict(argv=[str(x) for x in argv], exit_code=child.returncode, stdout=child.stdout, stderr=child.stderr)); child.check_returncode()
    try:
        for i, record in enumerate(prior['images']):
            image = Path(record['path']); before = A.digests(image)
            need(all(before[k] == record[k] for k in ('sha256','sha384','bytes')), 'Input differs from fixed component')
            inputs.append(dict(component=record['component'], path=str(image), before=before))
            mount = work/str(i); mount.mkdir(); run([C.TOOL, '-o', 'ro', image, mount]); mounted.append(mount); run(['mountpoint','-q',mount])
            roots[record['component']] = mount/'root' if (mount/'root').is_dir() else mount
            print(json.dumps(dict(component=record['component'], digest_matches=True, mounted_read_only=True)), flush=True)
        cache_dir = '/System/Library/Caches/com.apple.dyld'
        cache_root = C.rooted(roots['Cryptex1,SystemOS'], cache_dir)
        cache = CacheSet(cache_root/'dyld_shared_cache_arm64')
        print(json.dumps(dict(subcaches=len(cache.subcaches), indexed_images=len(cache.images), symbols_uuid_matched=cache.symbols is not None)), flush=True)
        layers = [dict(prefix='/', component='OS', root=roots['OS']),
                  dict(prefix='/System/Cryptexes/OS', component='Cryptex1,SystemOS', root=roots['Cryptex1,SystemOS']),
                  dict(prefix='/System/Cryptexes/App', component='Cryptex1,AppOS', root=roots['Cryptex1,AppOS']),
                  dict(prefix=cache_dir, component='Cryptex1,SystemOS', root=cache_root)]
        ns = Namespace(layers)
        entries = ['/sbin/launchd','/usr/lib/dyld','/System/Library/CoreServices/SpringBoard.app/SpringBoard','/usr/libexec/backboardd']
        selected = []
        for path in entries+[cache_dir+'/dyld_shared_cache_arm64']:
            record = ns.resolve(path); data = Path(record['physical']).read_bytes()
            record['sha256'] = C.sha(data); selected.append(record)
        for key, item in prior['images'][0]['binaries'].items():
            candidates = [r for r in selected if r['path'] == A.A.ITEMS[key]]
            need(len(candidates) == 1 and candidates[0]['sha256'] == item['sha256'], 'Desktop executable differs from fixed inventory')
        hidden = roots['OS']/cache_dir.lstrip('/')
        try:
            hidden_stat = hidden.lstat()
        except FileNotFoundError:
            conflict = dict(path=cache_dir, present_in_OS=False)
        else:
            conflict = dict(path=cache_dir, present_in_OS=True, mode=oct(hidden_stat.st_mode), symlink=os.readlink(hidden) if stat.S_ISLNK(hidden_stat.st_mode) else None,
                            entries=sorted(x.name for x in hidden.iterdir()) if stat.S_ISDIR(hidden_stat.st_mode) else None)
        dependency = closure(ns, cache, entries)
        result.update(namespace=dict(proposed_bindings=[dict(v, root=str(v['root'])) for v in layers], selected_paths=selected, cache_graft_hides=conflict,
                                     deployed=False, scope='Selected-path composition model; not exhaustive root conflict/link validation'),
                      cache=cache.report(), dependency_closure=dependency)
        print(json.dumps(dict(nodes=len(dependency['nodes']), edges=len(dependency['edges']), required_missing=len(dependency['required_missing']), contextual=len(dependency['unresolved_contextual']))), flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
    finally:
        if cache:
            cache.close()
        for mount in reversed(mounted):
            try:
                run(['fusermount','-u',mount])
            except BaseException as exc:
                error = error or dict(type=type(exc).__name__, message=str(exc))
        for mount in mounted:
            need(subprocess.run(['mountpoint','-q',str(mount)], capture_output=True).returncode != 0, 'Mount remains active')
        for item in inputs:
            item['after'] = A.digests(Path(item['path'])); need(item['after'] == item['before'], 'Input changed during read-only audit')
    result.update(inputs=inputs, commands=commands, error=error, mount_cleanup_complete=True,
                  sources=[dict(path='scripts/'+name, sha256=C.sha((ROOT/'scripts'/name).read_bytes())) for name in ('desktop_cache.py','desktop_namespace.py','audit-desktop-cache.py','audit-desktop-system.py','audit-desktop-root.py','audit-userland-closure.py')],
                  parent=dict(path=str(prior_path.relative_to(ROOT)), sha256=C.sha(prior_raw)),
                  format_reference=dict(repository='apple-oss-distributions/dyld', tag='dyld-1066.8', paths=['cache-builder/dyld_cache_format.h','common/DyldSharedCache.cpp'], license='APSL-2.0', role='Format reference; not proof of exact OS dyld build'),
                  device_accessed=False, userland_executed=False, root_assembled=False, release_guard_changed=False)
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(json.dumps(result, indent=2).encode()+b'\n')
    need(error is None, 'Audit failed: '+str(error))


if __name__ == '__main__':
    main()
