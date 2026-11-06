"""Execute the packaged AArch64 stream survey against bounded synthetic MMIO."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC
import flush_trace_inputs as trace

work = ROOT/'out/ufs-r2-r1'
report = ROOT/'reports/ufs-r2-r1'
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

def case(name, cr, idr, entries, terminal, matched=(), fail=False):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for addr in (site, mapper, scratch, sym['trace_1'], mmio):
        u.mem_map(addr & ~4095,4096)
    for addr,size in ((site,4),(sym['trace_1'],build['code_bytes'])):
        offset=B.backed(m,addr+slide,size)
        u.mem_write(addr,kernel[offset:offset+size])
    u.mem_map(fb,0x700000)
    u.mem_write(scratch,struct.pack('<QQ',fb,stride))
    registers={0:cr,0x20:idr,0x24:0x41,0x28:0x1242}
    for index,(smr,s2cr) in entries.items():
        registers[0x800+4*index]=smr
        registers[0xc00+4*index]=s2cr
    for off,value in registers.items():
        u.mem_write(mmio+off,struct.pack('<I',value))
    reads=[]; fields={}
    def mapped(cpu,addr,size,data):
        assert [cpu.reg_read(reg) for reg in (UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2)]==[0x15000000,4096,1]
        cpu.reg_write(UC_ARM64_REG_X0,0 if fail else mmio)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
    def draw(cpu,addr,size,data):
        fields[cpu.reg_read(UC_ARM64_REG_X0)]=cpu.reg_read(UC_ARM64_REG_X1)
    def read(cpu,access,addr,size,value,data):
        assert size==4
        reads.append(addr-mmio)
    def write(*args):
        raise AssertionError('device write')
    for addr,cb in ((mapper,mapped),(sym['draw'],draw)):
        u.hook_add(UC_HOOK_CODE,cb,begin=addr,end=addr)
    u.hook_add(UC_HOOK_MEM_READ,read,begin=mmio,end=mmio+4095)
    u.hook_add(UC_HOOK_MEM_WRITE,write,begin=mmio,end=mmio+4095)
    u.emu_start(site,sym['halt'],count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and fields[0]==terminal
    expected=[] if fail else [0,0x20]
    if not fail and idr not in (0,0xffffffff):
        expected.extend([0x24,0x28])
    if terminal in (16,17,18):
        for i in range(idr&255):
            expected.append(0x800+4*i)
            if matched and i==matched[0]:
                expected.append(0xc00+4*i)
        assert fields[5]==len(matched)
        if matched:
            i=matched[0]
            assert [fields[n] for n in (6,7,8)]==[i,*entries[i]]
    assert reads==expected
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xf200+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),reads=len(reads),device_writes=0)

cases=[
 ('exact translated',0,sms+128,{127:(valid+0x60,7)},16,(127,)),
 ('masked bypass',0,sms+4,{2:(valid+(3<<16)+0x61,1<<16)},16,(2,)),
 ('fault route',0,sms+1,{0:(valid+0x60,2<<16)},16,(0,)),
 ('absent',0,sms+3,{0:(0x60,0),1:(valid+0x61,0)},17),
 ('ambiguous',0,sms+4,{1:(valid+0x60,0),3:(valid+(1<<16)+0x61,0)},18,(1,3)),
 ('client disabled',1,sms+1,{},32),('extended ids',8,sms+1,{},33),
 ('indexed mode',0,1,{},33),('no slots',0,sms,{},33),
 ('excess slots',0,sms+129,{},33),('zero id',0,0,{},33),
 ('invalid id',0,0xffffffff,{},33),('map failure',0,0,{},34,(),True)]
if __name__=='__main__':
    result=[case(*args) for args in cases]
    (report/'host-test.json').write_text(json.dumps(result,indent=2))
    print(len(result),'cases passed')
