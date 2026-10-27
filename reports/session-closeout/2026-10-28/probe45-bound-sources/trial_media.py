"""Prepare local per-trial media folders before any device preflight query."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def prepare(package, *, media_root=None):
    if package.get('approval')!='XNU-FIRST-ENTRY-ANALYSIS':
        raise ValueError('XNU trial package required')
    title=package['fat_detail']['config']['entry'][0]['title']
    probes=re.findall(r'\bPROBE\s+([0-9]+)\b',title,re.IGNORECASE)
    revisions=re.findall(r'\bR([0-9]+)\b',title,re.IGNORECASE)
    if len(probes)!=1 or len(revisions)>1:
        raise ValueError('Unambiguous probe title required for media directory')
    label='PROBE'+str(int(probes[0]))+('-r'+str(int(revisions[0])) if revisions else '')
    root=Path(media_root) if media_root is not None else ROOT.parent/'Media-nuwa'
    root=root.absolute()
    # Do not follow redirected directories outside the intended media tree.
    if root.resolve()!=root:
        raise ValueError('Media root redirects')
    paths=[root/label,root/label/'original',root/label/'derived']
    for path in paths:
        if path.resolve()!=path or (path.exists() and not path.is_dir()):
            raise ValueError('Media directory redirects or conflicts with a file')
    for path in paths:path.mkdir(parents=True,exist_ok=True)
    return dict(round=label,original=str(paths[1]),derived=str(paths[2]),existing_files_preserved=True)
