"""Execute only 36 original ABL gate bytes in an isolated AArch64 user fixture.

The surrounding wrapper replaces the two exit destinations with return values.
This is neither full ABL execution nor a claim about the phone's runtime context.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def linux(path):
    text = path.resolve().as_posix()
    if not text.startswith('D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/'):
        raise ValueError('Fixture paths must stay under device out/')
    return '/mnt/d/' + text[3:]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    if not work.is_relative_to(ROOT / 'out') or work.exists():
        raise ValueError('Require a new fixture directory under out/')
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('Require a fresh report under reports/')
    source = ROOT / 'reports/abl-handoff/usb-v3-gates.json'
    raw = source.read_bytes()
    report = json.loads(raw)
    pe, = report['pe_images']
    if (report['abl_sha256'] != '38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188'
        or pe['sha256'] != 'b489faff3f66a415af69b73fe23a59fb9469da0b70aeb4a1792201e22b5bb116'):
        raise ValueError('Unexpected installed ABL provenance')
    selected = next(r for r in pe['requested_code_ranges'] if r['start'] == '0x7660' and r['end'] == '0x7684')
    instructions = selected['instructions']
    if [int(i['address'], 16) for i in instructions] != list(range(0x7660, 0x7684, 4)):
        raise ValueError('Gate instruction range changed')
    code = b''.join(bytes.fromhex(i['bytes']) for i in instructions)
    # Exact bytes also keep accidental evidence edits from silently changing the fixture.
    expected = bytes.fromhex('e80341f90871513948' '2e0034' '01000014' 'e80341f9' '085944b9' '08110071' 'a32d0054' '01000014')
    if code != expected:
        raise ValueError('Original selection gate bytes changed')
    asm = ('.text\n.balign 4\n.global gate\n.type gate,%function\ngate:\n'
           'sub sp,sp,#0x210\nstr x0,[sp,#0x200]\ngate_actual:\n.byte '
           + ','.join(str(b) for b in code)
           + '\nmov w0,#1\nadd sp,sp,#0x210\nret\n'
           '.space 0x5d0-(.-gate_actual)\n'
           'mov w0,#0\nadd sp,sp,#0x210\nret\n'
           '.section .note.GNU-stack,"",%progbits\n')
    harness = '''#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern unsigned gate(void *);
int main(void) {
  uint32_t versions[]={0,1,2,3,4,5,0x80000000u,0xffffffffu};
  unsigned count=0;
  for (unsigned flag=0;flag<2;flag++) for(unsigned i=0;i<8;i++) {
    unsigned char context[0x460]={0};
    memcpy(context+0x458,&versions[i],4); context[0x45c]=flag;
    unsigned result=gate(context), expected=flag && versions[i]>=4;
    if(result!=expected) {printf("FAIL version=%u flag=%u result=%u\\n",versions[i],flag,result);return 1;}
    count++;
  }
  printf("PASS %u isolated selection-gate cases\\n",count); return 0;
}
'''
    work.mkdir(parents=True)
    (work / 'gate.S').write_text(asm, encoding='utf-8')
    (work / 'main.c').write_text(harness, encoding='utf-8')
    commands = []
    def run(argv):
        result = subprocess.run(argv, capture_output=True, timeout=60)
        commands.append(dict(argv=argv, exit_code=result.returncode,
                             stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
        result.check_returncode()
        return result.stdout.decode()
    run(['wsl', '-d', 'Ubuntu-22.04', '--', 'aarch64-linux-gnu-gcc', '-static', '-Wall', '-Wextra', '-Werror',
         linux(work / 'gate.S'), linux(work / 'main.c'), '-o', linux(work / 'gate-test')])
    runtime = ROOT / 'out/upstream-host-tests/qemu-runtime/usr/bin/qemu-aarch64'
    stdout = run(['wsl', '-d', 'Ubuntu-22.04', '--', linux(runtime), linux(work / 'gate-test')])
    if stdout != 'PASS 16 isolated selection-gate cases\n':
        raise ValueError('Unexpected fixture output')
    result = dict(scope='QEMU user-space isolated real ABL gate bytes only; not phone or full ABL execution',
        source_report=source.relative_to(ROOT).as_posix(), source_report_sha256=hashlib.sha256(raw).hexdigest(),
        code_start='0x7660', code_end='0x7684', code_sha256=hashlib.sha256(code).hexdigest(),
        original_gate_bytes_preserved=True, exit_destinations_replaced_by_fixture_returns=True,
        cases=16, result='QEMU execution passed', commands=commands,
        conclusion='For both modeled values of context+0x45c, version3 bypasses this init_boot lookup gate; version4 can enter it when flag is set',
        limitations=['Actual context field values and full ramdisk assembly path are not executed',
                     'Header compatibility and successful firmware/initrd entry need a separately captured phone trial'],
        device_accessed=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(stdout.strip())


if __name__ == '__main__':
    main()
