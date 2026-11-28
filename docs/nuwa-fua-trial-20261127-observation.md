# nuwa FUA-permissive disposable Data outer — 2026-11-27 flash observation

状态：设备写入已执行一次，主机侧 self-checked。刷写轮**未重启、未启动**，刷后设备
留在 fastboot；2026-11-27 18:09:40 另有用户授权的单次重启与 200 秒只读在场采样，
18:36 另有授权重刷一次 FUA outer（不重启），随后用户按「拔 USB + 长按电源进菜单」
启动该实验包并拍照，均见文末追加节（照片不入 Git，只记文件名与 SHA-256）。刷写轮
只验证身份、产物哈希与 `vendor_boot_a` 单次刷写，不构成启动验收、文件系统挂载、
介质持久性或认证证据。

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

## 2026-11-27 18:09:40 授权重启与 200 秒在场采样（追加）

状态：用户当轮授权启动一次——只执行一次 `fastboot reboot`，随后 200 秒只读采样
adb/fastboot 是否出现。本轮未刷写、未切槽、未初始化，未执行任何 adb 写/挂载命令。
主机侧 self-checked；屏幕内容由用户拍照，本节不写屏幕结论。

### 重启前门禁

- `fastboot devices` 有两台：另一台 `product=enuma`（未操作，采样期间其 serial 始终
  可读）；唯一 nuwa 命中并固定 serial（不入库）。
- nuwa `product=nuwa`、`current-slot=a`、`is-userspace=no`、`slot-count=2`。三项要求
  全部满足后才执行重启；身份或槽位不符即停的约定未触发。

### 唯一一次重启

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
exit 0
```

重启时刻 `2026-11-27T18:09:40.790+08:00`（UTC `2026-11-27T10:09:40.790Z`）。只执行
一次，无重试。

### 200 秒采样时间线

每 10 秒只读执行一次 `fastboot devices` 与 `adb devices`，共 21 个采样点（0–200 s）。
原始输出（serial 已脱敏）在 `out/nuwa-fua-reboot-20261127/reboot-and-sample.log`
（Git 忽略）。

| 采样 | 相对重启 | 本地时刻（+08:00） | nuwa 在 fastboot | adb 设备 |
| --- | --- | --- | --- | --- |
| 00 | 0.0 s | 18:09:40.808 | 否：serial 不可读，同一行显示 `????????????` | 无 |
| 01 | 10.0 s | 18:09:50.799 | 是 | 无 |
| 02 | 20.0 s | 18:10:00.794 | 是 | 无 |
| 03 | 30.0 s | 18:10:10.808 | 是 | 无 |
| 04 | 40.0 s | 18:10:20.800 | 是 | 无 |
| 05 | 50.0 s | 18:10:30.806 | 是 | 无 |
| 06 | 60.0 s | 18:10:40.803 | 是 | 无 |
| 07 | 70.0 s | 18:10:50.795 | 是 | 无 |
| 08 | 80.0 s | 18:11:00.814 | 是 | 无 |
| 09 | 90.0 s | 18:11:10.792 | 是 | 无 |
| 10 | 100.0 s | 18:11:20.800 | 是 | 无 |
| 11 | 110.0 s | 18:11:30.804 | 是 | 无 |
| 12 | 120.0 s | 18:11:40.793 | 是 | 无 |
| 13 | 130.0 s | 18:11:50.811 | 是 | 无 |
| 14 | 140.0 s | 18:12:00.815 | 是 | 无 |
| 15 | 150.0 s | 18:12:10.796 | 是 | 无 |
| 16 | 160.0 s | 18:12:20.792 | 是 | 无 |
| 17 | 170.0 s | 18:12:30.795 | 是 | 无 |
| 18 | 180.0 s | 18:12:40.798 | 是 | 无 |
| 19 | 190.0 s | 18:12:50.795 | 是 | 无 |
| 20 | 200.0 s | 18:13:00.804 | 是 | 无 |

- 采样 00 在重启命令返回后 0.018 s：`fastboot devices` 不再列出 nuwa serial，原行
  变为 `????????????`；同一时刻 enuma 的 serial 仍正常显示。
- 采样 01 起直到 200.0 s，nuwa serial 每个采样点均恢复出现；`adb devices` 21 个点
  均无设备。
- 追加只读核对 `2026-11-27T18:13:48.082+08:00`：`fastboot devices` 仍列出 nuwa；
  `product=nuwa`、`current-slot=a`、`is-userspace=no`；`adb devices` 仍无设备。

### 判读边界

- 采样 00 的 `????????????` 是 fastboot 在 USB 重新枚举、序列号暂不可读时的占位行，
  表明重启瞬间 fastboot 稳定态被打断；10 秒内 nuwa 又回到 fastboot 并持续到 200 秒。
- 采样间隔 10 秒，不能据此区分“bootloader 仅复位 USB 后留在 fastboot”与“尝试启动后
  回落到 fastboot”，也不能给出离开 fastboot 的确切时长。
- 本节不提供启动、屏幕、内核日志或用户态证据；屏幕内容由用户拍照。下一次设备动作
  仍需单独授权。

## 2026-11-27 18:36 重刷 FUA outer（不重启）

状态：用户当轮授权再刷一次 FUA 包做启动试验，**明确不执行 reboot**；本轮只写
`vendor_boot_a`。主机侧 self-checked；屏幕内容由用户拍照，本节不写屏幕结论。

### 门禁与产物

- `fastboot devices` 两台：一台为 enuma（未操作）；另一台为唯一 nuwa
  （serial 不入库）。
- 四项各连查 2 次，共 8 次全部成功、exit 0：`product=nuwa`、`current-slot=a`、
  `is-userspace=no`、`partition-size:vendor_boot_a=0x6000000`。
- FUA outer：`out/nuwa-fua-trial-20261127-package/vendor_boot.img`，100,663,296 B，
  SHA-256 `b5d1b9f1d75da5ac2c37f9ee52d570f3e7afb40b734189f52d05efa11c91c97e`，一致。

### 唯一一次刷写

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [  2.262s]
  Writing 'vendor_boot_a'             OKAY [  0.035s]
  Finished. Total time: 2.329s
```

