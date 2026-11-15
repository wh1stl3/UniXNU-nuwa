#!/usr/bin/env python3
"""Host-only by default. Explicit per-phase authorization is required for I/O."""
import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

REPO = Path(__file__).resolve().parents[1]
SIZE = 100663296
STOCK = '493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad'
CANDIDATE = 'a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0'
R4 = '692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5'
BLOCK = '/dev/block/by-name/vendor_boot_b'
STATES = ('identified', 'backup_verified', 'candidate_verified_on_B',
          'bootloader_stable', 'set_B_accepted', 'boot_attempt_consumed',
          'set_A_accepted', 'android_A_confirmed', 'B_restored_verified')
BAD = re.compile(r'(?:^|\s)FAILED(?:\s|:|$)|unknown command|permission denied|not permitted|error:|no such file', re.I | re.M)
LABEL = 'DIAG: PMAP initializer normal epilogue reached; STOP'
STOP_PROFILE = 'pmap-ret-stop-20261111-r1'
CONTINUATION_PROFILE = 'pmap-ret-continue-20261111-r1'
AMNM_PROFILE = 'amnm-observe-20261111-r1'
CHMH_PROFILE = 'chmh-only-20261112-r1'
PTHREAD_PROFILE = 'pthread-chmh-20261112-r1'
PMGR_PROFILE = 'pmgr-mode2-20261113-r1'
HC_PROFILE = 'ufs-hc-observe-20261114-r1'
QUEUE_PROFILE = 'ufs-queue-five-20261114-r1'
SID_PROFILE = 'ufs-sid-domain-20261114-r1'
NOP_PROFILE = 'ufs-preserved-nop-20261114-r1'
ROOT_PROFILE = 'ufs-apfs-root-20261115-r9'
STOP_OBSERVATION = ('Record 60 seconds of video; observe: ' + LABEL
                    + '; after observation manually return to bootloader, then run restore separately'
                    + ' with its own authorization; do not rerun boot; no automatic continue/reboot/retry.')
CONTINUATION_OBSERVATION = (
    'Record 60 seconds of video; observe the first natural panic or a visible native milestone. '
    'The old DIAG STOP line is not expected and park is not claimed. '
    'MAC Framework successfully initialized only proves the mac_policy_initbsd printf before callbacks. '
    'Missing/new output is ambiguous: do not infer not-reached, and do not attribute menu stops, reboots or '
    'screen changes to PMAP/watchdog/stage5. After observation manually return to bootloader, then run '
    'restore separately with its own authorization; do not rerun boot; no automatic continue/reboot/retry.')
AMNM_OBSERVATION = ('Record 60 seconds of video; observe the original panic and AMNM snapshot if visible. '
                    'Missing panic or snapshot is ambiguous, not success. After observation manually return to bootloader, '
                     'then run restore separately with its own authorization; do not rerun boot.')
CHMH_OBSERVATION = ('Record 60 seconds of video; observe the first natural panic or a later visible milestone. '
                    'Missing panic is not success; no AMNM snapshot is expected. After observation manually return '
                    'to bootloader, then run restore separately with its own authorization; do not rerun boot.')
PTHREAD_OBSERVATION = ('Record 60 seconds of video; observe whether execution naturally passes pthread_init; '
                       'identify the first new panic or visible milestone. No output is not success. '
                       'Then manually return to bootloader and restore separately with its own authorization; '
                       'do not rerun boot.')
PMGR_OBSERVATION = ('Record 60 seconds of video; seek evidence of actual PMGR nub publication and AMFI consumption. '
                    'Disappearance of the old panic does not prove pthread passed; no output is inconclusive. '
                    'Manually return to bootloader and restore separately with its own authorization; do not rerun boot.')
HC_OBSERVATION = ('Record 60 seconds of video; observe the stage marker and single raw VER/CAP/HCS/HCE readings. '
                  'Missing or abnormal output is inconclusive and does not uniquely identify a cause. '
                  'Manually return to bootloader and restore separately with its own authorization; do not rerun boot.')
QUEUE_OBSERVATION = ('Record 60 seconds of video; observe QUEUE_ONLY_DONE attempt=5 completed=5 hc_read=5 '
                     'and raw HCE/UTRLDBR/UTRLRSR/UTRLBA/UTRLBAU values. '
                     'The old HC_SNAPSHOT_DONE stage marker alone is not success; missing or abnormal output is inconclusive. '
                     'Manually return to bootloader and restore separately with its own authorization; do not rerun boot.')
SID_OBSERVATION = ('Record 60 seconds of video; distinguish these panic texts: '
                   'NUWA SID MAP_REFUSED no SMMU reads; no cause inferred; '
                   'NUWA SID UNSUPPORTED scr0=%08x id0=%08x id1=%08x id2=%08x; no scan; '
                   'NUWA SID NONUNIQUE count=%u checked=%u matches=%u; no bank read; '
                   'NUWA SID ROUTE_REFUSED slot=%u smr=%08x s2cr=%08x banks=%u; no bank read; '
                   'NUWA SID DOMAIN_STOP status=%u scr0=%08x id0=%08x id1=%08x id2=%08x. '
                   'DOMAIN_STOP status4 reports an AArch64 stage1 summary; '
                   'status9 is an unsupported context mode, not a successful domain. The other terminals are '
                   'refusals, not domain success. All readings are momentary and prove no ownership, translation '
                   'or readiness. Missing output is inconclusive. Manually return to bootloader and restore '
                   'separately with its own authorization; do not rerun boot.')
NOP_OBSERVATION = ('Record 60 seconds; observe NUWA PRESERVED_NOP end/stage/dma/bank/slot/id2/cbar/sctlr/polls/db/is/ocs. '
                   'Printed end is zero-based; terminal is end+1. End 0 Success; 1 Claimed (never panics); '
                   '2 Mapping, 3 Domain, 4 Allocation, 5 Prerequisite, 6 InterruptMask, 7 Stop, 8 Changed, '
                   '9 Base, 10 Ready, 11 Final, 12 Fatal, 13 Timeout, 14 Ocs, 15 Response are failures. '
                   'No marker rows are emitted; unknown or missing endpoint cannot be attributed and panic alone '
                   'does not prove NOP success. Missing/unknown endpoint means HC control writes and DMA may already '
                   'have occurred; it proves neither non-submission nor success. This attempt is consumed; do not retry. '
                   'No media write applies only to the NOP; vendor_boot_b installation and restoration are separate '
                   'authorized writes. Manually return to bootloader, then restore separately with its '
                   'own authorization; do not rerun boot. Proposed operation: HC control writes, own descriptor DMA '
                   'and one NOP; no SMMU write, media write or root.')
PROFILES = {
    STOP_PROFILE: {
        'candidate': 'out/owner-vendor-boot-20261111-final/vendor_boot.img',
        'candidate_sha256': CANDIDATE, 'stock_sha256': STOCK, 'r4_sha256': R4,
        'bytes': SIZE, 'r4_bytes': 1495040, 'observation': STOP_OBSERVATION,
    },
    CONTINUATION_PROFILE: {
        'candidate': 'out/owner-continuation-vendor-boot-20261111-final/vendor_boot.img',
        'candidate_sha256': '4a52ddbc2cc06401f76676f480eb1b0e4b1dfafce0a8d07b453dd53967a05618',
        'stock_sha256': STOCK, 'r4_sha256': R4,
        'bytes': SIZE, 'r4_bytes': 1495040, 'observation': CONTINUATION_OBSERVATION,
        'frozen': {'kernel_sha256': '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4',
                   'args': '-v serial=3',
                   'fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
                   'adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
                   'evidence': 'out/owner-continuation-vendor-boot-verifier-20261111/outer-record.json'},
    },
    AMNM_PROFILE: {
        'candidate': 'out/amnm-observe-20261111-r1/vendor_boot.img',
        'candidate_sha256': 'c5784135e3bb03e371808510dc0031fe3641782fd5fedf852fd7401783c0ddef',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': AMNM_OBSERVATION,
        'frozen': {'kernel_sha256': '1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162',
                   'kernel_bytes': 55402496, 'args': '-v serial=3', 'fat_bytes': 67108864,
                   'fat_sha256': '7074311dc2e2d3e0e71432b150a4bbef557625e27412a98b1464a7736f11c1fa',
                   'fat': 'out/amnm-observe-20261111-r1/payload.img', 'adt_bytes': 13256,
                   'adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
                   'parent_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
                   'derived': 'out/amnm-observe-20261111-r1/derived-record.json',
                   'derived_sha256': '0b26d1f64b417882307b3dd904a95c19d19068e7a56613950156162ecd78e888',
                   'report': 'out/amnm-observe-20261111-r1/report.json',
                   'report_sha256': '410471b127632260331325bc8d326f2d9cb23089d1079ce1cc935c0a3bee8d1d',
                   'audit': 'out/amnm-package-audit-r2-resume-20261111/audit.json',
                   'audit_sha256': 'cb64eeedd79b71e0e1f0b4982b81fa69b1bd2fc3529e05a8f027c1374cdcda2a',
                   'audit_source': 'scripts/audit-owner-amnm-observe.py',
                   'audit_source_sha256': '283507b2cc44dc9c678c0a64d4d3f4def548681b6a9270e3b9dd88d206d42e48'},
    },
    CHMH_PROFILE: {
        'candidate': 'out/chmh-only-vendor-boot-20261112-r1/vendor_boot.img',
        'candidate_sha256': 'c120de57a1517660947dca381a4713a7a9e146dc704b722f455816b892733baa',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': CHMH_OBSERVATION,
        'frozen': {'kernel_sha256': '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4',
                   'kernel_bytes': 55386112, 'args': '-v serial=3', 'fat_bytes': 67108864,
                   'fat': 'out/chmh-only-verifier-20261112/payload.img',
                   'fat_sha256': '799190b496fa3398412dec551910fa8920498a4e5313de9d3cd792706109db68',
                   'adt': 'out/chmh-only-verifier-20261112/derived.adt', 'adt_bytes': 13340,
                   'adt_sha256': '42494097fcd5e0777bc9792b2225df7eb39dc64384a2cae38fe09c409a790eed',
                   'derived': 'out/chmh-only-verifier-20261112/record.json',
                   'derived_sha256': '992416d057b280ea5376b839c34d169889968c248129b43befcb2737a731b08a',
                   'report': 'out/chmh-only-vendor-boot-20261112-r1/outer-record.json',
                   'report_sha256': '7b9cf2d761ab5b7fbf32fbf785cd74bba1106690c709704d250e56c39f49fb62',
                   'audit': 'out/chmh-only-vendor-boot-audit-20261112-r2/audit.json',
                   'audit_sha256': '65f16d7f3eaf93cef605a143b41dfb77f689df1bdb5920551c7fb7e6640ebaff',
                   'audit_source': 'scripts/build-chmh-only-vendor-boot.py',
                   'audit_source_sha256': '3a5e48d926ecbff4b1bd78a3d9dc9222d3983f1615fde4a024a42c7cf25a4954'},
    },
    PTHREAD_PROFILE: {
        'candidate': 'out/pthread-chmh-20261112-r4/vendor_boot.img',
        'candidate_sha256': '175258a62cc9543cb2a7387d0b3a1312eeab5fd7443d1614b0038f2928f8ff3a',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': PTHREAD_OBSERVATION,
        'frozen': {
            'package_profile': 'pthread-chmh-only-20261112-r1', 'args': '-v serial=3',
            'kernel': 'out/pthread-chmh-20261112-r4/kernel.macho', 'kernel_bytes': 55390208,
            'kernel_sha256': 'e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d',
            'fat': 'out/pthread-chmh-20261112-r4/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': 'd2f48bf3244d9571375fcd2b9aaff4a8814935ae6d48bad05b5faf2dc1f9a07b',
            'adt': 'out/pthread-chmh-20261112-r4/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': '4099834dedf4e3ee0b20bc9bbbedf7ad1402d1cdd70afe0ddf7c7adf1e40dfe8',
            'derived': 'out/pthread-chmh-20261112-r4/record.json',
            'derived_sha256': '8c8009146e8d4d0a4abe2caa85f6db9251d847faab2c5928611a2bf7366318df',
            'report': 'out/pthread-chmh-20261112-r4/outer-record.json',
            'report_sha256': '43d60553c1c66ca71478522ae20c8e4e7d56280423da503b4869b7037fd91db1',
            'audit': 'out/pthread-chmh-20261112-r4/audit.json',
            'audit_sha256': '22715fde9c453deee09598e3ef3652a123a1c228af4b1b988fc5e3ac9ec1398b',
            'layout': 'out/pthread-chmh-20261112-r4/layout.json',
            'layout_sha256': 'a685229f79cb5350a07440e1f005d168bc89173158277baed614f02fe97a18f2',
            'audit_source': 'scripts/build-pthread-chmh.py',
            'audit_source_sha256': '27c5767578cd073740a59b876ff17507d0bc485bbc57d01f431326d0e026835a',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'pristine_sha256': '8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d',
            'chmh_hex': 'e864dc22f22aab99007526d1c02a1f80210dd954c2ca27caefc250f0c5db588d2cf90c4cee5e82a859cd8327835bb6a8',
            'evidence': {
                'renderer_manifest': {'path': 'out/pthread-renderer-verifier-20261112/renderer-manifest.json', 'sha256': 'd57e9b18788330a7bad8ceedcec12fb62015037a0dd202dc1ce8bcf5372e2eb1'},
                'renderer_audit': {'path': 'out/pthread-renderer-verifier-20261112/audit.json', 'sha256': '884a4d4a5ae0ff221ef0eb4047441f2be91bb8fd00f4b2038862e86423eaa454'},
                'prelink_audit': {'path': 'out/pthread-normal-prelink-20261112-r4/audit.json', 'sha256': 'b4e0907f5f153918e193d19f5506b507c100fadec1d134b754a5c8449a22ba3e'},
                'prelink_provenance': {'path': 'out/pthread-normal-prelink-20261112-r4/provenance.json', 'sha256': '0be27e7ee76a45801baa2874165961c4d2a6e72dfc9b3e946b212abc00c91202'},
            },
        },
    },
    PMGR_PROFILE: {
        'candidate': 'out/pmgr-mode2-chmh-20261113-r4/vendor_boot.img',
        'candidate_sha256': 'ad74c1cb7beee59b60bc0fbb446a7439e8a21a39a3f956ea574b6a62410efd45',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': PMGR_OBSERVATION,
        'frozen': {
            'package_profile': 'pmgr-mode2-chmh-20261113-r1', 'args': '-v serial=3 nuwa-pmgr=2',
            'kernel': 'out/pmgr-mode2-chmh-20261113-r4/kernel.macho', 'kernel_bytes': 55451648,
            'kernel_sha256': '81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1',
            'fat': 'out/pmgr-mode2-chmh-20261113-r4/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': 'a9697c46d775e722d902cceea32070518ea2e8e5cfce8af8abc4eccd25afe701',
            'adt': 'out/pmgr-mode2-chmh-20261113-r4/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': '59e78384804830a981e894451c66301c873afbb1da5d768220e538db2a4c8fff',
            'derived': 'out/pmgr-mode2-chmh-20261113-r4/record.json',
            'derived_sha256': 'be10c1a9c113e84ad3ac9d29f26e453c3ea01a02c0b7bbc75987f4208b1dd3c4',
            'report': 'out/pmgr-mode2-chmh-20261113-r4/outer-record.json',
            'report_sha256': 'bd9a94d2d60a349a1615cd47d3c52c51e4fb1fc1408280abdaa6e7685b2dcac3',
            'audit': 'out/pmgr-mode2-chmh-20261113-r4/audit.json',
            'audit_sha256': 'ff58a8556bf4798d8ccae6cb0bcf2f6792b43abd4d1691ad68553a0010649cf8',
            'layout': 'out/pmgr-mode2-chmh-20261113-r4/layout.json',
            'layout_sha256': 'c0f5d98fbaf7d2d1812b869b7ba05fa88acb1cd5832451defce7a8a019169284',
            'provenance': 'out/pmgr-mode2-chmh-20261113-r4/provenance.json',
            'provenance_sha256': 'fca4a2ebcc2643fb3f2c6e4a21b432adac253a7beeacbac4c7a3f032da25ffde',
            'config': 'out/pmgr-mode2-chmh-20261113-r4/unixnu.toml', 'config_bytes': 414,
            'config_sha256': 'bc6a52a868eb762560f6a399b45e786105bfad69b93dec951d45e056a0003cdd',
            'source': 'scripts/build-pmgr-mode2-chmh.py',
            'source_sha256': '3173f69350086a562ffae20e4d1d4d9586c37bfd9a0b022bc3a1e8e6420f7774',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'parent_config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'chmh_hex': '4af690f92784ee79da2330dbd49372cadea6c242375dfd1e54cfd703f49fde6dc51c035adcd09db805e79c045afad502',
            'evidence': {
                'kernel_manifest': {'path': 'out/nuwa-pmgr-kernel-20261113-r5/kernel.json', 'sha256': 'd3c435d48dcd138d77d3d5fca03bbfae8b525f653c8ea4caf68cb69419190e1a'},
                'kernel_audit': {'path': 'out/nuwa-pmgr-kernel-20261113-r5/audit.json', 'sha256': '54f24ddbf85e34eee9c1cdbc4adeddef7c6e73f4dfeaa3d4413556df556b9853'},
                'startup_audit': {'path': 'out/nuwa-pmgr-kernel-20261113-r5/startup-audit.json', 'sha256': '216de401faacbb77e9dba181a8d4d861e544f70ac79e6c54f7ad69d3eb5e4253'},
                'provenance': {'path': 'out/nuwa-pmgr-kernel-20261113-r5/provenance.json', 'sha256': '82f6bb10d8adead8c3da824d564b51ad66b6298b5c0da23df8a19470d448207d'},
            },
        },
    },
    HC_PROFILE: {
        'candidate': 'out/nuwa-ufs-hc-chmh-20261113-r1/vendor_boot.img',
        'candidate_sha256': '6e150640b3780bcd2bc890d007619eecce2ce2fa6e511a451803556c01c54227',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': HC_OBSERVATION,
        'frozen': {
            'package_profile': 'nuwa-ufs-hc-chmh-20261113-r1',
            'args': '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0',
            'kernel': 'out/nuwa-ufs-hc-chmh-20261113-r1/kernel.macho', 'kernel_bytes': 55545856,
            'kernel_sha256': '134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5',
            'fat': 'out/nuwa-ufs-hc-chmh-20261113-r1/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': '48b463403dffe1cb82c11becc0f6f2e8ba83a4f1c269aea33b97370065471475',
            'adt': 'out/nuwa-ufs-hc-chmh-20261113-r1/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': '58ffccb0f46e4cd47bca352341508e9daefcaed468fef85c9ff7f3ee814a3ea7',
            'derived': 'out/nuwa-ufs-hc-chmh-20261113-r1/record.json',
            'derived_sha256': '46644bdb2306c22e22fa03e713c0efb824ea5b8e6b6ae0de500bd0acbfe6e41f',
            'report': 'out/nuwa-ufs-hc-chmh-20261113-r1/outer-record.json',
            'report_sha256': '249bb56740ef4f98cb19fad3446372dfdf31507b84fdca0cadac1b252c5a8648',
            'audit': 'out/nuwa-ufs-hc-chmh-20261113-r1/audit.json',
            'audit_sha256': 'c14742bf8367871a590bb3bf782f5757a04107995e658c2557e4084abefbf926',
            'layout': 'out/nuwa-ufs-hc-chmh-20261113-r1/layout.json',
            'layout_sha256': 'c8c2c19aacc25bee61463ce683623d58a1576b6f48b2591fcbee36dc3558bc39',
            'provenance': 'out/nuwa-ufs-hc-chmh-20261113-r1/provenance.json',
            'provenance_sha256': '51ca2da295324f6d900129c20ea883551f71ad9c02b76acc84e5feac2b11125e',
            'config': 'out/nuwa-ufs-hc-chmh-20261113-r1/unixnu.toml', 'config_bytes': 451,
            'config_sha256': '30984f0efac472a095e551084c799487537c596db4ba1eeef13c47ab56d4cf81',
            'source': 'scripts/build-hc-observe-chmh.py',
            'source_sha256': 'c00342ea8657700b1d82040e07b0fc99fc4baee2e096bb1d07aa976b11ad1fd9',
            'kernel_path': 'out/nuwa-ufs-hc-observe-20261113/run-r7/kernel.macho',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'parent_config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'chmh_hex': 'c2b2aa90d7814beb884c17f9bd19727476b9fa3267bb82847e76419e96f15cbeefff1a8e5bed8120e02878d34a45ed29',
            'evidence': {
                'kernel_manifest': {'path': 'out/nuwa-ufs-hc-observe-20261113/run-r7/manifest.json', 'sha256': 'f6cc009bf5ea7d246e7f744fea5e8a7738470a9852e70fc3df0a83f5caf13553'},
                'two_findings': {'path': 'out/nuwa-ufs-hc-observe-20261113/run-r7/two-findings.json', 'sha256': '6cb1ddbe8496fb3bac9754b67f3335f81312ce86ac255a5551923f0119bed789'},
                'provenance': {'path': 'out/nuwa-ufs-hc-observe-20261113/run-r7/provenance.json', 'sha256': '7831a34223a46425163d32a2ab7d3c1d12b444b9db5d02ba7898d09e8da736ce'},
            },
        },
    },
    NOP_PROFILE: {
        'candidate': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/vendor_boot.img',
        'candidate_sha256': 'd9550552966ac18d0d615870750a67225690b0ecc3ad1d9d62160d61279b3ee7',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': NOP_OBSERVATION,
        'frozen': {
            'package_profile': 'nuwa-ufs-preserved-nop-chmh-20261114-r1',
            'args': '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0',
            'kernel': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/kernel.macho', 'kernel_bytes': 55549952,
            'kernel_sha256': '05ebb53baf0d98aa0f189b8c1569e7375f6403c20b3df2c739734ba459488944',
            'fat': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': '0a1d1f7eda4c17bfe0edb3e8e0b62bb9616198719924f34521a0a0654a89a606',
            'adt': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': 'daddb05628d0541697bbe2ad3a207cf261670c5718f497e2584bbfa2eea71a24',
            'derived': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/record.json',
            'derived_sha256': 'e2e4f85f0bcdec1e8b10446f8b363e6d4226b0b316d52344edd1f8abcdd5bf43',
            'report': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/outer-record.json',
            'report_sha256': '3c600870caccc75eac928391494ace4fe9fb0163f8a65fbdc0b7c6a5d03baa99',
            'audit': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/audit.json',
            'audit_sha256': 'c03d813978c574b629550ceccc2bb3b3c2474006ca4eb20f33480f829a12a923',
            'layout': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/layout.json',
            'layout_sha256': 'c8c2c19aacc25bee61463ce683623d58a1576b6f48b2591fcbee36dc3558bc39',
            'provenance': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/provenance.json',
            'provenance_sha256': '0a80669bb2bc638d3a8933230c7a4c34f314f12474e56b6357c23b7ee4d28b91',
            'config': 'out/nuwa-ufs-preserved-nop-chmh-20261114-r1/unixnu.toml', 'config_bytes': 451,
            'config_sha256': '30984f0efac472a095e551084c799487537c596db4ba1eeef13c47ab56d4cf81',
            'source': 'scripts/build-preserved-nop-chmh.py',
            'source_sha256': '5690df2d2fa1e98e1bf700cf2a13b7aa4f80724148f4ce863f57abb04f85dc6b',
            'kernel_path': 'out/nuwa-ufs-preserved-nop-exec-20261114/run-r2/kernel.macho',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'parent_config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'chmh_hex': '9c536cf3983cc039106c5a438184a505f577bd2cd0c30eb28bb05a44e490ead563df77af3f2dcea8e976b97983740a9b',
            'evidence': {},
        },
    },
    SID_PROFILE: {
        'candidate': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/vendor_boot.img',
        'candidate_sha256': 'f52fec8c5dbd10dfe072368f5a6a4b0e136a69a50075db38f71278a44cce7763',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': SID_OBSERVATION,
        'frozen': {
            'package_profile': 'nuwa-ufs-sid-domain-chmh-20261114-r1',
            'args': '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0',
            'kernel': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/kernel.macho', 'kernel_bytes': 55545856,
            'kernel_sha256': '8610b862b2801b5e5730c227b518f76b3969bde351b2416acf786f84f946d0e4',
            'fat': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': 'e863e81cf06b443047bf8f4ccfdf2366c92af263bc3ee0f82c9040d8b68da08b',
            'adt': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': '317b0530b62c8685849a01e63f484a83ccbe4ea51f55c3862064feb8796cc31c',
            'derived': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/record.json',
            'derived_sha256': '772164112ec27889e0df3b3d77f708742ce1ff4f6803ff6fd336197c309567a4',
            'report': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/outer-record.json',
            'report_sha256': 'f6c7c47d041bea454e148ebd032f1f74472ce86f3dd131648fec059907c92664',
            'audit': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/audit.json',
            'audit_sha256': 'd46393df4ce3f9379943670d2c7e0081f4a8df56e1f1a0bfad0c3e136c732768',
            'layout': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/layout.json',
            'layout_sha256': 'c8c2c19aacc25bee61463ce683623d58a1576b6f48b2591fcbee36dc3558bc39',
            'provenance': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/provenance.json',
            'provenance_sha256': 'fa34875e778aa800724a54445870269656346d496efcb48163468e20ef4068ed',
            'config': 'out/nuwa-ufs-sid-domain-chmh-20261114-r1/unixnu.toml', 'config_bytes': 451,
            'config_sha256': '30984f0efac472a095e551084c799487537c596db4ba1eeef13c47ab56d4cf81',
            'source': 'scripts/build-sid-domain-chmh.py',
            'source_sha256': 'be4545c7937a5ac9033cd5ee2f1f1a4c19e1de6aab9b78487ef67e4954dbb267',
            'kernel_path': 'out/nuwa-ufs-sid-domain-20261114/run/kernel.macho',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'parent_config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'chmh_hex': 'a0c6190eef9cacd72b7b9e17e172681759f0fc6126493a9b094c6a8f9d910bedb576ffbf3fabd4e15e294515317a444e',
            'evidence': {},
        },
    },
    QUEUE_PROFILE: {
        'candidate': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/vendor_boot.img',
        'candidate_sha256': '44205ea9c123afd1a13109c98329f2c8c0d96e9c2a1021ff9b82cc3920248dc9',
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': QUEUE_OBSERVATION,
        'frozen': {
            'package_profile': 'nuwa-ufs-queue-five-chmh-20261114-r1',
            'args': '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0',
            'kernel': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/kernel.macho', 'kernel_bytes': 55545856,
            'kernel_sha256': 'eff66a33a097568e3c44f84fb1a7f3365889613cdcb629583944f2c99022012b',
            'fat': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/payload.img', 'fat_bytes': 67108864,
            'fat_sha256': 'eb30a7d4e2354b4618a80fc6d50becdf4fff2a6820aec7e44a1a27f8d8deaae9',
            'adt': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/derived.adt', 'adt_bytes': 13340,
            'adt_sha256': 'f5ee7ad8f1b1fd144d984859c1d94597fb449aa765c0c666f4660554ac4012df',
            'derived': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/record.json',
            'derived_sha256': '9a7e0662564606663f9ad631b046945bd18d313ef3720beee843d74ea3a90a69',
            'report': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/outer-record.json',
            'report_sha256': 'ff8221fcfceae6454c9e6923f6c37b5c56552174c6e19a79c9990abdd18479ce',
            'audit': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/audit.json',
            'audit_sha256': '58e1fcaf919b010db77d55a35b07c8db21d9db9a690f7de63b0021c7b30b27a9',
            'layout': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/layout.json',
            'layout_sha256': 'c8c2c19aacc25bee61463ce683623d58a1576b6f48b2591fcbee36dc3558bc39',
            'provenance': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/provenance.json',
            'provenance_sha256': '76eb148e05a893181d46904c647e378acc8a13ef696331366ae286b94476c8a3',
            'config': 'out/nuwa-ufs-queue-five-chmh-20261114-r1/unixnu.toml', 'config_bytes': 451,
            'config_sha256': '30984f0efac472a095e551084c799487537c596db4ba1eeef13c47ab56d4cf81',
            'source': 'scripts/build-queue-five-chmh.py',
            'source_sha256': '579f2f9d8928a27bce53b84d0e3881b19e957a87b9f0cf81cc13024b4b887eef',
            'kernel_path': 'out/nuwa-ufs-queue-five-20261114/run/kernel.macho',
            'parent_fat_sha256': '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c',
            'parent_record_sha256': 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57',
            'parent_adt_sha256': '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
            'parent_config_sha256': '7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931',
            'trust_sha256': '367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e',
            'chmh_hex': '903e2f042fd56440fa7da925a4efc32a755b70ebdbdd75c1c1841779e69a630a1c9b1e7c47299db71ddc03c5bea598fd',
            'evidence': {},
        },
    },
}

