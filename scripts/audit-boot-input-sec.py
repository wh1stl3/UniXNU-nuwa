"""Compare actual successful-probe and failed-audit SEC images, including reproducible build time."""
import sys,importlib.util,hashlib,struct,json
from datetime import datetime,timezone
from pathlib import Path
r=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('reader',r/'scripts/ci/inspect-firmware-candidate.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
records=[];bodies=[];times=[]
expected={39988591973:"70b266b3355716dd82bc7120a908334db00b6290be1b69584bfbd1b3f3a3376b",39995937843:"bfb02a6334f201778467ecc1f1a9042396dc1a3dcd2014c8c4118b88664f106b"}
for run in (39988591973,39995937843):
 capture=[];original=m.heap_descriptors
 def hook(data):capture.append(data);return original(data)
 m.heap_descriptors=hook
 fd=(r/f'out/firmware-ci/{run}/nuwa-firmware-{run}/build/FV/SILICIUM_UEFI.fd').read_bytes()
 if hashlib.sha256(fd).hexdigest()!=expected[run]:raise ValueError('Pinned actual FD changed')
 m.Firmware().volume(fd,'Actual FD');m.heap_descriptors=original
 if len(capture)!=1:raise ValueError('Ambiguous SEC')
 data=capture[0];bodies.append(data);settings=json.loads((r/f'out/firmware-ci/{run}/nuwa-firmware-{run}/build-settings.json').read_text());stamp=datetime.fromtimestamp(int(settings['source_date_epoch']),timezone.utc).strftime('%H:%M:%S').encode()
 if data.count(stamp)!=1:raise ValueError('Unique SOURCE_DATE_EPOCH build time not found')
 times.append((data.index(stamp),stamp));sections={};strip=struct.unpack_from('<H',data,6)[0]
 for i in range(data[4]):
  at=40+40*i;name=data[at:at+8].rstrip(b'\0').decode();vs,va,size,off=struct.unpack_from('<4I',data,at+8);body=data[off-strip+40:off-strip+40+size];sections[name]=dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
 records.append(dict(run=run,sec_sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),sections=sections))
if times[0][0]!=times[1][0]:raise ValueError('Build time moved')
at=times[0][0]
if bodies[0][:at]+bytes(8)+bodies[0][at+8:]!=bodies[1][:at]+bytes(8)+bodies[1][at+8:]:raise ValueError('SEC changes outside reproducible build time')
diffs=[i for i,(a,b) in enumerate(zip(*bodies)) if a!=b];groups=[]
for i in diffs:
 if groups and groups[-1][1]==i:groups[-1][1]=i+1
 else:groups.append([i,i+1])
result=dict(scope='Static actual SEC comparison; no runtime cause proven',records=records,equal_length=len(bodies[0])==len(bodies[1]),entire_sec_equal_after_masking_build_time=True,build_time=dict(offset=hex(at),old=times[0][1].decode(),new=times[1][1].decode()),differing_bytes=len(diffs),difference_ranges=[dict(offset=hex(a),bytes=b-a,old_hex=bodies[0][a:b].hex(),new_hex=bodies[1][a:b].hex()) for a,b in groups],device_accessed=False)
(r/'reports/boot-input-audit-trial/2026-10-24/sec-differential.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
