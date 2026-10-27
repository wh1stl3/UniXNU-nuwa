#!/usr/bin/env python3
"""Compare the loader's DARWIN_BOOT_ARGS against the XNU arm64 boot_args.

The kernel reads boot_args->deviceTreeP to initialise the device tree. If the
loader writes the device tree pointer at a different offset than the kernel
reads it from, the kernel sees deviceTreeP == 0, SecureDTInit() marks the tree
uninitialised, SecureDTFindEntry() returns kError without touching memory,
pe_arm_get_soc_base_phys() returns 0, pe_identify_machine() returns early and
gPEClockFrequencyInfo stays zeroed - which is exactly the observed
"invalid bit index" panic.

Usage: boot-args-abi.py <path-to-XNU-boot.h> <path-to-loader-BootArgs.h>
"""

import re
import sys

SCALARS = {
    'uint16_t': 2, 'UINT16': 2, 'unsigned short': 2,
    'uint32_t': 4, 'UINT32': 4, 'unsigned int': 4, 'int': 4,
    'uint64_t': 8, 'UINT64': 8, 'unsigned long': 8, 'long': 8,
    'char': 1, 'CHAR8': 1,
}


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def find_struct_body(text, name):
    # Form 1: "typedef struct { ... } Name;" or "typedef struct Tag { ... } Name;"
    m = re.search(r'typedef\s+struct\s*(?:\w+\s*)?\{(.*?)\}\s*' + re.escape(name) + r'\s*;',
                  text, re.S)
    if m:
        return strip_comments(m.group(1))
    # Form 2: a plain "struct Name { ... };" with a separate typedef alias.
    m = re.search(r'\bstruct\s+' + re.escape(name) + r'\s*\{(.*?)\}\s*;', text, re.S)
    if m:
        return strip_comments(m.group(1))
    raise SystemExit('struct %s not found' % name)

def parse_fields(body):
    """Return [(name, type, count)] for one struct body."""
    fields = []
    for raw in body.split(';'):
        raw = raw.strip()
        if not raw:
            continue
        # Keep a pointer star with the type: "void *deviceTreeP" -> "void *"
        raw = re.sub(r'\b(void|char|uint\d+_t|UINT\d+|unsigned\s+\w+|long|int)\s*\*',
                     r'\1 *', raw)
        parts = raw.split()
        if len(parts) < 2:
            continue
        # "void *deviceTreeP" splits into ["void", "*deviceTreeP"]: the star
        # belongs to the type, not to a separate token.
        if parts[-1].startswith('*'):
            ftype = ' '.join(parts[:-1]) + ' *'
            fname = parts[-1][1:]
        else:
            ftype = ' '.join(parts[:-1])
            fname = parts[-1]
        count = 1
        m = re.search(r'\[([^\]]*)\]', fname)
        if m:
            fname = fname[:m.start()]
            token = m.group(1).strip()
            count = int(token) if token.isdigit() else ('MACRO:' + token)
        fields.append((fname, ftype, count))
    return fields


def macro_value(name, text):
    m = re.search(r'#\s*define\s+' + re.escape(name) + r'\s+(\d+)', text)
    return int(m.group(1)) if m else None


def type_size(ftype, text):
    ftype = ftype.strip()
    if ftype.endswith('*'):
        return 8
    if ftype in SCALARS:
        return SCALARS[ftype]
    if ' ' in ftype:
        # "unsigned long" and friends are already in SCALARS; anything else
        # with a space is a type we cannot size safely.
        return None
    body = find_struct_body(text, ftype)
    total = 0
    for _, ftype2, count2 in parse_fields(body):
        base = type_size(ftype2, text)
        if base is None:
            return None
        if isinstance(count2, str) and count2.startswith('MACRO:'):
            resolved = macro_value(count2[6:], text)
            if resolved is None:
                return None
            count2 = resolved
        total += base * count2
    return total


