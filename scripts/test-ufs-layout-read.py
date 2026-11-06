"""Execute the packaged AArch64 DMA buffer probe against bounded synthetic MMIO."""
import json
import struct
import zlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'out/python-tools'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_LR, UC_ARM64_REG_PC, UC_ARM64_REG_X3, UC_ARM64_REG_SP
import flush_trace_inputs as trace

work = ROOT/'out/ufs-r10-r1'
report = ROOT/'reports/ufs-r10-r1'
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
         fail='', no_task=False, queue=None, changes=None, stuck=0, sequence=(), power=0x11, after=0x11):
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
    for addr in (site,mapper,scratch,sym['trace_1'],sym['font']+63,mmio,mmio+4096,mmio+8192,mmio+12288,mmio+16384,task,alloc,obj,stack):
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
    smmu=mmio+8192
    for off,val in [(0,0x2f0406),(0x20,0x4c017e69),(0x24,0x60000046),(0x808,0x80000060),(0xc08,2),(0x1008,0x1f000),(0x1808,1),(0x2000,0x0a9f00e0),(0x2058,0x400)]:word(smmu+off,val)
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
            mapped={0x177000:mmio,0x1d84000:mmio+4096,0x15000000:mmio+8192,0x15001000:mmio+12288,0x15082000:mmio+16384}[a]
            ret(cpu,0 if fail=='map' else mapped)
        elif addr==alloc:
            assert (a,b,c,d)==(0x12345678,0x813,0x22000,4096)
            calls.append('alloc');ret(cpu,0 if fail=='alloc' else obj)
        elif addr==obj+0x800:
            assert a==obj
            calls.append('virtual');ret(cpu,0 if fail=='virtual' else 0xabcd0000)
        elif addr==obj+0x804:
            assert (a,b,c,d)==(obj,0,sp-288,0x800)
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
    phases=[];responses=[]; ack=[]
    def write(cpu,access,addr,size,value,data):
        off=addr-hc
        assert size==4 and off in (0x50,0x54,0x60,0x58,0x20)
        if off in (0x50,0x54): assert cpu.mem_read(hc+0x60,4)==bytes(4)
        base=struct.unpack('<Q',cpu.mem_read(hc+0x50,8))[0]
        if off==0x58:
            stage=fields[5]
            assert value==1 and base==phys and cpu.mem_read(hc+0x60,4)==struct.pack('<I',1)
            ucd=bytes(cpu.mem_read(owned+4096,32))
            assert ucd[0]==(0x16 if stage in (6,8) else 0 if stage==0 else 1) and ucd[3]==int(stage in (0,6,8))
            if stage in (6,8):assert ucd[5]==1 and ucd[12:16]==bytes.fromhex('03020000')
            if stage==7:assert ucd[2]==0xd0 and ucd[16:22]==bytes.fromhex('1b0000001000')
            assert ucd[16]==[0,0,0x25,0x28,0x28,0x28,0,0x1b,0,0x28,0x28][stage]
            n=[0,0,8,4096,4096,len(entries),0,0,0,4096,4096][stage]
            assert (stage in (6,8) or int.from_bytes(ucd[12:16],'big')==n) and ucd[1]==(0x40 if n else 0)
            utrd=struct.unpack('<8I',cpu.mem_read(owned,32))
            assert utrd==(0x14000000 if n else 0x10000000,0,15,0,(phys+4096)&0xffffffff,(phys+4096)>>32,0x800080,0x1000000+int(n>0))
            if n:
                assert struct.unpack('<QII',cpu.mem_read(owned+5120,16))==(phys+8192,0,n-1)
            if stage==5: assert ucd[16:26]==bytes.fromhex("28000000000200000100")
            if stage in (9,10):
                assert struct.unpack_from('>I',ucd,18)[0]==(61850623 if stage==9 else 61850619)
                assert struct.unpack_from('>H',ucd,23)[0]==1
            if stage in (3,4): assert ucd[16:26]==bytes.fromhex('28000000000100000100')
            phases.append(stage)
        if off==0x20:
            assert value==1 and len(ack)<len(phases)
            ack.append(1)
        writes.append((off,value))
    def model(cpu,addr,size,data):
        if addr==sym['poll_rsr']:
            if cpu.mem_read(hc+0x20,4)==b'\x01\0\0\0':word(hc+0x20,0x400)
            return
        if addr==sym['submit_one']:
            if ack:word(hc+0x20,0x400)
            return
        stage=phases[-1]
        if len(responses)==len(phases):return
        responses.append(stage)
        if fail=='fatal':
            word(hc+0x20,0x10400);return
        if fail=='timeout':
            from unicorn.arm64_const import UC_ARM64_REG_X11
            cpu.reg_write(UC_ARM64_REG_X11,0);return
        word(hc+0x58,0);word(hc+0x20,0x401);word(owned+8,2 if fail=='ocs' else 0)
        resp=bytearray(32);resp[0]=0x20 if stage==0 else 0x21;resp[3]=int(stage==0)
        if stage in (6,8):
            resp[0]=0x36;resp[3]=1;resp[12]=3;resp[13]=1 if fail=='echo' else 2
            resp[20:24]=struct.pack('>I',power if stage==6 else after)
            if fail=='query-error':resp[6]=0xf6
        if stage==7:
            resp[2]=0 if fail=='wrong-wlun' else 0xd0
            if fail=='ssu-error':resp[7]=2
        if stage==1 and fail in ('r8-persistent','ready-after-wait') and (phases.count(1)==1 or fail=='r8-persistent'):
            resp.extend(bytes(32));resp[6]=1;resp[7]=2;resp[10:12]=bytes.fromhex('0014');resp[32:34]=bytes.fromhex('0012');resp[34]=0x70;resp[36]=2
        if stage==1 and fail=='tur':resp[7]=2
        if stage==1 and fail in ('unit-attention','twice-UA','qemu10') and (phases.count(1)==1 or fail=='twice-UA'):
            resp.extend(bytes(32));resp[6]=1;resp[7]=2
            resp[10:12]=bytes.fromhex('1400' if fail=='qemu10' else '0014')
            resp[32:34]=b'\x00\x12';resp[34]=0x70;resp[36]=6;resp[46]=0x29
        if stage==2 and fail=='residual':resp[15]=1
        if fail=='tag':resp[3]=7
        cpu.mem_write(owned+4608,bytes(resp))
        if stage==2:cpu.mem_write(owned+8192,struct.pack('>II',61850623,512 if fail=='geometry' else 4096))
        if stage in (3,4):cpu.mem_write(owned+8192,bytes(4096) if fail=='crc' else fixture(1 if fail=='collision' and stage==4 else 0,fail=='oversize'))
        if stage==5:cpu.mem_write(owned+8192,bytes(len(entries)) if fail=='entries' else layout(fail))
        if stage==9:cpu.mem_write(owned+8192,backup(fail))
        if stage==10:cpu.mem_write(owned+8192,layout(fail if fail!='mirror-byte' else 'other-valid-bytes'))
    u.hook_add(UC_HOOK_MEM_WRITE,write,begin=mmio,end=mmio+20479)
    for n in ('poll_rsr','nop_poll','submit_one'):u.hook_add(UC_HOOK_CODE,model,begin=sym[n],end=sym[n])
    def time_tick(cpu,addr,size,data):
        from unicorn.arm64_const import UC_ARM64_REG_X9
        cpu.reg_write(UC_ARM64_REG_X9,0)  # virtual 50ms has elapsed
    u.hook_add(UC_HOOK_CODE,time_tick,begin=sym['settle_loop'],end=sym['settle_loop'])
    u.emu_start(site,sym['halt'],count=18000000)
    assert u.reg_read(UC_ARM64_REG_PC)==sym['halt'] and fields[0]==terminal,(name,fields,writes)
    assert u.reg_read(UC_ARM64_REG_SP)==sp
    wanted=list(sequence)
    if wanted[:2]==[0,1]:wanted.insert(1,6)
    if terminal==16:wanted.extend([9,10])
    assert phases==wanted,(name,phases,wanted)
    if 8 in phases:assert fields[15]==(after<<8|power)
    elif 6 in phases and fail not in ('echo','query-error') and power<=255:assert fields[15]==0xff00+power
    if terminal in (0x50,0x51):
        assert 'release' not in calls and len(ack)==0 and writes[-1]==(0x58,1)
    elif phases:
        assert calls[-1]=='release' and writes[-3:]==[(0x50,0xc54e6000),(0x54,0),(0x60,1)] and len(ack)==len(phases)
    if terminal==16:
        assert fields[9]==63 and fields[5]==10 and fields[1]==3110976 and fields[2]==61850618 and fields[3]==0xf63ae02d and fields[4]==0x4edcb8b5 and fields[7]==61850623 and fields[8]==4096 and fields[13]==0xe7514394
    font=struct.unpack_from('<16I',kernel,B.backed(m,sym['font']+slide,64))
    for index,value in fields.items():
        for digit,char in enumerate(f'{0xfa00+index:04X}{value:08X}'):
            bits=0
            for y in range(5):
                for x in range(4):
                    addr=fb+(576+32*index+y*4)*stride+384+96*digit+16*x
                    bits=2*bits+int(u.mem_read(addr,4)==b'\xff'*4)
            assert bits==font[int(char,16)]
    return dict(case=name,status=hex(terminal),calls=calls,device_writes=writes)