_root_dir = 'out/nuwa-ufs-apfs-root-chmh-20261114-r2/'
_root_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_root_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261114-r2',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7',
    'kernel_bytes': 55545856, 'kernel_sha256': '809587d53fef9b0b3e9b2054a9e06c649d3c66cd45be3fafbe632ac575cb0acc',
    'kernel_path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/kernel.macho',
    'fat_sha256': '04dc73dbaa3be025db690318c3f28fcedbd05c4ee09f94a426f27f023b1ab190',
    'adt_bytes': 13548, 'adt_sha256': '88a41d7f377207a50e564ee76dd0f822d77711593c34dab04313a912cab8ab1b',
    'derived_sha256': '0d3df7c94a5a424e925c80475b6f6e706151a8e1669288d11576766ba23d3819',
    'report_sha256': '57395f2c381883dfc2bd6caa5ad74d9db9983dcba14472ed817c5027f57498a9',
    'audit_sha256': 'aaba93a21ae540e9a11fe0659681f27e3b5c3fc44d39b8814df3ba12db1ebc28',
    'layout_sha256': 'ef22f065b227e0e316a5a30767cee038e494e69cbe3d96e6b2178d9cd5939de3',
    'provenance_sha256': 'f63a952af17a236d480d4bf328580d44147f67203a4d1b69a3739dfb4aa2b0f6',
    'config_bytes': 504, 'config_sha256': '9600826a392f124f949c4b72a83170c3cda2e04b3b4dfc808a678f0884c34a40',
    'source': 'scripts/build-ufs-apfs-root-chmh.py',
    'source_sha256': 'ee3f5e97cd990f7df731c7b9f634dcacdc635cf8df565d6851372edd10b6fc8e',
    'chmh_hex': 'cb24f1ef2ea31cc1f5704429b17637970c0c66aad15e74f429b5f7c318fdebdfae04e8b309ff00c344139a44f5123372',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _root_frozen[_key] = _root_dir + _name
PROFILES['ufs-apfs-root-20261114-r2'] = {
    'candidate': _root_dir + 'vendor_boot.img',
    'candidate_sha256': '72a4e8eaa420e6bff6713518126452d60a13329905833ef5a9b41dd1d0b279a9',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not mount success. Failures display panic text; success has only '
                    'bounded ROOT_ENTER, WINDOW_START, MEDIA_WAIT, MEDIA_READY and ROOT_PUBLISHED markers. '
                    'MEDIA_READY and ROOT_PUBLISHED do not prove mounting. Judge mount outcome from existing '
                    'panic or later evidence. Userdata installation is separate and not performed here. '
                    'No automatic retry; manually return to bootloader and restore separately with authorization.'),
    'frozen': _root_frozen,
}
# r3: same packaging path, kernel rebuilt with the nuwa-only root-auth skip.
_r3_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r3/'
_r3_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_r3_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r3',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7',
    'kernel_bytes': 55545856, 'kernel_sha256': 'f0d53c88d7ec89016399e1cef3d6f797b113dd98d136015535efbcdd0e6d8596',
    'kernel_path': 'out/nuwa-root-auth-skip-20261115-r1/kernel.macho',
    'fat_sha256': 'ece5facdb814070068bf6b217242fe2c42476ae218de8a1b2928e5e89ebd66d3',
    'adt_bytes': 13548, 'adt_sha256': '0a9ef2bbf0b4fbb558973f5ac0dd01e2c94a74d38592b5ce52de0832438e4ab7',
    'derived_sha256': '841f85e8e7406edc443453dfed93619bc06032f4369bbc5382da64b734b7e48c',
    'report_sha256': '9ad269cefc268c13cb4f8cee545e914f05fa9ecea70ae90b6ed1c42a53a68bf2',
    'audit_sha256': '680dfb5e733c4f040d7669e30aafaf5a6f430565e210db9e9a958045398e3a90',
    'layout_sha256': 'ef22f065b227e0e316a5a30767cee038e494e69cbe3d96e6b2178d9cd5939de3',
    'provenance_sha256': '2653c14497c03e2220da873479ada80ca8372cc0ad0d13c885294322d28f7b8d',
    'config_bytes': 504, 'config_sha256': '9600826a392f124f949c4b72a83170c3cda2e04b3b4dfc808a678f0884c34a40',
    'source': 'scripts/build-ufs-apfs-root-chmh.py',
    'source_sha256': 'ee3f5e97cd990f7df731c7b9f634dcacdc635cf8df565d6851372edd10b6fc8e',
    'chmh_hex': '194ce232ac76a3e3ec1b41efb2393976ea061014fccd18d6214d13884e091e6f25d40bf36f1b63ddb4ff4c7a887a5d03',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r3_frozen[_key] = _r3_dir + _name
PROFILES['ufs-apfs-root-20261115-r3'] = {
    'candidate': _r3_dir + 'vendor_boot.img',
    'candidate_sha256': '1caf930a4b7fa954abc1ffceb5be4edb8e92a905579dfd2c2e03d99c9b2893de',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not mount success. Failures display panic text; success has only '
                    'bounded ROOT_ENTER, WINDOW_START, MEDIA_WAIT, MEDIA_READY and ROOT_PUBLISHED markers. '
                    'MEDIA_READY and ROOT_PUBLISHED do not prove mounting. Judge mount outcome from existing '
                    'panic or later evidence. Userdata installation is separate and not performed here. '
                    'No automatic retry; manually return to bootloader and restore separately with authorization.'),
    'frozen': _r3_frozen,
}
# r8: r7's kernel and args with the two-module trust cache bundle (StaticTrustCache +
# Cryptex1,SystemTrustCache of the same 20H392 donor). Only the trust input changes
# against r7, so the CHMH identity, the ADT and the FAT/outer hashes are re-derived.
_r8_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r8/'
_r8_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_r8_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r8',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7',
    'kernel_bytes': 55545856, 'kernel_sha256': '2561c0c527bfa85dda4de218f933eb17a14c821edd20573755aa7b6efdb7872b',
    'kernel_path': 'out/nuwa-exec-skip-20261115-r6/kernel.macho',
    'fat_sha256': 'd250c6bc2c2448323e37c41af007c45e118cce988d2365cd17cbc55a1c0e7904',
    'adt_bytes': 13548, 'adt_sha256': '5752bd3c1ce01a9e0d43965ea295ad8d775a1a9226e43f5e5f758eb549121e6b',
    'derived_sha256': '070106f1e84ede06429f9145179d960dd99f417b58ee9a7993a107e901a090c6',
    'report_sha256': '051b626f053e857c3e05d37a3d3faa7611047b206d3be2a596526202e2af5be5',
    'audit_sha256': '16404e5a6897d345f871ed23ab2a8883b54ebf2ccd46dddd615874cf0d2ad817',
    'layout_sha256': '97db13bd7189fb0c0bfd1502c6b7992355ab06626f5df37e5545b9eb54ed6181',
    'provenance_sha256': '3746f5cf7606cd4c0e2ca01d30d692f6789b13b1783ebc48c1e6528ef12fdfc4',
    'config_bytes': 504, 'config_sha256': '9600826a392f124f949c4b72a83170c3cda2e04b3b4dfc808a678f0884c34a40',
    'source': 'scripts/build-ufs-apfs-root-chmh-r8.py',
    'source_sha256': 'fcf864004e1a203a34edfe77b2aa7b23f7550ea53bfe7c18bfe3ce2c8be46c9f',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': 'f5b5f96a55a1639fd4263338a3457b90ac3d9a2368756404ee1055c437313313fa1f5353e23934532ad8324e0fd14a11',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r8_frozen[_key] = _r8_dir + _name
