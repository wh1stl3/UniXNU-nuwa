#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build and audit an incomplete, host-only 20H392 CPU display archive."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DRIVER_REV = 'e47c1b8de169cd2bd0b885c7d85e433010e3cdf2'
BASE_REV = '693f5d9cae8a408dd18b39f3f9fdc4228c934241'
INIT = '__GLOBAL__sub_I_NativeLegacyDisplay.cpp'
DEFERRED = {'_native_legacy_vsync_notify'}
START_REFRESH = '_nuwa_legacy_publish_start_refresh'
OLD_REFRESH = '_native_legacy_set_refresh_properties'
# The pinned 8796 reference import list includes owner and weak-ref bits;
# different toolchains may need a deliberate requalification, not a whitelist
# that silently swallows new unresolved symbols.
UNRESOLVED_SHA256 = 'c2b547267d51f69a79995ecceab0c6bd12b315b358e8720849b8f29795c12862'
CPU_UNRESOLVED_SHA256 = 'bd169e2fd505971d5cb6b15978e787b831f5bfaee160ef7fcc5a5ae1e475a121'
# Intentional nub IOPlatformDevice -> IOService fix: IOPlatformDevice's
# compareName/getResources unconditionally cast the provider to IOPlatformExpert.
# Added: __ZN9IOServiceC1Ev, __ZN9IOServicenwEm
# Removed: __ZN16IOPlatformDeviceC1Ev, __ZN16IOPlatformDevicenwEm
# NormalModeEnable/ADCLLoadAll publication adds _kOSBooleanTrue and
# _kOSBooleanFalse to the board object's imports.
NO_VSYNC_UNRESOLVED_SHA256 = 'a2d0d02b50e7819b421d742e489a9761e6d8e808f4258bbd9a2c4be8460d8120'
GPU_IMPORTS = {
    '_native_adreno_fences', '_native_adreno_fences_detail',
    '_native_gpu_trace_enabled', '_native_gpu_trace_record',
}
CPU_REMOVED_IMPORTS = GPU_IMPORTS | {
    '_native_ufs_dpu_map', '_native_ufs_dpu_state',
}
CPU_EXCLUDED = CPU_REMOVED_IMPORTS | {
    '_native_legacy_gpu_offer', '_native_legacy_gpu_complete',
    '_native_legacy_gpu_fallback_observed', '_native_legacy_direct_snapshot',
    '_native_legacy_direct', '_native_legacy_early_retires', '_native_legacy_early_failures',
}
SLOTS = {
    184: '__ZN19NativeLegacyDisplay13isMainDisplayEv',
    188: '__ZN19NativeLegacyDisplay11getDotPitchEPj',
    212: '__ZN19NativeLegacyDisplay18supportedFrameInfoEjPjPc',
    321: '__ZN19NativeLegacyDisplay24collectCompletionReportsEjPvPjj',
    329: '__ZN19NativeLegacyDisplay9opaque329Ev',
    330: '__ZN25IOMobileFramebufferLegacy9opaque330Ev',
}
BASE_METHOD = '''    IOReturn supportedFrameInfo(uint32_t,uint32_t *count,char *key,uint32_t *mask) override {
        if(!count || !key || !mask)return kIOReturnBadArgument;
        *count=0;*mask=0;bzero(key,64);return kIOReturnUnsupported;
    }'''
NUWA_METHOD = '''    IOReturn supportedFrameInfo(uint32_t,uint32_t *count,char *key) override {
        if(!count || !key)return kIOReturnBadArgument;
        *count=0;bzero(key,64);return kIOReturnUnsupported;
    }'''
BASE_REGISTER_REFRESH = '''        // Nothing in the family publishes IOMFBDisplayRefresh (its platform subclass does), and without it the render server keeps its own
        // 1/60 s heartbeat (int-210: refresh=0). Publish it before any client can find the display, only when sheng-vsync asks for more.
        unsigned hz=native_legacy_refresh_hz();
        if(primary && hz>60 && hz<=240)native_legacy_set_refresh_properties(this);
'''
BASE_HARDWARE_RETURN = '        OSSafeReleaseNULL(mapping);return valid;'
NUWA_HARDWARE_RETURN = '''        OSSafeReleaseNULL(mapping);
        // Legacy start tests this slot before its first registerService.
        if(valid && primary && !nuwa_legacy_publish_start_refresh(*this,native_legacy_refresh_hz())) {
            primary=false;
            OSSafeReleaseNULL(bootMapping);
            return false;
        }
        return valid;'''


def adapt_source(text, original):
    for before, after in (
            (BASE_METHOD, NUWA_METHOD),
            ('extern "C" bool native_legacy_set_refresh_properties(void *display);',
             '#include "NuwaDisplayRefresh.h"'),
            (BASE_REGISTER_REFRESH, ''),
            (BASE_HARDWARE_RETURN, NUWA_HARDWARE_RETURN)):
        if text.count(before) != 1:
            raise SystemExit(f'{original}: expected exactly one match for {before.splitlines()[0]}')
        text = text.replace(before, after, 1)
    return text


