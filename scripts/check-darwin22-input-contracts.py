"""Execute fixed DarwinBoot pure parsers on the host, never boot a payload.

Upstream function text is supplied to clang via stdin only. The ELF host probe
and synthetic parser fixtures stay in ignored out; no upstream source tree or
nuwa Apple DT is generated. This is not UEFI, QEMU or device execution.
"""
import datetime
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from virtual_patch import Tree

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOS/common/sources/UniXNU')
PIN = '75bc13dd34dc4e403826793739e316a264ce00dd'
GIT = 'C:/Program Files/Git/cmd/git.exe'
WORK = ROOT / 'out/darwin22-input-contracts/host-probe'
REPORT = ROOT / 'reports/darwin22-input-contracts/results.json'
C_PATH = 'drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def node(name, props=(), children=()):
    values = [('name', name.encode() + b'\0'), *props]
    data = struct.pack('<II', len(values), len(children))
    for key, value in values:
        data += struct.pack('<32sI', key.encode(), len(value)) + value + bytes(-len(value) % 4)
    return data + b''.join(children)


def tree(window=0x20000000, chosen_props=(), map_props=(), root_props=()):
    window_props = [] if window is None else [('darwinboot-memory-size', struct.pack('<Q', window))]
    return node('parser-fixture-only', root_props, [node('chosen', [*window_props, *chosen_props],
                [node('memory-map', map_props)])])


def main():
    global WORK, REPORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=WORK, help='Fresh scratch directory under repo out/')
    parser.add_argument('--output', type=Path, default=REPORT, help='Fresh report under repo reports/')
    parser.add_argument('--kernel', type=Path, help='Explicit analysis candidate under out/')
    parser.add_argument('--kernel-sha256', help='Required exact digest with --kernel')
    options = parser.parse_args()
    if bool(options.kernel) != bool(options.kernel_sha256):
        raise ValueError('Explicit kernel path and SHA256 must be supplied together')
    WORK = options.work.resolve()
    REPORT = options.output.resolve()
    if not WORK.is_relative_to((ROOT / 'out').resolve()):
        raise ValueError('Scratch must stay under repo out/')
    if not REPORT.is_relative_to((ROOT / 'reports').resolve()):
        raise ValueError('Evidence must stay under repo reports/')
    if WORK.exists() or REPORT.exists():
        raise ValueError('Fresh output required')
    sources = {}
    for path in (C_PATH, 'drivers/DarwinBoot/DarwinBootPkg/Driver/WindowSize.h'):
        pinned = subprocess.check_output([GIT, '-c', f'safe.directory={BASE}', '-C', str(BASE), 'show', PIN + ':' + path])
        current = (BASE / path).read_bytes().replace(b'\r\n', b'\n')
        if pinned.replace(b'\r\n', b'\n') != current:
            raise ValueError('Pinned source differs')
        sources[path] = sha(current)
    virtual = Tree(BASE)
    patch = ROOT / 'patches/loader-candidates/0005-darwin22-boot-args.patch'
    virtual.apply(patch.read_text())
    source = virtual.read(C_PATH)
    expected = next(x['lf_sha256'] for x in json.loads((ROOT / 'config/loader-candidate.json').read_text())['post_patch_inputs'] if x['path'] == C_PATH)
    if sha(source.encode()) != expected:
        raise ValueError('Post-patch loader differs from compiled recipe')
    types = source[source.index('typedef struct {'):source.index('STATIC EFI_HANDLE  mImage;')]
    kernel_parser = source[source.index('STATIC\nEFI_STATUS\nParseKernel'):source.index('STATIC\nBOOLEAN\nAdtNode')]
    adt_parser = source[source.index('STATIC\nBOOLEAN\nAdtNode'):source.index('STATIC\nBOOLEAN\nValidTrustCaches')]
    window_header = (BASE / 'drivers/DarwinBoot/DarwinBootPkg/Driver/WindowSize.h').read_text()
    # Only primitive host adapters are provided; no hardware driver stubs.
    host = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define STATIC static