def align_to(value, alignment):
    if alignment <= 1:
        return value
    return (value + alignment - 1) & ~(alignment - 1)


def alignment_of(ftype, text):
    ftype = ftype.strip()
    if ftype.endswith('*'):
        return 8
    if ftype in SCALARS:
        return SCALARS[ftype]
    if ' ' in ftype:
        return None
    try:
        body = find_struct_body(text, ftype)
    except SystemExit:
        return None
    return max((alignment_of(t, text) or 1) for _, t, _ in parse_fields(body)) or 1


def layout(fields, text):
    """Lay out the struct with C natural alignment, like the real compiler."""
    out = []
    off = 0
    for fname, ftype, count in fields:
        size = type_size(ftype, text)
        if size is None:
            return None
        if isinstance(count, str) and count.startswith('MACRO:'):
            resolved = macro_value(count[6:], text)
            if resolved is None:
                return None
            count = resolved
        align = alignment_of(ftype, text) or 1
        off = align_to(off, align)
        out.append((fname, ftype, off, size * count, count))
        off += size * count
    return out


def main():
    xnu_path, loader_path = sys.argv[1], sys.argv[2]
    xnu_text = open(xnu_path, encoding='utf-8', errors='replace').read()
    loader_text = open(loader_path, encoding='utf-8', errors='replace').read()

    xnu = layout(parse_fields(find_struct_body(xnu_text, 'boot_args')), xnu_text)
    loader = layout(parse_fields(find_struct_body(loader_text, 'DARWIN_BOOT_ARGS')),
                    loader_text)
    if xnu is None or loader is None:
        raise SystemExit('could not resolve a field size')

    print('=== XNU arm64 boot_args (%s) ===' % xnu_path)
    for fname, ftype, off, size, count in xnu:
        print('  +0x%03x  %-18s %-16s %4d bytes%s'
              % (off, fname, ftype, size, ' x%d' % count if count > 1 else ''))
    print('\n=== loader DARWIN_BOOT_ARGS (%s) ===' % loader_path)
    for fname, ftype, off, size, count in loader:
        print('  +0x%03x  %-18s %-16s %4d bytes%s'
              % (off, fname, ftype, size, ' x%d' % count if count > 1 else ''))

    xmap = {f: off for f, _, off, _, _ in xnu}
    lmap = {f: off for f, _, off, _, _ in loader}

    print('\n=== field alignment for the fields that matter ===')
    pairs = [('deviceTreeP', 'DeviceTree'),
             ('deviceTreeLength', 'DeviceTreeLength'),
             ('machineType', 'MachineType'),
             ('Video', 'Video'),
             ('CommandLine', 'CommandLine'),
             ('bootFlags', 'BootFlags'),
             ('memSizeActual', 'MemorySizeActual'),
             ('virtBase', 'VirtualBase'),
             ('physBase', 'PhysicalBase'),
             ('memSize', 'MemorySize'),
             ('topOfKernelData', 'TopOfKernelData')]
    bad = []
    for xf, lf in pairs:
        xo, lo = xmap.get(xf), lmap.get(lf)
        if xo is None or lo is None:
            print('  ?      %-18s @ xnu %-6s  %-20s @ loader %s' % (xf, xo, lf, lo))
            continue
        ok = xo == lo
        if not ok:
            bad.append((xf, lf, xo, lo))
        print('  %s %-18s @ xnu +0x%03x   %-20s @ loader +0x%03x  (delta %+d)'
              % ('OK  ' if ok else 'DIFF', xf, xo, lf, lo, lo - xo))

    print('\n%s' % ('ALL OFFSETS MATCH' if not bad else
                    '%d MISMATCHED FIELD(S) -> the kernel cannot read what the '
                    'loader wrote:' % len(bad)))
    for xf, lf, xo, lo in bad:
        print('  %s: kernel reads +0x%03x, loader writes +0x%03x' % (xf, xo, lo))


if __name__ == '__main__':
    main()
