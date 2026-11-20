#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Derive the nuwa (iOS 16.7.16 / 20H392) IOMobileFramebufferLegacy ABI from our donor kernelcache.

Read-only inputs: the 20H392 kernelcache and the base checkout's XnuPrelink Mach-O parser.
Outputs: package/OriginalLegacyFramebufferABI.h, package/original-bindings.S and a JSON summary.

Every number below is anchored to an instruction in the family executable; the checks assert the
anchors before anything is written. Slot roles were found by structure (callers, argument use,
return shape) and by the same base-class stub sequence, never by carrying a number from another
board's build. See docs/nuwa-display-abi-20261120.md for the per-item derivation.

Recompute:
  python3 scripts/derive-nuwa-display-abi.py --base /path/to/UniXNU \
      --kernelcache /path/to/20H392/kernelcache.decompressed --out package
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILY = 'com.apple.iokit.IOMobileGraphicsFamily'
SLOTS = 338
PURE = [211, 212, 242, 243, 292, 293, 321, 322, 329]

# vtable entry -> role. Anchors are the method addresses themselves plus the instruction checks below.
ROLES = {
    246: ('void getDisplayDimensions(uint32_t *, uint32_t *)', '5c247ac'),
    274: ('bool startHardware()', '5c17e44'),
    276: ('void kickSwapQueue()', '5c192b8'),
    281: ('void completeCurrentSwap()', '5c1ace4'),
    282: ('bool validateSwap(const OriginalLegacySwapRequest *)', '5c1ad10'),
    287: ('bool getRefreshAttributes(uint64_t *, bool)', '5c234b4'),
    336: ('int applyStateRequest(OriginalLegacyStateRequest *, bool)', '5c1c1d8'),
}

# Mangled names verified with clang++ -target arm64-apple-ios16.0 and llvm-nm against this class shape.
MANGLED = {
    'getDisplayDimensions': '__ZN25IOMobileFramebufferLegacy20getDisplayDimensionsEPjS0_',
    'startHardware': '__ZN25IOMobileFramebufferLegacy13startHardwareEv',
    'kickSwapQueue': '__ZN25IOMobileFramebufferLegacy13kickSwapQueueEv',
    'completeCurrentSwap': '__ZN25IOMobileFramebufferLegacy19completeCurrentSwapEv',
    'validateSwap': '__ZN25IOMobileFramebufferLegacy12validateSwapEPK25OriginalLegacySwapRequest',
    'getRefreshAttributes': '__ZN25IOMobileFramebufferLegacy20getRefreshAttributesEPyb',
    'applyStateRequest': '__ZN25IOMobileFramebufferLegacy17applyStateRequestEP26OriginalLegacyStateRequestb',
}
SLOT_SYMBOL = {246: 'getDisplayDimensions', 274: 'startHardware', 276: 'kickSwapQueue',
               281: 'completeCurrentSwap', 282: 'validateSwap', 287: 'getRefreshAttributes',
               336: 'applyStateRequest'}

INSTANCE = {
    'current_request': 4872,
    'pending_head': 4880,
    'pending_tail': 4888,
    'vsync_clients': 4992,
    'vsync_object': 5064,
    'width': 5208,
    'height': 5212,
    'state_requested': 5236,
    'state_powered': 5240,
}
REQUEST = {
    'surfaces': 2184,
    'masks': 792,
    'rect0': 17,
    'rect1': 81,
    'options': 804,
    'dims': 816,
    'node_next': 2408,
    'node_previous': 2416,
}
INSTANCE_BYTES = 0x1660


def va(text):
    return 0xfffffff000000000 | int(text, 16)


