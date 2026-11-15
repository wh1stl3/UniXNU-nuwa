"""Cross-platform CHMH path and real host_inputs checks; no device commands."""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('executor', ROOT / 'scripts/run-pmap-ret-once.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
f = M.PROFILES[M.CHMH_PROFILE]['frozen']
relative = f['derived']
tail = '/out/chmh-only-verifier-20261112/record.json'
positive = [relative, relative.replace('/', '\\'),
            '/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa' + tail,
            'D:/Code/PortingiOS/nuwa/UniXNU-nuwa' + tail,
            r'D:\Code\PortingiOS\nuwa\UniXNU-nuwa' + tail.replace('/', '\\')]
negative = ['E:/Code/PortingiOS/nuwa/UniXNU-nuwa' + tail,
            '/mnt/e/Code/PortingiOS/nuwa/UniXNU-nuwa' + tail,
            '/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa-other' + tail,
            'D:/Code/PortingiOS/nuwa/UniXNU-nuwa-other' + tail,
            'out/chmh-only-verifier-20261112/../chmh-only-verifier-20261112/record.json',
            'out/chmh-only-verifier-20261112/other.json',
            '//server/share/record.json', '', None]
for value in positive:
    assert M.chmh_record_path_matches(value, ROOT, relative), repr(value)
for value in negative:
    assert not M.chmh_record_path_matches(value, ROOT, relative), repr(value)

def stopped(fn):
    try:
        fn()
    except M.Stop:
        return
    raise AssertionError('expected host gate refusal')


with patch.object(M.subprocess, 'run', side_effect=AssertionError('device command forbidden')):
    run = M.Run(ROOT, 'chmh-20261112-01', 'forbidden-adb', 'forbidden-fastboot', profile=M.CHMH_PROFILE)
    assert not run.directory.exists()
    run.host_inputs()  # real frozen outer, FAT, ADT, records, sources and r4
    assert not run.directory.exists()
    temp = Path(tempfile.mkdtemp(prefix='chmh-path-test-', dir=ROOT / 'out'))
    fake = M.Run(temp, 'fixture', 'forbidden-adb', 'forbidden-fastboot', profile=M.CHMH_PROFILE)
    fake.check_file = lambda *args: None
    for key in ('derived', 'report', 'audit', 'audit_source'):
        target = temp / f[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / f[key]).read_bytes())
    report_path = temp / f['report']
    report = json.loads(report_path.read_bytes())
    report['record_path'] = str(temp / f['derived'])
    report_path.write_text(json.dumps(report), encoding='utf-8')
    fake.frozen = dict(f, report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
    fake.chmh_inputs()
    other = temp / 'same-content-record.json'
    other.write_bytes((temp / f['derived']).read_bytes())
    report['record_path'] = str(other)
    report_path.write_text(json.dumps(report), encoding='utf-8')
    fake.frozen = dict(fake.frozen, report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
    stopped(fake.chmh_inputs)
    report['record_path'] = str(temp / f['derived'])
    report_path.write_text(json.dumps(report), encoding='utf-8')
    fake.frozen = dict(fake.frozen, report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
    (temp / f['derived']).write_bytes((temp / f['derived']).read_bytes() + b' ')
    stopped(fake.chmh_inputs)
    assert not fake.directory.exists()
print('self-checked real host_inputs and path matrix; device commands=0; run directory absent')
