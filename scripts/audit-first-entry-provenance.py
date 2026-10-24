"""Offline provenance audit; no device operations or runtime qualification."""
import argparse, hashlib, json, re, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MU='cfb93724a06ff86ff5ba971413368a7809ee42a5'
LOADER='d099354d0eab34df5088ca1ba89c9c88bc3260bb'
GUID='42857F0A-13F2-4B21-8A23-53D3F714B840'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--artifact',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); checks=[]; evidence=[]; sources={}
    def require(name,ok):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok: raise ValueError(name)
    paths={
      'CapsuleService.c':('microsoft/mu_basecore',MU,'MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleService.c'),
      'CapsuleRuntimeDxe.inf':('microsoft/mu_basecore',MU,'MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleRuntimeDxe.inf'),
      'SecurityLockAuditDebugMessageLib.c':('microsoft/mu_basecore',MU,'MdeModulePkg/Library/SecurityLockAuditDebugMessageLib/SecurityLockAuditDebugMessageLib.c'),
      'Entry.S':('UniXNU/DarwinBoot',LOADER,'DarwinBootPkg/Driver/Entry.S'),
      'DarwinBoot.c':('UniXNU/DarwinBoot',LOADER,'DarwinBootPkg/Driver/DarwinBoot.c')}
    for name,(repo,rev,path) in paths.items():
        data=(a.sources/name).read_bytes(); s=data.decode('utf-8-sig'); sources[name]=s
        evidence.append(dict(name=name,sha256=hashlib.sha256(data).hexdigest(),url=f'https://github.com/{repo}/blob/{rev}/{path}',lines=[dict(line=i,text=line.strip()) for i,line in enumerate(s.splitlines(),1) if any(x in line for x in ('LockCapsuleInterface','SECURITY_LOCK_REPORT_EVENT','gEfiEventExitBootServicesGuid','SecurityLock::','SOFTWARE_LOCK','FILE_GUID','DarwinEnter','ExitBootServices','stp w10','br x1'))]))
    require('CI Mu pin',MU in (a.artifact/'submodules-final.txt').read_text())
    require('CI DarwinBoot pin',LOADER in (a.artifact/'unixnu-submodules.log').read_text())
    require('Capsule GUID',GUID in sources['CapsuleRuntimeDxe.inf'])
    require('Software audit event','SECURITY_LOCK_REPORT_EVENT ("Lock Capsule Interface", SOFTWARE_LOCK)' in sources['CapsuleService.c'])
    require('Callback registered at EBS',re.search(r'CreateEventEx\s*\(\s*EVT_NOTIFY_SIGNAL,\s*TPL_NOTIFY,\s*LockCapsuleInterface,\s*NULL,\s*&gEfiEventExitBootServicesGuid',sources['CapsuleService.c']))
    require('Mu implements displayed format','SecurityLock::LockType: %a, Module: %g, Function: %a, Output: %a' in sources['SecurityLockAuditDebugMessageLib.c'])
    require('Source green store before branch',sources['Entry.S'].index('stp w10')<sources['Entry.S'].index('br x1'))
    require('Enter follows successful EBS',re.search(r'ExitBootServices \(mImage, Key\);\s*if \(!EFI_ERROR \(Status\)\) \{\s*DarwinEnter',sources['DarwinBoot.c']))
    build=(a.artifact/'BUILD_REPORT.txt').read_text()
    require('Actual build includes Capsule', 'Module Name:          CapsuleRuntimeDxe' in build and GUID in build)
    require('Actual build links audit lib','/SecurityLockAuditDebugMessageLib/SecurityLockAuditDebugMessageLib.inf' in build)
    fd=(a.artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes()
    package=json.loads((ROOT/'reports/xnu-first-entry/package-01.json').read_text())
    require('FD matches trial',hashlib.sha256(fd).hexdigest()==package['fd_sha256'])
    binary=(a.artifact/'build/AARCH64/DarwinBoot.efi').read_bytes()
    mapping=(a.artifact/'build/AARCH64/DarwinBootPkg/Driver/DarwinBoot/DEBUG/DarwinBoot.map').read_text()
    match=re.search(r'^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+1\s+.*\.text.DarwinEnter',mapping,re.M)
    require('Actual entry located',match)
    rva,length=(int(x,16) for x in match.groups()); h=struct.unpack_from('<I',binary,60)[0]
    count=struct.unpack_from('<H',binary,h+6)[0]; opt=struct.unpack_from('<H',binary,h+20)[0]
    sections=[struct.unpack_from('<4I',binary,h+24+opt+40*i+8) for i in range(count)]
    sec=next(s for s in sections if s[1]<=rva and rva+length<=s[1]+s[2]); off=sec[3]+rva-sec[1]; code=binary[off:off+length]
    sys.path.insert(0,str(ROOT/'out/python-tools')); import capstone
    ins=list(capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_LITTLE_ENDIAN).disasm(code,rva))
    require('Full body decoded',sum(i.size for i in ins)==length)
    store=next(i.address for i in ins if i.mnemonic=='stp' and i.op_str.startswith('w10, w10,'))
    branch=next(i.address for i in ins if i.mnemonic=='br' and i.op_str=='x1')
    require('Actual green store before kernel branch',store<branch)
    result=dict(scope='Static provenance only; no XNU execution proof',checks=checks,sources=evidence,fd_sha256=hashlib.sha256(fd).hexdigest(),loader_sha256=hashlib.sha256(binary).hexdigest(),darwin_enter=dict(rva=hex(rva),bytes=length,sha256=hashlib.sha256(code).hexdigest(),instructions=[dict(address=hex(i.address),mnemonic=i.mnemonic,operands=i.op_str) for i in ins]))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(checks=len(checks),passed=True,report=str(a.output))))
if __name__=='__main__': main()
