"""Compare source header layouts as ARM64 LP64; no compilation/image changes.

This does not recover the compiled kernel's DWARF type or validate runtime ABI.
"""
import ctypes as c
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
XNU = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/pexpert/pexpert/arm64/boot.h')
LOADER = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/DarwinBoot/DarwinBootPkg/Driver/BootArgs.h')


def layout(command_bytes):
    # ARM64 ABI: unsigned long and pointers are 64-bit, independent of Windows.
    class Args(c.LittleEndianStructure):
        _fields_ = [('Revision', c.c_uint16), ('Version', c.c_uint16),
                    ('VirtualBase', c.c_uint64), ('PhysicalBase', c.c_uint64),
                    ('MemorySize', c.c_uint64), ('TopOfKernelData', c.c_uint64),
                    ('Video', c.c_uint64 * 6), ('MachineType', c.c_uint32),
                    ('DeviceTree', c.c_uint64), ('DeviceTreeLength', c.c_uint32),
                    ('CommandLine', c.c_char * command_bytes),
                    ('BootFlags', c.c_uint64), ('MemorySizeActual', c.c_uint64)]
    return dict(size=c.sizeof(Args), command_line_bytes=command_bytes,
                offsets={name: getattr(Args, name).offset for name, _ in Args._fields_})


def main():
    xnu, loader = XNU.read_bytes(), LOADER.read_bytes()
    # This model was reviewed for these precise source declarations. Fail closed
    # on a different header rather than silently model only its string length.
    assert hashlib.sha256(xnu).hexdigest() == 'e69bc1d56697c6ac649b8700551bb50df0f4cf3e31f8390bac799aca9a91868e'
    assert hashlib.sha256(loader).hexdigest() == '1d6b172a306bf5d3fc409d22bd7e674d166e5fde92652c4135de5c79f3eddd16'
    xs, ls = xnu.decode(), loader.decode()
    xlength = int(re.search(r'#define\s+BOOT_LINE_LENGTH\s+(\d+)', xs).group(1))
    llength = int(re.search(r'CommandLine\[(\d+)\]', ls).group(1))
    xl, ll = layout(xlength), layout(llength)
    # Guard the simplified model against changes in the two declarations.
    assert 'uint64_t                memSizeActual' in xs
    assert 'UINT64  MemorySizeActual;' in ls
    assert ll['size'] == 0x480
    assert ll['offsets']['DeviceTree'] == 0x60
    assert ll['offsets']['CommandLine'] == 0x6c
    assert ll['offsets']['MemorySizeActual'] == 0x478
    assert xl['offsets']['DeviceTree'] == ll['offsets']['DeviceTree']
    assert xl['offsets']['CommandLine'] == ll['offsets']['CommandLine']
    result = dict(scope='Source-header comparison under explicit ARM64 LP64 layout; compiled CI15 type and runtime remain unverified',
                  xnu=dict(path=str(XNU), sha256=hashlib.sha256(xnu).hexdigest(), layout=xl),
                  loader=dict(path=str(LOADER), sha256=hashlib.sha256(loader).hexdigest(), layout=ll),
                  differences={key: dict(xnu=xl['offsets'][key], loader=ll['offsets'][key])
                      for key in xl['offsets'] if xl['offsets'][key] != ll['offsets'][key]},
                  compatible_source_layouts=xl == ll,
                  compiled_kernel_type_checked=False, device_accessed=False,
                  image_written=False)
    out = ROOT / 'reports/official-site-audit/darwin22-boot-args.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