PROFILES['ufs-apfs-root-20261115-r8'] = {
    'candidate': _r8_dir + 'vendor_boot.img',
    'candidate_sha256': '8e09fae228f985eb4efc7bcf9d8c2c55b594f499af1f48a91f53db431e1ff66e',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not mount success. Failures display panic text; success has only '
                    'bounded ROOT_ENTER, WINDOW_START, MEDIA_WAIT, MEDIA_READY and ROOT_PUBLISHED markers. '
                    'MEDIA_READY and ROOT_PUBLISHED do not prove mounting. Judge mount outcome from existing '
                    'panic or later evidence. Userdata installation is separate and not performed here. '
                    'No automatic retry; manually return to bootloader and restore separately with authorization.'),
    'frozen': _r8_frozen,
}
# r9: r8's package (two-module trust cache bundle, r7 args) with the observation
# kernel: cyan band-3 exec completion and orange band-15 initproc first system call
# on top of the r7 baseline.
_r9_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r9/'
_r9_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_r9_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r9',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7',
    'kernel_bytes': 55545856, 'kernel_sha256': 'b1029f3d32d1db3ae0bca1b85a665a6758c608ee9f9a5aaffbc55589f83d3764',
    'kernel_path': 'out/nuwa-observe-20261115-r1/kernel.macho',
    'fat_sha256': '7587079c8060cb3cd8a5e4c448e19af3d8e1d4404f4ba29283b8931bc4dede65',
    'adt_bytes': 13548, 'adt_sha256': '9d76537a5743fc973e9bfcade2115d209b125ba1531a76f7efa938f10c212b91',
    'derived_sha256': '5ea8b6756f79e3f9ca1ab4ae096804199f0cc9920fba0dea27e18407177ce8da',
    'report_sha256': '83d207de34aa328461d2863bd18acf653458996d53ab747ef6564c09a27407dc',
    'audit_sha256': '1f0b5785f52010f7b70f5451d442c7407172fe1bff34f4867afcb2095376cd8a',
    'layout_sha256': '1e5626384c808ec94169f092e2b6c1c1e6012fdd8c07a86c18131d264d92c40a',
    'provenance_sha256': '9708d9575c287a239f91fec93881dee753e4327ed671ddbe2b48df44aef34b2f',
    'config_bytes': 504, 'config_sha256': '9600826a392f124f949c4b72a83170c3cda2e04b3b4dfc808a678f0884c34a40',
    'source': 'scripts/build-ufs-apfs-root-chmh-r9.py',
    'source_sha256': '5b3ade1fff26307d5c2d12181e0f424d5244087132ad2d211bbc9f0b42479462',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '841f20fe7b300d5c74fb2f64c1696dce9497d742c2d56780118202b432d1a35944425fc222795fca06c43c5959b3da95',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r9_frozen[_key] = _r9_dir + _name
PROFILES[ROOT_PROFILE] = {
    'candidate': _r9_dir + 'vendor_boot.img',
    'candidate_sha256': '37b665da4629f69ad97fca1335c91f99f81780c896ebceac4dd419264de8667f',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not mount success. Failures display panic text; success has only '
                    'bounded ROOT_ENTER, WINDOW_START, MEDIA_WAIT, MEDIA_READY and ROOT_PUBLISHED markers. '
                    'MEDIA_READY and ROOT_PUBLISHED do not prove mounting. Judge mount outcome from existing '
                    'panic or later evidence. Userdata installation is separate and not performed here. '
                    'No automatic retry; manually return to bootloader and restore separately with authorization.'),
    'frozen': _r9_frozen,
}


class Stop(Exception):
    """Messages must contain only fixed host diagnostics, never device output."""


