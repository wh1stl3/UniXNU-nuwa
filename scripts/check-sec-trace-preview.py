"""Apply a proposed SEC trace patch in RAM; never compile or emit firmware."""
import hashlib
import json
from pathlib import Path
from virtual_patch import Tree, parse

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/uefi-nuwa')
RELATIVE = 'Silicon/Silicium/SiliciumPkg/Sec/Sec.c'
PATCH = ROOT / 'patches/firmware-candidates/0005-nuwa-sec-stage-trace.patch'


def main():
    profile = json.loads((ROOT / 'config/firmware-dedicated-profile.json').read_text())
    entry = next(item for item in profile['recipe']['inputs']
                 if item['root'] == 'firmware' and item['path'] == RELATIVE)
    original = (FIRMWARE / RELATIVE).read_text(encoding='utf-8')
    source_hash = hashlib.sha256(original.encode()).hexdigest()
    if source_hash != entry['lf_sha256']:
        raise ValueError('SEC source differs from the built dedicated profile')
    patch = PATCH.read_text(encoding='utf-8')
    if [path for path, _, _ in parse(patch)] != [RELATIVE]:
        raise ValueError('Trace candidate must modify SEC.c only')
    tree = Tree(FIRMWARE)
    tree.apply(patch)
    source = tree.read(RELATIVE)
    stages = ('C-before-platform', 'C-after-platform', 'before-memory',
              'before-platform-hobs', 'before-fv-decompress', 'before-dxe-core')
    calls = ('PlatformInitialize ();', 'Status = InitializeMemory ();', 'Status = PlatformPeim ();',
             'Status = DecompressFirstFv ();', 'Status = LoadDxeCoreFromFv (NULL, 0);')
    checks = {
        'one_file_only': set(tree.files) == {RELATIVE},
        'all_original_stage_calls_retained_once': all(source.count(call) == 1 for call in calls),
        'all_six_trace_markers_present_once': all(source.count('NUWA_ENTRY_TRACE ("' + stage + '")') == 1
                                                for stage in stages),
        'trace_precedes_platform': source.index('NUWA_ENTRY_TRACE ("C-before-platform")') < source.index(calls[0]),
        'framebuffer_clear_removed': 'ClearFrameBuffer' not in source,
        'no_address_constants_added': not any(line.startswith('+') and '0x' in line
                                              and 'x0=0x%lx' not in line for line in patch.splitlines()),
        'no_new_library_headers': [line for line in source.splitlines() if line.startswith('#include')]
                                  == [line for line in original.splitlines() if line.startswith('#include')],
    }
    if not all(checks.values()):
        raise ValueError(checks)
    report = {'scope': 'Source patch preview only; no diagnostic/firmware image generated',
              'firmware_commit': profile['recipe']['sources']['firmware']['commit'], 'path': RELATIVE,
              'source_lf_sha256': source_hash, 'patched_lf_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'patch_sha256': hashlib.sha256(PATCH.read_bytes()).hexdigest(), 'checks': checks,
              'compile_status': 'unverified; requires approved diagnostic build',
              'limitations': ['Framebuffer only; no USB/UART or persistent logs',
                              'Does not instrument ABL/BootShim/earliest SEC assembly',
                              'Absent text cannot prove no SEC execution',
                              'DEBUG formatting/cache flush can perturb timing']}
    destination = ROOT / 'reports/firmware-ci/39805110487/sec-trace-preview.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
