# v28 / PROBE20：iOS16 pthread 正常 OSKext 启动

## 当前结论

PROBE19 已实机进入 BSD，当前首要阻塞是遗漏 `com.apple.kec.pthread`，不是 Image4。v28 将固定 donor 中的真实 iOS16.7 组件加入闭合选择，并在 BSD 入口请求正常 OSKext 加载。候选尚未实机验证；root 发现、挂载和用户态仍未进入。设备最近后验仍为 2026-10-25 20:03:58 +08 Android 完成1、A槽、三分区SHA不变。

## 固定来源与运行顺序

旧30组件基线 SHA256 `1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6`；只加入 pthread 的31组件 prelink 为 `52227410fd5ad0da9b8487a3fc3706a8f03042cc8256cfe99018897337f47e01`。沿用 v27 pthread-registration.json 的固定 donor、集成提交、原生绑定与11项注册审计。新旧段布局逐项相同，原生 __TEXT_EXEC 未改变；差异作为带前像的显式范围写入 build.json，不改变历史构建的 INPUT。

只读 XNU 源码提交 `1b191cb58250d0705d8a51287127505aa4bc0789`，源文件均为 APSL-2.0：

| 文件（xnu-ios16-full 下） | SHA256 | 核对内容 |
| --- | --- | --- |
| libkern/OSKextLib.cpp | a62ce50e4559ee51b1989f1750323cab27008d598fac7e8502905c363ccb3ac2 | :46 单参数 C API 转正常加载器 |
| libkern/c++/OSKext.cpp | 182b7473996e4f646bcbffff0ad67ad292fa4c27b1a31ab42786c900653d4244 | :5855 创建标识，查注册表，load/start，保留原生错误 |
| libkern/libkern/c++/OSKext.h | 44c5426822fce5aa0e674078148b063db9aa23d667c1a13d8e63155179475342 | :786 默认 startOpt=kOSKextExcludeNone |

BSD 入口诊断外层保存 x9–x28/NZCV，新增 helper 保存 x0–x8/x29/x30、全部 SIMD 和 FPCR/FPSR。若真实 `_pthread_functions` 已非零则不重复请求；否则调用 `_OSKextLoadKextWithIdentifier("com.apple.kec.pthread")`，记录真实返回码和表指针，再继续原始 BSD 第一条指令。出货 helper 不直接调用 kmod，不填函数表，不跳过 `_pthread_init`，不吞原生 panic。

真实 donor kmod start 是 `0xfffffff005112000`，表 `0xfffffff005ea0980`，实际初始化函数 `0xfffffff005113240`。原生注册将真实 callbacks 交给组件；真正 `_pthread_init` 后续仍由 BSD 调用。只读 libpthread-ios16 提交 `a6c70ca0e544347a0377babf748f831577ec24f9` 的 kern/kern_support.c:1030 显示初始化依赖 lock/group/mtx、全局 hash、thread_call_allocate、boot arg 和 sysctl_register_oid；不以 Darwin23/iOS17 参考实现替换 ABI。

## 离线模型边界

`test-pthread-startup.py` 从实际 BSD hook 执行，在正常 OSKext API 边界显式建模：成功边界转真实 donor kmod，执行原生注册；失败返回固定错误；已注册无调用。分别覆盖视频和无视频，并主动破坏 volatile GPR、SIMD、NZCV、FPCR/FPSR，比较原生第一条指令后的机器状态。继续执行真实 `_pthread_init` wrapper，确认成功分派到 donor 初始化入口、失败仍到原生 panic。

此模型不执行完整 OSKext 生命周期或 pthread 初始化函数体；报告字段明确为 false。旧740项透明性检查在此修订显式采用已注册夹具，不能冒充加载成功证据。正常生命周期、初始化体和后续 BSD 需要实机。

## 候选输入与观测

