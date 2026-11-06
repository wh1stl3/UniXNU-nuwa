"""Prepare a pinned shared-library constructor logging patch, in memory only.

Does not modify either upstream checkout or firmware sources. The CI profile
applies this diagnostic to four Mu libraries, including their non-SEC consumers.
"""
import copy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MU = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')
FW = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
PIN = 'cfb93724a06ff86ff5ba971413368a7809ee42a5'
FW_PIN = 'ddd794fc07e9bc64057222a9bffa4d79c8553af8'
sys.path.insert(0, str(ROOT / 'scripts'))
from virtual_patch import Tree


def blob(root, pin, path):
    return subprocess.check_output(['git', '--no-optional-locks', '-c', f'safe.directory={root}',
                                    '-C', str(root), 'show', pin + ':' + path])


def function(source, name):
    at = source.index('\n' + name + ' (')
    begin = source.index('{', at)
    depth = 0
    for end in range(begin, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return begin, end + 1
    raise ValueError('Unterminated constructor')


def main():
    output = ROOT / 'reports/constructor-trace/proposal.json'
    if output.exists():
        raise ValueError('Fresh output required')
    profile = json.loads((ROOT / 'config/firmware-sec-handoff-profile.json').read_text())
    if profile['recipe']['sources']['firmware']['commit'] != FW_PIN:
        raise ValueError('Unexpected firmware parent')
    paths = {
        'MdePkg/Library/BaseDebugLibSerialPort/DebugLib.c': 'BaseDebugLibSerialPortConstructor',
        'EmbeddedPkg/Library/PrePiExtractGuidedSectionLib/PrePiExtractGuidedSectionLib.c': 'ExtractGuidedSectionLibConstructor',
        'UefiCpuPkg/Library/ArmMmuLib/AArch64/ArmMmuLibCore.c': 'ArmMmuBaseLibConstructor',
        'MdeModulePkg/Library/LzmaCustomDecompressLib/GuidedSectionExtraction.c': 'LzmaDecompressLibConstructor',
    }
    labels = ['Debug', 'Extract', 'Mmu', 'Lzma']
    chunks, records, markers = [], [], []
    tree = Tree(MU)
    for (path, name), label in zip(paths.items(), labels):
        raw = blob(MU, PIN, path)
        before = raw.replace(b'\r\n', b'\n').decode()
        if tree.read(path) != before:
            raise ValueError('Read-only worktree differs from pinned library')
        begin, end = function(before, name)
        original_body = before[begin:end]
        entry = f'[NUWA-CTOR] {label} enter'
        leave = f'[NUWA-CTOR] {label} leave status=%r'
        markers.extend([entry, leave])
        if label == 'Debug':
            expected = '{\n  return SerialPortInitialize ();\n}'
            if original_body != expected:
                raise ValueError('Unexpected Debug constructor')
            body = ('{\n  RETURN_STATUS Status;\n\n'
                    f'  DEBUG ((EFI_D_ERROR, "{entry}\\n"));\n'
                    '  Status = SerialPortInitialize ();\n'
                    f'  DEBUG ((EFI_D_ERROR, "{leave}\\n", Status));\n'
                    '  return Status;\n}')
        elif label == 'Lzma':
            body = original_body.replace('{\n', '{\n  EFI_STATUS Status;\n\n'
                                         f'  DEBUG ((EFI_D_ERROR, "{entry}\\n"));\n', 1)
            body = body.replace('  return ExtractGuidedSectionRegisterHandlers (',
                                '  Status = ExtractGuidedSectionRegisterHandlers (')
            body = body[:-1] + f'  DEBUG ((EFI_D_ERROR, "{leave}\\n", Status));\n  return Status;\n' + '}'
        else:
            body = original_body
            if label == 'Extract':
                needle = '  //\n  // Allocate global pool space'
            else:
                needle = '  Hob = GetFirstGuidHob ('
            if body.count(needle) != 1:
                raise ValueError('Unexpected constructor body')
            body = body.replace(needle, f'  DEBUG ((EFI_D_ERROR, "{entry}\\n"));\n\n' + needle, 1)
            for status in ('RETURN_OUT_OF_RESOURCES', 'RETURN_SUCCESS'):
                body = body.replace('return ' + status + ';',
                                    f'DEBUG ((EFI_D_ERROR, "{leave}\\n", {status}));\n' +
                                    ('    ' if status == 'RETURN_OUT_OF_RESOURCES' else '  ') + 'return ' + status + ';')
        after = before[:begin] + body + before[end:]
        if label == 'Lzma':
            # Keep the new DebugLib dependency explicit for this source file.
            after = after.replace('#include "LzmaDecompressLibInternal.h"',
                                  '#include "LzmaDecompressLibInternal.h"\n#include <Library/DebugLib.h>')
        chunks.append(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                        fromfile='a/Mu_Basecore/' + path, tofile='b/Mu_Basecore/' + path)))
        records.append(dict(path='Mu_Basecore/' + path, constructor=name, label=label,
                            original_lf_sha256=hashlib.sha256(before.encode()).hexdigest(),
                            post_lf_sha256=hashlib.sha256(after.encode()).hexdigest(),
                            source_lines=dict(start=before[:begin].count('\n') + 1, end=before[:end].count('\n') + 1),
                            markers=[entry, leave]))
    patch = ROOT / 'patches/firmware-candidates/0011-mu-constructor-trace.patch'
    data = ''.join(chunks).encode()
    if patch.exists() and patch.read_bytes().replace(b'\r\n', b'\n') != data:
        raise ValueError('Existing patch differs')
    patch.write_bytes(data)
    # Apply exact normalized patch contexts in memory, stripping Mu_Basecore.
    text = data.decode().replace('a/Mu_Basecore/', 'a/').replace('b/Mu_Basecore/', 'b/')
    tree.apply(text)
    for item in records:
        actual = hashlib.sha256(tree.read(item['path'].split('/', 1)[1]).encode()).hexdigest()
        if actual != item['post_lf_sha256']:
            raise ValueError('Memory patch result differs')
    profile['scope'] = 'Offline constructor boundary logging; shared Mu instances affect SEC and other consumers'
    profile['source_evidence'] = 'reports/constructor-trace/proposal.json'
    profile['recipe']['approval'] = 'User requested mainline continuation after evening trial; offline build only, refresh capture/recovery gate before any new device trial'
    for item in records:
        profile['recipe']['inputs'].append(dict(root='firmware', path=item['path'], lf_sha256=item['original_lf_sha256']))
        profile['candidate']['post_patch_inputs'].append(dict(root='firmware', path=item['path'], lf_sha256=item['post_lf_sha256']))
    profile['candidate']['patches'].append(dict(path=patch.relative_to(ROOT).as_posix(), root='firmware', sha256=hashlib.sha256(data).hexdigest()))
    (ROOT / 'config/firmware-constructor-trace-profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    serial_path = 'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c'
    serial = blob(FW, FW_PIN, serial_path)
    begin, end = function(serial.replace(b'\r\n', b'\n').decode(), 'SerialPortInitialize')
    report = dict(scope=profile['scope'], mu_repository='microsoft/mu_basecore', mu_commit=PIN,
                  license='BSD-2-Clause-Patent per changed file headers', firmware_commit=FW_PIN,
                  files=records, markers=markers, patch=patch.relative_to(ROOT).as_posix(), patch_sha256=hashlib.sha256(data).hexdigest(),
                  exact_context_memory_apply_passed=True, source_calls_preserved=True,
                  serial_port=dict(path=serial_path, sha256=hashlib.sha256(serial).hexdigest(),
                                   body=serial.replace(b'\r\n', b'\n').decode()[begin:end]),
                  generated_autogen_untouched=True, memory_tables_untouched=True,
                  shared_library_scope_warning='Mu patches also affect linked DXE/other instances, so this is not a SEC-only binary delta',
                  compiled=False, device_accessed=False)
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(files=len(records), markers=len(markers), serial_body=report['serial_port']['body'])))


if __name__ == '__main__':
    main()
