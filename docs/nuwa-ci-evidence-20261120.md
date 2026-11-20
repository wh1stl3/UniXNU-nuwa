# Existing porting evidence summaries (2026-11-20)

Transcribed verbatim from the pre-existing `porting.toml` evidence fields at device revision `134fd4ec88ba78b09d8c92d0676efdce50d55ee6`. Original `out/` and `.cache/` paths are local provenance, not files available in a clean checkout. These summaries are not independent verification, and preserve the original stated limitations. No device operation was performed for this transcription.

## 01. firmware

- Kind: `device`
- Original local reference: `out/nuwa-boot-payload-write-20261115-01/WRITE-r9-vendor_boot_a.json`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

Authorised fastboot flash boot_a (.cache/boot-stage12-v4-r4.img) and fastboot flash vendor_boot_a (r9 package), each a single bounded attempt, then one normal reboot; bootloader answered OKAY/Finished and the JSON records the measured candidate hash. Not rerun by this records update.

**Recorded result:**

boot_a 1495040 B sha256 692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5 with the stock tail untouched; vendor_boot_a r9 100663296 B sha256 37b665da4629f69ad97fca1335c91f99f81780c896ebceac4dd419264de8667f bound to kernel b1029f3d and CHMH rebound to it. Slot active, init_boot_a, vbmeta, misc and userdata untouched; write acknowledgement only, no device-side readback.

## 02. storage

- Kind: `device`
- Original local reference: `out/nuwa-boot-payload-write-20261115-01/WRITE-r34.json`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

Authorised single write under the multi-device policy: one fastboot devices, one getvar product per device (only nuwa targeted), fastboot -s <nuwa serial> flash vendor_boot_a out/nuwa-ufs-apfs-root-chmh-20261119-r34/vendor_boot.img, then one fastboot -s <nuwa serial> reboot at 2026-11-19T22:45:14+08:00; the 8-minute enumeration window is boot-observe-r34-20261119.log. Not rerun by this records update.

**Recorded result:**

Bootloader write acknowledgement only: r34 100663296 B 46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e matched the directory record, kernel ce24818ea19e1301dc0f4173a448ff3088aabf9bcc413f645f93c1c569a7f6dd (55717888 B), args include aks=1 and disable-watchdogd=1, seed 2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110 (apsb_xid 16), CHMH fe7053a7...d8ad, ADT dd1734b3...326a (13640 B); no device-side readback exists (no fastboot fetch, no adb in fastboot mode) and only vendor_boot_a was touched. The window had zero adb and zero fastboot enumeration at all 48 samples; that is an enumeration observation, not attribution. Device behaviour is parent/user-reported (SpringBoard and mobileactivationd SIGTRAP); authentication NOT REACHED.

## 03. storage

- Kind: `host`
- Original local reference: `out/nuwa-r28-20261119/INVALID-FIXES.md`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

Windows host, read-only review of the r22-r28 device readings and the r28 object/verify assertions; no device command, no build.

**Recorded result:**

self-checked summary of device readings relayed by the parent: r22 mg=bad plus a vnode_rele_ext panic (vfs_subr.c:2691, usecount -1) on the reboot path, r23 mg=ok after the one-lookup/one-put probe, r24/r25 uc=10/8 with the removed root guard, r24 hdr=9 gpt=ff/ff, r26/r27 both aborting in OSMetaClass::getClassName (pc 0x785ee38, far inside the NativeRamBlock literal) at two creation points, and the r28 conclusion that the cause is the missing preModLoad/postModLoad bracket rather than the timing. Values are what the device reported, not an independent trace; the file also records which fixes are invalid so later rounds do not reapply them.

## 04. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-chmh-20261119-r34/record.json`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

WSL Ubuntu-22.04 device repo: /home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r34.py --output out/nuwa-ufs-apfs-root-chmh-20261119-r34, then the same script with --audit into out/nuwa-ufs-apfs-root-chmh-20261119-r34-audit-r1.

**Recorded result:**

self-checked packaging record only: r34 kernel ce24818e...f6dd (55717888 B), seed 2c95d15b...8110 (1896608 B, apsb_xid 16, Data volume B0E0F71F-A265-4038-8F5C-6D3632859DEF), args with aks=1 and disable-watchdogd=1, CHMH fe7053a7...d8ad, derived ADT dd1734b3...326a (13640 B), payload 114f6a05...e35e, outer 46aa4fd9...891e reproduced by the audit; authentication NOT REACHED and device_release false. The keybag seed file itself is outside the repository.

## 05. storage

- Kind: `device`
- Original local reference: `out/nuwa-userdata-write-20261115-03/REPORT.md`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