- 开始 `2026-11-27T18:36:29.272+08:00`，结束 `18:36:31.756`，**exit 0**；无 AVB
  footer / `partition size: 0` 警告。
- 未执行 `reboot`，未切槽，未刷其他分区，未初始化，未写 `userdata`/`metadata`。
- 刷后只读复核（18:36:47）：nuwa 与 enuma 仍在 fastboot，`adb devices` 无设备；
  `product=nuwa`、`current-slot=a`、`is-userspace=no` 不变。

### 用户观察（主控转述，非独立验证）

- 拔掉 USB 时长按电源，可进入 UniXNU 菜单。
- 接 USB 时重启，10 秒内回落 fastboot。

这两条与此前「重启瞬间 USB 重枚举、10 s 内回 fastboot」的采样一致，同时说明设备
并非完全无法启动到 UniXNU：差别在 USB 是否连接及进入方式（拔线 + 长按电源）。
具体机制未证（USB 存在时 ABL/UEFI 的启动选择、键值检测或 UEFI 侧 USB 处理均未
排查）。

### 给用户的下一步提示（本轮不执行）

拔掉 USB，长按电源进入 UniXNU 菜单，选 XNU 启动；在 60/110/180 秒各拍照一次，
之后重新插线。屏幕与菜单内容由用户观察，本轮不做判读。

### 边界

- 本轮只证明 bootloader 接收并写入 `b5d1b9f1…` outer；无回读，不证明盘上字节。
- 不提供启动、菜单、panic 或用户态证据；「拔线可进菜单」为用户观测，未独立验证。
- 下一次设备动作（启动、采图、插线）由用户手动完成；本轮不 reboot。

## 2026-11-27 启动试验：FUA 实验包出现 Apple logo（追加）

状态：用户在已刷 FUA 实验 outer（`b5d1b9f1…`，见上文 18:36 重刷）的设备上，按
「拔掉 USB → 长按电源进 UniXNU 菜单 → 启动 XNU」进入系统并拍照。屏幕字段由**主控
转述用户照片**，照片不入 Git，本节只记文件名与 SHA-256。本轮**不接设备、不刷写**，
未取串口或内核日志，未做独立 verifier 或 vision 复核。

### 这是实验包行为（不得外推）

- 本轮启动的是 `NUWA_DISPOSABLE_FUA_PERMISSIVE=1` 的 trial build：`doAsyncReadWrite()`
  接受 `kIOStorageOptionForceUnitAccess` 位并走普通读写路径；`doSynchronizeCache()`
  只复查既有 overlay 会话后返回成功。它**接受 FUA 位但不承诺耐久性**，UFS 命令仍是
  既有非 FUA `WriteVolatile`。
- 默认构建仍返回 `kIOReturnUnsupported`；生产 `Provider<CandidatePort, false>` 与
  `fuaProvenLocked() == false` 未变。本结果只描述该实验包。

