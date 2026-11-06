"""Run pinned DarwinBoot allocation selection with host services, never a phone.

Photographed merged runs are input subsets, not a complete EFI memory map.
Upstream C is read from a fixed Git object and passed to clang on stdin only.
"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
PIN = '75bc13dd34dc4e403826793739e316a264ce00dd'
SOURCE = 'drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c'
OUT = ROOT / 'reports/loader-window-host/results.json'
WORK = ROOT / 'out/loader-window-host-v2'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists() or WORK.exists():
        raise ValueError('Fresh evidence/output required')
    raw = subprocess.check_output(['git', '-c', f'safe.directory={BASE}', '-C', str(BASE),
                                   'show', PIN + ':' + SOURCE])
    source = raw.decode()
    run_end = source[source.index('STATIC\nUINT64\nRunEnd ('):source.index('// Large diagnostic text')]
    allocate = source[source.index('STATIC\nEFI_STATUS\nAllocateWindow ('):
                      source.index('STATIC\nEFI_STATUS\nEFIAPI\nBoot (')]
    # Load exactly the reviewed post-patch recipe, so function identities are checked.
    from virtual_patch import Tree
    tree = Tree(BASE)
    tree.apply((ROOT / 'patches/loader-candidates/0005-darwin22-boot-args.patch').read_text())
    post = tree.read(SOURCE)
    profile = json.loads((ROOT / 'config/loader-candidate.json').read_text())
    expected = next(i['lf_sha256'] for i in profile['post_patch_inputs'] if i['path'] == SOURCE)
    if digest(post.encode()) != expected or run_end not in post or allocate not in post:
        raise ValueError('Allocation functions differ from reviewed loader recipe')
    kernel_path = ROOT / 'out/native-prelink-current/analysis/kernel-prelinked-analysis.macho'
    kernel = kernel_path.read_bytes()
    kernel_sha = digest(kernel)
    if kernel_sha != '5a128fb282009fa7f24fc35574d2199baa010edb650c50c5f903b8351e61f5e6':
        raise ValueError('Analysis candidate changed')
    offset, bases = 32, []
    for _ in range(struct.unpack_from('<I', kernel, 16)[0]):
        command, length = struct.unpack_from('<II', kernel, offset)
        if command == 0x19:
            address, size = struct.unpack_from('<QQ', kernel, offset + 24)
            if size:
                bases.append(address)
        offset += length
    kernel_base = min(bases)
    candidate = 0x8c0000000 + (kernel_base & 0x1fffff)
    harness = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#define STATIC static
#define VOID void
typedef uint64_t UINT64, EFI_STATUS, EFI_PHYSICAL_ADDRESS;
typedef uint8_t UINT8;
typedef size_t UINTN; typedef int BOOLEAN; typedef wchar_t CHAR16;
#define TRUE 1
#define FALSE 0
#define MAX_UINT64 UINT64_MAX
#define EFI_PAGE_SIZE 4096ULL
#define EFI_PAGES_TO_SIZE(x) ((x)*EFI_PAGE_SIZE)
#define EFI_SIZE_TO_PAGES(x) (((x)+4095)/4096)
#define BLOCK_SIZE 0x200000ULL
#define ALIGN_VALUE(x,a) (((x)+(a)-1)&~((a)-1))
#define EFI_SUCCESS 0
#define EFI_OUT_OF_RESOURCES 9
#define EFI_ERROR(x) ((x)!=0)
#define EfiConventionalMemory 7
#define AllocateAddress 2
#define EfiLoaderCode 1
typedef struct { uint32_t Type,Pad; UINT64 PhysicalStart,VirtualStart,NumberOfPages,Attribute; } EFI_MEMORY_DESCRIPTOR;
typedef struct { UINT64 Base; } KERNEL;
static unsigned char rows[8*64];
static UINTN row_count, row_stride, calls, failures, freed, attempts;
static UINT64 requested, requested_bytes;
static EFI_STATUS map_error;
static void add(uint32_t type,UINT64 base,UINT64 bytes,UINT64 attr){
  EFI_MEMORY_DESCRIPTOR d={type,0,base,0,bytes/4096,attr};
  memcpy(rows+row_count++*row_stride,&d,sizeof(d));
}
static void reset(UINTN stride){memset(rows,0,sizeof(rows));row_count=0;row_stride=stride;
  calls=failures=freed=attempts=0;map_error=0;requested=requested_bytes=0;}
static EFI_STATUS GetMap(EFI_MEMORY_DESCRIPTOR **m,UINTN *c,UINTN *s,UINTN *k,UINTN *st){
  *s=row_count*row_stride;*c=*s;*st=row_stride;*k=1;
  *m=malloc(*s ? *s:1);assert(*m);memcpy(*m,rows,*s);return map_error;
}
static void FreePool(void *p){freed++;free(p);}
static void UnicodeSPrint(CHAR16 *p,UINTN n,const CHAR16 *fmt,...){(void)p;(void)n;(void)fmt;}
static void DiagDraw(const CHAR16 *p,UINTN row){(void)p;(void)row;}
static EFI_STATUS allocate_pages(int type,int memtype,UINTN pages,EFI_PHYSICAL_ADDRESS *a){
  assert(type==AllocateAddress && memtype==EfiLoaderCode);calls++;attempts++;
  requested=*a;requested_bytes=pages*4096ULL;
  if(failures){failures--;return EFI_OUT_OF_RESOURCES;}return EFI_SUCCESS;
}
static struct {EFI_STATUS (*AllocatePages)(int,int,UINTN,EFI_PHYSICAL_ADDRESS*);} services={allocate_pages};
#define gBS (&services)
'''
    harness += run_end + allocate
    harness += r'''
static void check(KERNEL k,UINT64 bytes,int ok,UINT64 expected,UINTN ncalls){
  EFI_PHYSICAL_ADDRESS a=0x1234;EFI_STATUS s=AllocateWindow(&k,bytes,&a);
  assert((s==EFI_SUCCESS)==ok);assert(a==expected);assert(calls==ncalls);assert(freed==1);
  if(ok){assert(requested==a);assert(requested_bytes==bytes);}
}
int main(void){
  KERNEL k={0xfffffff007004000ULL};unsigned n=0;
  /* Photograph's largest merged run only; services are host records, not UEFI. */
  for(UINT64 size=0x20000000ULL;size<=0x200000000ULL;size*=2){
    reset(48);add(7,0x8c0000000ULL,0x240000000ULL,0xf);
    check(k,size,1,0x8c0004000ULL,1);n++;
  }
  /* 9GiB exact run cannot fit 9GiB at this kernel's required congruence. */
  reset(48);add(7,0x8c0000000ULL,0x240000000ULL,0xf);
  check(k,0x240000000ULL,0,0,0);n++;
  /* Low region alone is insufficient for 512MiB, high region is selected. */
  reset(48);add(7,0x8c000000ULL,0x3000000ULL,0xf);add(7,0x8c0000000ULL,0x240000000ULL,0xf);
  check(k,0x20000000ULL,1,0x8c0004000ULL,1);n++;
  /* Split contiguous descriptors, including unsorted and extended stride. */
  reset(64);add(7,0x8d0000000ULL,0x10000000ULL,0xf);add(7,0x8c0000000ULL,0x10000000ULL,0xf);
  check(k,0x18000000ULL,1,0x8c0004000ULL,1);n++;
  /* Real allocation rejection must propagate, never snapshot-as-success. */
  reset(48);add(7,0x8c0000000ULL,0x240000000ULL,0xf);failures=1;
  check(k,0x20000000ULL,0,0,1);n++;
  /* Reservation and gaps may not be bridged. */
  reset(48);add(7,0x8c0000000ULL,0x10000000ULL,0xf);add(0,0x8d0000000ULL,0x10000000ULL,0xf);
  check(k,0x18000000ULL,0,0,0);n++;
  reset(48);add(7,0x8c0000000ULL,0x10000000ULL,0xf);add(7,0x8e0000000ULL,0x10000000ULL,0xf);
  check(k,0x18000000ULL,0,0,0);n++;
  reset(48);add(7,0x8c0000000ULL,0x240000000ULL,0xf);map_error=9;
  check(k,0x20000000ULL,0,0,0);n++;
  printf("{\"cases_passed\":%u,\"high_address_selection\":\"0x8c0004000\",\"actual_uefi_allocation\":false}\n",n);
}
'''
    harness = harness.replace('0xfffffff007004000ULL', hex(kernel_base) + 'ULL')
    harness = harness.replace('0x8c0004000', hex(candidate))
    WORK.mkdir(parents=True)
    binary = '/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/loader-window-host-v2/probe'
    commands = []

    def run(args, stdin=None):
        cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', *args]
        p = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60)
        commands.append(dict(argv=cmd, stdin_sha256=digest(stdin) if stdin else None,
                             exit_code=p.returncode, stdout=p.stdout.decode(errors='replace'),
                             stderr=p.stderr.decode(errors='replace')))
        if p.returncode:
            (WORK / 'failed.json').write_text(json.dumps(commands[-1], indent=2))
        p.check_returncode()
        return p.stdout

    run(['clang', '-x', 'c', '-std=c11', '-O1', '-g', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-Wall', '-Wextra', '-Werror',
         '-', '-o', binary], harness.encode())
    result = json.loads(run([binary]))
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Exact pinned allocation-selection functions with host service adapters; not device/EFI allocation',
                  source=dict(repository='UniXNU/UniXNU', commit=PIN, path=SOURCE, sha256=digest(raw),
                              license='BSD-2-Clause-Patent', post_patch_sha256=expected,
                              function_sha256=dict(RunEnd=digest(run_end.encode()), AllocateWindow=digest(allocate.encode()))),
                  snapshot_source='reports/hob-cache-handoff-trial/2026-10-24/ready-to-boot-map.png',
                  fixture='Only photographed largest merged conventional run plus explicitly synthetic perturbations, not all128 original descriptors',
                  analysis_kernel=dict(sha256=kernel_sha, virtual_base=hex(kernel_base),
                                       allocation_congruence=hex(kernel_base & 0x1fffff), loadable=False),
                  result=result, commands=commands,
                  findings=['No 32-bit physical address truncation in allocation selection',
                            'Kernel 2MiB congruence adds an offset; a run as large as a requested window may still be too small',
                            'AllocatePages failure propagates, GetMemoryMap visibility does not guarantee allocation',
                            'RunEnd merges adjacent conventional descriptors without comparing Attribute; audit separately before policy adoption'],
                  limitations=['No full Boot(), copy, ExitBootServices, page-table, cache or XNU execution',
                               'Host allocation adapter records requests; does not reserve real physical memory',
                               'No board/bringup values, real target ADT or verified flags changed'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