class Image:
    def __init__(self, base, kernelcache):
        sys.path.insert(0, str(base / 'kits/XnuPrelink'))
        from native_prelink import macho, backed_offset, unserialize_xml

        self.macho = macho
        self.backed_offset = backed_offset
        self.blob = kernelcache.read_bytes()
        self.image = macho(self.blob)
        info = next(s for s in self.image['segments'] if s['name'] == '__PRELINK_INFO')
        at = backed_offset(self.image['segments'], info['va'], info['filesize'], len(self.blob))
        entries = {e['CFBundleIdentifier']: e for e in
                   unserialize_xml(self.blob[at:at + info['filesize']])['_PrelinkInfoDictionary']
                   if e.get('CFBundleIdentifier')}
        self.entry = entries[FAMILY]
        self.module = macho(self.blob, backed_offset(
            self.image['segments'], self.entry['_PrelinkExecutableLoadAddr'], 32, len(self.blob)))
        self.segments = {}
        for segment in self.module['segments']:
            if segment['name'] == '__LINKEDIT' or not segment['filesize']:
                continue
            off = backed_offset(self.image['segments'], segment['va'], segment['filesize'], len(self.blob))
            self.segments[segment['name']] = (segment['va'], self.blob[off:off + segment['filesize']])

    def read(self, address, size):
        for sva, data in self.segments.values():
            if sva <= address and address + size <= sva + len(data):
                return data[address - sva:address - sva + size]
        raise KeyError(hex(address))

    def word(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def qword(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]


def check_word(image, address, value, label):
    actual = image.word(address)
    if actual != value:
        raise SystemExit('%s: %s is %08x, expected %08x' % (label, hex(address), actual, value))


def find_vtable(image):
    text = [s for s in image.module['segments'] if s['name'] in ('__TEXT_EXEC', '__TEXT')]
    lo = min(s['va'] for s in text)
    hi = max(s['va'] + s['size'] for s in text)
    found = []
    for name, (sva, data) in image.segments.items():
        for start in range(0, len(data) - 16, 8):
            if data[start:start + 16] != bytes(16):
                continue
            values, at = [], start + 16
            while at + 8 <= len(data):
                value = struct.unpack_from('<Q', data, at)[0]
                if not value:
                    break
                values.append(value)
                at += 8
            if len(values) < 300 or data[at:at + 24] != bytes(24):
                continue
            if not lo <= values[0] < hi:
                continue
            outside = [i for i, value in enumerate(values) if not lo <= value < hi]
            above = [i for i in outside if i >= 168]
            if {values[i] for i in above}.__len__() != 1:
                continue
            found.append((len(values), sva + start + 16, values))
    if not found:
        raise SystemExit('no Legacy vtable shape found')
    slots, vptr, values = max(found)
    return vptr, slots, values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT.parents[1] / 'UniXNU')
    parser.add_argument('--kernelcache', type=Path,
                        default=ROOT.parents[1] / 'UniXNU/out/ipsw/20H392/kernelcache.decompressed')
    parser.add_argument('--out', type=Path, default=ROOT / 'package')
    args = parser.parse_args()

    image = Image(args.base, args.kernelcache)
    vptr, slots, values = find_vtable(image)
    if slots != SLOTS:
        raise SystemExit('slot count %d, expected %d' % (slots, SLOTS))
    abstract = [i for i, value in enumerate(values) if value == values[PURE[0]]]
    if abstract != PURE:
        raise SystemExit('abstract slots %s, expected %s' % (abstract, PURE))
    if image.read(vptr + slots * 8, 24) != bytes(24):
        raise SystemExit('vtable run is not followed by 24 zero bytes')

    # Instance size and class identity from the OSMetaClass constructor that installs this vtable.
    check_word(image, va('5c0bbc8'), 0x90008f28, 'vtable adrp')
    check_word(image, va('5c0bbcc'), 0x91234108, 'vtable add')
    check_word(image, va('5c0bbd0'), 0x91004108, 'vptr add')
    check_word(image, va('5c0bca4'), 0x5282cc03, 'metadata size movz')
    check_word(image, va('5c0bc98'), 0x91192821, 'metadata name add')

    # The seven limited slots and their identical addresses in the vtable.
    for slot, (_, address) in ROLES.items():
        if values[slot] != va(address):
            raise SystemExit('slot %d is %s, expected %s' % (slot, hex(values[slot]), address))

    # Slot semantics anchors.
    check_word(image, va('5c0d5d8'), 0xf9444908, 'start() calls startHardware')
    check_word(image, va('5c0c22c'), 0xf9445108, 'kickSwapQueue call offset')
    check_word(image, va('5c165b4'), 0xf9446908, 'validateSwap call offset')
    check_word(image, va('5c1acf8'), 0x52800028, 'completeCurrentSwap passes true')
    check_word(image, va('5c1acfc'), 0x12000101, 'completeCurrentSwap bool arg')
    check_word(image, va('5c10240'), 0xf9450508, 'completion dispatch slot 321')
    check_word(image, va('5c1ad18'), 0xf90003e1, 'validateSwap saves request')
    check_word(image, va('5c1ad1c'), 0x52800008, 'validateSwap default false')
    check_word(image, va('5c234c0'), 0xd2888888, 'refresh 2^32/60 low')
    check_word(image, va('5c234c4'), 0xf2a08888, 'refresh 2^32/60 high')
    check_word(image, va('5c247dc'), 0xb9545908, 'dimensions width field')
    check_word(image, va('5c247e4'), 0xb9000128, 'dimensions width store')
    check_word(image, va('5c24804'), 0xb9545d08, 'dimensions height field')
    check_word(image, va('5c2480c'), 0xb9000128, 'dimensions height store')
    check_word(image, va('5c1c20c'), 0x39404108, 'state changed byte 16')
    check_word(image, va('5c1c240'), 0xb9547529, 'state requested read')
    check_word(image, va('5c1c260'), 0xb9147528, 'state requested store')
    check_word(image, va('5c1c294'), 0xb9547929, 'state powered read')

    # Instance fields.
    for address, expected, label in (
        ('5c0fe9c', 0xf9498508, 'current request read'),
        ('5c0fed0', 0xf9098528, 'current request store from pending head'),
        ('5c0feb4', 0xf9498908, 'pending head read'),
        ('5c0fecc', 0xf9498928, 'pending head read for current request'),
        ('5c0fe50', 0xf9498d28, 'pending tail read'),
        ('5c0fe70', 0xf9098d28, 'pending tail store'),
        ('5c10060', 0xf949c108, 'vsync clients read'),
        ('5c1b948', 0xf949c108, 'vsync clients read 2'),
        ('5c0c5e8', 0xf909e51f, 'vsync object init zero'),
        ('5c196ec', 0xf949e500, 'vsync object release'),
        ('5c19700', 0xf909e51f, 'vsync object clear'),
    ):
        check_word(image, va(address), expected, label)

    # Request fields.
    for address, expected, label in (
        ('5c161f0', 0x91222108, 'surfaces add'),
        ('5c0eed4', 0x91222108, 'surfaces add 2'),
        ('5c14c18', 0xb9031949, 'masks store'),
        ('5c14ca8', 0xb9032148, 'masks third store'),
        ('5c167b8', 0xb9431908, 'masks read'),
        ('5c167c4', 0xb9431d08, 'masks second read'),
        ('5c16264', 0x9100450a, 'rect0 add'),
        ('5c16284', 0x9101450a, 'rect1 add'),
        ('5c14cb8', 0xb9032548, 'options store'),
        ('5c167d0', 0xb9432d08, 'options read'),
        ('5c14cd4', 0xb9033148, 'dims store 0'),
        ('5c14ce0', 0xb9033548, 'dims store 4'),
    ):
        check_word(image, va(address), expected, label)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    named = {slot: text for slot, (text, _) in ROLES.items()}
    virtuals = []
    for slot in range(168, SLOTS):
        if slot == 321:
            virtuals.append('    virtual IOReturn collectCompletionReports(uint32_t, void *, uint32_t *, uint32_t) = 0;')
        elif slot in named:
            virtuals.append('    virtual ' + named[slot] + ';')
        elif slot in PURE:
            virtuals.append('    virtual __attribute__((noreturn)) void opaque%d() = 0;' % slot)
        else:
            virtuals.append('    virtual void opaque%d();' % slot)
    if len(virtuals) != SLOTS - 168:
        raise SystemExit('virtual count %d' % len(virtuals))

    leaves = ' '.join('LEAF(%d)' % i for i in PURE if i != 321)
    header = '''// SPDX-License-Identifier: BSD-2-Clause-Patent
// nuwa (iOS 16.7.16 / 20H392) declarations for the instruction-qualified
// IOMobileFramebufferLegacy ABI. Generated by scripts/derive-nuwa-display-abi.py;
// do not edit. Not the unrelated Mobile prototype.
#pragma once
#include <IOKit/IOService.h>
#include <IOKit/IOUserClient.h>
#include <libkern/libkern.h>

// Swap request layout. Fields used by the original path are at the enum below; the
// two queue links are the only members with a qualified offset. The total allocation
// size is not anchored, so it is not asserted.
struct OriginalLegacySwapRequest {
    unsigned char bytes[%(node_next)d];
    void *next;                 // +%(node_next)d
    void *previous;             // +%(node_previous)d
};
struct OriginalLegacyStateRequest {
    uint32_t skipRequested, requested, skipPowered, powered;
    uint8_t changed;
    uint8_t padding[3];         // tail padding of the 20-byte original record
};
static_assert(__builtin_offsetof(OriginalLegacyStateRequest, powered) == 12, "state word");
static_assert(__builtin_offsetof(OriginalLegacyStateRequest, changed) == 16, "state flag");

class IOMobileFramebufferLegacy : public IOService {
    OSDeclareAbstractStructors(IOMobileFramebufferLegacy)
    unsigned char privateABI[%(instance_bytes)d - sizeof(IOService)];
public:
    void installBootDimensions(uint32_t width, uint32_t height) {
        memcpy(reinterpret_cast<char *>(this) + %(width)d, &width, sizeof(width));
        memcpy(reinterpret_cast<char *>(this) + %(height)d, &height, sizeof(height));
    }
    const OriginalLegacySwapRequest *pendingSwapRequest() const {
        const OriginalLegacySwapRequest *head;
        memcpy(&head, reinterpret_cast<const char *>(this) + %(pending_head)d, sizeof(head));
        return head;
    }
    // Tail-queue representation read from this image's enqueue/remove/completion bodies:
    // the head field holds the first request base, the first node's previous link points at
    // the head field's own address, and each request carries next/previous at +%(node_next)d/+%(node_previous)d.
    bool activateOnlyPendingSwap(const OriginalLegacySwapRequest *request) {
        if (!request) return false;
        char *self = reinterpret_cast<char *>(this);
        const char *bytes = reinterpret_cast<const char *>(request);
        const void *head, *current, *tail, *next, *previous;
        memcpy(&head, self + %(pending_head)d, 8);
        memcpy(&current, self + %(current_request)d, 8);
        memcpy(&tail, self + %(pending_tail)d, 8);
        memcpy(&next, bytes + %(node_next)d, 8);
        memcpy(&previous, bytes + %(node_previous)d, 8);
        if (head != request || current || previous != self + %(pending_head)d ||
            (!next && tail != bytes + %(node_next)d)) return false;
        if (next) {
            const void *newPrevious = self + %(pending_head)d;
            memcpy(const_cast<char *>(static_cast<const char *>(next)) + %(node_previous)d, &newPrevious, 8);
        } else {
            const void *newTail = self + %(pending_head)d;
            memcpy(self + %(pending_tail)d, &newTail, 8);
        }
        memcpy(self + %(pending_head)d, &next, 8);
        memcpy(self + %(current_request)d, &request, 8);
        return true;
    }
    void free() override;
    bool init(OSDictionary *properties = nullptr) override;
    IOReturn setProperties(OSObject *) override;
    void systemWillShutdown(IOOptionBits) override;
    IOService *probe(IOService *, SInt32 *) override;
    bool start(IOService *) override;
    void stop(IOService *) override;
    IOWorkLoop *getWorkLoop() const override;
    IOReturn newUserClient(task_t, void *, UInt32, IOUserClient **) override;
    IOReturn setPowerState(unsigned long, IOService *) override;
%(virtuals)s
};
static_assert(sizeof(IOMobileFramebufferLegacy) == %(instance_bytes)d, "qualified metadata instance size");
enum : unsigned {
    kRequestSurfaces = %(surfaces)d, kRequestMasks = %(masks)d, kRequestRect0 = %(rect0)d,
    kRequestRect1 = %(rect1)d, kRequestOptions = %(options)d, kRequestDims = %(dims)d,
    kRequestNodeNext = %(node_next)d, kRequestNodePrevious = %(node_previous)d,
    kInstanceCurrentRequest = %(current_request)d, kInstancePendingHead = %(pending_head)d,
    kInstancePendingTail = %(pending_tail)d, kInstanceVsyncClients = %(vsync_clients)d,
    kInstanceVsyncObject = %(vsync_object)d, kInstanceWidth = %(width)d, kInstanceHeight = %(height)d,
    kInstanceStateRequested = %(state_requested)d, kInstanceStatePowered = %(state_powered)d,
    kLegacyVsyncClients = %(vsync_clients)d
};
#define NATIVE_LEGACY_LEAVES(LEAF) %(leaves)s
''' % dict(
        instance_bytes=INSTANCE_BYTES,
        virtuals='\n'.join(virtuals),
        leaves=leaves,
        surfaces=REQUEST['surfaces'],
        masks=REQUEST['masks'],
        rect0=REQUEST['rect0'],
        rect1=REQUEST['rect1'],
        options=REQUEST['options'],
        dims=REQUEST['dims'],
        node_next=REQUEST['node_next'],
        node_previous=REQUEST['node_previous'],
        current_request=INSTANCE['current_request'],
        pending_head=INSTANCE['pending_head'],
        pending_tail=INSTANCE['pending_tail'],
        vsync_clients=INSTANCE['vsync_clients'],
        vsync_object=INSTANCE['vsync_object'],
        width=INSTANCE['width'],
        height=INSTANCE['height'],
        state_requested=INSTANCE['state_requested'],
        state_powered=INSTANCE['state_powered'],
    )
    (out / 'OriginalLegacyFramebufferABI.h').write_text(header)

    bindings = [('__ZTV25IOMobileFramebufferLegacy', vptr - 16)]
    for slot in sorted(ROLES):
        bindings.append((MANGLED[SLOT_SYMBOL[slot]], values[slot]))
    lines = ['// SPDX-License-Identifier: BSD-2-Clause-Patent',
             '// Generated by scripts/derive-nuwa-display-abi.py from the 20H392 donor kernelcache.',
             '// Absolute bindings for the original Legacy entry points that the port calls directly.']
    for symbol, address in bindings:
        lines += ['.globl ' + symbol, '.set ' + symbol + ', 0x%x' % address]
    (out / 'original-bindings.S').write_text('\n'.join(lines) + '\n')

    summary = dict(
        kernelcache=dict(bytes=len(image.blob), sha256=hashlib.sha256(image.blob).hexdigest()),
        family=dict(load=hex(image.entry['_PrelinkExecutableLoadAddr']),
                    executable_size=image.entry['_PrelinkExecutableSize']),
        vtable=dict(vptr=hex(vptr), slots=slots,
                    method_extent=[hex(min(v for i, v in enumerate(values[168:], 168) if i not in PURE)),
                                   hex(max(v for i, v in enumerate(values[168:], 168) if i not in PURE))],
                    abstract=abstract, pure_target=hex(values[abstract[0]])),
        instance_bytes=INSTANCE_BYTES,
        slots={**{str(slot): dict(address=hex(values[slot]), prototype=text,
                                  abstract=slot in PURE) for slot, (text, _) in ROLES.items()},
               '321': dict(address=hex(values[321]), prototype='IOReturn collectCompletionReports(uint32_t, void *, uint32_t *, uint32_t)', abstract=True)},
        instance=INSTANCE,
        request=REQUEST,
        outputs=[str(out / 'OriginalLegacyFramebufferABI.h'), str(out / 'original-bindings.S')],
    )
    (out / 'nuwa-display-abi.json').write_text(json.dumps(summary, indent=1) + '\n')
    print('vtable', hex(vptr), slots, 'abstract', abstract)
    print('instance', INSTANCE_BYTES, 'roles', sorted(ROLES))
    print('wrote', out / 'OriginalLegacyFramebufferABI.h', out / 'original-bindings.S')
    return 0


if __name__ == '__main__':
    sys.exit(main())
