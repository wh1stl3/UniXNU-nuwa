"""Compile the actual patched 8796 check_for_panic_log body and test its DT guards.
Host DT/map adapters are test doubles; no kernel hardware or whole-kernel qualification.
"""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/pexpert/arm/pe_init.c')
DEBUG=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/osfmk/kern/debug.h')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False)
 before=SOURCE.read_text();(a.work/'pexpert/arm').mkdir(parents=True);(a.work/'pexpert/arm/pe_init.c').write_text(before,encoding='utf-8',newline='\n')
 def linux(path):return '/mnt/d/'+path.resolve().as_posix().split(':/',1)[1]
 patch=ROOT/'patches/xnu-8796-candidates/native-dt-panic-region.patch'
 cmd=['wsl','-d','Ubuntu-22.04','--','patch','--fuzz=0','-p1','-d',linux(a.work),'-i',linux(patch)]
 r=subprocess.run(cmd,capture_output=True,text=True);r.check_returncode();after=(a.work/'pexpert/arm/pe_init.c').read_text()
 body=after[after.index('static void\ncheck_for_panic_log(void)'):after.index('\nint\nPE_initialize_console')]
 header=DEBUG.read_text();start=header.index('struct embedded_panic_header {');end=header.index('\n\n\n#define MACOS_PANIC_HEADER_CURRENT_VERSION',start);struct_=header[start:end]
 oslen=int(re.search(r'#define EMBEDDED_PANIC_HEADER_OSVERSION_LEN\s+(\d+)',header)[1])
 prefix='''typedef unsigned long uintptr_t; typedef unsigned long uint64_t; typedef unsigned int uint32_t; typedef unsigned long eph_panic_flags_t; typedef char uuid_string_t[37];
#define UINTPTR_MAX (~(uintptr_t)0)
#define TRUE 1
#define kSuccess 1
#define XNU_DT_PANIC_REGION 1
#define PLATFORM_PANIC_LOG_PADDR 0x3c0fc000
#define PLATFORM_PANIC_LOG_SIZE 16384
#define EMBEDDED_PANIC_MAGIC 0x46554e4b
#define EMBEDDED_PANIC_HEADER_OSVERSION_LEN OSLEN
'''.replace('OSLEN',str(oslen))+struct_+'''
typedef const void *DTEntry;
static uintptr_t gPanicBase; static unsigned int gPanicSize,panic_text_len; static struct embedded_panic_header *panic_info; static int panic_console_available;
int SecureDTLookupEntry(DTEntry,const char*,DTEntry*);
int SecureDTGetProperty(DTEntry,const char*,const void**,unsigned int*);
uintptr_t ml_io_map_wcomb(uintptr_t,unsigned long);
void bzero(void*,unsigned long);
int printf(const char*,...);
'''
 fixture=r'''
static int scenario,maps; static uintptr_t region[2]; static uint32_t logsize; static unsigned char buffer[16384] __attribute__((aligned(8)));
int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
int SecureDTLookupEntry(DTEntry root,const char*path,DTEntry*out){(void)root;if((eq(path,"pram")&&scenario==0)||(eq(path,"/chosen")&&scenario==1))return 0;*out=(void*)1;return 1;}
int SecureDTGetProperty(DTEntry e,const char*n,const void**v,unsigned int*s){(void)e;if(eq(n,"reg")){*v=region;*s=scenario==2?8:16;}else{*v=&logsize;*s=scenario==6?8:4;}return 1;}
uintptr_t ml_io_map_wcomb(uintptr_t base,unsigned long size){maps++;if(base!=0x80000000UL||size!=16384)return 0;return scenario==9?0:(uintptr_t)buffer;}
void bzero(void*p,unsigned long n){unsigned char*q=p;while(n--)*q++=0;}
int main(void){
 for(scenario=0;scenario<=10;scenario++){
  gPanicBase=0;gPanicSize=0;panic_info=0;panic_text_len=0;panic_console_available=0;maps=0;
  region[0]=0x80000000UL;region[1]=16384;logsize=16384;((struct embedded_panic_header*)buffer)->eph_magic=0x53484d43;
  if(scenario==3)region[0]=0;
  if(scenario==4)region[0]=UINTPTR_MAX-100;
  if(scenario==5)region[1]=sizeof(struct embedded_panic_header)-1;
  if(scenario==7)logsize=sizeof(struct embedded_panic_header)-1;
  if(scenario==8)logsize=16385;
  check_for_panic_log();
  if(scenario<9&&(maps||gPanicBase||panic_info))return 10+scenario;
  if(scenario==9&&(maps!=1||panic_info))return 29;
  if(scenario==10&&(maps!=1||!panic_console_available||gPanicSize!=16384||panic_text_len!=16384-sizeof(struct embedded_panic_header)))return 30;
 }
 printf("11 source guard cases passed; header=%lu\n",(unsigned long)sizeof(struct embedded_panic_header));return 0;
}
'''
 unit=a.work/'unit.c';unit.write_text(prefix+body+'\nvoid exported_check(void){check_for_panic_log();}\n',encoding='utf-8',newline='\n');host=a.work/'host.c';host.write_text(prefix+body+fixture,encoding='utf-8',newline='\n')
 commands=[]
 for argv in [['clang','--target=aarch64-none-elf','-ffreestanding','-Wall','-Wextra','-Werror','-Wno-multichar','-c',linux(unit),'-o',linux(a.work/'unit.o')],['clang','-O1','-fsanitize=undefined','-fno-sanitize-recover=all','-Wno-multichar',linux(host),'-o',linux(a.work/'host')],[linux(a.work/'host')]]:
  cmd=['wsl','-d','Ubuntu-22.04','--',*argv];r=subprocess.run(cmd,capture_output=True,text=True);commands.append(dict(argv=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));r.check_returncode()
 out=dict(scope=__doc__,source_path=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest(),function_sha256=hashlib.sha256(body.encode()).hexdigest(),commands=commands,cases=11,full_kernel_build_verified=False)
 a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(aarch64_compile=True,source_guard_cases=11,passed=True)))
if __name__=='__main__':main()
