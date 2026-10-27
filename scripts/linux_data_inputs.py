"""Safe archive intake and a Data directory spec traced to fixed iOS16 metadata."""
import json, shutil, tarfile
from pathlib import Path, PurePosixPath


def need(ok,message):
    if not ok:
        raise ValueError(message)


def extract_source(archive,destination):
    need(not destination.exists(),'Fresh dependency destination required')
    with tarfile.open(archive,'r:gz') as source:
        members = source.getmembers(); need(0 < len(members) <= 10000,'Archive entry budget')
        roots = set(); total = 0
        for member in members:
            name = member.name.rstrip('/'); path = PurePosixPath(name)
            need(not path.is_absolute() and '\\' not in name and ':' not in name and all(p not in ('..','.git') for p in path.parts),'Unsafe source archive path')
            need(member.isdir() or member.isfile(),'Source links/special nodes refused'); roots.add(path.parts[0])
            total += member.size; need(total <= 64*1024*1024,'Archive byte budget')
        need(len(roots) == 1,'Single archive root required'); destination.mkdir(parents=True)
        for member in members:
            relative = PurePosixPath(member.name).parts[1:]
            if not relative:
                continue
            target = destination.joinpath(*relative); need(target.resolve().is_relative_to(destination.resolve()),'Archive destination escape')
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with source.extractfile(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src,dst,1024*1024)
                target.chmod(member.mode & 0o777)
    need(not (destination/'.git').exists(),'Dependency must not be a Git repository')


def spec_from_os(source_report):
    need(source_report['error'] is None and source_report['data_source']['readback_passed'],'OS directory evidence incomplete')
    entries = source_report['data_source']['entries']; root = next(v for v in entries if v['path']=='private/var')
    need((root['uid'],root['gid'],int(root['mode'],8)) == (0,0,0o755),'Builder root metadata differs from source')
    directories = []
    for item in entries:
        if item['type'] != 'directory' or item['path']=='private/var':
            continue
        need(item['path'].startswith('private/var/'),'Unexpected source root')
        path = item['path'][len('private/var/'):]
        need(path.isascii() and all(p not in ('','.','..') for p in path.split('/')),'Unsupported directory name')
        directories.append([path,item['uid'],item['gid'],f"{int(item['mode'],8):04o}"])
    directories.sort(key=lambda v:(v[0].count('/'),v[0]))
    need(directories and len({v[0] for v in directories}) == len(directories),'Directory set differs')
    return dict(comment='Host candidate only: numeric directory metadata from fixed 20H392 OS; not a runtime-qualified Data seed',
                size_mib=1024,volume_name='Data',case_sensitive=True,role='none',directories=directories,files=[])
