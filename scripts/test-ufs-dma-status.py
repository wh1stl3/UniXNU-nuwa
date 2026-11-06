"""Execute the packaged AArch64 DMA buffer probe against bounded synthetic MMIO."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_X3, UC_ARM64_REG_SP
import flush_trace_inputs as trace

work = ROOT/'out/ufs-r4-r1'
report = ROOT/'reports/ufs-r4-r1'
build = json.loads((report/'build.json').read_bytes())
kernel = (work/'fat/readback-kernel.macho').read_bytes()
B = trace.builder()
m = B.macho(kernel)
slide = 0xfffffff000000000
sym = {k:v-slide for k,v in json.loads((work/'symbols.json').read_bytes()).items()}
site, mapper, scratch = [int(build[k],16)-slide for k in ('site','map_function','scratch')]
mmio, fb, stride = 0x20000000, 0x30000000, 5760
valid = 1 << 31
sms = 1 << 27

regs=(UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3)
def case(name, terminal, phys=0xc1240000, length=0x22000, cap=0x01000001,
         fail='', no_task=False):
    u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    task=m['symbols']['_kernel_task']-slide
    alloc=m['symbols']['__ZN24IOBufferMemoryDescriptor17inTaskWithOptionsEP4taskjmm']-slide
    obj=0x25000000
    stack=0x26000000
    mapped_pages=set()
    def page(addr):
        base=addr & ~4095
        if base not in mapped_pages:
            u.mem_map(base,4096)
            mapped_pages.add(base)
    for addr in (site,mapper,scratch,sym['trace_1'],sym['font']+63,mmio,mmio+4096,mmio+8192,task,alloc,obj,stack):
        page(addr)
    for addr,size in ((site,4),(sym['trace_1'],build['code_bytes'])):
        offset=B.backed(m,addr+slide,size)
        u.mem_write(addr,kernel[offset:offset+size])
    u.mem_map(fb,0x700000)
    u.mem_write(scratch,struct.pack('<QQ',fb,stride))
    u.mem_write(task,struct.pack('<Q',0 if no_task else 0x12345678))
    u.mem_write(obj,struct.pack('<Q',obj+0x100))
    sp=stack+0xf00
    u.reg_write(UC_ARM64_REG_SP,sp)
    def word(addr,val): u.mem_write(addr,struct.pack('<I',val))
    word(mmio+4,1<<31); word(mmio+0x18,1); word(mmio+0x24,0 if fail=='clock' else 0x80000003)
    word(mmio+4096+8,0x400); word(mmio+4096,cap)
    word(mmio+8192+0x28,0 if fail=='width-id' else 0x5111)
    calls=[];fields={}
    def ret(cpu,value):
        cpu.reg_write(regs[0],value)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
    def handle(cpu,addr,size,data):
        a,b,c,d=[cpu.reg_read(r) for r in regs]
        if addr==mapper:
            assert (b,c)==(4096,1)
            mapped={0x177000:mmio,0x1d84000:mmio+4096,0x15000000:mmio+8192}[a]
            ret(cpu,0 if fail=='map' else mapped)
        elif addr==alloc:
            assert (a,b,c,d)==(0x12345678,0x813,0x22000,4096)
            calls.append('alloc');ret(cpu,0 if fail=='alloc' else obj)
        elif addr==obj+0x800:
            assert a==obj
            calls.append('virtual');ret(cpu,0 if fail=='virtual' else 0xabcd0000)
        elif addr==obj+0x804:
            assert (a,b,c,d)==(obj,0,sp-16,0x800)
            calls.append('segment');cpu.mem_write(c,struct.pack('<Q',length));ret(cpu,phys)
        elif addr==obj+0x808:
            assert a==obj
            calls.append('release');ret(cpu,0)
        else:
            fields[a]=b
    for slot,off in [(0x148,0x800),(0x98,0x804),(0x28,0x808)]:
        u.mem_write(obj+0x100+slot,struct.pack('<Q',obj+off))
    for addr in (mapper,alloc,obj+0x800,obj+0x804,obj+0x808,sym['draw']):
        u.hook_add(UC_HOOK_CODE,handle,begin=addr,end=addr)
    def forbidden(*args): raise AssertionError('Device write')
    u.hook_add(UC_HOOK_MEM_WRITE,forbidden,begin=mmio,end=mmio+12287)
    u.emu_start(site,sym['halt'],count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and fields[0]==terminal
    assert u.reg_read(UC_ARM64_REG_SP)==sp
    expected=[] if terminal in (33,34,39) else ['alloc'] if terminal==35 else ['alloc','virtual','release'] if terminal==36 else ['alloc','virtual','segment','release']
    assert calls==expected
    if 'segment' in calls:
        assert fields[2]+(fields[3]<<32)==phys and fields[4]+(fields[5]<<32)==length
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xf400+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),calls=calls,device_writes=0)

if __name__=='__main__':
    cases=[
        case('normal',16),case('above 4G',16,phys=1<<32),
        case('32-bit exact end',16,phys=(1<<32)-0x22000,cap=1),
        case('32-bit crosses',38,phys=(1<<32)-0x21000,cap=1),
        case('36-bit exact end',16,phys=(1<<36)-0x22000),
        case('36-bit crosses',38,phys=(1<<36)-0x21000),
        case('u64 overflow',38,phys=(1<<64)-4096),
        case('short',37,length=0x21fff),case('null PA',37,phys=0),
        case('unaligned',37,phys=0x1234),case('no task',39,no_task=True),
        case('allocation fails',35,fail='alloc'),case('no VA',36,fail='virtual'),
        case('clock gate',33,fail='clock'),case('width changed',33,fail='width-id'),
        case('invalid HCI CAP',33,cap=0xffffffff),case('no map',34,fail='map')]
    (report/'host-test.json').write_text(json.dumps(cases,indent=2))
    print(len(cases),'cases passed')
