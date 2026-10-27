"""Offline ARM64/BootShim/SEC audit of existing files. No device or image writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware')
BACKUP = Path('D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z')
ART = ROOT / 'out/firmware-ci/39764322744/nuwa-firmware-39764322744'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def word(data, at):
    return struct.unpack_from('<I', data, at)[0]


def branch_target(instruction, pc):
    if instruction & 0x7c000000 != 0x14000000:
        raise ValueError('Expected immediate B/BL')
    immediate = instruction & 0x3ffffff
    if immediate & (1 << 25):
        immediate -= 1 << 26
    return pc + immediate * 4


def adr_target(instruction, pc):
    if instruction & 0x9f000000 != 0x10000000:
        raise ValueError('Expected ADR')
    immediate = ((instruction >> 5) & 0x7ffff) << 2 | ((instruction >> 29) & 3)
    if immediate & (1 << 20):
        immediate -= 1 << 21
    return pc + immediate


def main():
    output = ROOT / 'reports/arm64-sec-entry-audit'
    output.mkdir(exist_ok=True, parents=True)
    checks = []

    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)

    fd = (ART / 'build/FV/SILICIUM_UEFI.fd').read_bytes()
    shim = (ART / 'shim/shim.bin').read_bytes()
    candidate_path = ROOT / 'out/trial-boot/firmware-v4/boot-firmware-v4.img'
    candidate = candidate_path.read_bytes()
    original = (BACKUP / 'boot_a.img').read_bytes()
    check('candidate hash unchanged since trial', sha(candidate) == '12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9')
    check('original recovery hash unchanged', sha(original) == 'ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31')
    check('FD matches inspected CI', sha(fd) == 'a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83')
    check('shim matches inspected CI', sha(shim) == '9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9')
    check('candidate embeds exact shim and FD', candidate[4096:4096 + 112 + len(fd)] == shim + fd)

    def image_header(data):
        size = word(data, 8)
        image = data[4096:4096 + size]
        pe_at = word(image, 60)
        pe = image[pe_at:pe_at + 96]
        return dict(kernel_file_bytes=size, code_words=[hex(word(image, n)) for n in (0, 4)],
                    text_offset=hex(struct.unpack_from('<Q', image, 8)[0]),
                    image_size=struct.unpack_from('<Q', image, 16)[0],
                    flags=hex(struct.unpack_from('<Q', image, 24)[0]),
                    page_size_flag=(struct.unpack_from('<Q', image, 24)[0] >> 1) & 3,
                    arm64_magic=image[56:60].hex(), dos_mz=image[:2] == b'MZ',
                    pe_offset=hex(pe_at), pe_present=pe[:4] == b'PE\0\0')

    headers = dict(original=image_header(original), candidate=image_header(candidate))
    settings = json.loads((ART / 'build-settings.json').read_text())
    base = int(settings['fd_base'], 0)
    check('shim image_size covers itself plus FD', struct.unpack_from('<Q', shim, 16)[0] == len(shim) + len(fd))
    check('shim ADR computes exact appended FD start', adr_target(word(shim, 0), 0) == len(shim))
    check('shim branch skips Linux header data', branch_target(word(shim, 4), 4) == 64)
    check('copy loop is the expected fixed 16-byte sequence',
          [word(shim, n) for n in (84, 88, 92, 96)] == [0xa8c10c82, 0xa8810ca2, 0xf10040c6, 0x54ffffa1])
    movz5, movz6 = word(shim, 68), word(shim, 80)
    immediate5 = ((movz5 >> 5) & 65535) << (((movz5 >> 21) & 3) * 16)
    immediate6 = ((movz6 >> 5) & 65535) << (((movz6 >> 21) & 3) * 16)
    check('X5 receives fixed FD destination', movz5 & 0xff80001f == 0xd2800005 and immediate5 == base)
    check('X6 receives FD-only copy count', movz6 & 0xff80001f == 0xd2800006 and immediate6 == len(fd))
    check('final branch is BR X5', word(shim, 104) == 0xd61f00a0)
    check('copy size and shim alignment support 16-byte loop', len(fd) % 16 == 0 and len(shim) % 16 == 0)

    map_path = ART / 'build/FV/FVMAIN_COMPACT.Fv.map'
    symbols, reverse = {}, {}
    for line in map_path.read_text().splitlines():
        match = re.match(r'\s+(0x[0-9a-fA-F]+)\s+(\S+)', line)
        if match:
            address = int(match[1], 16)
            symbols[match[2]] = address
            reverse.setdefault(address, set()).add(match[2])
    entry = symbols['_ModuleEntryPoint']
    vector_target = branch_target(word(fd, 0), base)
    check('FD reset-vector B reaches SEC map entry', vector_target == entry)
    # Current inspected FD: outer FV header (72), FFS header (24), padding
    # section (244), then TE section header (4). No files are extracted.
    te_at = 72 + 24 + 244 + 4
    signature, machine, sections, subsystem, stripped, entry_rva, text_rva, image_base = struct.unpack_from('<HHBBHIIQ', fd, te_at)
    check('TE header agrees with linked entry and physical layout',
          signature == 0x5a56 and machine == 0xaa64 and image_base + entry_rva == entry
          and base + te_at + 40 - stripped == image_base)
    entry_at = entry - base
    slot = adr_target(word(fd, entry_at), entry)
    check('SEC entry ADR points to gSecEntryArg0', slot == symbols['gSecEntryArg0'])
    check('SEC first store preserves X0 to the slot', word(fd, entry_at + 4) == 0xf9000020)
    first_calls = []
    for offset in range(symbols['SecEntry'] - base, symbols['SecEntry'] - base + 128, 4):
        insn = word(fd, offset)
        if insn & 0xfc000000 == 0x94000000:
            target = branch_target(insn, base + offset)
            first_calls.append(dict(pc=hex(base + offset), target=hex(target), symbols=sorted(reverse.get(target, []))))
    check('compiled C entry first calls perform cache setup',
          [x['symbols'][0] for x in first_calls[:3]] == ['ArmDisableDataCache', 'ArmInvalidateInstructionCache', 'ArmEnableInstructionCache'])
    check('compiled early entry has no explicit SPSel selection',
          not any(word(fd, n) in (0xd50040bf, 0xd50041bf) for n in range(entry_at, slot - base, 4)))
    check('linked SEC exception vector has 2KiB alignment', symbols['SecVectorTable'] % 2048 == 0)

    report_path = ROOT / 'reports/firmware-ci/39764322744/BUILD_REPORT.txt'
    build_report = report_path.read_text()
    at = build_report.index('Module Name:          Sec')
    section = build_report[at:build_report.index('Module Name:', at + 1)]
    names = ('PcdDebugPropertyMask', 'PcdDebugPrintErrorLevel', 'PcdFixedDebugPrintErrorLevel',
             'PcdFrameBufferWidth', 'PcdFrameBufferHeight', 'PcdFrameBufferColorDepth', 'PcdFrameBufferDelay',
             'PcdCPUCoresStackBase', 'PcdCPUCorePrimaryStackSize')
    pcds = {}
    for name in names:
        match = re.search(r'\b' + name + r'\s*:.*?=\s*(0x[0-9a-fA-F]+)', section)
        if not match:
            raise ValueError('Missing actual SEC PCD: ' + name)
        pcds[name] = int(match[1], 16)
    check('actual SEC uses framebuffer serial implementation', 'FrameBufferSerialPortLib.inf' in section)
    check('actual SEC uses serial debug implementation', 'BaseDebugLibSerialPort.inf' in section)
    check('actual SEC debug agent is null', 'DebugAgentLibNull.inf' in section)
    check('actual SEC banner and exception messages are in FD',
          b'Project Silicium for %a %a' in fd and b'Synchronous Exception at' in fd)
    check('actual masks permit WARN and ERROR but not INFO',
          pcds['PcdDebugPropertyMask'] & 2 and pcds['PcdDebugPrintErrorLevel'] & 2
          and pcds['PcdDebugPrintErrorLevel'] & 0x80000000 and not pcds['PcdDebugPrintErrorLevel'] & 0x40)
    check('assert mask requests deadloop rather than breakpoint',
          pcds['PcdDebugPropertyMask'] & 0x20 and not pcds['PcdDebugPropertyMask'] & 0x10)

    source_paths = ['BootShim/BootShim.S', 'Silicon/Silicium/SiliciumPkg/Sec/Sec.c',
        'Silicon/Silicium/SiliciumPkg/Sec/AArch64/ModuleEntryPoint.S',
        'Silicon/Silicium/SiliciumPkg/Sec/AArch64/Helper.S',
        'Silicon/Silicium/SiliciumPkg/Sec/AArch64/ArchSec.c',
        'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c',
        'Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBuffer.h',
        'Silicon/Silicium/SiliciumPkg/Library/MemoryMapHelperLib/MemoryMapHelper.c',
        'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c',
        'Silicon/Qualcomm/KailuaPkg/Library/PlatformSecLib/PlatformSec.c',
        'Silicon/Qualcomm/KailuaPkg/Library/PlatformSecLib/AArch64/PlatformHelper.S',
        'Silicon/Qualcomm/QcomPkg/Library/ArmSmmuDetachLib/ArmSmmuDetachLib.c',
        'Mu_Basecore/MdePkg/Library/BaseDebugLibSerialPort/DebugLib.c',
        'Mu_Basecore/MdePkg/Library/BaseDebugPrintErrorLevelLib/BaseDebugPrintErrorLevelLib.c',
        'Mu_Basecore/MdePkg/Library/ArmLib/AArch64/AArch64Support.S']
    source_hashes = [dict(path=str(FW / path), sha256=sha((FW / path).read_bytes())) for path in source_paths]
    map_source = (FW / source_paths[8]).read_text()
    fb = re.search(r'\{"Display Reserved",\s*(0x\w+),\s*(0x\w+)', map_source)
    fb_base, fb_length = int(fb[1], 16), int(fb[2], 16)
    pixel_bytes = pcds['PcdFrameBufferWidth'] * pcds['PcdFrameBufferHeight'] * pcds['PcdFrameBufferColorDepth'] // 8
    check('compiled geometry fits declared Display Reserved region', pixel_bytes + 8 <= fb_length)
    dt_module = importlib.util.spec_from_file_location('own_dt_parser', ROOT / 'scripts/audit-trial-boot-inputs.py')
    dt_parser = importlib.util.module_from_spec(dt_module); dt_module.loader.exec_module(dt_parser)
    dt_path = ROOT / 'out/trial-boot/nuwa-android-live.dtb'
    dt_bytes = dt_path.read_bytes(); dt_nodes = dt_parser.properties(dt_bytes)
    splash = dt_nodes['/reserved-memory/splash_region']
    splash_base, splash_size = struct.unpack('>QQ', splash['reg'])
    check('historical Android splash reservation matches static framebuffer region',
          splash_base == fb_base and splash_size == fb_length)
    recipe = json.loads((ROOT / 'config/firmware-ci-inputs.json').read_text())
    for item in recipe['inputs']:
        if item['root'] == 'firmware' and str(FW / item['path']) in {x['path'] for x in source_hashes}:
            check('pinned source LF hash: ' + item['path'],
                  sha((FW / item['path']).read_bytes().replace(b'\r\n', b'\n')) == item['lf_sha256'])

    # Read/decompress only an archived ABL input, using the repository's own FV
    # parser. Strings identify code paths, not which path ran during the trial.
    spec = importlib.util.spec_from_file_location('fv_reader', ROOT / 'scripts/ci/inspect-firmware-candidate.py')
    fv = importlib.util.module_from_spec(spec); spec.loader.exec_module(fv)

    class AblReader(fv.Firmware):
        def __init__(self):
            super().__init__(); self.messages = set()

        def sections(self, data, owner, depth):
            for match in re.finditer(rb'[\x20-\x7e]{8,}', data):
                text = match.group().decode()
                if any(key in text for key in ('Kernel mode check 32/64', 'Failed to load/authenticate boot image', 'BootLinux:')):
                    self.messages.add(text)
            return super().sections(data, owner, depth)

    abl = (BACKUP / 'abl_a.img').read_bytes()
    check('archived ABL hash pinned', sha(abl) == '38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188')
    reader = AblReader(); reader.volume(abl[4096:], 'Archived ABL')
    result = dict(scope='Offline static audit only; no device access, image creation or execution',
        sources=recipe['sources'], source_hashes=source_hashes,
        artifacts=[dict(path=str(path), sha256=sha(path.read_bytes())) for path in
                   (candidate_path, map_path, report_path)], headers=headers,
        bootshim=dict(bytes=len(shim), destination=hex(base), copy_bytes=len(fd),
          source_expression='L + 112; L is the unknown actual ABL load address',
          preserved_argument='X0; scratch X1-X6 may change',
          unvalidated=['incoming EL/DAIF/MMU/cache state', 'source/destination and DTB non-overlap',
                       'new destination cache coherency before BR X5']),
        sec=dict(fd_reset_vector_target=hex(vector_target), te_entry=hex(image_base + entry_rva),
                 saved_x0_slot=hex(slot), c_entry=hex(symbols['SecEntry']), early_compiled_calls=first_calls,
                 exception_vector=hex(symbols['SecVectorTable']),
                 spsel='inherited; no explicit selection in compiled early entry', pcds=pcds),
        logging=dict(route='DebugLib -> SerialPortWrite -> framebuffer pixels; not UART/USB/file',
          debug_agent='null', framebuffer_base=hex(fb_base), declared_region_bytes=fb_length,
          pixel_bytes=pixel_bytes, assumed_stride_bytes=pcds['PcdFrameBufferWidth'] * 4,
          historical_android_splash=dict(path=str(dt_path), sha256=sha(dt_bytes),
              base=hex(splash_base), bytes=splash_size, scope='Historical Android DT; not candidate live scanout'),
          first_banner_preceded_by=['BootShim', 'SEC assembly and stack', 'cache/vector setup', 'PlatformInitialize SMMU detach', 'framebuffer clear'],
          exceptions='SerialPortWrite of type/ELR then CpuDeadLoop; same framebuffer dependency'),
        archived_abl=dict(sha256=sha(abl), scope='Archived input only; current installed ABL not queried',
                         volumes=reader.volumes, messages=sorted(reader.messages),
                         live_handoff_policy='unverified; strings are not control-flow proof'),
        protocol_reference='https://docs.kernel.org/arch/arm64/booting.html',
        passed_static_checks=checks, runtime_status='unverified; device access remains paused')
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(checks=len(checks), headers=headers, sec=result['sec'], logging=result['logging']), indent=2))


if __name__ == '__main__':
    main()
