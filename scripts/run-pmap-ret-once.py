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
ROOT_PROFILE = 'ufs-apfs-root-20261115-r11'
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
PROFILES['ufs-apfs-root-20261115-r9'] = {
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
# r10: r8's package with the upstream trust-cache kernel. Same args, same two-module
# trust bundle; the local 8796-nuwa-trust-cache-init.patch is replaced by the upstream
# native-trust-cache-runtime.patch, so the kernel digest and every CHMH-derived hash move.
_r10_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r10/'
_r10_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_r10_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r10',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7',
    'kernel_bytes': 55545856, 'kernel_sha256': 'c015d041220e13cdf4173b075b4b2c4a91a5e80f9c80d4449d8ae5173bde136e',
    'kernel_path': 'out/nuwa-native-trust-cache-20261115-r1/kernel.macho',
    'fat_sha256': 'c479c5e19292404b230576c219c85118cabc67bd34e63703318eef5f8ac527da',
    'adt_bytes': 13548, 'adt_sha256': '341a5d9b2e15c67f7e0a44081a10ec747bcd855f4c5fc6bb664aef95b280524f',
    'derived_sha256': '82092ddd2524296aac718c5490e12e3897e52f7fcf0d09a983a872ff309225fd',
    'report_sha256': '5af3399195dda4e000cbf239af444895671b469260a8fcca035bbc21f24746c8',
    'audit_sha256': '1c88ff5abf2d1ad572cd33e9249976502d9dbe0b56c7506c0ae7ab85385fe27d',
    'layout_sha256': '97db13bd7189fb0c0bfd1502c6b7992355ab06626f5df37e5545b9eb54ed6181',
    'provenance_sha256': '0b9837d4ec7636a3e32243f622b097b43e31afb8a13611b5ecc5fc244fafe26b',
    'config_bytes': 504, 'config_sha256': '9600826a392f124f949c4b72a83170c3cda2e04b3b4dfc808a678f0884c34a40',
    'source': 'scripts/build-ufs-apfs-root-chmh-r10.py',
    'source_sha256': '2815ca6a8be9ca3cc267176dd200bf9648a8eb6303f75845d71f1250c634375b',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '54629b6e1b49b523aa9cd7076a64cf80db3df246bc2666334c1dbc6ac9346b77e46a40e07d2f8c43ddd1b47ea52e118c',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r10_frozen[_key] = _r10_dir + _name
PROFILES['ufs-apfs-root-20261115-r10'] = {
    'candidate': _r10_dir + 'vendor_boot.img',
    'candidate_sha256': 'e1a6d789455fd6c01d1026648b5971023b30c4585791a4bc63d89dba662bebc8',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not mount success. Failures display panic text; success has only '
                    'bounded ROOT_ENTER, WINDOW_START, MEDIA_WAIT, MEDIA_READY and ROOT_PUBLISHED markers. '
                    'MEDIA_READY and ROOT_PUBLISHED do not prove mounting. Judge mount outcome from existing '
                    'panic or later evidence. Userdata installation is separate and not performed here. '
                    'No automatic retry; manually return to bootloader and restore separately with authorization.'),
    'frozen': _r10_frozen,
}
# r11: the boot progress layer. Nine objects carry the ported call sites
# (patches/xnu/8796-nuwa-boot-progress.patch) and libBootProgress.a is force-loaded;
# args gain boot-progress=2 (continuous mode: the 30 s stall / 120 s deadline only
# warn, the OS keeps running) and build-tag=nuwa-r11 (printed in the title row), so the
# args material, CHMH digest, ADT, FAT and outer hashes all move again.
_r11_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r11/'
_r11_frozen = dict(PROFILES[NOP_PROFILE]['frozen'])
_r11_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r11',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r11',
    'kernel_bytes': 55595008, 'kernel_sha256': 'b2c5ed6017aa58a1f25a998e585f060a5ea28dbcf0a14e7faca1ee4687dae167',
    'kernel_path': 'out/nuwa-bootprogress-20261115-r1/kernel.macho',
    'fat_sha256': '4bafff0b834a83999ab72cc455872595ee66429766bd284c06e8783965f3afec',
    'adt_bytes': 13548, 'adt_sha256': 'f956a48f05771ab01405ee5f0d776b047102d4d6c4bff55d5cfced02d607753c',
    'derived_sha256': '8d09b52af5d141b715565dc297669793bd639aae5d88813781c4d6d8ec575459',
    'report_sha256': 'b4f5d5a52cdfab72f46cea1434d854c6ec364c07c5811698bee77d40ccb7737c',
    'audit_sha256': 'aa9ce980d6978a086f300cc1f4c0101588d3204857e249ca3bbad91bf28915ed',
    'layout_sha256': '732a1ccdcd9ea27c927b938311ca873217b52b1be7ec8b237662125919197b13',
    'provenance_sha256': 'f359a76f431cbbb7e2caee2dfb8f1f4ab7b3befe61a44ecdf3f22934618ce183',
    'config_bytes': 539, 'config_sha256': '8a97a11eb3a6c2a9bd5ef159cec34ec51b2d557eb687b364e249efa2ed310071',
    'source': 'scripts/build-ufs-apfs-root-chmh-r11.py',
    'source_sha256': '6bbaaf2ce884507d6b41c4e9f44e40316a52a5d52ab218b9943e3014ca7552d3',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '39bf82f106904b47d5d0cf6fc756e5bb4b08e1c7578ed7eb13cc3350de4946e43401a92639852ac3eb921a057675e59b',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r11_frozen[_key] = _r11_dir + _name
PROFILES[ROOT_PROFILE] = {
    'candidate': _r11_dir + 'vendor_boot.img',
    'candidate_sha256': 'f63b5b54bd30a03908e29fa8b06167b121fe9b4d0e0af26aa291162a3a7c290d',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not a screen claim. Expect the boot progress page as soon as the '
                    'video console binds: title row with [nuwa-r11], then time=, UFS requests/verified4K and the '
                    'stage rows (arm_vm_init, bsd_init, vfs_mountroot, load_init_program, exec process signature). '
                    'boot-progress=2 is continuous: the 30 s stall / 120 s deadline only change the title, the OS '
                    'keeps running, and the page is whatever the kernel last recorded. No automatic retry; '
                    'manually return to bootloader and restore separately with authorization.'),
    'frozen': _r11_frozen,
}


# r12: the SystemOS cryptex mount (kern_exec.c + nuwa_systemos.c + the vm_unix.c
# cache-location exception) and the boot progress r12 renderer (scale 3, pid1/SYSOS row).
# Args gain build-tag=nuwa-r12 and boot-progress-scale=3, so the args material, CHMH
# digest, ADT, FAT and outer hashes all move again.  This becomes the current root
# profile below; the r11 entry above stays intact and reachable by name.
_r12_dir = 'out/nuwa-ufs-apfs-root-chmh-20261115-r12/'
_r12_frozen = dict(_r11_frozen)
_r12_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261115-r12',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12 boot-progress-scale=3',
    'kernel_bytes': 55623680, 'kernel_sha256': 'ce2cd4666eb7afa1f9d3d805f76a0636ad239b0c2708a90f5798fa3700e01dd2',
    'kernel_path': 'out/nuwa-systemos-mount-20261115-r1/kernel.macho',
    'fat_sha256': 'bd8dca47b5d130ca3f846ad13bb616a61941f74c17807c4621934c3376ca13ab',
    'adt_bytes': 13548, 'adt_sha256': '3b28b659119356ad14aef2bebea8782727239a8bbd2fc80be4c8c97edd20822d',
    'derived_sha256': '41dd88fd13b775422a3b86c7666572b8dd6caf3d7c19674c416e63776e2db0aa',
    'report_sha256': '2d458127e9263d4064413331cd5d301c4ce36757c3f490de2c284b3464489524',
    'audit_sha256': '46ab5b3d57a79ceae834accfa69628f857c2c00e1d3225352932b0a036326b58',
    'layout_sha256': '340de87fd15dc6be4e77628323c34d5f67640aef92f2ac91df5cdda383871c1c',
    'provenance_sha256': '5caf7eb2b6e0c08c5b7244f9fa92cee504a39a3d6b4ef52b0b0b6d4ba1a94fa0',
    'config_bytes': 561, 'config_sha256': '55bdd51c4a39a45e291932b20470f638a618d407a03deae92dde4bfacc253515',
    'source': 'scripts/build-ufs-apfs-root-chmh-r12.py',
    'source_sha256': '3b4984c7b9b590c6a8d06f3e82fce33b96f82cde5b5f8dc323bc23dd1fde63e3',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '58aab3e96a089f08cfd6f9b80f2fb5dd20ab32d5840b8f2bc8b97122aa338fd9bada75c9a88b1cd25006f6100cb1d15b',
    'evidence': {
        'root_inputs': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-inputs.json', 'sha256': 'bc344eb1f00aacccb6c09b07b3100800fe26acda77fb216139fbae8f70935bc4'},
        'root_config': {'path': 'out/nuwa-ufs-apfs-root-integration-20261114/run-r4/root-config.json', 'sha256': 'ec3a2705e70342dccdbfd3cb4bef7eceab606d611370562ca0a574620a193556'},
    },
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r12_frozen[_key] = _r12_dir + _name
PROFILES['ufs-apfs-root-20261115-r12'] = {
    'candidate': _r12_dir + 'vendor_boot.img',
    'candidate_sha256': 'c7bbbb74dd20e50ce469805eea7e1a37e4069c2b884a5459436fe583603c1e15',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('Boot command success is not a screen claim. Expect the boot progress page with the r12 '
                    'title ([nuwa-r12]) in scale 3 (three times r11 glyph size, 80 columns, text rows along the '
                    'panel height). Row 3 is the new pid 1 row: "PID1 st=<1..5>(<name>) comm=<comm> init=<0|1> '
                    'nprocs=<n> | SYSOS st=<0..5> err=<errno> dev=/dev/disk?s? rauth=<0|1>". st=5(ZMB) means launchd '
                    'is a zombie (exited, not reaped); st=3(SLP) means it is sleeping in the kernel; SYSOS st=5 and '
                    'err=0 means the cryptex was mounted and the env handed to exec. Rows 4..: stage bar and the six '
                    'stage rows, then the seven console lines with a continuation row each. The page keeps every '
                    'row r11 had (TCR/last-IRQ moved to rows 33/34). No automatic retry; manually return to the '
                    'bootloader and restore separately with authorization.'),
    'frozen': _r12_frozen,
}
# The current root profile is r12; r11 stays above for comparison.
ROOT_PROFILE = 'ufs-apfs-root-20261115-r12'

# --- r12 bisect candidates (2026-11-16) --------------------------------------
# r12 on device showed only the three entry bands and no page: the kernel stopped
# before the video console bound, so the page was never painted and (r7/r8/r9 had the
# observe patches, r10+) the ROOT_* rows are not expected.  Host analysis ruled out the
# panic-screen/entry-vector layout (identical to r11, 1-byte margin) and the component's
# static constructor (plain OSMetaClass ctor, valid donor superclass).  These two
# candidates split what is left:
#   r12b = r11 kernel objects + only the r12 renderer  -> is the renderer the cause?
#   r12a = r12 kernel minus the VirtioMmioBlock component (minimal IOKit shim)
#                                                      -> is the component/systemos half?
R12A_PROFILE = 'ufs-apfs-root-20261116-r12a'
R12B_PROFILE = 'ufs-apfs-root-20261116-r12b'
_r12a_dir = 'out/nuwa-ufs-apfs-root-chmh-20261116-r12a/'
_r12a_frozen = dict(_r12_frozen)
_r12a_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12a',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12a boot-progress-scale=3',
    'kernel_bytes': 55615488, 'kernel_sha256': '9f48a1ae0efd620e053c27fdc3c86198a1a4bac2b14bf135d5c8185236b327be',
    'kernel_path': 'out/nuwa-r12bisect-20261116/r12a/kernel.macho',
    'fat_sha256': 'd91f4c432696374bea015b5f711c4198a1aead87dd3936e4fc80a9f41e2f5190',
    'adt_bytes': 13548, 'adt_sha256': '8ecaa070f8c8b2e5950c5f812bef4f5cf5d0db6b914a6a975cdcf7ae5b423595',
    'derived_sha256': 'e2735658056e36b9ccad7e2ba9680025e2447707d8accd3148cff87f6bd921b4',
    'report_sha256': '1b78afbcacf1071eea6588a2dfb2ff796727d87640333d313d2a60022ba1d237',
    'audit_sha256': 'ff72b65e86dc3795af4dc8bf66b9a1034985bf9f6e3822ce44158948d9bd7cef',
    'layout_sha256': 'e7f37d322e49e010eb26a9daa010d698eaee6ddc41743105aa51da28629d53d5',
    'provenance_sha256': '59539c9032bd65c7973c9518f00dfe11beaac9c78fe3bb6ca49fc3766eacfa9b',
    'config_bytes': 562, 'config_sha256': '76dcd0fc8171c39d00ccd9cab2a8cd3a94a4b88f6db46a2ce8d953e397a47ddb',
    'source': 'scripts/build-ufs-apfs-root-chmh-r12a.py',
    'source_sha256': 'f4475d4c8d3124e651e45129be44c8b388b1f5c4b4efe247162800a3a94308a8',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '0da3a02a96da2515ac832c22e0cf9947ba254228177ba5fecb0a9d2e29b2c2754b2ff2e0d72c8b614250161f090c211c',
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r12a_frozen[_key] = _r12a_dir + _name
PROFILES[R12A_PROFILE] = {
    'candidate': _r12a_dir + 'vendor_boot.img',
    'candidate_sha256': '7e152d9cb9e74cd6c4c77715e788eed1c94686bbcf6c37d0e16945430e62a57c',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r12a: the r12 kernel without the VirtioMmioBlock component (minimal IOKit shim for '
                    'native_verified_block_*, native_virtio_* back in the stubs).  If the page appears, the '
                    'component was the early-boot culprit; if it again shows only the three entry bands, the '
                    'SystemOS patch/vm_unix/args half is implicated and r12b decides the renderer.'),
    'frozen': _r12a_frozen,
}
_r12b_dir = 'out/nuwa-ufs-apfs-root-chmh-20261116-r12b/'
_r12b_frozen = dict(_r12_frozen)
_r12b_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12b',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12b boot-progress-scale=3',
    'kernel_bytes': 55595008, 'kernel_sha256': 'bd3c1130b016df1c596c579053c5749bb0a9ecfb94e25a99861c881414b53419',
    'kernel_path': 'out/nuwa-r12bisect-20261116/r12b/kernel.macho',
    'fat_sha256': '46e4824e39aba4ad5807a73a7e2029c1b34bcdd5c78fd73b5e735cb0474bdf8c',
    'adt_bytes': 13548, 'adt_sha256': '3590394f92e9041be2a146299b02b518f456570c0b4ffb5b0798a81bc9f0a770',
    'derived_sha256': 'e781ca36a05631d47912e753ffdf4792d78d8d87f9defab404facd2681115c92',
    'report_sha256': '8830ea041c1677ccbd1fb0d194cc86ecf4ef904a4ec22e27297d277f78bd2952',
    'audit_sha256': '377e4f2d959c19cd083170a32e8052e9eeb7487b4101c17cde45bab41ae5c527',
    'layout_sha256': '732a1ccdcd9ea27c927b938311ca873217b52b1be7ec8b237662125919197b13',
    'provenance_sha256': 'e1ace951d70976f4a567794010f89d8887199b357c067aa88192b311b0e2f0e9',
    'config_bytes': 562, 'config_sha256': 'd217342e4a403f1b93c2c21323b752b61b33121d8ea020ad2da6892ba01419f9',
    'source': 'scripts/build-ufs-apfs-root-chmh-r12b.py',
    'source_sha256': 'e1b8e2c8579e3fd2908270fbaf8a7caf8a3be6ae529dfe2dbe6640c06c82baba',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '3822607dcf8961436dfe79852e01a36772317cd8f3554c2e19a3da05be59e35b18ae2a382f50a934713250642b79825f',
})
for _key, _name in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                    ('derived', 'record.json'), ('report', 'outer-record.json'), ('audit', 'audit.json'),
                    ('layout', 'layout.json'), ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r12b_frozen[_key] = _r12b_dir + _name
