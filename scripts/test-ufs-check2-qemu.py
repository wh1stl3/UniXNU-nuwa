"""EL1 QEMU UFS pre-rehearsal with the same instrumented command implementation.

Uses a synthetic disk only. Not nuwa hardware, XNU scheduling or APFS execution.
"""
import argparse,hashlib,json,re,runpy,shutil,subprocess
from pathlib import Path
import ufs_carrier_object_link as o

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
p.add_argument('--work',type=Path,required=True);p.add_argument('--qemu',type=Path,required=True)
a=p.parse_args();w=a.work.resolve();w.mkdir(parents=True,exist_ok=False)
src=w/'source';shutil.copytree(a.source,src)
probe=o.ROOT/'package/verified-root';guest=src/'tests/RootCommandsArm64.cpp'
s=guest.read_text().replace('#include <stdint.h>','#include <stdint.h>\n#include "NuwaUfsReadProbe.h"\nstatic bool command_seen=false;')
s=s.replace('static uint64_t mach_absolute_time() {','static uint64_t mach_absolute_time() {\n  if ((nuwa_ufs_probe_state>>16)&15) command_seen=true;')
s=s.replace('  auto result=hostNop();\n#if TEST_BAD_DMA','  IOReturn result=0;\n#if TEST_BAD_DMA\n  NuwaUfsReadProbe probe;\n  result=hostRead4k(0,8,1,output,&probe);\n  check(command_seen && ((nuwa_ufs_probe_state>>20)&15),"timeout phase missing");\n  probe.result(result);probe.move(UfsIdle);\n  check(!(nuwa_ufs_probe_state&((1ULL<<40)-1)),"timeout request did not exit");')
s=s.replace('  check(result==0,"NOP");','  result=hostNop();\n  check(result==0,"NOP");')
s=s.replace('    check(hostRead4k(0,8,blocks,output)==0,"READ10");','    NuwaUfsReadProbe probe;\n    check(hostRead4k(0,8,blocks,output,&probe)==0,"READ10");\n    check(((nuwa_ufs_probe_state>>20)&15)==1,"READ completion phase");\n    probe.move(UfsIdle);\n    check(!(nuwa_ufs_probe_state&((1ULL<<40)-1)),"READ remains active");')
guest.write_text(s,encoding='utf-8',newline='\n')
extract=runpy.run_path(str(src/'tests/check_arm64_root_commands.py'))['extract']
hardware='\n'.join(extract((src/'NativeUfs.cpp').read_text(),n) for n in ['read32','write32','cacheCivac','cacheInvalidate','hostWrite'])
(w/'RootHardwareExtracted.h').write_text(hardware)
(w/'link.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x40200000; .text : { *(.text.entry) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } . = ALIGN(4096); __bss_start = .; .bss : { *(.bss*) *(COMMON) } . = ALIGN(8); __bss_end = .; ASSERT(. < 0x40400000, "fixture mapping budget") }\n')
(w/'blank-firmware.bin').write_bytes(bytes(4096))
disk=bytearray(2*1024*1024);disk[8*4096:8*4096+131072]=bytes(((i*17+(i>>8)*31)^0xa5)&255 for i in range(131072));(w/'disk.raw').write_bytes(disk)
common=['clang++','--target=aarch64-none-elf','-O2','-ffreestanding','-fno-builtin','-nostdinc++','-fno-exceptions','-fno-rtti','-fno-stack-protector','-mgeneral-regs-only','-mno-outline-atomics','-fno-strict-aliasing','-Wall','-Wextra','-Werror','-Wno-unused-function','-I',o.linux(w),'-I',o.linux(probe)]
o.run('clang++','--target=aarch64-none-elf','-c',o.linux(src/'tests/RootCommandsArm64.S'),'-o',o.linux(w/'entry.o'))
o.run(*common,'-c',o.linux(probe/'NuwaUfsReadProbe.cpp'),'-o',o.linux(w/'probe.o'))
results=[]
for name,physical,bad,sharing in [('low',0x40010000,0,2),('high',0x8cb5e9000,0,2),('high-inner-shareable',0x8cb5e9000,0,3),('truncated-high',0x8cb5e9000,1,2),('virtual-as-physical',0x8cb5e9000,2,2)]:
 d=w/name;d.mkdir();o.run(*common,f'-DTEST_DMA_PHYS={physical:#x}ULL',f'-DTEST_BAD_DMA={bad}',f'-DTEST_SHAREABILITY={sharing}','-c',o.linux(guest),'-o',o.linux(d/'guest.o'))
 o.run('ld.lld','-T',o.linux(w/'link.ld'),o.linux(w/'entry.o'),o.linux(d/'guest.o'),o.linux(w/'probe.o'),'-o',o.linux(d/'guest.elf'))
 command=[str(a.qemu.resolve()),'-machine','virt,gic-version=3,highmem-ecam=off,acpi=on,virtualization=off,secure=off','-cpu','cortex-a710','-accel','tcg','-m','128M,slots=1,maxmem=64G','-bios',str(w/'blank-firmware.bin'),'-object','memory-backend-ram,id=hi,size=256M','-device','pc-dimm,memdev=hi,addr=0x8c0000000','-device','ufs,id=ufs0,bus=pcie.0,addr=1.0','-drive',f'if=none,id=disk,format=raw,readonly=on,file={(w/"disk.raw").as_posix()}','-device','ufs-lu,bus=ufs0,drive=disk,lun=0','-device',f'loader,file={(d/"guest.elf").as_posix()},cpu-num=0','-nodefaults','-display','none','-serial','stdio','-monitor','none','-no-reboot','-semihosting-config','enable=on,target=native']
 (d/'command.json').write_text(json.dumps(command,indent=2)+'\n')
 try:r=subprocess.run(command,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
 except subprocess.TimeoutExpired as e:
  (d/'serial.log').write_bytes(e.stdout or b'');(d/'qemu.log').write_bytes(e.stderr or b'');raise
 (d/'serial.log').write_bytes(r.stdout);(d/'qemu.log').write_bytes(r.stderr)
 log=r.stdout.decode(errors='replace');print(name,log,flush=True)
 assert r.returncode==0 and 'FAIL' not in log,(name,r.returncode,r.stderr.decode(errors='replace'))
 assert ('PASS rejected bad DMA without resubmission' if bad else 'PASS ALL') in log
 results.append(dict(case=name,passed=True,dma_pa=hex(physical),shareability=sharing))
files=[probe/'NuwaUfsReadProbe.cpp',probe/'NuwaUfsReadProbe.h',src/'NativeUfs.cpp',src/'RootCommands.h',guest,Path(__file__)]
(w/'report.json').write_text(json.dumps(dict(passed=True,results=results,sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},qemu=subprocess.check_output([str(a.qemu),'--version'],text=True).splitlines()[0],scope='QEMU virt UFS synthetic read-only disk; production read command, DC/barriers and new ledger compiled for EL1. Not iOS16 full boot, APFS, XNU locks, real SM8550 cache/SMMU/power/timing.'),indent=2)+'\n')
