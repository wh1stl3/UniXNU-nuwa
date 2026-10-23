# 主线交接（2026-10-24T04:19:54.495058+08:00）

## 当前任务已完成部分

用户“合并所有更新”已落实：wh1stl3/UniXNU main=e553e467ebfe7642e9f483d3977a57066c6d1aef，父76dd6414/上游1a01c2af；完整树等于上游+3份nuwa工作流，21个模块固定、独立D:/Code/UniXNU-integration检出。代码/CI接入5abdde1，前置授权补丁修复6070627。历史75bc、旧固件profile和26ef8efd实测证据保留；不修改原始报告。两个旧资料库只读，执行前先读AGENTS及STATUS。

## 产物及验收

- 固件40014018074/source5abdde1 success，3MiB FD2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f；shim8a3b5476/112B。下载out/upstream-firmware-40014018074/nuwa-firmware-40014018074/。697项实际检查通过，整个SEC与已实测缓存候选完全相同，HOB检查、缓存维护和Heap/内存表不变。新默认固件profile upstream-merged。
- 内核40015845083/source6070627 success；原失败40014023191漏zzw辅助函数依赖的记录不覆盖。新64项补丁及真实平台归档/复链通过，下载out/upstream-kernel-40015845083-final/nuwa-8796-merged-40015845083/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped。SHA bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea，20188216B，Darwin22.6.0/iOS16.0，零未定义符号，5项平台导出及实际归档独立核对通过。
- 新解析24项、packed逻辑1TiB/13拒绝、SMMU夹具、grant助手9项、常量池4项通过。GPU VM AArch64交叉链接+用户QEMU软件寄存器/IOKit夹具通过；不是目标XNU ABI或真实GPU/cache/SMMU。21模块源码可用，source-only内核未擅自开启可选root/hash-cache/GPU分支，不能称全部功能已编译/实机通过。

全量证据reports/upstream-integration/2026-10-24/及reports/upstream-merged/40014018074/；关键integration-result.json、kernel-inspection.json、firmware-regression.json。固件仓文档ca2f043，构建固件pin仍6176a82+11补丁，不将文档HEAD当镜像来源。详细操作2026-10-24-upstream-integration.md。

## 实机与边界

本任务没有adb/fastboot/flash/erase/改槽位。最近实际恢复仍26ef8efd postcondition.at=2026-10-23T18:55:45.904383+00:00（北京时间02:55:45），Android完成1/三分区SHA不变，不当作当前新查询。26ef8efd原图after-mmu/ReadyToBoot/配置菜单通过，缓存遗漏是首要工程判断，重复性未闭环；新FD2d606985和内核bf14均未实测。无需用户按键/补图，不复用旧录像许可。

Heap/HOB保护、ST FTS硬件路线、内存/地址/身份/_verified不改。sheng Novatek/CPU列表/存储尾部布局和Data重置动作不套nuwa。9GiB是快照，未分配OS窗口。

## 可直接续接的工作

1. 以新内核bf14实际产物为输入，离线重新准备NativePrelink/initializer/ABI资格。工具已迁移到合并源的NativePrelink2b6ffb50，两个原始工具与历史字节相同，4项常量池拒绝回归通过；旧7774和5a128fb2仍是历史分析fixture，不改标成新内核预链接，不直接启动。
2. 继续独立大文件长度/SHA运输诊断、真实ADT属性核对及实际AllocatePages候选。4MiB配置FAT不能装约58MiB分析预链接；USB host/扩大FV/UFS写入均需各自具体依据，不通过删保护/乱换Heap解决。
3. 复核新固件静态链：bundled Python -B scripts/check-upstream-merged.py。实际二进制已审，不因无变化重复重建。新内核检查见scripts/ci/inspect-source-kernel.py原命令与报告。
4. 以后需设备动作时先新鲜录像确认/恢复路径、严格包验收、唯一nuwa/kalama并即时通知；使用新轮次目录，禁止覆盖旧preflight/launch/recovery/postcondition。试验结束恢复Android完成1与三分区SHA核验。当前没有新的临时启动授权或启动包实测结果。
