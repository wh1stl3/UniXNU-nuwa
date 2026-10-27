"""Inventory regressions: missing desktop, shared-cache ambiguity and escape."""
import importlib.util,json,plistlib,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('desktop_audit',R/'scripts/audit-desktop-root.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();checks=[]
    with tempfile.TemporaryDirectory(prefix='desktop-fixture-') as d:
        root=Path(d)
        def write(path,data=b'x'):
            target=root/path.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);return target
        write('/sbin/launchd');write('/usr/lib/dyld')
        report=A.inventory(root);assert report['desktop_executable_gaps']==['SpringBoard','backboardd'];checks.append('restore root does not imply desktop')
        for key in ('SpringBoard','backboardd'):write(A.ITEMS[key])
        report=A.inventory(root);assert report['desktop_executable_gaps']==[] and 'pending' in report['classification'];checks.append('presence does not imply runnable desktop')
        write('/System/Library/dyld/dyld_shared_cache_arm64',b'cache')
        report=A.inventory(root);assert len(report['dyld_cache_files'])==1 and not report['items']['UIKitCore']['present'] and 'not by itself' in report['framework_resolution'];checks.append('cache presence leaves membership unresolved')
        props=dict(Label='test',ProgramArguments=['/usr/lib/dyld'],Disabled=True,RunAtLoad=True,MachServices={'test':True})
        write('/System/Library/LaunchDaemons/test.plist',plistlib.dumps(props))
        report=A.inventory(root);assert report['launch_jobs'][0]['declared']=={k:props[k] for k in ('RunAtLoad','Disabled','MachServices')} and report['launch_jobs'][0]['program_present'];checks.append('trigger declarations retained without activation claim')
        write(A.MAIN_CONFIG,plistlib.dumps({'LaunchDaemons':{'test.plist':props}}))
        report=A.inventory(root);assert report['main_launch_config']['jobs'][0]['keys']==['LaunchDaemons','test.plist'] and report['main_launch_config']['jobs'][0]['program_present'];checks.append('iOS main launch config inventoried separately')
        link=root/'System/Library/Frameworks/IOSurface.framework/IOSurface';link.parent.mkdir(parents=True,exist_ok=True);link.symlink_to('../../../../../../outside')
        try:A.inventory(root)
        except ValueError as e:assert 'escape' in str(e)
        else:raise AssertionError('Root escape accepted')
        checks.append('symlink root escape rejected')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(json.dumps(dict(checks=[dict(name=c,passed=True) for c in checks],test_sha256=A.C.sha(Path(__file__).read_bytes()),script_sha256=A.C.sha((R/'scripts/audit-desktop-root.py').read_bytes()),device_accessed=False),indent=2).encode()+b'\n');print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