def pixsig_source(text, original):
    # The CPU-only replay has no GPU completion or direct scanout path.
    # Read the already mapped source only after a successful CPU store.
    for before, after in (
        ('#include "NuwaDisplayRefresh.h"',
         '''#include "NuwaDisplayRefresh.h"
#include "NuwaPixelSig.h"
#include <machine/machine_routines.h>
// XNU 8796 arm/cpu_data.h declares this under MACH_KERNEL_PRIVATE.
extern "C" int get_preemption_level(void);
struct nuwa_pix_state nuwa_pix_state;'''),
        ('            native_legacy_transfer_observed(kIOReturnSuccess,request,blankLength);',
         '''            nuwa_pix_blank(&nuwa_pix_state);
            native_legacy_transfer_observed(kIOReturnSuccess,request,blankLength);'''),
        ('            shadowValid=false;OSSafeReleaseNULL(source);transferred=true;',
         '''            observeCopiedSource(surface,source,allocation,width,height,sourceStride);
            shadowValid=false;OSSafeReleaseNULL(source);transferred=true;'''),
        ('        OSSafeReleaseNULL(source);transferred=true;\n',
         '''        observeCopiedSource(surface,source,allocation,width,height,sourceStride);
        OSSafeReleaseNULL(source);transferred=true;
'''),
        ('    void kickOnce() {',
         '''    static void observeCopiedSource(OSObject *surface,IOMemoryMap *source,
        uint64_t allocation,uint32_t width,uint32_t height,uint64_t stride) {
        const bool threadContext=!ml_at_interrupt_context() && ml_get_interrupts_enabled() &&
            get_preemption_level()==0;
        const auto *bytes=threadContext ?
            reinterpret_cast<const uint8_t *>(source->getVirtualAddress()) : nullptr;
        nuwa_pix_surface(&nuwa_pix_state,bytes,allocation,width,height,stride,
            native_legacy_surface_format(surface),native_legacy_surface_planes(surface),
            mach_absolute_time());
    }
    void kickOnce() {'''),
    ):
        if text.count(before) != 1:
            raise SystemExit(f'{original}: pixel hook anchor mismatch at {before.strip()}')
        text = text.replace(before, after, 1)
    return text


def cpu_only_source(text, original):
    """Pinned e47c1b8 overlay: omit offload and direct scanout, not just imports."""
    # Each range starts/ends on one exact line. The revision/cleanliness gate
    # before staging also pins the contents between these boundaries.
    for first, after in (
        ('#define NATIVE_GPU_TRACE_OPTIONAL', '#include "NativeLegacyRequest.h"'),
        ('// GPU hand-off (boot-arg sheng-fb-gpu=1): the frame is offered to the privileged GPU client instead of being copied; the swap retires when the',
         "// The compositor's swapped surfaces, for a display that fetches them itself: [0] distinct surfaces seen, [1] swaps checked; for the first four, at"),
        ("// Direct scanout (sheng-dpu-scanout=2): the display's two pipes fetch the compositor's surface through the display bank's window",
         "// The swap lifecycle: native_legacy_ring holds the newest native_legacy_ring_cap events (allocated at start: a static array of this size no longer fits the kernel's data segment), {[0] microseconds since boot (64 bit), [1] event << 56 | slot + 1 << 48 |"),
        ('extern "C" uint32_t native_ufs_dpu_map(unsigned slot,const uint64_t *pages,unsigned count) __attribute__((weak_import));',
         'static void noteSurface(OSObject *surface,IOMemoryDescriptor *memory)'),
        ('extern "C" void native_legacy_gpu_fallback_observed(int status);',
         '// Swaps the family gave up on after waiting 5 s for them (cancelSwapsAfterTimeout).'),
        ('class NativeLegacyDisplay;', 'class NativeLegacyDisplay : public IOMobileFramebufferLegacy {'),
        ('    uint64_t traceRequestIds[8];', '    uint64_t validatedAt[8];   // no initializer: IOKit objects are allocated zeroed, and a member memset would push the constructor\'s call to the original C2 out of the binding check\'s window'),
        ('        if(&native_gpu_trace_enabled && native_gpu_trace_enabled()) {',
         '        if(!native_legacy_ring_cap)return;'),
        ('    // Microseconds since this request was validated, 0 when it is not tracked.',
         '    void addValidated(const OriginalLegacySwapRequest *request) {'),
        ('    const OriginalLegacySwapRequest *gpuRequest=nullptr;',
         "    // The refresh tick runs on the family's work loop, the loop of the command gate that registers and removes the vsync clients, so the"),
        ('    // Direct scanout state, used on the work loop only. DPU 9.2 inside the MDP block (0xae01000): VIG 0 and 1 at 0x4000 and 0x6000 (source',
         '    bool vsyncWanted() const {'),
        ("    // Called by the GPU client's completion (any thread): the swap is finished on the framebuffer's work loop.",
         '    void free() override {stopVsync();if(logicalPM){PMstop();logicalPM=false;}primary=false;OSSafeReleaseNULL(bootMapping);IOMobileFramebufferLegacy::free();}'),
        ('        directToBoot();latchRequest=nullptr;pendingSlot=-1;',
         '        if(logicalPM){PMstop();logicalPM=false;}'),
        ('        if(directOn && !half && !gpuBypass && latchRequest)stat(5);',
         '        // Surfaces may be write-combined (iPadOS 27 display surfaces are): reading them uncached costs seconds per frame. Read through'),
        ('    // The GPU client reported its copy (status 0) or lost it. Success retires the swap like a finished copy; anything else uses the CPU copy.',
         '    // Hands the pending head to the unchanged family\'s completion. Leaves transferred alone: the callers decide when the next frame may go.'),
    ):
        first, after = first + '\n', after + '\n'
        if text.count(first) != 1 or text.count(after) != 1 or text.index(first) >= text.index(after):
            raise SystemExit(f'{original}: CPU-only range mismatch at {first.strip()}')
        replacement = '        stat(7);note(7,-1,request);\n' if first.startswith(
            '        if(directOn') else ''
        text = text[:text.index(first)] + replacement + text[text.index(after):]
    for before, after in (
        (';traceRequestIds[i]=0', ''),
        ('|uint64_t(outstanding)<<24', ''),  # Reserved ring bits stay zero without a fence provider.
        (';gpuRequest=nullptr;gpuRetired=false;', ';'),
        ('        startVsync();startDirect();return true;', '        startVsync();return true;'),
        ('            gpuBypass=false;\n', ''),
        ('            directToBoot();\n', ''),
        ('''        if(!gpuBypass) {
            if(!native_legacy_prepare_scanout()) {native_legacy_transfer_observed(kIOReturnNotReady,request,0);return;}
        }''', '''        if(!native_legacy_prepare_scanout()) {native_legacy_transfer_observed(kIOReturnNotReady,request,0);return;}'''),
        ('extern "C" void native_legacy_direct_snapshot(void) {if(gDirectDisplay)gDirectDisplay->snapshot();}\n', ''),
        ('extern "C" void native_legacy_gpu_complete(void *display,int status) {if(display)static_cast<NativeLegacyDisplay *>(display)->gpuComplete(status);}\n', ''),
    ):
        if text.count(before) != 1:
            raise SystemExit(f'{original}: CPU-only replacement mismatch at {before.splitlines()[0]}')
        text = text.replace(before, after, 1)
    return text


