"""Prepare/check a device-only Darwin22 patch without editing upstream trees.

Compiles the real patched header with the real EDK II headers and exercises
the command-line conversion/copy statements extracted from DarwinBoot.c on
the WSL host. This is not a full firmware build or a target execution test.
"""
import argparse
import base64
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from virtual_patch import Tree

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('D:/Code/PortingiOS/common/sources/UniXNU')
EDK = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore/MdePkg/Include')
COMMIT = 'd099354d0eab34df5088ca1ba89c9c88bc3260bb'
PREFIX = 'drivers/DarwinBoot/DarwinBootPkg/Driver/'
PATCH = ROOT / 'patches/loader-candidates/0005-darwin22-boot-args.patch'
OUT = ROOT / 'out/darwin22-loader'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def upstream(name):
    data = json.loads(subprocess.check_output([
        'C:/Program Files/GitHub CLI/gh.exe', 'api',
        f'repos/UniXNU/DarwinBoot/contents/DarwinBootPkg/Driver/{name}?ref={COMMIT}'],
        env={**os.environ, 'GODEBUG': 'http2client=0'}))
    return base64.b64decode(data['content'])


def replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Expected one source context: {before!r}')
    return text.replace(before, after)


def adapt(name, text):
    if name == 'BootArgs.h':
        text = replace(text, '// Darwin 23 pexpert/pexpert/arm64/boot.h ABI; all fields are little-endian.',
            '// Darwin 22 (XNU 8796) ARM64 ABI; device-only iOS 16 build.\n'
            '#define DARWIN_BOOT_LINE_LENGTH  608')
        text = replace(text, 'CommandLine[1024]', 'CommandLine[DARWIN_BOOT_LINE_LENGTH]')
        text = replace(text, 'STATIC_ASSERT (OFFSET_OF (DARWIN_BOOT_ARGS, MemorySizeActual) == 0x478, "memory ABI");',
            'STATIC_ASSERT (OFFSET_OF (DARWIN_BOOT_ARGS, BootFlags) == 0x2d0, "flags ABI");\n'
            'STATIC_ASSERT (OFFSET_OF (DARWIN_BOOT_ARGS, MemorySizeActual) == 0x2d8, "memory ABI");')
        return replace(text, 'sizeof (DARWIN_BOOT_ARGS) == 0x480', 'sizeof (DARWIN_BOOT_ARGS) == 0x2e0')
    text = replace(text, 'CommandLine[1024]', 'CommandLine[DARWIN_BOOT_LINE_LENGTH]')
    return replace(text, 'CopyMem (Args->CommandLine, CommandLine, sizeof (CommandLine));',
        'CopyMem (Args->CommandLine, CommandLine, sizeof (Args->CommandLine));')


def apply_in_memory(original, patch):
    # Exact unified-diff application, without fuzz or filesystem source copies.
    lines, result, position = original.splitlines(keepends=True), [], 0
    records = patch.splitlines(keepends=True)
    i = 2
    while i < len(records):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', records[i])
        assert match, records[i]
        start, old_count = int(match[1])-1, int(match[2] or 1)
        assert start >= position
        result.extend(lines[position:start])
        position, consumed, produced = start, 0, 0
        i += 1
        while i < len(records) and not records[i].startswith('@@ '):
            sign, line = records[i][0], records[i][1:]
            assert sign in ' +-'
            if sign in ' -':
                assert lines[position] == line, 'Patch source context mismatch'
                position += 1
                consumed += 1
            if sign in ' +':
                result.append(line)
                produced += 1
            i += 1
        assert consumed == old_count and produced == int(match[4] or 1)
    result.extend(lines[position:])
    return ''.join(result)