Authorised no-backup write into the userdata prefix from TWRP: run-write-once.ps1 -Mode write driving scripts/nuwa-userdata-install.py with --without-backup --authorize-userdata-write-this-round --exclusive-offline-userdata --reviewed-and-independently-verified --staging-root /dev; 126 windows then the installer's own whole-image final readback. Not rerun by this records update.

**Recorded result:**

Installer and driver exited 0 (write-exit=0, outer timeout not reached): 8446279680 B written and read back, sha256 da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7, 126 windows, backup_policy=without-backup, no rollback; the pinned installer 1d8d077e, tests bb97229c and manifest bc344eb1 matched the pre-write gates. Device-side result is self-checked: the independent verifier re-run (out/nuwa-userdata-final-verifier-20261115-r3) was host-only, device_calls=0.

## 06. storage

- Kind: `device`
- Original local reference: `out/nuwa-boot-payload-write-20261115-01/REPORT.md`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

Authorised writes: fastboot flash boot_a with .cache/boot-stage12-v4-r4.img and fastboot flash vendor_boot_a with the r7/r8/r9 packages (each single attempt, bounded timeout, exit 0), then one normal reboot; observability poll recorded in boot-observe-r9-20261115.log. Not rerun by this records update.

**Recorded result:**

boot_a 1495040 B sha256 692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5 (199831552 B of the stock tail untouched); vendor_boot_a r7 24258f44c5a0869fa9ff6358cb13771f8c889d9721795b237a31af431a55a418, r8 8e09fae228f985eb4efc7bcf9d8c2c55b594f499af1f48a91f53db431e1ff66e, r9 37b665da4629f69ad97fca1335c91f99f81780c896ebceac4dd419264de8667f (100663296 B each). Slot active, init_boot_a, vbmeta, misc and userdata were not touched. Bootloader has no fastboot fetch and fastboot mode has no adb, so these writes have write acknowledgement only, no device-side readback; stock images and ROLLBACK-r*.md are retained.

## 07. storage

- Kind: `device`
- Original local reference: `out/nuwa-boot-payload-write-20261115-01/boot-observe-r9-20261115.log`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

Bounded enumeration poll (31 samples, 10 s interval) during the r9 boot window 2026-11-15T19:56:33+08:00..20:02:13+08:00.

**Recorded result:**

Neither adb nor fastboot enumerated at any sample. This is an enumeration observation only: it is consistent with iOS running and with no recovery/Android/Android-bootloader entry, but it is not attributed to a panic, to user action or to a successful boot by itself.

## 08. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-integration-20261114/observable-r5/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root Python3.11 -B observable-r5/{build.py,tests.py,setup-tests.py,marker-tests.py,audit.py}; exclusive run-r5-visible-candidate. Full paths and independent fresh-build commands in REPORT.md.

**Recorded result:**

self-checked only: 920 continuous/concurrent reads and tag wrap, nine terminal IO faults, guard/isolated NotReady/verify/shortcopy, zero failure callback and both locks released at actual panic stub; twelve injected real startRoot failure exits; actual publisher SystemOS-first stop and marker ordering; twelve final ARM64 marker cases including cap16 and refusal/cache/DSB; thirteen incremental final functions/191 calls, helper-to-panic and patched panic-to-existing renderer branch checked. Source delta exactly NativeUfs.cpp/RootCommands.h/NuwaUfsMarker.h; transport/policy/producer/TPL/old ABI unchanged. ShengUfs@99d8bcd3 and UniXNU@693f5d9 renderer/marker BSD-2-Clause-Patent ancestry reused. No hardware, DMA ownership, runtime ABI, actual panel scan, APFS mount or persistence claim; no device/package/default-config changes.

## 09. storage

- Kind: `host`
- Original local reference: `out/nuwa-userdata-crlf-host-20261114/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-userdata-crlf-host-20261114/check.py; six new TextProtocolTests plus four affected cases only, AST/whitespace/exact before-after diff and porting-record --base origin/feat/step7-kernel-patches-8796. Exits/hashes in commands.json/hashes.json.

**Recorded result:**

self-checked; actual confirmed CRLF text framing reproduced with deidentified146B fixture, LF/CRLF accepted only by shell-text parser; missing/false footer, ASCII/field/rc/stderr gates retain refusal. Raw diagnostic length/hash and binary memory/file/GPT/image paths verified unchanged, writer/staging/tools/guards exercised with both endings. Old source/evidence retained; zero device, real image/backup read, install or root boot. Existing authorization/claim gates unchanged; no automatic extra independent verifier/full-matrix expansion.

## 10. storage

- Kind: `host`
- Original local reference: `out/nuwa-userdata-no-backup-host-20261114/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-userdata-no-backup-host-20261114/check.py; directed/full tests, actual local wslpath, AST/whitespace/precise snapshot diff and porting-record --base origin/feat/step7-kernel-patches-8796. Exits/hashes in commands.json/hashes.json.

