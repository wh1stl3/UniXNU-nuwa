# Daily 探针合并候选 — 2026-11-28

主机构建与测试仅为 **self-checked**；独立 verifier 待主控派发。普通 reviewer 和
`deep_reviewer` 的结论由主控转述，见文末。没有设备操作或设备写入授权。

## 合同

- **daily 不得 reset**：打包未传 `--v1-reset`，实际参数必须无
  `sheng-data-reset`。目标是观测既有 r4 overlay 的重开结果，不调用 Fresh
  重建；`D1 why=ok`、非 Fresh 与 `D2 er=0` 均是待观察项，不是本机结论。
  内核仍包含已有的显式 reset 代码；缺少 reset 参数不构成持久性证明。
- 在 r4 同组构建参数上增加 `--sb-threads`；`--pixsig` 的正常构建路径已经
  使用 `verify-nuwa-display-host-abi.py` 的 RG 插入点，无需 replay 或新增
  队列修改。复用 `UniXNU/GopFramebuffer@e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`
  （BSD-2-Clause-Patent）与本仓已有采样器。
- 显示状态行去掉候选名、`NEON` 和设备型号；不屏蔽任意内核控制台内容。
  已有 `nuwa:` 日志和旧冻结二进制仍可能暴露型号，不能声称整个屏幕绝无名称。
  这些状态行不携带可区分候选的身份，须靠主机上的产物哈希关联。

## 行与解释

- `IO cid=N261126A s=<phase> old=? rsr=?` 保留原字段；`old`/`rsr` 仍未知。
- `D1 st/h/pres/why/rst`、`D2 wr/er/ufs`、`D3 first/after` 保留原含义。
  `DATA0 ... dur=?` 表示未证明介质耐久。
- `RG en/ret/g/last` 分别为进入 retirement、completion 返回、最新进入世代
  和最后返回世代；独立 relaxed 采样，不证明完成通知或用户态消费。
- `SBTH n=` 是 SpringBoard 线程数；详情为采样 PC 的频数和代表 LR/SP，
  字段非原子快照。普通页摘要占第 0 行，详情在第 48 行之后；panic 只留摘要。
  D1–D3 为第 4–6 行，RG 为第 9 行；XP 仅进 live banner 的最低优先级，
  行预算不足可被舍弃，不抢占这些行。
- `XP p<pid> pc=<16 hex> b=<16 hex>` 对应原 XR 的首个异常退出环记录。
  `pc` 是该退出时**当前线程的保存用户态 PC，不等于 fault PC**；`b` 是
  XNU `task->mach_header_vm_address`（进程主可执行文件的 Mach-O header
  地址），不是任意 PC 所在共享缓存/动态库的基址。`-` 表示未能关联当前
  PID/保存寄存器；有效字段显示零时不能推断映像已装载。重复环项沿用首个
  采样。`bp_critical` 单独保存同样的样本，但本候选不新增 panic 安全带
  的 XP 绘制；画面可见性和采样时序未上机验证。
- XNU 8796 `activate_exec_state()` 在加载时将 `result->mach_header` 交给
  `task_set_mach_header_address()`；后者写入时持 task lock。本候选对当前
  task 做 relaxed 无锁只读，不加锁、不读用户内存；字段可能与 PC 不是一致
  快照。现有环锁与 critical 发布机制未改；对象生命周期、并发和实际退出上下文
  的审查结果见文末，不能把主程序基址直接减去共享缓存 PC。

## 构建和测试

本机 UniXNU pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，开始与编译后
远端 HEAD：UniXNU `fdf81eaa832ce5c850d3c53c698407aa722a4653`，device
`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`。r4 的 retained
`RetainedPersist.inc`、`NativeRamBlock.cpp` 逐字节匹配；CPO、GPT、donor 和
模板 SHA-256 分别为 `d390eb44…822e0c70`、`e96313e1…4b030529c`、
`2ec297ba…375c1221`、`18fa4941…fc76202a`。

首次构建因生成器缺少 `bp_v1_status_suffix` 前向声明而失败，目录
`out/nuwa-probe-merge-20261128-build` 保留；修正声明后使用新目录：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
b=out/nuwa-probe-merge-20261128-build-r2
pkg=out/nuwa-probe-merge-20261128-package
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
$p -B scripts/build-nuwa-display-native.py --base "$base" --cpo "$cpo" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag \
  --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --data-v1-retained --post-event --sb-threads --out "$b"
$p -B tests/test-nuwa-sb-threads.py --build "$b" --normal-build
$p -B tests/test-nuwa-retire-generation.py --build "$b" --normal-build
$p -B tests/test-nuwa-v1-retained.py "$base" "$b"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B scripts/test-handoff-xr.py
$p -B tests/test-nuwa-ufs-neon.py "$b"
$p -B tests/test-nuwa-pixsig.py
$p -B tests/test-nuwa-crashcap.py "$b/kernel.macho"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
```

构建、SBTH fixture/链接调用、RG 三路径、74 个 retained fixture、post-event
链接反汇编、XR/XP 格式、UFS 行、PIX、crashcap、outer `--audit-only` 和
`fsck.fat -vn` 均运行，self-checked。独立从两份 FAT 的 `unixnu.toml` 提取
参数比对：本候选恰是 r4 参数删除 `sheng-data-reset=1`，无其他 token 差异。
XP 最大 fixture 行长 53；这不是独立验证或设备观察。

| 项目 | 值 |
|---|---|
| kernel | `out/nuwa-probe-merge-20261128-build-r2/kernel.macho` |
| kernel SHA-256 | `3fda852321b78508ba4d3d9c2014601e2c8e2a585e127d407ddd0bb67b45222d` |
| outer | `out/nuwa-probe-merge-20261128-package/vendor_boot.img`，100663296 B |
| outer SHA-256 | `86624e665e904b66583e35ae9a335e8c023b561ce8423a8f23b6e11a8c386c10` |
| FAT SHA-256 / 空闲 | `143fec42bd9fb502df3980a5592e350721dc40fe11d663c93ba0f8793f30ee22` / 11005440 B |
| CHMH SHA-384 | `46900593b36a9203a9acbe4a168756984afc4abb7933a628fe02c138123acd24f038c225042a617cb04d810ffae586df` |
| 外审 | 普通 reviewer 和 deep_reviewer 均为 PASS WITH CONDITIONS（主控转述）；未获设备放行 |

## 审查留痕

以下结论均为主控转述，审查日期 **2026-11-28**，绑定 outer SHA-256
`86624e665e904b66583e35ae9a335e8c023b561ce8423a8f23b6e11a8c386c10` 和
kernel SHA-256 `3fda852321b78508ba4d3d9c2014601e2c8e2a585e127d407ddd0bb67b45222d`。

- 普通 `reviewer`：**PASS WITH CONDITIONS**，接受上述 outer 和 kernel。
  确认 daily 不含 reset 语义、不会写 LBA `57393401`；RG/SBTH 落点和行位
  合规，XP 不挤占 D1–D3；整屏去名未闭合。
- `deep_reviewer`：**PASS WITH CONDITIONS**，仅限 XP 项。采样对象生命周期
  成立，无新增 UAF 或用户页故障。**须后修**单全局 `bp_critical` 就地覆写的
  发布协议：进程 A 的快照可能被进程 B 覆盖；在把 critical 快照用于事件归因
  或输出 critical XP 之前必须修复。此项不在刷入前阻断。
