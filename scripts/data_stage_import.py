"""Import explicitly selected source bytes into a fresh POSIX staging tree.

This is not an APFS writer. Compression is materialized as plain file bytes;
unknown xattrs/ACL/protection semantics are rejected, not silently discarded.
"""
import hashlib,os,stat,tarfile
from pathlib import Path,PurePosixPath

def require(ok,message):
 if not ok:raise ValueError(message)

def prepare(archive,records,selected):
 require(len(set(selected))==len(selected),'Duplicate selection')
 index={r['path']:r for r in records};require(len(index)==len(records),'Duplicate source record')
 names=set(selected)|{r['path'] for r in records if r['type']=='directory'}
 require(set(selected)<=set(index),'Unknown selected file');result=[]
 with tarfile.open(archive,'r') as source:
  members=source.getmembers();byname={m.name.rstrip('/'):m for m in members}
  require(len(byname)==len(members),'Duplicate archive member')
  for name in sorted(names,key=lambda n:(n.count('/'),n)):
   p=PurePosixPath(name);require(name.startswith('private/var') and p.parts[:2]==('private','var') and not p.is_absolute() and all(v not in ('..','.','') for v in name.split('/')) and '\\' not in name,'Unsafe path')
   r=index[name];m=byname.get(name);require(m is not None,'Missing archive member')
   require((m.uid,m.gid,m.mode)==(r['uid'],r['gid'],int(r['mode'],8)),'Metadata mismatch')
   require(r.get('xattr_query')=='available_through_host_reader','Unknown source xattrs')
   require(all(x['name']=='com.apple.decmpfs' for x in r.get('xattrs',[])),'Unsupported xattr/ACL/protection metadata')
   require(r['type'] in ('directory','file') and (m.isdir() if r['type']=='directory' else m.isfile()),'Links/special nodes unsupported')
   payload=None
   if r['type']=='file':
    require(name in selected and m.size==r['bytes'] and m.size<=8*1024*1024,'File selection/size')
    with source.extractfile(m) as stream:payload=stream.read()
    require(hashlib.sha256(payload).hexdigest()==r['sha256'],'File digest mismatch')
   if name!='private/var':require(str(p.parent) in names and index[str(p.parent)]['type']=='directory','Missing parent')
   result.append((r,payload))
 return result

def import_stage(archive,records,selected,destination):
 destination=Path(destination);require(destination.parent==Path('/var/tmp') and not destination.exists() and not destination.is_symlink(),'Fresh direct /var/tmp destination required')
 require(os.geteuid()==0,'Numeric owner restoration requires root in isolated WSL staging')
 prepared=prepare(archive,records,selected)
 stage=destination.with_name(destination.name+'.partial');require(not stage.exists() and not stage.is_symlink(),'Fresh partial tree required');stage.mkdir(mode=0o700)
 # Parent remains private to this process/root until commit; no existing tree is traversed.
 (stage/'private').mkdir(mode=0o700);links={};written=[]
 for r,payload in prepared:
  target=stage/r['path']
  if r['type']=='directory':target.mkdir(mode=0o700)
  else:
   key=r['source_inode'];previous=links.get(key)
   if previous:
    require((previous[1]['sha256'],previous[1]['uid'],previous[1]['gid'],previous[1]['mode'])==(r['sha256'],r['uid'],r['gid'],r['mode']),'Hardlink metadata conflict')
    os.link(previous[0],target,follow_symlinks=False)
   else:
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
     with os.fdopen(fd,'wb',closefd=False) as stream:stream.write(payload);stream.flush()
     os.fchown(fd,r['uid'],r['gid']);os.fchmod(fd,int(r['mode'],8));os.fsync(fd)
    finally:os.close(fd)
    links[key]=(target,r)
   require(hashlib.sha256(target.read_bytes()).hexdigest()==r['sha256'],'Readback mismatch');written.append(r['path'])
 # Restore directories last so source read-only/traversal permissions cannot obstruct construction.
 for r,payload in reversed(prepared):
  target=stage/r['path'];os.chown(target,r['uid'],r['gid'],follow_symlinks=False);os.chmod(target,int(r['mode'],8),follow_symlinks=False)
  os.utime(target,ns=(r['mtime_ns'],r['mtime_ns']),follow_symlinks=False)
  st=target.lstat();require((st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))==(r['uid'],r['gid'],int(r['mode'],8)),'Owner/mode readback')
  if r['type']=='directory':
   fd=os.open(target,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
   try:os.fsync(fd)
   finally:os.close(fd)
 os.rename(stage,destination)
 fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return dict(destination=str(destination),directories=sum(r['type']=='directory' for r,_ in prepared),files=written,
  file_encoding='decompressed regular files; decmpfs not copied, no compressed inode flag',
  metadata='uid/gid/mode/mtime and selected hardlink groups; host filesystem only',apfs_imported=False,deployment_ready=False)