**Recorded result:**

self-checked only; actual adapter subprocess boundary injected, no device. Default backup still enforced; explicit authorized waiver succeeds/audits no rollback, failed tools/boot binding stop before mkdir/push/write, Windows push source-only conversion, nonzero rc/stderr/timeout/host open/fsync errors durably redacted. Old source pair snapshotted before editing for concurrent reviewer; old root/super executors and failed backup output not edited or imported. No cancelled8GB read, installation, restoration or root boot; new independent review/verifier pending.

## 11. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-integration-20261114/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root, GIT_NO_LAZY_FETCH=1, Python3.11 -B: exclusive build.py --out run-r4; tests.py --build run-r4; audit.py --build run-r4. Exact paths and fresh-output verifier commands in REPORT.md; commands.json and incremental-tests.json retain actual exits.

**Recorded result:**

self-checked only: real isolated kernel/build and extracted native entry/read/IO/parser functions with mocked IOKit/MMIO/cache primitives; 12 build commands exit0; 85 ARM64 function inventories, 269 direct calls, 72 indirect sites, 54 MMIO windows; 4208 APFS/52674 total donor bindings, 1050376 APFS executable bytes, exact final two 544-byte policy pointers/count2/public anchor. Existing OS+SystemOS userdata-v2 inputs reused, bounded header/external-table hashes checked; no full8GB/signature/old ABI matrix rerun. All media writes refused, no product board default change, packaging or device operation. Runtime domain/data DMA/IOKit private ABI/APFS mount/persistent interaction unqualified; future kernel CHMH rebind and new userdata/device authorization required. Reuse ShengUfs@99d8bcd3 BSD-2-Clause/source BSD-2-Clause-Patent, VerifiedRoot@974f043d BSD-2-Clause-Patent, existing ArmSmmu4K@83969cd8 MIT ancestry. Independent verifier/scout/deep and parent acceptance pending.

## 12. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-chmh-20261114-r1/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root, device repo, Python3.11 -B: build-ufs-apfs-root-chmh.py explicit r4 kernel/size/hash/profile --audit; test-ufs-apfs-root-chmh.py; complete commands in REPORT.md.

**Recorded result:**

self-checked only: historical r4 CHMH/FAT/outer with actual outer extraction, linked dual policy headers, userdata policy table hashes and bounded mutation rejection. New observable-failure kernel and fresh CHMH required; no final profile, no device action, no mount or authentication claim.

## 13. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-chmh-20261114-r2/REPORT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root, device repo, Python3.11 -B: explicit r5 root CHMH builder, actual outer audit, test-ufs-apfs-root-profile.py, three unauthorized dry phases; exact argv and exit in REPORT.md.

**Recorded result:**

self-checked only: r5 kernel 809587d5...575cb0acc bound to outer 72a4e8ea...0b279a9 and isolated executor profile; actual outer extraction, process trap and bounded negative controls, no device or userdata installation. Independent review/verifier pending; mount and visible runtime output not established.

## 14. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-combined-read-20261114/RESULT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root /usr/bin/g++ C++17 exact-chain test; /home/wh1stl3/.local/bin/python3.11 isolated build.py and audit.py; GIT_NO_LAZY_FETCH=1. Final commands/hash and rerun instructions in RESULT.md.

**Recorded result:**

self-checked only; parameterized upstream wire encoding/response logic resolves gHost/IS-W1C conflict without production transport changes. Final revision, fault endpoints and artifact identity bound by RESULT.md and provenance. No packaging/executor/device/root action; live data DMA, media read and ABI not qualified. ShengUfs@99d8bcd3 BSD-2-Clause/source BSD-2-Clause-Patent and retained ArmSmmu4K@83969cd8 MIT references. Independent verifier/final directed deep pending.

## 15. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-preserved-nop-chmh-20261114-r1/RESULT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root Python3.11 build-preserved-nop-chmh.py and test-preserved-nop-chmh.py; Windows WorkBuddy and WSL hostcheck, Windows selfcheck/dry/targeted; command logs in out/nuwa-ufs-preserved-nop-chmh-hostlogs-20261114

**Recorded result:**

self-checked only; actual kernel 55549952 bytes SHA256 05ebb53baf0d98aa0f189b8c1569e7375f6403c20b3df2c739734ba459488944, outer SHA256 d9550552966ac18d0d615870750a67225690b0ecc3ad1d9d62160d61279b3ee7. Four wrapper negatives, actual inputs and synthetic executor gates; no real device, claim or authorization. Authentication NOT REACHED; runtime and semantics pending independent review.