def no_software_vsync_source(text, original):
    """Remove the GOP timer lifecycle from the pinned CPU-only source copy."""
    for first, after in (
            ('// Display refresh tick (boot-arg sheng-vsync=', 'extern "C" __attribute__((weak)) unsigned native_legacy_refresh_hz(void) {'),
            ("    // The refresh tick runs on the family's work loop,", '    bool vsyncWanted() const {'),
            ('    bool vsyncWanted() const {', 'public:\n    void free() override {stopVsync();'),
    ):
        if text.count(first) != 1 or text.count(after) != 1 or text.index(first) >= text.index(after):
            raise SystemExit(f'{original}: no-software-vsync range mismatch at {first}')
        text = text[:text.index(first)] + text[text.index(after):]
    for before, after in (
            ('#include <IOKit/IOTimerEventSource.h>\n', ''),
            ('extern "C" void native_legacy_vsync_observed(unsigned event,unsigned hz);\n', ''),
            ('extern "C" uint64_t mach_continuous_time(void);\n', ''),
            (' override {stopVsync();if(logicalPM)', ' override {if(logicalPM)'),
            ('        stopVsync();\n', ''),
            ('        startVsync();return true;', '        return true;'),
            ('        armVsync();\n', ''),
            ('        native_legacy_vsync_observed(5,hz);\n', ''),
    ):
        if text.count(before) != 1:
            raise SystemExit(f'{original}: no-software-vsync replacement mismatch at {before.strip()}')
        text = text.replace(before, after, 1)
    return text


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def compile_args(record, source, obj, driver):
    # Replay the previous real 8796 IOPMGR command, substituting inputs and
    # dropping that XNU TU's warning policy (including -Xclang -W pairs).
    original = record['arguments']
    if original.count('-c') != 1 or original.count('-o') != 1 or original.count(record['file']) != 1:
        raise SystemExit('expected a single XNU compile-only input/output')
    args = iter(original)
    command = []
    for arg in args:
        if arg == record['file']:
            command.append(str(source))
        elif arg in ('-MF', '-MJ', '-MT', '-MQ'):
            next(args)
        elif arg in ('-MD', '-MMD', '-MP'):
            continue
        elif arg == '-o':
            next(args)
            command.extend(['-o', str(obj)])
        elif arg == '-Xclang':
            value = next(args)
            if not value.startswith('-W'):
                command.extend([arg, value])
        elif not arg.startswith('-W'):
            command.append(arg)
    osfmk = Path(record['file']).parents[2] / 'osfmk'
    return command + ['-iquote', str(driver), '-I' + str(ROOT / 'package'),
                      '-I' + str(osfmk), '-DNATIVE_LEGACY_CANCEL_SWAPS=0',
                      '-ferror-limit=1']


