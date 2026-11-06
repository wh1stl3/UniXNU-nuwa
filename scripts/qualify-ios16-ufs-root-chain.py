"""Qualify actual root parser and production completion method; no device I/O."""
import argparse,difflib,hashlib,json,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve();assert w.is_relative_to(R/'out') and not w.exists();w.mkdir()
 src=R/'out/kernel-mainline-nuwa-route-r1/publish-source/NativeUfs.cpp';original=src.read_text();local=w/'NativeUfs.cpp';local.write_text(original)
 commands=[]
 def run(args,name,expected=0):
  q=subprocess.run(list(map(str,args)),cwd=w,capture_output=True);(w/(name+'.log')).write_bytes(q.stdout+q.stderr);commands.append(dict(name=name,exit=q.returncode,expected=expected));assert q.returncode==expected,(name,(q.stdout+q.stderr).decode()[-3000:]);return q.stdout
 patch=R/'patches/driver-candidates/native-ufs-nuwa-root-publication.patch'
 run(['git','apply','--check',patch],'root-apply-check');run(['git','apply',patch],'root-apply')
 before=local.read_text();text=before
 def replace(old,new):
  nonlocal text
  assert text.count(old)==1,old;text=text.replace(old,new)
 replace('static inline uint64_t timerTicks (void) {uint64_t v; __asm__ volatile ("isb\\n\\tmrs %0, cntpct_el0" : "=r" (v)); return v;}','// Timing counters retained for symbol compatibility; hot-path sampling removed.')
 replace('#if defined(NATIVE_VERIFIED_BLOCK) && NATIVE_VERIFIED_BLOCK\n      uint64_t t0 = timerTicks ();\n#endif\n      IOReturn r = hostRead4k (0, lba, blocks, out);\n#if defined(NATIVE_VERIFIED_BLOCK) && NATIVE_VERIFIED_BLOCK\n      __atomic_fetch_add (&native_ufs_read_ticks, timerTicks () - t0, __ATOMIC_RELAXED);\n#endif\n      return r;','      return hostRead4k (0, lba, blocks, out);')
 replace('      uint64_t t0 = timerTicks ();\n      int status = vr_verify_block (view, index, data, length, &vr_xnu_crypto);\n      __atomic_fetch_add (&native_ufs_verify_ticks, timerTicks () - t0, __ATOMIC_RELAXED);','      int status = vr_verify_block (view, index, data, length, &vr_xnu_crypto);')
 replace('      if (boot_progress_poll) boot_progress_poll ();\n','')
 replace('    rootDiagnosticFailure ("root window read failed");','    // Return the real error through the completion, after releasing the window lock.')
 local.write_text(text)
 delta=''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/NativeUfs.cpp',tofile='b/NativeUfs.cpp'))
 target=R/'patches/driver-candidates/native-ufs-root-read-completion.patch'
 if target.exists():assert target.read_text()==delta
 else:target.write_text(delta)
 shutil.copyfile(R/'out/kernel-mainline-nuwa-route-r1/source/RootWindowRead.h',w/'RootWindowRead.h')
 flags=['/usr/bin/clang++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-pointer-bool-conversion','-fsanitize=address,undefined','-fno-pie','-no-pie','-g','-DNATIVE_VERIFIED_BLOCK=1','-I',w]
 fixture=R/'tests/ufs-root-completion.cpp'
 def method(s):return s[s.index('IOReturn NativeUfsBlock::doAsyncReadWrite'):s.index('void NativeUfsBlock::free')]
 (w/'production-method.inc').write_text(method(original));run(flags+[fixture,'-o',w/'negative'],'negative-build');run([w/'negative','negative'],'negative-reproduction',42)
 (w/'production-method.inc').write_text(method(text));run(flags+[fixture,'-o',w/'completion'],'completion-build');run([w/'completion'],'completion-tests')
 # The unmodified shared parser and publication/read algorithms, with only
 # the synthetic GPT fixture bound to the recorded nuwa partition geometry.
 source=R/'out/kernel-mainline-nuwa-route-r1/source';shutil.copytree(source,w/'source')
 fixture_read=w/'source/tests/RootWindowRead.cpp';s=fixture_read.read_text();assert s.count('{0ULL,UINT64_MAX}')==1;fixture_read.write_text(s.replace('{0ULL,UINT64_MAX}','{uint64_t(0),UINT64_MAX}'))
 f=w/'source/tests/RootLayout.cpp';s=f.read_text();g=json.loads((R/'reports/ufs-r9-r1/trial/android-gpt-layout.json').read_bytes());part=next(x for x in g['rows'] if x['name']=='userdata')
 for old,new in [('0x2f3840',hex(part['first'])),('0x3d0abfa',hex(part['last'])),('0x3d0abff',hex(g['last_lba']))]:s=s.replace(old,new)
 f.write_text(s)
 base=flags[:];base.remove('-DNATIVE_VERIFIED_BLOCK=1')
 run(base+['-Wno-deprecated-declarations',f,'-lcrypto','-o',w/'layout'],'layout-build')
 run([w/'layout',R/'out/ufs-root-ios16-auth-r2/root-manifest.bin'],'layout-tests')
 for suite in ['RootWindowRead','RootPublication']:
  run(base+[w/('source/tests/'+suite+'.cpp'),'-pthread','-o',w/suite],suite+'-build');run([w/suite],suite+'-tests')
 root='DADD93F8-DBBF-4B17-A1DF-0F11E64172F7';xml='<dict><key>IOProviderClass</key><string>IOMedia</string><key>IOPropertyMatch</key><dict><key>UUID</key><string>'+root+'</string></dict></dict>\0'
 (w/'chosen-root-matching.bin').write_bytes(xml.encode())
 import plistlib
 parsed=plistlib.loads(b'<plist version="1.0">'+xml[:-1].encode()+b'</plist>');assert parsed=={'IOProviderClass':'IOMedia','IOPropertyMatch':{'UUID':root}}
 report=dict(passed=True,source_sha256=sha(src),candidate_source_sha256=sha(local),activation_patch_sha256=sha(patch),completion_patch_sha256=sha(target),fixture_sha256=sha(fixture),commands=commands,negative_control='Original production method panics before completion on read failure',completed_request_cases=9,synchronous_rejection_cases=5,callback_destruction_and_reentry=True,host_parser_and_crypto_not_hardware=True,device_accessed=False,full_driver_compiled=False,activation_patch_applied_only=True,root_matching_sha256=sha(w/'chosen-root-matching.bin'),root_selected_by='IOMedia UUID; not BSD name and not Apple_HFS fallback',publication_order=['SystemOS','OS'],removed=['per-read and per-block ISB/timer samples','per-block boot_progress_poll','diagnostic panic before failed-request completion'],preserved=['signed policy and every-block verification','read-only windows','window lock across read/verify/copy','completion after unlocking','partial byte count and original error code'])
 (w/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