PROFILES[R12B_PROFILE] = {
    'candidate': _r12b_dir + 'vendor_boot.img',
    'candidate_sha256': '9a21106d8ced9ec182fb298ec1b89a5b6a5c3495766a7a16a6b5e67b5d30354e',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r12b: r11 kernel objects byte for byte plus only the r12 boot progress renderer '
                    '(scale 3, row layout, constant pid1 row).  Narrowest possible delta from r11: if the page '
                    'appears here, the renderer is fine and r12a decides the remaining half; if the three entry '
                    'bands are all that appears again, the r12 renderer is the regression.'),
    'frozen': _r12b_frozen,
}


# --- renderer-internal bisect (2026-11-16) -----------------------------------
# The r12b device run (r11 kernel objects + r12 renderer) still showed only the three
# entry bands, so the renderer itself is implicated.  These three candidates keep r11's
# kernel objects byte for byte (same filelist) and only swap libBootProgress.a:
#   r12fix = r12 renderer + `if (!display.bound) { line(row,text,color); return; }` at the
#            top of line_or_wrap: the only new pre-bind read of width/scale disappears and
#            the pre-bind path is r11's again (scale 3, pid1 row, wrap and all shortened
#            texts stay for the bound path).
#   r12b1  = r11 renderer + ONLY the scale block (default 3, boot-progress-scale 1..3,
#            width clamp); no pid1 row, no wrap helper, original rows and texts.
#   r12b2  = r12 renderer with display.scale forced to 1 (pid1 row + wrap helper kept,
#            which at 119 columns never wraps).
R12FIX_PROFILE = 'ufs-apfs-root-20261116-r12fix'
R12B1_PROFILE = 'ufs-apfs-root-20261116-r12b1'
R12B2_PROFILE = 'ufs-apfs-root-20261116-r12b2'
_BISECT = {
    R12FIX_PROFILE: {
        'dir': 'out/nuwa-ufs-apfs-root-chmh-20261116-r12fix/',
        'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12fix',
        'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12fix boot-progress-scale=3',
        'kernel_bytes': 55595008, 'kernel_sha256': 'c741464befbb57027636b2730b678f82bf224a98f13b802e4c07fcb452c1ae2c',
        'kernel_path': 'out/nuwa-r12bisect-20261116/r12fix/kernel.macho',
        'fat_sha256': '56f107c5de4903b212ec80c10c10662fd20afb4ca398c5131897e312a51f93a3',
        'adt_sha256': '2e7538a8a3414a8329d6315d9d68a749106117b9fce5af7f3e5bd859ec97c87d',
        'derived_sha256': '8dd3422d7fbaf027d286f928db800133dba1b0d6a85a2612b36ad9b1bf7f69e1',
        'report_sha256': 'd698119e9b8dd80c5392fdb3043a0c89afb789c975470e212baad9cf23362418',
        'audit_sha256': 'ed1d425ecae1c668d28bb6f89f112139312f02e6bda31a5d02aaf2eb3ef5fea9',
        'layout_sha256': '732a1ccdcd9ea27c927b938311ca873217b52b1be7ec8b237662125919197b13',
        'provenance_sha256': 'b940686c60d73f0cd420224e48bfa5623863b706c627e900a64db41679384bb2',
        'config_bytes': 564, 'config_sha256': '2dd296a13e3136c134d6f6953491aec25626cf75632832853cd4b4ca73d8ef86',
        'source': 'scripts/build-ufs-apfs-root-chmh-r12fix.py',
        'source_sha256': 'c944264bd357a3bc482bb3ef8470c49f63f323ccb32bf3f890053232fd98edf8',
        'chmh_hex': '6da621e077e04e076a33628adc3196064b48e758e64cd52c2db123e5a3f0a49e236f88f408ba29e7884458541b6c640f',
        'candidate_sha256': '794288689a1a4461bd46cf98caf7a0ca8cfd23f18b4decacbebca52d0a77c9a8',
    },
    R12B1_PROFILE: {
        'dir': 'out/nuwa-ufs-apfs-root-chmh-20261116-r12b1/',
        'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12b1',
        'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12b1 boot-progress-scale=3',
        'kernel_bytes': 55595008, 'kernel_sha256': '0bc665cebfe56d43f1dfb540dfc94724aa5ef2efd04cf77cc0a41d23811f79c5',
        'kernel_path': 'out/nuwa-r12bisect-20261116/r12b1/kernel.macho',
        'fat_sha256': 'e037b1f7302a41ad4dea59670fbc913e27f528c938bb10e78f8b9822d8b6523b',
        'adt_sha256': 'b4a3a3fd70ab21fc50532f5ca8f4990981e48e8e9dfc2cabaaeb4cb297bb513f',
        'derived_sha256': '4d4f5a3ef3dd756c1b1174dea226357c222dcb852087679f1b8b664344d321b0',
        'report_sha256': '243e7c650c72fbc853a15c6416395a434b1071e6fe564e13824ec0f3db4447a7',
        'audit_sha256': '258197dbf5be145aa12d59dd2661f6a7b5e7707b7f9cfc308d3d3130f53ba08e',
        'layout_sha256': '732a1ccdcd9ea27c927b938311ca873217b52b1be7ec8b237662125919197b13',
        'provenance_sha256': '8ea9db4761d07d3fd913fbafb5b28c7c1fa4512771c31c4e846dda62951760ad',
        'config_bytes': 563, 'config_sha256': '1449d735968a1d41cd530402e9d82472d3810141475b6d9760f20e41eb278764',
        'source': 'scripts/build-ufs-apfs-root-chmh-r12b1.py',
        'source_sha256': '8e1c2bccc33ce57a8aba86f77432c07bf7ce63fb44646249f7b810ed9a1519a8',
        'chmh_hex': 'd5f71079e85ae8572b3ee78dc0889c2bc847f6a986a297f15ba69f30a0eefc09c1ee2e20cdc49c1e8e1b9e46075f568a',
        'candidate_sha256': 'bfc8e287ed7273560f5ac8aab0fa041735fd65e79028a67d8dab02c1abc445bf',
    },
    R12B2_PROFILE: {
        'dir': 'out/nuwa-ufs-apfs-root-chmh-20261116-r12b2/',
        'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12b2',
        'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12b2',
        'kernel_bytes': 55595008, 'kernel_sha256': '92582f69c13002c9e7f58ea4a74cf5d5dbf7cc9b403ad705e0c20717134779f5',
        'kernel_path': 'out/nuwa-r12bisect-20261116/r12b2/kernel.macho',
        'fat_sha256': '7c4793985ce6cd351dc477750b7ad50fd09413c0a14df5c6d72f692e79d6da7c',
        'adt_sha256': '3da90f04feb75fe87bc2d293aed05c84146390930e7ad5222b1202b7bfb4395e',
        'derived_sha256': '2e5bec9ebd403bc4b4073625785d07eae1bc70eb24d0d32a910def286a35cd25',
        'report_sha256': 'e74a3a24906b251768b03f49debeaead7b53421e98810dd554f110324bf4ea60',
        'audit_sha256': '71ce38ac83b98486f8300f773c08bd08ca8141fb8d3c37b69154cd781ac52499',
        'layout_sha256': '732a1ccdcd9ea27c927b938311ca873217b52b1be7ec8b237662125919197b13',
        'provenance_sha256': 'c24b5b5197eda728b0442904752afb9cf8a087f197074e5f3677418b80b70e16',
        'config_bytes': 541, 'config_sha256': 'fe952e98b55fc2fd8df1082c9b1a68a1777891112f74e39b2f3db58c7e1c9e1b',
        'source': 'scripts/build-ufs-apfs-root-chmh-r12b2.py',
        'source_sha256': 'd2448636dfacda34b3a6495ef94462e9da3d68394aadb2e487fe97020e6d5da3',
        'chmh_hex': '5f47af1e4bdfeeb38b86a972fe9f4a0de7ff058e7c1175bc21085d732b8c8c2ca4d7cb97fb073b88bc7dd77c5dad28f8',
        'candidate_sha256': '474a8bde9f61b089c3fe832fbf82ba47ce74fe6413a3fc2dd2f55ee0dc355d7f',
    },
}
_BISECT_NOTE = {
    R12FIX_PROFILE: ('r12fix: r11 kernel objects + r12 renderer with the !display.bound guard in '
                     'line_or_wrap.  If the page appears, the renderer is usable again (scale 3, pid1 row); '
                     'if only the three bands appear, the fault is not this pre-bind path and r12b1/r12b2 split it.'),
    R12B1_PROFILE: ('r12b1: r11 kernel + r11 renderer with only the scale block.  A page here means the '
                    'font size / column-count change is harmless and the pid1 row or wrap helper is the '
                    'difference; no page means the scale or the boot-progress-scale parse itself.'),
    R12B2_PROFILE: ('r12b2: r11 kernel + r12 renderer with display.scale forced to 1.  A page here means '
                    'the row insertion and wrap helper are harmless at r11 glyph size, so only their '
                    'combination with scale 3 is at fault.'),
}
for _name, _spec in _BISECT.items():
    _frozen = dict(_r12b_frozen)
    _frozen.update({
        'package_profile': _spec['package_profile'], 'args': _spec['args'],
        'kernel_bytes': _spec['kernel_bytes'], 'kernel_sha256': _spec['kernel_sha256'],
        'kernel_path': _spec['kernel_path'], 'fat_sha256': _spec['fat_sha256'],
        'adt_bytes': 13548, 'adt_sha256': _spec['adt_sha256'],
        'derived_sha256': _spec['derived_sha256'], 'report_sha256': _spec['report_sha256'],
        'audit_sha256': _spec['audit_sha256'], 'layout_sha256': _spec['layout_sha256'],
        'provenance_sha256': _spec['provenance_sha256'],
        'config_bytes': _spec['config_bytes'], 'config_sha256': _spec['config_sha256'],
        'source': _spec['source'], 'source_sha256': _spec['source_sha256'],
        'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
        'chmh_hex': _spec['chmh_hex'],
    })
    for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                            ('derived', 'record.json'), ('report', 'outer-record.json'),
                            ('audit', 'audit.json'), ('layout', 'layout.json'),
                            ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
        _frozen[_key] = _spec['dir'] + _filename
    PROFILES[_name] = {
        'candidate': _spec['dir'] + 'vendor_boot.img',
        'candidate_sha256': _spec['candidate_sha256'],
        'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
        'observation': _BISECT_NOTE[_name],
        'frozen': _frozen,
    }


# --- r13: the Data volume on the ram disk, mounted at /private/var --------------
# Base: r12fix (r11 kernel objects + the guarded r12 boot progress renderer).  r13 adds
#  * bsd/kern/kern_exec.c: one extern and one call of nuwa_data_mount_prepare() after
#    mach_vm_allocate_kernel, before the first exec (opt-in -DXNU_NUWA_DATA_MOUNT=1);
#  * package/nuwa-data/nuwa_data_mount.c: the mount itself, the boot_progress_ext[0..1]
#    diagnostics, and the one-shot NativeRamBlock initializer call;
#  * drivers/RamBlock/NativeRamBlock.cpp compiled in, late-transformed (its static
#    constructor is externalized and __mod_init_func emptied) and force-loaded;
#  * iokit personas: the NativeRamBlock IOResources/IOBSD match and the
#    nuwa_ram_block_init() call after nuwa_ufs_handoff_init();
#  * payload: a 16-byte /chosen/memory-map/PackedRAMDisk entry in the derived ADT, the
#    `initrd` line in unixnu.toml, and Payloads/scratch-data.img (the DBRDISK1 seed,
#    352384 B) as a fourth FAT member; the seed is NOT part of the CHMH material;
#  * args: sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024 (kernel and
#    args both move, so this is a new CHMH, not a reuse of r12fix's).
# The seed content, its APFS volume UUID and the window arithmetic are host-checked; the
# kernel, package and the CHMH rebinding are host self-checked; nothing has run on a
# device, so whether Apple's APFS accepts this seed and whether the persona/init timing
# publishes the volume are assumptions, not results.
R13_PROFILE = 'ufs-apfs-root-20261116-r13'
_r13_dir = 'out/nuwa-ufs-apfs-root-chmh-20261116-r13/'
_r13_frozen = dict(_r12b_frozen)
_r13_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r13',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r13 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55660544, 'kernel_sha256': '781cf08c32e8da80524f5f8d69d3c64478e9e10188945233d4a23d3b4601b93a',
    'kernel_path': 'out/nuwa-data-mount-20261116-r13/kernel.macho',
    'fat_sha256': '7415ecee4e9a2e8464f83175c2231fb897f448d2d632752249afd520637c7821',
    'adt_bytes': 13600, 'adt_sha256': '099154468d3b7dc83bf479caed9baa504fb50f7836641becc959b7f853c22efb',
    'derived_sha256': 'a1ca03562e89f69a60943c9a9e0e7ff78b916db4a0f1edca7449068ae672efc9',
    'report_sha256': '945a560352eb342d2ef7d7106166bae1dec0816933ebf49948d06230250f95e5',
    'audit_sha256': '1409d9a2e09bf9339c10c878fdd4a634574aa26874d8430f6fcbc8fb4a52621a',
    'layout_sha256': '195e911940c77b00b8544bc83a125e82df38d57e2fe3c1a2f1db44f43a734f21',
    'provenance_sha256': 'c42c985b00a42479b0b14cb7c59cd1615b9d6ad653f4b4de198145315205f43b',
    'config_bytes': 661, 'config_sha256': '8c2abd4bc792d032f53e25159e018cc1bf1243c0bb25de2eb4b63ae4a9f46578',
    'source': 'scripts/build-ufs-apfs-root-chmh-r13.py',
    'source_sha256': '75b162f6c11e64462646be403a8ea795de26f1b11c457d25a41669f5c821172c',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '550be24d584286a93d3b30b54f83f685a4d037c316dba8c024ad4b7c2b0dced8b179527a70d9a03d34439337b4094d3e',
    'seed_sha256': 'a3363fd186aa557777b3b3815bf4975b5e3a9a284bf17a44c08158b4348bd5f2',
    'data_volume_uuid': 'C7DE20F1-3A70-482B-B14F-801EE1513E3D',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r13_frozen[_key] = _r13_dir + _filename
PROFILES[R13_PROFILE] = {
    'candidate': _r13_dir + 'vendor_boot.img',
    'candidate_sha256': '61929ec28c31ecde4b63e467f31a8f855122ba986a6238d933db9ea0bcf6d8e2',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r13: the Data volume on the ram disk (DBRDISK1 seed from the payload FAT, DBRDISK1 '
                    'delivered as PackedRAMDisk) mounted at /private/var before the first exec. The boot '
                    'command succeeding is not a mount claim. Read the right-hand extension rows (drawn to the '
                    'right of the page text, rows 13-20): slot 0 "DATA mnt st=<0..4> err=<errno> ro=<0|1> '
                    'dev=<dev_t>" and slot 1 "DATA seed ok=<0|1> id=<first 4 digest bytes> blk=<seed KiB/4>". '
                    'The two BootProgress DATA rows from NativeRamBlock (slots 2-3, "DATA st= hdr= gpt= lba=" '
                    'and "pres= ld= wr= sy= er=") appear only in r13 because the driver that defines their '
                    'counters is now linked: if neither pair is on screen, look at the link/persona (the '
                    'driver never started), not the seed. st=1 err=2 = the volume UUID was never published; '
                    'st=3 err=22 = the volume was published but mount() was refused; st=3 err=0 ro=0 = the '
                    'mount worked. The first boot writes the overlay header at LBA 59491258 (inside the '
                    '1024 MiB tail reserve, below the 32 MiB log region); sheng-data-reset=1 discards it '
                    'again. No automatic retry; manually return to the bootloader and restore separately '
                    'with authorization.'),
    'frozen': _r13_frozen,
}

