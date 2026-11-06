"""Run the shipped terminal hook with synthetic GCC/HCI, decode its actual pixels."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC
import flush_trace_inputs as trace

REV = 2 if sys.argv[1:] == ['--r2'] else 1
WORK = ROOT/f'out/ufs-r1-r{REV}'
REPORT = ROOT/f'reports/ufs-r1-r{REV}'
proof = json.loads((REPORT/'build.json').read_bytes())
kernel = (WORK/'kernel.macho').read_bytes()
builder = trace.builder()
macho = builder.macho(kernel)
symbols = json.loads((WORK/'symbols.json').read_bytes())
slide = 0xfffffff000000000
start = trace.START-slide
site = int(proof['site'],16)-slide
mapper = int(proof['map_function'],16)-slide
scratch = int(proof['scratch'],16)-slide
offsets = [8,0x34,0x30,0x20,0x50,0x54,0x58,0x60,0x70,0x74,0x78,0x80]
gcc, hc, fb, stride = 0x20000000,0x20010000,0x30000000,5760
font = struct.unpack_from('<16I',kernel,builder.backed(macho,symbols['font'],64))


def exercise(name, power, axi, ahb, fail, expected, version=None):
    u = Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    for address in (start,site,mapper,scratch,gcc,hc):
        u.mem_map(address & ~4095,4096)
    for address,size in ((start,proof['code_bytes']),(site,4)):
        at = builder.backed(macho,address+slide,size)
        u.mem_write(address,kernel[at:at+size])
    u.mem_map(fb,0x700000)
    u.mem_write(scratch,struct.pack('<QQ',fb,stride))
    for off,value in zip((4,0x18,0x24),(power,axi,ahb)):
        u.mem_write(gcc+off,struct.pack('<I',value))
    for off in offsets:
        u.mem_write(hc+off,struct.pack('<I',(version if off==8 and version is not None else 0x12345600+off)))
    reads, maps = [], []
    def mapped(cpu, addr, size, data):
        phys = cpu.reg_read(UC_ARM64_REG_X0)
        assert cpu.reg_read(UC_ARM64_REG_X1)==4096 and cpu.reg_read(UC_ARM64_REG_X2)==1
        maps.append(phys)
        va = {0x177000:gcc,0x1d84000:hc}[phys]
        cpu.reg_write(UC_ARM64_REG_X0,0 if phys==fail else va)
        cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
    def memory(cpu, access, addr, size, value, data):
        assert size==4
        reads.append(addr)
    def forbidden(*args):
        raise AssertionError('Device write')
    u.hook_add(UC_HOOK_CODE,mapped,begin=mapper,end=mapper)
    for base in (gcc,hc):
        u.hook_add(UC_HOOK_MEM_READ,memory,begin=base,end=base+4095)
        u.hook_add(UC_HOOK_MEM_WRITE,forbidden,begin=base,end=base+4095)
    u.emu_start(site,symbols['halt']-slide,count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==symbols['halt']-slide
    def row(index):
        chars=[]
        for digit in range(12):
            glyph=0
            for y in range(5):
                for x in range(4):
                    address = fb+(576+32*index+4*y)*stride+(384 if REV==2 else 1024)+96*digit+16*x
                    glyph = glyph*2 + int(u.mem_read(address,4)==b'\xff'*4)
            chars.append(format(font.index(glyph),'X'))
        return ''.join(chars)
    assert row(0)==f'F100{expected:08X}'
    if fail!=0x177000:
        for n,value in enumerate((power,axi,ahb),1):
            assert row(n)==f'{0xf100+n:04X}{value:08X}'
    if expected==16:
        for n,off in enumerate(offsets,4):
            assert row(n)==f'{0xf100+n:04X}{0x12345600+off:08X}'
    if expected==35:
        assert row(4)==f'F104{version:08X}'
    assert reads==([] if fail==0x177000 else [gcc+4,gcc+24,gcc+36])+([hc+off for off in offsets] if expected==16 else [hc+8] if expected==35 else [])
    assert maps==[0x177000]+([0x1d84000] if expected in (16,35) or fail==0x1d84000 else [])
    return dict(case=name,terminal=row(0),device_reads=len(reads),device_writes=0)


if __name__=='__main__':
    on=1<<31
    cases=[('success',on,1,1,None,16),('power-off',0,1,1,None,32),
           ('axi-disabled',on,0,1,None,33),('axi-stopped',on,on+1,1,None,33),
           ('ahb-disabled',on,1,0,None,33),('ahb-stopped',on,1,on+1,None,33),
           ('gcc-map-failure',on,1,1,0x177000,34),('hci-map-failure',on,1,1,0x1d84000,34)]
    if REV == 2:
        cases.extend([('nuwa-observed',0xf822f800,1,on+3,None,16),
                      ('hwcg-without-enable',on,1,on+2,None,33),
                      ('axi-off-even-with-hwcg',on,on+3,on+3,None,33),
                      ('zero-version',on,1,on+3,None,35,0),
                      ('ones-version',on,1,on+3,None,35,0xffffffff)])
    results=[exercise(*case) for case in cases]
    (REPORT/'host-test.json').write_text(json.dumps(results,indent=2)+'\n')
    print(len(results),'AArch64 cases passed')
