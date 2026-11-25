# nuwa UFS 控制器 re-init 可行性（2026-11-25）

**只能部分实现：已经实现主机顺序模型和候选拒绝路径；没有启用实机 re-init。**
没有证据排除旧 DMA 在 HCE/PHY 状态改变后仍到达，没有可信的新域授权，
也没有可替代 Xiaomi variant callbacks 的板级电源/时钟/ICE 合同。停旧请求、
DB=0 或 HCE=0 不提供 DMA fence。推入实机 HCE 操作会破坏现有隔离合同，
因此不增加硬件写、重新配置、解绑/复用旧 DMA 或自动重试。

参考：[MiCode/Xiaomi_Kernel_OpenSource，fuxi-t-oss `7fad87dc178d09489b74a714e4a525d56f546855`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/7fad87dc178d09489b74a714e4a525d56f546855/drivers/scsi/ufs)；GPL，只核对顺序，无源码移植。
retained 参考为 r8 构建锁定的 `NativeUfs.cpp:274–294`（4 KiB HC 映射；
保留 firmware domain）、`PreservedNop.h:68–128`、`CombinedRead.h`。

## 寄存器与读回边界

| 模型阶段 | 寄存器与应核对的证据 | 当前 retained 边界 |
| --- | --- | --- |
| HCE stop/start | HCE `0x34` bit 0；stop 验证读回 0；start 须识别可信的初始化过渡，不把写入后的首个 1 当完成。`ufshci.h:27–50`、`ufshcd.c:4556–4641`。源码 `retry_outer=3` 是初次之后最多三次额外尝试；模型不复制重试。 | HCE 可读；当前没有可信地执行 HCE 写的合同。`ufs-qcom.c:749–790` PRE_CHANGE 包含电源/PHY 序列、lane clocks、ICE；POST_CHANGE 涉及 shared ICE/hibern8，不能假设 retained 状态在 reset 后保留。 |
| 中断策略 | IS/IE `0x20/24`，UTP interrupt aggregation `0x4c`（bit 31 enable，`ufshci.h:215–220`）。模型要求读回已限定的 IE/聚合策略；本路径应保留轮询/不接 IRQ，不能照抄 Linux 的 IRQ enable。 | IS/IE 可读、正常接管已有 IE mask；不在隔离后清 IS/W1C 或写聚合。`ufshcd.c:4501–4548` 的 IRQ/聚合控制有已绑定的 IRQ/clock 前提。 |
| UTP 定时器 | `0xc0` SYS1CLK_1US、`0xc4` TX_SYMBOL_CLK_NS_US、`0xd8` PA_LINK_STARTUP_TIMER：经资格化的值写回后读回核对。`ufs-qcom.h:73–78`、`ufs-qcom.c:800–943`。 | 偏移在映射内；当前无经证明的 live core clock/gear/rate 及 reset 后配置，安全读写/重放旧值均未证。不读取或写入这些厂商定时器。 |
| Link startup | HCS `0x30` UCRDY bit 3；UIC command/args `0x90/94/98/9c`、DME_LINK_STARTUP `0x16`，IS completion bit 10；要有可归属的本次 UIC 完成、返回值与 HCS DP bit 0。`ufshci.h:122,149–159,266`；`ufshcd.c:4728–4801`。 | 标准偏移在映射内，不代表可发命令。`ufs-qcom.c:1102–1153` PRE_CHANGE 包含 timer/PHY line configuration、UniPro clock 控制和时钟门控。现有 provider 无安全的 post-reset link startup 合同。 |
| 队列 BA/RSR | UTRL `0x50/54`、DB `0x58`、RSR `0x60`；UTMR `0x70/74`、DB `0x78`、RSR `0x80`。新域 BA/U 逐项读回；HCS DP/UCRDY/UTRLRDY/UTMRLRDY 即 bits 0–3 全就绪才启动并核对 RSR/最终 HCS。`ufshci.h:37–46,149–159`；`ufshcd.c:4501–4548`。 | 现有初始接管只在预先限定的 quiet domain 更换 UTRL 并使用 slot 0/DB bit 0，UTMR 保持停止；两列表的标准结构可建模，故障后地址域和旧 DMA 未证，不能重建真实队列。 |
| 板级 reset | DTS 线索：`GCC_UFS_PHY_BCR`、GPIO 210；`ufs-qcom.c:551–565,2346–2373,3374–3387` 展示驱动控制 reset 的依赖。 | **unknown**：没有验证 nuwa 内核对 BCR/GPIO 的所有权、对应 host/device reset 职责、极性、外部电源/PHY 顺序或 reset 后 SID `0x60` 行为。没有硬点或访问引脚。 |

## 接入与故障注入