def object_layout(base, blob):
    location = str(base / 'kits/XnuPrelink')
    if location not in sys.path:
        sys.path.insert(0, location)
    sys.dont_write_bytecode = True
    from native_prelink import macho

    if struct.unpack_from('<III', blob) != (0xfeedfacf, 0x0100000c, 0):
        raise SystemExit('expected an arm64 Mach-O object')
    if struct.unpack_from('<I', blob, 12)[0] != 1:  # MH_OBJECT
        raise SystemExit('expected MH_OBJECT')
    image = macho(blob)
    sym, = (at for cmd, at, _ in image['commands'] if cmd == 2)  # LC_SYMTAB
    symoff, nsyms, stroff, strsize = struct.unpack_from('<4I', blob, sym + 8)
    strings = blob[stroff:stroff + strsize]
    symbols = []
    for i in range(nsyms):
        ix, kind, section, desc, value = struct.unpack_from('<IBBHQ', blob, symoff + i * 16)
        symbols.append((strings[ix:strings.index(b'\0', ix)].decode(), kind, section, desc, value))
    sections = [s for segment in image['segments'] for s in segment['sections']]
    return sections, symbols


def relocations(blob, sections, symbols):
    for sec in sections:
        start, count = struct.unpack_from('<II', blob, sec['command_offset'] + 56)
        for off, word in struct.iter_unpack('<II', blob[start:start + count * 8]):
            if word & (1 << 27):
                yield sec, off, word >> 24, symbols[word & 0xffffff][0]


def inspect_cpu_only(base, obj):
    blob = obj.read_bytes()
    sections, symbols = object_layout(base, blob)
    nm = subprocess.check_output(['llvm-nm', '-P', obj], text=True)
    if (CPU_EXCLUDED.intersection(line.split()[0] for line in nm.splitlines() if line)
            or CPU_EXCLUDED.intersection(name for name, *_ in symbols)
            or CPU_EXCLUDED.intersection(name for _, _, _, name in relocations(blob, sections, symbols))):
        raise SystemExit(f'{obj.name}: GPU/DPU symbol or relocation survived CPU-only compilation')
    if any(arg in blob for arg in (b'sheng-dpu-scanout\0', b'sheng-early-retire\0')):
        raise SystemExit(f'{obj.name}: GPU/DPU boot-arg branch survived')


def inspect_no_software_vsync(base, obj, *, driver):
    blob = obj.read_bytes()
    sections, symbols = object_layout(base, blob)
    refs = list(relocations(blob, sections, symbols))
    for name in {s[0] for s in symbols} | {name for _, _, _, name in refs}:
        if 'vsync' in name.lower() or 'IOTimerEventSource' in name or name == '_mach_continuous_time':
            raise SystemExit(f'{obj.name}: software vsync symbol/relocation survived: {name}')
    if driver:
        calls = {name for sec, _, kind, name in refs if sec['name'] == '__text' and kind == 0x2d}
        required = {
            START_REFRESH, '__ZN19NativeLegacyDisplay14finishTransferEPK25OriginalLegacySwapRequestb',
            '_native_legacy_prepare_scanout', '_flush_dcache64', '_native_legacy_copy_timing_observed',
            '_native_legacy_swap_validation_observed', '_native_legacy_transfer_observed',
            '_native_legacy_retirement_observed',
        }
        if not required <= calls:
            raise SystemExit(f'{obj.name}: missing CPU/refresh branches: {sorted(required - calls)}')


def inspect_original_imports(blob, sections, symbols, original, meta):
    functions = original['functions']
    expected = set(functions) | {original['vtable_symbol'], meta['symbol']}
    imports = {n for n, k, _, _, v in symbols if '25IOMobileFramebufferLegacy' in n
               and k & 0xef == 1 and not v}
    if imports != expected:
        raise SystemExit(f'original-class import mismatch: missing {sorted(expected - imports)}, '
                         f'unexpected {sorted(imports - expected)}')
    _, _, ordinal, _, value = next(s for s in symbols if s[0] == '__ZTV19NativeLegacyDisplay')
    table = sections[ordinal - 1]
    refs = {n: [] for n in functions}
    for sec, off, kind, name in relocations(blob, sections, symbols):
        if name in refs:
            refs[name].append((sec, off, kind))
    audited = {}
    for name, entry in functions.items():
        slot = entry['slot']
        seen = []
        for sec, off, kind in refs[name]:
            fileoff = sec['fileoff'] + off
            if (slot is not None and sec == table and kind == 0x0e and
                    sec['va'] + off == value + 16 + slot * 8 and
                    struct.unpack_from('<Q', blob, fileoff)[0] == 0):
                seen.append({'slot': slot})
            elif (not entry['inherited_only'] and sec['name'] == '__text' and kind == 0x2d
                  and struct.unpack_from('<I', blob, fileoff)[0] in (0x14000000, 0x94000000)):
                seen.append({'branch_offset': hex(sec['va'] + off)})
            else:
                raise SystemExit(f'{name}: unexpected reference {sec["name"]}+{off:#x} ({kind:#x})')
        if not seen or (entry['inherited_only'] and seen != [{'slot': slot}]):
            raise SystemExit(f'{name}: expected an actual import and only its own slot for opaque entries')
        audited[name] = seen
    return audited


