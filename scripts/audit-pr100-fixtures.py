"""Assess pinned PR100 scripts in isolated fixtures; never run its system installer."""
import argparse, ast, hashlib, importlib.util, json, os, pathlib, shutil, subprocess, sys

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--xnu',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);linux=a.source/'scripts/linux';checks=[];commands=[]
 def check(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
 def run(argv,stdin=None,env=None):
  r=subprocess.run(list(map(str,argv)),input=stdin,capture_output=True,text=True,env={**os.environ,**(env or {})},timeout=40);commands.append(dict(argv=list(map(str,argv)),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));return r
 manifest=json.loads((a.source/'sources.json').read_text())
 check('Selected fixed PR100 input hashes match',all(hashlib.sha256((a.source/item['path']).read_bytes()).hexdigest()==item['sha256'] for item in manifest))
 for item in manifest:
  if not item['path'].endswith('.py'):continue
  file=a.source/item['path'];ast.parse(file.read_text());check('Python syntax '+item['path'],True)
 for name in ('clang','clang++','xcrun','install','codesign','cc','gm4'):
  r=run(['bash','-n',linux/name]);check('Shell syntax '+name,r.returncode==0);(linux/name).chmod(0o755)
 env=dict(XNU_TOOLCHAIN_BIN=str(linux),UNIXNU_SDKROOT=str(a.work/'fakeroot'),UNIXNU_SDK_VERSION='16.0',UNIXNU_SDK_BUILD='20H392',DARWIN_TRIPLE='arm64-apple-ios16.0',CROSS_CLANG='/usr/bin/clang',CROSS_EXTRA_FLAGS='')
 r=run([linux/'xcrun','--sdk','iphoneos','--show-sdk-version'],env=env);check('xcrun accepts Darwin22 SDK override',r.returncode==0 and r.stdout.strip()=='16.0')
 r=run([linux/'xcrun','--sdk','iphoneos','--show-sdk-build-version'],env=env);check('xcrun accepts iOS16 build override',r.returncode==0 and r.stdout.strip()=='20H392')
 r=run([linux/'xcrun','--find','nuwa-pr100-nonexistent-tool'],env=env);check('xcrun rejects absent tool',r.returncode!=0 and not r.stdout.strip())
 r=run([linux/'clang','-ffreestanding','-fsyntax-only','-x','c','-'],stdin='#if !defined(__aarch64__) || __ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__ != 160000\n#error wrong_target\n#endif\nint a;\n',env=env);check('clang wrapper can target arm64 iOS16 explicitly',r.returncode==0)
 r=run([linux/'clang','-target','arm64-apple-ios17.0','-E','-P','-x','c','-'],stdin='__ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__\n',env=env);check('Explicit helper iOS17 flag overrides wrapper iOS16 (expected porting risk)',r.returncode==0 and '170000' in r.stdout)
 r=run([linux/'clang','-E','-P','-x','c','-'],stdin='#include "'+str(linux/'TargetConditionals.h')+'"\n#if !TARGET_OS_IPHONE || !TARGET_CPU_ARM64 || TARGET_OS_OSX || TARGET_OS_SIMULATOR\n#error wrong_target_conditions\n#endif\n',env=env);check('TargetConditionals reflects actual iOS16 target',r.returncode==0)
 r=run(['/usr/bin/clang','-target','arm64-apple-ios16.0','-E','-P','-x','c','-'],stdin='SIG=__has_builtin(__builtin_xnu_type_signature)\nSUM=__has_builtin(__builtin_xnu_type_summary)\nCMP=__has_builtin(__builtin_xnu_types_compatible)\n');check('Host clang14 lacks required XNU builtins (expected blocker)',r.returncode==0 and all(s in r.stdout for s in ('SIG=0','SUM=0','CMP=0')))
 env_default={**env,'CROSS_EXTRA_FLAGS':'-mllvm -disable-atexit-based-global-dtor-lowering'}
 r=run([linux/'clang','-c','-x','c','-','-o',a.work/'sample.o'],stdin='int a;',env=env_default);check('Existing clang14 cannot replace PR100 clang (expected blocker)',r.returncode!=0 and 'disable-atexit' in r.stderr)
 src=a.work/'copy.in';dst=a.work/'copy.out';src.write_text('nuwa fixture\n');r=run([linux/'install','-c','-S','-m','0644',src,dst]);check('BSD install flags produce real GNU copy',r.returncode==0 and dst.read_bytes()==src.read_bytes())
 import tempfile
 with tempfile.TemporaryDirectory(prefix='nuwa-pr100-',dir='/tmp') as tmp:
  native=pathlib.Path(tmp)/'copy.out';r=run([linux/'install','-c','-S','-m','0644',src,native]);check('Install mode is0644 on native Linux filesystem',r.returncode==0 and native.stat().st_mode&0o777==0o644)
 commands.append(dict(observation='DrvFS file mode after install',path=str(dst),mode=oct(dst.stat().st_mode&0o777),limitation='Windows mount permissions may not reflect requested POSIX modes; use native Linux build/toolchain paths'))
 r=run([linux/'codesign','--verify','/nuwa-pr100-nonexistent']);check('codesign is intentionally no-op, not signature proof',r.returncode==0)
 import plistlib
 xml=a.work/'sample.plist';binary=a.work/'sample.binary.plist';xml.write_bytes(plistlib.dumps({'version':22,'name':'nuwa'}));r=run(['python3',linux/'plutil','-convert','binary1','-o',binary,xml]);check('plutil converts real plist',r.returncode==0 and plistlib.loads(binary.read_bytes())=={'version':22,'name':'nuwa'})
 r=run(['python3',linux/'plutil','--nuwa-unsupported',xml]);check('plutil rejects unknown options',r.returncode!=0)
 spec=importlib.util.spec_from_file_location('pr100_prepare',linux/'prepare-xnu.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 fixture=a.work/'source-fixture';module.ROOT=fixture;module.XNU=fixture/'.cache/xnu-work';module.FAKEROOT=fixture/'.cache/fakeroot'
 paths=['bsd/kern/makesyscalls.sh','osfmk/arm64/corecrypto/arm64_isa_compatibility.h','SETUP/kextsymboltool/kextsymboltool.c']
 originals={}
 for relative in paths:
  data=(a.xnu/relative).read_bytes();originals[relative]=hashlib.sha256(data).hexdigest();target=module.XNU/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 try:
  module.rewrite_sources();check('PR100 rewrites run on original XNU8796 sources',True)
  before={r:(module.XNU/r).read_bytes() for r in paths};module.rewrite_sources();check('PR100 source rewrites are idempotent on XNU8796',all(before[r]==(module.XNU/r).read_bytes() for r in paths))
  check('8796 ISA condition admits non-Apple clang',module.ISA_ANY in (module.XNU/paths[1]).read_text())
  check('8796 kextsymboltool exact seek replacement applied',module.SEEK_NEW in (module.XNU/paths[2]).read_text())
 except Exception as e:check('PR100 rewrites run on original XNU8796 sources',False,str(e))
 result=dict(scope='Pinned PR100 source/shim and original8796 three-file rewrite fixtures; no patched LLVM/IIG/whole-kernel build, no system install or device action',checks=checks,commands=commands,xnu_original_source_sha256=originals,host=dict(machine=__import__('platform').machine(),os=__import__('platform').freedesktop_os_release()),limitations=['Syntax/shim behavior is not toolchain or kernel qualification','Original8796 fixture does not replay the full64-patch device sequence','codesign no-op acceptance is documented host behavior, not target signing'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(checks=len(checks),failed=[c['name'] for c in checks if not c['passed']])));return int(any(not c['passed'] for c in checks))
if __name__=='__main__':sys.exit(main())