#define CONST const
#define VOID void
typedef uint8_t UINT8; typedef uint32_t UINT32; typedef uint64_t UINT64;
typedef char CHAR8;
typedef size_t UINTN; typedef uint8_t BOOLEAN; typedef uint64_t EFI_STATUS;
#define TRUE 1
#define FALSE 0
#define MAX_UINTN SIZE_MAX
#define MAX_UINT64 UINT64_MAX
#define MAX_SEGMENTS 64
#define EFI_PAGE_MASK 4095
#define WINDOW_SIZE 0x10000000ULL
#define SIZE_2MB 0x200000ULL
#define EFI_SUCCESS 0
#define EFI_UNSUPPORTED (0x8000000000000000ULL | 3)
#define EFI_LOAD_ERROR (0x8000000000000000ULL | 1)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define ALIGN_VALUE(a,b) (((a)+(b)-1)&~((b)-1))
#define ScanMem8(p,n,v) memchr((p),(v),(n))
#define AsciiStrCmp strcmp
#define CompareMem memcmp
#define ZeroMem(p,n) memset((p),0,(n))
_Static_assert(sizeof(UINTN)==8, "LP64 host required");
static UINT32 U32(const VOID *p){UINT32 v;memcpy(&v,p,4);return v;}
static UINT64 U64(const VOID *p){UINT64 v;memcpy(&v,p,8);return v;}
'''
    wrapper = r'''
