"""Emit an analysis prelink with an explicit early security initializer.

The existing analysis path passes an empty mapping to the emitter and writes an
empty `early_security_initializers` into its report
(scripts/emit-current-prelink-analysis.py:18,43), so the early-security blocker
has never actually been exercised against emit_prelink.py's checks. This script
runs that path with a real value and reports what the emitter accepted.

It does not replace or overwrite the existing analysis candidate, and it does
not change `loadable`: that flag is set by hand after hardware qualification,
and this script only proves the emitter's own preconditions hold.

emit_prelink.py enforces, for every configured initializer (lines 137-156):
  * the native kernel exports _native_prelink_security_init_version == 1
  * the bundle is among the selected components and carries
    AppleSecurityExtension = true
  * the original VA is 4-byte aligned and inside a __TEXT_EXEC segment with
    initprot == 5 and no write in maxprot
  * original VA + slide does not overflow 64 bits
Each of those is checked independently here and reported either way.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_prelink_inputs import inputs, tools, components, SELECTION  # noqa: E402

MASK = (1 << 64) - 1
DEFAULT_BUNDLE = 'com.apple.driver.AppleMobileFileIntegrity'
DEFAULT_VA = 0xFFFFFFF005703C54


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--work', type=Path, required=True, help='fresh directory under out/')
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    cli.add_argument('--profile', type=Path,
                     default=ROOT / 'config/native-prelink-merged-analysis-profile.json')
    cli.add_argument('--bundle', default=DEFAULT_BUNDLE)
    cli.add_argument('--original-va', type=lambda value: int(value, 0), default=DEFAULT_VA,
                     help='original (pre-slide) VA of the early security initializer')
    args = cli.parse_args()

    work = args.work.resolve()
    output = args.output.resolve()
    if not work.is_relative_to(ROOT / 'out') or work.exists():
        raise ValueError('fresh work directory under out/ required')
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('fresh report under reports/ required')

    profile, native, donor, selection = inputs(args.profile)
    slide = profile['slide']
    roots = selection['components'] + selection['codeless_components']

    with tools(True, args.profile) as (parser, emitter):
        # --- precondition checks, reported whether or not emit accepts ----
        native_image = parser.macho(native)
        native_exports = parser.exports(native, native_image)
        marker_hits = [address for address, names in native_exports.items()
                       if any('_native_prelink_security_init_version' in name for name in names)]
        marker = {'found': len(marker_hits) == 1, 'addresses': [hex(a) for a in marker_hits]}
        if len(marker_hits) == 1:
            try:
                marker['value'] = struct.unpack_from('<I', native, parser.backed_offset(
                    native_image['segments'], marker_hits[0], 4, len(native)))[0]
            except ValueError:
                marker['value'] = None

        parent, metadata, modules = components(parser, donor, selection)
        entry = next((e for e in metadata['_PrelinkInfoDictionary']
                      if e['CFBundleIdentifier'] == args.bundle), None)
        preconditions = {'bundle_selected': args.bundle in modules,
                         'apple_security_extension': entry.get('AppleSecurityExtension') if entry else None,
                         'aligned': args.original_va % 4 == 0,
                         'sum_within_64_bits': 0 <= args.original_va + slide < 1 << 64}
        segment_hit = None
        if args.bundle in modules:
            for segment in modules[args.bundle]['segments']:
                if segment['name'] != '__TEXT_EXEC':
                    continue
                if (segment['va'] <= args.original_va < segment['va'] + segment['filesize']
                        and segment['initprot'] == 5 and not segment['maxprot'] & 2):
                    segment_hit = {'va': hex(segment['va']), 'size': hex(segment['size']),
                                   'initprot': segment['initprot'], 'maxprot': segment['maxprot']}
        preconditions['inside_rx_text_exec'] = segment_hit is not None
        preconditions['segment'] = segment_hit

        # --- the actual emit with the mapping supplied --------------------
        configured = {args.bundle: args.original_va}
        emitted, accepted, error = None, False, None
        try:
            image, full = emitter.emit(native, donor, roots, slide, configured)
            accepted = True
        except ValueError as failure:
            image, full, error = None, None, str(failure)

        result = {
            'scope': 'offline analysis prelink exercising emit_prelink early-security checks; not a boot payload',
            'native_sha256': sha(native), 'donor_sha256': sha(donor),
            'reference_selection_sha256': profile['reference_selection_sha256'],
            'slide': slide,
            'configured_initializer': {'bundle': args.bundle, 'original_va': hex(args.original_va),
                                       'expected_slid_va': hex((args.original_va + slide) & MASK)},
            'abi_marker': marker,
            'preconditions': preconditions,
            'emit_accepted': accepted,
            'emit_error': error,
            'loadable': False,
            'loadable_note': 'loadable stays false: the emitter flag is set by hand after hardware qualification, '
                             'and this run only proves the early-security preconditions hold',
            'device_accessed': False,
        }

        if accepted:
            reported = full.get('early_security_initializers', {})
            result['emitted_early_security_initializers'] = {key: hex(value) for key, value in reported.items()}
            result['emitted_value_matches_expected'] = reported.get(args.bundle) == (args.original_va + slide) & MASK
            # Tier one: the emitter records the mapping. Tier two: nothing ran.
            result['candidate'] = {'bytes': len(image), 'sha256': sha(image)}
            work.mkdir(parents=True)
            (work / 'kernel-prelinked-earlysec.macho').write_bytes(image)
            (work / 'emission.json').write_text(json.dumps(full, indent=2) + '\n', encoding='utf-8')

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        print('abi marker:', marker)
        print('preconditions:', {k: v for k, v in preconditions.items() if k != 'segment'})
        print('emit accepted:', accepted, 'error:', error)
        if accepted:
            print('recorded:', result['emitted_early_security_initializers'],
                  'matches:', result['emitted_value_matches_expected'])
            print('candidate:', result['candidate']['sha256'][:16], result['candidate']['bytes'], 'bytes')


if __name__ == '__main__':
    main()
