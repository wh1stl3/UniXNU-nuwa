# nuwa 20H392 HID ABI: donor extraction

**self-checked, host only**; no independent verifier, deep review, device,
image build, SPI or probe implementation changes. "Verified" below means
the pinned donor's bytes/tables and the stated synthetic host checks, not
runtime or hardware verification. This is an evidence header, not a qualified
interface for linking or writing a vtable.

## Inputs and method

* Donor: iPhone10,3, iOS 16.7.16 / 20H392,
  `D:/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed`,
  50,937,856 bytes, SHA-256
  `2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`.
  Its original `com.apple.iokit.IOHIDFamily` has metadata version `2.0.0`,
  load VA `0xfffffff004e2e6c0`; `IOHIDEventDriver` personality is codeless.
* `UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241` and its
  `XnuPrelink@f1d80d37528a33e24643583787123c652b70a268` supply the local
  Mach-O parser; `scripts/derive-nuwa-hid-abi.py` and
  `scripts/derive-nuwa-display-abi.py` supply the existing donor-pinned reader
  and prior 207-slot `IOHIDDevice` checks. No generated Apple binary is saved.
* Upstream reuse target:
  [`UniXNU/ShengHidInput@71a40e76daeae1bb4127546f96ffa7339c7a06ff`](https://github.com/UniXNU/ShengHidInput/tree/71a40e76daeae1bb4127546f96ffa7339c7a06ff),
  BSD-2-Clause-Patent. Its descriptor is a source reference, **not** a source
  of donor ABI offsets. Apple source
  [`apple-oss-distributions/IOHIDFamily@777ccd9698845aadf711e32d843c8c9b777431d9`](https://github.com/apple-oss-distributions/IOHIDFamily/tree/777ccd9698845aadf711e32d843c8c9b777431d9)
  (APSL-2.0), `IOHIDEventDriver.cpp`, `IOHIDEventService.cpp` and
  `IOHIDEvent.cpp` is used to name matching code shapes, not to assign
  offsets. It is not asserted to be the 20H392 build source.
* `git ls-remote` read-only stage check: device origin HEAD
  `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`; UniXNU origin HEAD
  `fdf81eaa832ce5c850d3c53c698407aa722a4653`; ShengHidInput origin HEAD
  `114061452959a547aaa08f9ca5aa54033394ca2f`. No pin was changed.

The donor's outer symbol table does **not** export these private kext C++
methods. Class names and vptrs are reconstructed from named metaclass
initializers and independent C2 vptr stores, then the table entries, callers,
field accesses and property string are checked. Thus the labels in the table
are semantic reconstructions, not claims that `llvm-nm` exported them.
Actual exported `IORegistryEntry::setProperty` and `___cxa_pure_virtual` are
looked up by name. All VAs below are unslid donor VAs; an actual prelink may
rebase the original family and must independently bind/check the final image.
`slot` counts from the object vptr, after the two 8-byte vtable header words;
the vptr byte displacement is `slot * 8`.

## Tables and callable path

| Class | Instance vptr | Instance bytes | Function slots | Independent anchors |
| --- | --- | ---: | ---: | --- |
| `IOHIDDevice` | `0xfffffff006cbe2d0` | `0xd0` | 207 | Existing donor derive: class name, C2, metaclass initializer, parent overrides, pure slot and trailing zeros. |
| `IOHIDEventService` | `0xfffffff006cbfb20` | `0xc8` | 218 | Name initializer `0xfffffff00573d468`, C2 vptr store `0xfffffff005738530`. |
| `IOHIDEventDriver` | `0xfffffff006cc0770` | `0x108` | 219 | Name initializer `0xfffffff005748388`, C2 `0xfffffff00573e008` calls the service C2 and installs its own vptr. |
| `IOHIDEvent` | `0xfffffff006cc1018` | `0x50` | 37 | Name initializer `0xfffffff00574ecc8`, C2 vptr store `0xfffffff005748434`. |

Sizes/table boundaries and target addresses are **verified static** by the
script below. The function role is also checked against calls and, where
necessary, named using the Apple source above; exact C++ prototypes and final
linkage remain inferred/UNKNOWN.

| Method or entry | Slot / bytes | Donor target VA | Why this label |
| --- | --- | --- | --- |
| `IOHIDDevice::newReportDescriptor` | 180 / `0x5a0` | `0xfffffff00770ace4` | Exported `___cxa_pure_virtual`; device `start` calls this slot with an output pointer and checks status. |
| `IOHIDDevice::handleReport` | 181 / `0x5a8` | `0xfffffff00572a730` | Entry forwards timestamp, report, type and options at `0xfffffff00572a77c` through slot 197; matches the source entry's shape. |
| `IOHIDDevice` timestamped report path | 197 / `0x628` | `0xfffffff00572b83c` | Direct dynamic call from the preceding entry; exact declaration remains UNKNOWN. |
| `IOHIDDevice::setProperty(OSSymbol const *, OSObject *)` | 23 / `0xb8` | `0xfffffff00572a53c` | Device override of the exported base overload, same table/slot. Exact override body contract remains unqualified. |
| `IORegistryEntry::setProperty(char const *, bool)` on device/service/driver | 27 / `0xd8` | `0xfffffff00773dba8` | Actual root export `__ZN15IORegistryEntry11setPropertyEPKcb`; all three tables point here. This is the overload used for boolean properties, not `setProperties`. |
| `IOHIDEventDriver::setProperties(OSObject *)` | 44 / `0x160` | `0xfffffff005742d10` | Driver overrides the service slot; source-matched method shape. It is **not** the singular `setProperty` overload. |
| `IOHIDEventDriver::handleInterruptReport` | 218 / `0x6d0` | `0xfffffff0057444e8` | Driver's extra slot; input-report handler calls the digitizer path at `0xfffffff0057445d4`. |
| `IOHIDEventService::dispatchEvent` | 198 / `0x630` | `0xfffffff00573bdcc` | Collection calls slot 198 with `(self,event,0)` at `0xfffffff005746f1c`. |
| `IOHIDEventDriver::dispatchEvent` | inherited slot 198 / `0x630` | `0xfffffff005747ff8` | Override takes the event/options, appends children when present, then tail-calls the base service's slot 198 at `0xfffffff0057480f4`. Do **not** bind the service address as the driver's override. |
| `IOHIDEvent::appendChild` | 15 / `0x78` | `0xfffffff00574a158` | Collection call `0xfffffff005746c9c`; body reads and creates the child array at object `+0x18`. |
| `IOHIDEvent::getType` | 18 / `0x90` | `0xfffffff00574a208` | Loads `[self+0x10]`, then data `+4`. |
| `IOHIDEvent::{getIntegerValue,setIntegerValue,getFixedValue}` | 23/24/25, `0xb8/0xc0/0xc8` | `0xfffffff00574a230`, `0xfffffff00574c09c`, `0xfffffff00574b620` | Distinct collection-path calls: `0xfffffff005746b18`, `0xfffffff005746af4`, `0xfffffff005746b3c`; getter paths executed on synthetic data below. |

The singular `setProperty(OSSymbol const *, OSObject *)` driver/service slot
23 points to exported `__ZN15IORegistryEntry11setPropertyEPK8OSSymbolP8OSObject`
at `0xfffffff00773d890`; it is not the device's overriding target. No
`IOHIDEventDriver::handleReport` override is invented: this reuse path calls
`IOHIDDevice::handleReport`, then reaches the event driver's interrupt-report
callback.

## Collection and digitizer data

1. At `0xfffffff005741c68..0xfffffff005741c8c`, the driver searches the
   service plane for the actual donor string `DigitizerCollectionDispatch`
   (`0xfffffff004e308ec`). The GOT at `0xfffffff006cbaf80` resolves to the
   exported `_kOSBooleanTrue`. On equality, `0xfffffff005741cb0` writes 1 to
   `[[driver+0x100]+0x69]`; other branches also set that flag, so it is not
   exclusively caused by the property.
2. The report handler at `0xfffffff0057453dc` tests that flag at
   `0xfffffff005745408` and branches to the collection routine
   `0xfffffff005746944` if nonzero. That routine builds a digitizer event by
   calling `0xfffffff00574969c`, obtains individual transducer events, calls
   `appendChild`, and dispatches the collection through driver slot 198.
   Method labels are source-matched inference; these branch, constructor,
   child and dispatch **instructions are verified static**.
3. The `IOHIDEvent` instance contains a pointer to event data at `+0x10` and
   a child-array pointer at `+0x18`. In the donor constructor at
   `0xfffffff005749738..0xfffffff005749764`, type `11`, options, index, type,
   x/y and pressure-related values are written into that pointed-to data.
   This is not a flat `IOHIDEvent` digitizer struct.

| Field | Base and byte offset | Evidence / confidence |
| --- | --- | --- |
| x / y | data `+0x10` / `+0x14` | Constructor stores and collection calls to `getFixedValue` with `0xb0000`/`0xb0001`; synthetic execution of donor getter reads those exact offsets. **Verified static + synthetic.** |
| index | data `+0x1c` | Constructor store and synthetic `getIntegerValue(0xb0005)` reads this word. **Verified static + synthetic**; mapping report Contact Identifier to this value is **UNKNOWN**. |
| transducer type / identity | data `+0x20` / `+0x24` | Constructor and `getIntegerValue(0xb0004/6)` accesses. **Verified static + synthetic**; identity is not automatically the hardware Contact Identifier. |
| event mask | data `+0x28` | Constructor zero and getter `0xb0007`. **Verified static + synthetic**; edge semantics still unqualified. |
| touch | data `+0x08`, bit 17 | Getter `0xb0009` at `0xfffffff00574abbc` reads the options word and extracts bit 17; synthetic zero/one checks. **Verified static + synthetic.** |
| pressure | data `+0x34` | `getFixedValue(0xb000a)` reads this word at `0xfffffff00574bf38`; constructor stores the paired pressure arguments. **Verified static + synthetic**, role label follows the source-matched constructor; report 3 contains no pressure field. |

The script tests getter machine instructions in Unicorn against a synthetic
`IOHIDEvent` and memory; it does not emulate IOKit matching, a real report,
transducer processing, a live kernel or touch hardware.

## Reuse work and UNKNOWNs

* Replace `UniXNU/scripts/build-sheng-hid-input.py`'s explicit iOS-17-only
  guard, fixed reference candidate/text hash, hard-coded donor vptr/slot
  locations, constructor, start/handleReport bytes, superclass/metaclass and
  import bindings with a **separately qualified 20H392 builder**. Reuse the
  existing `scripts/derive-nuwa-hid-abi.py` reader/stand-in checks, but its
  current generated header deliberately leaves slot 181 opaque and its owned
  override set targets `NuwaHidStandin`, not `NativeHidInput`. In particular,
  `newTransportString`/`newProductString` slot roles 171/173 are **UNKNOWN**:
  their donor bodies are identical null stubs and have not been independently
  identified. Compile the real target TU and audit every actual relocation,
  inherited and owned slot, signature, initializer and final rebinding.
* Upstream `edge` hard-codes driver slot 198, `IOHIDEvent` slots 18/23/24/25,
  children `+24`, a 256-entry arm64 vtable copy, and a separate arm64e
  24A446 PAC-diversity table. The values in this header come from 20H392
  independently; numerical coincidence is not license to reuse the wrapper.
  Here the donor driver has **219**, not 256, function entries. Runtime class
  identity, table replacement, publication/lifetime, synchronization,
  allocation and teardown are **UNKNOWN**. Do not enable or copy the wrapper;
  any future ABI/concurrency modification requires `deep_reviewer`.
* `NativeHidInput.cpp` builds report ID 3 with ten six-byte finger entries,
  count, tip, confidence, ID and little-endian x/y. This is an upstream
  **descriptor layout**, not a kernel object layout; it has no pressure field.
  Its `30480`/`20320` coordinate denominators and edge thresholds are board
  policy, not nuwa measurements. Nuwa coordinate range/orientation, transform,
  producer notification and contact ID lifetime remain **UNKNOWN**.
* The donor property-to-collection branch is present, not proof that this
  descriptor, ten simultaneous contacts, lift reports, native matching or
  backboardd will work. Those require real target-family linkage and a later
  authorized test. The name/offset for every private method's full prototype,
  `getWorkLoop` and remaining NativeHidInput overrides remain **UNKNOWN**
  until compiled against the actual 20H392 TU and call sites. The ID-to-index
  transducer mapping and all physical hardware behavior remain **UNKNOWN**.
* The existing probe's new files and already-modified `porting.toml` were not
  touched. Before an integration commit, the parent must add this document's
  finding/evidence to the input area and rerun the region check against the
  actual integration base.

## Host self-check results

The extraction below ran under WSL Python 3.10 / Unicorn 2.1.4: 21 instruction
anchors, all 52 header declarations, three branch targets and nine synthetic
getter runs matched. A C11 `clang -Wall -Wextra -Werror -fsyntax-only` include
check and `git diff --check` plus `git diff --no-index --check` for each new
file also ran successfully. These are **self-checked**, not independent
verification.

`porting-record.py check --device ... --base origin/main` ran with WSL Python
3.11 and checked 14 areas. The Windows-created worktree has a Windows `.git`
pointer, so Linux Git needs `GIT_DIR` and `GIT_WORK_TREE` as in the command
below. A separate call to `check_changes` with the two actual new paths
confirms that input owns the header and docs are exempt. This only passes
because the probe already changed input findings; that finding does **not**
yet refer to this ABI document. In addition, the CLI's `--base` comparison
uses `base..HEAD`, not untracked worktree files.

```sh
env GIT_DIR=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.git/worktrees/worktree-touch-probe-20261128 \
    GIT_WORK_TREE=/mnt/d/Code/PortingiOS/nuwa/worktree-touch-probe-20261128 \
    /home/wh1stl3/.local/bin/python3.11 -B \
    /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check \
    --device /mnt/d/Code/PortingiOS/nuwa/worktree-touch-probe-20261128 \
    --base origin/main
```

## Reproducible extraction and self-check

From this device worktree in WSL, Python 3 with `unicorn` is required. The
script reads the donor and existing parser only; it writes nothing. Its
getters are run with synthetic data and an artificial return address.

```sh
export BASE=/mnt/d/Code/PortingiOS/UniXNU
sed -n '/^# BEGIN NUWA_HID_ABI_EXTRACT$/,/^# END NUWA_HID_ABI_EXTRACT$/p' \
  docs/nuwa-touch-hid-abi-20261128.md | python3 -B
```

```python
# BEGIN NUWA_HID_ABI_EXTRACT
import importlib.util
import os
import re
import struct
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ
from unicorn.arm64_const import (
    UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X30,
)

base = Path(os.environ.get("BASE", "/mnt/d/Code/PortingiOS/UniXNU"))
donor = base / "out/ipsw/20H392/kernelcache.decompressed"
scripts = Path("scripts")

def load(name):
    spec = importlib.util.spec_from_file_location(name, scripts / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

hid = load("derive-nuwa-hid-abi")
image, device_slots = hid.derive(base, donor)
from native_prelink import exports

root = {name: addr for addr, names in exports(image.blob, image.image).items()
        for name in names}
tables = {
    "device": (0xfffffff006cbe2d0, 207),
    "service": (0xfffffff006cbfb20, 218),
    "driver": (0xfffffff006cc0770, 219),
    "event": (0xfffffff006cc1018, 37),
}
for name, (vptr, count) in tables.items():
    assert image.read(vptr - 16, 16) == bytes(16), name
    assert all(image.qword(vptr + 8 * j) for j in range(count)), name
    assert image.read(vptr + count * 8, 24) == bytes(24), name
    print(f"{name}: vptr={vptr:#x}, slots={count}")
assert tuple(device_slots) == tuple(image.qword(tables["device"][0] + 8 * j)
                                    for j in range(207))

slots = {
    ("device", 23): 0xfffffff00572a53c,
    ("device", 180): 0xfffffff00770ace4,
    ("device", 181): 0xfffffff00572a730,
    ("device", 197): 0xfffffff00572b83c,
    ("service", 198): 0xfffffff00573bdcc,
    ("driver", 44): 0xfffffff005742d10,
    ("driver", 198): 0xfffffff005747ff8,
    ("driver", 218): 0xfffffff0057444e8,
    ("event", 15): 0xfffffff00574a158,
    ("event", 18): 0xfffffff00574a208,
    ("event", 23): 0xfffffff00574a230,
    ("event", 24): 0xfffffff00574c09c,
    ("event", 25): 0xfffffff00574b620,
}
for (name, slot), target in slots.items():
    assert image.qword(tables[name][0] + 8 * slot) == target, (name, slot)
    print(f"{name}[{slot}] +{8*slot:#x} = {target:#x}")
assert root["___cxa_pure_virtual"] == slots["device", 180]
for name in ("device", "service", "driver"):
    assert image.qword(tables[name][0] + 8 * 27) == \
        root["__ZN15IORegistryEntry11setPropertyEPKcb"]
for name in ("service", "driver"):
    assert image.qword(tables[name][0] + 8 * 23) == \
        root["__ZN15IORegistryEntry11setPropertyEPK8OSSymbolP8OSObject"]
assert image.qword(0xfffffff006cbaf80) == root["_kOSBooleanTrue"]

def branch_target(address):
    word, = struct.unpack("<I", image.read(address, 4))
    assert word >> 26 in (5, 0x25), hex(address)
    imm = word & 0x3ffffff
    return address + ((imm ^ 0x2000000) - 0x2000000) * 4

digitizer_report = branch_target(0xfffffff0057445d4)
collection_report = branch_target(0xfffffff00574542c)
digitizer_event = branch_target(0xfffffff005746ae4)
assert (digitizer_report, collection_report, digitizer_event) == (
    0xfffffff0057453dc, 0xfffffff005746944, 0xfffffff00574969c)

for address, text in {
    0xfffffff004e2ff4f: b"IOHIDEventService\0",
    0xfffffff004e307bd: b"IOHIDEventDriver\0",
    0xfffffff004e309b1: b"IOHIDEvent\0",
    0xfffffff004e308ec: b"DigitizerCollectionDispatch\0",
}.items():
    assert image.read(address, len(text)) == text, hex(address)

# Exact 20H392 instruction anchors: class initializer/C2, property, report,
# collection, dispatch, appendChild, object data, digitizer constructor.
anchors = {
    0xfffffff00573d468: "a01601b00040279181b7ffd0213c3d91e2ab00b0422447f9031980529a7b0094",
    0xfffffff005748388: "401601d000c0309141b7ff9021f41e91421601d04240279103218052d24f0094",
    0xfffffff00574ecc8: "201601900060319101b7ffd021c4269162ab009042fc46f9030a805282350094",
    0xfffffff005738530: "fd7bbfa9fd0300915d90009428ac00f008812c91080000f9fd7bc1a8c0035fd6",
    0xfffffff00573e008: "fd7bbfa9fd03009148e9ff9708ac00d008c11d91080000f9fd7bc1a8c0035fd6",
    0xfffffff005748434: "fd7bbfa9fd03009175500094c8ab00b008610091080000f9fd7bc1a8c0035fd6",
    0xfffffff00572a77c: "680240f9081543f9e00313aae20316aae30315aae40314aa00013fd6",
    0xfffffff005741c68: "c8ab00b008b147f9020140f9880240f9089940f961b7fff021b02391e00314aa6300805200013fd6d50240f9a80240f9",
    0xfffffff005741ca8: "888240f92900805209a50139d50240f9",
    0xfffffff0057445c8: "e00315aae10314aae20313aa82030094",
    0xfffffff0057453dc: "f85fbca9f65701a9f44f02a9fd7b03a9fdc30091f50300aa088040f9002940f9c00400b4f30302aaf40301aa08a5413928010034e00315aae10314aae20313aafd7b43a9f44f42a9f65741a9f85fc4a846050014",
    0xfffffff005746b38: "880340f9086540f9e0031caa6101a0520200805200013fd6",
    0xfffffff005746b5c: "880340f9086540f9e0031caa210080526101a0720200805200013fd6",
    0xfffffff005746c9c: "880240f9083d40f9e00314aae1031caa00013fd6",
    0xfffffff005746f1c: "a80240f9081943f9e00315aae10314aa0200805200013fd6",
    0xfffffff0057480f4: "a8ab00f008412c91032143f9e00315aae10314aae20313aafd7b43a9f44f42a9f65741a9f85fc4a860001fd6",
    0xfffffff00574a17c: "000c40f9a00100b4",
    0xfffffff00574a1c4: "f2480094600e00f9680a40f9",
    0xfffffff00574a208: "080840f9000540b9c0035fd6",
    0xfffffff005749738: "6e0180527b1a00f96d4a00b9298100325f03007129118d1a0ea500291f2900b919d5032918590229141900b917310629",
    0xfffffff00574abbc: "080940b900451153beffff17",
}
for addr, raw in anchors.items():
    value = bytes.fromhex(raw)
    assert image.read(addr, len(value)) == value, hex(addr)
print(f"matched {len(anchors)} instruction anchors and 4 class/property strings")

# Compare every declaration in the deliverable with the extracted/anchored
# values, not merely this script's own table.
header = Path("package/nuwa-touch/NuwaHidAbi20H392.h").read_text()
declared = {name: int(value, 0) for name, value in re.findall(
    r"^\s*(NUWA_HID20_[A-Z0-9_]+)\s*=\s*(0x[0-9a-f]+|[0-9]+)",
    header, re.M)}
declared.update({name: int(value, 0) for name, value in re.findall(
    r"^#define\s+(NUWA_HID20_[A-Z0-9_]+)\s+UINT64_C\((0x[0-9a-f]+)\)",
    header, re.M)})
expected = {
    "NUWA_HID20_DEVICE_VPTR": tables["device"][0],
    "NUWA_HID20_SERVICE_VPTR": tables["service"][0],
    "NUWA_HID20_DRIVER_VPTR": tables["driver"][0],
    "NUWA_HID20_EVENT_VPTR": tables["event"][0],
    "NUWA_HID20_DEVICE_HANDLE_REPORT_VA": slots["device", 181],
    "NUWA_HID20_DEVICE_SET_PROPERTY_VA": slots["device", 23],
    "NUWA_HID20_DRIVER_SET_PROPERTIES_VA": slots["driver", 44],
    "NUWA_HID20_SERVICE_DISPATCH_VA": slots["service", 198],
    "NUWA_HID20_DRIVER_DISPATCH_VA": slots["driver", 198],
    "NUWA_HID20_DRIVER_INTERRUPT_REPORT_VA": slots["driver", 218],
    "NUWA_HID20_DIGITIZER_REPORT_VA": digitizer_report,
    "NUWA_HID20_COLLECTION_REPORT_VA": collection_report,
    "NUWA_HID20_DIGITIZER_EVENT_VA": digitizer_event,
    "NUWA_HID20_EVENT_APPEND_CHILD_VA": slots["event", 15],
    "NUWA_HID20_EVENT_GET_TYPE_VA": slots["event", 18],
    "NUWA_HID20_EVENT_GET_INTEGER_VA": slots["event", 23],
    "NUWA_HID20_EVENT_SET_INTEGER_VA": slots["event", 24],
    "NUWA_HID20_EVENT_GET_FIXED_VA": slots["event", 25],
    "NUWA_HID20_DEVICE_SLOTS": 207,
    "NUWA_HID20_SERVICE_SLOTS": 218,
    "NUWA_HID20_DRIVER_SLOTS": 219,
    "NUWA_HID20_EVENT_SLOTS": 37,
    "NUWA_HID20_DEVICE_NEW_REPORT_DESCRIPTOR_SLOT": 180,
    "NUWA_HID20_DEVICE_HANDLE_REPORT_SLOT": 181,
    "NUWA_HID20_DEVICE_TIMESTAMPED_REPORT_SLOT": 197,
    "NUWA_HID20_SET_PROPERTY_SYMBOL_OBJECT_SLOT": 23,
    "NUWA_HID20_SET_PROPERTY_CSTRING_BOOL_SLOT": 27,
    "NUWA_HID20_DRIVER_SET_PROPERTIES_SLOT": 44,
    "NUWA_HID20_SERVICE_DISPATCH_SLOT": 198,
    "NUWA_HID20_DRIVER_INTERRUPT_REPORT_SLOT": 218,
    "NUWA_HID20_EVENT_APPEND_CHILD_SLOT": 15,
    "NUWA_HID20_EVENT_GET_TYPE_SLOT": 18,
    "NUWA_HID20_EVENT_GET_INTEGER_SLOT": 23,
    "NUWA_HID20_EVENT_SET_INTEGER_SLOT": 24,
    "NUWA_HID20_EVENT_GET_FIXED_SLOT": 25,
    "NUWA_HID20_DEVICE_SIZE": 0xd0,
    "NUWA_HID20_SERVICE_SIZE": 0xc8,
    "NUWA_HID20_DRIVER_SIZE": 0x108,
    "NUWA_HID20_EVENT_SIZE": 0x50,
    "NUWA_HID20_DRIVER_PRIVATE_POINTER": 0x100,
    "NUWA_HID20_DRIVER_PRIVATE_COLLECTION_FLAG": 0x69,
    "NUWA_HID20_EVENT_DATA_POINTER": 0x10,
    "NUWA_HID20_EVENT_CHILDREN_POINTER": 0x18,
    "NUWA_HID20_DIGITIZER_OPTIONS": 0x08,
    "NUWA_HID20_DIGITIZER_X": 0x10,
    "NUWA_HID20_DIGITIZER_Y": 0x14,
    "NUWA_HID20_DIGITIZER_INDEX": 0x1c,
    "NUWA_HID20_DIGITIZER_TYPE": 0x20,
    "NUWA_HID20_DIGITIZER_IDENTITY": 0x24,
    "NUWA_HID20_DIGITIZER_EVENT_MASK": 0x28,
    "NUWA_HID20_DIGITIZER_PRESSURE": 0x34,
    "NUWA_HID20_DIGITIZER_TOUCH_OPTIONS_BIT": 17,
}
assert declared == expected, (declared.keys() ^ expected.keys(),
                              {k: (declared[k], expected[k]) for k in
                               declared.keys() & expected.keys()
                               if declared[k] != expected[k]})
print(f"matched all {len(expected)} header declarations")

def execute_getter(entry, key, offset, expected, expected_pc, touch=True):
    u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for segment in ("__TEXT", "__TEXT_EXEC", "__DATA_CONST"):
        va, content = image.segments[segment]
        low, high = va & ~4095, (va + len(content) + 4095) & ~4095
        u.mem_map(low, high - low)
        u.mem_write(va, content)
    u.mem_map(0x100000, 0x20000)
    obj, data = 0x101000, 0x102000
    u.mem_write(obj, struct.pack("<Q", tables["event"][0]))
    u.mem_write(obj + 0x10, struct.pack("<Q", data))
    for off, value in ((4, 11), (8, (1 << 17) if touch else 0),
                       (0x10, 0x12345), (0x14, 0x23456),
                       (0x1c, 0x5a), (0x20, 2), (0x24, 0x35),
                       (0x28, 0x135), (0x34, 0x34567)):
        u.mem_write(data + off, struct.pack("<I", value))
    for reg, value in ((UC_ARM64_REG_X0, obj), (UC_ARM64_REG_X1, key),
                       (UC_ARM64_REG_X2, 0), (UC_ARM64_REG_SP, 0x11f000),
                       (UC_ARM64_REG_X30, 0x110000)):
        u.reg_write(reg, value)
    reads = []
    def on_read(machine, access, address, size, value, opaque):
        if data <= address < data + 0x100:
            reads.append((machine.reg_read(UC_ARM64_REG_PC), address-data, size))
    u.hook_add(UC_HOOK_MEM_READ, on_read)
    u.emu_start(entry, 0x110000, count=5000)
    assert u.reg_read(UC_ARM64_REG_X0) == expected, (hex(key), reads)
    assert (expected_pc, offset, 4) in reads, (hex(key), reads)
    print(f"getter key={key:#x}, data+{offset:#x}, pc={expected_pc:#x}, result={expected:#x}")

integer = slots["event", 23]
fixed = slots["event", 25]
for entry, key, off, value, pc in (
    (fixed, 0xb0000, 0x10, 0x12345, 0xfffffff00574bc8c),
    (fixed, 0xb0001, 0x14, 0x23456, 0xfffffff00574bdd4),
    (fixed, 0xb000a, 0x34, 0x34567, 0xfffffff00574bf38),
    (integer, 0xb0004, 0x20, 2, 0xfffffff00574a65c),
    (integer, 0xb0005, 0x1c, 0x5a, 0xfffffff00574a7a4),
    (integer, 0xb0006, 0x24, 0x35, 0xfffffff00574a900),
    (integer, 0xb0007, 0x28, 0x135, 0xfffffff00574abb4),
    (integer, 0xb0009, 0x08, 1, 0xfffffff00574abbc),
):
    execute_getter(entry, key, off, value, pc)
execute_getter(integer, 0xb0009, 0x08, 0, 0xfffffff00574abbc, touch=False)
print("self-checked: donor anchors and synthetic getter paths; no runtime claim")
# END NUWA_HID_ABI_EXTRACT
```