int main(int argc,char **argv){
  if(argc!=3)return 2;
  FILE *f=fopen(argv[2],"rb");if(!f)return 3;
  if(fseek(f,0,SEEK_END))return 4;long n=ftell(f);
  if(n<0||n>134217728)return 5;rewind(f);
  UINT8 *d=malloc((size_t)n+1);if(!d)return 6;
  if(fread(d,1,(size_t)n,f)!=(size_t)n)return 7;fclose(f);
  if(strcmp(argv[1],"--kernel")==0){
    KERNEL k;EFI_STATUS s=ParseKernel(d,n,&k);
    if(s==0)printf("{\"accepted\":true,\"segments\":%zu,\"span_bytes\":%llu}\n",k.Count,(unsigned long long)(k.End-k.Base));
    else printf("{\"accepted\":false,\"status\":\"0x%llx\"}\n",(unsigned long long)s);
  }else{
    UINTN o=0,r=MAX_UINTN,t=MAX_UINTN;UINT64 w=0;BOOLEAN p=FALSE;
    BOOLEAN ok=AdtNode(d,n,&o,0,3,&r,&t,&w,&p)&&o==(UINTN)n;
    printf("{\"accepted\":%s,\"consumed\":%zu,\"ramdisk_found\":%s,\"trustcache_found\":%s,\"window_bytes\":%llu,\"keep_packed\":%s}\n",
      ok?"true":"false",o,r!=MAX_UINTN?"true":"false",t!=MAX_UINTN?"true":"false",(unsigned long long)w,p?"true":"false");
  }free(d);return 0;
}
'''
    harness = '\n'.join((host, window_header, types, kernel_parser, adt_parser, wrapper))
    WORK.mkdir(parents=True)
    commands = []

    def wsl(path):
        value = path.resolve().as_posix()
        if not value.startswith('D:/Code/UniXNU-nuwa/out/'):
            raise ValueError('Only existing repo artifacts and output fixtures are allowed')
        return '/mnt/d/' + value[3:]

    def run(args, stdin=None):
        cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', *args]
        proc = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60)
        commands.append(dict(argv=cmd, stdin_sha256=sha(stdin) if stdin else None,
                             exit_code=proc.returncode, stdout=proc.stdout.decode(errors='replace'),
                             stderr=proc.stderr.decode(errors='replace')))
        if proc.returncode:
            (WORK / 'failed-command.json').write_text(json.dumps(commands[-1], indent=2) + '\n')
            print(proc.stderr.decode(errors='replace'))
        proc.check_returncode()
        return proc.stdout

    binary = WORK / 'darwin-parser-host'
    run(['clang', '--version'])
    run(['clang', '-x', 'c', '-std=c11', '-O1', '-g', '-fsanitize=undefined',
         '-fno-sanitize-recover=all', '-Wall', '-Wextra', '-Werror', '-', '-o', wsl(binary)], harness.encode())
    cases = [
        ('no_optional_sidecars', tree(), True),
        ('ramdisk_placeholder', tree(map_props=[('RAMDisk', bytes(16))]), True),
        ('packed_placeholder', tree(map_props=[('PackedRAMDisk', bytes(16))]), True),
        ('trustcache_placeholder', tree(map_props=[('TrustCache', bytes(16))]), True),
        ('minimum_window', tree(0x10000000), True), ('maximum_window', tree(0x200000000), True),
        ('below_window_minimum', tree(0x0fe00000), False), ('above_window_maximum', tree(0x200200000), False),
        ('unaligned_window', tree(0x20000001), False),
        ('duplicate_window', tree(chosen_props=[('darwinboot-memory-size', struct.pack('<Q', 0x20000000))]), False),
        ('wrong_window_width', tree(None, chosen_props=[('darwinboot-memory-size', bytes(4))]), False),
        ('window_outside_chosen', tree(None, root_props=[('darwinboot-memory-size', struct.pack('<Q', 0x20000000))]), False),
        ('short_ramdisk_slot', tree(map_props=[('RAMDisk', bytes(8))]), False),
        ('short_trustcache_slot', tree(map_props=[('TrustCache', bytes(8))]), False),
        ('both_ramdisk_names', tree(map_props=[('RAMDisk', bytes(16)), ('PackedRAMDisk', bytes(16))]), False),
        ('duplicate_node_name', node('parser-fixture-only', [('name', b'again\0')]), False),
        ('unterminated_key', struct.pack('<II', 1, 0) + b'x' * 32 + struct.pack('<I', 0), False),
        ('truncated_header', b'\0' * 7, False), ('trailing_bytes', tree() + b'\0\0\0\0', False),
        ('linux_fdt_magic_is_not_adt', bytes.fromhex('d00dfeed') + bytes(36), False),
    ]
    results = []
    for name, data, accepted in cases:
        path = WORK / (name + '.adt')
        path.write_bytes(data)
        result = json.loads(run([wsl(binary), '--adt', wsl(path)]))
        if result['accepted'] != accepted:
            raise ValueError('Parser result differs: ' + name)
        results.append(dict(name=name, input_bytes=len(data), sha256=sha(data), expected=accepted, result=result))
    kernel = (options.kernel.resolve() if options.kernel else next((ROOT / 'out/kernel-ci/39793231214').glob('**/mach.development.bcm2837.unstripped')))
    if not kernel.resolve().is_relative_to(ROOT / 'out'):
        raise ValueError('Analysis kernel must be repo-local under out/')
    kernel_sha = sha(kernel.read_bytes())
    expected_kernel_sha = options.kernel_sha256 or '77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8'
    if kernel_sha != expected_kernel_sha:
        raise ValueError('Current kernel differs')
    kernel_result = json.loads(run([wsl(binary), '--kernel', wsl(kernel)]))
    if not kernel_result['accepted']:
        raise ValueError('Actual source kernel rejected by fixed loader parser')
    report = dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='Native Linux host execution of fixed pure parser functions only; not EFI/QEMU/device execution',
                  source=dict(repository='UniXNU/UniXNU', commit=PIN, source_sha256=sources,
                              applied_patch_sha256=sha(patch.read_bytes()), post_patch_c_sha256=expected,
                              license='BSD-2-Clause-Patent', harness_stdin_sha256=sha(harness.encode()),
                              parser_function_sha256=dict(ParseKernel=sha(kernel_parser.encode()), AdtNode=sha(adt_parser.encode()))),
                  commands=commands, cases=results, cases_passed=len(results),
                  actual_kernel=dict(sha256=kernel_sha, bytes=kernel.stat().st_size, parser_result=kernel_result),
                  caller_contracts=['RAMDisk/PackedRAMDisk slot required only when Request->Ramdisk is supplied; no ramdisk with a slot is unsupported',
                                    'PackedRAMDisk also requires packed input; slot must start as sixteen zero bytes',
                                    'TrustCache slot and actual valid trustcache file must agree; stray slot is compromised data'],
                  limitations=['No full Boot() execution, allocation, EL1 transition or platform-driver configure()',
                               'Synthetic parser trees are not nuwa DTs and do not supply kernel-required platform nodes',
                               'No native prelink component ABI or current compiled boot_args DWARF qualification',
                               'No board/feed/bringup-plan or verified flag changed'], device_accessed=False)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(parser_cases=len(results), actual_kernel=report['actual_kernel'], device_accessed=False), indent=2))


if __name__ == '__main__':
    main()
