"""Compare two prelink candidates byte for byte, grouped by segment.

The early-security marker changes a dictionary entry inside __PRELINK_INFO, and
the serialized metadata shifts everything after it. A raw byte diff therefore
looks enormous while no code changed. This reports the difference per segment so
"executable text is unchanged" is a checked claim, not an impression.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_prelink_inputs import inputs, tools  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--old', type=Path, required=True)
    cli.add_argument('--new', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True, help='fresh report under reports/')
    args = cli.parse_args()

    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'reports') or output.exists():
        raise ValueError('fresh report under reports/ required')

    old, new = args.old.read_bytes(), args.new.read_bytes()
    if len(old) != len(new):
        raise ValueError('candidates differ in length (%d vs %d); per-segment comparison needs equal length'
                         % (len(old), len(new)))

    differing = [index for index in range(len(old)) if old[index] != new[index]]
    runs, start, previous = [], None, None
    for index in differing:
        if start is None:
            start = previous = index
            continue
        if index != previous + 1:
            runs.append((start, previous))
            start = index
        previous = index
    if start is not None:
        runs.append((start, previous))

    profile_path = ROOT / 'config/native-prelink-merged-analysis-profile.json'
    profile, native, donor, selection = inputs(profile_path)
    with tools(True, profile_path) as (parser, emitter):
        image = parser.macho(new)

        def segment_of(offset):
            for segment in image['segments']:
                if segment['fileoff'] <= offset < segment['fileoff'] + segment['filesize']:
                    return segment['name']
            return '(header/other)'

        per_segment = {}
        for index in differing:
            name = segment_of(index)
            per_segment[name] = per_segment.get(name, 0) + 1
        touches_executable = sorted(name for name in per_segment if 'TEXT' in name)

        report = {
            'scope': 'byte comparison of two offline prelink candidates; no device, no boot',
            'old': {'path': str(args.old), 'bytes': len(old), 'sha256': sha(old)},
            'new': {'path': str(args.new), 'bytes': len(new), 'sha256': sha(new)},
            'same_length': True,
            'differing_bytes': len(differing),
            'differing_runs': len(runs),
            'differing_bytes_per_segment': per_segment,
            'executable_segments_with_differences': touches_executable,
            'executable_text_unchanged': not touches_executable,
            'largest_runs': [{'file_offset': hex(begin), 'bytes': end - begin + 1,
                              'segment': segment_of(begin)} for begin, end in
                             sorted(runs, key=lambda run: run[1] - run[0], reverse=True)[:10]],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('differing bytes: %d in %d runs' % (len(differing), len(runs)))
        print('per segment:', per_segment)
        print('executable text unchanged:', report['executable_text_unchanged'])


if __name__ == '__main__':
    main()