## 16. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-preserved-nop-exec-20261114/RESULT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root device repo: g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread -Iout/nuwa-ufs-sid-domain-20261114/run/source out/nuwa-ufs-preserved-nop-exec-20261114/test.cpp; explicit output/test invocation in RESULT.md. Python3.11 build.py --out out/nuwa-ufs-preserved-nop-exec-20261114/run-r2 and audit.py --build same directory, GIT_NO_LAZY_FETCH=1.

**Recorded result:**

self-checked: compile/test/build/final audit exit0; 20 actual shared execution-chain endpoints, competing entry, width/overflow boundaries. Kernel 55549952 bytes SHA256 05ebb53baf0d98aa0f189b8c1569e7375f6403c20b3df2c739734ba459488944. Exact inspect-only baseline delta, emitted seven HC writes and read whitelist, claim/cache code and full layout recorded. IOKit/MMIO/DMA/cache effects mocked in tests, no runtime acceptance. ShengUfs@99d8bcd3 BSD and ArmSmmu4K@83969cd8 MIT reuse; Arm IHI0062D.c source/hash retained locally. All artifacts isolated; no original kernel/executor/production path changes or device/package operation. Independent verifier/deep review pending.

## 17. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-preserved-route-plan-20261114/RESULT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root clang++ -std=c++17 -Wall -Wextra -Werror out/nuwa-ufs-preserved-route-plan-20261114/fixture.cpp -o out/nuwa-ufs-preserved-route-plan-20261114/fixture; run fixture

**Recorded result:**

Host-only self-checked: measured route/context fields within otherwise synthetic complete snapshot; no domain writes or submission API. Widths unqualified, producer handoff, shared bank, DMA lifetime and hardware ownership remain open; independent verifier pending.

## 18. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-sid-domain-chmh-20261114-r1/RESULT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root Python3.11 scripts/build-sid-domain-chmh.py and scripts/test-sid-domain-chmh.py; Windows and WSL host input checks and Windows executor self-check/dry/targeted checks; see RESULT.md

**Recorded result:**

SID packaging and executor host-only self-checked, no device operation or real claim. CHMH identity unauthenticated; mocked kernel tests do not establish live SMMU domain, ownership or accessibility. Independent verifier and final directed deep pending.

## 19. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-sid-domain-20261114/CONTRACT.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-ufs-sid-domain-20261114/build.py --out out/nuwa-ufs-sid-domain-20261114/run; test.py, retained-check.py and audit.py --build same run; rerun collectively via selfcheck.py

**Recorded result:**

self-checked only: actual build, 58 new final ARM64 cases, 6 retained marker/AT/SMMU mapper-policy cases and final machine audit exit0. Kernel 55545856 bytes SHA256 8610b862b2801b5e5730c227b518f76b3969bde351b2416acf786f84f946d0e4. Build commands/cwd/exit in run/commands.json; consolidated checks in run/selfcheck-commands.json. ArmSmmu4K@83969cd874503e65997ff7639f7dcf3d0a92cd17 MIT and ShengUfs@99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0 BSD reused locally, lazy fetch disabled. Exact inspect-only generated source delta and unchanged marker audited; 263 target loads max, all u32, 16 rows max. Hardware/IOKit/AT/marker-return boundaries mocked; no live domain/panel/PTE/power/ownership proof. Independent verifier and final directed deep pending; no original r7/queue/executor edits or device/package actions.

## 20. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-handoff-observation-20261114/SPEC.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-ufs-handoff-observation-20261114/test_association.py

**Recorded result:**

Synthetic correlation fixture only, self-checked; command and actual exit recorded in the exclusive output directory. No observed EBS, producer exclusion, hardware ownership or DMA claim. Independent verification pending. Earlier r2 incremental and repeatable trace extraction independently reproduced at out/nuwa-ufs-nop-r2-verifier-20261114/verifier-summary.md; later TRACE text corrections are not part of that verifier input.

## 21. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-nop-host-20261114/DESIGN.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL root Python3.11 -B out/nuwa-ufs-nop-host-20261114/build.py --incremental --out out/nuwa-ufs-nop-host-20261114/revision-r2-final; same Python -B out/nuwa-ufs-ownership-trace-20261114/trace.py

**Recorded result:**