def linux(path):
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def execute(argv, source=None):
    result = subprocess.run(argv, input=source, text=True, encoding='utf-8',
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return dict(argv=argv, exit_code=result.returncode, output=result.stdout)


def validation_source(header, implementation):
    start = implementation.index('  ZeroMem (CommandLine, sizeof (CommandLine));')
    end = implementation.index('  Root = NULL;', start)
    conversion = implementation[start:end]
    copy = re.findall(r'  CopyMem \(Args->CommandLine, CommandLine, .*?;', implementation)
    assert len(copy) == 1
    # Compile and run the actual production conversion and copy statements,
    # rather than a Python reimplementation of their intended behavior.
    return '#include <Uefi.h>\n#include <string.h>\n#include <stdio.h>\n' + header + '''
#define ZeroMem(p,n) memset((p),0,(n))
#define CopyMem(d,s,n) memcpy((d),(s),(n))
#define Print(...) ((void)0)
static EFI_STATUS Convert (CONST CHAR16 *Input, DARWIN_BOOT_ARGS *Args) {
  struct { CONST CHAR16 *BootArgs; } Storage = {Input}, *Request = &Storage;
  UINTN Index;
  CHAR8 CommandLine[DARWIN_BOOT_LINE_LENGTH];
''' + conversion + copy[0] + '''
  return EFI_SUCCESS;
}
int main(void) {
  const UINTN Lengths[] = {0, 1, 606, 607, 608, 609, 1023};
  UINTN Case, I;
  for (Case=0; Case<sizeof(Lengths)/sizeof(Lengths[0])+3; Case++) {
    CHAR16 Input[1025];
    struct { UINT64 Before; DARWIN_BOOT_ARGS Args; UINT64 After; } Guard;
    UINTN Length = Case<7 ? Lengths[Case] : 607;
    EFI_STATUS Expected = Length<608 ? EFI_SUCCESS : EFI_BAD_BUFFER_SIZE;
    CONST CHAR16 *Value = Input;
    memset(&Guard, 0xa5, sizeof(Guard));
    for (I=0; I<Length; I++) Input[I]='a';
    Input[Length]=0;
    if (Case==7) { Input[0]=0x80; Expected=EFI_BAD_BUFFER_SIZE; }
    if (Case==8) { Input[606]=0x100; Expected=EFI_BAD_BUFFER_SIZE; }
    if (Case==9) { Value=NULL; Length=0; Expected=EFI_SUCCESS; }
    if (Convert(Value, &Guard.Args)!=Expected) return 10+Case;
    if (Guard.Before!=0xa5a5a5a5a5a5a5a5ULL || Guard.After!=Guard.Before ||
        Guard.Args.BootFlags!=Guard.Before || Guard.Args.MemorySizeActual!=Guard.Before)
      return 30+Case;
    if (Expected==EFI_SUCCESS) {
      for (I=0; I<608; I++)
        if (Guard.Args.CommandLine[I]!=(I<Length ? 'a' : 0)) return 50+Case;
    } else {
      for (I=0; I<sizeof(Guard.Args.CommandLine); I++)
        if ((UINT8)Guard.Args.CommandLine[I]!=0xa5) return 70+Case;
    }
  }
  puts("10 production command-line conversion/copy cases passed; guards intact");
  return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='write reviewed candidate patch')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    adapted, parts, evidence = {}, [], []
    for name in ('BootArgs.h', 'DarwinBoot.c'):
        remote = upstream(name)
        original = remote.decode().replace('\r\n', '\n')
        old = (BASE / PREFIX / name).read_bytes().decode().replace('\r\n', '\n')
        text = adapt(name, original)
        patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True),
            text.splitlines(keepends=True), fromfile='a/'+PREFIX+name, tofile='b/'+PREFIX+name))
        assert apply_in_memory(original, patch) == text
        parts.append(patch)
        evidence.append(dict(path=PREFIX+name, remote_sha256=sha(remote),
            old_lf_sha256=sha(old.encode()), candidate_lf_sha256=sha(text.encode()),
            old_baseline_identical=old == original, latest_exact_patch_applies=True))
        adapted[name] = text
    content = ''.join(parts).encode()
    if args.prepare:
        PATCH.parent.mkdir(parents=True, exist_ok=True)
        PATCH.write_bytes(content)
    else:
        assert PATCH.read_bytes() == content, 'Patch differs from reviewed transformations'
    # Existing source tree is never modified. --check is read-only.
    check = execute(['C:/Program Files/Git/cmd/git.exe', '-C', str(BASE), 'apply',
                     '--check', str(PATCH)])
    old_tree = Tree(BASE)
    old_tree.apply(content.decode())
    old_post = {path: sha(text.encode()) for path, text in old_tree.files.items()}
    checks = [check]
    dwarf = json.loads((ROOT/'reports/official-site-audit/ci15-boot-args-dwarf.json').read_text())
    assert dwarf['kernel_dsym_uuid_matches'] and len(dwarf['definitions']) == 3
    fields = dict(Revision='Revision', Version='Version', virtBase='VirtualBase',
        physBase='PhysicalBase', memSize='MemorySize', topOfKernelData='TopOfKernelData',
        Video='Video', machineType='MachineType', deviceTreeP='DeviceTree',
        deviceTreeLength='DeviceTreeLength', CommandLine='CommandLine',
        bootFlags='BootFlags', memSizeActual='MemorySizeActual')
    asserts = []
    for record in dwarf['definitions']:
        asserts.append(f'STATIC_ASSERT (sizeof (DARWIN_BOOT_ARGS) == {record["byte_size"]}, "DWARF size");')
        for member, value in record['members'].items():
            asserts.append(f'STATIC_ASSERT (OFFSET_OF (DARWIN_BOOT_ARGS, {fields[member]}) == {value["offset"]}, "DWARF {member}");')
        asserts.append('STATIC_ASSERT (sizeof (((DARWIN_BOOT_ARGS *)0)->CommandLine) == 608, "DWARF array");')
    common = ['wsl.exe', '-e', 'clang', '-x', 'c', '-std=gnu11', '-fshort-wchar',
              '-Wall', '-Werror', '-I'+linux(EDK), '-I'+linux(EDK/'AArch64')]
    checks.append(execute(common+['--target=aarch64-none-elf', '-ffreestanding', '-fsyntax-only', '-'],
        adapted['BootArgs.h']+'\n'+'\n'.join(asserts)+'\n'))
    for label, header, implementation in (
        ('latest', adapted['BootArgs.h'], adapted['DarwinBoot.c']),
        ('baseline', old_tree.read(PREFIX+'BootArgs.h'), old_tree.read(PREFIX+'DarwinBoot.c'))):
        executable = OUT / ('commandline-host-test-'+label)
        # Use a fixed host executable layout for the old WSL ASan runtime; no
        # sanitizer checks are disabled. The earlier PIE exit 139 is retained
        # as separate evidence and its exact cause is still unverified.
        checks.append(execute(common+['-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                                     '-g', '-o', linux(executable), '-'],
            validation_source(header, implementation)))
        if checks[-1]['exit_code'] == 0:
            for _ in range(4):
                checks.append(execute(['wsl.exe', '-e', linux(executable)]))
    report = dict(upstream_repository='UniXNU/DarwinBoot', upstream_commit=COMMIT,
        patch=PATCH.relative_to(ROOT).as_posix(), patch_sha256=sha(content), sources=evidence,
        old_baseline_post_patch_sha256=old_post,
        compiled_type_evidence='reports/official-site-audit/ci15-boot-args-dwarf.json',
        checks=checks, passed=all(item['exit_code'] == 0 for item in checks),
        toolchain=execute(['wsl.exe', '-e', 'clang', '--version']),
        edk_header_sha256={str(p): sha(p.read_bytes()) for p in (EDK/'Base.h', EDK/'AArch64/ProcessorBind.h')},
        full_darwinboot_module_compiled=False, firmware_generated=False, device_accessed=False)
    target = ROOT / 'reports/darwin22-loader/checks.json'
    target.parent.mkdir(exist_ok=True, parents=True)
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
