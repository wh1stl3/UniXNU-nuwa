"""Bind iOS16 display requests to native cache bytes and CHECK5 metadata."""
import argparse,hashlib,importlib.util,json,struct,subprocess,sys
from pathlib import Path
import unicorn
import capstone as CS
try: import tomllib
except ImportError:
    import pip._vendor.tomli as tomllib
    sys.modules['tomllib']=tomllib
import aes_origin_inputs as A
from desktop_cache import CacheSet

R=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert a.work.parent==Path('/var/tmp') and not a.work.exists() and not a.output.exists()
    parent=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7/cached-contracts-final.json'; d=json.loads(parent.read_bytes());assert d['passed']
    spec=importlib.util.spec_from_file_location('core',R/'scripts/audit-desktop-core-services.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    assert sha(core.C.TOOL.read_bytes())==core.C.TOOL_SHA
    source=Path(d['source_image']['path']);assert source.stat().st_size==d['source_image']['after']['bytes']
    a.work.mkdir();mounted=False;cache=None;records=[];error=None
    try:
        subprocess.run([str(core.C.TOOL),'-o','ro',str(source),str(a.work)],check=True,capture_output=True);mounted=True
        root=a.work/'root' if (a.work/'root').is_dir() else a.work
        cache=CacheSet(root/'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64');md=CS.Cs(CS.CS_ARCH_ARM64,CS.CS_MODE_ARM)
        for rec in d['records']:
            if not any(k in rec['path'] for k in ('IOSurface.framework','IOMobileFramebuffer.framework')):continue
            for span in rec['code_spans']:assert sha(cache.vmread(span['address'],span['size']))==span['sha256']
            windows=[]
            for call in rec['calls']:
                pc=int(call['pc'],16);start=pc-40;raw=cache.vmread(start,100)
                windows.append(dict(call=call,address=hex(start),bytes=raw.hex(),sha256=sha(raw),instructions=[dict(pc=hex(i.address),instruction=i.mnemonic+' '+i.op_str) for i in md.disasm(raw,start)]))
            functions=[]
            for name in ('_IOMobileFramebufferSwapBegin','_IOMobileFramebufferSwapWait','_IOMobileFramebufferSwapEnd','_IOMobileFramebufferOpen','_IOMobileFramebufferGetMainDisplay','_IOSurfaceClientLookup'):
                if name not in rec['exports']:continue
                addr=int(rec['exports'][name],16);raw=cache.vmread(addr,512)
                functions.append(dict(name=name,address=hex(addr),bytes=raw.hex(),sha256=sha(raw),instructions=[dict(pc=hex(i.address),instruction=i.mnemonic+' '+i.op_str) for i in md.disasm(raw,addr)]))
            records.append(dict(path=rec['path'],windows=windows,functions=functions))
    except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc))
    finally:
        if cache:cache.close()
        if mounted:subprocess.run(['fusermount','-u',str(a.work)],check=True,capture_output=True)
    cleaned=subprocess.run(['mountpoint','-q',str(a.work)],capture_output=True).returncode!=0
    c=A.carrier();meta=A.metadata(c)
    result=dict(passed=error is None and cleaned,error=error,records=records,mount_cleanup_complete=cleaned,parent_sha256=sha(parent.read_bytes()),kernel_sha256=sha(c.raw),
        matching_metadata=[x for x in meta if any(k in str(x.get('CFBundleIdentifier')) for k in ('IOSurface','IOHIDEventDriver'))],
        framebuffer_personality_entries=[x for x in meta if 'IOMobileFramebuffer' in str(x.get('IOKitPersonalities',{}))],
        string_counts={s:c.raw.count(s.encode()) for s in ('IOMobileFramebuffer','IOMobileFramebufferUserClient','NativeLegacyDisplay','IOSurfaceRoot')},
        interpretation='Framebuffer strings remain in the carrier; absent metadata/symbols do NOT prove implementation absence. No native nuwa display subclass identified by this audit.',
        device_accessed=False,script_sha256=sha(Path(__file__).read_bytes()))
    a.output.write_text(json.dumps(result,indent=2)+'\n');assert result['passed'],error;print('PASS display byte binding',sum(len(r['windows']) for r in records),'call windows')
if __name__=='__main__':main()