def inspect_veneers(blob, sections, symbols, entries):
    sym = {row[0]: row[1:] for row in symbols}
    expected = set(entries)
    if {n for n, k, _, _, _ in symbols if '25IOMobileFramebufferLegacy' in n
            and k & 1} != expected | {n + '.original' for n in expected}:
        raise SystemExit('unexpected original-class symbols in veneer object')
    positions = {}
    for name in entries:
        kind, ordinal, _, va = sym[name]
        sec = sections[ordinal - 1]
        off = va - sec['va']
        if kind != 0x0f or sec['name'] != '__text' or struct.unpack_from(
                '<I', blob, sec['fileoff'] + off)[0] != 0x14000000:
            raise SystemExit(f'{name}: expected an owned B veneer')
        if sym[name + '.original'] != (1, 0, 0, 0) or off in positions:
            raise SystemExit(f'{name}: expected unique veneer and external target')
        positions[off] = name + '.original'
    actual = [(sec['name'], off, kind, name) for sec, off, kind, name in relocations(blob, sections, symbols)]
    if sorted(actual) != sorted(('__text', off, 0x2d, name) for off, name in positions.items()):
        raise SystemExit('veneer branch relocations do not match exact original targets')


def inspect_object(base, blob):
    sections, symbols = object_layout(base, blob)
    table_name = '__ZTV19NativeLegacyDisplay'
    (_, kind, ordinal, _, value), = (sym for sym in symbols if sym[0] == table_name)
    if kind & 0x0e != 0x0e or not ordinal:  # N_SECT
        raise SystemExit(f'{table_name} is not defined in a section')
    section = sections[ordinal - 1]
    table = value - section['va']
    if not 0 <= table <= section['size'] - (2 + max(SLOTS)) * 8 - 8:
        raise SystemExit(f'{table_name} has no space for the audited slots')
    reloff, nreloc = struct.unpack_from('<II', blob, section['command_offset'] + 56)
    relocs = list(struct.iter_unpack('<II', blob[reloff:reloff + nreloc * 8]))
    results = {}
    for slot, expected in SLOTS.items():
        offset = table + 16 + slot * 8  # Skip offset-to-top and RTTI.
        words = [word for address, word in relocs if address == offset]
        # External, unsigned, non-PC-relative, 8-byte relocation with no addend.
        if len(words) != 1 or words[0] >> 24 != 0x0e or struct.unpack_from(
                '<Q', blob, section['fileoff'] + offset)[0] != 0:
            raise SystemExit(f'{table_name}[{slot}]: expected one plain pointer relocation')
        target = symbols[words[0] & 0xffffff][0]
        if target != expected:
            raise SystemExit(f'{table_name}[{slot}]: got {target}, expected {expected}')
        results[slot] = {'section_offset': hex(offset), 'symbol': target}
    return {'vtable': table_name, 'section': section['name'], 'slots': results}


def constructor_sections(blob, sections):
    return [s for s in sections if struct.unpack_from(
        '<I', blob, s['command_offset'] + 64)[0] & 0xff in (0x9, 0xA, 0x16)]


def inspect_initializers(base, raw, late):
    sections, symbols = object_layout(base, raw)
    auto = constructor_sections(raw, sections)
    if len(auto) != 1 or (auto[0]['name'], auto[0]['size']) != ('__mod_init_func', 8):
        raise SystemExit('expected exactly one original NativeLegacyDisplay initializer pointer')
    rel, count = struct.unpack_from('<II', raw, auto[0]['command_offset'] + 56)
    if count != 1:
        raise SystemExit('expected one relocation for the original initializer pointer')
    offset, word = struct.unpack_from('<II', raw, rel)
    if (offset, word >> 24, symbols[word & 0xffffff][0]) != (0, 0x0e, INIT) or \
            struct.unpack_from('<Q', raw, auto[0]['fileoff'])[0] != 0:
        raise SystemExit('initializer pointer does not reference the explicit board entry')
    sections, symbols = object_layout(base, late)
    if constructor_sections(late, sections):
        raise SystemExit('automatic initializer/terminator survived in the host archive member')
    if sum(n == INIT and k == 0x0f and s > 0 for n, k, s, _, _ in symbols) != 1:
        raise SystemExit('expected one external manual initializer in the host archive member')


def inspect_metaclass_import(blob, sections, symbols, name):
    got_page, got_pageoff = 0x5d, 0x6c  # ARM64_RELOC_GOT_LOAD_* plus width/extern/pcrel
    index, = (i for i, sym in enumerate(symbols) if sym[0] == name)
    if symbols[index][1:3] != (1, 0) or symbols[index][4] != 0:
        raise SystemExit(f'{name}: expected an undefined object import in the driver')
    pairs = []
    pointers = []
    for sec in sections:
        start, count = struct.unpack_from('<II', blob, sec['command_offset'] + 56)
        relocs = [(off, word >> 24) for off, word in
                  struct.iter_unpack('<II', blob[start:start + count * 8])
                  if word & (1 << 27) and word & 0xffffff == index]
        for off, kind in relocs:
            at = sec['fileoff'] + off
            if sec['name'] == '__text' and kind == got_page and (off + 4, got_pageoff) in relocs:
                if struct.unpack_from('<II', blob, at) != (0x90000002, 0xf9400042):
                    raise SystemExit(f'{name}: expected ADRP/LDR into x2')
                pairs.append(hex(sec['va'] + off))
            elif sec['name'] == '__text' and kind == got_pageoff and (off - 4, got_page) in relocs:
                continue
            elif sec['name'] == '__const' and kind == 0x0e and not struct.unpack_from('<Q', blob, at)[0]:
                pointers.append(hex(sec['va'] + off))
            else:
                raise SystemExit(f'{name}: unexpected relocation {sec["name"]}+{off:#x} ({kind:#x})')
    if len(pairs) != 3 or len(pointers) != 1:
        raise SystemExit(f'{name}: expected three GOT load pairs and one plain pointer')
    return {'got_pages': pairs, 'plain_pointers': pointers}


