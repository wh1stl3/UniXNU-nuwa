# nuwa FUA-permissive disposable Data outer — 2026-11-27 flash observation

状态：设备写入已执行一次，主机侧 self-checked；**未重启、未启动**，刷后设备留在
fastboot。本轮只验证身份、产物哈希与 `vendor_boot_a` 单次刷写，不构成启动验收、
文件系统挂载、介质持久性或认证证据。

## 授权与审查

- 用户当轮明确授权：刷入 FUA 实验包，**不重启**，刷后留在 fastboot。
- `deep_reviewer` 终审 **PASS WITH CONDITIONS**
  （session `ses_de49ff134ffepX3A6SfemOc7pJ`，由主控转述）。条件清单未在本工作区
  留档，本轮不替审查补充、缩减或解释条件。

## 设备身份与门禁

- 重新识别时有两台 fastboot 设备：一台 `product=enuma`（未操作），一台
  `product=nuwa`（唯一 nuwa，本轮固定使用，serial 不入库）。
- nuwa `product=nuwa`、`is-userspace=no`、`current-slot=a`、`slot-count=2`。
- `partition-size:vendor_boot_a=0x6000000` = 100,663,296 B，满足候选长度。
- 四项门禁全部满足后才执行刷写；身份或槽位不符即停的约定未触发。

## 产物哈希

输入路径与 `docs/nuwa-fua-trial-20261127.md` 记录一致：
`out/nuwa-fua-trial-20261127-package/vendor_boot.img`。本轮在主机重新实算 outer
长度与 SHA-256，与记录逐字节一致：

| 产物 | 字节 | SHA-256 / SHA-384 |
| --- | --- | --- |
| outer `vendor_boot.img` | 100,663,296 | `b5d1b9f1d75da5ac2c37f9ee52d570f3e7afb40b734189f52d05efa11c91c97e` |
| kernel `kernel.macho` | 52,207,616 | `b414fcf6648c61be85015712d48ca610ad0a96314d691066c423ef8d8ca01cad` |
| FAT readback | 67,108,864 | `f9f96207d2c7ef2670e7977e9fd98cb236433705a329ab8a6a7d3f411daf2e2a` |
| CHMH (experimental) | — | SHA-384 `5c730ebffe45b2ef1f47226bb4d48e7a9f9d5fb10fef33742c44c3cae3c42eabe2ec7a4d87d562633796f02b57317436` |
| ADT `kernel.macho.adt` | 13,680 | `05db501aa06408456d557ede61c467d68b2bd53dea75cbb5eecb4d1c4975a95b` |

包内 args 602 B、seed/trust 未变、FAT free 11,021,312 B（见包记录与 audit）。
CHMH 为实验身份，非认证。

## 编译开关

`NUWA_DISPOSABLE_FUA_PERMISSIVE`（默认 0）。本轮包是该开关为 1 的 trial build：

- `doAsyncReadWrite()` 的 `kIOStorageOptionForceUnitAccess` 分支不再返回
  `kIOReturnUnsupported`，而是走普通读写路径并递增
  `nuwa_disposable_fua_requests`。
- `doSynchronizeCache()` 在 disposable store 健康时先经
  `native_ufs_store_order()` 复查既有会话，再返回 `kIOReturnSuccess` 并递增
  `nuwa_disposable_flushes`；这不是 UFS cache flush。
- 屏上现有 panic-safe DATA0 行追加 `fua=N flush=N`，trial build 另加
  `FUA-EXP-nodur`；改的只是既有行文本，没有新增绘制路径。
- 默认构建、生产 `Provider<CandidatePort, false>` 与
  `fuaProvenLocked() == false` 未变；被接受的 FUA 位没有转成介质 FUA，本包不声称
  介质持久性。

## 刷写

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [  2.266s]
  Writing 'vendor_boot_a'             OKAY [  0.036s]
  Finished. Total time: 2.334s
exit 0
```

只写一次，无重试。未执行 `reboot`，未切槽，未刷其他分区，未初始化，未写
`userdata`/`metadata`。

## 刷后设备状态

- `fastboot devices`：nuwa 与 enuma 两台仍在 fastboot；nuwa 未离开 fastboot。
- nuwa 复读 `product=nuwa`、`is-userspace=no`、`current-slot=a`，与刷前一致。
- 本轮未做 `fastboot fetch` 或分区回读；bootloader 只给出 Sending/Writing 确认。
  设备盘上 `vendor_boot_a` 现为本轮 outer `b5d1b9f1…`；`boot_a` 与其余分区未动。

## 边界

- 刷写成功只证明 bootloader 接收了镜像，不证明镜像可启动、屏幕可见或运行时正确。
- 本轮没有启动候选，不能报告 DATA0、`fua/flush` 计数、`FUA-EXP-nodur`、PID1、
  SpringBoard、panic 行或任何屏幕结果；这些字段仍未在实机显示。
- UFS 写入仍是既有的非 FUA `WriteVolatile`；RamBlock 层接受的 FUA 位不构成介质
  缓存刷新或断电持久性证据。
- SB0/disposable 写门、挂载状态与认证均未改变；认证仍 **NOT REACHED**。
- 下一次启动需要单独授权；刷写轮不提供快速启动或冷启动证据。
- 原始命令输出只留在 `out/nuwa-fua-trial-flash-20261127/`（Git 忽略，serial 已脱敏）。