候选内核 `out/kernel-entry-probe-28-pthread-c/kernel-entry-probe.macho`，SHA256 `d34a5de954a806f66fa346a74e5312a2513ec24d4377759d850ec6d6dd3eeb1d`，58,413,056B。构建报告 `reports/kernel-entry-probe/2026-10-25-v28/build.json`。

本次基础 ADT 重新生成；Nuwa.DiagnosticLaunch.v1 生产器保持原文件，独立生成新 nonce，并绑定真实候选内核、FD、shim、基础ADT。最终 ADT `out/pthread-mainline-v28/launch/kernel.macho.adt`，SHA256 `635d4f4dd8fc4abc7c2d15b427cf69b6a037086a39df21fb22b33b6fddb1ed09`。原像仅本地 out；仍为非Apple诊断测量，不是硬件nonce/可信链或防重放证明。

旧178点、A02A/B/C含义不变。新增ID178=调用加载器前（蓝），179=加载器返回（绿），180=真实表非NULL（品红），181=进入时已注册（黄）；坐标依旧按10列、24像素行距，178/179在第17行第8/9列，180/181在第18行第0/1列。ID7/8才是root发现/挂载入口；未亮不单独作为停点。旧错误检查原样保留。

## 验证与续接

19项串行验证任务全部通过，记录在 v28/execution.json：740项差分、25项完整Image4检查、6项pthread定向检查、31项绑定检查及入口/MMU/向量/显示/同ADT回归通过。独立内核重建逐字节一致，证据reproduce.json。包 reports/xnu-first-entry/entry-probe-20.json 已完成实际FAT内核/ADT回读与FD/shim/manifest重新测量。

镜像 `out/trial-boot/xnu-entry-probe-20-pthread/boot-xnu-first-entry.img`，70,266,880B，SHA256 `365216aebab5ec2e925a65f65576a26a6f1173ca4aa631e0c0ff0faf46422198`；FAT SHA256 `6ff839e19c9dd5015a3f8f54a55456ddb796a1604ce9bd6d5498c18e79c57eba`。菜单明确标PROBE20。尚未执行本包设备启动，loadable/runtime_qualified仍false。

续接命令（仓库根目录）：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-20.json
# 收到PROBE20当轮录像/按键恢复就绪答复后，按原文填capture-confirmation：
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/record-nuwa-trial-state.py --package reports/xnu-first-entry/entry-probe-20.json --before reports/xnu-entry-probe-trial/2026-10-25-v27/postcondition.json --output reports/xnu-entry-probe-trial/2026-10-25-v28/preflight.json --capture-confirmation '<当轮用户原文>'
# 通过新鲜preflight并即时通知后：
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/trial-v4-firmware.py launch --package reports/xnu-first-entry/entry-probe-20.json --preflight reports/xnu-entry-probe-trial/2026-10-25-v28/preflight.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v28/launch.json --observation-seconds 0
```

下一次设备动作之前，按 AGENTS.md 第3/9节确认**PROBE20当轮**全程录像、菜单电源Enter、停屏采集和必要时按键恢复就绪；刷新 preflight 对比 v27/postcondition.json 三SHA。即时通知后只做一次临时boot，不flash/erase/改槽。采集后恢复Android完成1并比较本轮preflight三SHA。此确认只针对实机观测和恢复条件，不阻断离线工作。

本轮构建、补丁和离线验证不改板值/TCR/内存/IPSW身份，不设置任何 *_verified=true；loadable/runtime_qualified 仍false。不上载原始媒体，无push或新CI。

2026-10-25 20:42:51 +08：用户答复“现在可以，录像与恢复就绪”；新鲜preflight Android1/A槽/三SHA与v27后验一致，即时通知后只执行一次临时fastboot boot。ACK成功，等待菜单电源Enter后的真实画面；未取得pthread/root结果或本轮恢复后验。代码f0f4ea6，launch/preflight在reports/xnu-entry-probe-trial/2026-10-25-v28/。不得把此ACK写成内核执行通过。