def inspect_archive(base, archive, members, *, no_software_vsync):
    names = subprocess.check_output(['llvm-ar', 't', archive], text=True).splitlines()
    if names != [obj.name for obj in members]:
        raise SystemExit('unexpected archive member list')
    definitions, undefined = {}, {}
    paths = {}
    abi = json.loads((ROOT / 'package/nuwa-display-abi.json').read_text())
    meta = abi['metaclass']
    original_abi = abi['original_imports']
    functions = original_abi['functions']
    addresses = {n + '.original': int(e['linked_address'], 16) for n, e in functions.items()}
    addresses[meta['symbol']] = int(meta['linked_address'], 16)
    addresses[original_abi['vtable_symbol']] = int(original_abi['vtable_linked_address'], 16)
    for obj in members:
        blob = subprocess.check_output(['llvm-ar', 'p', archive, obj.name])
        original = obj.read_bytes()
        # Darwin archives include up to seven newline alignment bytes in
        # the extracted member. No other change to the object is permitted.
        if blob != original + b'\n' * (-len(original) % 8):
            raise SystemExit(f'{obj.name}: archive member does not match inspected object')
        sections, symbols = object_layout(base, blob)
        if constructor_sections(blob, sections):
            raise SystemExit(f'{obj.name}: archive contains automatic initialization/termination')
        if obj == members[0]:
            meta_relocs = inspect_metaclass_import(blob, sections, symbols, meta['symbol'])
            original_refs = inspect_original_imports(blob, sections, symbols, original_abi, meta)
        if obj == members[3]:
            if {n: (k, s, d, v) for n, k, s, d, v in symbols if k & 1} != {
                    n: (0x03, 0, 0x20, va) for n, va in addresses.items()}:
                raise SystemExit('original-addresses.o: expected the exact collection-slid N_ABS table')
        if obj == members[2]:
            inspect_veneers(blob, sections, symbols, functions)
            for getter, info in abi['surfaces'].items():
                name = '_native_legacy_surface_' + getter
                (_, kind, section, _, value), = (sym for sym in symbols if sym[0] == name)
                sec = sections[section - 1]
                at = sec['fileoff'] + value - sec['va']
                bits = info['load_bits']
                load = (0xf9400000 if bits == 64 else 0xb9400000) | (
                    info['offset'] // (bits // 8) << 10)
                if kind != 0x0f or sec['name'] != '__text' or struct.unpack_from(
                        '<II', blob, at) != (load, 0xd65f03c0):
                    raise SystemExit(f'{name}: assembly does not match qualified getter')
        for name, kind, _, desc, value in symbols:
            if kind & 0xe0 or not kind & 1:
                continue
            if kind & 0x0e or value:  # includes tentative common symbols
                definitions.setdefault(name, []).append((obj.name, bool(desc & 0x80)))
            else:
                undefined.setdefault(name, []).append((obj.name, bool(desc & 0x40)))
        paths[obj.name] = sha256(obj)
    for name, owners in definitions.items():
        if sum(not weak for _, weak in owners) > 1:
            raise SystemExit(f'{name}: duplicate strong archive definitions: {owners}')
    if definitions.get(INIT) != [(members[0].name, False)] or undefined.get(INIT) != [
            (members[1].name, False)]:
        raise SystemExit('manual initializer must be defined by the driver and imported by the board TU')
    for name in addresses.keys() | functions.keys():
        owner = members[2] if name in functions else members[3]
        importer = members[2] if name.endswith('.original') else members[0]
        if definitions.get(name) != [(owner.name, False)] or undefined.get(name) != [(importer.name, False)]:
            raise SystemExit(f'{name}: original binding must have exactly its expected definition and importer')
    unresolved = {name: imports for name, imports in sorted(undefined.items()) if name not in definitions}
    if any('25IOMobileFramebufferLegacy' in name for name in unresolved):
        raise SystemExit('original-class import closure failed')
    missing_glue = {name for name in unresolved if name.startswith(
        ('_native_legacy_surface_', '_native_legacy_set_refresh_', '_native_legacy_vsync_'))}
    if missing_glue != (set() if no_software_vsync else DEFERRED):
        raise SystemExit(f'unexpected unresolved glue: {sorted(missing_glue)}')
    if (OLD_REFRESH in definitions or OLD_REFRESH in undefined or
            definitions.get(START_REFRESH) != [(members[4].name, False)] or
            undefined.get(START_REFRESH) != [(members[0].name, False)]):
        raise SystemExit('start refresh must have one formatter definition and one driver import')
    glued = ['descriptor', 'width', 'height', 'stride', 'allocation', 'format', 'planes']
    for getter in glued:
        name = '_native_legacy_surface_' + getter
        if definitions.get(name) != [(members[2].name, False)] or undefined.get(name) != [
                (members[0].name, False)]:
            raise SystemExit(f'{name}: expected one assembly definition and one driver import')
    fingerprint = hashlib.sha256(json.dumps(
        unresolved, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'members': paths, 'unresolved': unresolved, 'unresolved_sha256': fingerprint,
             'metaclass_relocations': meta_relocs,
             'original_relocations': original_refs,
            'automatic_initializers': 0,
            'manual_initializer': INIT, 'runtime_eligible': False, 'sha256': sha256(archive)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--cpo', required=True, type=Path, help='real 8796 IOPMGR.cpo.json')
    parser.add_argument('--out', required=True, type=Path, help='new directory below device out/')
    parser.add_argument('--cpu-only', action='store_true', help='exclude GPU and DPU scanout at compile time')
    parser.add_argument('--no-software-vsync', action='store_true',
                        help='exclude the GOP software timer lifecycle (requires --cpu-only)')
    parser.add_argument('--pixsig', action='store_true', help='sample CPU swap sources in the replay')
    parser.add_argument('--strip-debug', action='store_true',
                        help='compile the display members with -g0; preserve relocations and symbols')
    parser.add_argument('--bringup-diag', action='store_true')
    args = parser.parse_args()
    if args.no_software_vsync and not args.cpu_only:
        parser.error('--no-software-vsync requires --cpu-only')
    if args.pixsig and not args.no_software_vsync:
        parser.error('--pixsig requires --no-software-vsync')
    base, cpo, out = (p.resolve() for p in (args.base, args.cpo, args.out))
    if (ROOT / 'out').resolve() not in out.parents:
        parser.error('--out must be below the device out/ directory')
    driver = base / 'drivers/GopFramebuffer'
    original = driver / 'NativeLegacyDisplay.cpp'
    # WSL reads the Windows checkout, whose tracked text may have CRLF.
    git = ['git', '--no-optional-locks', '-c', 'core.autocrlf=true', '-C', str(driver)]
    if subprocess.check_output(git[:-1] + [str(base), 'rev-parse', 'HEAD'],
                               text=True).strip() != BASE_REV:
        raise SystemExit(f'expected UniXNU at {BASE_REV}')
    if subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() != DRIVER_REV:
        raise SystemExit(f'expected GopFramebuffer at {DRIVER_REV}')
    if subprocess.check_output(git + ['status', '--porcelain', '--', '.']):
        raise SystemExit('GopFramebuffer inputs are dirty')
    record = json.loads(cpo.read_text().strip().rstrip(','))
    if Path(record['file']).name != 'IOPMGR.cpp' or not Path(record['directory']).is_absolute():
        raise SystemExit(f'{cpo}: expected the IOPMGR.cpp compilation record')
    out.mkdir(parents=True)
    if args.cpu_only:
        # The only base sources this replay can modify are the driver copies.
        # The real 8796 headers/CPO and XnuPrelink remain read-only inputs.
        staged = out / 'base/drivers/GopFramebuffer'
        shutil.copytree(driver, staged, ignore=shutil.ignore_patterns('.git'))
        driver, original = staged, staged / original.name
    text = adapt_source(original.read_text(), original)
    if args.cpu_only:
        text = cpu_only_source(text, original)
        if args.no_software_vsync:
            text = no_software_vsync_source(text, original)
        if args.pixsig:
            text = pixsig_source(text, original)
        original.write_text(text)
    source, obj = (out / ('NativeLegacyDisplay' + suffix) for suffix in ('.cpp', '.o'))
    # Clang's integrated assembler exports the exact synthetic constructor
    # while maintaining the normal Mach-O symbol ordering. Objcopy only
    # drops the automatic pointer; no handwritten rewriting of nlist.
    source.write_text(text + f'\n__asm__(".globl {INIT}");\n')
    refresh = ROOT / 'scripts/host/NuwaDisplayRefresh.cpp'
    refresh_obj = out / 'NuwaDisplayRefresh.o'
    refresh_cmd = compile_args(record, refresh, refresh_obj, driver)
    command = compile_args(record, source, obj, driver) + ['-iquote', str(refresh.parent)]
    if args.pixsig:
        command += ['-iquote', str(ROOT / 'package')]
    provider = ROOT / 'package/NuwaLegacyDisplay.cpp'
    provider_obj = out / 'NuwaLegacyDisplay.o'
    provider_cmd = compile_args(record, provider, provider_obj, driver)
    if args.cpu_only:
        provider_cmd.append('-DNUWA_DISPLAY_HOST_CPU_ONLY=1')
    if args.no_software_vsync:
        provider_cmd.append('-DNUWA_DISPLAY_HOST_NO_SOFTWARE_VSYNC=1')
    if args.bringup_diag:
        provider_cmd.append('-DNUWA_DISPLAY_BRINGUP_DIAG=1')
    if args.strip_debug:
        for cpp_cmd in (command, provider_cmd, refresh_cmd):
            cpp_cmd.append('-g0')
    bindings = ROOT / 'package/original-bindings.S'
    bindings_obj = out / 'original-bindings.o'
    target = [arg for arg in command if arg.startswith('--target=')][-1]
    bindings_cmd = [command[0], target, '-x', 'assembler-with-cpp', '-c',
                    str(bindings), '-o', str(bindings_obj)]
    addresses = ROOT / 'package/original-addresses.S'
    addresses_obj = out / 'original-addresses.o'
    addresses_cmd = [*bindings_cmd[:-3], str(addresses), '-o', str(addresses_obj)]
    write_json(out / 'compile.json', {
        'directory': record['directory'], 'arguments': command,
        'provider_arguments': provider_cmd, 'bindings_arguments': bindings_cmd,
        'refresh_arguments': refresh_cmd, 'refresh_source_sha256': sha256(refresh),
        'refresh_header_sha256': sha256(refresh.with_suffix('.h')),
        'addresses_arguments': addresses_cmd, 'addresses_source_sha256': sha256(addresses),
        'cpo': str(cpo), 'cpo_sha256': sha256(cpo),
        'driver_revision': DRIVER_REV, 'adapted_source_sha256': sha256(source),
        'cpu_only': args.cpu_only,
        'no_software_vsync': args.no_software_vsync,
        'strip_debug': args.strip_debug,
        'board_source_sha256': sha256(provider), 'bindings_source_sha256': sha256(bindings),
    })
    for argv in (command, provider_cmd, bindings_cmd, addresses_cmd, refresh_cmd):
        status = subprocess.run(argv, cwd=record['directory']).returncode
        if status:
            return status
    late = out / 'NativeLegacyDisplay.manual.o'
    subprocess.run(['llvm-objcopy', '--remove-section=__DATA,__mod_init_func', obj, late],
                   check=True)
    inspect_initializers(base, obj.read_bytes(), late.read_bytes())
    result = inspect_object(base, late.read_bytes())
    result.update(bytes=late.stat().st_size, sha256=sha256(late))
    write_json(out / 'object.json', result)
    archive = out / 'HOST-ONLY-incomplete-display.a'
    members = [late, provider_obj, bindings_obj, addresses_obj, refresh_obj]
    if args.cpu_only:
        for item in [obj, *members]:
            inspect_cpu_only(base, item)
    if args.no_software_vsync:
        for item in [obj, *members]:
            inspect_no_software_vsync(base, item, driver=item in (obj, late))
    subprocess.run(['llvm-ar', '--format=darwin', 'rcs', archive, *members], check=True)
    audit = inspect_archive(base, archive, members, no_software_vsync=args.no_software_vsync)
    audit['no_software_vsync'] = args.no_software_vsync
    write_json(out / 'archive.json', audit)
    expected = CPU_UNRESOLVED_SHA256 if args.cpu_only else UNRESOLVED_SHA256
    if args.no_software_vsync:
        expected = NO_VSYNC_UNRESOLVED_SHA256
    # Identity probe adds exactly these four strong board imports; removes none.
    # Check them separately so all existing profile fingerprints remain strict.
    unresolved = audit['unresolved'].copy()
    if args.pixsig:
        for symbol in ('_ml_at_interrupt_context', '_ml_get_interrupts_enabled', '_get_preemption_level'):
            imports = unresolved.get(symbol, [])
            owner = ('NativeLegacyDisplay.manual.o', False)
            if imports.count(owner) != 1:
                raise SystemExit(f'expected pixel sample context check {symbol}')
            imports = [entry for entry in imports if entry != owner]
            if imports:
                unresolved[symbol] = imports
            else:
                del unresolved[symbol]
    for symbol in ('_current_task', '_pid_from_task', '_proc_selfname', '_strcmp'):
        if unresolved.pop(symbol, None) != [(provider_obj.name, False)]:
            raise SystemExit(f'unexpected identity import {symbol}')
    if args.bringup_diag:
        # copyProperty(const char *) is virtual: the board calls its vtable slot,
        # so it adds no direct provider import. Retain the existing vtable import
        # in the strict fingerprint and assert its exact owner.
        if unresolved.get('__ZNK15IORegistryEntry12copyPropertyEPKc') != [('NativeLegacyDisplay.manual.o', False)]:
            raise SystemExit('unexpected copyProperty virtual-table import')
        if unresolved.pop('_boot_progress_diag_set', None) != [(provider_obj.name, False)]:
            raise SystemExit('expected a strong diagnostic import from the board member only')
        if unresolved.pop('_boot_progress_prop_set', None) != [(provider_obj.name, False)]:
            raise SystemExit('expected a strong property diagnostic import from the board member only')
        if unresolved.pop('__ZN12OSDictionary9metaClassE', None) != [(provider_obj.name, False)]:
            raise SystemExit('expected dictionary type check from the board member only')
        for symbol in ('__ZN6OSData9metaClassE', '__ZN15OSMetaClassBase12safeMetaCastEPKS_PK11OSMetaClass'):
            imports = unresolved.get(symbol, [])
            if imports.count((provider_obj.name, False)) != 1:
                raise SystemExit(f'expected property type check import {symbol}')
            unresolved[symbol] = [entry for entry in imports if entry != (provider_obj.name, False)]
    fingerprint = hashlib.sha256(json.dumps(
        unresolved, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if fingerprint != expected:
        raise SystemExit(f'unresolved symbol fingerprint changed: see {out / "archive.json"}')
    print(f'{archive}: {len(audit["unresolved"])} unresolved externals; not runtime-eligible')
    return 0


if __name__ == '__main__':
    sys.exit(main())