# Synthetic CRC-matching sector, never presented as actual device bytes.
def forge(blob,target,offset):
    base=zlib.crc32(blob);basis={}
    for i in range(32):
        tmp=bytearray(blob);tmp[offset+i//8]^=1<<(i%8);v=zlib.crc32(tmp)^base;mask=1<<i
        while v:
            b=v.bit_length()-1
            if b not in basis:
                basis[b]=(v,mask);break
            x,y=basis[b];v^=x;mask^=y
    v=base^target;mask=0
    while v:
        x,y=basis[v.bit_length()-1];v^=x;mask^=y
    blob[offset:offset+4]=mask.to_bytes(4,'little')
    assert zlib.crc32(blob)==target
    return bytes(blob)

def layout(fail=''):
    raw=bytearray(4096)
    for i,part in enumerate(json.loads((ROOT/'reports/ufs-r9-r1/trial/android-gpt-layout.json').read_bytes())['rows']):
        import uuid
        off=i*128
        raw[off:off+16]=uuid.UUID(part['type']).bytes_le
        struct.pack_into('<QQ',raw,off+32,part['first']+(i==5 and fail=='gap'),part['last'])
        name=part['name'] if i!=31 or fail!='bad-name' else 'not-data'
        name=name.encode('utf-16le');raw[off+56:off+56+len(name)]=name
    if fail=='other-valid-bytes':raw[16]=3
    return forge(raw,0x4edcb8b5,48)
entries=layout()
def fixture(marker=0,oversize=False):
    blob=bytearray(4096);blob[:8]=b'EFI PART';blob[128]=marker
    struct.pack_into('<QQQQ',blob,24,1,61850623,6,61850618)
    struct.pack_into('<QIII',blob,72,2,1025 if oversize else 32,128,0x4edcb8b5)
    return forge(blob,0xe7514394,4092)
def backup(fail):
    raw=bytearray(fixture());raw[4092:]=bytes(4)
    struct.pack_into('<QQ',raw,24,61850623,1)
    struct.pack_into('<Q',raw,72,3110976 if fail=='redirect' else 61850619)
    if fail=='wrong-guid':raw[56]=1
    return forge(raw,0xf63ae02d,4092)

if __name__=='__main__':
    cases=[case('end-to-end fixture',16,sequence=range(6)),case('one reset unit attention',16,fail='unit-attention',sequence=[0,1,1,2,3,4,5]),case('no second retry',84,fail='twice-UA',sequence=[0,1,1]),case('model bad sense length',84,fail='qemu10',sequence=range(2)),case('same CRC different bytes',86,fail='collision',sequence=range(5)),case('oversize GPT array',85,fail='oversize',sequence=range(4)),case('array CRC mismatch',86,fail='entries',sequence=range(6)),case('wrong tag',83,fail='tag',sequence=[0]),
           case('bad ocs',82,fail='ocs',sequence=[0]),case('check condition',84,fail='tur',sequence=range(2)),
           case('short reply',83,fail='residual',sequence=range(3)),case('wrong geometry',85,fail='geometry',sequence=range(3)),
           case('wrong data',86,fail='crc',sequence=range(4)),case('fatal',80,fail='fatal',sequence=[0]),
           case('timeout',81,fail='timeout',sequence=[0]),case('pending',50,queue={0x58:1}),case('no descriptor',35,fail='alloc')]
    cases.extend([
        case('powerdown wake and full read',16,power=0x33,sequence=[0,6,7,8,1,2,3,4,5]),
        case('sleep wake and full read',16,power=0x22,sequence=[0,6,7,8,1,2,3,4,5]),
        case('QEMU zero power value',87,power=0,sequence=[0,6]),
        case('unknown full-width value',87,power=0x133,sequence=[0,6]),
        case('no active readback',87,power=0x33,after=0x33,sequence=[0,6,7,8]),
        case('bad query echo',83,fail='echo',sequence=[0,6]),
        case('query error',83,fail='query-error',sequence=[0,6]),
        case('wrong SSU response LUN',83,power=0x33,fail='wrong-wlun',sequence=[0,6,7]),
        case('wake rejected',84,power=0x33,fail='ssu-error',sequence=[0,6,7]),
        case('active but still R8 NOT READY',84,fail='r8-persistent',sequence=[0,6,1,1,1]),
        case('TUR settles',16,fail='ready-after-wait',sequence=[0,6,1,1,2,3,4,5])])
    cases.extend([case('gap in real extent layout',89,fail='gap',sequence=range(6)),
                  case('missing protected name',89,fail='bad-name',sequence=range(6)),
                  case('header redirect into userdata',90,fail='redirect',sequence=[0,1,2,3,4,5,9]),
                  case('backup disk GUID differs',90,fail='wrong-guid',sequence=[0,1,2,3,4,5,9]),
                  case('same CRC different backup entries',90,fail='mirror-byte',sequence=[0,1,2,3,4,5,9,10])])
    (report/'host-test.json').write_text(json.dumps(cases,indent=2))
    print(len(cases),'cases passed')
