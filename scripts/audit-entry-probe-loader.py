"""Compile and execute pinned DarwinBoot ParseKernel against shipped Mach-O bytes."""
import argparse, hashlib, importlib.util, json, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    build=json.loads(a.build.read_text());candidate=(ROOT/build['candidate']['path']).read_bytes()
    source_path=Path('D:/Code/UniXNU-integration/drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c');s=source_path.read_text();begin=s.index('STATIC\nEFI_STATUS\nParseKernel (');end=s.index('STATIC\nBOOLEAN\nAdtNode (',begin);body=s[begin:end]
    definitions=s[s.index('#define WINDOW_SIZE'):s.index('STATIC EFI_HANDLE')]
    prefix='''#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t UINT64; typedef uint32_t UINT32; typedef uint8_t UINT8; typedef size_t UINTN; typedef int BOOLEAN; typedef int EFI_STATUS; typedef void VOID;
#define STATIC static
#define CONST const
#define TRUE 1
#define FALSE 0
#define EFI_SUCCESS 0
#define EFI_UNSUPPORTED 1
#define EFI_LOAD_ERROR 2
#define MAX_UINT64 UINT64_MAX
#define SIZE_256MB 0x10000000ULL
#define SIZE_2MB 0x200000ULL
#define EFI_PAGE_MASK 4095
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define ZeroMem(p,n) memset(p,0,n)
static UINT32 U32(const void *p){UINT32 v;memcpy(&v,p,4);return v;}
static UINT64 U64(const void *p){UINT64 v;memcpy(&v,p,8);return v;}
'''
    suffix='''int main(int argc,char **argv){if(argc!=2)return 90;FILE*f=fopen(argv[1],"rb");if(!f)return 91;fseek(f,0,SEEK_END);size_t n=ftell(f);rewind(f);unsigned char*p=malloc(n);if(fread(p,1,n,f)!=n)return 92;fclose(f);KERNEL k={0};int st=ParseKernel(p,n,&k);printf("%d %zu %llx %llx %llx\\n",st,k.Count,(unsigned long long)k.Base,(unsigned long long)k.End,(unsigned long long)k.Entry);free(p);return st;}
'''
    source=a.work/'parse.c';source.write_text(prefix+definitions+body+suffix,encoding='utf-8',newline='\n');exe=a.work/'parse';cmd=['wsl','-d','Ubuntu-22.04','--','clang','-O1','-g','-fsanitize=address,undefined',b.linux(source),'-o',b.linux(exe)];r=subprocess.run(cmd,capture_output=True,text=True);r.check_returncode()
    m=b.macho(candidate);probe=m['segments'][-1];variants=[]
    variants.append(('original',b.INPUT.read_bytes(),True));variants.append(('candidate',candidate,True))
    changed=bytearray(candidate);struct.pack_into('<Q',changed,probe['command_offset']+24,m['segments'][0]['va']);variants.append(('overlapping-probe',changed,False))
    changed=bytearray(candidate);struct.pack_into('<I',changed,20,len(candidate));variants.append(('command-overrun',changed,False))
    changed=bytearray(candidate);struct.pack_into('<Q',changed,probe['command_offset']+48,0x200000);variants.append(('probe-file-overrun',changed,False))
    results=[]
    for name,raw,ok in variants:
        image=a.work/(name+'.macho');image.write_bytes(raw);run=subprocess.run(['wsl','-d','Ubuntu-22.04','--',b.linux(exe),b.linux(image)],capture_output=True,text=True)
        passed=(run.returncode==0)==ok and not run.stderr
        results.append(dict(name=name,expected_accept=ok,passed=passed,exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr))
        if not passed:raise ValueError('Loader source fixture failed: '+name)
    result=dict(scope='Host ASan/UBSan execution of pinned ParseKernel source body; not full EFI module or hardware execution',candidate_sha256=b.sha(candidate),source_path=str(source_path),source_body_sha256=b.sha(body.encode()),compile_command=cmd,cases=results)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(cases=len(results),passed=True)))
if __name__=='__main__':main()
