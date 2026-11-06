"""Execute the packaged AArch64 transfer-list stop/restore survey against bounded synthetic MMIO."""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_SP
import flush_trace_inputs as trace

work = ROOT/'out/ufs-r6-r1'
report = ROOT/'reports/ufs-r6-r1'
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

def case(name,terminal,expected,initial=None,changes=None,stuck=None):
    u=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    gcc,hc,stack=mmio,mmio+4096,0x26000000
    for page in set(a&~4095 for a in (site,mapper,scratch,sym['trace_1'],sym['font']+63,gcc,hc,stack)):
        u.mem_map(page,4096)
    for a,size in ((site,4),(sym['trace_1'],build['code_bytes'])):
        offset=B.backed(m,a+slide,size)
        u.mem_write(a,kernel[offset:offset+size])
    u.mem_map(fb,0x700000)
    u.mem_write(scratch,struct.pack('<QQ',fb,stride))
    sp=stack+0xf00
    u.reg_write(UC_ARM64_REG_SP,sp)
    def word(addr,value): u.mem_write(addr,struct.pack('<I',value))
    word(gcc+4,1<<31);word(gcc+24,1);word(gcc+36,0x80000003)
    state={0:0x3587031f,8:0x400,0x34:1,0x30:0x10f,0x20:0x400,0x50:0xc54e6000,0x70:0xc54e7000,0x60:1}
    state.update(initial or {})
    for k,v in state.items():word(hc+k,v)
    writes=[];fields={};samples=[];permissions=[]
    def step(cpu,addr,size,data):
        a=cpu.reg_read(UC_ARM64_REG_X0);b=cpu.reg_read(UC_ARM64_REG_X1)
        if addr==mapper:
            prot=cpu.reg_read(UC_ARM64_REG_X2)
            assert (a,b,prot) in [(0x177000,4096,1),(0x1d84000,4096,3)]
            permissions.append(prot)
            cpu.reg_write(UC_ARM64_REG_X0,gcc if prot==1 else hc)
            cpu.reg_write(UC_ARM64_REG_PC,cpu.reg_read(UC_ARM64_REG_LR))
        elif addr==sym['snapshot']:
            samples.append(1)
            for k,v in (changes or {}).get(len(samples),{}).items():word(hc+k,v)
        elif addr==sym['poll_rsr']:
            if stuck==len(writes):word(hc+0x60,1-writes[-1])
        else:fields[a]=b
    for a in (mapper,sym['draw'],sym['snapshot'],sym['poll_rsr']):
        u.hook_add(UC_HOOK_CODE,step,begin=a,end=a)
    def write(cpu,access,addr,size,value,data):
        assert (addr,size)==(hc+0x60,4) and value in (0,1)
        writes.append(value)
    u.hook_add(UC_HOOK_MEM_WRITE,write,begin=gcc,end=hc+4095)
    u.emu_start(site,sym['halt'],count=4000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and u.reg_read(UC_ARM64_REG_SP)==sp
    assert fields[0]==terminal and writes==expected and permissions==[1,3],(name,fields,writes,struct.unpack("<13I",u.mem_read(sp-240,52)),len(samples))
    if terminal==16:
        assert [fields[i] for i in (1,2,3,4)]==[0,0,0,1]
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xf600+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),run_stop_writes=writes)

if __name__=='__main__':
    tests=[
        case('observed handoff',16,[0,1]),
        case('IE active',49,[],{0x24:1}),case('MCQ active',49,[],{0x300:1}),
        case('HCE disabled',49,[],{0x34:0}),case('unexpected IS',49,[],{0x20:0x401}),
        case('transfer busy',50,[],{0x58:1}),case('management busy',50,[],{0x78:1}),
        case('wrong RSR',49,[],{0x60:0}),case('task RSR',49,[],{0x80:1}),
        case('misaligned list',49,[],{0x50:0xc54e6004}),case('overlapping lists',49,[],{0x70:0xc54e6000}),
        case('pre-stop drift',51,[],changes={2:{0x50:0xc54e8000}}),
        case('busy after STOP',52,[0],changes={3:{0x58:1}}),
        case('different list after STOP',52,[0],changes={3:{0x54:1}}),
        case('drift after restore',53,[0,1],changes={4:{0x24:1}}),
        case('stop timeout',55,[0,1],stuck=1),case('restore timeout',54,[0,1],stuck=2)]
    (report/'host-test.json').write_text(json.dumps(tests,indent=2))
    print(len(tests),'cases passed')
