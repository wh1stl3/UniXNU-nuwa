"""Positive and malformed-input checks for cache references and virtual paths."""
import argparse, importlib.util, json, struct, tempfile
from pathlib import Path
from desktop_cache import CacheSet, Reader, header, macho_dependencies
from desktop_namespace import Namespace
import hashlib
ROOT = Path(__file__).resolve().parents[1]


def fixture(root):
    def head(uuid, base):
        b = bytearray(0x3000); b[:16] = b'dyld_v1   arm64\0'; b[88:104] = uuid
        struct.pack_into('<II', b, 16, 0x200, 1)
        struct.pack_into('<QQQII', b, 0x200, base, len(b), 0, 5, 5)
        return b
    main = head(b'a'*16, 0x180000000); sub = head(b'b'*16, 0x180010000)
    struct.pack_into('<II', main, 0x188, 0x300, 1)
    main[0x300:0x310] = b'b'*16; struct.pack_into('<Q', main, 0x310, 0x10000); main[0x318:0x31c] = b'.01\0'
    struct.pack_into('<II', main, 0x1c0, 0x400, 1)
    struct.pack_into('<QQQII', main, 0x400, 0x180010800, 0, 0, 0x500, 0)
    name = b'/usr/lib/example.dylib\0'; main[0x500:0x500+len(name)] = name
    struct.pack_into('<8I', sub, 0x800, 0xfeedfacf, 0x100000c, 0, 6, 0, 0, 0, 0)
    (root/'cache').write_bytes(main); (root/'cache.01').write_bytes(sub)
    return main, sub


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(ROOT/'reports'):
        raise ValueError('Fresh reports path required')
    checks = []
    def reject(name, action):
        try:
            action()
        except (ValueError, FileNotFoundError):
            checks.append(dict(name=name, passed=True))
        else:
            raise AssertionError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='nuwa-cache-tests-') as temp:
        root = Path(temp); original, sub = fixture(root); cache = CacheSet(root/'cache')
        assert cache.dependencies('/usr/lib/example.dylib')['dependencies'] == []
        assert len(cache.files) == 2; cache.close(); checks.append(dict(name='referenced subcache and image address resolved', passed=True))
        for title, mutate in (
            ('UUID mismatch rejected', lambda b: b.__setitem__(slice(0x300, 0x310), b'c'*16)),
            ('unsafe suffix rejected', lambda b: b.__setitem__(slice(0x318, 0x31d), b'../x\0')),
            ('table extent rejected', lambda b: struct.pack_into('<I', b, 0x188, len(b)-8)),
            ('mapping extent rejected', lambda b: struct.pack_into('<Q', b, 0x210, len(b))),
            ('unbacked image rejected', lambda b: struct.pack_into('<Q', b, 0x400, 0x77770000)),
        ):
            changed = bytearray(original); mutate(changed); (root/'cache').write_bytes(changed)
            reject(title, lambda: CacheSet(root/'cache'))
        (root/'cache').write_bytes(original); (root/'cache.01').unlink()
        reject('missing subcache rejected', lambda: CacheSet(root/'cache'))
        reject('truncated Mach-O commands rejected', lambda: macho_dependencies(struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 6, 1, 24, 0, 0)))
        text = b'/usr/lib/lazy.dylib\0'; length = (24+len(text)+7)//8*8
        command = struct.pack('<6I', 0x20, length, 24, 0, 0, 0)+text
        command += bytes(length-len(command))
        parsed = macho_dependencies(struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 6, 1, length, 0, 0)+command)
        assert parsed['dependencies'] == [dict(path='/usr/lib/lazy.dylib', weak=False, command='0x20')]
        checks.append(dict(name='lazy-load dependency retained as required edge', passed=True))
        fixture(root); actual = root/'standalone'; (actual/'usr/lib').mkdir(parents=True)
        (actual/'usr/lib/example.dylib').write_bytes(struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 7, 0, 0, 0, 0))
        spec = importlib.util.spec_from_file_location('cache_audit', ROOT/'scripts/audit-desktop-cache.py')
        audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
        cache = CacheSet(root/'cache')
        try:
            closed = audit.closure(Namespace([dict(prefix='/', component='OS', root=actual)]), cache, ['/usr/lib/example.dylib'])
            assert closed['nodes'][0]['origin']['kind'] == 'standalone' and closed['nodes'][0]['filetype'] == 7
        finally:
            cache.close()
        checks.append(dict(name='explicit executable entry uses disk file over cached namesake', passed=True))
        osroot = root/'os'; cryptex = root/'cryptex'; osroot.mkdir(); cryptex.mkdir()
        (cryptex/'payload').write_text('fixture'); (osroot/'absolute').symlink_to('/System/Cryptexes/OS/payload')
        (osroot/'relative').symlink_to('absolute'); (osroot/'loop').symlink_to('loop')
        (osroot/'escape').symlink_to('../../outside')
        ns = Namespace([dict(prefix='/', component='OS', root=osroot), dict(prefix='/System/Cryptexes/OS', component='SystemOS', root=cryptex)])
        assert ns.resolve('/relative')['component'] == 'SystemOS'
        checks.append(dict(name='relative/absolute links cross declared virtual mount', passed=True))
        reject('namespace root escape rejected', lambda: ns.resolve('/escape'))
        reject('namespace symlink loop rejected', lambda: ns.resolve('/loop'))
        reject('non-directory traversal rejected', lambda: ns.resolve('/relative/child'))
    result = dict(checks=checks, sources=[dict(path='scripts/'+name, sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('desktop_cache.py','desktop_namespace.py','audit-desktop-cache.py','test-desktop-cache.py')], device_accessed=False)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_bytes(json.dumps(result, indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks), passed=True)))


if __name__ == '__main__':
    main()
