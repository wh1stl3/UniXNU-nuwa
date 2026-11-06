"""One-shot LOG-SURVEY2 temporary boot; independent of XNU trial scopes."""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IMAGE=ROOT/'out/log-survey-v2-build01/boot-log-survey-v2.img'
SHA='60885122c82aa91a7b6e682198923f0a4681ecfe0776f5768a562365100a40db'
BASELINE=ROOT/'reports/log-survey-trial/2026-10-28-survey1-r3/recovery1/postcondition.json'
QUAL=ROOT/'reports/log-survey-v2/qualification-final.json'
ORIGINAL=Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def validate():
    q=json.loads(QUAL.read_text())
    if digest(IMAGE)!=SHA or q['image_sha256']!=SHA or len(IMAGE.read_bytes())!=70266880:raise ValueError('Candidate mismatch')
    for path,expected in q['source_seal'].items():
        if digest(Path(path))!=expected:raise ValueError('Sealed source/evidence changed: '+path)
    baseline=json.loads(BASELINE.read_text())
    if baseline['android_boot_completed']!='1' or not baseline['three_partition_hashes_unchanged']:raise ValueError('Recovery baseline invalid')
    if digest(ORIGINAL)!=baseline['partition_hashes']['/dev/block/by-name/boot_a']:raise ValueError('Original recovery image changed')
    return baseline
