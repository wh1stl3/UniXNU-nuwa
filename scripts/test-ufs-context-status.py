"""Execute the packaged AArch64 context-bank survey against bounded synthetic MMIO."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC
import flush_trace_inputs as trace

work = ROOT/'out/ufs-r3-r1'
report = ROOT/'reports/ufs-r3-r1'
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

def case(name, changes, terminal, fail=0, sharing=1):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for addr in (site, mapper, scratch, sym['trace_1'], mmio, mmio+0x1000, mmio+0x82000):
        u.mem_map(addr & ~4095,4096)
    for addr,size in ((site,4),(sym['trace_1'],build['code_bytes'])):
        offset=B.backed(m,addr+slide,size)
        u.mem_write(addr,kernel[offset:offset+size])
    u.mem_map(fb,0x700000)
    u.mem_write(scratch,struct.pack('<QQ',fb,stride))
    registers={0:0x2f0406,0x20:0x4c017e69,0x24:0x60000046,0x808:0x80000060,
               0xc08:2,0x1008:0x10000,0x1808:1,0x82000:1,0x82058:2,
               0x82010:3,0x82030:4,0x82020:0x89abcdef,0x82024:0x12345678}
    registers.update(changes)
    for off,value in registers.items():
        u.mem_write(mmio+off,struct.pack('<I',value))
    reads=[]; fields={}; maps=[]
    def mapped(cpu,addr,size,data):
        addr=cpu.reg_read(UC_ARM64_REG_X0)
        assert addr in (0x15000000,0x15001000,0x15082000) and cpu.reg_read(UC_ARM64_REG_X1)==4096 and cpu.reg_read(UC_ARM64_REG_X2)==1
        maps.append(addr)
        cpu.reg_write(UC_ARM64_REG_X0,0 if fail==addr else mmio+addr-0x15000000)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
    def draw(cpu,addr,size,data):
        fields[cpu.reg_read(UC_ARM64_REG_X0)]=cpu.reg_read(UC_ARM64_REG_X1)
    def read(cpu,access,addr,size,value,data):
        assert size==(8 if addr==mmio+0x82020 else 4)
        reads.append(addr-mmio)
    def write(*args):
        raise AssertionError('device write')
    for addr,cb in ((mapper,mapped),(sym['draw'],draw)):
        u.hook_add(UC_HOOK_CODE,cb,begin=addr,end=addr)
    u.hook_add(UC_HOOK_MEM_READ,read,begin=mmio,end=mmio+0x82fff)
    u.hook_add(UC_HOOK_MEM_WRITE,write,begin=mmio,end=mmio+0x82fff)
    u.emu_start(site,sym['halt'],count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and fields[0]==terminal
    if terminal==33:
        assert maps==[0x15000000] and all(off<4096 for off in reads)
    elif fail:
        assert maps[-1]==fail and all(off < fail-0x15000000 for off in reads)
    else:
        assert maps==[0x15000000,0x15001000,0x15082000]
        assert fields[1]==sharing
        expected=[0x1008,0x1808,0x82000,0x82058]
        if terminal==16:
            expected.extend([0x82010,0x82030,0x82020])
            assert fields[8]==0x89abcdef and fields[9]==0x12345678
        assert [off for off in reads if off>=4096]==expected
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xf300+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),reads=len(reads),device_writes=0)

cases=[
 ('live S1 AArch64',{},16),('shared bank',{0x804:0x80000070,0xc04:2},16,0,2),
 ('bank M clear',{0x82000:0},17),('S2 context',{0x1008:0},18),
 ('32-bit context',{0x1808:0},18),('changed bank',{0xc08:3},33),
 ('masked target',{0x808:0x80010060},33),('duplicate',{0x804:0x80000060},33),
 ('missing target',{0x808:0},33),('geometry drift',{0x24:0x70000046},33),
 ('ID drift',{0x20:0},33),('extended ID',{0:8},33),('client disabled',{0:1},33),
 ('GR0 map failed',{},34,0x15000000),('GR1 map failed',{},34,0x15001000),
 ('CB2 map failed',{},34,0x15082000)]
if __name__=='__main__':
    result=[case(*args) for args in cases]
    (report/'host-test.json').write_text(json.dumps(result,indent=2))
    print(len(result),'cases passed')
