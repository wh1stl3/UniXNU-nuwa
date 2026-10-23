# 主线交接（2026-10-24T03:08:47.513216+08:00）

## 当前结果与执行门

五张用户原图已归档：维护后after-mmu ok/count84、memory Success、ReadyToBoot及唯一配置菜单，本轮阶段实机通过。缓存遗漏为首要原因判断，重复性及唯一根因未验。最后无OS/用户报告充电与探针action=exit/无OS负载相符。原Android完成1/三分区SHA一致已闭环；当前不需按键/本轮补图，不新增启动。AGENTS第8节落实用户主动结合公开资料作明确判断要求。

## 来源与准备好的包

构建设备源bdcf4a2f02f86dca5b7ad88e24377912f3612b0e（随后审计脚本/文档提交不改变产物）。固件codex/nuwa-sec-handoff-trace@6176a822e66b846620b5bcd2739a0666814ee663；Mu cfb93724a06ff86ff5ba971413368a7809ee42a5；UniXNU 75bc13dd34dc4e403826793739e316a264ce00dd。51原始输入/11补丁/15后哈希；在2273bdec候选链后追加0019，不改普通DSC/FDF或旧profile。

CI40005057158 success：https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/40005057158 。
报告reports/hob-cache-handoff/40005057158/package.json。
镜像out/trial-boot/hob-cache-handoff-40005057158/boot-fv-probe-v4.img。
SHA256 26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051，3153920B。
FD SHA256 0e90473e1526d29cfda8f0c285f3b3e7db4ee0862e81b3f138dac604860ba225，3145728B。
Shim仍8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，112B/text_offset0；FATc097413d/4MiB仅配置，无XNU/ADT、ramdisk或追加DTB。

## 单变量范围与已完成验证

MemoryPeim只新增登记私有一次性回调；ArmConfigureMmu ABI/默认空回调路径保留，最后FillTranslationTable后、MAIR/TTBR前消费并清空回调。HOB交接要求实际EL1/2、适当级SCTLR.M/C都0和原可信arena/完整链有效；按缓存行覆盖最新成功HOB终点+8，要求基址对齐、无溢出、补齐仍在arena内。只DSB→范围IVAC→DSB→ISB，之后不HOB写入/分配/打印，立即回原MMU安装。错误EL/状态/范围或坏链仍停机，不绕过保护。

0018原保护块源码逐字节保留；移除0019私有回调声明/钩子后MMU正文与基线相同。没有新增HOB/GUID，没有改Heap、地址、属性、页表算法或TTBR/TCR数值。新增ArmLib/CacheMaintenance依赖没有构造器。诊断/回调会影响布局时序，尚非修复效果或根因证明。

主机精确C（真实寄存器/cache操作由记录适配器替代）ASan/UBSan验证8192对齐/上轮FF0→1000、拒绝溢出/错状态/坏HOB时零维护、显式调用序列、HOB内存不变、默认/一次性/失败不安装；旧FD冒充/空录像门通过。实际SEC核验DSB→InvalidateDataCacheRange→DSB→ISB，范围函数的行操作指针解析到ArmInvalidateDataCacheEntryByMVA，实际DC IVAC及DSB SY/ISB存在，原CreateHob2次/查询1次checkpoint与CpuDeadLoop保留。直接调用审查不是全传递调用图或运行cache效果。

41行2952B内存表SHA7694de6cf91ac305c82b3a2a82ad717a3155f88d59a185093a2a74a1a42bbdda与基线完全一致。memory-map-identical里的firmware_commit是表布局参考ddd794f；实际候选源见package/inputs6176a82。启动头+shim+FD+填充严格重建一致；实际新包缺preflight在设备子进程前拒绝，调用0。报告reports/hob-cache-handoff/，技术细节operations/2026-10-24-hob-cache-handoff.md。

## 最近实机事实

2273bdec上轮before-mmu56条/endBAB00AA8有效，函数内末次create-after84条/endBAB00FE8/context20030有效，返回Success后after-mmu首次off718/type0/len0。未到PlatformPeim/构造/DXE。公开资料及源码/实际指令支持首嫌缓存交接遗漏，次嫌映射/属性；不认定已证明具体机制。照片/审查reports/hob-stage-audit-trial/2026-10-24/。

