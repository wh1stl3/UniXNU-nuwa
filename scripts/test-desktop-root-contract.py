"""Geometry, missing-capacity and launch declaration regression controls."""
import argparse, hashlib, json, plistlib, struct, tempfile
from pathlib import Path
import desktop_root_contract as D
ROOT = Path(__file__).resolve().parents[1]


def udif(path, first=0, count=1, stored=512):
    mish = bytearray(244); mish[:4] = b'mish'; struct.pack_into('>Q', mish, 8, first)
    struct.pack_into('>I', mish, 200, count); struct.pack_into('>IIQQQQ', mish, 204, 1, 0, 0, 1, 0, stored)
    meta = plistlib.dumps({'resource-fork':{'blkx':[{'Data':bytes(mish)}]}})
    trailer = bytearray(512); trailer[:4] = b'koly'; struct.pack_into('>II', trailer, 4, 4, 512)
    struct.pack_into('>QQ', trailer, 24, 0, 512); struct.pack_into('>QQ', trailer, 216, 512, len(meta))
    struct.pack_into('>Q', trailer, 492, first+1)
    path.write_bytes(b'A'*512+meta+trailer)


def main():
    cli = argparse.ArgumentParser(description=__doc__); cli.add_argument('--output', type=Path, required=True); a = cli.parse_args()
    D.need(not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports'), 'Fresh reports path required')
    checks = []
    def passed(name):
        checks.append(dict(name=name, passed=True))
    def reject(name, action):
        try:
            action()
        except ValueError:
            passed(name)
        else:
            raise AssertionError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='nuwa-root-contract-') as directory:
        path = Path(directory)/'image'; udif(path)
        assert D.geometry(path)['raw_bytes'] == 512; passed('UDIF logical disk differs from stored file length')
        udif(path, first=1); reject('UDIF logical gap rejected', lambda:D.geometry(path))
        udif(path, count=2); reject('UDIF chunk table overflow rejected', lambda:D.geometry(path))
        udif(path, stored=1024); reject('UDIF stored extent rejected', lambda:D.geometry(path))
        path.write_bytes(b'R'*1024); assert D.geometry(path)['raw_bytes'] == 1024; passed('raw aligned image geometry')
        path.write_bytes(b'R'*513); reject('raw sector misalignment rejected', lambda:D.geometry(path))
    components = [dict(name='OS',component='OS',raw_bytes=512),dict(name='SystemOS',component='Cryptex1,SystemOS',raw_bytes=2 << 20)]
    plan = D.windows(components); assert plan['image_bytes'] == 4 << 20 and plan['capacity_fit'] is None and not plan['deployable']; passed('aligned preview never invents target capacity')
    reject('undersized target rejected', lambda:D.windows(components, 3 << 20))
    reject('duplicate window rejected', lambda:D.windows(components+[components[0]]))
    cfg = {'LaunchDaemons':{
        'first':{'Label':'first','Program':'/bin/first','UserName':'mobile','MachServices':{'port':True},'Sockets':{'one':[{'SockPathName':'/var/run/example'}]},'KeepAlive':{'OtherJobEnabled':{'second':True},'PathState':{'/var/db/flag':True}}},
        'second':{'Label':'second','ProgramArguments':['/bin/second'],'MachServices':{'port':{'ResetAtClose':True}}}}}
    result = D.contract(cfg)
    assert len(result['jobs']) == 2 and 'port' in result['duplicate_service_declarations']
    assert not result['explicit_job_conditions'][0]['startup_dependency']; passed('provider duplicates and keepalive conditions do not invent startup edges')
    assert len(result['path_references']) == 2; passed('nested socket and path-state references retained')
    assert not any(j['enabled_for_deployment'] for j in result['jobs']); passed('inventory never enables jobs')
    special = D.contract({'Label':'typed','ProgramArguments':['/bin/typed',7]})['jobs'][0]
    assert special['non_string_arguments'] == [dict(index=1,type='int',value=7)] and not special['argument_expansion_resolved']
    binary = D.contract({'Label':'binary','ProgramArguments':['/bin/typed',b'fixture']})['jobs'][0]
    assert binary['non_string_arguments'][0]['value']['plist_type'] == 'data'
    json.dumps(binary)
    passed('non-string arguments retained as unresolved instead of coerced')
    reject('wrong path array type rejected', lambda:D.contract({'Label':'x','Program':'/x','WatchPaths':'/var/x'}))
    users = D.identities('mobile:SHOULD_NOT_APPEAR:501:501::/var/mobile:/bin/sh\nnobody:*:-2:-2::/var/empty:/usr/bin/false\n')
    assert users['records']['mobile']['uid'] == 501 and users['records']['nobody']['uid'] == 0xfffffffe
    assert 'SHOULD_NOT_APPEAR' not in json.dumps(users); passed('numeric identities preserve signed sentinels and omit password column')
    out = dict(checks=checks, sources=[dict(path='scripts/'+name,sha256=hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()) for name in ('desktop_root_contract.py','test-desktop-root-contract.py')], device_accessed=False)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_bytes(json.dumps(out,indent=2).encode()+b'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))


if __name__ == '__main__':
    main()