Both exit0, self-checked only; seven inner build/model/audit commands exit0. Six incremental cases (five partial configure/start failures and normal/reentry), four fixed-firmware validation negatives; no old full matrix. First Model.cpp:156 fixture expected2 SMMU writes but actual combined format readback follows3, corrected expectation only; failed output retained. Bounded static trace pins local OEM SHA and matching DarwinBoot@3c757340 source; EBS registration-code target is not proof of registration success/execution. Trace final commands disable lazy-fetch; initial different partial-clone object query auto-attempted failed fetch, no retry; matching original Windows-base local object used. Original independent host verifier PASS retained separately, r2/trace independent verification pending. No device, packaging, DMA ownership or successful hardware-stop claim.

## 22. storage

- Kind: `host`
- Original local reference: `out/nuwa-ufs-nop-host-20261114/DESIGN.md`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root device repo: /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-ufs-nop-host-20261114/build.py --out out/nuwa-ufs-nop-host-20261114/selfcheck-final

**Recorded result:**

self-checked only; final command/log exits and hashes retained in commands.json/evidence.json. Closed actual host entry and local two-thread exclusion; model busy transfer/task/stop deadline/SMMU-conflict before dangerous writes, eight single-NOP failure/quarantine cases and valid response. MMIO/cache/clock fixture is not nuwa ownership or DMA evidence. Selected OEM EBS callback/GUID/patch bytes asserted against local asset; one additional public source edk2-stable202411 EventGroup.h BSD-2-Clause-Patent. Reuse ShengUfs@99d8bcd3 BSD-2-Clause repository/BSD-2-Clause-Patent SPDX. No kernel/device qualification, packaging, old ABI/signature replay or device action; independent verifier pending.

## 23. power

- Kind: `host`
- Original local reference: `out/pmgr-mode2-chmh-20261113-r4/outer-record.json`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

/home/wh1stl3/.local/bin/python3.11 -B scripts/build-pmgr-mode2-chmh.py --output out/pmgr-mode2-chmh-20261113-r4

**Recorded result:**

self-checked, uncommitted; fixed kernel 81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1 and exact mode2 args, CHMH rebound; FAT a9697c46d775e722d902cceea32070518ea2e8e5cfce8af8abc4eccd25afe701, outer ad74c1cb7beee59b60bc0fbb446a7439e8a21a39a3f956ea574b6a62410efd45. Actual outer FAT members reconstructed/read back. No normal configuration or device changes; authentication NOT REACHED.

## 24. power

- Kind: `host`
- Original local reference: `out/nuwa-pmgr-kernel-20261113-r5/kernel.json`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

WSL Ubuntu-22.04 root cwd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa: /home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-pmgr-kernel.py --out out/nuwa-pmgr-kernel-20261113-r5 --reuse-provider out/nuwa-pmgr-kernel-20261113-r2/provider; then scripts/audit-nuwa-pmgr-kernel.py --build out/nuwa-pmgr-kernel-20261113-r5 --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages with same interpreter; both exit0

**Recorded result:**

self-checked; uncommitted on stated HEAD. kernel 81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1/55451648B, native 98c4f8bd18bbf0829846e191039811d5feba12ad7ad4a1082e0a9402bc3f4185, map 90d1d88f1d1d694f0a219fd3e1c8c3c51180948b5bb4dea58de9d1bc60789e49. Manifest binds provenance/prelink/renderer/startup/eight bindings/final audit. Ten real-code bounded checks; eight final original bindings, 325 vslots, single manual initializer and root call statically checked. Mode1 cleanup/mode2 publication/full mode3 lifecycle not executed; pthread runtime unproven. Initial blocker superseded by parent-supplied review root-parent route; directed deep and independent verifier pending. No pins/official tree/old outputs changed, no device/packaging/commit/push.

## 25. power

- Kind: `host`
- Original local reference: `out/nuwa-platform-power-20261113-r2/build-report.json`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-platform-power.py --out out/nuwa-platform-power-20261113-r2

**Recorded result:**

self-checked; ordinary ARM64 build via /opt/unixnu-linux/llvm/bin/clang-24 against the pinned carrier out/pthread-renderer-20261112-r1/renderer-baseline.macho (SHA e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d). 325 vtable slots verified: slots 0/1/7 and 168-324 (except 312/313) are NuwaPlatformPower guards/lifecycle, 312/313 are inherited ApplePMGR readAon/writeAon, and slots 44/81/82/86/87/117/159/160 are the audited native IORegistryEntry/IOService deviations. late_transform moves the static initializer to the extdef partition with relocation remap and LC_DYSYMTAB bound update; re-parsed to assert N_EXT/partition consistency and __mod_init_func nreloc=0. Archive libNuwaPlatformPower.a SHA 568885fd698489843701907e5d8216f3c9b377c678a2d6710bd8652bad93d29e, 8 bindings, runtime_qualified=false, original_executable_modified=false, late_symbol_external=true.

