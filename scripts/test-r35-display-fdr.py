#!/usr/bin/env python3
"""Check the FDR overlay against the pinned r35l renderer."""
import sys
from pathlib import Path
from generate_r35_display_diag import generate

src = generate(Path(sys.argv[1]).read_bytes()).decode()
exit_fn = src[src.index("void boot_progress_exit(int pid,"):]
assert exit_fn.index('__atomic_store_n(&bp_fdr_exit') < exit_fn.index('__atomic_exchange_n(&exit_lock')
assert 'strcmp(name,"IOMFB_FDR_Loader")' in exit_fn
assert 'if((signal || ns) && !(name && !strcmp(name,"IOMFB_FDR_Loader")))' in exit_fn
assert src.count('__atomic_load_n(&bp_fdr_exit,__ATOMIC_RELAXED)') == 1
assert 'line(10,b,0xff00ffcc);' in src
assert 'FDR no exit seen' in src
assert src.count('__atomic_load_n(&bp_dsp_properties,__ATOMIC_RELAXED)') == 1
assert len(f"PROP {0xffff:04x} FDR {0xffffffff}s st={0xffff} sig={0xff}") <= 80
assert len(f"SC n={0xffffffff} r={0xffffffff} o={0xffffffff}") <= 80
assert 'line(11,b,0xff00ffcc);' in src
for name in ("calls", "rejects", "ok"):
    assert src.count(f'__atomic_load_n(&nuwa_sc_{name},__ATOMIC_RELAXED)') == 2
banner = src[src.index("static void crash_banner(unsigned now)"):]
assert 'SC n=%u r=%u o=%u' in banner
assert 'SC +%u in %us' in banner
assert len(f"SC +{0xffffffff} in {0xffffffff}s") <= 80
provider = Path("package/NuwaLegacyDisplay.cpp").read_text()
assert 'displayObject->setProperty("IOFBRotation", (unsigned long long)0, 32)' in provider
assert provider.index('setProperty("IOFBRotation"') < provider.index('displayObject->registerService();')
assert 'failure(17); goto finish;' in provider
for bit, key in enumerate(("canvas-width", "canvas-height", "device_type",
                           "IOMFBNumLayers", "IOMFBDisplayRefresh",
                           "NormalModeEnable", "ADCLLoadAll", "IOFBRotation")):
    method = "copyProperty" if bit in (0, 4) else "getProperty"
    assert f'{method}("{key}")' in provider
    assert f'properties |= 1u << {bit}' in provider
assert 'refresh && !OSDynamicCast(OSDictionary, refresh)' in provider
assert 'widthData && widthData->getLength() != 4' in provider
for name in ("width", "refresh"):
    assert provider.count(f'OSSafeReleaseNULL({name});') == 1
    assert provider.index(f'OSDynamicCast({"OSData" if name == "width" else "OSDictionary"}, {name})') < provider.index(f'OSSafeReleaseNULL({name});')
bridge = provider[provider.index("bool native_legacy_prepare_scanout(void) {"):
                  provider.index("// CPU-copy policy:")]
for name in ("calls", "rejects", "ok"):
    assert bridge.count(f'__atomic_fetch_add(&nuwa_sc_{name}, 1u, __ATOMIC_RELAXED)') == 1
assert 'return ok;' in bridge
assert provider.index('displayObject->registerService();') < provider.index('boot_progress_prop_set(properties);')
assert 'CLI in=%u out=%u ret=%08x bb=%c' in src
assert len(f"DSP s={255} r={255} CLI in={0xffffffff} out={0xffffffff} ret={0xffffffff:08x} bb=?") <= 80
assert 'CLI unavailable' in src
for second, status in [(1, 0), (388, 0x100), (42, 5), (0xffffffff, 0xffff)]:
    value = second << 32 | (status & 0xffff) << 16 | status & 127
    assert (value >> 32, (value >> 16) & 0xffff, value & 0xff) == (second, status, status & 127)
print("FDR overlay checks passed")