def inventory(tool):
    r=subprocess.run([tool,'devices'],capture_output=True,text=True,timeout=15,check=True)
    return [v[0] for line in r.stdout.splitlines() if len(v:=line.split())==2 and v[1]==('device' if tool=='adb' else 'fastboot')]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['prepare','launch','postcondition']);p.add_argument('--trial',required=True,type=Path);a=p.parse_args()
    trial=a.trial.resolve()
    if not trial.is_relative_to(ROOT/'reports/log-survey-trial'):raise ValueError('Dedicated trial path required')
    if a.phase=='launch' and (ROOT/'reports/log-survey-v2/consumed.json').exists():raise ValueError('Candidate already consumed')
    baseline=validate()
    report={'at':now(),'image_sha256':SHA,'commands':[]}
    output=trial/({'prepare':'preflight.json','launch':'launch.json','postcondition':'postcondition.json'}[a.phase])
    if output.exists():raise ValueError('Evidence exists; refusing reuse')
    if a.phase=='prepare':trial.mkdir(parents=True,exist_ok=False)
    elif not trial.is_dir():raise ValueError('Missing trial')
    def run(tool,serial,argv,timeout=30):
        r=subprocess.run([tool,'-s',serial,*argv],capture_output=True,text=True,timeout=timeout)
        report['commands'].append(dict(at=now(),argv=[tool,'-s','<selected-nuwa>',*argv],exit_code=r.returncode,stdout=r.stdout.replace(serial,'<selected-nuwa>'),stderr=r.stderr.replace(serial,'<selected-nuwa>')))
        save(output,report)
        if r.returncode:raise RuntimeError('Command failed: '+tool+' '+argv[0])
        return (r.stdout+r.stderr).replace('\0','\n').strip()
    def android():
        found=[]
        for candidate in inventory('adb'):
            probe=subprocess.run(['adb','-s',candidate,'exec-out','getprop ro.product.device'],capture_output=True,text=True,timeout=15)
            if probe.returncode==0 and probe.stdout.strip()=='nuwa':found.append(candidate)
        if len(found)!=1:raise ValueError('Need one uniquely identified nuwa Android target')
        serial=found[0]
        identity=run('adb',serial,['exec-out',"su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'"])
        if 'nuwa' not in identity.lower() or 'kalama' not in identity.lower():raise ValueError('Wrong target')
        completed=run('adb',serial,['exec-out','getprop sys.boot_completed'])
        slot=run('adb',serial,['exec-out','getprop ro.boot.slot_suffix'])
        if completed!='1' or slot!='_a':raise ValueError('Android/slot gate failed')
        raw=run('adb',serial,['exec-out',"su -c 'sha256sum /dev/block/by-name/boot_a /dev/block/by-name/vendor_boot_a /dev/block/by-name/init_boot_a'"],60)
        hashes={line.split()[1]:line.split()[0] for line in raw.splitlines()}
        if hashes!=baseline['partition_hashes']:raise ValueError('Partition hashes changed')
        report.update(device='nuwa',soc='kalama',android_boot_completed=completed,slot=slot,partition_hashes=hashes,three_partition_hashes_unchanged=True)
        save(output,report);return serial
    try:
        if a.phase in ('prepare','postcondition'):
            android()
            report.update(recovery_evidence={'path':str(BASELINE.relative_to(ROOT)),'sha256':digest(BASELINE)},qualification_sha256=digest(QUAL))
            if a.phase=='prepare':
                for sub in ('original','derived'):(ROOT.parent/'Media-nuwa/LOG-SURVEY2'/sub).mkdir(parents=True,exist_ok=True)
                report.update(process_log_method='framebuffer photographed or recorded by user',human_capture_confirmation='User: 可以上机了; established authorization includes recording and physical-key recovery',original_boot_sha256=digest(ORIGINAL))
            print('PASS '+a.phase+' identity, Android completion, slot and three hashes')
        else:
            gate=json.loads((trial/'preflight.json').read_text());age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(gate['at'])).total_seconds()
            if not 0<=age<=900 or gate['image_sha256']!=SHA or gate['qualification_sha256']!=digest(QUAL) or not gate['human_capture_confirmation']:raise ValueError('Stale/mismatched preflight')
            if gate['recovery_evidence']['sha256']!=digest(BASELINE):raise ValueError('Recovery evidence changed')
            if not all((ROOT.parent/'Media-nuwa/LOG-SURVEY2'/s).is_dir() for s in ('original','derived')):raise ValueError('Missing media directories')
            # Revalidate target immediately before transitioning from Android.
            serial=android();report['preflight_sha256']=digest(trial/'preflight.json')
            run('adb',serial,['reboot','bootloader'])
            end=time.monotonic()+60
            while time.monotonic()<end:
                found=inventory('fastboot')
                if serial in found and len(found)==1:break
                time.sleep(2)
            else:raise RuntimeError('Selected bootloader absent')
            run('fastboot',serial,['reboot','bootloader']);time.sleep(3)
            end=time.monotonic()+45
            while time.monotonic()<end:
                if inventory('fastboot')==[serial]:break
                time.sleep(2)
            else:raise RuntimeError('Bootloader re-entry failed')
            if 'product: nuwa' not in run('fastboot',serial,['getvar','product']):raise ValueError('Fastboot product mismatch')
            if 'unlocked: yes' not in run('fastboot',serial,['getvar','unlocked']):raise ValueError('Unlock state not confirmed')
            if 'current-slot: a' not in run('fastboot',serial,['getvar','current-slot']):raise ValueError('Fastboot slot mismatch')
            if digest(IMAGE)!=SHA:raise ValueError('Candidate changed before boot')
            consumed=ROOT/'reports/log-survey-v2/consumed.json'
            with consumed.open('x',encoding='utf-8') as f:json.dump(dict(at=now(),image_sha256=SHA,trial=str(trial.relative_to(ROOT)),state='attempt committed before fastboot boot; never resend'),f,indent=2)
            report['candidate_consumed']=True;save(output,report)
            accepted=run('fastboot',serial,['boot',str(IMAGE)],60)
            report['fastboot_boot_exit_code']=0;report['observation_scope']='Transport ACK only; actual survey execution needs captured pages'
            print(accepted)
    except Exception as e:
        report['error']=str(e);raise
    finally:
        report['ended_at']=now();save(output,report)
if __name__=='__main__':main()
