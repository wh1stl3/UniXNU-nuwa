"""Bounded directory-source archive, preserving basic metadata without extraction.

Never follows source symlinks, creates device nodes, chowns host paths or calls
image programs. Archive is preparation material, not a bootable Data filesystem.
"""
import errno, hashlib, os, stat, tarfile
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def export_tree(source, archive, max_entries=10000, max_bytes=128*1024*1024, excluded_prefixes=()):
    need(not archive.exists() and source.is_dir() and not source.is_symlink(), 'Fresh archive and real source directory required')
    records = []; skipped = []; excluded = []; todo = [(source, 'private/var')]; total = 0
    with tarfile.open(archive, 'x', format=tarfile.PAX_FORMAT) as output:
        while todo:
            path, name = todo.pop(); need(len(records)+len(skipped)+len(excluded) < max_entries, 'Data source entry budget at '+name)
            st = path.lstat(); info = tarfile.TarInfo(name); info.uid = st.st_uid; info.gid = st.st_gid
            info.mode = stat.S_IMODE(st.st_mode); info.mtime = st.st_mtime
            item = dict(path=name, uid=info.uid, gid=info.gid, mode=oct(info.mode), mtime_ns=st.st_mtime_ns, source_inode=st.st_ino)
            if any(name == prefix or name.startswith(prefix+'/') for prefix in excluded_prefixes):
                excluded.append(dict(**item, reason='Explicit source scope; subtree retained in original OS image'))
                continue
            if stat.S_ISDIR(st.st_mode):
                info.type = tarfile.DIRTYPE; item['type'] = 'directory'; output.addfile(info)
                todo.extend((child, name+'/'+child.name) for child in sorted(path.iterdir(), reverse=True))
            elif stat.S_ISLNK(st.st_mode):
                info.type = tarfile.SYMTYPE; info.linkname = os.readlink(path); item.update(type='symlink', target=info.linkname); output.addfile(info)
            elif stat.S_ISREG(st.st_mode):
                total += st.st_size; need(total <= max_bytes, 'Data source byte budget at '+name)
                info.size = st.st_size
                with path.open('rb') as data:
                    digest = hashlib.sha256()
                    while block := data.read(1024*1024):
                        digest.update(block)
                    data.seek(0); output.addfile(info, data)
                item.update(type='file', bytes=st.st_size, sha256=digest.hexdigest())
            else:
                skipped.append(dict(**item, type='unsupported_special_node')); continue
            try:
                attrs = os.listxattr(path, follow_symlinks=False)
                item['xattrs'] = [dict(name=key, bytes=len(value), sha256=hashlib.sha256(value).hexdigest()) for key in sorted(attrs) for value in [os.getxattr(path,key,follow_symlinks=False)]]
                item['xattr_query'] = 'available_through_host_reader'
            except OSError as exc:
                if exc.errno not in (errno.ENOTSUP, errno.EOPNOTSUPP):
                    raise
                item['xattr_query'] = 'reader_not_supported'
            records.append(item)
    # Inspect the actual archive; never extract it on the host.
    with tarfile.open(archive, 'r') as check:
        members = check.getmembers(); need(len(members) == len(records), 'Archive member count')
        for member, item in zip(members, records):
            need((member.name.rstrip('/'),member.uid,member.gid,member.mode) == (item['path'],item['uid'],item['gid'],int(item['mode'],8)), 'Archive metadata differs')
            if item['type'] == 'file':
                data = check.extractfile(member); digest = hashlib.sha256()
                while block := data.read(1024*1024):
                    digest.update(block)
                need(digest.hexdigest() == item['sha256'], 'Archive content differs')
            elif item['type'] == 'symlink':
                need(member.issym() and member.linkname == item['target'], 'Archive symlink differs')
    return dict(entries=records, skipped=skipped, excluded=excluded, file_bytes=total, archive_bytes=archive.stat().st_size,
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), readback_passed=True,
                filesystem_image=False, deployable=False,
                limitations=['Basic tar metadata and content only; xattrs recorded by digest, not restored',
                             'Hard-link topology is recorded only through source inode numbers, not restored',
                             'APFS object flags, ACLs, protection classes, volume identity and runtime initialization unqualified',
                             'OS directory source is not a complete Data-volume seed'])


def feature_references(value, trail=()):
    found = []
    if isinstance(value, dict):
        if '#IfFeatureFlagEnabled' in value:
            found.append(dict(location=list(trail), feature=value['#IfFeatureFlagEnabled'], then=value.get('#Then'), otherwise=value.get('#Else'), resolved=False))
        for key, child in value.items():
            found.extend(feature_references(child, trail+(str(key),)))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found.extend(feature_references(child, trail+(str(i),)))
    return found
