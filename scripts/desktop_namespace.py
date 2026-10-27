"""Selected-path virtual composition; never mounts, copies or writes image files."""
import os, stat
from pathlib import Path


class Namespace:
    def __init__(self, layers):
        self.layers = sorted(layers, key=lambda v: len(v['prefix']), reverse=True)
        if len({v['prefix'] for v in layers}) != len(layers) or not any(v['prefix'] == '/' for v in layers):
            raise ValueError('Unique prefixes and root layer required')
        for item in layers:
            if not item['prefix'].startswith('/') or '..' in item['prefix'].split('/'):
                raise ValueError('Invalid namespace prefix')

    def provider(self, path):
        for item in self.layers:
            prefix = item['prefix'].rstrip('/')
            if not prefix or path == prefix or path.startswith(prefix+'/'):
                return item, Path(item['root']) / path[len(prefix):].lstrip('/')
        raise ValueError('No namespace provider')

    def resolve(self, path):
        if not path.startswith('/'):
            raise ValueError('Absolute namespace path required')
        pending = path.split('/'); parts = []; links = []; count = 0
        while pending:
            part = pending.pop(0)
            if part in ('', '.'):
                continue
            if part == '..':
                if not parts:
                    raise ValueError('Namespace root escape')
                parts.pop(); continue
            logical = '/'+ '/'.join(parts+[part]); layer, physical = self.provider(logical)
            try:
                st = physical.lstat()
            except FileNotFoundError:
                if any(v['prefix'].startswith(logical+'/') for v in self.layers):
                    parts.append(part); continue  # Declared mount ancestor only.
                raise
            if stat.S_ISLNK(st.st_mode):
                count += 1
                if count > 40:
                    raise ValueError('Namespace symlink loop')
                target = os.readlink(physical)
                links.append(dict(path=logical, component=layer['component'], target=target))
                if target.startswith('/'):
                    parts = []
                pending = target.split('/')+pending
            else:
                if pending and not stat.S_ISDIR(st.st_mode):
                    raise ValueError('Namespace non-directory traversal')
                parts.append(part)
        canonical = '/'+ '/'.join(parts); layer, physical = self.provider(canonical); st = physical.stat()
        return dict(path=path, canonical=canonical, component=layer['component'], physical=str(physical),
                    bytes=st.st_size, mode=oct(stat.S_IMODE(st.st_mode)), uid=st.st_uid, gid=st.st_gid,
                    symlinks=links, regular=stat.S_ISREG(st.st_mode), directory=stat.S_ISDIR(st.st_mode))
