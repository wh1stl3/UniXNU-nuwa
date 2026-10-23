# 主线交接（2026-10-24T02:58:55.763501+08:00）

## 当前结果与执行门

用户要求“继续，按缓存交接遗漏这个方向准备单变量修复候选，先完成离线验证和新包构建，保持Heap和坏条目保护不变，需要实测时再通知我录像”。本轮hob-cache-handoff已在用户新鲜确认录像后，完成preflight并即时通知后单次临时启动，ACK=0。120秒观察已结束，用户直接报告“进入了unixnu菜单”；缓存阶段原图待补；recovery/postcondition已确认Android完成1与三分区SHA不变，当前无需按键。不要重复启动，不以ACK认定缓存修复。实测记录目录reports/hob-cache-handoff-trial/2026-10-24/。先读AGENTS/STATUS/DECISIONS，两个旧资料库只读；不改板内存/基址或_verified。

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

固件仓文档已推送b569e4a（前序899ede3），仅同步集成/运输/输入审计状态；构建源仍固定6176a82，不将文档HEAD冒充实际镜像来源。设备仓本轮决策D-025已追加。

## 已完成执行与下一步

本轮preflight、launch、recovery、postcondition均已完成，原始证据不得覆盖；747d8fcc7368778a4af6ff49bf3d845e5154cf2e已推送。用户录像确认只用于本轮一次启动。当前无需按键，不要重新运行launch或恢复流程。

1. 接收并原样归档本轮缓存日志/菜单照片或录像，记录SHA256及来源。只有用户文字“进入了unixnu菜单”，尚无本轮图像。
2. 核对HOB-CACHE el/sctlr/base/bytes/line，以及cache-handoff-before、after-mmu和后续阶段。缺行写未验证，不从菜单倒推具体寄存器值或每个checkpoint。
3. 若原图支持跨越MMU，则将结论限定为单次候选阶段推进；仍有代码布局/时序混杂。若仍坏或维护被拒绝，依实际日志转向状态/映射诊断，保留Heap与保护。
4. 无需因等画面停止离线核对；不在本次“落实文档”请求下新增包或启动。后续设备试验必须新鲜录像确认、包复验、唯一nuwa/kalama、恢复门及即时通知。

## 后续试验命令模板（未执行，不含启动授权）

使用新的证据目录，例如reports/hob-cache-handoff-trial/<新的轮次>/；禁止复用本轮文件。配置PYTHONUTF8=1，PATH加入只读platform-tools，使用bundled Python。先执行record-nuwa-trial-state.py --output <新目录>/preflight.json --package <经严格验收的package.json> --capture-confirmation <本轮真实答复>。只有满足所有门且即时通知后，才执行trial-v4-firmware.py launch --evidence <新目录>/launch.json --package <同一包> --preflight <新目录>/preflight.json --observation-seconds 120。观察后按需recover --evidence <新目录>/recovery.json --package <同一包>，再record-nuwa-trial-state.py --output <新目录>/postcondition.json --before <新目录>/preflight.json。模板本身不是许可。
