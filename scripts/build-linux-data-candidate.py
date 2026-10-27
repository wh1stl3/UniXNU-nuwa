"""Build a source-derived APFS Data host candidate using the pinned fajita method.

No git operations, board edits, device access or kernel integration. The new
filesystem is not accepted as an iOS16 runtime seed by these host checks alone.
"""
import argparse, datetime, hashlib, importlib.util, json, os, stat, subprocess, sys, uuid
from pathlib import Path
from linux_data_inputs import need, spec_from_os
ROOT=Path(__file__).resolve().parents[1]
DEPS=ROOT.parent/'Toolchain-nuwa/data-seed-20261027'
PACKER=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/DarwinBoot/Test/packed_ramdisk.py')
APFS=Path('/mnt/d/Code/PortingiOSLegacy/common/tools/apfs-fuse-linux/bin/apfs-fuse')
UTIL=APFS.with_name('apfsutil')
APFS_SHA='4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922'
UTIL_SHA='1ad246148909835c180cd06bfa47c58c2f199a1ffe40e6103bcca3163aa8eddb'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--work',type=Path,required=True); p.add_argument('--mount',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    work=a.work.resolve(); mount=a.mount.resolve(); output=a.output.resolve()
    need(os.name!='nt' and work.is_relative_to(ROOT/'out') and not work.exists() and mount.parent==Path('/var/tmp') and not mount.exists(),'Fresh host candidate paths required')
    need(output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh report required')
    parent_path=ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json'; parent_raw=parent_path.read_bytes(); parent=json.loads(parent_raw)
    qualification_path=ROOT/'reports/desktop-readiness/2026-10-27-contract-r1/qualification-r2.json'; qualification=json.loads(qualification_path.read_bytes())
    need(any(e['path'].replace('\\','/')==str(parent_path.relative_to(ROOT)) and e['sha256']==hashlib.sha256(parent_raw).hexdigest() for e in qualification['evidence']),'OS source metadata binding differs')
    tool_path=ROOT/'reports/desktop-readiness/2026-10-27-data-linux-r1/tools.json'; tool_raw=tool_path.read_bytes(); tools=json.loads(tool_raw)
    for value in tools['binaries'].values(): need(sha(Path(value['path']))==value['sha256'],'Host tool changed')
    dependencies_path=ROOT/tools['dependencies']['path']; dependencies_raw=dependencies_path.read_bytes()
    need(hashlib.sha256(dependencies_raw).hexdigest()==tools['dependencies']['sha256'],'Dependency manifest differs')
    for value in json.loads(dependencies_raw): need(sha(DEPS/Path(value['path'].replace('\\','/')).name)==value['sha256'],'Dependency source changed')
    need(sha(APFS)==APFS_SHA and sha(UTIL)==UTIL_SHA,'Independent APFS reader changed')
    original_packer_sha=sha(PACKER); work.mkdir(); mount.mkdir(); spec=spec_from_os(parent)
    spec_path=work/'nuwa-data-spec.json'; spec_path.write_bytes(json.dumps(spec,indent=2).encode()+b'\n')
    # The old locally pinned packer already hashes <=2GiB disks densely. The
    # compatibility alias supplies the newer builder's explicit threshold API.
    shim=work/'packer-compat.py'
    shim.write_text('import importlib.util,hashlib\nfrom pathlib import Path\np=Path('+repr(str(PACKER))+')\nassert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(original_packer_sha)+'\ns=importlib.util.spec_from_file_location("local_packer",p)\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\npack=m.pack\nregions=m.regions\nPLAIN_HASH_LIMIT=m.MAX_LOGICAL\n',encoding='utf-8')
    volume=str(uuid.uuid5(uuid.NAMESPACE_URL,'nuwa/20H392/host-data-candidate/'+hashlib.sha256(spec_path.read_bytes()).hexdigest())).upper()
    container=str(uuid.uuid5(uuid.NAMESPACE_URL,'nuwa/20H392/host-data-container/'+volume)).upper()
    timestamp=int(datetime.datetime(2026,10,27,tzinfo=datetime.timezone.utc).timestamp())
    commands=[]; mounted=False; error=None; result={}
    def run(argv,name,timeout=240):
        log=work/(name+'.txt')
        with log.open('x') as stream:
            child=subprocess.run([str(v) for v in argv],stdout=stream,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        commands.append(dict(argv=[str(v) for v in argv],exit_code=child.returncode,log=str(log.relative_to(ROOT)),sha256=sha(log)))
        (work/'commands.json').write_bytes(json.dumps(commands,indent=2).encode()+b'\n'); child.check_returncode(); return log.read_text(errors='replace')
    try:
        reports=[]
        for name in ('build-a','build-b'):
            print(json.dumps(dict(phase=name,logical_mib=spec['size_mib'],directories=len(spec['directories']))),flush=True)
            directory=work/name; need(not directory.exists(),'Fresh builder output required')
            run([sys.executable,'-B','-I',DEPS/'make-data-seed-linux.py','--packer',shim,'--spec',spec_path,'--out',directory,
                 '--apfsprogs',tools['source_directory'],'--volume-uuid',volume,'--container-uuid',container,'--timestamp',timestamp,'--keep-raw'],name)
            report=json.loads((directory/'data-linux.json').read_bytes()); reports.append(report)
            need(report['logical_bytes']==1024**3 and report['volume_uuid']==volume and report['role_value']=='0x0' and not report['encrypted'],'Candidate volume properties differ')
        need(reports[0]['raw_sha256']==reports[1]['raw_sha256'] and reports[0]['packed_sha256']==reports[1]['packed_sha256'],'Independent fresh outputs differ')
        raw=work/'build-a/data-linux.raw'; packed=work/'build-a/data-linux.dbr'
        before=sha(raw); need(before==reports[0]['raw_sha256'] and sha(packed)==reports[0]['packed_sha256'],'Candidate file digest differs')
        text=run([UTIL,raw],'independent-volume')
        need(volume in text and 'No specific role' in text and 'Case-sensitive' in text,'Independent volume identity differs')
        run([APFS,'-o','ro',raw,mount],'independent-mount'); mounted=True; run(['mountpoint','-q',mount],'mountpoint')
        root=mount/'root' if (mount/'root').is_dir() else mount; actual=[]
        for path,uid,gid,mode in spec['directories']:
            # The specification contains only validated relative directory paths.
            st=(root/path).lstat()
            need(stat.S_ISDIR(st.st_mode) and (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))==(uid,gid,int(mode,8)),'Independent directory metadata differs: '+path)
            actual.append(dict(path=path,uid=st.st_uid,gid=st.st_gid,mode=oct(stat.S_IMODE(st.st_mode))))
        run(['fusermount','-u',mount],'independent-unmount'); mounted=False
        need(sha(raw)==before,'Read-only candidate changed')
        parser=importlib.util.spec_from_file_location('packed_candidate',shim); module=importlib.util.module_from_spec(parser); parser.loader.exec_module(module)
        logical,regions=module.regions(packed.read_bytes())
        resident=sum(sum(any(data[i:i+4096]) for i in range(0,len(data),4096))*4096 for _,data in regions)
        result.update(candidate=reports[0],reproduction=reports[1],independent_directories=actual,
                      packed_format=dict(logical_bytes=logical,packed_bytes=packed.stat().st_size,extents=len(regions),nonzero_page_bytes=resident,
                                         pointer_table_bytes=logical//4096*8,input_owned_until_reboot=True),
                      raw_path=str(raw.relative_to(ROOT)),packed_path=str(packed.relative_to(ROOT)))
        print(json.dumps(dict(phase='complete',volume_uuid=volume,packed_bytes=packed.stat().st_size,independent_directories=len(actual),reproduced=True)),flush=True)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc))
    finally:
        if mounted: run(['fusermount','-u',mount],'cleanup-unmount')
        need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0,'Data mount remains active')
    need(sha(PACKER)==original_packer_sha,'Read-only packer changed')
    result.update(error=error,mount_cleanup_complete=True,volume_uuid=volume,container_uuid=container,timestamp=timestamp,
                  spec=dict(path=str(spec_path.relative_to(ROOT)),sha256=sha(spec_path)),commands=commands,
                  original_packer=dict(path=str(PACKER),sha256=original_packer_sha,git_metadata_read=False),
                  parents=[dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest()) for path,raw in ((parent_path,parent_raw),(tool_path,tool_raw),(dependencies_path,dependencies_raw))],
                  sources=[dict(path='scripts/'+name,sha256=sha(ROOT/'scripts'/name)) for name in ('linux_data_inputs.py','build-linux-data-candidate.py')],
                  device_accessed=False,kernel_linked=False,ios16_runtime_accepted=False,deployed=False,release_guard_changed=False,
                  limitations=['Host APFS and packed-format candidate only; no iOS16/runtime/driver ABI qualification','Directory metadata only; original files, protection classes, migrations and runtime-created contents remain unqualified','No board size/identity, persistent store, Setup state, watchdog or authentication policy changes'])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    need(error is None,'Data candidate build failed: '+str(error))


if __name__=='__main__': main()