# --- r12afix: r12fix renderer + the r12a SystemOS mount, no component ---------
# The r12fix device run showed a working diagnostic page but a single process and no
# mount/apfs/dyld output: the page proves the renderer, not the SystemOS path, because
# r12fix deliberately carried no SystemOS code (its pid1 row was the r12b control
# placeholder).  r12afix keeps r12fix's renderer and every r12fix kernel object except
# the two the mount changes: kern_exec.c (the r12 SystemOS mount + envp build) and
# vm_unix.c (the cache-location exception), adds nuwa_systemos.c and the r12a IOKit
# shim for native_verified_block_*, and drops -DNUWA_PID1_STUB so boot_process_capture()
# calls the real nuwa_pid1_sample.  No VirtioMmioBlock, no new __mod_init_func entry.
R12AFIX_PROFILE = 'ufs-apfs-root-20261116-r12afix'
_r12afix_dir = 'out/nuwa-ufs-apfs-root-chmh-20261116-r12afix/'
_r12afix_frozen = dict(_r12b_frozen)
_r12afix_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r12afix',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r12afix boot-progress-scale=3',
    'kernel_bytes': 55615488, 'kernel_sha256': 'fb05dd1884678ff100230f9091e01153f171cd841691ac4928412b43dc844125',
    'kernel_path': 'out/nuwa-r12afix-20261116-r1/kernel.macho',
    'fat_sha256': '2459f957348de82b4ac09135d8993bc784846096960d7ea22881c982dadcb696',
    'adt_bytes': 13548, 'adt_sha256': '7264b0e0ea736b34a6ff40550d3882febe91b1053137b66d00549e666c2d783c',
    'derived_sha256': '54221d3f1f35382b5061238975e9979a031dad4dee1c417221ed87c244744462',
    'report_sha256': '33aed4906423b74dbf80b1df578bb788e5c87fb30ba337497cf891c7ee0c9e84',
    'audit_sha256': '5bc9d278159341ca576f44d12ead72e361cdf00da5b0a9f401b76122476b7b40',
    'layout_sha256': 'e7f37d322e49e010eb26a9daa010d698eaee6ddc41743105aa51da28629d53d5',
    'provenance_sha256': '8189077befa76eb3f616b5fa8d4bb263ff5ffe115ebd0c443d94edfbf1100886',
    'config_bytes': 565, 'config_sha256': 'f33030393a19f5ccfdffd3eba2cc10a6f7e24ce07907dd0b25fc71ad3690369b',
    'source': 'scripts/build-ufs-apfs-root-chmh-r12afix.py',
    'source_sha256': 'ddfacfe7e4ec1381acfd92230144542cd04dae0081320e2d13e6a67b1e9cf71b',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '1846496e748065787218eacb44fee3e7bed7613ce847c84ca84bad0ad8c90b569392dbd8a6f70ae35c229318f6219edf',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r12afix_frozen[_key] = _r12afix_dir + _filename
PROFILES[R12AFIX_PROFILE] = {
    'candidate': _r12afix_dir + 'vendor_boot.img',
    'candidate_sha256': 'edaa7393817d09d7a36bac48e459cef7700b42a819b412ccb9a32b9ae9a0e376',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r12afix: the r12fix page plus the SystemOS mount. Boot command success is not a '
                    'mount claim. Row 3 is now the real sample: "PID1 st=<n>(<IDL|RUN|SLP|STP|ZMB>) '
                    'comm=<name> init=<0|1> nprocs=<n> | SYSOS st=<0..5> err=<errno> dev=<path|-> '
                    'rauth=<0|1>". SYSOS st=0/1 = nuwa_systemos_prepare never finished (root device '
                    'lookup); st=2 with err=2 = the SystemOS cryptex UUID was not published by the UFS '
                    'driver (lookup, not mount: see nuwa_systemos_device_path); st=3 with err=<n> = mount() '
                    'was refused (2 ENOENT device path, 22 EINVAL the APFS volume is not accepted as a '
                    'system volume, 30 EROFS read-only mount refused); st=3 err=0 then st=4 = the volume '
                    'mounted and verified (dev=/dev/disk?s? is the cryptex window) and st=5 means the '
                    'DYLD_SHARED_CACHE_DIR vector was handed to exec. rauth=1 is the recorded root '
                    'authorization result (native_verified_block_root_authorized; it does not gate). '
                    'nprocs>1 is the first sign that launchd got further than r12fix; nprocs=1 with '
                    'SYSOS st=5 means the mount and the environment were fine and the blocker is after '
                    'dyld. No automatic retry; manually return to the bootloader and restore '
                    'separately with authorization.'),
    'frozen': _r12afix_frozen,
}

# --- r14: r12afix's SystemOS mount + r13's Data mount in one image -----------
# The two parents each mount one volume and each carried its own kernel: r12afix mounts
# the SystemOS cryptex on /private/preboot and builds the initproc envp, r13 mounts the
# ram-disk Data volume on /private/var.  Their patches insert at the same two anchors in
# kern_exec.c, so r14 applies the r12 patch and then patches/xnu/8796-nuwa-r14-data-mount.patch
# (the r13 hunk rebased onto the patched text): SystemOS mount -> Data mount -> exec.
# The seed is the macOS-built copy (1,609,888 B encoded, identity 689fd890..., APFS volume
# UUID B0E0F71F-...), which differs from r13's Linux seed in bytes, identity and UUID, so
# the kernel, args, CHMH, ADT, FAT and outer hashes all move again.  The seed is not part
# of the CHMH material.
R14_PROFILE = 'ufs-apfs-root-20261116-r14'
_r14_dir = 'out/nuwa-ufs-apfs-root-chmh-20261116-r14/'
_r14_frozen = dict(_r13_frozen)
_r14_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261116-r14',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r14 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': 'bd40fa3cdde9f32470bb802f91fe279cd1698fc76f2f7bc517798fcf4533f238',
    'kernel_path': 'out/nuwa-r14-kernel-20261117/kernel.macho',
    'fat_sha256': '77b7ea6d4a96705dc5e3408255561c70561874b8584fd6a97ec408ff82f25e07',
    'adt_bytes': 13600, 'adt_sha256': 'a30e485a1425ea0860c5fc4bb3b1cafe506710ded75e81c30fa3020bf0a91acb',
    'derived_sha256': '1b07877ca187ca543b05571a8f2483afa4473e20bbc5459fac1851b529400c80',
    'report_sha256': '3160cbfb42b6d574a9b2eed206ef0a8a40ace8486ec3eeca8538240cc2d47806',
    'audit_sha256': 'acf782f5fcb1f4a5e0966f41295213773cd81061418d8b95d0fee4381c80aef9',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'e6c8f8813deefb2fb1da51526acd5bfa710d8eff5a7845cdb31b0658ed9839ce',
    'config_bytes': 661, 'config_sha256': '3a2e828587f0c6725ece9a20095a25326aa869b8e40be052cdc1586104ffb3c0',
    'source': 'scripts/build-ufs-apfs-root-chmh-r14.py',
    'source_sha256': 'a95d906159e0d8f1f9fa2ff3846890c6cd6ef63ae269129a12083af4c32a10cd',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '0c76b070b8aa06a3f5b2a5b60c6e158381c6f29724638206f9ea362936865979276ee177c4f362643d3dea4a4b91f763',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r14_frozen[_key] = _r14_dir + _filename
PROFILES[R14_PROFILE] = {
    'candidate': _r14_dir + 'vendor_boot.img',
    'candidate_sha256': 'ea8ce443ac18cdc125362abc9f2d080da1781a47ae046db6de9319d3c15e9de6',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r14: one image, two mounts. The boot command succeeding is not a mount claim; read the '
                    'page. Row 3 (the pid1 sample) now reports both the process probe and SystemOS: "PID1 '
                    'st=<n>(<IDL|RUN|SLP|STP|ZMB>) comm=<name> init=<0|1> nprocs=<n> | SYSOS st=<0..5> '
                    'err=<errno> dev=<path|-> rauth=<0|1>". The right-hand extension rows carry the Data '
                    'side: slot 0 "DATA mnt st=<0..4> err=<errno> ro=<0|1> dev=<dev_t>", slot 1 "DATA seed '
                    'ok=<0|1> id=<first 4 digest bytes> blk=<seed KiB/4>", and slots 2-3 the NativeRamBlock '
                    'store counters "DATA st= hdr= gpt= lba=" / "pres= ld= wr= sy= er=". Expected order on a '
                    'good boot: SYSOS st=5 err=0 (cryptex mounted read-only, envp built) and DATA mnt st=4 '
                    'err=0 ro=0 (the ram-disk Data volume mounted on /private/var); DATA mnt st=1 err=2 means '
                    'the ram-disk volume UUID was never published (persona/init, not the seed), st=2 err=<n> '
                    'means mount() refused the seed (22 EINVAL = Apple APFS did not accept it), st=3 with '
                    'err=0 and ro=1 is the diagnostic read-only mount. SYSOS st=2 err=2 means the SystemOS '
                    'cryptex UUID was not published; st=3 err=<n> is a refused system mount. If either pair '
                    'is absent, the missing one never ran: check the link/persona before the seed. nprocs>1 '
                    'is the first sign that launchd moved past exec. No automatic retry; manually return to '
                    'the bootloader and restore separately with authorization.'),
    'frozen': _r14_frozen,
}

# --- r16: r14's two mounts + the dyld/AMFI observation kernel ------------------
# Same single stable kernel as r14 (kern_exec.c with the SystemOS hunk then the Data
# hunk) plus two observation-only insertions: vm_unix.c formats one DYLD row per
# shared_region_map_np request (path/mnt/root/err/byp/mac/flg) and its MAC check prints
# one console line when it rejects; kern_exec.c sets dyld_flags |= 8 and publishes it
# with commpage_update_dyld_flags before the first exec.  The renderer adds three page
# rows (32 DYLD, 39 Data mount, 44 Data counters) because the right-hand extension
# slots are not drawn at boot-progress-scale=3.  Seed, ADT PackedRAMDisk, mounts,
# CHMH and outer hashes are re-derived; the seed is not part of the CHMH material.
R16_PROFILE = 'ufs-apfs-root-20261117-r16'
_r16_dir = 'out/nuwa-ufs-apfs-root-chmh-20261117-r16/'
_r16_frozen = dict(_r14_frozen)
_r16_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261117-r16',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r16 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': '078455211767759261106cada09046ff2238a70f70aee6f8e15f614af5a263c0',
    'kernel_path': 'out/nuwa-r16-20261117/kernel.macho',
    'fat_sha256': 'b0ca0d00df8f3cbfe4325c59260369c8bd164f213f4ff63cde964bef0553ae3f',
    'adt_bytes': 13600, 'adt_sha256': '2347e655be87f44f84a7a09d055c303c8b93a4f66ec6dc6ed666eb028114290a',
    'derived_sha256': '9c00c9eeddbafa2ca1c6afac884f75b7849318a0157cee6592667baa2b40ef12',
    'report_sha256': 'aec474e52c9f0b253cf99b10e76724d5bb8bc08e187204c035a36a5be13a55d3',
    'audit_sha256': '771a69f75cbd58e5ba60e7e705173983ebebdc336ec0d73d9601ec784306fb90',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '4923551c735652c14e797a8511ae60143d42abd050cab5253bd6c5f54929353a',
    'config_bytes': 661, 'config_sha256': 'd4a12747dbf6e7f16601948e765b13397a3fc7578d2c5cde6e1e6364523fa896',
    'source': 'scripts/build-ufs-apfs-root-chmh-r16.py',
    'source_sha256': '3b8f3c1d7cfcf0da3c45c095e5a3515b74a5e4887c609a35733a7fc8b62619e8',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': 'fc1d3933cb39256c025f5e1e420e5e44a3a352cec9c2a0dbcee6e517a50056e1fe1b519bda87ebef19b31b8b277e827e',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r16_frozen[_key] = _r16_dir + _filename
PROFILES[R16_PROFILE] = {
    'candidate': _r16_dir + 'vendor_boot.img',
    'candidate_sha256': '9a434132341f42c812c515a6b0e0ea7d8a249c89ab252ea44e17eac74215ac9f',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r16: two mounts plus the dyld probe. A successful boot command is not a mount or dyld '
                    'claim; read the page. Row 3 (two rows on this page) is the pid1 sample: "PID1 st=<n> '
                    '(<IDL|RUN|SLP|STP|ZMB>) comm=<name> init=<0|1> nprocs=<n> | SYSOS st=<0..5> err=<errno> '
                    'dev=<path|-> rauth=<0|1>". Row 32 is the new DYLD line, written on the first '
                    'shared_region_map_np request: "DYLD path=<cache vnode name> mnt=0x<dev of its mount> '
                    'root=0x<dev of the process root> err=<setup return> byp=<cache-location acceptances in '
                    'this call> mac=<last mac_file_check_mmap return> flg=<dyld_flags>". A successful mapping '
                    'reads err=0, byp=1, mac=0, flg=8; "DYLD (no shared_region_map_np yet)" means dyld never '
                    'asked, and err=<nonzero> names the refusal (1 EPERM = root/cache-location, 22 EINVAL = '
                    'bad file/geometry). Row 39 is the Data mount ("DATA mnt st= err= ro= dev= seed="), row 44 '
                    'the NativeRamBlock store counters ("DATA hdr= gpt= lba= | pres= ld= wr= sy= er="). Good '
                    'boot: SYSOS st=5 err=0, DYLD err=0, DATA mnt st=4 err=0 ro=0. A nonzero mac also prints '
                    '"nuwa: cache mmap MAC returned <n>" in the console block (rows 17-30). No automatic '
                    'retry; manually return to the bootloader and restore separately with authorization.'),
    'frozen': _r16_frozen,
}

# --- r17: r16 + SystemOS on the fixed dyld path (memory-backed preboot) ---------
# The r16 device run showed the r12/r16 shape does not reach dyld: the cryptex was mounted
# on /private/preboot, so the root's /System/Cryptexes/OS symlink (-> ../../private/preboot
# /Cryptexes/OS) dangled and dyld fell back to /usr/lib/libSystem.B.dylib.  r17 mounts a
# memory-backed devfs on /private/preboot, creates Cryptexes in it and mounts the cryptex at
# /private/preboot/Cryptexes/OS, with r16's mount as the recorded fallback (xnu-8796 has no
# tmpfs).  The same run also showed the page's diagnostics were unusable when a producer had
# not run: rows 3/4 stayed "not sampled", the DATA counter row was skipped, and the Data
# block read st=0 err=-1 while exec had happened.  r17 draws all four blocks unconditionally
# and gives the SystemOS record its own formatter.
R17_PROFILE = 'ufs-apfs-root-20261117-r17'
_r17_dir = 'out/nuwa-ufs-apfs-root-chmh-20261117-r17/'
_r17_frozen = dict(_r14_frozen)
_r17_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261117-r17',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r17 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': '5632a383ecc2aa3330b543468544b445c46dc1258b391738cde1f6b916b84c1f',
    'kernel_path': 'out/nuwa-r17-20261117/kernel.macho',
    'fat_sha256': 'db11c94a11932fb819e702478831601b6d001844045d9628358ec16dbefe10a9',
    'adt_bytes': 13600, 'adt_sha256': '526494d9c6f09688b0b411baf6bc87752a4a8a7f240ba10cfb1a2934e835ff64',
    'derived_sha256': '8a16c6529157eb1626028f013312e5f4c0ea02e8beb6366a14a6d24897a95fed',
    'report_sha256': '3a09f9104ce29b9ff9e224074e383d9dbf4e89ad3a4b8fd7ff0f8e7ceaf08ee3',
    'audit_sha256': '678fbe47ec4bd2a52b11479ad2a1823774c3fc60553f27e262ad8175cc7d181e',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '18e1186b9f4e5e5638a85cdbeeffdf3f7cec0a1f0068beb2c991ffc1d14613f1',
    'config_bytes': 661, 'config_sha256': 'a69640003c3b5fd2ac1e82811b1db3fcbf77ee0698614b5abf3fe6138ab91eee',
    'source': 'scripts/build-ufs-apfs-root-chmh-r17.py',
    'source_sha256': '391d4b383a203b7693369237141bdfff3edb557969d95177fb7ad817836b0d09',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': 'fb7652bc847028de5653446742161fedb4b88ab0b3865a2207fd1bc440933e53db6b18a721e297a4006430f137bcd735',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r17_frozen[_key] = _r17_dir + _filename
