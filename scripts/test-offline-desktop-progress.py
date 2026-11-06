"""Execute fixed framework instructions and reject unsupported Data seed input."""
import argparse, copy, hashlib, importlib.util, json, struct, tempfile
from pathlib import Path
import unicorn as U
from unicorn import arm64_const as A
from linux_data_inputs import validate_directory_only_spec

R=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); assert not a.output.exists()
    source=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7/cached-contracts-final.json'; evidence=json.loads(source.read_bytes()); assert evidence['passed']
    cases=[]
    def machine(window):
        u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM); addr=int(window['address'],16); raw=bytes.fromhex(window['bytes'])
        assert hashlib.sha256(raw).hexdigest()==window['sha256']
        u.mem_map(addr&~4095,((addr+len(raw)+4095)&~4095)-(addr&~4095)); u.mem_write(addr,raw)
        u.mem_map(0x100000,0x10000); u.reg_write(A.UC_ARM64_REG_SP,0x108000); u.reg_write(A.UC_ARM64_REG_LR,0x10f000)
        return u
    def run(u,start,stops,calls=None):
        calls=calls or {}; hit=[]
        def hook(uc,pc,size,data):
            if pc in stops: hit.append(pc); uc.emu_stop()
            elif pc in calls:
                calls[pc](uc); uc.reg_write(A.UC_ARM64_REG_PC,pc+4)
        u.hook_add(U.UC_HOOK_CODE,hook); u.emu_start(start,0,count=2000); assert len(hit)==1; return hit[0]
    w=evidence['code_windows'][0]
    for errno,port,target in ((0,0,0x18dcc7cb4),(0,0xffffffff,0x18dcc7cb4),(0,0x123,0x18dcc7cf4),(5,0x123,0x18dcc7cb4)):
        u=machine(w);u.reg_write(A.UC_ARM64_REG_W0,errno);u.reg_write(A.UC_ARM64_REG_X21,0x100000);u.mem_write(0x100000,struct.pack('<I',port))
        assert run(u,0x18dcc7ca0,{0x18dcc7cb4,0x18dcc7cf4})==target
        cases.append(dict(name='BKS lookup return',errno=errno,port=port,boundary=hex(target)))
    for value,target in ((0,0x1937a0d08),(0x100000,0x1937a0c34)):
        u=machine(evidence['code_windows'][2]);u.reg_write(A.UC_ARM64_REG_X0,value)
        assert run(u,0x1937a0c2c,{0x1937a0d08,0x1937a0c34})==target
        cases.append(dict(name='RBS resource notification connection',connection=value,boundary=hex(target)))
    for errno,stat_result,mode in ((0,0,0o700),(0,0,0o755),(0,5,0),(17,0,0),(13,0,0)):
        u=machine(evidence['code_windows'][3]);u.reg_write(A.UC_ARM64_REG_X0,0x100100);u.mem_write(0x100100,b'/fixture/path\0')
        u.mem_write(0x100200,struct.pack('<I',errno)); seen=[]
        def mkdir(uc):
            assert uc.reg_read(A.UC_ARM64_REG_W1)==0o700; seen.append('mkdir0700'); uc.reg_write(A.UC_ARM64_REG_W0,0xffffffff if errno else 0)
        def err(uc):uc.reg_write(A.UC_ARM64_REG_X0,0x100200)
        def stat(uc):
            uc.mem_write(uc.reg_read(A.UC_ARM64_REG_X1)+4,struct.pack('<H',mode));uc.reg_write(A.UC_ARM64_REG_W0,stat_result);seen.append('metadata-query')
        def chmod(uc):
            assert uc.reg_read(A.UC_ARM64_REG_W1)==0o700;seen.append('mode-repair');uc.reg_write(A.UC_ARM64_REG_W0,0)
        target=run(u,0x18dcbb7b8,{0x10f000,0x18dcbb7f0},{0x18dcbb7d4:mkdir,0x18dcbb7e0:err,0x18dcbb84c:stat,0x18dcbb874:chmod})
        assert target==(0x18dcbb7f0 if errno==13 else 0x10f000)
        if errno!=13: assert u.reg_read(A.UC_ARM64_REG_X0)==0
        assert ('mode-repair' in seen)==(errno==0 and stat_result==0 and mode!=0o700)
        cases.append(dict(name='native private-directory helper',mkdir_errno=errno,metadata_result=stat_result,mode=oct(mode),calls=seen,boundary=hex(target)))
    seed=json.loads((R/'out/linux-data-candidate-20261027-r1/nuwa-data-spec.json').read_bytes()); validate_directory_only_spec(seed)
    rejected=[]
    for name,change in [('files',{'files':[{'path':'db/test'}]}),('acl',{'acl':[]}),('protection',{'protection_class':4}),('links',{'hardlinks':[]}),('escape',{'directories':[['../escape',0,0,'0755']]}),('parent',{'directories':[['missing/child',0,0,'0755']]}),('identity',{'directories':[['db','root',0,'0755']]}),('mode',{'directories':[['db',0,0,'0999']]})]:
        bad=copy.deepcopy(seed);bad.update(change)
        try:validate_directory_only_spec(bad)
        except ValueError:rejected.append(name)
        else:raise AssertionError('Accepted '+name)
    spec=importlib.util.spec_from_file_location('upstream',R.parent/'Toolchain-nuwa/data-seed-20261027/make-data-seed-linux.py'); upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
    with tempfile.TemporaryDirectory(prefix='nuwa-spec-') as temp:
        path=Path(temp)/'spec.json';bad=copy.deepcopy(seed);bad['files']=[{'path':'ignored-file'}];path.write_text(json.dumps(bad))
        _,entries=upstream.load_spec(path);assert len(entries)==len(seed['directories'])
    result=dict(passed=True,native_cases=cases,data_guard=dict(valid_directory_seed=True,rejected=rejected,upstream_ignores_nonempty_files_reproduced=True),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Native code starts at explicit local states; no whole process execution','mkdir, metadata query/mode repair and errno API are fixtures','BKS/RBS stop at real branch boundaries; service availability and caller fatality unproven','Data guard prevents false import claims; it does not implement APFS file/ACL/protection import'],device_accessed=False)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',len(cases),'native cases,',len(rejected),'Data negative cases')

if __name__=='__main__':main()
