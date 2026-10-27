"""Source-archive boundaries and readback without host extraction."""
import argparse, hashlib, json, os, tempfile
from pathlib import Path
import desktop_data_source as D
ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--output',type=Path,required=True); a = cli.parse_args()
    D.need(not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports'),'Fresh report required'); checks = []
    def reject(name, action):
        try:
            action()
        except ValueError:
            checks.append(dict(name=name,passed=True))
        else:
            raise AssertionError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='nuwa-data-source-') as temp:
        root = Path(temp); source = root/'var'; source.mkdir(); (source/'mobile').mkdir(); (source/'mobile/item').write_bytes(b'fixture')
        (source/'absolute').symlink_to('/outside'); (source/'relative').symlink_to('../../outside')
        before = (source/'mobile/item').stat(); result = D.export_tree(source, root/'source.tar')
        assert result['readback_passed'] and result['file_bytes'] == 7 and not result['deployable']; checks.append(dict(name='content/basic metadata actual archive readback',passed=True))
        assert len([r for r in result['entries'] if r['type']=='symlink']) == 2; checks.append(dict(name='absolute and relative links stored without following',passed=True))
        after = (source/'mobile/item').stat()
        assert all(getattr(after,k)==getattr(before,k) for k in ('st_size','st_mode','st_uid','st_gid','st_mtime_ns'))
        checks.append(dict(name='source content metadata unchanged',passed=True))
        reject('existing archive rejected',lambda:D.export_tree(source,root/'source.tar'))
        reject('byte budget enforced',lambda:D.export_tree(source,root/'small.tar',max_bytes=1))
        reject('entry budget enforced',lambda:D.export_tree(source,root/'short.tar',max_entries=1))
        os.mkfifo(source/'fifo'); skipped = D.export_tree(source,root/'special.tar')
        assert len(skipped['skipped']) == 1; checks.append(dict(name='special node recorded without materialization',passed=True))
        scoped = D.export_tree(source,root/'scoped.tar',excluded_prefixes=('private/var/mobile',))
        assert scoped['file_bytes'] == 0 and len(scoped['excluded']) == 1
        checks.append(dict(name='explicit excluded subtree inventoried without copying',passed=True))
        refs = D.feature_references({'ProgramArguments':['/x',{'#IfFeatureFlagEnabled':'domain/flag','#Then':'--a','#Else':'--b'}]})
        assert refs[0]['feature'] == 'domain/flag' and not refs[0]['resolved']; checks.append(dict(name='feature branches retained without selecting a runtime value',passed=True))
    report = dict(checks=checks,sources=[dict(path='scripts/'+name,sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('desktop_data_source.py','test-desktop-data-source.py')],device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__ == '__main__':
    main()