PROFILES[R17_PROFILE] = {
    'candidate': _r17_dir + 'vendor_boot.img',
    'candidate_sha256': '579d19b4714364a842d90f48343d21e23dcfece7f783bd147a5d7206fdd8a12a',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r17: the cryptex on the fixed dyld path. A successful boot command is not a mount or dyld '
                    'claim; read the page. Every block is now painted on every frame, so a frame taken after the '
                    'fact still says how far the boot got. Row 3/4 (one wrapped line): "PID1 st=<n>(<IDL|RUN|SLP|STP'
                    '|ZMB>) comm=<name> init=<0|1> nprocs=<n> | SYSOS st=<0..6> err=<errno> dev=<path|-> rauth=<0|1> '
                    'pb=<0|errno|-1> mk=<0|errno|-1> mos=<0|errno|-1> ap=<0|errno> mnt=<path> dst=<path>". st=1 root '
                    'device, 2 volume, 3 preboot scratch filesystem mounted, 4 cryptex mount() called, 5 verified, 6 '
                    'environment written. pb=0 means the memory filesystem (devfs) is on /private/preboot, pb=<errno> '
                    'means it failed and the r16 mount point /private/preboot was used; mk is '
                    'mkdir(/private/preboot/Cryptexes), mos is mkdir(/private/preboot/Cryptexes/OS) - the mount point '
                    'itself - and either is -1 when never attempted; ap is the cryptex mount() errno. The order is '
                    'devfs mount, mkdir Cryptexes, mkdir Cryptexes/OS, mount (asserted in the build from both the '
                    'source and the object). Good boot: st=6 err=0 pb=0 mk=0 mos=0 ap=0 with '
                    'mnt=/private/preboot/Cryptexes/OS and dst the same string. mk=<errno> with ap=-1 means the '
                    'directory step failed and no mount was attempted; mk=0 mos=<errno> means Cryptexes exists but its '
                    'OS child does not, so again no mount; ap=<errno> with mk=0 mos=0 is a refused mount. If the pid '
                    'sample never ran, the same SYSOS text is drawn from its own formatter (the row then starts with '
                    '"SYSOS", not "PID1"). '
                    'Row 32 is the DYLD row: "DYLD path=<cache vnode> mnt=0x<dev> root=0x<dev> err=<ret> byp=<n> '
                    'mac=<n> flg=<dyld_flags>"; "DYLD none (no shared_region_map_np yet) err=- byp=0 mac=- flg=-" '
                    'means dyld never asked for the cache. Row 39 "DATA mnt st=.. err=.. ro=.. dev=.. seed=.." and '
                    'row 44 "DATA hdr=.. gpt=../.. lba=.. | pres= ld= wr= sy= er= st=.." are drawn even when the Data '
                    'mount never ran (then st=0 err=-1 and the row says "(not run)"), so "exec happened but Data did '
                    'not" is visible instead of a missing row. The SystemOS and Data prepares are independent calls '
                    '(build asserts no compare/branch between them); a failure in one must not skip the other. No '
                    'automatic retry; manually return to the bootloader and restore separately with authorization.'),
    'frozen': _r17_frozen,
}

# --- r17c: r17 + a synchronous repaint after each mount -----------------------
# The r17 device frame read "PID1 absent ... | SYSOS st=0 ... pb=-1" while the initproc
# panic proves an exec happened, and the kernel disassembly shows the two prepare calls are
# unconditional and precede every exec call site.  The frame was simply painted before the
# mounts: the monitor repaints once a second and the dyld failure panics in the same second.
# r17c keeps every mount decision identical and adds boot_progress_sync_draw(), called at
# the end of both prepares, so the frame that survives the panic already carries st/pb/mk/
# mos/ap/mnt/dst and the Data rows.
R17C_PROFILE = 'ufs-apfs-root-20261117-r17c'
_r17c_dir = 'out/nuwa-ufs-apfs-root-chmh-20261117-r17c/'
_r17c_frozen = dict(_r14_frozen)
_r17c_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261117-r17c',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r17c boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': '278cbc705aaadc7ceae1bedd518f6bc024c35da2f971b644a5fe2c56d6c470cd',
    'kernel_path': 'out/nuwa-r17c-20261117/kernel.macho',
    'fat_sha256': '868b6da3b8ca5b7036c13d0041912538f525589c4c27e10d91f3b78e7386720d',
    'adt_bytes': 13600, 'adt_sha256': '9509f00e0f29c901fe71544823464ff03aff2e248aab25b203c44dd376be9bec',
    'derived_sha256': 'eced00b327c01f72d7614c366975e232b1073318cd66861155ebbd7033da1562',
    'report_sha256': '78394c5398610e421b187f03d69ef2863fba028c0db797e610f82e8f424f17dd',
    'audit_sha256': 'db9bca920a43fe6d4cbfcc1e7f0b693e324344ffc4144d24e3de8a13b3bcdbc2',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '5babc1b5f126484402e3351004371a8adde7b0025b2064c61637c4b1295a7684',
    'config_bytes': 662, 'config_sha256': 'f812aa7486d8d04ffe6283ceeb379b5eb908a07b1389ff8cc5c142b640810c41',
    'source': 'scripts/build-ufs-apfs-root-chmh-r17c.py',
    'source_sha256': '1e614742b26a4b9583eb779f5030afddb38ae579d5ade8a675b865ac0031e619',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': 'fbde43988556a12e7f57886fcae156af321a97c20fdab5baa70b0fddbc5fc28ce7746fa54cf345fdc1ebcedf61b921cd',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r17c_frozen[_key] = _r17c_dir + _filename
PROFILES[R17C_PROFILE] = {
    'candidate': _r17c_dir + 'vendor_boot.img',
    'candidate_sha256': 'dfbbc3038c455fa188fae2080ebb2502a18facefc71d178514490a20789ec7a1',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r17c: r17 with the mounts flushed to the panel before the exec. Same rows and fields as r17 '
                    '(row 3/4 "PID1 ... | SYSOS st=<0..6> err= dev= rauth= pb= mk= mos= ap= mnt= dst=", row 32 '
                    'DYLD, row 39 DATA mnt, row 44 DATA counters), but the last frame before an initproc panic now '
                    'shows the post-mount values instead of a pre-mount snapshot: the r17 frame read SYSOS st=0 pb=-1 '
                    'with "PID1 absent ... nprocs=0" although the panic itself proves an exec happened, i.e. the '
                    'prepare calls had run. Read SYSOS in that frame: st=6 err=0 pb=0 mk=0 mos=0 ap=0 with '
                    'mnt=dst=/private/preboot/Cryptexes/OS means the fixed dyld path is mounted; pb/mk/mos/ap carry '
                    'the first failing step otherwise (mk or mos set and ap=-1 means no mount was attempted). Row 39 '
                    '"DATA mnt st=4 err=0 ro=0 ..." and row 44 "DATA hdr=... st=..." now show the Data result in the '
                    'same frame. A row that still reads st=0 with pb=-1 in this build means the flush or the mount '
                    'call itself did not run - the two are now distinguishable. No automatic retry; manually return '
                    'to the bootloader and restore separately with authorization.'),
    'frozen': _r17c_frozen,
}

# --- r18: the SystemOS cryptex union-mounted on "/" (official shape) -----------
# dyld has no preboot-cryptex search path: for a platform binary it ignores
# DYLD_SHARED_CACHE_DIR, libignition is not in this kernel, and the only fixed location left
# is /System/Library/Caches/com.apple.dyld on the root - which only the SystemOS volume has.
# r18 mounts that volume on "/" with MNT_RDONLY|MNT_UNION.  This tree implements union in
# VFS (CONFIG_UNION_MOUNTS: the flag stays on mnt_flag, vfs_syscalls.c:1273-1281; ENOENT in
# a union mount falls through to the covered vnode, vfs_lookup.c:1327-1344) and mounting on
# the root vnode moves rootvnode (checkdirs(), vfs_syscalls.c:2549-2560).  If the mount is
# refused, r17c's devfs + Cryptexes/OS mount runs once as the fallback.  The Data row also
# gains devpath/pub/serr so "volume never published" is separable from "device node missing".
R18_PROFILE = 'ufs-apfs-root-20261117-r18'
_r18_dir = 'out/nuwa-ufs-apfs-root-chmh-20261117-r18/'
_r18_frozen = dict(_r14_frozen)
_r18_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261117-r18',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r18 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': '8d608d5484e4729a0cd897ed37fa8d4d9f181cba8cf84bc3b09db0829a07566b',
    'kernel_path': 'out/nuwa-r18-20261117/kernel.macho',
    'fat_sha256': '4d0c7c3ab7f21e7fe3923925451589510971cc1ee0c2108d13ff4105400c6f9e',
    'adt_bytes': 13600, 'adt_sha256': 'a4b71a446fc9e6941cc341b335a55034fac92e832aac17ca722c9ac3a351f1a5',
    'derived_sha256': 'a085477fffebe0732c4e6785392d81ba5f60e0b40c61fe54cc497ab4903c5cec',
    'report_sha256': '7e94aae4df52f62db759d5587b39d8392e7a7a9ec949790eaa23b2f1c7de207c',
    'audit_sha256': '98dd0c9625271add30cd0251c7662b7b23567803fab2e891d37ccdac475585ec',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'fe2275a21712727faeaf3c07e57e7f1559ec817e7eed1d8daa03df2ce63449fb',
    'config_bytes': 661, 'config_sha256': '3071cb5da927dd69e5583abe79e817b20d6f7db6d33dff95cc23cbacd995f648',
    'source': 'scripts/build-ufs-apfs-root-chmh-r18.py',
    'source_sha256': 'f3b40d3e54f49bbf68d87e6b3664427e07ab14f70321a2ed71c2110da1cccb03',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': 'cb36b64194a274c86f1f9e719ab6733d7bdcff3e690d6f9076b8966691a02b0f6dd786e1c847d6d14233d37deeb5e8f5',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r18_frozen[_key] = _r18_dir + _filename
PROFILES[R18_PROFILE] = {
    'candidate': _r18_dir + 'vendor_boot.img',
    'candidate_sha256': 'a1996558ce34d27e33068012b22d05ddf9f8c56b995a73be49089d8ae1824bdd',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r18: SystemOS union-mounted on "/". Read row 3/4 as "PID1 ... | SYSOS st=<0..6> err=<n> '
                    'dev=<path|-> rauth=<0|1> pb=<0|-1> mk=<0|-1> mos=<0|-1> ap=<0|errno> mnt=<path> dst=<path> '
                    'uni=<0|1> rv=<0|1>". Success of the union shape: st=6 err=0 pb=-1 mk=-1 mos=-1 ap=0 '
                    'mnt=/ dst=/ uni=1 rv=1 (pb/mk/mos stay -1 because the union path needs no preboot filesystem). '
                    'uni=1 rv=1 is what makes /System/Library/Caches/com.apple.dyld resolvable: the mount carries '
                    'MNT_UNION, so lookups that miss in the cryptex fall through to the boot volume, and checkdirs() '
                    'moved rootvnode to the mounted root.  ap=<errno> with mnt=/ means the union mount was refused; '
                    'the boot then falls back once to r17c (mnt=/private/preboot/Cryptexes/OS, pb=0 mk=0 mos=0) and '
                    'the console carries "nuwa: mount(apfs, /, MNT_UNION) refused; r17c fallback".  uni=0 or rv=0 with '
                    'ap=0 means the mount was accepted but is not the union/visible root (verification fails, '
                    'st=4).  Row 39 is the Data triage line: "DATA mnt st= err= ro= dev=<dev_t> seed= devpath=<path|-> '
                    'pub=<0|1> serr=<0|1|-1>"; serr=1 with devpath=- means the RamBlock driver never published the '
                    'seed (volume lookup failed), serr=0 with devpath=/dev/... and err=2 means the lookup worked but '
                    'mount() could not find that device node.  Row 32 stays the DYLD row (err=0 byp=1 mac=0 flg=8 is '
                    'a successful shared-cache mapping).  No automatic retry; manually return to the bootloader and '
                    'restore separately with authorization.'),
    'frozen': _r18_frozen,
}

# --- r19: r18 + the four-path dyld cache probe ---------------------------------
# r18's union on "/" verified (uni=1 rv=1) but launchd still failed with "no dyld cache", so
# r19 asks the mounted namespace itself whether the dyld file is reachable: after the mount
# verifies, four vnode_lookup()s record their errno (SYSOS p1..p4) and the size of
# /System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64 (csz, KiB), plus one console
# line.  The opt-in namei() trace (patches/xnu/8796-nuwa-lookup-trace.patch) stays off in
# this image, so the kernel must not contain "nuwa: lookup <".
R19_PROFILE = 'ufs-apfs-root-20261118-r19'
_r19_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r19/'
_r19_frozen = dict(_r14_frozen)
_r19_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r19',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r19 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': '19bd5d5b4a469024ac32492d6aa81748b0695edc5cdfe34b98c4ea7cede4246c',
    'kernel_path': 'out/nuwa-r19-20261118/kernel.macho',
    'fat_sha256': '968911b3b3b825c0bf61c8029ec037d285e27ba4006674c5401415f73bdfbdea',
    'adt_bytes': 13600, 'adt_sha256': 'cc71588de4c04f560e5a6d389d1238cd265396b0e237a976db7f34edf2f9ccaa',
    'derived_sha256': '37f9884f334cb59bde88170ff27a9697fb24084632b326147a540619f75b8141',
    'report_sha256': '58ad1c2ce248433ec83074de01ce93ae760a6cfb0562963f98728b61d7cf74dc',
    'audit_sha256': 'b763910764dd4cba807f30c18d5aea0b46ed8b776acfd888bb9de248c1985a89',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'f695b78d0cb5b7e2dfe6ba379ece7b8bb7ad8dffde0de83d97908d2489eb87ec',
    'config_bytes': 661, 'config_sha256': 'f3889f3abf3a2202c7341f6dfb1701e71573727d3626bce69ee1e17c38dbb2cb',
    'source': 'scripts/build-ufs-apfs-root-chmh-r19.py',
    'source_sha256': 'fe2ec1af7a4ddf0d4aae7fcdc51e68e15bb14a5fa8caef5be0bdffbb26d5370c',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '5a71dd1555d68b19a3baddebccc3e58cffed9c03b2ca018ded92bd5265963d9c6e6a0aecfc1ad4fd6abc4d51d2b463a2',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r19_frozen[_key] = _r19_dir + _filename
PROFILES[R19_PROFILE] = {
    'candidate': _r19_dir + 'vendor_boot.img',
    'candidate_sha256': 'd5f2855ffbc9b79ba2aad3d987dbe97d4dcf82a63f47ac812ae3053edc9aabbb',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r19: r18 plus the cache probe. Row 3/4 keeps its fields and ends with " p1=<errno> p2=<errno> '
                    'p3=<errno> p4=<errno> csz=<KiB>": p1 = /System/Library/Caches/com.apple.dyld, p2 = the same '
                    'directory plus /dyld_shared_cache_arm64, p3 = the same file through /System/Cryptexes/OS, p4 = '
                    'the same file through /private/preboot/Cryptexes/OS; -1 means the probe did not run, 0 means the '
                    'lookup succeeded, anything else is the errno.  csz is the p2 va_data_size in KiB (0 when p2 is not '
                    'a readable file).  The console block carries "nuwa: cache probe a=<err>/<bytes>/<dev> b=... c=... '
                    'd=..." with full sizes and each vnode mount device.  Reading it: p1=0 p2=0 csz>0 means the '
                    'union does cover the dyld path and a repeat of the "no dyld cache" panic is a dyld/AMFI side '
                    'decision (then look at DYLD row 32 err/byp/mac and flg=8, and the "cache mmap MAC returned" '
                    'console line); p1=0 p2=2 means the directory is there but the file name/layout differs (check '
                    'for dyld_shared_cache_arm64e); all four nonzero with uni=1 rv=1 means the cryptex root is not '
                    'laid out as System/... and the union target is misaligned; p3=0 with p2!=0 means only the '
                    '/System/Cryptexes/OS link resolves; uni=0 or rv=0 means the union itself is not in effect and '
                    'the dyld question does not apply yet.  The namei() lookup trace is compiled out of this image, '
                    'so no "nuwa: lookup <" lines are expected.  No automatic retry; manually return to the '
                    'bootloader and restore separately with authorization.'),
    'frozen': _r19_frozen,
}

