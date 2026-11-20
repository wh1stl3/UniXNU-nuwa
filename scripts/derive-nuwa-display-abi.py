#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Derive the nuwa (iOS 16.7.16 / 20H392) IOMobileFramebufferLegacy ABI from our donor kernelcache.

Read-only inputs: the 20H392 kernelcache and the base checkout's XnuPrelink Mach-O parser.
Outputs: package/OriginalLegacyFramebufferABI.h, package/original-bindings.S and a JSON summary.

The ABI below is anchored to instructions in 20H392 donor modules; the checks assert the
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
SURFACE = 'com.apple.iokit.IOSurface'
DONOR_DISPLAY = 'com.apple.driver.AppleMobileDispH10P'
DONOR_SHA256 = '2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221'
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

# Override-only roles used by NativeLegacyDisplay.cpp, not direct-call bindings.
CONSUMER_ROLES = {
    184: ('bool isMainDisplay()', '5c12264'),
    188: ('IOReturn getDotPitch(uint32_t *)', '5c1d128'),
}
ABSTRACT_ROLES = {
    212: 'IOReturn supportedFrameInfo(uint32_t, uint32_t *, char *)',
    321: 'IOReturn collectCompletionReports(uint32_t, void *, uint32_t *, uint32_t)',
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
    def __init__(self, base, kernelcache, family=FAMILY):
        location = str(base / 'kits/XnuPrelink')
        if location not in sys.path:
            sys.path.insert(0, location)
        sys.dont_write_bytecode = True
        from native_prelink import macho, backed_offset, unserialize_xml

        self.macho = macho
        self.backed_offset = backed_offset
        self.blob = kernelcache.read_bytes()
        if hashlib.sha256(self.blob).hexdigest() != DONOR_SHA256:
            raise SystemExit('expected the pinned 20H392 donor kernelcache')
        self.image = macho(self.blob)
        info = next(s for s in self.image['segments'] if s['name'] == '__PRELINK_INFO')
        at = backed_offset(self.image['segments'], info['va'], info['filesize'], len(self.blob))
        entries = {e['CFBundleIdentifier']: e for e in
                   unserialize_xml(self.blob[at:at + info['filesize']])['_PrelinkInfoDictionary']
                   if e.get('CFBundleIdentifier')}
        self.entry = entries[family]
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


def check_words(image, address, words, label):
    for index, word in enumerate(words):
        check_word(image, va(address) + index * 4, word, label)


def check_string(image, address, text):
    if image.read(va(address), len(text) + 1) != text.encode() + b'\0':
        raise SystemExit(f'{address}: expected donor string {text!r}')


def derive_surfaces(family, surface):
    # Each family stub's pointer must land on the complete IOSurface leaf.
    # Check the unsigned load itself: a W load zero-extends even for the
    # four consumer declarations with uint64_t return types.
    result = {}
    for name, stub, got_offset, target, field, width in (
        ('descriptor', '5c2737c', 0x320, '5a4e724', 56, 64),
        ('width',      '5c2740c', 0x380, '5a4e7f4', 144, 32),
        ('height',     '5c27418', 0x388, '5a4e7fc', 148, 32),
        ('stride',     '5c272f8', 0x2c8, '5a4e80c', 152, 32),
        ('allocation', '5c27298', 0x288, '5a4e834', 172, 32),
        ('format',     '5c27304', 0x2d0, '5a4e7e4', 164, 32),
        ('planes',     '5c272d4', 0x2b0, '5a4e82c', 176, 32),
    ):
        check_words(family, stub, (0x90008e30, 0xf9400210 | (got_offset // 8 << 10),
                                   0xd61f0200), name + ' family stub')
        got = va('6deb000') + got_offset
        if family.qword(got) != va(target):
            raise SystemExit(f'{name}: donor stub target changed')
        scale = width // 8
        load = (0xf9400000 if width == 64 else 0xb9400000) | (field // scale << 10)
        check_words(surface, target, (load, 0xd65f03c0), name + ' IOSurface getter')
        result[name] = dict(stub=hex(va(stub)), got=hex(got), target=hex(va(target)),
                            offset=field, load_bits=width,
                            ownership='borrowed' if name == 'descriptor' else 'value')

    # Independent uses distinguish adjacent getters. Descriptor is read
    # straight from the request's surface, with no retain in the leaf.
    check_words(family, '5c0f050', (0x91222108, 0xb89b43a9, 0xf8697900, 0x940060c8,
                                    0xf9400008, 0xf9407108, 0x52800001, 0xd63f0100),
                'surface descriptor consumed as an object in swap path')
    check_words(family, '5c159c4', (0x91222108, 0xb89983a9, 0xf8697900, 0x9400468f,
                                    0xb94037e8, 0x6b000108), 'width coverage')
    check_words(family, '5c15b0c', (0x91222108, 0xb89983a9, 0xf8697900, 0x94004640,
                                    0xb94033e8, 0x6b000108), 'height coverage')
    check_words(family, '5c15a54', (0xb0ff9a80, 0x911cb800), 'width diagnostic')
    check_words(family, '5c15b9c', (0xb0ff9a80, 0x911e4400), 'height diagnostic')
    check_string(family, '4f6672e', "%s Buffer width (%d) doesn't cover read region (x = %d, w = %d)\n")
    check_string(family, '4f66791', "%s Buffer height (%d) doesn't cover read region(y = %d, h = %d)\n")
    check_words(family, '5c1d6cc', (0x9400270b, 0xaa0003e2, 0xf9400be0,
                                    0xd0ff9a41, 0x91069421), 'stride property')
    check_string(family, '4f671a5', 'src_stride')
    check_words(family, '5c1d7dc', (0x940026ca, 0xb94007e3, 0xaa0003e2, 0xf94007e0,
                                    0xd0ff9a41, 0x9107c821), 'format property')
    check_string(family, '4f671f2', 'format')
    check_string(surface, '4ed0aad', 'IOSurfaceAllocSize')
    check_words(surface, '5a4b2cc', (0xb0ffa421, 0x912ab421, 0xaa1403e0, 0xd63f0100,
                                     0xaa1503e1, 0x9400707d, 0xb4000180, 0xf9400008,
                                     0xf9405908, 0xd63f0100, 0xd360fc08, 0xb5ffcd68,
                                     0x1400002e), 'checked allocation size property')
    check_words(surface, '5a4b3b4', (0xb900ae60,), 'allocation size stored at +172')
    check_string(surface, '4ed0ad6', 'IOSurfacePlaneInfo')
    check_words(surface, '5a47894', (0xb0ffa441, 0x912b5821, 0xaa1403e0, 0xd63f0100,
                                     0xd00099e8, 0xf9412d08, 0xf9400117, 0xaa1703e1,
                                     0x94007f08, 0xb4000420, 0xaa0003f9, 0xf9400008,
                                     0xf9404908, 0xd63f0100, 0xb900b260),
                'plane array count stored at +176')
    return result


def inspect_unbound_timing(family, display):
    # Evidence only: neither entry is emitted as a callable binding.
    check_words(display, '5ccfc5c', (0xf94e1660, 0xf9400008, 0xf9402108, 0xd63f0100,
                                     0x36000080, 0xaa1303e0, 0x94004677),
                'hardware boot calls refresh only after readiness test')
    check_words(display, '5ce1650', (0xd00088d0, 0xf9430e10, 0xd61f0200),
                'hardware boot refresh stub')
    if display.qword(va('6dfb618')) != va('5c23610'):
        raise SystemExit('refresh properties donor target changed')
    check_string(display, '4f97c81', 'bool UnifiedPipeline::start_hardware_boot()')
    check_words(family, '5c2360c', (0xd65f03c0, 0xd10203ff, 0xa9077bfd,
                                    0x9101c3fd, 0xf81f03a0),
                'refresh properties method entry')
    check_words(family, '5c236a8', (0xf9400008, 0xf9447d08, 0x9100a3e1, 0x12000122,
                                    0xd63f0100, 0x370001c0), 'refresh slot 287')
    check_words(family, '5c237b0', (0x90ff9a21, 0x91354821, 0xd63f0100),
                'refresh publishes IOMFBDisplayRefresh')
    check_string(family, '4f67d52', 'IOMFBDisplayRefresh')
    check_word(family, va('5c237e4'), 0x12000100, 'refresh returns bool')
    check_words(family, '5c0dc28', (0xf94b1401, 0xf94b1802, 0xf94b1c03, 0x94003701),
                'donor VBL send from recorded timestamps')
    check_words(family, '5c1b844', (0xf81f83a0, 0xf81f03a1, 0xf81e83a2, 0xf81e03a3),
                'VBL sender saves four 64-bit arguments')
    check_word(family, va('5c1b948'), 0xf949c108, 'VBL sender loads client queue')
    check_words(family, '5c1b9b0', (0xf85d83a8, 0xf9400108, 0xf81d83a8, 0x17ffffe6),
                'VBL sender walks next links directly')
    check_string(family, '4f66ddf', 'dropped VBL message\n')
    return dict(refresh=dict(target=hex(va('5c23610')), caller=hex(va('5ccfc74')),
                             bound=False),
                vsync=dict(target=hex(va('5c1b838')), caller=hex(va('5c0dc34')),
                           bound=False))


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
    surfaces = derive_surfaces(image, Image(args.base, args.kernelcache, SURFACE))
    timing = inspect_unbound_timing(image, Image(args.base, args.kernelcache, DONOR_DISPLAY))
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

    # Named concrete slots must retain their original addresses in the vtable.
    named_roles = {**ROLES, **CONSUMER_ROLES}
    for slot, (_, address) in named_roles.items():
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

    # Main-display scalar query (selector 18) and dot-pitch property getter.
    if image.read(va('6decd08'), 24) != struct.pack('<QIIII', va('5c00658'), 0, 0, 1, 0):
        raise SystemExit('selector 18 scalar-query dispatch entry changed')
    check_word(image, va('5bff47c'), 0xb0008f69, 'externalMethod dispatch table page')
    check_word(image, va('5bff480'), 0x912d6129, 'externalMethod dispatch table offset')
    check_word(image, va('5c00688'), 0x97fff79f, 'selector 18 calls scalar query')
    check_word(image, va('5bfe52c'), 0xf942e108, 'scalar query dispatch slot 184')
    check_word(image, va('5bfe534'), 0x360000c0, 'scalar query reads boolean')
    check_word(image, va('5c12274'), 0xd282a449, 'main display flag offset')
    check_word(image, va('5c12294'), 0xd282a569, 'main display exclusion flag offset')
    check_word(image, va('5c122b0'), 0x12000100, 'main display returns boolean')
    if image.read(va('4f6718d'), len(b'dot-pitch\0')) != b'dot-pitch\0':
        raise SystemExit('dot-pitch property string changed')
    check_word(image, va('5c1d184'), 0xd0ff9a41, 'dot-pitch property page')
    check_word(image, va('5c1d188'), 0x91063421, 'dot-pitch property offset')
    check_word(image, va('5c1d248'), 0xf85f03a9, 'dot-pitch output pointer')
    check_word(image, va('5c1d24c'), 0xb9000128, 'dot-pitch uint32_t output')
    check_word(image, va('5c1d250'), 0xb85ec3a0, 'dot-pitch IOReturn')
    check_word(image, va('5bfe818'), 0xf942f108, 'dot-pitch dispatch slot 188')

    # Selector 74 exposes one scalar in, one scalar out and a 64-byte key out.
    # Pin both call sequences, including the complete wrapper up to blr:
    # it passes the local count and key in x2/x3, without an x4 argument.
    if image.read(va('6decb58') + 74 * 24, 24) != struct.pack(
            '<QIIII', va('5c00c04'), 1, 0, 1, 64):
        raise SystemExit('selector 74 frame-info dispatch entry changed')
    for start, words, label in (
        ('5c00c20', (0xf94007e8, 0xf9401108, 0xf9400108, 0xaa0803e1,
                     0xf94007e8, 0xf9402502, 0xf94007e8, 0xf9402d03,
                     0x97fff7f5), 'selector 74 handler forwards to frame-info wrapper'),
        ('5bfec14', (0xd10103ff, 0xa9037bfd, 0x9100c3fd, 0xf81f83a0,
                     0xb81f43a1, 0xf9000fe2, 0xf9000be3, 0xf85f83a8,
                     0x910033e2, 0x3201f3e9, 0xb9000fe9, 0xb9000fff,
                     0xb9000be9, 0xf9406d00, 0xb85f43a1, 0xf9400be3,
                     0xf9400008, 0xf9435108, 0xd63f0100, 0xb9000be0,
                     0xb9400fe8, 0xf9400fe9, 0xf9000128,
                     0xb9400be0), 'frame-info wrapper slot 212 and outputs'),
        ('5c10244', (0xd2800003, 0xaa0303e2, 0x52800004,
                     0xd63f0100), 'completion reports invocation'),
        ('5c11980', (0xf9452508, 0xd63f0100), 'timeout timing dispatch slot 329'),
        ('5c119dc', (0x9240016b, 0xf900192b), 'TimingEnable log bit'),
        ('5c11a74', (0xf9452908, 0xd63f0100), 'donor queue dispatch slot 330'),
    ):
        for index, word in enumerate(words):
            check_word(image, va(start) + index * 4, word, label)
    if values[330] != va('5c0fbe8'):
        raise SystemExit('slot 330 donor queue target changed')

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

    named = {slot: text for slot, (text, _) in named_roles.items()} | ABSTRACT_ROLES
    virtuals = []
    for slot in range(168, SLOTS):
        if slot in named:
            virtuals.append('    virtual ' + named[slot] + (' = 0;' if slot in PURE else ';'))
        elif slot in PURE:
            virtuals.append('    virtual __attribute__((noreturn)) void opaque%d() = 0;' % slot)
        else:
            virtuals.append('    virtual void opaque%d();' % slot)
    if len(virtuals) != SLOTS - 168:
        raise SystemExit('virtual count %d' % len(virtuals))

    leaves = ' '.join('LEAF(%d)' % i for i in PURE if i not in ABSTRACT_ROLES)
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
    lines += ['', '// Qualified IOSurface getters. Descriptor is borrowed; W loads zero-extend.',
              '.text', '.p2align 2']
    for name, info in surfaces.items():
        symbol = '_native_legacy_surface_' + name
        register = 'x0' if info['load_bits'] == 64 else 'w0'
        lines += ['.globl ' + symbol, symbol + ':',
                  f"    ldr {register}, [x0, #{info['offset']}]", '    ret']
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
        slots={str(slot): dict(address=hex(values[slot]), prototype=text, abstract=slot in PURE)
               for slot, text in sorted(named.items())},
        instance=INSTANCE,
        request=REQUEST,
        surfaces=surfaces,
        unbound_timing=timing,
        outputs=['OriginalLegacyFramebufferABI.h', 'original-bindings.S'],
    )
    (out / 'nuwa-display-abi.json').write_text(json.dumps(summary, indent=1) + '\n')
    print('vtable', hex(vptr), slots, 'abstract', abstract)
    print('instance', INSTANCE_BYTES, 'roles', sorted(named_roles))
    print('wrote', out / 'OriginalLegacyFramebufferABI.h', out / 'original-bindings.S')
    return 0


if __name__ == '__main__':
    sys.exit(main())
