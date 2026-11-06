"""Bind AES-origin evidence without rebuilding or changing CHECK5."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'reports/desktop-readiness/2026-11-03-offline-mainline-r6'
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bindings=[]
for report,script,count in [('donor-key-origin.json','test-donor-aes-key-origin.py',5),('domain-activation.json','test-native-image4-domain-activation.py',4),('origin-publication-bound.json','audit-aes-origin-publication.py',0)]:
 path=BASE/report;r=json.loads(path.read_bytes());assert r['passed'];assert r['script_sha256']==sha(ROOT/'scripts'/script)
 if count:assert len(r['cases'])==count
 if report=='origin-publication-bound.json':
  assert all(row['donor_code_sha256']==row['check5_code_sha256'] for row in r['family_code_binding'])
  assert r['donor_derivation_table'][10]['parent_selector']==2000
  assert not r['adt_aes_matches']
 bindings.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),cases=count))
frozen=[]
for rel,digest in [('out/ufs-check-5-r1-qualified/boot-ufs-check-5-r1.img','876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540'),('reports/ufs-check-5-r1/offline-qualification-final.json','27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb')]:
 assert sha(ROOT/rel)==digest;frozen.append(dict(path=rel,sha256=digest))
refs=[]
for name,repo,rev,path in [('software-aes','UniXNU/SoftwareAES','4a45326da5c2cd6fe6813d79ee43db20805628af','NativeAES.cpp'),('software-abi','UniXNU/SoftwareAES','4a45326da5c2cd6fe6813d79ee43db20805628af','OriginalAESABI.h'),('unixnu-personality','UniXNU/UniXNU','75bc13dd34dc4e403826793739e316a264ce00dd','patches/xnu/native-aes-personality.patch'),('sheng-board','UniXNU/UniXNU-sheng','a599a1a8a92093b5077543e071b72130769eb325','board.toml'),('xpwn-aes','planetbeing/xpwn','20c32e5c12d1b22a9d55a59a0ff6267f539b77f4','crypto/aes.c')]:
 file=BASE/'references'/(name+'.txt');refs.append(dict(url=f'https://github.com/{repo}/blob/{rev}/{path}',snapshot=str(file.relative_to(ROOT)),sha256=sha(file)))
software=(BASE/'references/software-aes.txt').read_text();assert 'selector == 0' in software and 'if (key->selector ||' in software and 'registerService();' in software
assert '#define kIOAESAcceleratorUIDMask 0x7D0' in (BASE/'references/xpwn-aes.txt').read_text()
local=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeAes/NativeAES.cpp');assert local.read_text().rstrip('\n')==software.rstrip('\n')
sources=[]
for p in [ROOT/'scripts/aes_origin_inputs.py',local,Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/iokit/bsddev/IOKitBSDInit.cpp'),Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/bsd/sys/errno.h')]:sources.append(dict(path=str(p),sha256=sha(p)))
r=dict(passed=True,native_scenarios=9,evidence=bindings,frozen=frozen,public_references=refs,reference_comparison='Local and fetched NativeAES text identical after newline normalization, including final blank line introduced when snapshot saved',source_bindings=sources,
 findings=['2212 derives from hardware selector 2000 and fixed public 16-byte block; constant is not the derived key','native parent error leaves derived slot invalid; actual lookup then fails','native CHECK5 initializer errno 2/84/96 reaches publication of 11 domains, errno 5 panics','CHECK5 retains byte-identical family helper ranges but no selected AppleS8000AES personality or matching ADT node','SoftwareAES startup publishes raw-key service after KAT but rejects 2000/2212; publication alone cannot satisfy nonce path'],
 remaining=['actual platform protected-key capability and nonce verifier/identity contract','runtime provider and active-domain evidence','full nonce initialization including seed creation and full successful AES completion'],
 scope='Offline source, static and instruction models with explicit crypto/IO/service fixtures. No real key extracted or generated, no hardware acceptance, no CHECK3 root cause, target change or new candidate.',script_sha256=sha(Path(__file__)))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS 9 scenarios, 3 byte-identical family ranges, pinned references, frozen CHECK5')