## 26. power

- Kind: `host`
- Original local reference: `out/nuwa-platform-power-tests-20261113-r2/tests.json`
- Recorded revision: `029a79bb58a403c0f3441ed991ad312ae1102c39`

**Recorded command:**

/home/wh1stl3/.local/bin/python3.11 -B scripts/test-nuwa-platform-power.py --build out/nuwa-platform-power-20261113-r2 --output out/nuwa-platform-power-tests-20261113-r2/tests.json --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages

**Recorded result:**

self-checked; unicorn executes the carrier's actual nub read/write and readAon/writeAon instruction bytes with only the provider/nub object data mocked: nub read returns 0xffffffff, nub write routes through slot 313, readAon returns 0xffffffff, writeAon is a bare ret (final PC == return slot, x0 untouched, mock memory unchanged). Compiled object has nuwa_pmgr_run/nuwa_pmgr_checkpoint and does not redefine readAon/writeAon. 7/7 cases passed; 325-slot vtable resolution is a build-time static check, lifecycle/refusal not executed.

## 27. packaging

- Kind: `host`
- Original local reference: `out/verify-r35-20261120-03/record.json`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

WSL Ubuntu-22.04 device repo as root: /home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r35.py --output out/verify-r35-20261120-03/ (plain build) and the same script with --audit against out/nuwa-ufs-apfs-root-chmh-20261119-r35, plus scripts/test-ufs-apfs-root-profile.py, scripts/test-ufs-apfs-root-chmh.py and scripts/run-pmap-ret-once.py --self-check. No device command.

**Recorded result:**

coder self-checked, not verified: the four commands exit 0 and the self-check reports 157 groups with real_device_commands 0. out/verify-r35-20261120-03 matches the recorded r35 directory byte for byte on kernel.macho 55721984 B 787610183dc7...12464, vendor_boot.img 100663296 B c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed, derived.adt, payload.img and record.json, and its audit.json is byte-identical to out/nuwa-ufs-apfs-root-chmh-20261119-r35-audit-r1/audit.json (outer_sha256 c6e64820..., avb_authentication_claimed false). A first run failed only because build-nuwa-pmgr-kernel.py:23 reads /root/nuwa-pmap-ret-native-20261111/build-result.json under an ordinary user (EACCES, /root 700); the root rerun passed. r35 was not written to any partition and its device behaviour is unobserved; docs/nuwa-r34-page-evidence-20261120.md carries the record.

## 28. packaging

- Kind: `host`
- Original local reference: `out/nuwa-ufs-apfs-root-chmh-20261119-r35/record.json`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

WSL Ubuntu-22.04 device repo: /home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r35.py --output out/nuwa-ufs-apfs-root-chmh-20261119-r35, then the same script with --audit into out/nuwa-ufs-apfs-root-chmh-20261119-r35-audit-r1; both exited 0.

**Recorded result:**

self-checked packaging record only: r35 kernel 787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464 (55721984 B), args build-tag=nuwa-r35 with aks=1 and disable-watchdogd=1, seed 2c95d15b...8110 (apsb_xid 16), CHMH e767b49d...4b94, derived ADT 5a7df557...7ddc (13640 B), payload 90a5447c...121e, outer c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed reproduced by the audit; authentication NOT REACHED and device_release false. r35 was not written to any partition.

## 29. packaging

- Kind: `host`
- Original local reference: `out/nuwa-boot-payload-write-20261115-01/ROLLBACK-r34.md`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

Read-only review of the write ledger and rollback notes after the r34 write; no device command.

**Recorded result:**

self-checked ledger review: vendor_boot_a currently carries r34 46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e and boot_a still starts with the r4 loader 692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5; the file lists every earlier payload with its hash for rollback, the stock boot_a/vendor_boot_a images, and the known ABL rejection mode. It also states the limit that a rollback restores only the boot payload: any userdata tail-window write done by these kernels has no backup and no inverse operation.

## 30. packaging

- Kind: `host`
- Original local reference: `out/ios16-system-trust-bundle-20261115-r1/inputs.json`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

WSL Ubuntu-22.04 device repo: /home/wh1stl3/.local/bin/python3.11 -B scripts/build-ios16-system-trust-bundle.py --output out/ios16-system-trust-bundle-20261115-r1

**Recorded result:**

self-checked host only: the two donor modules are re-emitted unchanged (OS 2760 entries / Cryptex1,SystemTrustCache 61 entries) into bundle eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3 (67764 B); DarwinBoot's ValidTrustCaches parser was compiled from the pinned source and accepted the two-module and deployed single-module forms while rejecting eight malformed fixtures (raw IM4P, truncated, zero count, misaligned and header offsets, bad hash type, duplicate cdhash, module version). No Apple personalisation or runtime trust acceptance is claimed, and nothing was written to the device by this run.

