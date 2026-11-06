"""Run the actual firmware recipe's pure parsers on the staged payload."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
import nuwa_launch_context as context
from virtual_patch import Tree
from systemos_payload_sidecar import linux
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/Code/UniXNU-integration')

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    recipe=json.loads((ROOT/'config/firmware-upstream-merged-profile.json').read_bytes())
    assert subprocess.check_output(['git','-C',str(BASE),'rev-parse','HEAD']).decode().strip()==recipe['recipe']['sources']['unixnu']['commit']
    path='drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c'
    raw=(BASE/path).read_bytes().replace(b'\r\n',b'\n')
    assert sha(raw)==next(v['lf_sha256'] for v in recipe['recipe']['inputs'] if v['path']==path)
    virtual=Tree(BASE);virtual.apply((ROOT/'patches/loader-candidates/0005-darwin22-boot-args.patch').read_text())
    source=virtual.read(path)
    assert sha(source.encode())==next(v['lf_sha256'] for v in recipe['candidate']['post_patch_inputs'] if v['path']==path)
    types=source[source.index('typedef struct {'):source.index('STATIC EFI_HANDLE  mImage;')]
    functions=source[source.index('STATIC\nEFI_STATUS\nParseKernel'):source.index('STATIC\nEFI_STATUS\nGetMap')]
    window=(BASE/'drivers/DarwinBoot/DarwinBootPkg/Driver/WindowSize.h').read_text()
    host='''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define STATIC static
#define CONST const
#define VOID void
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef uint64_t UINT64;typedef size_t UINTN;typedef char CHAR8;typedef int BOOLEAN;typedef uint64_t EFI_STATUS;
#define TRUE 1
#define FALSE 0
#define MAX_UINTN SIZE_MAX
#define MAX_UINT64 UINT64_MAX
#define MAX_SEGMENTS 64
#define EFI_PAGE_MASK 4095
#define WINDOW_SIZE 0x10000000ULL
#define SIZE_2MB 0x200000ULL
#define EFI_SUCCESS 0
#define EFI_UNSUPPORTED 3
#define EFI_LOAD_ERROR 1
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define ALIGN_VALUE(a,b) (((a)+(b)-1)&~((b)-1))
#define ScanMem8(p,n,v) memchr((p),(v),(n))
#define AsciiStrCmp strcmp
#define CompareMem memcmp
#define ZeroMem(p,n) memset((p),0,(n))
static UINT32 U32(const void *p){UINT32 v;memcpy(&v,p,4);return v;}
static UINT64 U64(const void *p){UINT64 v;memcpy(&v,p,8);return v;}
'''+window+types+functions+'''
static unsigned char *readall(const char *path,size_t *size){FILE*f=fopen(path,"rb");if(!f)exit(3);fseek(f,0,SEEK_END);long n=ftell(f);if(n<=0||n>268435456)exit(3);rewind(f);unsigned char*p=malloc(n);if(!p||fread(p,1,n,f)!=(size_t)n)exit(3);fclose(f);*size=n;return p;}
int main(int argc,char **argv){if(argc!=4)return 3;size_t kn,an,tn;unsigned char*k=readall(argv[1],&kn),*a=readall(argv[2],&an),*t=readall(argv[3],&tn);KERNEL kernel;
UINTN offset=0,ram=MAX_UINTN,trust=MAX_UINTN,addon=MAX_UINTN;UINT64 window=0;BOOLEAN packed=0;
int ok=ParseKernel(k,kn,&kernel)==0&&AdtNode(a,an,&offset,0,3,&ram,&trust,&addon,&window,&packed)&&offset==an&&ram==MAX_UINTN&&addon==MAX_UINTN&&trust!=MAX_UINTN&&U64(a+trust)==0&&U64(a+trust+8)==0&&ValidTrustCaches(t,tn);
if(ok){UINT64 args=ALIGN_VALUE(kernel.End-kernel.Base,16384),tree=args+4096,tc=ALIGN_VALUE(tree+an,4096),used=ALIGN_VALUE(tc+tn,16384);ok=used<=window-SIZE_2MB;printf("{\\"trust_offset\\":%zu,\\"window\\":%llu,\\"relative_trust_address\\":%llu,\\"used\\":%llu}\\n",trust,(unsigned long long)window,(unsigned long long)tc,(unsigned long long)used);}
free(k);free(a);free(t);return ok?0:2;}
'''
    binary=a.work/'loader-parser'
    subprocess.run(['wsl','--','/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-x','c','-','-o',linux(binary)],input=host.encode(),check=True,capture_output=True)
    kernel=a.work/'kernel.macho';adt=a.work/'launch/kernel.macho.adt';trust=a.work/'kernel.macho.trustcache'
    cases=[]
    def check(name,ap,tp,want):
        run=subprocess.run(['wsl','--',linux(binary),linux(kernel),linux(ap),linux(tp)],capture_output=True)
        assert run.returncode==(0 if want else 2),(name,run.stderr)
        cases.append(dict(name=name,accepted=want,layout=json.loads(run.stdout) if want else None))
    check('actual-packaged-inputs',adt,trust,True)
    bad=a.work/'trust-truncated.fixture';bad.write_bytes(trust.read_bytes()[:-1]);check('truncated-trust',adt,bad,False)
    for name,value in [('absent-slot',None),('nonzero-slot',struct.pack('<QQ',1,67764))]:
        tree=context.parse(adt.read_bytes());node=context.find(tree,'/chosen/memory-map');node['properties']=[v for v in node['properties'] if v[0]!='TrustCache']
        if value is not None:node['properties'].append(('TrustCache',0,value))
        bad=a.work/(name+'.adt');bad.write_bytes(context.encode(tree));check(name,bad,trust,False)
    report=dict(passed=True,loader_source_sha256=sha(source.encode()),harness_sha256=sha(host.encode()),cases=cases,
                inputs={p.name:sha(p.read_bytes()) for p in (kernel,adt,trust)},allocation_executed=False,efi_boot_executed=False,
                native_kernel_trust_acceptance=False,device_accessed=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'actual-loader payload cases')
if __name__=='__main__':main()