def require(condition, message):
    if not condition:
        raise Stop(message)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def chmh_record_path_matches(value, repo, relative):
    """Match only the exact record in this repo, including the fixed WSL/Windows mapping."""
    if type(value) is not str or not value or '\x00' in value:
        return False
    parts = re.split(r'[/\\]', value)
    if any(part in ('.', '..') for part in parts):
        return False
    win = PureWindowsPath(value)
    posix = PurePosixPath(value)
    rel = PurePosixPath(relative)
    if not win.drive and not win.root and not posix.is_absolute():
        return PureWindowsPath(value) == PureWindowsPath(*rel.parts)
    expected = Path(repo) / relative
    if os.name == 'nt' and win.is_absolute() and win == PureWindowsPath(str(expected)):
        return True
    if os.name != 'nt' and posix.is_absolute() and posix == PurePosixPath(str(expected)):
        return True
    # Cross-OS mapping is restricted to this project's known D: checkout.
    windows_root = PureWindowsPath('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
    wsl_root = PurePosixPath('/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa')
    known_repo = (PureWindowsPath(str(repo)) == windows_root if os.name == 'nt'
                  else PurePosixPath(str(repo)) == wsl_root)
    if not known_repo:
        return False
    return ((win.is_absolute() and win == windows_root.joinpath(*rel.parts)) or
            (posix.is_absolute() and posix == wsl_root.joinpath(*rel.parts)))


class Run:
    def __init__(self, repo, run_id, adb, fastboot, runner=None, pause=None, profile=STOP_PROFILE):
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}', run_id) is not None,
                'invalid run-id')
        require(profile in PROFILES, 'unknown frozen profile')
        self.repo, self.run_id = Path(repo).resolve(), run_id
        self.directory = self.repo / 'out' / ('pmap-ret-run-' + run_id)
        self.remote = '/data/local/tmp/pmap-ret-run-' + run_id
        self.profile = profile
        self.settings = dict(PROFILES[profile])
        self.frozen = self.settings.get('frozen')
        self.size = self.settings['bytes']
        self.stock_sha256 = self.settings['stock_sha256']
        self.candidate_sha256 = self.settings['candidate_sha256']
        self.r4_sha256 = self.settings['r4_sha256']
        self.r4_bytes = self.settings['r4_bytes']
        self.observation = self.settings['observation']
        self.candidate = self.repo / self.settings['candidate']
        self.r4 = self.repo / '.cache/boot-stage12-v4-r4.img'
        self.backup = self.directory / 'vendor_boot_b.stock.img'
        self.adb, self.fastboot = str(adb), str(fastboot)
        self.runner = runner if runner is not None else subprocess.run
        self.pause = pause if pause is not None else time.sleep
        self.serials = set()
        self.events = []
        self.phase = None
        self.wait_deadline = None

    def identity(self):
        value = {'run_id': self.run_id, 'profile': self.profile, 'candidate': self.settings['candidate'],
                 'candidate_sha256': self.candidate_sha256, 'candidate_bytes': self.size,
                 'stock_sha256': self.stock_sha256, 'r4_sha256': self.r4_sha256,
                 'r4_bytes': self.r4_bytes}
        if self.frozen is not None:
            value['frozen'] = dict(self.frozen)
        return value

    def require_identity(self):
        path = self.directory / 'run-identity.json'
        if not path.exists():
            require(not path.is_symlink(), 'linked/invalid run identity')
            # Untouched historical runs have no identity and stay stop-only; never migrate them.
            require(self.profile == STOP_PROFILE, 'legacy run is stop-profile only; no migration/overwrite')
            return None
        require(path.is_file() and not path.is_symlink(), 'linked/invalid run identity')
        try:
            loaded = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise Stop('run identity unreadable') from None
        require(loaded == self.identity(), 'run profile/candidate/r4 identity mismatch')
        return loaded

    def sanitize(self, value):
        text = json.dumps(value, ensure_ascii=True)
        for serial in sorted(self.serials, key=len, reverse=True):
            text = text.replace(json.dumps(serial, ensure_ascii=True)[1:-1], '<REDACTED>')
        return json.loads(text)

    def create(self, name, value):
        require(not self.directory.is_symlink(), 'run directory must not be a symlink')
        try:
            with (self.directory / name).open('x', encoding='utf-8') as stream:
                json.dump(self.sanitize(value), stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise Stop('exclusive file already exists; no replay') from None

    def state(self):
        found = [state for state in STATES if (self.directory / ('state-' + state + '.json')).exists()]
        return found[-1] if found else None

    def advance(self, state):
        previous = self.state()
        require(previous is None or STATES.index(state) > STATES.index(previous), 'state regression/replay refused')
        self.create('state-' + state + '.json', {'state': state, 'previous': previous})

    def check_file(self, path, size, expected):
        require(path.is_file() and not path.is_symlink(), 'missing or linked frozen input/backup')
        require(path.stat().st_size == size and file_hash(path) == expected, 'frozen input/backup size/hash mismatch')

    def host_inputs(self):
        self.check_file(self.candidate, self.size, self.candidate_sha256)
        self.check_file(self.r4, self.r4_bytes, self.r4_sha256)
        if self.profile == AMNM_PROFILE:
            self.amnm_inputs()
            return
        if self.profile == CHMH_PROFILE:
            self.chmh_inputs()
            return
        if self.profile == PTHREAD_PROFILE:
            self.pthread_inputs()
            return
        if self.profile in (PMGR_PROFILE, HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE, ROOT_PROFILE):
            self.pmgr_inputs()
            return
        if self.frozen is not None:
            evidence = self.repo / self.frozen['evidence']
            require(evidence.is_file() and not evidence.is_symlink(), 'missing or linked outer evidence')
            try:
                record = json.loads(evidence.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                raise Stop('outer evidence unreadable') from None
            require(isinstance(record, dict), 'outer evidence must be a JSON object')
            require(record.get('vendor_ramdisk_sha256') == self.frozen['fat_sha256'],
                    'outer evidence vendor ramdisk does not match frozen FAT')
            binding = record.get('input_binding')
            require(isinstance(binding, dict), 'outer evidence input_binding must be an object')
            require(binding.get('fat_sha256') == self.frozen['fat_sha256'],
                    'outer evidence input FAT does not match frozen FAT')
            hashes = record.get('fat_hashes')
            require(isinstance(hashes, dict), 'outer evidence lacks FAT hashes')
            require(record.get('profile') == self.profile and
                    record.get('vendor_boot_sha256') == self.candidate_sha256 and
                    record.get('vendor_boot_bytes') == self.size and
                    record.get('kernel_sha256') == self.frozen['kernel_sha256'] and
                    record.get('adt_sha256') == self.frozen['adt_sha256'] and
                    record.get('args_exact') == self.frozen['args'] and
                    hashes.get('Payloads/kernel.macho') == self.frozen['kernel_sha256'] and
                    hashes.get('Payloads/kernel.macho.adt') == self.frozen['adt_sha256'],
                     'outer evidence does not bind the frozen candidate/kernel/ADT/args')

    def chmh_inputs(self):
        f = self.frozen
        self.check_file(self.repo / f['fat'], f['fat_bytes'], f['fat_sha256'])
        self.check_file(self.repo / f['adt'], f['adt_bytes'], f['adt_sha256'])
        records = {}
        for key in ('derived', 'report', 'audit', 'audit_source'):
            path = self.repo / f[key]
            require(path.is_file() and not path.is_symlink(), 'missing or linked CHMH evidence')
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == f[key + '_sha256'], 'CHMH evidence hash mismatch')
            if key != 'audit_source':
                try:
                    records[key] = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise Stop('CHMH evidence unreadable') from None
                require(isinstance(records[key], dict), 'CHMH evidence must be object')
        d, r, a = (records[k] for k in ('derived', 'report', 'audit'))
        require(d.get('profile') == self.profile and d.get('type') == 'experimental-unauthenticated-boot-set-identity'
                and d.get('device_release') is False and d.get('authentication') == 'NOT REACHED'
                and d.get('derived_adt_sha256') == f['adt_sha256'] and d.get('derived_adt_bytes') == f['adt_bytes']
                and d.get('payload_sha256') == f['fat_sha256'], 'CHMH derived identity mismatch')
        binding = d.get('inputs_sha256')
        require(isinstance(binding, dict) and binding.get('kernel') == f['kernel_sha256']
                and binding.get('loader') == self.r4_sha256
                and binding.get('args') == hashlib.sha256(f['args'].encode()).hexdigest(),
                'CHMH material input mismatch')
        for item in (r, a):
            members = item.get('members_sha256')
            require(item.get('outer_sha256') == self.candidate_sha256 and item.get('ramdisk_sha256') == f['fat_sha256']
                    and isinstance(members, dict) and members.get('kernel') == f['kernel_sha256']
                    and members.get('parent-adt') == f['adt_sha256'], 'CHMH outer audit mismatch')
        require(r.get('profile') == self.profile and r.get('record_sha256') == f['derived_sha256']
                and chmh_record_path_matches(r.get('record_path'), self.repo, f['derived'])
                and r.get('device_release') is False and r.get('authentication') == 'NOT REACHED',
                'CHMH outer report identity mismatch')

    def pthread_inputs(self):
        f = self.frozen
        for key in ('kernel', 'fat', 'adt'):
            self.check_file(self.repo / f[key], f[key + '_bytes'], f[key + '_sha256'])
        records = {}
        for key in ('derived', 'report', 'audit', 'layout', 'audit_source'):
            path = self.repo / f[key]
            require(path.is_file() and not path.is_symlink(), 'missing or linked pthread evidence')
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == f[key + '_sha256'], 'pthread evidence hash mismatch')
            if key != 'audit_source':
                try:
                    records[key] = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise Stop('pthread evidence unreadable') from None
                require(isinstance(records[key], dict), 'pthread evidence must be object')
        provenance = {}
        for key, item in f['evidence'].items():
            path = self.repo / item['path']
            require(path.is_file() and not path.is_symlink() and file_hash(path) == item['sha256'],
                    'pthread provenance hash mismatch')
            try:
                provenance[key] = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeDecodeError):
                raise Stop('pthread provenance unreadable') from None
            require(isinstance(provenance[key], dict), 'pthread provenance must be object')
        d, r, a, layout = (records[k] for k in ('derived', 'report', 'audit', 'layout'))
        inputs = {'fat': f['parent_fat_sha256'], 'parent-record': f['parent_record_sha256'],
                  'loader': self.r4_sha256, 'args': hashlib.sha256(f['args'].encode()).hexdigest(),
                  'kernel': f['kernel_sha256'], 'parent-adt': f['parent_adt_sha256'],
                  'trust': f['trust_sha256'], 'config': f['config_sha256']}
        material = bytearray(b'Nuwa.HostBootSetIdentity.v1\0')
        for key in ('kernel', 'loader', 'trust', 'args', 'parent-adt'):
            label = key.encode('ascii')
            material.extend(bytes([len(label)]) + label + bytes.fromhex(inputs[key]))
        require(d.get('profile') == f['package_profile'] and
                d.get('type') == 'experimental-unauthenticated-boot-set-identity' and
                d.get('device_release') is False and d.get('authentication') == 'NOT REACHED' and
                d.get('inputs_sha256') == inputs and d.get('evidence') == f['evidence'] and
                d.get('material_hex') == bytes(material).hex() and
                d.get('chmh_hex') == f['chmh_hex'] == hashlib.sha384(material).hexdigest() and
                d.get('derived_adt_sha256') == f['adt_sha256'] and d.get('derived_adt_bytes') == f['adt_bytes'] and
                d.get('payload_sha256') == f['fat_sha256'] and d.get('layout') == layout,
                'pthread derived material/identity mismatch')
        expected_members = {'kernel': f['kernel_sha256'], 'parent-adt': f['adt_sha256'],
                            'trust': f['trust_sha256'], 'config': f['config_sha256']}
        for item in (r, a):
            require(item.get('outer_sha256') == self.candidate_sha256 and
                    item.get('ramdisk_sha256') == f['fat_sha256'] and
                    item.get('members_sha256') == expected_members and
                    item.get('record_sha256') == f['derived_sha256'], 'pthread outer audit mismatch')
        require(r.get('profile') == f['package_profile'] and
                chmh_record_path_matches(r.get('record_path'), self.repo, f['derived']) and
                r.get('device_release') is False and r.get('authentication') == 'NOT REACHED' and
                r.get('loader_sha256') == self.r4_sha256 and
                r.get('stock_sha256') == '5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23' and
                r.get('original_backup_sha256') == self.stock_sha256 and
                r.get('original_backup_is_template') is False, 'pthread outer provenance mismatch')
        rm, ra, pa, pp = (provenance[k] for k in ('renderer_manifest', 'renderer_audit', 'prelink_audit', 'prelink_provenance'))
        require(rm.get('input', {}).get('sha256') == f['pristine_sha256'] and
                rm.get('output', {}).get('sha256') == f['kernel_sha256'] and
                ra.get('output_sha256') == f['kernel_sha256'] and ra.get('pthread_bindings_checked') == 95 and
                ra.get('pthread_metadata_unchanged') is True and
                pa.get('kernel_sha256') == f['pristine_sha256'] and pa.get('pthread_bindings') == 95 and
                pa.get('binding_values_match') is True and pp.get('output', {}).get('sha256') == f['pristine_sha256'],
                'pthread renderer/prelink provenance mismatch')

    def pmgr_inputs(self):
        f = self.frozen
        for key in ('kernel', 'fat', 'adt', 'config'):
            self.check_file(self.repo / f[key], f[key + '_bytes'], f[key + '_sha256'])
        expected_args = (PROFILES[ROOT_PROFILE]['frozen']['args'] if self.profile == ROOT_PROFILE else
                         '-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0'
                         if self.profile in (HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE) else '-v serial=3 nuwa-pmgr=2')
        require(f['args'] == expected_args and
                (self.repo / f['config']).read_bytes().count(('args = "' + expected_args + '"').encode()) == 1,
                'PMGR exact mode/args mismatch')
        records = {}
        for key in ('derived', 'report', 'audit', 'layout', 'provenance', 'source'):
            path = self.repo / f[key]
            require(path.is_file() and not path.is_symlink() and file_hash(path) == f[key + '_sha256'],
                    'PMGR evidence/source hash mismatch')
            if key != 'source':
                try:
                    records[key] = json.loads(path.read_bytes())
                except (ValueError, UnicodeDecodeError):
                    raise Stop('PMGR evidence unreadable') from None
                require(isinstance(records[key], dict), 'PMGR evidence must be object')
        for item in f['evidence'].values():
            path = self.repo / item['path']
            require(path.is_file() and not path.is_symlink() and file_hash(path) == item['sha256'],
                    'PMGR provenance hash mismatch')
        inputs = {'fat': f['parent_fat_sha256'], 'parent-record': f['parent_record_sha256'],
                  'loader': self.r4_sha256, 'args': hashlib.sha256(f['args'].encode()).hexdigest(),
                  'kernel': f['kernel_sha256'], 'parent-adt': f['parent_adt_sha256'],
                  'trust': f['trust_sha256'], 'config': f['config_sha256'],
                  'parent-config': f['parent_config_sha256']}
        material = bytearray(b'Nuwa.HostBootSetIdentity.v1\0')
        for key in ('kernel', 'loader', 'trust', 'args', 'parent-adt'):
            label = key.encode('ascii')
            material.extend(bytes([len(label)]) + label + bytes.fromhex(inputs[key]))
        d, r, a, layout, provenance = (records[k] for k in ('derived', 'report', 'audit', 'layout', 'provenance'))
        require(d.get('profile') == f['package_profile'] and d.get('type') == 'experimental-unauthenticated-boot-set-identity'
                and d.get('authentication') == 'NOT REACHED' and d.get('device_release') is False
                and d.get('inputs_sha256') == inputs and d.get('evidence') == f['evidence']
                and d.get('material_hex') == material.hex() and d.get('chmh_hex') == f['chmh_hex'] == hashlib.sha384(material).hexdigest()
                and d.get('derived_adt_sha256') == f['adt_sha256'] and d.get('derived_adt_bytes') == f['adt_bytes']
                and d.get('payload_sha256') == f['fat_sha256'] and d.get('layout') == layout,
                'PMGR derived material/identity mismatch')
        require(provenance.get('profile') == f['package_profile'] and provenance.get('kernel_sha256') == f['kernel_sha256']
                and provenance.get('kernel_path') == (f['kernel_path'] if self.profile in (HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE, ROOT_PROFILE)
                                                       else 'out/nuwa-pmgr-kernel-20261113-r5/kernel.macho')
                and provenance.get('args') == f['args'] and provenance.get('inputs_sha256') == inputs
                and provenance.get('evidence') == f['evidence'] and provenance.get('device_release') is False
                and provenance.get('authentication') == 'NOT REACHED', 'PMGR provenance identity mismatch')
        members = {'kernel': f['kernel_sha256'], 'parent-adt': f['adt_sha256'],
                   'trust': f['trust_sha256'], 'config': f['config_sha256']}
        for item in (r, a):
            require(item.get('outer_sha256') == self.candidate_sha256 and item.get('ramdisk_sha256') == f['fat_sha256']
                    and item.get('members_sha256') == members and item.get('record_sha256') == f['derived_sha256'],
                    'PMGR outer audit mismatch')
        require(r.get('profile') == f['package_profile'] and chmh_record_path_matches(r.get('record_path'), self.repo, f['derived'])
                and r.get('device_release') is False and r.get('authentication') == 'NOT REACHED'
                and r.get('loader_sha256') == self.r4_sha256 and r.get('original_backup_sha256') == self.stock_sha256
                and r.get('stock_sha256') == '5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23'
                and r.get('original_backup_is_template') is False, 'PMGR outer provenance mismatch')

    def amnm_inputs(self):
        f = self.frozen
        self.check_file(self.repo / f['fat'], f['fat_bytes'], f['fat_sha256'])
        source = self.repo / f['audit_source']
        require(source.is_file() and not source.is_symlink() and file_hash(source) == f['audit_source_sha256'],
                'AMNM audit source hash mismatch')
        records = {}
        for key in ('derived', 'report', 'audit'):
            path = self.repo / f[key]
            require(path.is_file() and not path.is_symlink(), 'missing or linked AMNM evidence')
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == f[key + '_sha256'], 'AMNM evidence hash mismatch')
            try:
                records[key] = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise Stop('AMNM evidence unreadable') from None
            require(isinstance(records[key], dict), 'AMNM evidence must be an object')
        d, r, a = (records[k] for k in ('derived', 'report', 'audit'))
        for item in (d, r, a):
            require(item.get('profile') == self.profile and item.get('kernel_sha256') == f['kernel_sha256'] and
                    item.get('adt_sha256') == f['adt_sha256'] and item.get('parent_record_sha256') == f['parent_sha256'] and
                    item.get('device_release') is False, 'AMNM evidence identity mismatch')
        require(d.get('type') == 'amnm-derived-input-v1' and d.get('args') == ['-v', 'serial=3'] and
                d.get('kernel_bytes') == f['kernel_bytes'] and r.get('kernel_bytes') == f['kernel_bytes'] and
                r.get('fat_bytes') == f['fat_bytes'] and r.get('outer_bytes') == self.size and
                r.get('readback_complete') is True, 'AMNM derived/report shape mismatch')
        for item in (r, a):
            hashes = item.get('fat_hashes')
            require(item.get('fat_sha256') == f['fat_sha256'] and item.get('outer_sha256') == self.candidate_sha256 and
                    isinstance(hashes, dict) and hashes.get('Payloads/kernel.macho') == f['kernel_sha256'] and
                    hashes.get('Payloads/kernel.macho.adt') == f['adt_sha256'], 'AMNM audit FAT binding mismatch')
        require(a.get('fixed_r4_sha256') == self.r4_sha256 and a.get('extraction_exit') == 0,
                'AMNM audit loader/extraction mismatch')

    def su_commands(self):
        commands = {'id', 'getprop sys.boot_completed', 'getprop ro.boot.slot_suffix',
                    'readlink -f ' + BLOCK, 'blockdev --getsize64 ' + BLOCK,
                    'sha256sum ' + BLOCK, 'sync', 'echo 3 > /proc/sys/vm/drop_caches',
                    'pidof dd', 'ls -A ' + self.remote, 'rmdir ' + self.remote,
                    'stat -c %F:%u:%a ' + self.remote}
        for name in ('candidate', 'restore'):
            path = self.remote + '/' + name + '.img'
            commands.add('sha256sum ' + path)
            commands.add('dd if=' + path + ' of=' + BLOCK + ' bs=1048576 conv=fsync')
            commands.add('stat -c %F:%u:%a ' + path)
            commands.add('rm ' + path)
        return commands

    def allowed(self, tool, args, binary):
        if tool == self.adb and args == ['devices', '-l']:
            return not binary
        if tool == self.fastboot and args == ['devices']:
            return not binary
        if len(args) < 3 or args[0] != '-s' or args[1] not in self.serials:
            return False
        tail = args[2:]
        if tool == self.fastboot:
            return not binary and tail in (['getvar', 'product'], ['getvar', 'current-slot'],
                ['set_active', 'a'], ['set_active', 'b'], ['boot', str(self.r4)], ['reboot'])
        if tool != self.adb:
            return False
        if tail == ['shell', 'getprop', 'ro.product.device'] or tail == ['reboot', 'bootloader']:
            return not binary
        if tail == ['shell', 'mkdir', '-m', '755', self.remote]:
            return not binary
        if tail in (['shell', 'chmod', '600', self.remote + '/candidate.img'],
                    ['shell', 'chmod', '600', self.remote + '/restore.img']):
            return not binary
        if tail[:1] == ['push'] and len(tail) == 3:
            return not binary and tail[1:] in ([str(self.candidate), self.remote + '/candidate.img'],
                                               [str(self.backup), self.remote + '/restore.img'])
        if len(tail) != 4 or tail[0] not in ('shell', 'exec-out') or tail[1:3] != ['su', '-c']:
            return False
        command = tail[3]
        if binary:
            # exec-out passes the su -c argument directly: no literal outer quotes.
            return tail[0] == 'exec-out' and command == 'dd if=' + BLOCK + ' bs=1048576 2>/dev/null'
        if not (command.startswith("'") and command.endswith("'")):
            return False
        command = command[1:-1]
        return tail[0] == 'shell' and command in self.su_commands() and not command.startswith('dd if=' + BLOCK)

    def call(self, tool, args, binary_path=None, optional=False):
        require(self.phase is not None, 'no authorized phase')
        require(self.allowed(tool, args, binary_path is not None), 'command outside exact whitelist')
        template = [tool, *args]
        if args[0] == '-s':
            template[2] = '<REDACTED>'
        record = {'command': template, 'returncode': None, 'stdout': '', 'stderr': ''}
        try:
            if binary_path is None:
                timeout = 20
                if self.wait_deadline is not None:
                    timeout = min(timeout, self.wait_deadline - time.monotonic())
                    require(timeout > 0, 'transport wait time budget exhausted')
                result = self.runner([tool, *args], capture_output=True, text=True, timeout=timeout)
                record.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            else:
                with binary_path.open('xb') as stream:
                    result = self.runner([tool, *args], stdout=stream, stderr=subprocess.PIPE, timeout=120)
                    stream.flush()
                    os.fsync(stream.fileno())
                record.update(returncode=result.returncode, stdout='<binary saved on host>',
                              stderr=result.stderr.decode('utf-8', 'replace'))
        except subprocess.TimeoutExpired:
            record['error'] = 'timeout; remote completion UNKNOWN'
        except OSError as error:
            record.update(error=type(error).__name__, errno=error.errno)
        # Inventory (including stderr) never leaves memory, even on failure.
        raw = dict(record)
        if args in (['devices', '-l'], ['devices']):
            record.update(stdout='<enumeration withheld>', stderr='<enumeration stderr withheld>')
        self.events.append(self.sanitize(record))
        self.create('event-%04d.json' % len(list(self.directory.glob('event-*.json'))), record)
        ok = raw['returncode'] == 0 and not BAD.search(raw['stdout'] + raw['stderr'])
        if not ok and not optional:
            raise Stop('command failed/timeout; inspect redacted event; no automatic retry')
        return raw, ok

    def adb_call(self, serial, command, optional=False):
        return self.call(self.adb, ['-s', serial, 'shell', 'su', '-c', "'" + command + "'"], optional=optional)

    def identify(self, transport, allow_absent=False):
        tool = self.adb if transport == 'adb' else self.fastboot
        args = ['devices', '-l'] if transport == 'adb' else ['devices']
        inventory, _ = self.call(tool, args)
        entries = [line.split() for line in inventory['stdout'].splitlines()
                   if line.strip() and not line.startswith('List of devices attached')]
        self.serials.update(parts[0] for parts in entries)
        require(all(len(parts) >= 2 for parts in entries), 'unrecognized enumeration')
        targets = []
        for parts in entries:
            if transport == 'adb':
                require(parts[1] == 'device', 'offline/unauthorized transport; identity unresolved')
                result, _ = self.call(tool, ['-s', parts[0], 'shell', 'getprop', 'ro.product.device'])
                values = result['stdout'].split()
            else:
                require(parts[1] == 'fastboot', 'unrecognized fastboot transport')
                result, _ = self.call(tool, ['-s', parts[0], 'getvar', 'product'])
                values = re.findall(r'^(?:\(bootloader\)\s*)?product:\s*(\S+)\s*$',
                                    result['stdout'] + '\n' + result['stderr'], re.M)
            require(len(values) == 1, 'product missing/ambiguous')
            if values == ['nuwa']:
                targets.append(parts[0])
        if not targets and allow_absent:
            return None
        require(len(targets) == 1, 'zero or multiple nuwa targets; stopped')
        return targets[0]

    def confirm(self, serial, transport='adb'):
        if transport == 'adb':
            result, _ = self.call(self.adb, ['-s', serial, 'shell', 'getprop', 'ro.product.device'])
            require(result['stdout'].strip() == 'nuwa', 'target product changed')
        else:
            result, _ = self.call(self.fastboot, ['-s', serial, 'getvar', 'product'])
            values = re.findall(r'^(?:\(bootloader\)\s*)?product:\s*(\S+)\s*$',
                                result['stdout'] + '\n' + result['stderr'], re.M)
            require(values == ['nuwa'], 'fastboot product missing/changed')

    def android_a(self, serial):
        self.confirm(serial)
        result, _ = self.adb_call(serial, 'getprop sys.boot_completed')
        require(result['stdout'].strip() == '1', 'Android not boot_completed=1')
        result, _ = self.adb_call(serial, 'id')
        require(re.search(r'\buid=0\b', result['stdout']), 'su uid0 not confirmed')
        result, _ = self.adb_call(serial, 'getprop ro.boot.slot_suffix')
        require(result['stdout'].strip() == '_a', 'current Android slot is not A')

    def device_hash(self, serial, path):
        result, _ = self.adb_call(serial, 'sha256sum ' + path)
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+' + re.escape(path) + r'\s*', result['stdout'])
        require(match is not None, 'sha256sum response malformed')
        return match.group(1).lower()

    def geometry(self, serial):
        result, _ = self.adb_call(serial, 'readlink -f ' + BLOCK)
        require(re.fullmatch(r'/dev/block/[A-Za-z0-9_/-]+\s*', result['stdout']) is not None,
                'block link unresolved')
        result, _ = self.adb_call(serial, 'blockdev --getsize64 ' + BLOCK)
        require(result['stdout'].strip() == str(self.size), 'partition capacity mismatch')

    def readback(self, serial, filename, expected):
        target = self.directory / filename
        self.call(self.adb, ['-s', serial, 'exec-out', 'su', '-c',
                            'dd if=' + BLOCK + ' bs=1048576 2>/dev/null'], binary_path=target)
        self.check_file(target, self.size, expected)

    def clear_writer(self, serial):
        pending = [phase for phase in ('prepare', 'restore')
                   if (self.directory / (phase + '-writer.claim')).exists()
                   and not (self.directory / (phase + '-writer-closed.json')).exists()]
        result, ok = self.adb_call(serial, 'pidof dd', optional=True)
        require(not ok and result['returncode'] == 1 and not result['stdout'].strip()
                and not result['stderr'].strip(), 'dd may still be running; no second writer permitted')
        for phase in pending:
            self.create(phase + '-writer-closed.json', {'remote_dd_absent': True})

    def staging(self, serial, create=False):
        if create:
            self.call(self.adb, ['-s', serial, 'shell', 'mkdir', '-m', '755', self.remote])
        else:
            marker = self.directory / 'staging-created.json'
            require(marker.is_file() and not marker.is_symlink(), 'no run-owned staging provenance')
            require(json.loads(marker.read_text(encoding='utf-8')) == {'path': self.remote, 'owner': 2000},
                    'staging provenance mismatch')
        result, _ = self.adb_call(serial, 'stat -c %F:%u:%a ' + self.remote)
        require(result['stdout'].strip() in ('directory:2000:700', 'directory:2000:750', 'directory:2000:755'),
                'staging directory type/owner/permissions unsafe')
        result, _ = self.adb_call(serial, 'ls -A ' + self.remote)
        names = result['stdout'].splitlines()
        require(len(names) == len(set(names)) and set(names) <= {'candidate.img', 'restore.img'},
                'unexpected staging entry; no push/write/cleanup')
        for name in names:
            result, _ = self.adb_call(serial, 'stat -c %F:%u:%a ' + self.remote + '/' + name)
            require(result['stdout'].strip() in ('regular file:2000:600', 'regular file:2000:400', 'regular file:2000:640'),
                    'staging file type/owner/permissions unsafe')
        if create:
            require(not names, 'new staging directory is not empty')
            self.create('staging-created.json', {'path': self.remote, 'owner': 2000})
        return names

    def cleanup(self, serial):
        names = self.staging(serial)
        for name in names:
            self.adb_call(serial, 'rm ' + self.remote + '/' + name)
        require(not self.staging(serial), 'staging not empty; no rmdir')
        self.adb_call(serial, 'rmdir ' + self.remote)

    def write_b(self, serial, restore=False):
        self.android_a(serial)
        self.geometry(serial)
        self.clear_writer(serial)
        name, expected = ('restore', self.stock_sha256) if restore else ('candidate', self.candidate_sha256)
        host = self.backup if restore else self.candidate
        self.check_file(host, self.size, expected)
        self.staging(serial, create=not (self.directory / 'staging-created.json').exists())
        self.confirm(serial)
        self.call(self.adb, ['-s', serial, 'push', str(host), self.remote + '/' + name + '.img'])
        # Initial mode assignment only for this run's just-uploaded fixed file.
        self.call(self.adb, ['-s', serial, 'shell', 'chmod', '600', self.remote + '/' + name + '.img'])
        self.staging(serial)
        require(self.device_hash(serial, self.remote + '/' + name + '.img') == expected, 'uploaded image hash mismatch')
        self.android_a(serial)
        self.create(self.phase + '-writer.claim', {'target': BLOCK, 'expected': expected})
        try:
            self.adb_call(serial, 'dd if=' + self.remote + '/' + name + '.img of=' + BLOCK + ' bs=1048576 conv=fsync')
        except Stop:
            self.clear_writer(serial)
            raise Stop('dd failed/timeout; do not reboot/switch; restore only after writer absence confirmed') from None
        self.create(self.phase + '-writer-closed.json', {'dd_returncode': 0})
        self.adb_call(serial, 'sync')
        self.adb_call(serial, 'echo 3 > /proc/sys/vm/drop_caches')
        require(self.device_hash(serial, BLOCK) == expected, 'partition hash mismatch; do not reboot/switch; use restore')
        self.readback(serial, name + '-readback.img', expected)
        self.android_a(serial)

    def prepare(self):
        serial = self.identify('adb')
        self.android_a(serial)
        self.advance('identified')
        self.geometry(serial)
        require(self.device_hash(serial, BLOCK) == self.stock_sha256, 'B is not frozen stock; no writes')
        self.readback(serial, self.backup.name, self.stock_sha256)
        require(self.device_hash(serial, BLOCK) == self.stock_sha256, 'backup/device hash changed; no writes')
        self.advance('backup_verified')
        self.write_b(serial)
        self.advance('candidate_verified_on_B')

    def current_slot(self, serial):
        result, ok = self.call(self.fastboot, ['-s', serial, 'getvar', 'current-slot'], optional=True)
        response = result['stdout'] + '\n' + result['stderr']
        require('error' not in result and result['returncode'] is not None,
                'current-slot transport failure; no subsequent slot action')
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        timing = re.compile(r'Finished\.(?: Total time: [0-9]+(?:\.[0-9]+)?s)?', re.I)
        body = [line for line in lines if not timing.fullmatch(line)]
        require(len(lines) - len(body) <= 1, 'unexpected current-slot timing/wrapper lines')
        # Exact retained response only. Missing-variable spelling is not available
        # in the retained redacted JSON, so do not guess or generalize it.
        if body == ["FAILED (remote: 'unknown command')"] and result['returncode'] == 1:
            return None
        require(ok and len(body) == 1, 'current-slot failed/mixed without exact retained unsupported response')
        value = re.fullmatch(r'(?:\(bootloader\)\s*)?current-slot:\s*([ab])', body[0])
        require(value is not None, 'current-slot malformed/ambiguous')
        return value.group(1)

    def accepted_slot(self, serial, slot, readable=None):
        if readable is None:
            readable = self.current_slot(serial) is not None
        self.confirm(serial, 'fastboot')
        result, _ = self.call(self.fastboot, ['-s', serial, 'set_active', slot])
        response = result['stdout'] + result['stderr']
        require('OKAY' in response and re.search(r'Finished', response, re.I), 'set_active lacks OKAY/Finished; no retry')
        if readable:
            require(self.current_slot(serial) == slot, 'post-set slot readback failed; no boot/reboot')

    def wait_transport(self, transport, expected, ready=False):
        rounds, seconds = (6, 150) if transport == 'adb' else (3, 75)
        self.wait_deadline = time.monotonic() + seconds
        try:
            for attempt in range(rounds):
                serial = self.identify(transport, allow_absent=True)
                if serial is not None:
                    require(serial == expected, 'transport target changed')
                    if not ready:
                        require(time.monotonic() <= self.wait_deadline, 'transport wait time budget exhausted')
                        return serial
                    result, ok = self.adb_call(serial, 'getprop sys.boot_completed', optional=True)
                    if ok and result['stdout'].strip() == '1':
                        require(time.monotonic() <= self.wait_deadline, 'transport wait time budget exhausted')
                        return serial
                if attempt + 1 < rounds:
                    remaining = self.wait_deadline - time.monotonic()
                    require(remaining > 0, 'transport wait time budget exhausted')
                    self.pause(min(5, remaining))
            raise Stop('transport wait attempts exhausted; no reboot/write retry')
        finally:
            self.wait_deadline = None

    def boot(self):
        require(self.state() == 'candidate_verified_on_B', 'boot requires verified candidate on B')
        require(not (self.directory / 'boot-attempt.claim').exists(), 'boot attempt already consumed')
        self.check_file(self.backup, self.size, self.stock_sha256)
        serial = self.identify('adb')
        self.android_a(serial)
        require(self.device_hash(serial, BLOCK) == self.candidate_sha256, 'B candidate changed; no reboot')
        self.confirm(serial)
        self.call(self.adb, ['-s', serial, 'reboot', 'bootloader'])
        fastboot_serial = self.wait_transport('fastboot', serial)
        require(fastboot_serial == serial, 'transport target changed; no slot switch')
        self.advance('bootloader_stable')  # Identified only, not sustained bootloader residency.
        current = self.current_slot(serial)
        self.create('bootloader-current-slot.json', {'value': current if current else 'unreadable'})
        self.accepted_slot(serial, 'b', readable=current is not None)
        self.advance('set_B_accepted')
        self.confirm(serial, 'fastboot')
        self.create('boot-attempt.claim', {'consumed_before_boot': True})
        self.advance('boot_attempt_consumed')
        self.call(self.fastboot, ['-s', serial, 'boot', str(self.r4)])
        return self.observation

    def restore(self):
        self.check_file(self.backup, self.size, self.stock_sha256)
        serial = self.identify('adb', allow_absent=True)
        if serial is None:
            serial = self.identify('fastboot')
            self.accepted_slot(serial, 'a')
            self.advance('set_A_accepted')
            self.confirm(serial, 'fastboot')
            self.call(self.fastboot, ['-s', serial, 'reboot'])
            serial = self.wait_transport('adb', serial, ready=True)
        self.android_a(serial)
        self.advance('android_A_confirmed')
        self.write_b(serial, restore=True)
        self.advance('B_restored_verified')
        self.cleanup(serial)

    def execute(self, phase, authorized=False):
        require(phase in ('prepare', 'boot', 'restore'), 'invalid phase')
        if not authorized:
            return {'dry_run': True, 'phase': phase, 'profile': self.profile,
                    'run_identity': self.identity(), 'device_commands_executed': 0,
                    'templates': self.templates(phase)}
        require(not self.directory.is_symlink() and not self.directory.parent.is_symlink(), 'linked run path refused')
        if phase == 'prepare':
            self.host_inputs()
            self.directory.mkdir(parents=True, exist_ok=False)
            self.create('run-identity.json', self.identity())
        else:
            require(self.directory.is_dir(), 'run directory/backup missing')
            self.require_identity()
            if phase == 'restore':
                # Restore consumes only this run's full stock backup, not the candidate/r4/evidence.
                self.check_file(self.backup, self.size, self.stock_sha256)
            else:
                self.host_inputs()
        # Cross-phase exclusion. Crash leaves lock intact: manual host review required.
        self.create('active.lock', {'phase': phase})
        try:
            self.create(phase + '.claim', {'phase': phase, 'authorized': True})
            self.phase = phase
            message = getattr(self, phase)()
            self.create(phase + '-complete.json', {'state': self.state(), 'message': message})
            return {'self_checked': True, 'state': self.state(), 'message': message}
        finally:
            self.phase = None
            (self.directory / 'active.lock').unlink()

    def templates(self, phase):
        adb, fastboot = self.adb + ' -s <REDACTED>', self.fastboot + ' -s <REDACTED>'
        return {'profile': self.profile, 'run_identity': self.identity(),
                'enumeration': [self.adb + ' devices -l', self.fastboot + ' devices'],
                'identity': [adb + ' shell getprop ro.product.device', fastboot + ' getvar product'],
                'su_exact_commands': sorted(self.su_commands()),
                'push': [adb + ' push <frozen-candidate> ' + self.remote + '/candidate.img',
                         adb + ' push <verified-run-backup> ' + self.remote + '/restore.img'],
                'staging_directory': adb + ' shell mkdir -m 755 ' + self.remote,
                'uploaded_file_modes': [adb + ' shell chmod 600 ' + self.remote + '/candidate.img',
                                        adb + ' shell chmod 600 ' + self.remote + '/restore.img'],
                'binary_read_argv': [self.adb, '-s', '<REDACTED>', 'exec-out', 'su', '-c',
                                     'dd if=' + BLOCK + ' bs=1048576 2>/dev/null'],
                'boot': [adb + ' reboot bootloader', fastboot + ' getvar current-slot',
                         fastboot + ' set_active b', fastboot + ' boot ' + str(self.r4)],
                'restore': [fastboot + ' set_active a', fastboot + ' reboot'], 'selected_phase': phase}


