"""Bind immutable originals, frame times and human visual readings to KMAIN-1."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
media=ROOT.parent/'Media-nuwa/KMAIN-1-r1'
report=ROOT/'reports/kmain-1-r1/trial/media-analysis.json'
assert not report.exists()
def ref(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
originals=sorted((media/'original').iterdir());video=next(p for p in originals if p.suffix=='.mp4')
probe=json.loads(subprocess.check_output(['D:/ffmpeg/bin/ffprobe.exe','-v','error','-select_streams','v:0','-show_frames','-show_format','-show_streams','-of','json',str(video)]))
frames=probe['frames']
observations=[]
for index,values,classification in [
 (112,{'FB00':'00000002','FB01':'00000000','FB02':'00000000','FB03':'00000003'},'complete early fields'),
 (113,{'FB00':'00000002','FB03':'00000003'},'same state'),
 (114,{'FB00':'00000002','FB03':'00000003'},'same state'),
 (115,{'FB00':'00000002','FB03':'00000003'},'same state'),
 (116,{'FB00':'00000002','FB03':'00000003','FB04':'00000000','FB05':'00000000','FB06':'00001000','FB07':'E7514394'},'mixed scanout/capture transition; not an atomic program snapshot'),
 (117,{'FB00':'00000010','FB01':'00000000','FB02':'00000000','FB03':'00000008','FB04':'00000000','FB05':'00000000','FB06':'00001000','FB07':'E7514394'},'complete success snapshot'),
 (139,{'FB00':'00000010','FB03':'00000008','FB06':'00001000','FB07':'E7514394'},'stable success snapshot')]:
 observations.append(dict(frame_zero_based=index,pts_seconds=frames[index]['best_effort_timestamp_time'],fields=values,classification=classification))
data=dict(candidate='KMAIN-1 r1',originals=[ref(p) for p in originals],
 video=dict(duration=probe['format']['duration'],frames=len(frames),frame_times=[f['best_effort_timestamp_time'] for f in frames]),
 observations=observations,photo_fields=observations[5]['fields'],
 derived=[ref(p) for p in sorted((media/'derived/review-01').glob('*.jpg'))],
 bindings={name:ref(ROOT/'reports/kmain-1-r1'/name) for name in ['qualification.json','trial/consumed.json','trial/launch.json','trial/postcondition.json']},
 passed=['IOStorageFamily load','NativeUfs late class registration','IOCatalogue provider matching','production hostBringUp and known blocks','bounded IOMedia with BSD unit 0 and NativeUfs ancestry','direct NativeUfsBlock read synchronous completion 4096 bytes CRC E7514394'],
 not_proven=['native root selector resumed after successful observer','IOMediaBSDClient strategy read','APFS root mount','init or EL0'],
 interpretation='Frame 116 lower fields contain successful read data while upper fields retain old values. Source draws FB03=8 before the final fields, so this mixed camera frame cannot be a single coherent code-state snapshot. Do not infer a stage regression or a second request.',
 recovery='ADB uniquely selected nuwa/kalama, boot completed 1, slot _a matches preflight; no partition hashes required for fastboot boot')
report.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(dict(frames=len(frames),observations=[(x['frame_zero_based'],x['pts_seconds']) for x in observations])))
