"""Archive traversal/link rejection and source-derived Data spec controls."""
import argparse, hashlib, io, json, tarfile, tempfile
from pathlib import Path
import linux_data_inputs as M
ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--output',type=Path,required=True); a = cli.parse_args()
    M.need(not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports'),'Fresh report required'); checks = []
    def reject(name,fn):
        try: fn()
        except ValueError: checks.append(dict(name=name,passed=True))
        else: raise AssertionError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='nuwa-data-inputs-') as temp:
        root = Path(temp)
        def archive(path,name,link=False):
            with tarfile.open(path,'w:gz') as output:
                info = tarfile.TarInfo(name); info.size = 3
                if link: info.type=tarfile.SYMTYPE; info.linkname='/outside'; info.size=0
                output.addfile(info,None if link else io.BytesIO(b'src'))
        path = root/'source.tar.gz'; archive(path,'source/file.c'); M.extract_source(path,root/'good')
        assert (root/'good/file.c').read_bytes() == b'src'; checks.append(dict(name='plain archive extracts without Git initialization',passed=True))
        for i,name in enumerate(('source/../../escape','/absolute','source/.git/config','source\\escape')):
            archive(path,name); reject('unsafe archive path '+str(i),lambda i=i:M.extract_source(path,root/str(i)))
        archive(path,'source/link',True); reject('source symlink rejected',lambda:M.extract_source(path,root/'link'))
        reject('existing destination refused',lambda:M.extract_source(path,root/'good'))
    sample = dict(error=None,data_source=dict(readback_passed=True,entries=[dict(path='private/var',type='directory',uid=0,gid=0,mode='0o755'),dict(path='private/var/mobile',type='directory',uid=501,gid=501,mode='0o755'),dict(path='private/var/mobile/Library',type='directory',uid=501,gid=501,mode='0o700')]))
    spec = M.spec_from_os(sample); assert spec['directories'][1] == ['mobile/Library',501,501,'0700'] and not spec['files'] and spec['size_mib'] <= 2048
    checks.append(dict(name='source numeric ownership retained without external preferences',passed=True))
    report = dict(checks=checks,sources=[dict(path='scripts/'+name,sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('linux_data_inputs.py','test-linux-data-inputs.py')],device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n'); print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__=='__main__': main()