上轮postcondition.at=2026-10-23T18:20:52.568611+00:00，即北京时间10-24 02:20:52；nuwa/kalama、Android完成1、slot_a、三分区SHA与当轮preflight一致，恢复闭环。本轮启动前新鲜preflight.at=2026-10-23T18:50:04.648494+00:00，Android完成1及基线已取得；本轮postcondition.at=2026-10-23T18:55:45.904383+00:00，恢复后Android完成1且三分区SHA一致，已闭环。分析预链接5a128fb2仍loadable=false，无真实ADT/窗口/XNU执行证据。

固件仓文档/规则已推送e7a2284（前序6770fb9、b569e4a），仅同步集成/运输/输入审计状态；构建源仍固定6176a82，不将文档HEAD冒充实际镜像来源。设备仓本轮决策D-025已追加。

## 已完成与下一步

本轮preflight/launch/recovery/postcondition及五原图完整，screen-observation.json记录SHA及逐图转录；SCTLR全值不强读。详见2026-10-24-hob-cache-handoff-trial.md，历史“原图待补”由新证据取代，不重跑设备动作。

1. 保持Heap、HOB保护、板内存及_verified，继续真实OS运输/ADT/窗口实际分配离线准备。ReadyToBoot最大9GiB仅快照，不据此填所有权或分配成功。
2. 缓存遗漏为首嫌，映射/属性、布局时序仍是备选。后续独立重复试验须新鲜录像确认、包复验、唯一nuwa/kalama、恢复证据及即时通知，不复用本轮preflight或录像许可。
3. 不包含XNU/ADT的配置探针退出后找不到OS符合设计；无需为此删守卫或改Heap。固件仓文档/规则e7a2284已推送，实际构建源仍6176a82。
4. 原始记录不覆盖。新轮次使用新证据目录；试验结束恢复Android完成1并核对三分区SHA。

## 最新离线续接（2026-10-24T03:17:12.549163+08:00）

固定DarwinBoot RunEnd/AllocateWindow主机ASan/UBSan12项通过；分析内核真实VA同余偏移0x1c8000，在照片最大合并区子集上计算0x8c01c8000，不写board、不称实际分配。详见2026-10-24-loader-window-offline.md。4MiB配置卷不能容纳约58MiB分析内核；直接启动的主阻塞是运输/ADT/初始化与ABI而非当前已越过的HOB。下一步独立文件读取/长度/SHA诊断优先，USB host或大FV均尚未qualified。无新包/设备动作，恢复状态仍此前证据。

## 上游审查续接（2026-10-24T03:28:17.252417+08:00）

用户要求查最新驱动，完成主仓1a01c2af/12模块/同SoC的固定对照，报告reports/upstream-review/2026-10-24/review.json。GPU/HID/显示等实质更新，CPU/平台/预链接工具代码无新实现；推荐独立评估DarwinBoot d099354d+RamBlock d4d22d98。0005对最新DarwinBoot严格内存apply通过，未构建/采用。主仓diverged，不pull或替换固定75bc；nuwa ST FTS不改成Novatek。详见2026-10-24-upstream-driver-review.md。手机和板值均未操作。

## 用户合并授权与执行（2026-10-24T03:46:17.280839+08:00）

用户明确要求合并所有更新，现已合并并推送基座e553e46，树与upstream1a01c2af+三nuwa工作流相同，21模块固定。设备新增upstream-merged固件profile并更新kernel-merged；63项内核完整patch与固件整链静态通过，待完整CI。本节替代前文“不整体升级/未采用”当前决定，不改历史证据。新包尚无实机，旧26ef8efd仍唯一缓存候选恢复闭环。完整命令/状态见2026-10-24-upstream-integration.md。

最新：固件40014018074成功，FD2d606985，SEC/Heap/HOB保护与已实测包字节一致；24项解析和packed/SMMU主机通过。内核40014023191最终链接因接入漏前置zzw授权补丁失败，已补完整上游实现+SHA，64项序列静态通过，需重建；不放宽链接或删检查。GPU x86主机受真实AArch64 dsb限制，不称其通过。新CI待后续本文件更新，无设备动作。
