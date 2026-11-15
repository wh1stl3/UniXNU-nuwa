"""Host-only pinned payload wrapper; no bootimg, patch, native build or device command."""
import argparse
from pathlib import Path

from owner_payload import BASELINE_PROFILE, PROFILES, build_candidate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'soc', 'kernel', 'identity-file', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--kernel-sha256', required=True)
    p.add_argument('--profile', choices=tuple(PROFILES), default=BASELINE_PROFILE,
                   help='Default baseline only; explicit frozen diagnostic/continuation opt-in, not an arbitrary hash override')
    p.add_argument('--enable-owner-bnch', action='store_true')
    p.add_argument('--continuation-reference', type=Path,
                   help='Frozen diagnostic source required only by the continuation profile; never modified')
    for name in ('reuse-record', 'trust-cache', 'data-ramdisk', 'gpu-addon'):
        p.add_argument('--' + name, type=Path)
    a = p.parse_args()
    report = build_candidate(a.base, a.soc, a.kernel, a.kernel_sha256, a.identity_file, a.output,
                            enabled=a.enable_owner_bnch, reuse=a.reuse_record,
                            trust=a.trust_cache, data=a.data_ramdisk, addon=a.gpu_addon, profile=a.profile,
                            continuation_reference=a.continuation_reference)
    print('self-checked host FAT readback:', report['payload_path'])
    print('payload SHA256:', report['payload_sha256'], '; no device release')


if __name__ == '__main__':
    main()
