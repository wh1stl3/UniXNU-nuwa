# nuwa SystemGroup seed result — 2026-11-22

## Identity and evidence sources

- Branch `display/20h392-dsp-diag`; record base `a2cd623d59a09157e4c7925d2114c0e526dbadf1`; preceding diagnostics and observation history `066e67b..a2cd623`. This is source history, not a proven payload-to-commit mapping. This is the subsequent documentation-only increment.
- Outer SHA-256 `6194d27d6c25ae62497ed1135d4480567a13bebdf37c4ab4b8ba87fbffea396c`; kernel SHA-256 `22af086c04d463f9be74ae302a180fa20c31346ee124a32dcd1791e89595ddc1` (same as previous); encoded seed SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`; CHMH SHA-384 `583b57ae…c740` (supplied abbreviation).
- **Device readings:** parent-supplied readings from this boot, not independently observed or rerun by this author. **Host static analysis and independent seed check:** supplied by parent, not rerun here. **User observation:** parent-relayed stationary white Apple logo. No image, video or screenshot included. Prior record: [migration](nuwa-mobileactivation-migration-20261122.md).

## Seed-only change

Only Data seed contents changed: 34 identifier-named directories were precreated under `private/var/containers/Shared/SystemGroup/`, without MCM metadata plists. `systemgroup.com.apple.mobileactivationd` additionally has `Library/ucrt`, `Library/dcrt` and `Library/internal`. Permissions are an **experimental assumption**, not an MCM contract: container roots `0:0/0755`, `Library` and descendants `501:501/0755`.

The parent reports independent host validation of 104 added directories, Data top-level count `30→30`, `db` `31→31`, Preferences `7→7`, and unchanged `keybags/systembag.kb` bytes. This is the reported scope of that check, not a claim of full filesystem equivalence.

## 已证 — reported device readings and host analysis

- Previously mobileactivationd repeatedly SIGTRAPed about once per 20 seconds (`status=5 sig=5`); at `t=414s` and `t=754s` this candidate showed `crashes=0`, and the XR row no longer showed it. The reported stability observation covers 754 seconds, with readings at those two times.
- The prior host static attribution identifies migration path resolution failure at `0x100029a88` → `Failed to copy UCRT path.` → `0x1001bf35c` (`Migration failed.`) → `_os_crash` → `brk #1` at `0x1001bf3bc`. It is static attribution, not a directly measured complete runtime PC or proof migration completed.
- Other readings for this boot: `PROC n=141 SB=25 bb=54 lsd=93 ld=1 lk=69 cm=61`; `SC n=12 r=0 o=12`, `SC +0`; `LOAD user=36% sys=63% idle=0%`; `UFS read=99ms reqs=69`.

**`crashes=0` 只证明该候选启动条件下未复现原周期性失败，不证明 MCM 认领成功、迁移真正完成或认证通过。** Authentication remains NOT REACHED.

## 未证

- Whether MCM actually claimed the 34 directories: no metadata plist was provided, and MCM has an orphan-deletion routine containing `Deleting orphaned data missing a metadata file at: %@`.
- Whether the experimental ownership and mode satisfy the MCM contract.
- The cause of SpringBoard's blockage: `SC n=12 +0` remains and the user reports a stationary white Apple logo. Interactive operation and persistence remain unproven.

## 已推翻 — new counterevidence

The serial inference “periodic mobileactivationd crashes cause SpringBoard not to advance” does not hold as a sufficient explanation: after the recurring crash was no longer observed, SpringBoard still submitted no frames in the reported observation. This does not exclude other relationships or establish the blockage cause.

## 新观察 — unexplained

- `EXIT p164 xpcproxy status=4e00 sig=0 exit=78`: `78` is `EX_CONFIG`, indicating a service failed to start due to configuration; the service name is unknown and the exact underlying problem is not established.
- At `t=414s`, `sys=90%`; at `t=754s`, `sys=63%`. The spike was transient; it does not establish that MCM was processing directories without metadata.

No build, device command, independent verification rerun, or media ingestion was performed for this record. Record: self-checked; device and independent host results are parent-reported.