`CandidatePort::tryReinitLocked()` 复用 `ReinitAttempt` 前置门禁；
只接受已经隔离的会话，耗用一次尝试，不从生产 I/O 路径调用。
当前 proof 全空，返回 `PlatformUnproven`，不触碰寄存器。主机顺序模型
要求已有 producer exclusion、独立旧 DMA fence、不同新 domain 的不重叠
队列和可信 platform init 合同，才执行模拟的逐步读回。任何失败不回退、
不释放旧/新 DMA，不发布新会话。模拟成功后仍需匹配同一 boot/domain/media
的固件、DMA、LUN/块长、主备 GPT、窗口、已知根块、overlay 世代所有证据；
模型的 `RECOVERY_PROVEN` 只产生新身份，不复活旧 slot。

```text
PASS missing DMA fence/invalid fresh identity: no re-init operations
PASS HCE stop not observed: isolated, no retry, old DMA unchanged
PASS HCE 1-to-0-to-1 unproven: isolated, no retry, old DMA unchanged
PASS interrupt aggregation/IE mismatch: isolated, no retry, old DMA unchanged
PASS timer readback mismatch: isolated, no retry, old DMA unchanged
PASS UIC link startup failed: isolated, no retry, old DMA unchanged
PASS UTRL readback mismatch: isolated, no retry, old DMA unchanged
PASS UTMR readback mismatch: isolated, no retry, old DMA unchanged
PASS HCS not ready: isolated, no retry, old DMA unchanged
PASS known root block mismatch: isolated, no retry, old DMA unchanged
PASS re-init media validation timed out: isolated, no retry, old DMA unchanged
PASS model proves a fresh session only; next timeout isolates it, no second attempt
PASS candidate re-init refuses without old-DMA/platform proof; MMIO=0, submissions=0
```

12 个模型断言组、34 个 retained 入口断言组、37 个 Data/冷启动组与
linked crashcap 均 self-checked。标准模型无介质写接口；实际候选 Port
空 proof 的测试断言 MMIO/doorbell 不增长。硬件 `RECOVERY_PROVEN` 不可达。

## 离线候选与复跑

`out/nuwa-ufs-reinit-20261125-package/vendor_boot.img`，100663296 B，单核。
native 和最终 kernel 与 r8 `cmp` 逐字节相同；重新封包后，回读相对于
打包模板只更换 kernel 和重绑的 ADT CHMH，args 561 B、seed、trust 不变。
Python outer/FAT audit 和 `fsck.fat -vn` 都通过，余 **11042304 B**。
`llvm-objdump` 确认 write/sync 只在软件门拒绝；`llvm-nm` 无 re-init
入口或独立写后端符号。未接触设备，写门关闭。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `c60c7bcc9198def8ea3f0ce3035ad1f9206ac99831d8f311211e63d84628e35a` |
| Outer SHA-256 | `c82d91a2a6c031115a8debd3edbf5851c83775b4a4ba33fe0130527551a19685` |
| CHMH SHA-384 | `e6ba8f76ebced1484d33c385a7be42a5b4d09063a0012e1c912e7bdf7b5ecbf5d7e0fa23e8502514a837b907a73f4c00` |
| 回读 FAT SHA-256 | `9ad9030c0b519b1185e981e7a4bccda038356886521bdcc25fc8a367fb140242` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

用 [r8 配方](nuwa-data-write-design-20261125.md) 的单核参数和 fresh
`B`/`P`（本轮 build 目录为 `out/nuwa-ufs-reinit-20261125-build-r2`）。
为了隔离同期显示实验，build 脚本固定取 `87264f3`，仍读取当前 UFS 头文件；
可用下列 launcher 替代原构建命令的脚本名，其后传 r8 的完整参数：

```sh
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B -c '
import pathlib, subprocess, sys
p = pathlib.Path.cwd() / "scripts/build-nuwa-display-native.py"
sys.path.insert(0, str(p.parent))
sys.argv[0] = str(p)
src = subprocess.check_output(["git", "show", "87264f3:scripts/build-nuwa-display-native.py"])
exec(compile(src, str(p), "exec"), {"__file__": str(p), "__name__": "__main__"})
' ...
```

随后按 r8 配方运行入口、Data、linked crashcap 及 outer/FAT 审计，并加跑：

```sh
c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
  tests/test-nuwa-ufs-reinit.cpp -o "$B/test-ufs-reinit"
"$B/test-ufs-reinit"
```

UniXNU 上游 HEAD 前后均为 `b04f131da9151182dbb26ce4e638fa8acc2933ac`，
本地 pin 未改。待 `deep_reviewer` 审查 DMA/初始化合同，硬件后端未实现。
