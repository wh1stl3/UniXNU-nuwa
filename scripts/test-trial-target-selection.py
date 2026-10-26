"""Verify pinned-target selection with a foreign attached device; no device calls."""
import importlib.util,json,sys,subprocess,argparse
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,R/'scripts'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(R/'reports')
 record=module('state_record','record-nuwa-trial-state.py');trial=module('trial','trial-v4-firmware.py');calls=[];written=[]
 def run(argv,**kw):
  calls.append(argv);assert argv[:3]==['adb','-s','nuwa-test'],('Foreign target queried',argv)
  text='nuwa' if argv[3:] == ['shell','getprop','ro.product.device'] else ('nuwa kalama' if 'identity' in str(argv) or 'devicetree' in str(argv) else '_a' if 'slot_suffix' in str(argv) else '1' if 'boot_completed' in str(argv) else 'a /dev/block/by-name/boot_a\nb /dev/block/by-name/vendor_boot_a\nc /dev/block/by-name/init_boot_a')
  return subprocess.CompletedProcess(argv,0,text,'')
 args=['record','--serial','nuwa-test','--output',str(R/'reports/__selection_fixture_never_written__.json')]
 with patch.object(sys,'argv',args),patch.object(record.subprocess,'check_output',return_value='List of devices attached\nforeign-test device\nnuwa-test device\n'),patch.object(record.subprocess,'run',side_effect=run),patch.object(Path,'write_text',side_effect=lambda text,**kw:written.append(json.loads(text))):record.main()
 assert len(calls)==5 and len(written)==1 and written[0]['android_boot_completed']=='1'
 checks=[dict(name='Full state recorder only queries explicitly selected nuwa amid foreign device',passed=True,queries=len(calls))]
 for tool in ('adb','fastboot'):
  state='device' if tool=='adb' else 'fastboot';trial.TARGET_SERIAL='nuwa-test'
  with patch.object(trial.subprocess,'run',return_value=subprocess.CompletedProcess([],0,f'foreign-test {state}\nnuwa-test {state}\n','')):assert trial.devices(tool)==['nuwa-test']
  with patch.object(trial.subprocess,'run',return_value=subprocess.CompletedProcess([],0,f'foreign-test {state}\n','')):assert trial.devices(tool)==[]
  checks.append(dict(name=tool+' selector excludes foreign devices and never falls back when selected device absent',passed=True))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(scope=__doc__,checks=checks,device_accessed=False),indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