# --- r20: namei() lookup trace on, plus the AMFI / code-signing view ------------
# r19 proved the kernel can open /System/Library/Caches/com.apple.dyld and the cache file
# inside it (p1=0 p2=0) while launchd still reported "no dyld cache", so r20 changes nothing
# about the mounts and only adds visibility: namei() failures under that prefix print
# "nuwa: lookup <path> err=N" (the opt-in patch is compiled in for this image), and the
# SystemOS diagnostics report whether the AMFI interface is installed and what the
# code-signing configuration record holds (SYSOS amfi=/cs=, console "nuwa: cs ...").
R20_PROFILE = 'ufs-apfs-root-20261118-r20'
_r20_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r20/'
_r20_frozen = dict(_r14_frozen)
_r20_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r20',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r20 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55681024, 'kernel_sha256': 'd85a7ba129fd41308d8c4909cadcc8fc0087881a45423f4192f9f1dfa1eff90e',
    'kernel_path': 'out/nuwa-r20-20261118/kernel.macho',
    'fat_sha256': 'e96f0311fe65a74ec950596385d708ab7346cf7b2e269628e2b31339c695393f',
    'adt_bytes': 13600, 'adt_sha256': '4413b4bc529d8abda93ecc3b6a4584118185957ec54dd4efd6b8c59c3f8dcfcc',
    'derived_sha256': 'd41e804b66eb85e2238a7ae9f912e79d333b6ea3fc8c1a3320c9cb9ef4e764cb',
    'report_sha256': 'e75d97dfb00893cd1db4cf2d4bfd964d782808ba5b14633c45020ce07167aad7',
    'audit_sha256': '789647e575b8a0b4f8249ef3f51b22537a2717c68f299ab1ce8050fcc9a25480',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'e428b65dbb381b8fba8aed7c5b56e76679d99ac6267434c6b2699b4304fa830b',
    'config_bytes': 661, 'config_sha256': '6c1f9c2cc254d9204fa22dfe1cc54d8c539ce2ac00a5e8afb199a920c148b85a',
    'source': 'scripts/build-ufs-apfs-root-chmh-r20.py',
    'source_sha256': '84089501065c1305fe7254f141b7193473fe8254f2385cfeb23e77065dcdadd1',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '011ce72ea586e03040676e437a4ca9f25b84a444693e07fb373bd6cbd117ee83121547e19d2b14b9264941c3ebadffe6',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r20_frozen[_key] = _r20_dir + _filename
PROFILES[R20_PROFILE] = {
    'candidate': _r20_dir + 'vendor_boot.img',
    'candidate_sha256': '6d6282388232b2d64d31f10902eb5a338f7463c2444ba36f7b83c2f53aa12d5f',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r20: r19 plus two diagnostics. Row 3/4 keeps every r19 field and now reads "... uni=<0|1> '
                    'rv=<0|1> amfi=<0|1> cs=0x<hex> p1=<e> p2=<e> p3=<e> p4=<e> csz=<KiB>": amfi=1 means the AMFI '
                    'interface pointer is installed (the kext ran), amfi=0 means it did not; cs is the code-signing '
                    'configuration record (0xffffffff means the opt-in accessor was not linked). The console carries '
                    '"nuwa: cs amfi=<0|1> cfg=0x<hex>" and the r19 "nuwa: cache probe ..." line. New in r20: any namei() '
                    'lookup that fails with a path starting /System/Library/Caches prints "nuwa: lookup <path> err=<n>" '
                    'to the console. Reading it: nothing printed means no failing lookup under that prefix happened - '
                    'either dyld never asked for the cache path, or its lookup succeeded (p1/p2 in the row already '
                    'show the kernel can open it) - so a repeat of the "no dyld cache" panic with a silent trace points '
                    'at dyld refusing the cache it found or at the AMFI/mmap side, not at the namespace; a printed '
                    'errno names the failing component (2 ENOENT means the path was not visible at that moment, 13 '
                    'EACCES a policy denial, 62 ELOOP a symlink loop). amfi=0 with a panicking launchd means AMFI never '
                    'installed its interface, so any AMFI-side policy the image expects is not active; amfi=1 with '
                    'cs=0x0 or a small value means the default (restrictive) configuration is in force. No automatic '
                    'retry; manually return to the bootloader and restore separately with authorization.'),
    'frozen': _r20_frozen,
}

# --- r22: no dyld cache override, six cache probes, 4K hash cache, flags readback ----
# The r21 frame showed the kernel could open the cache on its default path (p1=0, p2=0) while
# dyld still reported "no dyld cache".  The reason was the DYLD_SHARED_CACHE_DIR override this
# port handed to the initproc: that directory does not exist (p3=2 on r19), and dyld4 stops
# searching when an override directory cannot be opened instead of falling back to its own
# default.  r22 passes no environment at all, and it also shows what it needs to judge the
# result: six cache-path probes (directory, main cache, the .01 and .42 sub-caches, the
# cryptex and preboot spellings), the main cache magic, the dyld flags as written and as read
# back from the commpage, plus the official 4K code-signature hash cache.
R22_PROFILE = 'ufs-apfs-root-20261118-r22'
_r22_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r22/'
_r22_frozen = dict(_r14_frozen)
_r22_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r22',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r22 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'd267f9cab727b768e8f5f147ee02667ad21c378a274497c2249f643349ceab4f',
    'kernel_path': 'out/nuwa-r22-20261118/kernel.macho',
    'fat_sha256': '6923322d5ae14e821d6af5d2936b7b0574f3218ae8bbb88f45bac48c6f294d10',
    'adt_bytes': 13600, 'adt_sha256': 'bb1601c87ae70487114d15e4ee995bf17b0cf4aa4765c16835af1150426153a1',
    'derived_sha256': 'cd5dea1a5b9b92a1d426ca5fb8dcbcf116edcfac9b3e00e31cd0091b564bdb72',
    'report_sha256': '83b6b40e36bd84fc1aecd334836490ed793faacffcaf09ee9557e4c20a00f033',
    'audit_sha256': '3e69b5230bbb67c67d0179b2ddc6af19dbc8e93c69ac307ba354ab987feadafc',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'b63fb0f974dfbd7f6ebfaffc3e617d7912eee86f0c8cb26f86fa7e7c9041aedf',
    'config_bytes': 661, 'config_sha256': '0b464fb4b2dac3d7fd8fa146d45bfafd78af1f58d418f6e41f29fa85352bb265',
    'source': 'scripts/build-ufs-apfs-root-chmh-r22.py',
    'source_sha256': '8baca224495cf924efbb6ad9665d2c789cb8ea166a849a344d547f38c472c0d8',
    'trust_sha256': 'eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3',
    'chmh_hex': '5bbea18e1629607f9d7985c42b952c4adb47e65b48e9185b7919d4207a66aca97aa04fcc2fb988abb9e0fb759382c08a',
    'seed_sha256': '6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9',
    'data_volume_uuid': 'B0E0F71F-A265-4038-8F5C-6D3632859DEF',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r22_frozen[_key] = _r22_dir + _filename
PROFILES[R22_PROFILE] = {
    'candidate': _r22_dir + 'vendor_boot.img',
    'candidate_sha256': '8660cf6baf53a92939abe3638d45521db0cd9c67a4656cb8fa00e3c52353e7d0',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r22: the dyld override is gone and the record shows why dyld does or does not load the cache. '
                    'Rows 3-5: "PID1 ... | SYSOS st= err=", then "dev= rauth= pb= mk= mos= ap= uni= rv= mg=", then '
                    '"amfi= cs= flg= rd= p1= p2= p3= p4= p5= p6= csz=".  p1 is the directory /System/Library/Caches/'
                    'com.apple.dyld, p2 the main cache dyld_shared_cache_arm64, p3 and p4 the .01 and .42 sub-caches '
                    '(the header declares subCacheArrayCount=42 and a missing sub-cache fails the load), p5 and p6 the '
                    'same main cache through /System/Cryptexes/OS and /private/preboot/Cryptexes/OS.  0 means the '
                    'lookup succeeded, 2 ENOENT, other values are the errno.  mg=ok means the main cache starts with '
                    'dyld_v1 and arm64; mg=bad means the name resolved but the content is not that cache (truncated or '
                    'wrong file).  flg is the value written into the commpage dyld flags (8 = skip ignition) and rd is '
                    'what the commpage holds immediately after the write; both should read 8.  Expected if the fix '
                    'works: DYLD row 32 shows err=0 byp=1 mac=0 flg=8 and the initproc panic is gone.  If the panic '
                    'remains: p1/p2/mg locate the cache (all good rules the namespace out), p3/p4 tell whether the '
                    'sub-caches are present, and flg/rd tell whether dyld could see the flag; a small rd or rd=-1 means '
                    'the commpage write did not stick.  cs_native4k_hash_cache_version is compiled in, so a code '
                    'signature page-size failure should now be the 4K hash path instead of EBADEXEC.  No automatic '
                    'retry; manually return to the bootloader and restore separately with authorization.'),
    'frozen': _r22_frozen,
}

# --- r23: the cache probe holds no usecount and compares the full 16-byte magic ----------
# r22 reached launchd and loaded the cache, then panicked in vnode_rele_ext() with a usecount
# of -1 (vfs_subr.c:2691), and its page said mg=bad for a cache dyld had just loaded.  The
# probe read the header through a second lookup with vnode_open()/vnode_close(); vnode_close()
# is the rele, and the magic compare looked for "arm64" at offset 8 instead of 10.  r23 reads
# the header with vn_rdwr() on the vnode the lookup already holds (one lookup, one put, no
# usecount), compares all 16 bytes and prints them as hex.  Everything else is r22's.
R23_PROFILE = 'ufs-apfs-root-20261118-r23'
_r23_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r23/'
_r23_frozen = dict(_r22_frozen)
_r23_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r23',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r23 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': '89db8ee910a23d8732f18393e2065ab9ae2a1bb69b9f7d0fcd2fa96de966fdf2',
    'kernel_path': 'out/nuwa-r23-20261118/kernel.macho',
    'fat_sha256': '55ff28fbe5f1a8d5392cf63e35e6181691ead5870825e52f7b4ab7e202d81021',
    'adt_bytes': 13600, 'adt_sha256': 'ae54f5a7b5228e7b35d8dbeb7a1a5678b6ea59a808525628fd211c14501a6f0a',
    'derived_sha256': 'e48f886ced7367bf869b8d1544a3f00f34d43977a504140ca7d3ab7fac9124b6',
    'report_sha256': 'bc0f4f2bc656e80ebed58f676507ad7d75d9b9ccb7fbe940978c8b6159257073',
    'audit_sha256': '5bc530f8569acb7cf8d03081e3cdcf8c84e640ad293cf7d32d6634687417eaf8',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '335d02e3a7a436c9777187d236643ec512a4e19dbc09710a284fc483c1d1cda8',
    'config_bytes': 661, 'config_sha256': '9cb34645bf21b859efa7461ca6e2b3bb4b5994f9844d120e683a3582464fc8a8',
    'source': 'scripts/build-ufs-apfs-root-chmh-r23.py',
    'source_sha256': '79da982dbbfb2a4d0df0bc9ff40ba2ccc691dce07f3a96d3ca14e72d22f13f77',
    'chmh_hex': '25f92e0656b89ba385417b9c93a21a35a7b502ecd1559e4654c09a3ec14ab13f3307f2e0c922e2636c49d055f3b79641',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r23_frozen[_key] = _r23_dir + _filename
PROFILES[R23_PROFILE] = {
    'candidate': _r23_dir + 'vendor_boot.img',
    'candidate_sha256': '1a9f6299f90e5f9cfdd3e728e2679c59d6e381a112f5d3915454696286321e18',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r23: r22 with a probe that cannot over-release a vnode and a magic compare that '
                    'looks at all 16 header bytes.  Rows 3-5 are unchanged: "PID1 ... | SYSOS st= err=", '
                    '"dev= rauth= pb= mk= mos= ap= uni= rv= mg=", "amfi= cs= flg= rd= p1= p2= p3= p4= '
                    'p5= p6= csz=".  p1..p6 are the vnode_lookup errnos of the six cache paths (0 ok, '
                    '2 ENOENT); csz is the main cache in KiB; mg is ok when the first 16 bytes equal '
                    '"dyld_v1   arm64" + NUL, bad when the name resolved but the bytes differ, - when '
                    'the read did not run.  The console line "nuwa: cache probe p1=..." carries the '
                    'six errnos, sizes and devices plus mg; the next line, "nuwa: cache magic=<32 '
                    'hex digits>", is the 16 header bytes that were compared, so a cache dyld '
                    'accepts but the magic check rejects can be read off the record instead of '
                    'guessed (a dump starting "64796c64 5f76312020206172" is the arm64 spelling).  flg is the commpage dyld '
                    'flags as written and rd as read back; both should be 8.  The r22 run reached '
                    'launchd, started keybagd (nprocs=2) and then panicked in vnode_rele_ext() with '
                    'usecount -1; the probe no longer opens/closes the cache, so that rele source is '
                    'gone.  Expected: launchd and the first daemons stay up past the 120 s observation '
                    'or the panic moves to another call site (which the panel then names).  No '
                    'automatic retry; manually return to the bootloader and restore separately with '
                    'authorization.'),
    'frozen': _r23_frozen,
}

# --- r24: root reference across the union mount, reboot log, Data seed observations --------
# r23 showed the cache probe was not the panic's source (its frames are the reboot path) and
# that the Data volume never mounts: the packaged ADT carries PackedRAMDisk = {0,0} and the
# kernel's own start() saw no usable range.  r24 holds one reference on the old root across
# the union mount (kept only when the mount moved rootvnode, uc= on the SYSOS row), logs who
# asked for a reboot, and observes the Data seed path end to end: the packed ramdisk pair the
# loader put in /chosen/memory-map, the driver's readiness and init count, the lookup result
# and a 1..5 reason code (fork of the RamBlock driver, diagnostics only).
R24_PROFILE = 'ufs-apfs-root-20261118-r24'
_r24_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r24/'
_r24_frozen = dict(_r23_frozen)
_r24_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r24',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r24 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'd8fc613a2e0a5749ab3708b40292a00ac9bd5c070579cc75857f04a113f738a7',
    'kernel_path': 'out/nuwa-r24-20261118/kernel.macho',
    'fat_sha256': 'a95048382e991191545a5c4a9e86dc7b36f071c865b05b5beed074ebd55fa30f',
    'adt_bytes': 13600, 'adt_sha256': 'ac603219ca2f04dae3ab70e840e9dea581f93695e0f6bc5cab49992b839ca9b6',
    'derived_sha256': 'a98dccd9a30ec4336a50e3ac48585bae3fc76d657374e652573fe0072dcff3d3',
    'report_sha256': '325b15217a2f5ce811fdf63cc38339dce634895efa2357ab257589db343d0e73',
    'audit_sha256': '423f54772a44ed00a8408430939f20af671ee6e46ee3b4faf435f6af1161581a',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'b6d945f98fdf073d054e2f6f108beac4343cc86959cc49945f3b087850e193f6',
    'config_bytes': 661, 'config_sha256': 'f9eed7e101dc136492f8d3e40e30e09aea95bbcd855e9780417dd01fce56df27',
    'source': 'scripts/build-ufs-apfs-root-chmh-r24.py',
    'source_sha256': 'f80abc55f9f176a12cc9f505145d899d49fa5d3cf892c48a507d9fe4509b4f18',
    'chmh_hex': 'cce2ac36d072ec49bd125e43cfb5808366ebf2fbcb18de8f48bbad458fae7d845c704c8e4843f1eb1f7ea46a8fd36548',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r24_frozen[_key] = _r24_dir + _filename
