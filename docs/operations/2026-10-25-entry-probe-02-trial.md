# 入口探针02 实机试验：MMU 已开、进入 arm_init

2026-10-25 00:37–00:43（北京时间）。`main` 分支。单次 `fastboot boot`，未 flash/erase/改槽位。

## 结果（一句话）

**六条色带全部出现**：绿（DarwinBoot EBS）、蓝（入口）、黄（页表生成后）、品红（BCM 专写后）、**青（MMU 开启后）**、**白（进入 `_arm_init`）**。这是本项目第一次在真机上越过 MMU 开关并进入 C 入口。

## 证据

| 项 | 值 |
| --- | --- |
| 镜像 | `af5862be01126c5cf67e13b3fb36a9a5e8be3d6f028271f49ebc088d03876031`，70,266,880 B |
| 内核 | `8515068dcd6bd699a4301109b76b80022fb07120e6167b65b6169d52aeffcb6a`（v5，24 补丁） |
| ADT | `ed7235cbd4bebe1e38f4c9ef73ad727df3b5cfb5fb20ecab56aa75fb1468f9f3` |
| 菜单标识 | `XNU ENTRY PROBE 02 - BLUE YELLOW MAGENTA CYAN WHITE`（原图可见，排除与旧包混淆） |
| 启动 | 2026-10-24T16:37:52Z 起，ACK 16:38:10Z，180 秒 USB 观察至 16:41:10Z；`adb_device_count` 全程 0（nuwa 不在 Android） |
| 原图 | `out/trial-evidence/entry-probe-02/screen-01.jpg`，323,957 B，SHA256 `7030b14c8e82f1a63525f6d2d51b1632112762021ed8f4bd6791b0231ebeafac` |
| 判读 | `reports/xnu-entry-probe-trial/2026-10-25-01/screen-evidence.json` |
| 恢复 | 16:43:19Z 原厂 boot 临时加载，Android `boot_completed=1` |
| 恢复后 | 16:43:30Z 唯一 nuwa/kalama、槽_a，boot_a `ef558db2`、vendor_boot_a `5ad2a9dc`、init_boot_a `19e95d95` 与 preflight **逐字节相同**（`three_partition_hashes_unchanged: true`） |

## 每条带证明了什么

- **青（y=736）**：钩子在 `msr sctlr_el1, x0` 之后的 `isb` 上，且 v5 已改成**先回放 isb 再画带**。因此青出现 = SCTLR 写入已同步完成，**并且这条带本身是在 MMU 开启状态下、经由 pre-MMU 安装的 1 GiB 设备恒等映射写进 framebuffer 的**。这条同时证明三件事：MMU 真的开了、V=P 恒等映射覆盖到内核执行区、设备属性写屏可用。
- **白（y=832）**：钩在 `_arm_init` 第一条指令，该地址属于 KVA 区间。白出现 = **TTBR1 翻译与取指可用、控制权已进入 C 入口**。

这两条把此前最大的分叉（"MMU 到底开没开"）答掉了，并且顺带否掉了"页表属性/MAIR/TCR 配置错误导致开不起来"这一整类猜测。

## 必须写清的边界

1. **没有红条不等于没异常**：早期异常向量挂在物理 VBAR 上；MMU 之后 VBAR 已是内核 KVA 向量，那一阶段的异常我们抓不到。
2. **内核没有继续到 iOS**：屏幕上固件菜单被重绘、倒计时重新开始，说明内核在 `arm_init` 之后返回或复位回固件。**具体停在 `arm_vm_init`/pmap 的哪一步未知**。是返回、panic 复位还是看门狗复位，也未验证。
3. **菜单倒计时会再次拉起同一份包**：内核返回后固件菜单重新计时，可能又启动了一次同一内核。这不是第二次 `fastboot boot`（命令只发了一次，ACK 一次），但"单次启动"这一条以后要按"fastboot 动作一次"与"固件自行重入"分开记。
4. 本轮**未**设备份/恢复以外的任何写操作；`_verified`、板值、认证/AMFI 均未动。

## 下一步（按收益排序）

1. **往 C 里打点**：把钩子从汇编尾部推进到 `arm_vm_init` / `pmap_bootstrap` / `kernel_bootstrap` 等函数首指令，用同一条"探针页 + 快照"机制继续画带，把断点从"arm_init 之后"收敛到具体函数。
2. **让 MMU 后的异常自报**：在 magenta 钩子里把 `VBAR_EL1` 换成探针页的**恒等地址**（PA 形式），并在探针页放自己的向量，把 ESR/ELR/FAR 画出来。现在"MMU 后能写屏"已有实机证据，这条做起来风险显著降低；它能把"返回/复位"变成"具体 fault 地址"。
3. 只有在前两条都拿不到信息时，才考虑串口或 QEMU（并先验证同源 QEMU 对 T0SZ=26 的处理）。

## 复现命令

```sh
python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-02.json
python -B scripts/trial-v4-firmware.py launch --package reports/xnu-first-entry/entry-probe-02.json \
  --preflight reports/xnu-entry-probe-trial/2026-10-25-01/preflight.json \
  --evidence reports/xnu-entry-probe-trial/2026-10-25-01/launch.json --observation-seconds 180
python -B scripts/trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-02.json \
  --evidence reports/xnu-entry-probe-trial/2026-10-25-01/recovery.json
python -B scripts/record-nuwa-trial-state.py --before reports/xnu-entry-probe-trial/2026-10-25-01/preflight.json \
  --output reports/xnu-entry-probe-trial/2026-10-25-01/postcondition.json
```
