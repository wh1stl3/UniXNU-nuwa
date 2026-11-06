"""Execute actual carrier delay body in EL1, with explicit event-source conditions."""
import sys,json,subprocess,hashlib,struct
from pathlib import Path
import ufs_carrier_object_link as o
import flush_trace_inputs as t
w=o.ROOT/'out/ufs-delay-event-qemu-r1';w.mkdir(exist_ok=False)
raw=(o.ROOT/'out/ufs-check-1-r1-final/kernel.macho').read_bytes();b=t.builder();m=b.macho(raw)
a=0xfffffff0073cf094;body=raw[b.backed(m,a,44):][:44]
assert body[16:20]==bytes.fromhex('5f2003d5')
asm='.text\n.global native_delay\nnative_delay:\n'
for i in range(0,len(body),4):asm+=(' bl modeled_clock\n' if i==20 else f' .inst 0x{struct.unpack_from("<I",body,i)[0]:08x}\n')
(w/'native.S').write_text(asm)
(w/'guest.cpp').write_text(r'''#include <stdint.h>
extern "C" void native_delay(uint64_t,uint64_t);
extern "C" uint64_t modeled_clock(){uint64_t n;asm volatile("isb; mrs %0,cntvct_el0":"=r"(n));return n;}
static void puts(const char*s){while(*s)*reinterpret_cast<volatile uint32_t*>(0x09000000)=*s++;}
static void end(){uint64_t a[2]={0x20026,0};register uint64_t x0 asm("x0")=0x20;register uint64_t x1 asm("x1")=(uint64_t)a;asm volatile("hlt #0xf000"::"r"(x0),"r"(x1):"memory");}
extern "C" void guest_exception(){puts("EXCEPTION\n");for(;;);}
extern "C" void guest_main(){
 uint64_t event=MODE==1? (4|(15<<4)):0;
 asm volatile("msr cntkctl_el1,%0; msr cntv_ctl_el0,xzr; msr cntp_ctl_el0,xzr; isb"::"r"(event):"memory");
 uint64_t now=modeled_clock(),freq;asm volatile("mrs %0,cntfrq_el0":"=r"(freq));uint64_t deadline=now+freq/500000;
 puts("ENTER delay\n");
 if(MODE<2)native_delay(1,deadline);
 else while(modeled_clock()<deadline)asm volatile("yield");
 puts("RETURN delay\n");end();for(;;);
}
''')
entry=o.ROOT.parent/'references/ufs-check-r1/instrumented/tests/RootCommandsArm64.S'
(w/'link.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x40200000; .text : { *(.text.entry) *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } . = ALIGN(4096); __bss_start = .; .bss : { *(.bss*) } __bss_end = .; }')
(w/'firmware.bin').write_bytes(bytes(4096))
for src,name in ((entry,'entry'),(w/'native.S','native')):o.run('clang++','--target=aarch64-none-elf','-c',o.linux(src),'-o',o.linux(w/(name+'.o')))
q=o.ROOT.parent/'Toolchain-nuwa/qemu-11.1.0/portable/qemu-system-aarch64.exe';results=[]
for mode in range(3):
 o.run('clang++','--target=aarch64-none-elf','-O2','-ffreestanding','-fno-builtin','-fno-exceptions','-fno-rtti','-mgeneral-regs-only','-DMODE='+str(mode),'-c',o.linux(w/'guest.cpp'),'-o',o.linux(w/'guest.o'))
 elf=w/f'case-{mode}.elf';o.run('ld.lld','-T',o.linux(w/'link.ld'),*[o.linux(w/(x+'.o')) for x in ('entry','native','guest')],'-o',o.linux(elf))
 cmd=[str(q),'-machine','virt,gic-version=3,virtualization=off,secure=off','-cpu','cortex-a710','-accel','tcg','-m','128M','-bios',str(w/'firmware.bin'),'-device',f'loader,file={elf.as_posix()},cpu-num=0','-nodefaults','-display','none','-serial','stdio','-monitor','none','-no-reboot','-semihosting-config','enable=on,target=native']
 timeout=False
 try:r=subprocess.run(cmd,capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW);log=r.stdout
 except subprocess.TimeoutExpired as e:timeout=True;log=e.stdout or b''
 (w/f'case-{mode}.log').write_bytes(log);print(mode,timeout,log.decode(),flush=True)
 results.append(dict(mode=mode,timeout=timeout,returned=b'RETURN delay' in log,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest()))
(w/'report.json').write_text(json.dumps(dict(native_body=body.hex(),kernel_sha256=hashlib.sha256(raw).hexdigest(),results=results,scope='Actual machine_delay_until body; only BL relocated to CNTVCT fixture clock. Explicit event source and masked interrupts. Not real device event configuration.'),indent=2))