PROFILES[R24_PROFILE] = {
    'candidate': _r24_dir + 'vendor_boot.img',
    'candidate_sha256': '469524541c818af9527864644b9f5a7d19e9be822072ca6e1d60ae9136ee5e8a',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r24: r23 plus a root reference that survives the union mount, a reboot requester line, '
                    'and the Data seed path fully observed.  Rows 3-5 are unchanged except row 4 now ends '
                    'with "uc=<before>/<after>": the usecount of the old root before the mount and after the '
                    'reference was settled - after = before + 1 means the reference was kept (the mount really '
                    'moved rootvnode, which is what the union path needs), after = before means it was handed '
                    'back (mount refused or the root did not move).  Console: "nuwa: root usecount before= after= '
                    'ref_ok=" then "nuwa: packed ramdisk pa=<hex> bytes=<hex> found=<0|1>" - what the kernel '
                    'device tree holds at /chosen/memory-map/PackedRAMDisk; pa=0 bytes=0 '
                    'means the packed placeholder was never filled (found=0: no such property at all).  Then '
                    '"nuwa: data seed uuid=<uuid> ready=<0|1> ic=<n>" (RamBlock object ready, initializer calls) '
                    'and "nuwa: data seed rc=<0|1> dev=<hex> path=<devfs path|-> serr=<0..5>".  serr: 1 driver '
                    'not ready, 2 no IOMedia matched the UUID, 3 a match lacks UUID/BSD properties, 4 no '
                    'NativeRamBlock in the provider chain, 5 no usable seed.  The forked driver logs '
                    '"NativeRamBlock: start packed= pa= bytes= gphys=" plus a coded "start reject <1..9>" and '
                    '"NativeRamBlock: seed: matches= selected= reason=".  "nuwa: reboot requested by pid= comm=" '
                    'starts the reboot path in reboot_kernel().  Expected if the seed path is healthy: '
                    'pa!=0, bytes=1609888, ready=1, rc=1, serr=0, Dev /private/var mounted and launchd no longer '
                    'reboots for a missing Data volume.  No automatic retry; manually return to the bootloader '
                    'and restore separately with authorization.'),
    'frozen': _r24_frozen,
}

# --- r25: the console-only observations moved onto the diagnostic page --------------------
# The board's progress page does not capture printf()/IOLog(), so r24's Data/RamBlock/reboot
# lines were invisible.  r25 publishes them as globals and draws them: row 3 gains
# "rb=<ready>:<init-calls>:<reject>", row 8 gains "boot=<pid>/<comm6>", row 9 becomes
# "DATA st/e/ro/sd/serr/rc/d/dev=<prefix> | RD <pa>M/<size>K f=<0|1>".  Everything r24 fixed
# stays (root reference across the union mount with uc=, 4K hash cache, mg/flg/rd, probe).
R25_PROFILE = 'ufs-apfs-root-20261118-r25'
_r25_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r25/'
_r25_frozen = dict(_r24_frozen)
_r25_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r25',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r25 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'c4a2bdecde81ad511a153ab262ded1bd44a6078bea796a8b0e5bcab6982e362a',
    'kernel_path': 'out/nuwa-r25-20261118/kernel.macho',
    'fat_sha256': 'f06841dffa1894f2067316ab13f6fa7222e5eb732a34e2b2df9276a01ec5ac3a',
    'adt_bytes': 13600, 'adt_sha256': '060f2487d5bcf8ef9242862ce2423dc74671f0c633e5cdcfd5137717cbc2d0d7',
    'derived_sha256': 'f123da69fb8de9c24ece03d6ff3618311da0329f86da87f26010bfb5dde9f8ca',
    'report_sha256': '6c9fcbd80bacac005e5552524d3a13880f650fde08fefeebf1b4591cf3f8a37f',
    'audit_sha256': 'a8d7760ed3b30c36a95bc32465b887515b96557cb3c7f2c33301b9c6e86ed50c',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '7a0c7f62081a3510657285129185f209b4d9e30ebc9e15791fb8205b0dfe4259',
    'config_bytes': 661, 'config_sha256': 'b2e2cd1752a2399ae4b000718d35b9ab1cf510176b2fa3fcbd10211ebded591f',
    'source': 'scripts/build-ufs-apfs-root-chmh-r25.py',
    'source_sha256': '92123724b3573b1c748d4d586d61b41260eda6876f3a998876e130e9b789b778',
    'chmh_hex': '3b87ac45f6b013ac6364a1639229f118d90f422891a4e84156c7d1eabe31a07452d00bf93d26d80d1e8de1ec0a6ee5e2',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r25_frozen[_key] = _r25_dir + _filename
PROFILES[R25_PROFILE] = {
    'candidate': _r25_dir + 'vendor_boot.img',
    'candidate_sha256': 'fcfd25489425a6abe7bc262a9169d81df6b4f68b06a9017ec427f4360afafc6f',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r25: r24 with every observation the console lost drawn on the page instead.  '
                    'Row 3 = "<PID1 ... | SYSOS st= err=> rb=<ready>:<ic>:<rej>": ready is the RamBlock '
                    'disk object (1 = started), ic the initializer calls, rej the last start() rejection '
                    'code (1 base start, 2 no /chosen/memory-map, 3 both RAMDisk and PackedRAMDisk, 4 range '
                    'pa/bytes outside gphys, 5 ptovirt/lock, 6 packed layout, 7 seedCountNonzero, 8 big '
                    'sparse import, 9 sparse import; 0 = no rejection).  Row 8 ends with "boot=<pid>/<comm6>": '
                    'who called reboot (----/- until one does).  Row 9 = "DATA st=<stage> e=<errno> ro=<ro> '
                    'sd=<seed ok> serr=<1..5|0> rc=<seed return> d=<dev_t hex> dev=<devfs prefix> | RD '
                    '<pa>M/<size>K f=<0|1>": RD is the packed ramdisk the kernel read from '
                    '/chosen/memory-map/PackedRAMDisk, pa in MiB and size in KiB, f = the property exists.  '
                    'Expected if the seed path is healthy: RD pa!=0 with size=1572K (1609888 B), f=1, '
                    'rb=1:1:0, serr=0, rc=1, then DATA st=3 and /private/var mounted.  If RD is 0/0 with f=1 '
                    'the loader never filled the placeholder; f=0 means the kernel tree has no such property '
                    'at all (wrong ADT); rb reject 4 with a non-zero RD means the range argument, and serr=2 '
                    'with rb=1:1:0 means no IOMedia matched the Data UUID.  Row 4 still carries uc=<before>/'
                    '<after> for the old root.  No automatic retry; manually return to the bootloader and '
                    'restore separately with authorization.'),
    'frozen': _r25_frozen,
}

# --- r26: the Data ram disk is created explicitly (the IOResources persona never fired) -----
# r25's page showed RD filled (loader OK) but rb=0:1:0 - the class was registered and the
# persona is in the built-in table, yet no instance ever reached start().  r26 registers the
# class and then calls the fork's native_ram_block_start_service(): alloc, attach to
# IOService::getResourceService(), start; start() keeps one static claim so a late persona
# match cannot create a second disk.  Everything else is r25.
R26_PROFILE = 'ufs-apfs-root-20261118-r26'
_r26_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r26/'
_r26_frozen = dict(_r25_frozen)
_r26_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r26',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r26 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': '0ff3494854ee02dbb33e2d07ceb074da2d68fcfc18089c328791f35f4ac1f08a',
    'kernel_path': 'out/nuwa-r26-20261118/kernel.macho',
    'fat_sha256': 'a4c4c39983afeb7848c8ca47ccff0bcee9d8ed9bdc7c37ae9712529c72c7b1c4',
    'adt_bytes': 13600, 'adt_sha256': '701df9073b80f2694eca3e574da983c3f17436bedf4f636f4878e09dd75a3df3',
    'derived_sha256': 'b7aa7eebe22286d21ce0c1f1fc6fb00d682569e80d71f8010b2c4d93ea868541',
    'report_sha256': 'a8eccf6320a9b7d8605fde4938c6883b885295c1e19568b50e7d56e31307367a',
    'audit_sha256': 'b83895ed82f973277d2816175f5aceaf6ddcafea2930a6b2a47b216050e4853a',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '3337b7f1ed1f8b38f5e240dcd9312172b44d2527f688d89c885f9f46accb9785',
    'config_bytes': 661, 'config_sha256': 'd96a174e17b3647de98f198dde6079a77ab792cad483adaaa9ba6c4c5636e31e',
    'source': 'scripts/build-ufs-apfs-root-chmh-r26.py',
    'source_sha256': '98c86470db5ef10185b5eafe55f56079fffa0b5adb5e791b54db26db558c444f',
    'chmh_hex': '724b41cab99634f6d866e52f7573329a6104c0b3865ad507475359280ddf2991b1f9aef56704b8e24680851dea08c029',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r26_frozen[_key] = _r26_dir + _filename
PROFILES[R26_PROFILE] = {
    'candidate': _r26_dir + 'vendor_boot.img',
    'candidate_sha256': 'fc2fba6ab650d4ad2a742e4a20ad5146b86feb87535e84d90de5edd18d42d186',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r26: r25 with the Data disk created and started explicitly.  Row 3 is unchanged in '
                    'shape, "<PID1 ... | SYSOS st= err=> rb=<ready>:<ic>:<rej>", but the reject field is '
                    'one hex digit and now also covers the creation path: 0 none, 1..9 start() refusals '
                    '(1 base start, 2 no /chosen/memory-map, 3 both RAMDisk and PackedRAMDisk, 4 range, '
                    '5 ptovirt/lock, 6 packed layout, 7 seedCountNonzero, 8 big import, 9 sparse import), '
                    'a..d = 10..13 (alloc/init, attach, start returned false without its own code, no '
                    'IOResources), e = 14 a second instance was refused, f = 15 the creation entry point '
                    'was not linked.  Row 9 still shows "DATA st/e/ro/sd/serr/rc/d/dev | RD <pa>M/<size>K '
                    'f=" and row 8 the reboot requester.  Expected if the fix works: rb=1:1:0, RD non-zero '
                    'with 1572K, serr=0, rc=1, DATA st=3, then /private/var mounted and keybagd/launchd no '
                    'longer rebooting for a missing Data volume.  If rb stays 0:1:<hex>, the code says where '
                    'creation failed (a/b/c/d as above); if rb=1:1:0 but serr=2, the disk started but APFS '
                    'published no IOMedia with the Data UUID in time.  No automatic retry; manually return '
                    'to the bootloader and restore separately with authorization.'),
    'frozen': _r26_frozen,
}

# --- r27: the Data disk is created at the data mount, after bsd_autoconf -------------------
# r26 created it from IOPlatformExpertDevice::startIOServiceMatching(), which runs before
# IOService::setPlatform() puts IOResources on the registry root: the instance was not a
# registry member, registerService() took its diagnostic path and that faulted (Kernel data
# abort at OSMetaClass::getClassName+0xc reading the "NativeRamBlock" class-name string).
# r27 registers the class where it always did and creates the disk from
# nuwa_data_mount_prepare(), which the bootstrap thread reaches after bsd_init()/bsd_autoconf()
# (IOBSD published, registry connected), with a bounded 2 s wait for the media.
R27_PROFILE = 'ufs-apfs-root-20261118-r27'
_r27_dir = 'out/nuwa-ufs-apfs-root-chmh-20261118-r27/'
_r27_frozen = dict(_r26_frozen)
_r27_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261118-r27',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r27 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'a8921ab06add3bf514adfca4eafe74dd879176d76dceb887c74d211cfef6dd85',
    'kernel_path': 'out/nuwa-r27-20261118/kernel.macho',
    'fat_sha256': '878cf4eb03b8235576bc9a23111de4969acad78c751bda4389d66dcf519dee18',
    'adt_bytes': 13600, 'adt_sha256': '4215db6b2e85b6faf3b7352d2d1768aa7dcb7f4925e3f082d4403bfc4466ba02',
    'derived_sha256': 'fa02592c734cd2aec604070fe3a782dac28c5123077a83136ca6a956b6e04b59',
    'report_sha256': 'ec573c8b2ecb91755505ea45cafa069c79caab2c6ebc6b89adf72a79a05264da',
    'audit_sha256': '3d8fd3acd4e5a8c615dcb0d802e86161cda6b28a3660355dd1b45be845986d3b',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '72589c45b6e842d6777344a4faf9e60d1058160e54b4d0479382082074f7a595',
    'config_bytes': 661, 'config_sha256': 'e66e82482255b226016fdb7bfd8f4ab67d623a7f1161ba876baa6f38cb07062e',
    'source': 'scripts/build-ufs-apfs-root-chmh-r27.py',
    'source_sha256': '5d04fdb0084782200ce05afa5d132186ffaa4c59bf37c1e6122dc24ae9feece6',
    'chmh_hex': '4c77d6a7228fe09b2ffa49a500fecb59b42ee2004315e4b3b75268e12a98413cc4668332e7b27cc32c0f8b4f21632063',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r27_frozen[_key] = _r27_dir + _filename
PROFILES[R27_PROFILE] = {
    'candidate': _r27_dir + 'vendor_boot.img',
    'candidate_sha256': 'aa51fa0f0d0578308df939b94af1eb071f12b44a6d6015b3b9c3244c2c462401',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r27: r26 with the Data disk created at the data mount instead of inside the platform '
                    'expert start.  The page is r25/r26 shaped: row 3 "<PID1 ... | SYSOS st= err=> '
                    'rb=<ready>:<ic>:<rej hex>", row 8 "<last IRQ> boot=<pid>/<comm6>", row 9 "DATA '
                    'st/e/ro/sd/serr/rc/d/dev | RD <pa>M/<size>K f=".  Expected if the fix works: no early '
                    'Kernel data abort (r26 crashed at OSMetaClass::getClassName+0xc with far reading the '
                    '"NativeRamBlock" string), rb=1:1:0, RD non-zero with 1572K, serr=0, rc=1, d=<dev_t>, '
                    'DATA st=3 and /private/var mounted, and keybagd/launchd no longer rebooting for a '
                    'missing Data volume.  If rb=0:1:<hex> the hex digit still names the failure (a..d = '
                    '10..13 creation path, e = 14 a second instance, f = 15 the entry point was missing); if '
                    'rb=1:1:0 but serr=2 the disk started and the 2 s media wait was not enough.  No '
                    'automatic retry; manually return to the bootloader and restore separately with '
                    'authorization.'),
    'frozen': _r27_frozen,
}

# --- r28: class registration bracketed by preModLoad/postModLoad ----------------------------
# r26/r27 aborted in OSMetaClass::getClassName() because the class's static initializer was
# called bare: the metaclass only stores the class-name string and postModLoad() is what turns
# it into a registered OSSymbol.  r28 registers through
# native_ram_block_register_class(): preModLoad("__kernel__") -> initializer -> postModLoad().
# r27's creation point stays (data mount, after bsd_autoconf, 2 s media wait), and the
# ineffective r24 root-reference guard is gone (uc 10/8; see INVALID-FIXES.md).
R28_PROFILE = 'ufs-apfs-root-20261119-r28'
_r28_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r28/'
_r28_frozen = dict(_r27_frozen)
_r28_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r28',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r28 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'e000e7a6ac99b5f72e0ea1b0d73521c07986a0a126ff62b4b2250f46abb43391',
    'kernel_path': 'out/nuwa-r28-20261119/kernel.macho',
    'fat_sha256': 'c0957797ca2e61559767d28b4b63f8c78dd9b4776b584142bca4637da3289a07',
    'adt_bytes': 13600, 'adt_sha256': '04de0c775d1099f09fc1ba9de3099d6877af15ace2952dd5842c7080b4d70e80',
    'derived_sha256': '18d219f74249fd2e7823ae306050d82765fae76d4b2ffbab7056f7892b97bc72',
    'report_sha256': '4e9001b4f15f45576eaab18ba80eeb0efa7aad1c2a9c080fe2474751c2a455a9',
    'audit_sha256': 'e45706d10a055eae0c161b29d5059a186024308c63c346fd00d73d86e7fc8da3',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': '394dfdcd3e2a626d436ccb5a15ac075d22fd2523b7d9afc670e40bb46badccfd',
    'config_bytes': 661, 'config_sha256': '7e4d86c9ec6fc3881726b8281fb3815c81605ace0199585267fef00675984cd8',
    'source': 'scripts/build-ufs-apfs-root-chmh-r28.py',
    'source_sha256': '1225f84c363a8d7fe5aa118056e321956337bf097ffba72e46f1586cce516cad',
    'chmh_hex': '5fd2c37ff8f1eb1516730966ef66ce09ef863bca63f8fce320ce1a57d00cd040e781f7ee9ed1f06239fd115e90b1f026',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r28_frozen[_key] = _r28_dir + _filename