def self_check():
    """Real subprocess.run is trapped: every state-machine command is synthetic."""
    import tempfile
    from unittest.mock import patch
    tests = []

    class Fake:
        def __init__(self):
            self.calls, self.targets = [], ['SYNTHETIC123']
            self.candidate_sha, self.stock_sha, self.size = CANDIDATE, STOCK, SIZE
            self.stock, self.transport, self.slot = True, 'adb', '_a'
            self.bad_hash, self.dd_timeout, self.running_dd = False, False, False
            self.bad_product, self.bad_slot, self.boot_timeout = False, False, False
            self.fast_restore, self.wait_exhausted = False, False
            self.unrooted, self.bad_geometry, self.wrong_slot = False, False, False
            self.not_completed, self.postwrite_bad = False, False
            self.non_target = None
            self.remote_exists, self.remote_files = False, set()
            self.directory_stat, self.file_stat = 'directory:2000:755', 'regular file:2000:600'
            self.chmod_inert = False
            self.restore_upload_mode, self.restore_chmod_failure, self.restore_chmod_inert = '666', False, False
            self.restore_initial_modes = []
            self.slot_fault, self.slot_readable, self.slot_reads = None, False, 0
            self.slot_readback_fault = None
            self.binary_payload, self.binary_fault = b'synthetic', None
            self.fastboot_absent = 0
            self.timeouts = []

        def __call__(self, argv, **kwargs):
            self.calls.append(argv)
            self.timeouts.append(kwargs['timeout'])
            args = argv[1:]
            code, stdout, stderr = 0, '', ''
            if args in (['devices', '-l'], ['devices']):
                transport = 'adb' if args == ['devices', '-l'] else 'fastboot'
                stdout = 'List of devices attached\n' if transport == 'adb' else ''
                if transport == self.transport:
                    if transport == 'fastboot' and self.fastboot_absent:
                        self.fastboot_absent -= 1
                    else:
                        stdout += ''.join(s + ('\tdevice product:nuwa\r\n' if transport == 'adb' else '\tfastboot\r\n') for s in self.targets)
            elif args[2:] == ['shell', 'getprop', 'ro.product.device']:
                stdout = 'other-model\n' if args[1] == self.non_target else 'nuwa\n'
            elif args[2:] == ['getvar', 'product']:
                stderr = 'product: nuwa\n' if not self.bad_product else 'product: nuwa\nFAILED unknown command\n'
            elif args[2:] == ['getvar', 'current-slot']:
                self.slot_reads += 1
                fault = self.slot_fault if self.slot_reads == 1 else self.slot_readback_fault
                if fault == 'timeout':
                    raise subprocess.TimeoutExpired(argv, 20, output='SYNTHETIC123')
                if fault == 'oserror':
                    raise OSError('SYNTHETIC123')
                if fault == 'offline':
                    code, stderr = 1, 'FAILED device offline SYNTHETIC123\n'
                elif fault == 'other-failed':
                    code, stderr = 1, 'FAILED generic failure\n'
                elif fault == 'same-line-denied':
                    code, stderr = 1, "FAILED (remote: 'unknown command unsupported permission denied')\n"
                elif fault == 'unsupported-hint':
                    stdout = 'NOTE: unsupported feature\n'
                elif fault == 'unsupported-valid-slot':
                    code, stderr = 1, "FAILED (remote: 'unknown command')\ncurrent-slot: a\n"
                elif fault in ('extra-failure', 'zero-extra-failure'):
                    code = 0 if fault == 'zero-extra-failure' else 1
                    stderr = "FAILED (remote: 'unknown command')\nFAILED (remote: 'permission denied')\n"
                elif fault == 'hint-valid-slot':
                    stdout = 'NOTE: unsupported feature\ncurrent-slot: a\n'
                elif fault == 'extra-wrapper-text':
                    code, stderr = 1, "FAILED (remote: 'unknown command')\nFinished. Total time: 0.01s unsupported\n"
                elif fault == 'malformed':
                    stdout = 'current-slot: ???\n'
                elif fault in ('a', 'b'):
                    stdout = 'current-slot: ' + fault + '\n'
                elif self.slot_readable:
                    stdout = 'current-slot: ' + self.slot[1:] + '\n'
                else:
                    code, stderr = 1, "FAILED (remote: 'unknown command')\nFinished. Total time: 0.01s\n"
            elif args[2:4] == ['set_active', 'b'] or args[2:4] == ['set_active', 'a']:
                if self.bad_slot:
                    stderr = 'missing acknowledgement'
                else:
                    self.slot = '_' + args[3]
                    stderr = 'OKAY\nFinished. Total time: 0.01s\n'
            elif args[2:] == ['reboot', 'bootloader']:
                self.transport = 'fastboot'
            elif args[2:] == ['reboot']:
                self.transport = 'fastboot' if self.wait_exhausted else 'adb'
            elif args[2:3] == ['boot']:
                if self.boot_timeout:
                    raise subprocess.TimeoutExpired(argv, 20)
            elif args[2:3] == ['push']:
                self.remote_files.add(args[-1].rsplit('/', 1)[-1])
                if args[-1].endswith('/restore.img'):
                    self.file_stat = 'regular file:2000:' + self.restore_upload_mode
                    self.restore_initial_modes.append(self.file_stat)
            elif args[2:4] == ['shell', 'mkdir']:
                require(args[2:] == ['shell', 'mkdir', '-m', '755', args[-1]],
                        'synthetic mkdir must request exact creation mode755 without -p')
                if self.remote_exists:
                    code, stderr = 1, 'File exists\n'
                else:
                    self.remote_exists = True
            elif args[2:4] == ['shell', 'chmod']:
                require(args[2:] == ['shell', 'chmod', '600', args[-1]]
                        and args[-1].rsplit('/', 1)[-1] in ('candidate.img', 'restore.img'),
                        'synthetic chmod argv must target only fixed upload files, mode600')
                is_restore = args[-1].endswith('/restore.img')
                if is_restore and self.restore_chmod_failure:
                    code, stderr = 1, 'Permission denied\n'
                elif not (self.chmod_inert or (is_restore and self.restore_chmod_inert)):
                    self.file_stat = 'regular file:2000:600'
            else:
                require(args[2:5] in (['shell', 'su', '-c'], ['exec-out', 'su', '-c']), 'bad synthetic argv')
                command = args[5] if args[2] == 'exec-out' else args[5][1:-1]
                if command == 'id':
                    stdout = ('uid=2000(shell)' if self.unrooted else 'uid=0(root)') + ' SYNTHETIC123\n'
                elif command == 'getprop sys.boot_completed':
                    stdout = '0\n' if self.not_completed else '1\n'
                elif command == 'getprop ro.boot.slot_suffix':
                    stdout = '_b\n' if self.wrong_slot else self.slot + '\n'
                elif command.startswith('readlink'):
                    stdout = '/dev/block/sde54\n'
                elif command.startswith('blockdev'):
                    stdout = str(self.size - 1 if self.bad_geometry else self.size) + '\n'
                elif command.startswith('stat -c '):
                    stdout = (self.file_stat if command.endswith('.img') else self.directory_stat) + '\n'
                elif command.startswith('ls -A '):
                    stdout = ''.join(name + '\n' for name in sorted(self.remote_files))
                elif command.startswith('rm '):
                    self.remote_files.remove(command.rsplit('/', 1)[-1])
                elif command.startswith('rmdir '):
                    require(not self.remote_files, 'synthetic rmdir not empty')
                    self.remote_exists = False
                elif command.startswith('sha256sum'):
                    path = command.split()[1]
                    value = self.stock_sha if path.endswith('restore.img') or (path == BLOCK and self.stock) else self.candidate_sha
                    bad = self.bad_hash or (self.postwrite_bad and not self.stock and path == BLOCK)
                    stdout = ('0' * 64 if bad else value) + '  ' + path + '\n'
                elif command == 'pidof dd':
                    code, stdout = (0, '123\n') if self.running_dd else (1, '')
                elif ' of=' in command:
                    if self.dd_timeout:
                        self.running_dd = True
                        raise subprocess.TimeoutExpired(argv, 20)
                    self.stock = '/restore.img ' in command
                elif args[2] == 'exec-out':
                    require(command == 'dd if=' + BLOCK + ' bs=1048576 2>/dev/null',
                            'binary argv has extra quotes/arguments or lacks stderr isolation')
                    payload = self.binary_payload
                    if self.binary_fault == 'statistics':
                        payload += b'1+0 records in\n1+0 records out\n'
                    elif self.binary_fault == 'short':
                        payload = payload[:-1]
                    kwargs['stdout'].write(payload)
                    if self.binary_fault == 'timeout':
                        raise subprocess.TimeoutExpired(argv, 120, stderr=b'SYNTHETIC123')
                    return subprocess.CompletedProcess(argv, 0, None, b'')
            return subprocess.CompletedProcess(argv, code, stdout, stderr)

    def fixture(base, name, profile=STOP_PROFILE):
        fake = Fake()
        run = Run(Path(base) / name, name, 'adb.exe', 'fastboot.exe', runner=fake, pause=lambda _: None,
                  profile=profile)
        fake.candidate_sha, fake.stock_sha, fake.size = run.candidate_sha256, run.stock_sha256, run.size
        # Replace file validation only: production constants and device comparisons stay fixed.
        def check(path, size, expected):
            if path == run.backup:
                require(path.exists(), 'backup missing')
        run.check_file = check
        if profile in (AMNM_PROFILE, CHMH_PROFILE, PTHREAD_PROFILE, PMGR_PROFILE, HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE):
            keys = (('derived', 'report', 'audit', 'layout', 'provenance', 'source', 'config') if profile in (PMGR_PROFILE, HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE)
                    else ('derived', 'report', 'audit', 'audit_source', 'layout') if profile == PTHREAD_PROFILE
                    else ('derived', 'report', 'audit', 'audit_source'))
            for key in keys:
                path = run.repo / run.frozen[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((REPO / run.frozen[key]).read_bytes())
            if profile in (PTHREAD_PROFILE, PMGR_PROFILE, HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE):
                for item in run.frozen['evidence'].values():
                    path = run.repo / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes((REPO / item['path']).read_bytes())
            if profile in (CHMH_PROFILE, PTHREAD_PROFILE, PMGR_PROFILE, HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE):
                path = run.repo / run.frozen['report']
                data = json.loads(path.read_bytes())
                data['record_path'] = str(run.repo / run.frozen['derived'])
                path.write_text(json.dumps(data))
                run.frozen = dict(run.frozen, report_sha256=file_hash(path))
        elif run.frozen is not None:
            evidence = run.repo / run.frozen['evidence']
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps({'profile': run.profile,
                                            'vendor_boot_sha256': run.candidate_sha256,
                                            'vendor_boot_bytes': run.size,
                                            'vendor_ramdisk_sha256': run.frozen['fat_sha256'],
                                            'kernel_sha256': run.frozen['kernel_sha256'],
                                            'adt_sha256': run.frozen['adt_sha256'],
                                            'args_exact': run.frozen['args'],
                                            'input_binding': {'fat_sha256': run.frozen['fat_sha256']},
                                            'fat_hashes': {'Payloads/kernel.macho': run.frozen['kernel_sha256'],
                                                           'Payloads/kernel.macho.adt': run.frozen['adt_sha256']}}),
                                encoding='utf-8')
        return run, fake

    def stopped(action):
        try:
            action()
        except (Stop, FileExistsError):
            return
        raise AssertionError('expected safe stop')

    scratch = REPO / 'out'
    scratch.mkdir(exist_ok=True)
    with patch.object(subprocess, 'run', side_effect=AssertionError('REAL PROCESS FORBIDDEN')):
        # Retain synthetic evidence in ignored out/, never bulk-delete test trees.
        with contextlib.nullcontext(tempfile.mkdtemp(prefix='pmap-ret-selfcheck-', dir=scratch)) as tmp:
            queue, queue_fake = fixture(tmp, 'queue-five-fixture', QUEUE_PROFILE)
            queue.host_inputs()
            require(not queue_fake.calls and 'QUEUE_ONLY_DONE' in queue.observation,
                    'queue fixture host inputs/observation')
            tests.append('queue-five-fixture')
            sid, sid_fake = fixture(tmp, 'sid-domain-fixture', SID_PROFILE)
            sid.host_inputs()
            require(not sid_fake.calls and 'DOMAIN_STOP' in sid.observation and
                    'status9' in sid.observation and 'NONUNIQUE' in sid.observation,
                    'SID fixture host inputs/observation')
            tests.append('sid-domain-fixture')
            nop, nop_fake = fixture(tmp, 'preserved-nop-fixture', NOP_PROFILE)
            nop.host_inputs()
            require(not nop_fake.calls and '0 Success' in nop.observation and
                    '15 Response' in nop.observation and 'end+1' in nop.observation,
                    'preserved NOP fixture host inputs/observation')
            tests.append('preserved-nop-fixture')
            run, fake = fixture(tmp, 'happy')
            run.execute('prepare', True)
            require(run.state() == 'candidate_verified_on_B', 'prepare state')
            boot_result = run.execute('boot', True)
            require('manually return to bootloader' in boot_result['message']
                    and 'restore separately' in boot_result['message']
                    and 'do not rerun boot' in boot_result['message'], 'boot observation/restore guidance missing')
            require(run.state() == 'boot_attempt_consumed', 'boot state')
            stopped(lambda: run.execute('boot', True))
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified' and fake.slot == '_a' and fake.stock, 'restore state')
            require(sum(a[3:4] == ['boot'] for a in fake.calls) == 1, 'one boot only')
            require('SYNTHETIC123' not in ''.join(p.read_text() for p in run.directory.glob('*.json')), 'serial leak')
            tests.extend(['prepare-boot-restore', 'boot-replay-refused', 'serial-redaction', 'boot-manual-return-restore-guidance'])
            mkdir_calls = [args for args in fake.calls if args[3:5] == ['shell', 'mkdir']]
            require(mkdir_calls == [[run.adb, '-s', 'SYNTHETIC123', 'shell', 'mkdir', '-m', '755', run.remote]],
                    'staging mkdir argv not exact -m755/no-p')
            run.phase = 'prepare'
            checkpoint = len(fake.calls)
            for bad_tail in (['shell', 'mkdir', run.remote], ['shell', 'mkdir', '-p', run.remote],
                             ['shell', 'mkdir', '-m', '777', run.remote]):
                stopped(lambda tail=bad_tail: run.call(run.adb, ['-s', 'SYNTHETIC123', *tail]))
            require(len(fake.calls) == checkpoint, 'non-whitelist mkdir invoked runner')
            run.phase = None
            tests.append('mkdir-exact-mode755-argv-and-alternatives-refused')
            chmod_calls = [args for args in fake.calls if args[3:5] == ['shell', 'chmod']]
            require(chmod_calls == [[run.adb, '-s', 'SYNTHETIC123', 'shell', 'chmod', '600', run.remote + '/' + name + '.img']
                                     for name in ('candidate', 'restore')], 'fixed-file mode assignment argv not exact')
            push_index = next(i for i, args in enumerate(fake.calls)
                              if args[3:4] == ['push'] and args[-1] == run.remote + '/candidate.img')
            chmod_index = fake.calls.index(chmod_calls[0])
            stat_index = next(i for i, args in enumerate(fake.calls)
                              if args[-1] == "'stat -c %F:%u:%a " + run.remote + "/candidate.img'")
            require(push_index < chmod_index < stat_index, 'chmod not between push and file validation')
            run.phase = 'prepare'
            checkpoint = len(fake.calls)
            for tail in (['shell', 'chmod', '600', run.remote + '/../restore.img'],
                         ['shell', 'chmod', '600', run.remote + '/../candidate.img'],
                         ['shell', 'chmod', '600', '/data/local/tmp/other/candidate.img'],
                         ['shell', 'chmod', '600', '/data/local/tmp/other/restore.img'],
                         ['shell', 'chmod', '644', run.remote + '/candidate.img'],
                         ['shell', 'chmod', '644', run.remote + '/restore.img']):
                stopped(lambda args=tail: run.call(run.adb, ['-s', 'SYNTHETIC123', *args]))
            require(len(fake.calls) == checkpoint, 'out-of-scope chmod invoked runner')
            run.phase = None
            tests.append('chmod-exact-fixed-files-argv-order-and-path-boundary')
            run, fake = fixture(tmp, 'restore-mode-assignment')
            run.execute('prepare', True)
            fake.restore_upload_mode = '666'
            checkpoint = len(fake.calls)
            run.execute('restore', True)
            calls = fake.calls[checkpoint:]
            restore_path = run.remote + '/restore.img'
            push_index = next(i for i, args in enumerate(calls) if args[3:] == ['push', str(run.backup), restore_path])
            chmod_index = next(i for i, args in enumerate(calls) if args[3:] == ['shell', 'chmod', '600', restore_path])
            stat_index = next(i for i, args in enumerate(calls) if args[-1] == "'stat -c %F:%u:%a " + restore_path + "'")
            hash_index = next(i for i, args in enumerate(calls) if args[-1] == "'sha256sum " + restore_path + "'")
            require(fake.restore_initial_modes == ['regular file:2000:666']
                    and push_index < chmod_index < stat_index < hash_index
                    and run.state() == 'B_restored_verified', 'restore mode assignment order/gate failed')
            tests.append('restore-upload-666-chmod-before-stat-and-hash')
            for fault in ('chmod-failed', 'mode-666', 'mode-644'):
                run, fake = fixture(tmp, 'restore-prewrite-' + fault)
                run.execute('prepare', True)
                backup_bytes = run.backup.read_bytes()
                fake.restore_upload_mode = '644' if fault == 'mode-644' else '666'
                fake.restore_chmod_failure = fault == 'chmod-failed'
                fake.restore_chmod_inert = fault != 'chmod-failed'
                checkpoint = len(fake.calls)
                stopped(lambda: run.execute('restore', True))
                require(not any(' of=' in ' '.join(args) for args in fake.calls[checkpoint:]),
                        'failed restore chmod/stat reached dd writer')
                require((run.directory / 'restore.claim').exists()
                        and not (run.directory / 'restore-writer.claim').exists()
                        and run.state() == 'android_A_confirmed', 'prewrite restore claim/state not retained')
                checkpoint = len(fake.calls)
                stopped(lambda: run.execute('restore', True))
                require(len(fake.calls) == checkpoint and run.backup.read_bytes() == backup_bytes,
                        'restore failure allowed replay or changed backup')
                tests.append('restore-' + fault + '-no-dd-claim-retained-replay-refused')
            for phase in ('prepare', 'boot', 'restore'):
                run, fake = fixture(tmp, 'dry-' + phase)
                require(run.execute(phase)['dry_run'] and not fake.calls and not run.directory.exists(), 'dry-run executed')
            tests.append('all-phases-without-authorization-no-I/O')
            for count in (0, 2):
                run, fake = fixture(tmp, 'targets-' + str(count))
                fake.targets = [] if count == 0 else ['SYNTHETIC123', 'SYNTHETIC456']
                stopped(lambda: run.execute('prepare', True))
                require(not any('push' in a for a in fake.calls), 'identity gate wrote')
            tests.append('zero-multiple-nuwa')
            run, fake = fixture(tmp, 'mixed-targets')
            fake.targets.append('SYNTHETICOTHER')
            fake.non_target = 'SYNTHETICOTHER'
            run.execute('prepare', True)
            other_calls = [a for a in fake.calls if 'SYNTHETICOTHER' in a]
            require(len(other_calls) == 1 and other_calls[0][3:] == ['shell', 'getprop', 'ro.product.device'],
                    'non-target received expanded query')
            tests.append('mixed-devices-only-target-queried')
            run, fake = fixture(tmp, 'bad-hash')
            fake.bad_hash = True
            stopped(lambda: run.execute('prepare', True))
            require(not any('reboot' in a or 'set_active' in a for a in fake.calls), 'bad hash rebooted')
            tests.append('device-hash-mismatch-no-reboot')
            for fault in ('unrooted', 'bad_geometry', 'wrong_slot', 'not_completed'):
                run, fake = fixture(tmp, fault)
                setattr(fake, fault, True)
                stopped(lambda: run.execute('prepare', True))
                require(not any('push' in a for a in fake.calls), 'pre-write gate failed')
            tests.append('uid-slot-capacity-boot-completed-gates')
            run, fake = fixture(tmp, 'postwrite')
            fake.postwrite_bad = True
            stopped(lambda: run.execute('prepare', True))
            require(run.state() == 'backup_verified', 'mismatched candidate promoted')
            require(not any('reboot' in a or 'set_active' in a for a in fake.calls), 'write mismatch rebooted')
            fake.postwrite_bad = False
            run.execute('restore', True)
            tests.append('postwrite-hash-mismatch-direct-restore')
            run, fake = fixture(tmp, 'binary-mismatch')
            original_check = run.check_file

            def fail_readback(path, size, expected):
                require(path.name != 'candidate-readback.img', 'synthetic binary readback mismatch')
                original_check(path, size, expected)

            run.check_file = fail_readback
            stopped(lambda: run.execute('prepare', True))
            require(run.state() == 'backup_verified', 'bad binary readback promoted')
            tests.append('binary-readback-mismatch')
            run, fake = fixture(tmp, 'direct')
            run.execute('prepare', True)
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified', 'direct Android restore')
            tests.append('restore-direct-from-Android')
            for fault in ('bad_product', 'bad_slot', 'boot_timeout'):
                run, fake = fixture(tmp, fault)
                run.execute('prepare', True)
                setattr(fake, fault, True)
                stopped(lambda: run.execute('boot', True))
                if fault == 'boot_timeout':
                    require((run.directory / 'boot-attempt.claim').exists(), 'timeout did not consume')
                else:
                    require(not any(a[3:4] == ['boot'] for a in fake.calls), 'bad fastboot gate booted')
                setattr(fake, fault, False)
                run.execute('restore', True)
            tests.append('fastboot-product-slot-boot-failures-restore-independent')
            run, fake = fixture(tmp, 'writer')
            fake.dd_timeout = True
            stopped(lambda: run.execute('prepare', True))
            stopped(lambda: run.execute('restore', True))
            require(sum(' of=' in ' '.join(a) for a in fake.calls) == 1, 'second uncertain writer')
            tests.append('dd-timeout-no-second-writer')
            run, fake = fixture(tmp, 'no-backup')
            run.directory.mkdir(parents=True)
            stopped(lambda: run.execute('restore', True))
            require(not fake.calls, 'restore without backup touched device')
            tests.append('restore-no-backup')
            run, fake = fixture(tmp, 'host-hash')
            path = Path(tmp) / 'bad.img'
            path.write_bytes(b'x')
            stopped(lambda: Run.check_file(run, path, 1, '0' * 64))
            tests.append('real-host-hash-rejection')
            run.directory.mkdir(parents=True)
            run.create('claim', {})
            stopped(lambda: run.create('claim', {}))
            run.serials.add('SYNTHETIC123')
            run.phase = 'prepare'
            for command in ('dd if=x of=/dev/block/by-name/super', 'cat /dev/block/by-name/misc',
                            'rm -rf /data', 'setprop x y', 'mount /data'):
                stopped(lambda c=command: run.adb_call('SYNTHETIC123', c))
            require(not fake.calls, 'whitelist let command through')
            tests.extend(['exclusive-claim', 'non-whitelist-and-other-block-refused'])
            run, fake = fixture(tmp, 'locked')
            run.execute('prepare', True)
            run.create('active.lock', {'phase': 'synthetic crashed process'})
            previous_count = len(fake.calls)
            stopped(lambda: run.execute('restore', True))
            require(len(fake.calls) == previous_count and (run.directory / 'active.lock').exists(), 'lock gate failed')
            tests.append('cross-phase-lock-crash-stops')
            for bad_id in ('../escape', 'x/y', 'x;reboot', ''):
                stopped(lambda value=bad_id: Run(tmp, value, 'adb.exe', 'fastboot.exe'))
            tests.append('run-id-path-injection-refused')
            run, fake = fixture(tmp, 'frozen-input')
            run.check_file = lambda path, size, expected: Run.check_file(run, path, size, expected)
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'bad host input touched device/state')
            tests.append('frozen-input-before-device-and-state')
            run, fake = fixture(tmp, 'wait-exhausted')
            run.execute('prepare', True)
            fake.transport, fake.wait_exhausted = 'fastboot', True
            stopped(lambda: run.execute('restore', True))
            require(sum(a[1:] == ['devices', '-l'] for a in fake.calls) <= 8, 'unbounded wait')
            tests.append('bounded-Android-wait')
            run, fake = fixture(tmp, 'slot-exact-unknown')
            run.execute('prepare', True)
            run.execute('boot', True)
            require(json.loads((run.directory / 'bootloader-current-slot.json').read_text())['value'] == 'unreadable',
                    'exact retained failure did not record unreadable')
            tests.append('exact-retained-unknown-command-with-timing-fallback')
            for fault in ('same-line-denied', 'unsupported-hint', 'unsupported-valid-slot',
                          'extra-failure', 'zero-extra-failure', 'hint-valid-slot', 'extra-wrapper-text'):
                run, fake = fixture(tmp, 'strict-slot-' + fault)
                run.execute('prepare', True)
                fake.slot_fault = fault
                stopped(lambda: run.execute('boot', True))
                index = max(i for i, args in enumerate(fake.calls) if args[3:] == ['getvar', 'current-slot'])
                require(not fake.calls[index + 1:], 'mixed/unsupported hint continued product/set_active/boot')
                tests.append('strict-slot-' + fault + '-stops-immediately')
            for fault in ('timeout', 'oserror', 'offline', 'other-failed'):
                run, fake = fixture(tmp, 'slot-first-' + fault)
                run.execute('prepare', True)
                fake.slot_fault = fault
                stopped(lambda: run.execute('boot', True))
                index = max(i for i, args in enumerate(fake.calls) if args[3:] == ['getvar', 'current-slot'])
                require(not fake.calls[index + 1:], 'slot transport failure had subsequent device calls')
                tests.append('current-slot-' + fault + '-stops-immediately')
            run, fake = fixture(tmp, 'slot-readable')
            run.execute('prepare', True)
            fake.slot_readable = True
            run.execute('boot', True)
            run.execute('restore', True)
            require(fake.slot_reads == 4, 'readable slots not read before/after both switches')
            tests.append('readable-slot-B-and-A-readback')
            for phase, wrong in (('boot', 'a'), ('restore', 'b')):
                for fault in (wrong, 'malformed', 'timeout', 'oserror', 'offline'):
                    run, fake = fixture(tmp, 'readback-' + phase + '-' + fault)
                    run.execute('prepare', True)
                    fake.slot_readable, fake.slot_readback_fault = True, fault
                    if phase == 'restore':
                        fake.transport, fake.slot = 'fastboot', '_b'
                    checkpoint = len(fake.calls)
                    stopped(lambda p=phase: run.execute(p, True))
                    calls = fake.calls[checkpoint:]
                    index = max(i for i, args in enumerate(calls) if args[3:] == ['getvar', 'current-slot'])
                    require(not calls[index + 1:], 'bad post-set readback had subsequent calls')
                    tests.append('post-set-' + phase + '-' + fault + '-stops')
            for kind, directory_stat in (('symlink', 'symbolic link:2000:755'),
                                          ('owner', 'directory:0:755'), ('mode', 'directory:2000:777')):
                run, fake = fixture(tmp, 'staging-' + kind)
                fake.directory_stat = directory_stat
                stopped(lambda: run.execute('prepare', True))
                require(not any('push' in a or ' of=' in ' '.join(a) or "'rm " in ' '.join(a) for a in fake.calls),
                        'unsafe directory caused push/write/cleanup')
                tests.append('staging-' + kind + '-refused')
            run, fake = fixture(tmp, 'staging-exists')
            fake.remote_exists = True
            stopped(lambda: run.execute('prepare', True))
            require(not any('push' in a or ' of=' in ' '.join(a) for a in fake.calls), 'existing directory used')
            tests.append('staging-existing-mkdir-refused')
            for mode in ('666', '644'):
                run, fake = fixture(tmp, 'chmod-inert-' + mode)
                fake.chmod_inert, fake.file_stat = True, 'regular file:2000:' + mode
                stopped(lambda: run.execute('prepare', True))
                require(not (run.directory / 'prepare-writer.claim').exists(), 'unsafe file mode reached writer')
                require(not any(' of=' in ' '.join(args) for args in fake.calls), 'unsafe mode wrote B')
                tests.append('post-chmod-mode-' + mode + '-still-refused')
            for mode in ('600', '400', '640'):
                run, fake = fixture(tmp, 'file-mode-' + mode)
                run.directory.mkdir(parents=True)
                run.phase = 'prepare'
                run.serials.add('SYNTHETIC123')
                run.create('staging-created.json', {'path': run.remote, 'owner': 2000})
                fake.remote_files, fake.file_stat = {'candidate.img'}, 'regular file:2000:' + mode
                require(run.staging('SYNTHETIC123') == ['candidate.img'], 'safe file mode rejected')
            tests.append('file-mode-set-only-600-400-640-accepted')
            for fault in ('extra', 'symlink', 'permissions'):
                run, fake = fixture(tmp, 'restore-staging-' + fault)
                run.execute('prepare', True)
                if fault == 'extra':
                    fake.remote_files.add('unexpected.txt')
                else:
                    fake.file_stat = 'symbolic link:2000:644' if fault == 'symlink' else 'regular file:2000:666'
                checkpoint = len(fake.calls)
                stopped(lambda: run.execute('restore', True))
                require(not any('push' in a or ' of=' in ' '.join(a) or re.search(r"'(?:rm|rmdir) ", ' '.join(a))
                                for a in fake.calls[checkpoint:]), 'unsafe restore directory used')
                run.phase = 'restore'
                checkpoint = len(fake.calls)
                stopped(lambda: run.cleanup('SYNTHETIC123'))
                require(not any(re.search(r"'(?:rm|rmdir) ", ' '.join(a)) for a in fake.calls[checkpoint:]),
                        'unsafe cleanup removed entries')
                tests.append('restore-and-cleanup-staging-' + fault + '-refused')
            payload = b'\r\n\x00\xff\x80\n\r\x00binary\x81'
            payload_hash = hashlib.sha256(payload).hexdigest()
            path = Path(tmp) / 'host-binary.img'
            path.write_bytes(payload)
            Run.check_file(run, path, len(payload), payload_hash)
            stopped(lambda: Run.check_file(run, path, len(payload) + 1, payload_hash))
            stopped(lambda: Run.check_file(run, path, len(payload), '0' * 64))
            tests.append('real-check-file-binary-success-length-and-hash-failures')
            for fault in (None, 'statistics', 'short', 'timeout', 'hash'):
                run, fake = fixture(tmp, 'binary-' + str(fault))
                run.host_inputs = lambda: None
                run.check_file = lambda path, size, expected: Run.check_file(run, path, size, expected)
                run.write_b = lambda serial: None  # Isolate prepare backup gates, not mock their validation.
                fake.binary_payload = payload if fault != 'hash' else bytes([payload[0] ^ 1]) + payload[1:]
                fake.binary_fault = fault
                run.size, run.stock_sha256 = len(payload), payload_hash
                fake.size, fake.stock_sha = len(payload), payload_hash
                if fault is None:
                    run.execute('prepare', True)
                    require(run.backup.read_bytes() == payload, 'binary bytes changed')
                else:
                    stopped(lambda: run.execute('prepare', True))
                    require(not (run.directory / 'state-backup_verified.json').exists(), 'bad stream promoted backup')
                tests.append('real-file-stream-' + str(fault))
            for fault in ('timeout', 'oserror', 'offline'):
                run, fake = fixture(tmp, 'console-' + fault)
                run.execute('prepare', True)
                fake.slot_fault = fault
                import io
                output = io.StringIO()
                with patch.dict(globals(), {'Run': lambda *args, **kwargs: run}), contextlib.redirect_stdout(output):
                    require(main(['--phase', 'boot', '--run-id', 'synthetic', '--authorize-boot']) == 1,
                            'exception console path did not stop')
                persisted = ''.join(p.read_text() for p in run.directory.glob('*.json'))
                require('SYNTHETIC123' not in output.getvalue() + persisted, 'exception/console serial leak')
                tests.append('exception-console-redaction-' + fault)
            for absent, succeeds in ((2, True), (3, False)):
                run, fake = fixture(tmp, 'fastboot-wait-' + str(absent))
                run.execute('prepare', True)
                fake.fastboot_absent = absent
                if succeeds:
                    run.execute('boot', True)
                else:
                    stopped(lambda: run.execute('boot', True))
                    require(not any('set_active' in a for a in fake.calls), 'exhausted fastboot wait switched slot')
                require(sum(a[1:] == ['devices'] for a in fake.calls) == 3, 'fastboot wait round count')
                tests.append('bounded-fastboot-wait-' + str(absent))
            for transport, exhausted in (('adb', 151), ('fastboot', 76)):
                run, fake = fixture(tmp, 'budget-' + transport)
                run.directory.mkdir(parents=True)
                run.phase = 'restore' if transport == 'adb' else 'boot'
                with patch.object(time, 'monotonic', side_effect=[0, exhausted]):
                    stopped(lambda t=transport: run.wait_transport(t, 'SYNTHETIC123'))
                require(not fake.calls, 'exhausted wait budget spawned process')
            run, fake = fixture(tmp, 'budget-clipped')
            run.directory.mkdir(parents=True)
            run.phase, fake.transport = 'boot', 'fastboot'
            with patch.object(time, 'monotonic', side_effect=[0, 65, 65, 65]):
                require(run.wait_transport('fastboot', 'SYNTHETIC123') == 'SYNTHETIC123', 'clipped wait failed')
            require(fake.timeouts == [10, 10], 'child timeouts not clipped to remaining budget')
            tests.append('shared-wait-time-budget-clipping-and-exhaustion')
            run, fake = fixture(tmp, 'exec-out-argv')
            run.directory.mkdir(parents=True)
            run.phase = 'prepare'
            run.serials.add('SYNTHETIC123')
            run.readback('SYNTHETIC123', 'argv-probe.img', STOCK)
            require(fake.calls == [[run.adb, '-s', 'SYNTHETIC123', 'exec-out', 'su', '-c',
                                     'dd if=' + BLOCK + ' bs=1048576 2>/dev/null']],
                    'exec-out su -c raw argument changed')
            tests.append('exec-out-exact-raw-su-command-argv')
            checkpoint = len(fake.calls)
            for bad in ("'dd if=" + BLOCK + " bs=1048576 2>/dev/null'",
                        'dd if=' + BLOCK + ' bs=1048576 count=1 2>/dev/null',
                        'dd if=/dev/block/by-name/userdata bs=1048576 2>/dev/null'):
                stopped(lambda c=bad: run.call(run.adb, ['-s', 'SYNTHETIC123', 'exec-out', 'su', '-c', c],
                                               binary_path=run.directory / 'rejected.img'))
            require(len(fake.calls) == checkpoint and not (run.directory / 'rejected.img').exists(),
                    'quoted/arbitrary exec-out read passed whitelist')
            tests.append('old-quoted-and-non-whitelist-exec-out-refused')
            # Continuation profile binding: increment only, all synthetic; default remains stop.
            require(Run(tmp, 'profile-default', 'adb.exe', 'fastboot.exe').profile == STOP_PROFILE,
                    'default profile is not the stop profile')
            stopped(lambda: Run(tmp, 'profile-bogus', 'adb.exe', 'fastboot.exe', profile='bogus'))
            continuation = PROFILES[CONTINUATION_PROFILE]
            require(continuation['candidate_sha256'] ==
                    '4a52ddbc2cc06401f76676f480eb1b0e4b1dfafce0a8d07b453dd53967a05618' and
                    continuation['stock_sha256'] == STOCK and continuation['r4_sha256'] == R4 and
                    continuation['bytes'] == SIZE and continuation['r4_bytes'] == 1495040 and
                    continuation['frozen']['kernel_sha256'] ==
                    '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4' and
                    continuation['frozen']['args'] == '-v serial=3' and
                    continuation['frozen']['fat_sha256'] ==
                    '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c' and
                    continuation['frozen']['adt_sha256'] ==
                    '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4',
                    'continuation frozen mapping drift')
            tests.append('profile-default-stop-and-frozen-continuation-mapping')
            run, fake = fixture(tmp, 'continuation-happy', CONTINUATION_PROFILE)
            run.execute('prepare', True)
            require(run.state() == 'candidate_verified_on_B' and
                    json.loads((run.directory / 'run-identity.json').read_text(encoding='utf-8')) == run.identity(),
                    'continuation prepare identity/state failed')
            boot = run.execute('boot', True)
            require('first natural panic' in boot['message'] and
                    'MAC Framework successfully initialized' in boot['message'] and
                    LABEL not in boot['message'] and 'manually return to bootloader' in boot['message'],
                    'continuation observation text wrong')
            stopped(lambda: run.execute('boot', True))
            (run.repo / run.frozen['evidence']).unlink()
            require(not run.candidate.exists(), 'synthetic candidate unexpectedly present')
            run.execute('restore', True)  # Restore must not need candidate/r4/evidence.
            require(run.state() == 'B_restored_verified' and fake.slot == '_a' and fake.stock,
                    'continuation restore independence failed')
            require(sum(a[3:4] == ['boot'] for a in fake.calls) == 1, 'continuation boot replay not refused')
            tests.append('continuation-three-phase-single-boot-restore-without-candidate')
            run, fake = fixture(tmp, 'continuation-wrong-candidate', CONTINUATION_PROFILE)
            fake.candidate_sha = '0' * 64
            stopped(lambda: run.execute('prepare', True))
            require(not any(' of=' in ' '.join(a) for a in fake.calls) and
                    not (run.directory / 'state-candidate_verified_on_B.json').exists(),
                    'continuation wrong candidate hash reached writer')
            tests.append('continuation-mock-device-candidate-hash-refused-before-write')
            run, fake = fixture(tmp, 'continuation-wrong-evidence', CONTINUATION_PROFILE)
            evidence = run.repo / run.frozen['evidence']
            evidence.write_text(json.dumps({'profile': run.profile, 'vendor_boot_sha256': run.candidate_sha256,
                                            'vendor_boot_bytes': run.size,
                                            'vendor_ramdisk_sha256': run.frozen['fat_sha256'],
                                            'kernel_sha256': '0' * 64,
                                            'adt_sha256': run.frozen['adt_sha256'],
                                            'args_exact': run.frozen['args'],
                                            'input_binding': {'fat_sha256': run.frozen['fat_sha256']},
                                            'fat_hashes': {'Payloads/kernel.macho': '0' * 64,
                                                           'Payloads/kernel.macho.adt': run.frozen['adt_sha256']}}),
                                encoding='utf-8')
            checkpoint = len(fake.calls)
            stopped(lambda: run.execute('prepare', True))
            require(len(fake.calls) == checkpoint and not run.directory.exists(),
                    'wrong evidence touched device/state')
            tests.append('continuation-wrong-evidence-refused-before-device')
            # Real host-file validation, distinct from the mock device hash paths above.
            probe = Path(tmp) / 'small-host-candidate.bin'
            probe.write_bytes(b'host-candidate-probe-v1')
            probe_hash = hashlib.sha256(probe.read_bytes()).hexdigest()
            Run.check_file(run, probe, probe.stat().st_size, probe_hash)
            stopped(lambda: Run.check_file(run, probe, probe.stat().st_size + 1, probe_hash))
            stopped(lambda: Run.check_file(run, probe, probe.stat().st_size, '0' * 64))
            tests.append('real-host-check-file-small-success-size-hash')
            run, fake = fixture(tmp, 'identity-tamper', CONTINUATION_PROFILE)
            run.execute('prepare', True)
            identity_path = run.directory / 'run-identity.json'
            original = json.loads(identity_path.read_text(encoding='utf-8'))

            def write_identity(value):
                identity_path.write_text(json.dumps(value), encoding='utf-8')

            def tamper(mutate):
                value = json.loads(json.dumps(original))
                mutate(value)
                write_identity(value)
                checkpoint = len(fake.calls)
                stopped(lambda: run.require_identity())
                require(len(fake.calls) == checkpoint and
                        not (run.directory / 'active.lock').exists() and
                        not (run.directory / 'boot.claim').exists() and
                        not (run.directory / 'restore.claim').exists(),
                        'identity tamper touched device/lock/claim')

            for mutate in (lambda v: v.__setitem__('run_id', 'different-run'),
                           lambda v: v.__setitem__('profile', STOP_PROFILE),
                           lambda v: v.__setitem__('candidate', 'out/other/vendor_boot.img'),
                           lambda v: v.__setitem__('candidate_sha256', '0' * 64),
                           lambda v: v.__setitem__('candidate_bytes', v['candidate_bytes'] + 1),
                           lambda v: v.__setitem__('stock_sha256', '0' * 64),
                           lambda v: v.__setitem__('r4_sha256', '0' * 64),
                           lambda v: v['frozen'].__setitem__('kernel_sha256', '0' * 64),
                           lambda v: v['frozen'].__setitem__('args', '-v serial=3 reset=1'),
                           lambda v: v['frozen'].__setitem__('fat_sha256', '0' * 64),
                           lambda v: v['frozen'].__setitem__('adt_sha256', '0' * 64),
                           lambda v: v['frozen'].__setitem__('evidence', 'out/other/record.json')):
                tamper(mutate)
            missing_run = json.loads(json.dumps(original))
            missing_run.pop('run_id')
            write_identity(missing_run)
            stopped(lambda: run.require_identity())
            require(json.loads(identity_path.read_text(encoding='utf-8')) == missing_run,
                    'identity missing run_id was auto-filled/overwritten')
            write_identity(original)
            for phase in ('boot', 'restore'):
                value = json.loads(json.dumps(original))
                value['run_id'] = 'different-run'
                write_identity(value)
                checkpoint = len(fake.calls)
                stopped(lambda p=phase: run.execute(p, True))
                claim = 'boot.claim' if phase == 'boot' else 'restore.claim'
                require(len(fake.calls) == checkpoint and
                        not (run.directory / 'active.lock').exists() and
                        not (run.directory / claim).exists(),
                        'identity check ran after device/lock/claim for ' + phase)
                write_identity(original)
            other, other_fake = fixture(tmp, 'identity-same-profile-other-run', CONTINUATION_PROFILE)
            other.execute('prepare', True)
            (other.directory / 'run-identity.json').write_text(json.dumps(original), encoding='utf-8')
            stopped(lambda: other.require_identity())
            require(not (other.directory / 'boot.claim').exists() and
                    not (other.directory / 'restore.claim').exists(),
                    'same-profile identity swap reached claim')
            tests.append('identity-run-id-and-field-tamper-same-profile-swap')

            def evidence_case(name, mutate=None, raw=None):
                case_run, case_fake = fixture(tmp, 'evidence-' + name, CONTINUATION_PROFILE)
                path = case_run.repo / case_run.frozen['evidence']
                if raw is not None:
                    path.write_text(raw, encoding='utf-8')
                else:
                    value = json.loads(path.read_text(encoding='utf-8'))
                    mutate(value)
                    path.write_text(json.dumps(value), encoding='utf-8')
                checkpoint = len(case_fake.calls)
                stopped(lambda: case_run.execute('prepare', True))
                require(len(case_fake.calls) == checkpoint and not case_run.directory.exists() and
                        not (case_run.directory / 'active.lock').exists() and
                        not (case_run.directory / 'prepare.claim').exists(),
                        'evidence rejection was not before device/state: ' + name)

            evidence_case('missing-vendor-ramdisk', lambda v: v.pop('vendor_ramdisk_sha256'))
            evidence_case('wrong-vendor-ramdisk', lambda v: v.__setitem__('vendor_ramdisk_sha256', '0' * 64))
            evidence_case('mixed-vendor-ramdisk', lambda v: v.__setitem__('vendor_ramdisk_sha256', 123))
            evidence_case('missing-binding-fat', lambda v: v['input_binding'].pop('fat_sha256'))
            evidence_case('wrong-binding-fat', lambda v: v['input_binding'].__setitem__('fat_sha256', '0' * 64))
            evidence_case('binding-list', lambda v: v.__setitem__('input_binding', ['not', 'dict']))
            evidence_case('binding-string', lambda v: v.__setitem__('input_binding', 'not-a-dict'))
            evidence_case('record-list', raw='[1, 2, 3]')
            evidence_case('record-string', raw='"not-a-record"')
            evidence_case('args', lambda v: v.__setitem__('args_exact', '-v serial=3 reset=1'))
            evidence_case('outer-hash', lambda v: v.__setitem__('vendor_boot_sha256', '0' * 64))
            evidence_case('outer-size', lambda v: v.__setitem__('vendor_boot_bytes', v['vendor_boot_bytes'] + 1))
            evidence_case('record-kernel', lambda v: v.__setitem__('kernel_sha256', '0' * 64))
            evidence_case('record-adt', lambda v: v.__setitem__('adt_sha256', '0' * 64))
            evidence_case('fat-kernel', lambda v: v['fat_hashes'].__setitem__('Payloads/kernel.macho', '0' * 64))
            evidence_case('fat-adt', lambda v: v['fat_hashes'].__setitem__('Payloads/kernel.macho.adt', '0' * 64))
            tests.append('evidence-fat-two-fields-type-args-outer-size-refusals')
            run, fake = fixture(tmp, 'continuation-cross-profile', CONTINUATION_PROFILE)
            run.execute('prepare', True)
            checkpoint = len(fake.calls)
            other = Run(run.repo, run.run_id, 'adb.exe', 'fastboot.exe', runner=fake, pause=lambda _: None)
            for phase in ('boot', 'restore'):
                stopped(lambda p=phase: other.execute(p, True))
            require(len(fake.calls) == checkpoint and
                    not (run.directory / 'boot.claim').exists() and
                    not (run.directory / 'restore.claim').exists(),
                    'cross-profile use reached claim')
            tests.append('cross-profile-boot-restore-refused-before-claims')
            legacy, legacy_fake = fixture(tmp, 'legacy-stop')
            legacy.directory.mkdir(parents=True)
            legacy.backup.write_bytes(b'synthetic-backup')
            checkpoint = len(legacy_fake.calls)
            legacy.require_identity()
            require(not (legacy.directory / 'run-identity.json').exists(), 'legacy run migrated')
            stopped(lambda: Run(legacy.repo, legacy.run_id, 'adb.exe', 'fastboot.exe', runner=legacy_fake,
                                pause=lambda _: None, profile=CONTINUATION_PROFILE).execute('restore', True))
            require(len(legacy_fake.calls) == checkpoint and
                    not (legacy.directory / 'restore.claim').exists(),
                    'legacy continuation restore reached device/claim')
            legacy.execute('restore', True)  # Legacy stop restore still works.
            require(legacy.state() == 'B_restored_verified' and legacy_fake.slot == '_a',
                    'legacy stop restore failed')
            tests.append('legacy-no-identity-stop-only-no-migration-and-restore')
            run, fake = fixture(tmp, 'legacy-consumed-boot')
            run.directory.mkdir(parents=True)
            run.create('state-candidate_verified_on_B.json', {'state': 'candidate_verified_on_B', 'previous': None})
            run.create('boot-attempt.claim', {'consumed_before_boot': True})
            checkpoint = len(fake.calls)
            stopped(lambda: run.execute('boot', True))
            stopped(lambda: Run(run.repo, run.run_id, 'adb.exe', 'fastboot.exe', runner=fake,
                                pause=lambda _: None, profile=CONTINUATION_PROFILE).execute('boot', True))
            require(len(fake.calls) == checkpoint, 'legacy consumed claim touched device')
            tests.append('legacy-r4-consumed-boot-claim-never-reused')
            run, fake = fixture(tmp, 'amnm-happy', AMNM_PROFILE)
            run.execute('prepare', True)
            result = run.execute('boot', True)
            require('original panic' in result['message'] and 'AMNM snapshot' in result['message'], 'AMNM observation')
            stopped(lambda: run.execute('boot', True))
            for key in ('derived', 'report', 'audit'):
                (run.repo / run.frozen[key]).unlink()
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified' and fake.stock and
                    sum(a[3:4] == ['boot'] for a in fake.calls) == 1, 'AMNM restore independence')
            tests.append('amnm-single-boot-restore-without-inputs')
            for key in ('derived', 'report', 'audit'):
                run, fake = fixture(tmp, 'amnm-bad-' + key, AMNM_PROFILE)
                path = run.repo / run.frozen[key]
                path.write_bytes(path.read_bytes() + b' ')
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'AMNM bad hash reached device/claim')
            run, fake = fixture(tmp, 'amnm-record-mixed', AMNM_PROFILE)
            mixed = run.repo / run.frozen['derived']
            mixed.write_text('{"profile":"' + CONTINUATION_PROFILE + '"}')
            run.frozen = dict(run.frozen, derived_sha256=file_hash(mixed))  # Isolated fixture: exercise shape gate too.
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'AMNM mixed record reached device/claim')
            tests.append('amnm-bad-evidence-and-mixed-record-before-claim')
            for which in ('candidate', 'r4', 'fat'):
                run, fake = fixture(tmp, 'amnm-bad-input-' + which, AMNM_PROFILE)
                target = run.repo / run.frozen['fat'] if which == 'fat' else getattr(run, which)
                def reject_input(path, size, expected):
                    require(path != target, 'synthetic frozen input mismatch')
                run.check_file = reject_input
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'AMNM bad input reached device/claim')
            tests.append('amnm-candidate-r4-fat-rejection-before-claim')
            run, fake = fixture(tmp, 'amnm-identity-a', AMNM_PROFILE)
            run.execute('prepare', True)
            other, other_fake = fixture(tmp, 'amnm-identity-b', AMNM_PROFILE)
            other.execute('prepare', True)
            (other.directory / 'run-identity.json').write_bytes((run.directory / 'run-identity.json').read_bytes())
            checkpoint = len(other_fake.calls)
            for phase in ('boot', 'restore'):
                stopped(lambda p=phase: other.execute(p, True))
            require(len(other_fake.calls) == checkpoint and not (other.directory / 'active.lock').exists() and
                    not (other.directory / 'boot.claim').exists() and not (other.directory / 'restore.claim').exists(),
                    'AMNM cross-run identity reached device/claim')
            tests.append('amnm-cross-run-identity-rejected')
            run, fake = fixture(tmp, 'chmh-happy', CHMH_PROFILE)
            run.execute('prepare', True)
            result = run.execute('boot', True)
            require('Missing panic is not success' in result['message'], 'CHMH observation')
            stopped(lambda: run.execute('boot', True))
            for key in ('derived', 'report', 'audit', 'audit_source'):
                (run.repo / run.frozen[key]).unlink()
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified' and fake.stock and
                    sum(a[3:4] == ['boot'] for a in fake.calls) == 1, 'CHMH restore independence')
            tests.append('chmh-single-boot-restore-without-inputs')
            for key in ('derived', 'report', 'audit', 'audit_source'):
                run, fake = fixture(tmp, 'chmh-bad-' + key, CHMH_PROFILE)
                path = run.repo / run.frozen[key]
                path.write_bytes(path.read_bytes() + b' ')
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'CHMH bad evidence reached claim/device')
            run, fake = fixture(tmp, 'chmh-wrong-path', CHMH_PROFILE)
            path = run.repo / run.frozen['report']
            data = json.loads(path.read_bytes()); data['record_path'] = str(run.repo / 'wrong-record.json')
            path.write_text(json.dumps(data))
            run.frozen = dict(run.frozen, report_sha256=file_hash(path))
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'CHMH wrong path reached claim/device')
            tests.append('chmh-evidence-hash-and-path-rejected-before-claims')
            for which in ('candidate', 'r4', 'fat', 'adt'):
                run, fake = fixture(tmp, 'chmh-bad-input-' + which, CHMH_PROFILE)
                target = run.repo / run.frozen[which] if which in ('fat', 'adt') else getattr(run, which)
                def reject_chmh_input(path, size, expected):
                    require(path != target, 'synthetic CHMH frozen input mismatch')
                run.check_file = reject_chmh_input
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'CHMH bad input reached device/claim')
            tests.append('chmh-candidate-r4-fat-adt-rejected-before-claims')
            run, fake = fixture(tmp, 'chmh-identity-a', CHMH_PROFILE)
            run.execute('prepare', True)
            other, other_fake = fixture(tmp, 'chmh-identity-b', CHMH_PROFILE)
            other.execute('prepare', True)
            (other.directory / 'run-identity.json').write_bytes((run.directory / 'run-identity.json').read_bytes())
            checkpoint = len(other_fake.calls)
            for phase in ('boot', 'restore'):
                stopped(lambda p=phase: other.execute(p, True))
            require(len(other_fake.calls) == checkpoint and not (other.directory / 'active.lock').exists(),
                    'CHMH cross-run identity reached device/lock')
            switched = Run(run.repo, run.run_id, 'adb.exe', 'fastboot.exe', runner=fake,
                           pause=lambda _: None, profile=CONTINUATION_PROFILE)
            checkpoint = len(fake.calls)
            stopped(lambda: switched.execute('restore', True))
            require(len(fake.calls) == checkpoint and not (run.directory / 'restore.claim').exists(),
                    'CHMH cross-profile identity reached device/claim')
            tests.append('chmh-cross-run-and-profile-rejected')
            run, fake = fixture(tmp, 'pthread-happy', PTHREAD_PROFILE)
            run.execute('prepare', True)
            result = run.execute('boot', True)
            require('pthread_init' in result['message'] and 'No output is not success' in result['message'],
                    'pthread observation mismatch')
            stopped(lambda: run.execute('boot', True))
            for key in ('derived', 'report', 'audit', 'audit_source', 'layout'):
                (run.repo / run.frozen[key]).unlink()
            for item in run.frozen['evidence'].values():
                (run.repo / item['path']).unlink()
            require(not run.candidate.exists() and not run.r4.exists(), 'synthetic inputs unexpectedly exist')
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified' and fake.stock and
                    sum(a[3:4] == ['boot'] for a in fake.calls) == 1, 'pthread restore independence')
            tests.append('pthread-single-boot-restore-without-assets')
            for key in ('derived', 'report', 'audit', 'audit_source', 'layout'):
                run, fake = fixture(tmp, 'pthread-bad-' + key, PTHREAD_PROFILE)
                path = run.repo / run.frozen[key]
                path.write_bytes(path.read_bytes() + b' ')
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'pthread bad evidence reached device/claim')
            for key in PROFILES[PTHREAD_PROFILE]['frozen']['evidence']:
                run, fake = fixture(tmp, 'pthread-bad-evidence-' + key, PTHREAD_PROFILE)
                path = run.repo / run.frozen['evidence'][key]['path']
                path.write_bytes(path.read_bytes() + b' ')
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'pthread bad provenance reached device/claim')
            tests.append('pthread-evidence-source-and-provenance-refused-before-claim')
            for which in ('candidate', 'r4', 'kernel', 'fat', 'adt'):
                run, fake = fixture(tmp, 'pthread-bad-input-' + which, PTHREAD_PROFILE)
                target = run.repo / run.frozen[which] if which in ('kernel', 'fat', 'adt') else getattr(run, which)
                def reject_pthread_input(path, size, expected):
                    require(path != target, 'synthetic pthread frozen input mismatch')
                run.check_file = reject_pthread_input
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'pthread bad input reached device/claim')
            tests.append('pthread-candidate-r4-kernel-fat-adt-refused-before-claim')
            run, fake = fixture(tmp, 'pthread-wrong-path', PTHREAD_PROFILE)
            path = run.repo / run.frozen['report']
            data = json.loads(path.read_bytes()); data['record_path'] = str(run.repo / 'wrong-record.json')
            path.write_text(json.dumps(data))
            run.frozen = dict(run.frozen, report_sha256=file_hash(path))
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'pthread wrong path reached device/claim')
            run, fake = fixture(tmp, 'pthread-wrong-material', PTHREAD_PROFILE)
            path = run.repo / run.frozen['derived']
            data = json.loads(path.read_bytes()); data['material_hex'] = '00'
            path.write_text(json.dumps(data))
            run.frozen = dict(run.frozen, derived_sha256=file_hash(path))
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'pthread wrong material reached device/claim')
            tests.append('pthread-record-path-and-material-refused-before-claim')
            run, fake = fixture(tmp, 'pthread-identity-a', PTHREAD_PROFILE)
            run.execute('prepare', True)
            other, other_fake = fixture(tmp, 'pthread-identity-b', PTHREAD_PROFILE)
            other.execute('prepare', True)
            (other.directory / 'run-identity.json').write_bytes((run.directory / 'run-identity.json').read_bytes())
            checkpoint = len(other_fake.calls)
            for phase in ('boot', 'restore'):
                stopped(lambda p=phase: other.execute(p, True))
            require(len(other_fake.calls) == checkpoint and not (other.directory / 'active.lock').exists(),
                    'pthread cross-run identity reached device/lock')
            switched = Run(run.repo, run.run_id, 'adb.exe', 'fastboot.exe', runner=fake,
                           pause=lambda _: None, profile=CHMH_PROFILE)
            checkpoint = len(fake.calls)
            stopped(lambda: switched.execute('restore', True))
            require(len(fake.calls) == checkpoint and not (run.directory / 'restore.claim').exists(),
                    'pthread cross-profile identity reached device/claim')
            tests.append('pthread-cross-run-and-profile-refused')
            for field, value in (('args', '-v serial=3 nuwa-pmgr=1'), ('args', '-v serial=3 nuwa-pmgr=3'),
                                 ('args', '-v serial=3'), ('chmh_hex', '00')):
                run, fake = fixture(tmp, 'pmgr-frozen-' + str(len(tests)), PMGR_PROFILE)
                run.frozen = dict(run.frozen, **{field: value})
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'PMGR frozen gate reached device/claim')
                tests.append('pmgr-reject-' + value)
            for key in ('derived', 'source', 'audit', 'provenance'):
                run, fake = fixture(tmp, 'pmgr-bad-' + key, PMGR_PROFILE)
                path = run.repo / run.frozen[key]
                path.write_bytes(path.read_bytes() + b' ')
                stopped(lambda: run.execute('prepare', True))
                require(not fake.calls and not run.directory.exists(), 'PMGR evidence gate reached device/claim')
                tests.append('pmgr-bad-' + key)
            run, fake = fixture(tmp, 'pmgr-bad-path', PMGR_PROFILE)
            path = run.repo / run.frozen['report']
            data = json.loads(path.read_bytes()); data['record_path'] = 'record.json'
            path.write_text(json.dumps(data))
            run.frozen = dict(run.frozen, report_sha256=file_hash(path))
            stopped(lambda: run.execute('prepare', True))
            require(not fake.calls and not run.directory.exists(), 'PMGR path gate reached device/claim')
            tests.append('pmgr-record-path-refused')
            run, fake = fixture(tmp, 'pmgr-identity', PMGR_PROFILE)
            run.execute('prepare', True)
            identity = run.directory / 'run-identity.json'
            original = identity.read_bytes()
            data = json.loads(original); data['frozen']['args'] = '-v serial=3 nuwa-pmgr=1'
            identity.write_text(json.dumps(data))
            checkpoint = len(fake.calls)
            for phase in ('boot', 'restore'):
                stopped(lambda p=phase: run.execute(p, True))
            require(len(fake.calls) == checkpoint and not (run.directory / 'active.lock').exists(), 'PMGR identity gate failed')
            identity.write_bytes(original)
            switched = Run(run.repo, run.run_id, 'adb.exe', 'fastboot.exe', runner=fake, profile=PTHREAD_PROFILE)
            stopped(lambda: switched.execute('restore', True))
            require(len(fake.calls) == checkpoint, 'PMGR cross-profile restore reached device')
            for key in ('derived', 'report', 'audit', 'layout', 'provenance', 'source', 'config'):
                (run.repo / run.frozen[key]).unlink()
            require(not run.candidate.exists(), 'synthetic candidate unexpectedly exists')
            run.execute('restore', True)
            require(run.state() == 'B_restored_verified', 'PMGR restore required candidate/evidence')
            tests.append('pmgr-identity-cross-profile-and-restore-without-assets')
            for profile in PROFILES:
                for phase in ('prepare', 'boot', 'restore'):
                    run, fake = fixture(tmp, 'dry9-' + str(len(tests)) + '-' + phase, profile)
                    result = run.execute(phase)
                    require(result['device_commands_executed'] == 0 and not fake.calls and not run.directory.exists(),
                            'dry-run touched device or run directory')
                tests.append('dry-three-phases-' + profile)
            import io
            for profile, label in ((STOP_PROFILE, 'stop'), (CONTINUATION_PROFILE, 'continuation')):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    require(main(['--phase', 'prepare', '--run-id', 'dry-' + label,
                                  '--profile', profile]) == 0, 'dry-run main failed')
                payload = json.loads(output.getvalue())
                require(payload['dry_run'] and payload['device_commands_executed'] == 0 and
                        payload['profile'] == profile and
                        payload['run_identity']['candidate_sha256'] == PROFILES[profile]['candidate_sha256'] and
                        not (REPO / 'out' / ('pmap-ret-run-dry-' + label)).exists(),
                        'profile dry-run executed or lost identity')
                if profile == CONTINUATION_PROFILE:
                    require('owner-continuation-vendor-boot-20261111-final' in
                            payload['run_identity']['candidate'], 'continuation candidate identity wrong')
            tests.append('no-flag-and-explicit-profile-dry-run-zero-commands')
    print(json.dumps({'self_checked': True, 'real_device_commands': 0,
                      'synthetic_evidence': tmp, 'test_groups': len(tests), 'passed': tests}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('prepare', 'boot', 'restore'))
    parser.add_argument('--run-id')
    parser.add_argument('--profile', choices=tuple(PROFILES), default=STOP_PROFILE,
                        help='Default remains the frozen stop profile; continuation is explicit opt-in')
    parser.add_argument('--adb', default='D:/AndroidPhoneStuff/platform-tools/adb.exe')
    parser.add_argument('--fastboot', default='D:/AndroidPhoneStuff/platform-tools/fastboot.exe')
    parser.add_argument('--self-check', action='store_true')
    for phase in ('prepare', 'boot', 'restore'):
        parser.add_argument('--authorize-' + phase, action='store_true')
    args = parser.parse_args(argv)
    if args.self_check:
        self_check()
        return 0
    if args.phase is None or args.run_id is None:
        parser.error('--phase and --run-id required outside --self-check')
    run = Run(REPO, args.run_id, args.adb, args.fastboot, profile=args.profile)
    try:
        result = run.execute(args.phase, getattr(args, 'authorize_' + args.phase))
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        # Never stringify process exceptions: their argv may contain the serial.
        message = str(error) if isinstance(error, Stop) else type(error).__name__
        print(json.dumps({'stopped': True, 'reason': message, 'state': run.state(),
                          'restore_hint': 'Do not reboot/retry writers; retain backup; inspect events and request restore authorization.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