## 31. packaging

- Kind: `source`
- Original local reference: `out/pmap-ret-memory-ranges-verifier-20261111/result.json`

**Recorded result:**

Historical initial range FAIL, now withdrawn after correction.json plus native-flow/result.json final static PASS; original evidence preserved, not rewritten. Initial failure concerned incorrect __BOOTDATA reference, not a proven collision. Correct segment VA0xfffffff007ac0000-0xfffffff007b08000, __data0xfffffff007af0000-0xfffffff007b08000; old erroneous interval not propagated. result.json has artifact hashes/relative_intervals_hex/nonoverlap=true/absolute_W_observed=false, no status/command/exit; do not fabricate fields. Its prior pending status and historical outer-record snapshots no longer describe current acceptance. Final A-E closure and current device-authorization boundary in docs/owner-pmap-ret-range-acceptance-20261111.md; GOP/EFI map resource conditions retained.

## 32. diagnostics

- Kind: `host`
- Original local reference: `out/nuwa-r35-20261119/build.py`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

WSL Ubuntu-22.04 device repo: /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-r35-20261119/build.py (kernel into the same directory), then out/nuwa-r35-20261119/verify_r35.sh.

**Recorded result:**

self-checked build-side evidence only: the kernel compiles from r34's sources plus the abnormal-exit ring (boot_progress_exit keeps the last four exits with a non-zero status or os_reason namespace, row 0 renders EXk <comm6> <sig>:<ns>:<code>, the console prints pid/status/ns/code/nprocs and the AKS counters), the title with the build tag moves to row 1, and the verify script's string/relocation assertions pass. No device command, no flash; the SIGTRAP values themselves are not in this file.

## 33. diagnostics

- Kind: `host`
- Original local reference: `out/nuwa-r21-20261118/PLAN.md`
- Recorded revision: `06e62d3e1f2230a1d70bec38914bc5d96c19279e`

**Recorded command:**

Windows host, read-only review of the r19/r20 screen photos plus the renderer geometry; no device command, no build of the upstream package.

**Recorded result:**

self-checked analysis only: the page writes 18x42 px cells at depth 32 with the vinfo rowbytes, only three rows have writers, ext and touch overlays return early on this panel, and a 15 s full repaint rewrites every cell, so the missing thin strokes are lost after the store (DPU/DSI/panel or fb mapping) rather than by the renderer; it also records the rows 0-8 panic-safe band, the bind deduplication and the stop-on-panic rule that later rounds rely on. The glyph self-test pattern is the discriminator, and no photo of it has been analysed yet.

## 34. diagnostics

- Kind: `host`
- Original local reference: `out/nuwa-observe-20261115-r1/REPORT.md`
- Recorded revision: `9e0be264fb2689a96c5b7ba1edc563a4e5adb049`

**Recorded command:**

WSL Ubuntu-22.04 device repo: /home/wh1stl3/.local/bin/python3.11 -B out/nuwa-observe-20261115-r1/build.py, then out/nuwa-observe-20261115-r1/selfcheck.py

**Recorded result:**

self-checked host only: kernel b1029f3d32d1db3ae0bca1b85a665a6758c608ee9f9a5aaffbc55589f83d3764 (55545856 B) recompiles only bsd_init.o/startup.o/kern_exec.o/systemcalls.o; band 3 is cyan at [3/16,4/16) after process_signature returns 0 for initproc, band 15 orange at [15/16,16/16) on the first initproc unix_syscall; the band painter is bounded stores into vinfo.v_baseaddr with no lock/allocation/call-out. Control package nuwa-ufs-apfs-root-chmh-20261115-r8obs carries the single-module trust bundle. No device action in this run.

## 35. diagnostics

- Kind: `device`
- Original local reference: `out/pmap-ret-run-pmap-ret-20261111-r4/boot-complete.json`
- Recorded revision: `63769f208783769f7fa4ec5cffc14d3eba37b21a`

**Recorded command:**

scripts/run-pmap-ret-once.py --phase boot --run-id pmap-ret-20261111-r4 --authorize-boot (host interpreter not recorded in the retained JSON; exact child argv and returncodes in the same run event-*.json); not rerun for this records update

**Recorded result:**