PROFILES[R28_PROFILE] = {
    'candidate': _r28_dir + 'vendor_boot.img',
    'candidate_sha256': '2652369b1c2eb00f5396e8c1f19719709fc224b2c396199ba97a61cc247bacf7',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r28: r27 with the class registration bracketed by OSMetaClass::preModLoad/'
                    'postModLoad, and the ineffective r24 root guard removed.  Row 3 keeps "rb=<ready>:'
                    '<ic>:<rej hex>", row 8 "boot=<pid>/<comm6>", row 9 "DATA st/e/ro/sd/serr/rc/d/dev | RD '
                    '<pa>M/<size>K f="; row 4 no longer ends with uc= (the old-root pairing variables are '
                    'gone).  Expected: no early Kernel data abort (r26/r27 aborted in '
                    'OSMetaClass::getClassName with far inside the "NativeRamBlock" literal), '
                    '"nuwa: ram block class registered=1", rb=1:1:0, RD non-zero with 1572K, serr=0, rc=1, '
                    'd=<dev_t>, DATA st=3 and /private/var mounted, so keybagd/launchd stop rebooting for a '
                    'missing Data volume.  If rb=0:1:<hex> the hex digit names the creation failure (a..d = '
                    '10..13, e = 14 second instance, f = 15 entry point missing); if the registration line '
                    'says 0 the postModLoad bracket failed and the class is still unregistered.  No automatic '
                    'retry; manually return to the bootloader and restore separately with authorization.'),
    'frozen': _r28_frozen,
}

# --- r29: root cdir reference + reboot requester at the three entry points ------------------
# The r28 device run mounted the Data volume (DATA st=4) but still panicked on the reboot path
# (vnode_rele_ext usecount -ve, reached through apfs vflush -> vclean -> vnode_update_identity),
# and the page kept boot=-1/-.  r29 gives kernproc's fd_cdir its own vnode_ref in
# set_rootvnode() (XNU_NUWA_ROOT_CDIR_REF; the cdir moves and the hold is dropped with it), and
# records the reboot requester at reboot(2) (src=1), reboot_kernel() (src=2) and host_reboot()
# (src=3) with a first-wins latch, repainting the page on the spot.
R29_PROFILE = 'ufs-apfs-root-20261119-r29'
_r29_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r29/'
_r29_frozen = dict(_r28_frozen)
_r29_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r29',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r29 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55685120, 'kernel_sha256': 'ca33a66413e987a0dc97148f033d94c0d18f9db87df880e0b5c18a2997254de7',
    'kernel_path': 'out/nuwa-r29-20261119/kernel.macho',
    'fat_sha256': '004bf331dd6aa224d30bc527e1181730d18b2006b5c20c810d7a9ecf8d56b23c',
    'adt_bytes': 13600, 'adt_sha256': '8b4337b614870c0e114fcd3643423c56b5b187ad27c455043b4d01e1414bcefa',
    'derived_sha256': '6dbc8105016c8968430674b4320a0012153a52333b9b2f6cb10afadff89c19f8',
    'report_sha256': 'bd08fdb750ca06781b05ddc10ff1a4847a263fe8121477b44e98f73d5374b053',
    'audit_sha256': '4227734fd7209b0bca3ef058c8a9ad65d6b0000219d33199a0376ce8601f5ae5',
    'layout_sha256': 'fb070ca141ecc38f4eed4d12e973382427963b96d459500cf3b3502b1a51cc3d',
    'provenance_sha256': 'daf0bc8c2fc201a1ae83867e13b6399a0ab49ebd1c7a0e89085eb8763ff2726a',
    'config_bytes': 661, 'config_sha256': 'e482433c84ab535a94550d612f700a7deea4f956d123ed77e56b25d424f453ff',
    'source': 'scripts/build-ufs-apfs-root-chmh-r29.py',
    'source_sha256': '4901fe8edd6ee6b71d56063d84cbdb0750442178537c22f754ece705bd56a92b',
    'chmh_hex': 'a58fbab1a2fa18713a50ffdfd62b66f5234920792b5a31b3063d0bd0386b52b567fbbb642ba0da59fd93207abdafe3d4',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r29_frozen[_key] = _r29_dir + _filename
PROFILES[R29_PROFILE] = {
    'candidate': _r29_dir + 'vendor_boot.img',
    'candidate_sha256': 'e1f247f334e270730078e23368933d24c0c027f60c15c94d261f0624f214ffb6',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r29: r28 (Data volume mounted, DATA st=4) with the root cdir reference and the '
                    'reboot requester observation.  Row 9 still carries "DATA st/e/ro/sd/serr/rc/d/dev | '
                    'RD <pa>M/<size>K f=", row 3 "rb=<ready>:<ic>:<rej hex>", row 8 "boot=<pid>/<comm>".  '
                    'Expected on the reboot path: no "usecount -ve" panic in vnode_rele_ext (the '
                    'kernproc cdir + initproc cdir + rootvnode holds now match the three releases), '
                    'DATA stays st=4, and boot= shows the real requester with "nuwa: reboot request '
                    'src=<1|2|3> pid=<n> comm=<name>" on the console.  src 1 = reboot(2) syscall, 2 = '
                    'reboot_kernel(), 3 = host_reboot() (mach trap, which does not unmount).  If boot= '
                    'still reads -1/- the console line says why ("reboot record has no current '
                    'process") - the page is repainted by the recorder itself, not by the 1 s monitor.  '
                    'No automatic retry; return to the bootloader and restore separately with '
                    'authorization.'),
    'frozen': _r29_frozen,
}

# --- r30: reboot howto, keybag directories, bsd_init -> keybagd time -----------------------
# Observation only on top of r29 (which removed the vnode_rele_ext panic and mounted the Data
# volume writable): the reboot requester now carries its howto flag word, /private/var/{keybags,
# db,tmp} are checked (lookup+getattr) right after the mount verified, and the page shows
# bsd_init -> first keybagd sighting in milliseconds for the early-boot watchdog question.
R30_PROFILE = 'ufs-apfs-root-20261119-r30'
_r30_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r30/'
_r30_frozen = dict(_r29_frozen)
_r30_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r30',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 build-tag=nuwa-r30 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55689216, 'kernel_sha256': '334e43567a4084ab864aa3a363c71f9e87dd339f2b6596c107a54758107a3def',
    'kernel_path': 'out/nuwa-r30-20261119/kernel.macho',
    'fat_sha256': 'e142e02f092581efc30994a60d1ad0737de5aca12e00cc0d9c0211b94a3fc3ba',
    'adt_bytes': 13600, 'adt_sha256': 'd95b005bd00f756d8aaa22eceff1f08c8c6c7d7937163ffacfe733ceb8d6ed6a',
    'derived_sha256': 'c77a76eb5be34262153e680392526000c9bebc078c2674d2f13d351aa850d19b',
    'report_sha256': 'd27a41d7aeaf1fd57eb5c4e646127a90609e7fb140bee769ed98211be31563f3',
    'audit_sha256': '30c265de8b7fb4d65b4511c74e9eff060b4c9a6a9f33fbd208e23c9172da59df',
    'layout_sha256': 'b395b61827ae0cd1250563fb07ddf61cdeefc385653b347482fd89348cfa4479',
    'provenance_sha256': 'cfa98af6b947ca9d18336fe8ed520cbe9d8d73e95d3cd36df519b011bcd749ee',
    'config_bytes': 661, 'config_sha256': '306e46776dee6418535b77a9f70c78cb7cf5bd18681c272b8142570226a2497a',
    'source': 'scripts/build-ufs-apfs-root-chmh-r30.py',
    'source_sha256': 'af758d7e87ab663f2fe41a36234c75f574de412ebbf460a48e54a4c3d9336f71',
    'chmh_hex': '1f91c60d68b2b6a478334445d72188b9a4525b7c990ae92f3e8471cd5d7de70d67db731b341ecce7bc781be4e2b929df',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r30_frozen[_key] = _r30_dir + _filename
PROFILES[R30_PROFILE] = {
    'candidate': _r30_dir + 'vendor_boot.img',
    'candidate_sha256': 'd5d99a03597c3d571784beb4b8893d6f00c27aa7160ab749146a725f7ff5b97e',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r30: r29 plus observations.  Row 8 is now "IRQ PC <pc> PSR <x> SP <sp> '
                    'boot=<pid>/<comm>/<howto>"; the howto field is the RB_* flag word the requester '
                    'passed (0 = RB_AUTOBOOT, a plain userspace restart; 400 = RB_QUICK, no unmount '
                    'pass; 800 = RB_PANIC; 8 = RB_HALT; src=3 host_reboot records HOST_REBOOT_* '
                    'instead) and the console prints "nuwa: reboot request src=<1|2|3> howto=0x<flags> '
                    'pid=<n> comm=<name>".  Row 7 ends with "kb=<keybags><db><tmp> t=<ms>": each kb '
                    'letter is o (directory with a write bit), r (no write bit), m (missing) or e '
                    '(lookup/getattr error); t= is bsd_init -> first keybagd sighting in milliseconds '
                    '(0 until seen).  Expected on a watchdog-style restart: the requester is a '
                    'userspace process (comm keybag/launchd/...) with howto=0, kb without m, and t= '
                    'close to the elapsed time before the restart; t= of 100000+ with an otherwise '
                    'healthy boot points at the early-boot watchdog rather than at Data.  No '
                    'automatic retry; return to the bootloader and restore separately with '
                    'authorization.'),
    'frozen': _r30_frozen,
}

# --- r31: AppleKeyStoreState linked in, gated by aks=1 -------------------------------------
# r30 ended with keybagd asking for a plain reboot at t=72109 ms while the Data volume was
# mounted writable: there was no AppleKeyStore behind the keychain.  r31 links the unchanged
# UniXNU AppleKeyStoreState component (software key wrapping from the ADT identity), registers
# it inside the preModLoad/postModLoad bracket and creates it from the Data mount after
# bsd_autoconf(); the boot argument aks=1 turns it on.
R31_PROFILE = 'ufs-apfs-root-20261119-r31'
_r31_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r31/'
_r31_frozen = dict(_r30_frozen)
_r31_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r31',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 build-tag=nuwa-r31 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55717888, 'kernel_sha256': '626543a02f1a9d79e404ad588416e4f810ed1d7bb106ed9759c3b460a4227afd',
    'kernel_path': 'out/nuwa-r31-20261119/kernel.macho',
    'fat_sha256': 'dc3cf4ea1ffb683ab2170c2b6e13c11ac062e74164197cfb066fecaadfbf0776',
    'adt_bytes': 13600, 'adt_sha256': 'c8e06610aee8e2a6e46ee86d3c3c415abddf1f5a57ccda297adb32e92eab45d2',
    'derived_sha256': '3695c06ca818d6b0aa3e187760ca973472a5901e8adac4bab93e2a0af1847fa5',
    'report_sha256': 'c66db5dbf2a994fd59109ecdc38bd4c6b647e1c17ac3cc2f5399d55cdf4a36c6',
    'audit_sha256': '193141b1fd8039078fdb4957b381b5b02cb89b49cd078d10ed210510460647b4',
    'layout_sha256': 'd063b56b3ab9423bed01b0976358c72bf88978759347a5c3e5e20d5d23dae887',
    'provenance_sha256': 'd87e7ee7b3ac30063bfedaf256d962127b35415d6f9207924654ae561c36498c',
    'config_bytes': 667, 'config_sha256': '3672aa45df9983dbbb7d410589901969404b9f50fee322a1af3e582c2badecf3',
    'source': 'scripts/build-ufs-apfs-root-chmh-r31.py',
    'source_sha256': '9a99e404ea691b3bdb2424fe2eb7d062403f9adbac2f0f3b1e6d86213c37afd4',
    'chmh_hex': 'edd3602064e405780f1f7c324c7d175f43ff252553edbc32a4a0341fac010019f1960eaaa18b18c6e2f2a55ffaa7da53',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r31_frozen[_key] = _r31_dir + _filename
PROFILES[R31_PROFILE] = {
    'candidate': _r31_dir + 'vendor_boot.img',
    'candidate_sha256': 'c9ed423d3f6b3ac8ebf1d9fe79ac60d31b684cd56fe4abb8e3559b1e1286ffd9',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r31: r30 plus the UniXNU AppleKeyStoreState component and aks=1.  Row 4 ends '
                    'with ak=<state>/<opens>: state 0 = off/not run (aks missing), 1 = class '
                    'registered, 2 = service started; opens counts IOServiceOpen calls.  Console: '
                    '"nuwa: aks class registered (enabled=1)", "nuwa: aks started identity_bytes=8" '
                    'before initproc exec, "AppleKeyStore: register: postModLoad=0", then '
                    '"nuwa: aks user client opened" when keybagd/securityd connect.  Expected: no '
                    '"boot=11/keybag" reboot request, launchd keeps spawning (nprocs rises), '
                    't= still reports the keybagd sighting, DATA st=4 and kb=ooo unchanged.  If '
                    'ak=2/0 and boot= still names keybagd, the service started but the daemon did not '
                    'accept it (look at the console reject/selector lines).  No hardware data '
                    'protection: the wrap key comes from /chosen/unique-chip-id, keybag/passcode/'
                    'reference-key operations are unsupported.  No automatic retry.'),
    'frozen': _r31_frozen,
}

# --- r32: AppleKeyStore dispatch ring on row 10 --------------------------------------------
# r31 reached ak=2/1 (service started, keybagd connected once) and keybagd still asked for a
# reboot, so some selector's answer is not what it wants.  r32 records the last four
# (selector, IOReturn) pairs at the dispatch callback and draws them below the DATA row.
R32_PROFILE = 'ufs-apfs-root-20261119-r32'
_r32_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r32/'
_r32_frozen = dict(_r31_frozen)
_r32_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r32',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 build-tag=nuwa-r32 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55717888, 'kernel_sha256': '8a343b2784ea63862a971645c22fda3916b5dc9802cc0f01ce7c25dc5dd07966',
    'kernel_path': 'out/nuwa-r32-20261119/kernel.macho',
    'fat_sha256': '7b2240337d434824ff343251529dad9ff10cb441861be08e6d20aba8097aa734',
    'adt_bytes': 13600, 'adt_sha256': 'b69ffa48e1a65b935abf0103a6719cfbf595086aefc61d6cd4ee796937989e10',
    'derived_sha256': '05a17f424394b8063cfc23d3739bbd217e990c51a0729c97a5c8fd543ee1fb7a',
    'report_sha256': '40fded1f53850fa697ad05123f42e7d4f96df8f10368d6b1a990ba9c3dece04d',
    'audit_sha256': '551223e3405d871dec2f3ba69dc895dabc598c2ce491a494c7d3142fe1e81175',
    'layout_sha256': 'd063b56b3ab9423bed01b0976358c72bf88978759347a5c3e5e20d5d23dae887',
    'provenance_sha256': 'f1d20b2edd676195b8c7a8d1ddbd14cc5d5d7ee51f1a802bb66579a9077b181d',
    'config_bytes': 667, 'config_sha256': '9d6a01fe0514f495a219b648cb4ebebf3ea818acd75ccdf794f5c1e859c4d15e',
    'source': 'scripts/build-ufs-apfs-root-chmh-r32.py',
    'source_sha256': 'f2c6e2377e3eb3d1fa6c4e5fc95a49366ff9dacd884a56f813cdbd330281f6f8',
    'chmh_hex': '82445204ce6776ffa94550c9f3a01ecbb798fa34c8202385559dfe2a32687652c255509ea01220aaf8fa916d28845f78',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r32_frozen[_key] = _r32_dir + _filename
PROFILES[R32_PROFILE] = {
    'candidate': _r32_dir + 'vendor_boot.img',
    'candidate_sha256': 'dfecf0f3d9a5497e7a67875e225ae1dae56dbfb92da43653e205c0acb366e9c7',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r32: r31 plus row 10 "AKS <sel>:<rc> <sel>:<rc> <sel>:<rc> <sel>:<rc> '
                    'n=<count>", newest first, where sel is the AppleKeyStore selector the user '
                    'client was called with (hex) and rc the low byte of the IOReturn it returned '
                    '(00 success, c7 unsupported, c2 bad argument, 05 no memory, d5 not ready); '
                    'the newest entry equals nuwa_aks_last_selector/last_result and n counts every '
                    'dispatch since boot.  Read it against aks=1: the last selector keybagd reached '
                    'before the reboot is the one whose answer it rejected, so the next round '
                    'extends that selector instead of guessing.  Rows 3/4/7/8/9 are unchanged '
                    '(ak=, kb=, t=, boot=, DATA), and the two stage-history lines moved to rows '
                    '45/46 to make room.  No hardware data protection.  No automatic retry.'),
    'frozen': _r32_frozen,
}

