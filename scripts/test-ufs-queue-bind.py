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

work = ROOT/'out/ufs-r7-r1'
report = ROOT/'reports/ufs-r7-r1'
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
def case(name, terminal, phys=0x8cbd6c000, length=0x22000, cap=0x3587031f,
         fail='', no_task=False, queue=None, changes=None, stuck=0, sequence=()):
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
    hc=mmio+4096
    defaults={0x34:1,0x30:0x10f,0x20:0x400,0x50:0xc54e6000,0x70:0xc54e7000,0x60:1}
    defaults.update(queue or {})
    for off,value in defaults.items(): word(hc+off,value)
    owned=0xabcd0000
    u.mem_map(owned,0x22000)
    u.mem_write(owned,b'\xaa'*0x22000)
    calls=[];fields={};lines=[];samples=[];writes=[];polls=[]
    def cache_line(cpu,addr,size,data):
        from unicorn.arm64_const import UC_ARM64_REG_X11
        lines.append(cpu.reg_read(UC_ARM64_REG_X11))
    def sample(cpu,addr,size,data):
        samples.append(1)
        for off,val in (changes or {}).get(len(samples),{}).items(): word(hc+off,val)
        if len(samples)==2 and fail=='drift': word(hc+0x24,7)
    u.hook_add(UC_HOOK_CODE,cache_line,begin=sym['clean_line'],end=sym['clean_line'])
    u.hook_add(UC_HOOK_CODE,sample,begin=sym['snapshot'],end=sym['snapshot'])
    def ret(cpu,value):
        cpu.reg_write(regs[0],value)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
    def handle(cpu,addr,size,data):
        a,b,c,d=[cpu.reg_read(r) for r in regs]
        if addr==mapper:
            assert (b,c)==(4096,3 if a==0x1d84000 else 1)
            mapped={0x177000:mmio,0x1d84000:mmio+4096,0x15000000:mmio+8192}[a]
            ret(cpu,0 if fail=='map' else mapped)
        elif addr==alloc:
            assert (a,b,c,d)==(0x12345678,0x813,0x22000,4096)
            calls.append('alloc');ret(cpu,0 if fail=='alloc' else obj)
        elif addr==obj+0x800:
            assert a==obj
            calls.append('virtual');ret(cpu,0 if fail=='virtual' else 0xabcd0000)
        elif addr==obj+0x804:
            assert (a,b,c,d)==(obj,0,sp-160,0x800)
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
    def write(cpu,access,addr,size,value,data):
        off=addr-hc
        assert size==4 and off in (0x50,0x54,0x60)
        if off!=0x60: assert cpu.mem_read(hc+0x60,4)==bytes(4)
        if off==0x60 and value==1:
            assert struct.unpack('<Q',cpu.mem_read(hc+0x50,8))[0]==defaults[0x50]+(defaults.get(0x54,0)<<32)
        writes.append((off,value))
    u.hook_add(UC_HOOK_MEM_WRITE,write,begin=mmio,end=mmio+12287)
    def poll(cpu,addr,size,data):
        polls.append(1)
        if stuck==len(polls): word(hc+0x60,1-writes[-1][1])
    u.hook_add(UC_HOOK_CODE,poll,begin=sym['poll_rsr'],end=sym['poll_rsr'])
    u.emu_start(site,sym['halt'],count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and fields[0]==terminal,(name,fields,writes)
    assert u.reg_read(UC_ARM64_REG_SP)==sp
    expected=[] if terminal in (33,34,39) else ['alloc'] if terminal==35 else ['alloc','virtual','release'] if terminal==36 else ['alloc','virtual','segment','release']
    if terminal in (67,68): expected.remove('release')
    assert calls==expected
    assert writes==list(sequence),(name,writes,sequence)
    if terminal==16:
        assert fields[9]==15 and fields[10]+(fields[11]<<32)==phys
        assert fields[12]+(fields[13]<<32)==defaults[0x50]+(defaults.get(0x54,0)<<32) and fields[14]==1
    if 'segment' in calls:
        assert fields[2]+(fields[3]<<32)==phys and fields[4]+(fields[5]<<32)==length
    if lines:
        assert len(samples)>=2 and lines[0]==owned and len(lines)>=2
        assert lines==list(range(owned,owned+12288,lines[1]-lines[0]))
        expected=bytearray(12288)
        struct.pack_into('<8I',expected,0,0x14000000,0,15,0,(phys+4096)&0xffffffff,(phys+4096)>>32,0x00800080,0x01000001)
        expected[4096:4128]=bytes.fromhex('01400000 00000000 00000000 00001000 28000000 00010000 01000000 00000000')
        struct.pack_into('<QII',expected,5120,phys+8192,0,4095)
        if name=='observed address':
            assert u.mem_read(owned,12288)==(ROOT/'reports/ufs-r5-r1/descriptor-oracle.bin').read_bytes()
        assert u.mem_read(owned,12288)==expected and u.mem_read(owned+12288,4)==b'\xaa'*4
    else:
        assert not lines and u.mem_read(owned,12288)==b'\xaa'*12288
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xf700+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),calls=calls,device_writes=writes)

if __name__=='__main__':
    stop=[(0x60,0)]
    bind=stop+[(0x50,0xcbd6c000),(0x54,8)]
    rollback=bind+[(0x50,0xc54e6000),(0x54,0)]
    full=rollback+[(0x60,1)]
    cases=[
        case('complete',16,sequence=full),
        case('nonzero firmware high',16,queue={0x54:1},sequence=bind+[(0x50,0xc54e6000),(0x54,1),(0x60,1)]),
        case('controller mismatch',33,cap=1),case('no allocation',35,fail='alloc'),
        case('overlap',52,phys=0xc54e6000),case('short physical segment',37,length=4096),
        case('MCQ selected',48,queue={0x300:1}),case('interrupts enabled',49,queue={0x24:1}),
        case('doorbell pending',50,queue={0x58:1}),case('late base drift',54,changes={3:{0x50:0xc5550000}}),
        case('stop timeout',65,stuck=1,sequence=stop+[(0x60,1)]),
        case('changed after stop',64,changes={4:{0x78:1}},sequence=stop),
        case('owned base low ignored',66,changes={5:{0x50:0xc54e6000}},sequence=full),
        case('owned base high ignored',66,changes={5:{0x54:0}},sequence=full),
        case('foreign base',67,changes={5:{0x54:9}},sequence=bind),
        case('doorbell after bind',67,changes={5:{0x58:1}},sequence=bind),
        case('rollback wrong base',67,changes={6:{0x54:8}},sequence=rollback),
        case('restart timeout',68,stuck=2,sequence=full),
        case('post-restart drift',68,changes={7:{0x78:1}},sequence=full)]
    (report/'host-test.json').write_text(json.dumps(cases,indent=2))
    print(len(cases),'cases passed')