### 启动条件（用户观测）

- 拔掉 USB，长按电源进入 UniXNU 菜单后启动 XNU，可看到下述画面。
- 接 USB 时 reboot 会在 10 秒内回落 fastboot（用户观测；具体机制未证）。

### 照片与屏上字段（主控转述）

照片在工作区外 `nuwa/media/`，不入 Git；下表只记文件名与 SHA-256。

| 文件 | 相对时间 t | SHA-256 |
| --- | --- | --- |
| `fua-1.jpg` | 60 s | `2fe0da880428094d04a04c096058ed973442e758e4f9e393081d42da5eb86c29` |
| `fua-8.jpg` | 494 s | `55c95547f15547889ee3cee08bee3127307aa317db50d2075f80b874f2d7c7ea` |
| `fua-14.jpg` | 692 s | `6fe5b7d76472c937b5900136fee30f15187fd7f94c364827263faf4762348a39` |

t=60 s（`fua-1.jpg`）：

```text
DATA mnt st=4 err=0 ro=0 dev=1000002 seed=1 devpath=/dev/disk1s1 pub=1 serr=0
PID1 st=2(RU) comm=launchd init=1 nprocs=1
SYSOS st=6 err=0 dev=/dev/disk3s1 rauth=1 uni=1 rv=1 mg=ok ak=2/0
amfi=1 cs=0x0
launchd exec process signature accepted
DATA hdr=9 gpt=0/0 lba=36bc0f9 | pres=30 ld=843 wr=2 sy=0 er=0 st=2
Process exits: total=2 nonzero=0
```

t=494 s（`fua-8.jpg`）：Apple logo 可见。

- `crashes=4 exits=10`
- EXIT assistantd `status=6 sig=6`
- EXIT containermanagerd `status=6 sig=6`
- EXIT ScreenTimeAgent `status=6 sig=6`
- `PROC n=110 SB=25 bb=54 lsd=91 lk=69 cm=61`
- `PIX bk=0 so=6 chk=2`

t=692 s（`fua-14.jpg`）：Apple logo 可见。

- `crashes=52 exits=172`
- EXIT assistantd `status=9 sig=9`
- EXIT mobileactivationd `status=9 sig=9`
- EXIT findmydeviced `status=9 sig=9`
- CRASH ScreenTimeAgent `status=6 sig=6`
- CRASH privacyaccountingd `status=5 sig=5`
- `LOAD user=35% sys=64% idle=0%`

### 对照（FUA 放行前）

关闭 FUA 放行时（默认行为，拒绝 FUA）：`tzinit` 约 112 秒以 45 退出并 panic、
`sb=never`、从未见 Apple logo（主控转述的历史观察，仅作对照）。

### 已证（仅限该实验包 + 本次启动条件）

- `tzinit` 在采样范围内不再以 45 退出：t=60 s 的退出统计为
  `Process exits: total=2 nonzero=0`，且到 t=692 s 的采样记录中没有 45 退出项。
- Data 挂载 `pub=1`（t=60 s 的 DATA 行）。
- 系统运行到 ≥692 秒：t=692 s 仍有 `LOAD` 与进程计数。
- Apple logo 出现：t=494 s 与 t=692 s。

### 未证

- 锁屏/桌面及可交互：三张照片中没有相应记录，不能据此判定是否出现或可操作。
- 文件级持久：没有写入后重启再读的证据。
- 断电耐久：FUA 位未下传介质，本包不承诺耐久；无断电或冷启动测试。
- 认证：仍 **NOT REACHED**（实验 CHMH、空 runtime trust cache、initproc exec 策略
  跳过均未改变）。

### 用户态退出（只记录，不归因）

本节只按主控转述记录进程与信号，不推断退出原因或根因：

- t=494 s：assistantd、containermanagerd、ScreenTimeAgent，均 `status=6 sig=6`。
- t=692 s：assistantd、mobileactivationd、findmydeviced，均 `status=9 sig=9`；
  ScreenTimeAgent `status=6 sig=6`；privacyaccountingd `status=5 sig=5`。
- 同期累计 `crashes=4 exits=10`（t=494 s）与 `crashes=52 exits=172`（t=692 s）。

### 边界

- 屏幕内容全部来自用户照片的主控转述；未做独立 OCR/vision，未接设备，未取日志。
- 相对时间 t 以用户拍照记录为准，起点未独立校准；三个采样点之间的事件不可见。
- 照片与哈希只用于对应证据，照片不入 Git；本结果不改变显示验收、持久根卷、认证或
  交互目标的任何状态。