Stage 2 (parent-reported independent command review PASS): candidate vendor_boot staged with device-side SHA256 a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0, slot set to b and read back b, one fastboot boot of the fixed r4 loader .cache/boot-stage12-v4-r4.img exited 0 (Sending 1460 KB OKAY / Booting OKAY / Finished). The user then observed DIAG: PMAP initializer normal epilogue reached; STOP; the boot claim is consumed and no continue/reboot/retry followed. No recording file exists for independent visual confirmation; the line does not prove the original RET ran, nor authentication/stage5. Area level unchanged.

## 36. diagnostics

- Kind: `device`
- Original local reference: `out/pmap-ret-run-pmap-ret-20261111-r4/restore-complete.json`
- Recorded revision: `63769f208783769f7fa4ec5cffc14d3eba37b21a`

**Recorded command:**

scripts/run-pmap-ret-once.py --phase restore --run-id pmap-ret-20261111-r4 --authorize-restore; host readback independently recomputed by the review; not rerun here

**Recorded result:**

Stage 3 (parent-reported review PASS): the device returned to slot A and read back A, Android reported boot_completed=1, slot _a and uid0; B was restored from this round stock backup 100663296 B SHA256 493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad, the whole-partition hash matched restore-readback.img, r4 staging was removed and the stock backup/evidence retained. No runtime/authentication/stage5/device-ready claim; area level unchanged.

## 37. packaging

- Kind: `source`
- Original local reference: `.cache/fw-mask-719afa67-20261110/RESULT.md`

**Recorded result:**

Firmware719afa67e3aebbf058c2a8beff4c801057fb2b20 isolated environment final self-checked/BLOCKED: fixed Mu_Basecore cfb93724a06ff86ff5ba971413368a7809ee42a5 and edksetup acquired, then brotli e230f474b87134e8c6c85b630084c612057f253e fetch128 (TLS/early EOF), preparation wrapper1; task ended, not running. No BaseTools/EDK parse/AutoGen/build or device validation. Retry budget consumed; only read existing result/logs pending new decision. Existing dirty submodules retained.

## 38. packaging

- Kind: `device`
- Original local reference: `.cache/ota-preflight-20261110-201601/USER-SELECTED-FORMAT-BOOT-RESULT.md`
- Recorded revision: `8ae344cc05879a27cf77b5103e30b2ca51a6d41d`

**Recorded command:**

Historical authorized general task: targeted twrp format data; readback-installed-rom.ps1 and super localization; sibling POST-MANUAL-INSTALL-RESULT.md/SUPER-DIFF-RESULT.md. Not rerun here.

**Recorded result:**

Historical checkpoint, superseded by current reboot/recovery entry above: manual TWRP non-root ZIP install,59/60 readbacks matched with super mismatch; user accepted Format Data without super rewrite. Built-in userdata F2FS/associated metadata RC0, /data RW, A slot, no agent reboot after disconnect; user then reported Launcher, not machine boot_completed/version evidence. userdata Android, no surviving Apple root; future iOS UFS restoration needs fresh authorization. BNCH gate/area levels unchanged.

## 39. packaging

- Kind: `device`
- Original local reference: `.cache/media/stage5-panic-20261110-183907/execution.log`
- Recorded revision: `73824c65788a7c811f68ad77ef411e57ec032337`

**Recorded command:**

Prior authorised stage5 run, parent-delivered observation and photo review; no device command rerun in this host-only task

**Recorded result:**

Old vendor_boot SHA256 998d284ad4959aebdb1a7f26d161eea5b2a49fe169264a843f19708ec522bea5: no automatic reset; photo confirms failed to get mix-n-match policy: 2. Panic-screen park expected. AppleImage4 required /chosen property absent (ENOENT=2), frame fffffff0046e9f60 reviewed. Supports kernel_bootstrap_thread -> mac_policy_initmach -> KLDBootstrap loadSecurityExtensions -> OSKext start -> AppleImage4 init, not stage5. Parent reports 18:54:23 return A/TWRP current/active=0. Local media visual-frames/text-real.png stays ignored; area levels unchanged.

## 40. packaging

- Kind: `device`
- Original local reference: `.cache/media/stage4-console-after-20261110-180641/execution.log`
- Recorded revision: `982e92e67c0e266987a786865f53e9cd120a159c`

**Recorded command:**

Recorded prior authorised console-after round: .cache/run-console-after-20261110.ps1 and .cache/return-a-console-after-20261110.ps1; not rerun this host-only task

**Recorded result:**

Prior commands rc=0, self-checked log: nuwa identity, only vendor_boot_b written/read back SHA256 3f46e8a8dd213babec939e081d3273d17a03023e4fab107e22b07922d625a02a; one r4 boot. User reports three bars then approximately six-second reset: console returned only. Log lines 143-155 record return to A/TWRP current/active=0, not newly queried. No normal-boot/platform acceptance claim.
