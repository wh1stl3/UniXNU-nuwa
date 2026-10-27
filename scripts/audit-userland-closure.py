"""Offline restore executable closure and launch inventory; never runs image code.

Page digests establish byte integrity only, not CMS trust or kernel acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT/'out/root-mainline-v29/restore/restore-payload.bin'
IMAGE_SHA = 'd180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a'
TOOL = Path('/mnt/d/Code/PortingiOSLegacy/common/tools/apfs-fuse-linux/bin/apfs-fuse')
TOOL_SHA = '4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922'
DYLIBS = {0xc, 0x80000018, 0x8000001f, 0x80000023}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def need(ok, message):
    if not ok:
        raise ValueError(message)

def rooted(root, name):
    """Resolve absolute image symlinks inside the image, never against the host."""
    need(name.startswith('/'), 'Absolute image path required')
    pending = name.split('/'); parts = []; links = 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            need(bool(parts), 'Image root escape')
            parts.pop(); continue
        p = root.joinpath(*parts, part)
        st = p.lstat()
        if stat.S_ISLNK(st.st_mode):
            links += 1; need(links <= 40, 'Symlink loop')
            target = os.readlink(p)
            if target.startswith('/'):
                parts = []
            pending = target.split('/') + pending
        else:
            parts.append(part)
    return root.joinpath(*parts)

def signatures(raw, offset, size):
    need(size >= 12 and offset + size <= len(raw), 'Signature bounds')
    blob = raw[offset:offset+size]
    magic, length, count = struct.unpack_from('>III', blob)
    need(magic == 0xfade0cc0 and 12 <= length <= size and count <= (length-12)//8, 'Signature superblob')
    records = []
    for i in range(count):
        kind, at = struct.unpack_from('>II', blob, 12+i*8)
        need(12+count*8 <= at <= length-8, 'Signature child offset')
        tag, n = struct.unpack_from('>II', blob, at)
        need(8 <= n <= length-at, 'Signature child length')
        if tag != 0xfade0c02:
            continue
        cd = blob[at:at+n]; need(n >= 44, 'Short CodeDirectory')
        version, flags, hashes, ident, special, slots, limit = struct.unpack_from('>7I', cd, 8)
        width, algorithm, platform, shift = struct.unpack_from('4B', cd, 36)
        need(44 <= ident < n and b'\0' in cd[ident:], 'CodeDirectory identifier')
        record = dict(slot=kind, version=hex(version), flags=hex(flags), platform=platform,
                      code_slots=slots, hash_type=algorithm, page_shift=shift,
                      identifier=cd[ident:].split(b'\0', 1)[0].decode('utf-8'))
        if version >= 0x20300:
            need(n >= 64, 'Short 64-bit CodeDirectory')
            limit64 = struct.unpack_from('>Q', cd, 56)[0]
            if limit == 0xffffffff:
                limit = limit64
        scatter = struct.unpack_from('>I', cd, 44)[0] if version >= 0x20100 and n >= 48 else 0
        need(shift <= 30 and 0 < limit <= offset, 'CodeDirectory code limit')
        need(width > 0 and hashes >= special*width and hashes+slots*width <= n, 'CodeDirectory hash bounds')
        if scatter or algorithm not in (1, 2, 3, 4):
            record['page_integrity'] = 'unsupported scatter or algorithm'
        else:
            method = {1:'sha1', 2:'sha256', 3:'sha256', 4:'sha384'}[algorithm]
            need(width == {1:20, 2:32, 3:20, 4:48}[algorithm], 'CodeDirectory digest width')
            page = (1 << shift) if shift else limit
            need(slots == (limit+page-1)//page, 'CodeDirectory slot count')
            for j in range(slots):
                actual = hashlib.new(method, raw[j*page:min(limit,(j+1)*page)]).digest()[:width]
                need(actual == cd[hashes+j*width:hashes+(j+1)*width], f'Code page mismatch {j}')
            record.update(page_integrity='matched', code_limit=limit)
        records.append(record)
    return records

def macho(raw):
    need(len(raw) >= 32, 'Short Mach-O')
    magic, cpu, sub, kind, count, size, flags, reserved = struct.unpack_from('<8I', raw)
    need(magic == 0xfeedfacf and count <= 1024 and 32+size <= len(raw), 'Mach-O header bounds')
    cursor = 32; segments = []; deps = []; entries = []; codes = []; loader = None
    for _ in range(count):
        need(cursor+8 <= 32+size, 'Load command header')
        cmd, length = struct.unpack_from('<II', raw, cursor)
        need(length >= 8 and length % 8 == 0 and cursor+length <= 32+size, 'Load command bounds')
        if cmd in DYLIBS or cmd == 0xe:
            need(length >= (24 if cmd in DYLIBS else 12), 'Short path command')
            at = struct.unpack_from('<I', raw, cursor+8)[0]
            need((24 if cmd in DYLIBS else 12) <= at < length, 'Path offset')
            text = raw[cursor+at:cursor+length]; need(b'\0' in text, 'Unterminated path')
            path = text.split(b'\0',1)[0].decode('utf-8')
            if cmd == 0xe:
                need(loader is None, 'Duplicate dylinker'); loader = path
            else:
                deps.append(dict(path=path, weak=cmd==0x80000018, command=hex(cmd)))
        elif cmd == 0x19:
            need(length >= 72, 'Short segment')
            name, va, vs, off, fs, maximum, initial, sections, sf = struct.unpack_from('<16s4Q4I',raw,cursor+8)
            need(length == 72+80*sections and off+fs <= len(raw) and fs <= vs, 'Segment extent')
            need(initial & ~maximum == 0 and va+vs <= 1<<64, 'Segment protection or address')
            segments.append(dict(name=name.rstrip(b'\0').decode(), vmaddr=va, vmsize=vs, fileoff=off, filesize=fs, maxprot=maximum, initprot=initial))
        elif cmd == 0x80000028:
            need(length == 24, 'LC_MAIN size')
            entry, stack = struct.unpack_from('<QQ', raw, cursor+8)
            entries.append(dict(kind='LC_MAIN', file_offset=entry, stack_size=stack))
        elif cmd == 5:
            pos = cursor+8
            while pos < cursor+length:
                need(pos+8 <= cursor+length, 'Thread state header')
                flavor, words = struct.unpack_from('<II',raw,pos); pos += 8
                need(pos+words*4 <= cursor+length, 'Thread state extent')
                if flavor == 6:
                    need(words == 68, 'ARM64 thread state length')
                    entries.append(dict(kind='LC_UNIXTHREAD', pc=struct.unpack_from('<Q',raw,pos+256)[0]))
                pos += words*4
        elif cmd == 0x1d:
            need(length == 16, 'Code signature command')
            off, n = struct.unpack_from('<II',raw,cursor+8); codes.extend(signatures(raw,off,n))
        cursor += length
    need(cursor == 32+size, 'Unconsumed load command bytes')
    for i, left in enumerate(segments):
        for right in segments[i+1:]:
            need(not (left['vmsize'] and right['vmsize'] and max(left['vmaddr'],right['vmaddr']) < min(left['vmaddr']+left['vmsize'],right['vmaddr']+right['vmsize'])), 'Overlapping VM segments')
    for entry in entries:
        if entry['kind'] == 'LC_MAIN':
            entry['executable_segment'] = any(s['initprot'] & 4 and s['fileoff'] <= entry['file_offset'] < s['fileoff']+s['filesize'] for s in segments)
        else:
            entry['executable_segment'] = any(s['initprot'] & 4 and s['vmaddr'] <= entry['pc'] < s['vmaddr']+s['filesize'] for s in segments)
        need(entry['executable_segment'], 'Entry outside executable file-backed segment')
    return dict(cpu=hex(cpu), subtype=hex(sub), filetype=kind, flags=hex(flags), segments=segments, dependencies=deps, dylinker=loader, entries=entries, code_directories=codes)

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True); cli.add_argument('--mount',type=Path,required=True)
    args=cli.parse_args(); output=args.output.resolve(); mount=args.mount.resolve()
    need(os.name!='nt' and output.is_relative_to(ROOT/'reports') and not output.exists(), 'Fresh WSL report required')
    need(mount.parent==Path('/var/tmp') and not mount.exists(), 'Fresh /var/tmp mount required')
    need(sha(IMAGE.read_bytes())==IMAGE_SHA and sha(TOOL.read_bytes())==TOOL_SHA, 'Pinned inputs changed')
    commands=[]; mounted=False; files={}; services=[]; cache_files=[]
    def run(argv):
        p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=90)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)); p.check_returncode()
    mount.mkdir()
    try:
        run([TOOL,'-o','ro',IMAGE,mount]); mounted=True
        run(['mountpoint','-q',mount]); root=mount/'root' if (mount/'root').is_dir() else mount
        for folder in ('/System/Library/LaunchDaemons','/Library/LaunchDaemons'):
            try: directory=rooted(root,folder)
            except FileNotFoundError: continue
            for path in sorted(directory.glob('*.plist')):
                p=rooted(root,folder+'/'+path.name); raw=p.read_bytes(); need(len(raw)<131072,'Plist size')
                obj=plistlib.loads(raw); argslist=obj.get('ProgramArguments',[])
                program=obj.get('Program') or (argslist[0] if argslist else None)
                services.append(dict(path=folder+'/'+path.name,sha256=sha(raw),properties=obj,program=program))
        queue=['/sbin/launchd','/usr/lib/dyld']; edges=[]
        while queue:
            name=queue.pop(0)
            if name in files: continue
            need(len(files)<256,'Dependency closure limit')
            if not name.startswith('/'):
                files[name]=dict(status='unresolved dyld token'); continue
            try: path=rooted(root,name)
            except FileNotFoundError: files[name]=dict(status='missing standalone file; shared-cache membership not established'); continue
            st=path.stat(); need(stat.S_ISREG(st.st_mode) and st.st_size<32*1024*1024,'Executable type or size')
            raw=path.read_bytes(); info=macho(raw)
            files[name]=dict(status='parsed',resolved='/'+path.relative_to(root).as_posix(),sha256=sha(raw),bytes=len(raw),mode=oct(st.st_mode),uid=st.st_uid,gid=st.st_gid,macho=info)
            if info['dylinker']: queue.append(info['dylinker'])
            for dep in info['dependencies']:
                edges.append(dict(source=name,**dep)); queue.append(dep['path'])
        for service in services:
            program=service['program']
            if program and program.startswith('/'):
                try: p=rooted(root,program); service['program_file']=dict(exists=True,mode=oct(p.stat().st_mode),bytes=p.stat().st_size)
                except FileNotFoundError: service['program_file']=dict(exists=False)
        try: cache=rooted(root,'/System/Library/Caches/com.apple.dyld')
        except FileNotFoundError: cache=None
        if cache:
            cache_files=[dict(name=p.name,bytes=p.stat().st_size) for p in sorted(cache.iterdir()) if p.is_file()]
    finally:
        if mounted: run(['fusermount','-u',mount])
    need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0,'Mount remains active')
    need(sha(IMAGE.read_bytes())==IMAGE_SHA,'Image modified')
    result=dict(image_sha256=IMAGE_SHA,tool_sha256=TOOL_SHA,script_sha256=sha(Path(__file__).read_bytes()),commands=commands,files=files,edges=edges,services=services,dyld_cache_files=cache_files,mount_cleaned_up=True,device_accessed=False,userland_executed=False,release_guard_changed=False,limitations=['Host read-only APFS extraction, not native XNU read/decompression','Code page hashes do not establish CMS trust, entitlements or AMFI acceptance','Dependency presence does not prove symbol binding, dyld execution or hardware readiness','Launch inventory does not approve restore services or release guard removal'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2,default=str).encode()+b'\n')
    print(json.dumps(dict(files=len(files),services=len(services),unresolved=[k for k,v in files.items() if v['status']!='parsed'],output=str(output))))

if __name__=='__main__': main()