# --- r33: AKS ring inside the panic-safe band ------------------------------------------------
# r32 drew the ring on row 10; the device showed the panic clear (panel y >= h/8, about row
# 9.5) wipes it.  r33 keeps the ring on row 6 (safe rows 0..8 at scale 3) next to a 20-character
# stage label, paid for by one-letter counter labels on rows 1 and 2.
R33_PROFILE = 'ufs-apfs-root-20261119-r33'
_r33_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r33/'
_r33_frozen = dict(_r32_frozen)
_r33_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r33',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 build-tag=nuwa-r33 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55717888, 'kernel_sha256': '6234a90ca614f26c13779b1f17adf76b3c503f5d2f485188adae3baa54701535',
    'kernel_path': 'out/nuwa-r33-20261119/kernel.macho',
    'fat_sha256': 'ac64d589b46578e51dc8465cc5a6e39ba2a301430f5e111cd8e5e1609084c34a',
    'adt_bytes': 13600, 'adt_sha256': '507ea986272be7cc02d7f43a993e34c6586940690639a646fc511201db7ca472',
    'derived_sha256': 'c4ef52625020ce044c75de4aed85d1859996e59c44af01d04fcde3cb370a05cc',
    'report_sha256': 'c6bd27ca194e52b564f0faeba597e788574dff93da6ee01a018f5ce15e055ca3',
    'audit_sha256': '97ebb3bc0d5c0b0cea117699e82dc9f207e58a8ea52afd0842c4863be7ad4d59',
    'layout_sha256': 'd063b56b3ab9423bed01b0976358c72bf88978759347a5c3e5e20d5d23dae887',
    'provenance_sha256': '6e7f52d37f825848d3a5190eecfec7a4f3b21548ce6a27f16e6a49628a26d636',
    'config_bytes': 667, 'config_sha256': '41a31b66339542489d7932cdb66b51657df61e6ab547b16cc254bb476130d8b7',
    'source': 'scripts/build-ufs-apfs-root-chmh-r33.py',
    'source_sha256': 'b354259ff775ff2a41e767b7940aabe05233b2295e70780e9f6e3d84aeabb88f',
    'chmh_hex': 'e477ad218dfd00c03db3908c47328d6c68b3ec061fd539992ca28ec84be230650dfb23a33aa3bea09d7083be61322bb4',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r33_frozen[_key] = _r33_dir + _filename
PROFILES[R33_PROFILE] = {
    'candidate': _r33_dir + 'vendor_boot.img',
    'candidate_sha256': '2d97df5ffe06b81ed9ac16e4be8abaed9897b4bba1ebd8e3388cea5fa9e33f29',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r33: r32 with the AppleKeyStore dispatch ring inside the panic-safe band.  '
                    'Safe rows are 0..8 (panel y < h/8, 42 px per row at scale 3), so row 6 now '
                    'reads "<stg 20 chars>  AKS <sel>:<rc> <sel>:<rc> <sel>:<rc> <sel>:<rc> '
                    'n=<count>" (newest first, <=74 columns); rows 1 and 2 use one-letter labels '
                    '(t/i/q/m/l/r/np/f, U/OVIRT) to make the room; the two stage-history lines are '
                    'back on rows 10/11.  Everything else is unchanged: row 3 PID1+SYSOS+rb, row 4 '
                    'device/auth/mount+ak=, row 5 AMFI/CS/p1..p6, row 7 TCR/TTBR/SCTLR+kb+t, row 8 '
                    'last IRQ+boot, row 9 DATA+RD.  Read the ring against aks=1: the last '
                    'selector keybagd reached before the reboot is the one whose answer it '
                    'rejected (values and sel meanings are in the r32 notes).  No hardware data '
                    'protection; no automatic retry.'),
    'frozen': _r33_frozen,
}

# --- r34: keybag seed, ADT no-effaceable-storage, launchd disabled list ----------------------
# r33 ended with keybagd walking aks_get_system twice and rebooting: after the handle it reads
# /private/var/keybags/systembag.kb.  r34's seed carries that directory and a 234-byte
# systembag.kb (KeyBagKeys "SWEET"), /defaults gains no-effaceable-storage = 1, and the kernel
# now writes launchd's disabled.plist after the Data mount (com.apple.watchdogd true, gated by
# disable-watchdogd=1) so watchdogd cannot brk #1 on a board without IOWatchdog.  Rows and the
# AKS ring are r33's.
R34_PROFILE = 'ufs-apfs-root-20261119-r34'
_r34_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r34/'
_r34_frozen = dict(_r33_frozen)
_r34_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r34',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r34 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55717888, 'kernel_sha256': 'ce24818ea19e1301dc0f4173a448ff3088aabf9bcc413f645f93c1c569a7f6dd',
    'kernel_path': 'out/nuwa-r34-20261119/kernel.macho',
    'fat_sha256': '114f6a05f48d7b6814517fe55dc699c23eb38b4486239ea67605d653d7e8e35e',
    'adt_bytes': 13640, 'adt_sha256': 'dd1734b3dcddef1b7b49b64cea2adf4c68bcd7e09da9d860fef77682879c326a',
    'derived_sha256': 'b8bd0cdd58393142214d10815a89743d80f2315cbfcc61e5648940d947d31566',
    'report_sha256': '3fbffc4a48cf0ce69fc09406fe66a206c52f17089bb248c3900b550c09898e4d',
    'audit_sha256': '9ebe7ec682e16526ed901493a8e17a3feeae69b0f4a78b7a4c4deb5060f6890f',
    'layout_sha256': 'dd7b91ac154414622a42b5a6b53bed242a1ce95b17abd82e7d460bd7aa8b3d63',
    'provenance_sha256': '7bd31150018fa134fa9480467357abbf35970c77a2dae7aa45f7fa22956ef3d8',
    'config_bytes': 687, 'config_sha256': '07eeab416c85d62013d101bce7cdb40c85d54e99e026a61fccaaf85ac6508435',
    'source': 'scripts/build-ufs-apfs-root-chmh-r34.py',
    'source_sha256': '1235d26d0e2c48fb7582c97936a2e41d74b0738929ecb6bea9b49440e02cad1a',
    'chmh_hex': 'fe7053a72911fb31d4342c75a77e91aa5c110a942f5b8616d13116593e12f66418f60afee02a136369bc2a4a5c41d8ad',
    'seed_sha256': '2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110',
    'seed_identity': 'e17c9691f69caa05b8d2c04dfce32bb53068446bd305f0652bed889c2fc69ec8',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r34_frozen[_key] = _r34_dir + _filename
PROFILES[R34_PROFILE] = {
    'candidate': _r34_dir + 'vendor_boot.img',
    'candidate_sha256': '46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r34: r33 plus the macOS keybag seed, ADT /defaults no-effaceable-storage and '
                    'the kernel launchd disabled list.  Expected: watchdogd never starts (no '
                    'IOWatchdog brk #1), keybagd finds systembag.kb after aks_get_system and does '
                    'not reboot, nprocs keeps rising and the AKS row (row 6) shows later selectors '
                    '(10/11 wrap/unwrap, 17/35 device state) with a larger n=.  If boot= still '
                    'names a process, read its pid/comm and the AKS ring; console lines: '
                    '"nuwa: launchd disabled policy: 0 labels=2 (watchdogd=1)" after '
                    '"nuwa: aks started", and "nuwa: keybagd pid= exec_ms=" when the probe sees it.  '
                    'The seed identity changed, so the keychain starts empty.'),
    'frozen': _r34_frozen,
}

# --- r35: abnormal-exit ring on the bar row --------------------------------------------------
# r34 reaches 117 processes and then SpringBoard and mobileactivationd exit with status=5 sig=5
# repeatedly.  r35 records the last four abnormal exits (comm, pid, signal, os_reason namespace
# and code, plus nprocs and the AKS call/open counters at that moment) and draws them inside the
# panic-safe band: row 0 reads "EX1 <comm6> <sig>:<ns>:<code>" newest first, and the console
# prints the full record.  Everything else is r34's.
R35_PROFILE = 'ufs-apfs-root-20261119-r35'
_r35_dir = 'out/nuwa-ufs-apfs-root-chmh-20261119-r35/'
_r35_frozen = dict(_r34_frozen)
_r35_frozen.update({
    'package_profile': 'nuwa-ufs-apfs-root-chmh-20261119-r35',
    'args': '-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024',
    'kernel_bytes': 55721984, 'kernel_sha256': '787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464',
    'kernel_path': 'out/nuwa-r35-20261119/kernel.macho',
    'fat_sha256': '90a5447c8c67a18c9f14fdb6a67c1620252f5ab472555b018478c9149518121e',
    'adt_bytes': 13640, 'adt_sha256': '5a7df5576699af18806c866604984ff294443db8b06514e266da796a5dba7ddc',
    'derived_sha256': '0808da1d0af31fd2bbf56080a96920a4bb79ea10f693554f93a900e7db534739',
    'report_sha256': '5d976fea5e21bd69f728a86d8f99d0e8f9eef0f9168f549dd1a436551542bf24',
    'audit_sha256': 'f5cef37274a1e6aca39261710518123b27602b619e9b2bf3b308680d5fe08ad8',
    'layout_sha256': '51f9d246c11ae4db9ca89c66bbe78ec28468e29e55c96309267b857356248c08',
    'provenance_sha256': '9e723becda2b3ec2d167432d77d44e848e54e3064dcbee2ef6466eea3dbb126f',
    'config_bytes': 687, 'config_sha256': '1b0179e3c2ea83619ddedc4785b82aa517741494a2bb2f174b3ece1fde06b3f8',
    'source': 'scripts/build-ufs-apfs-root-chmh-r35.py',
    'source_sha256': 'cbdaff922bd2e335cf73268e55a56c98b74dffd36e5a3b5c5a1759b3d088a9b5',
    'chmh_hex': 'e767b49dd510f8effb79a269620a18ef509a4ffd7bcbbb0c8fb566308fbd8458552b15378927cdafcabe2659874f4b94',
    'seed_sha256': '2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110',
    'seed_identity': 'e17c9691f69caa05b8d2c04dfce32bb53068446bd305f0652bed889c2fc69ec8',
})
for _key, _filename in (('kernel', 'kernel.macho'), ('fat', 'payload.img'), ('adt', 'derived.adt'),
                        ('derived', 'record.json'), ('report', 'outer-record.json'),
                        ('audit', 'audit.json'), ('layout', 'layout.json'),
                        ('provenance', 'provenance.json'), ('config', 'unixnu.toml')):
    _r35_frozen[_key] = _r35_dir + _filename
PROFILES[R35_PROFILE] = {
    'candidate': _r35_dir + 'vendor_boot.img',
    'candidate_sha256': 'c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed',
    'stock_sha256': STOCK, 'r4_sha256': R4, 'bytes': SIZE, 'r4_bytes': 1495040,
    'observation': ('r35: r34 plus the abnormal-exit ring.  Row 0 (inside the panic-safe band) '
                    'reads "EX1 <comm6> <sig>:<ns>:<code>" x4, newest first; sig/ns/code are the '
                    'low nibble/byte of status, the os_reason namespace and the os_reason code '
                    '(the console line has the full values plus pid, status, nprocs and the AKS '
                    'calls/opens at that exit).  Read it with the r34 state: 117 processes, '
                    'stage "fairplayd.H2 exec process signature accepted", AKS ring '
                    'e:00 11:00 0:00 7:00 n=133.  If SpringBoard/mobileactivationd keep exiting '
                    'with 5:ns:code, ns names the OS_REASON_* group (1 = EXIT, 2 = SIGKILL/'
                    'jetsam, 3 = ABORT, 4 = SPOTLIGHT/other platform groups by build; the '
                    'console value is authoritative) and the code is what the process passed to '
                    'abort_with_reason/exit_with_reason - that is the assertion source.  Nothing '
                    'on this row means no abnormal exit since boot.'),
    'frozen': _r35_frozen,
}

# Profiles whose frozen inputs are the PMGR/root shape: two evidence artifacts (a dict),
# a layout, and a packager source file.  Derived, not hand-listed, so a new root candidate
# cannot fall into the AMNM/CHMH branch (which expects one evidence path string).
PMGR_FAMILY = tuple(name for name, spec in PROFILES.items()
                    if name != PTHREAD_PROFILE and isinstance(spec.get('frozen'), dict) and
                    isinstance(spec['frozen'].get('evidence'), dict))


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
        if self.profile in PMGR_FAMILY:
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
        expected_args = (PROFILES[self.profile]['frozen']['args']
                         if self.profile in (ROOT_PROFILE, R12A_PROFILE, R12B_PROFILE, R12FIX_PROFILE,
                                             R12B1_PROFILE, R12B2_PROFILE, R13_PROFILE, R12AFIX_PROFILE,
                                             R14_PROFILE, R16_PROFILE, R17_PROFILE, R17C_PROFILE, R18_PROFILE,
                                             R19_PROFILE, R20_PROFILE, R22_PROFILE, R23_PROFILE, R24_PROFILE, R25_PROFILE,
                     R26_PROFILE, R27_PROFILE, R28_PROFILE, R29_PROFILE, R30_PROFILE,
                     R31_PROFILE, R32_PROFILE, R33_PROFILE, R34_PROFILE,
                     R35_PROFILE) else
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
        if self.profile in (R13_PROFILE, R14_PROFILE, R16_PROFILE, R17_PROFILE, R17C_PROFILE,
                            R18_PROFILE, R19_PROFILE, R20_PROFILE, R22_PROFILE, R23_PROFILE,
                            R24_PROFILE, R25_PROFILE, R26_PROFILE, R27_PROFILE,
                            R28_PROFILE, R29_PROFILE, R30_PROFILE, R31_PROFILE, R32_PROFILE,
                            R33_PROFILE, R34_PROFILE, R35_PROFILE):
            # r13/r14 pin the Data seed as a boot-set input; it is deliberately not part of the
            # CHMH material (kernel/loader/trust/args/parent-adt only).
            inputs['seed'] = f['seed_sha256']
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
                and provenance.get('kernel_path') == (f['kernel_path'] if self.profile in (HC_PROFILE, QUEUE_PROFILE, SID_PROFILE, NOP_PROFILE, ROOT_PROFILE, R12A_PROFILE, R12B_PROFILE, R12FIX_PROFILE, R12B1_PROFILE, R12B2_PROFILE, R13_PROFILE, R12AFIX_PROFILE, R14_PROFILE, R16_PROFILE, R17_PROFILE, R17C_PROFILE, R18_PROFILE, R19_PROFILE,
                                             R20_PROFILE, R22_PROFILE, R23_PROFILE, R24_PROFILE,
                                             R25_PROFILE, R26_PROFILE, R27_PROFILE, R28_PROFILE,
                                             R29_PROFILE, R30_PROFILE, R31_PROFILE, R32_PROFILE,
                                             R33_PROFILE, R34_PROFILE, R35_PROFILE)
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
        if profile in PMGR_FAMILY or profile in (AMNM_PROFILE, CHMH_PROFILE, PTHREAD_PROFILE):
            keys = (('derived', 'report', 'audit', 'layout', 'provenance', 'source', 'config') if profile in PMGR_FAMILY
                    else ('derived', 'report', 'audit', 'audit_source', 'layout') if profile == PTHREAD_PROFILE
                    else ('derived', 'report', 'audit', 'audit_source'))
            for key in keys:
                path = run.repo / run.frozen[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((REPO / run.frozen[key]).read_bytes())
            if profile in PMGR_FAMILY or profile == PTHREAD_PROFILE:
                for item in run.frozen['evidence'].values():
                    path = run.repo / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes((REPO / item['path']).read_bytes())
            if profile in PMGR_FAMILY or profile in (CHMH_PROFILE, PTHREAD_PROFILE):
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
