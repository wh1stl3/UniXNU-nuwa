# 主线交接（2026-10-24T02:14:14.358409+08:00）

## 当前结果与执行门（2026-10-24T02:38:56.760611+08:00）

用户已要求按缓存交接遗漏准备单变量候选，只做离线验证和构建，实测前通知录像。新增hob-cache-handoff/0019，以2273bdec为基线，固件6176a82/Mu cfb93724不变；原HOB扫描/坏条目保护逐字节保留、Heap/地址/属性不改。私有一次性回调在建表完成后、MAIR/TTBR前维护完整对齐的已拥有HOB使用范围；要求EL1/2且SCTLR.M/C均0，否则停住。

51输入/11补丁/15后哈希和精确新增C的8192对齐/拒绝/序列/HOB不变/一次性回调主机ASan/UBSan通过。完整CI待触发；无新包SHA，不执行手机。续接推送后 `gh workflow run firmware-candidate.yml --repo wh1stl3/UniXNU-nuwa --ref main -f profile=hob-cache-handoff`，下载实际SEC/全表/严格容器验收后才通知录像。详见operations/2026-10-24-hob-cache-handoff.md。

最近真实设备仍2273bdec本轮postcondition.at=2026-10-23T18:20:52.568611+00:00（北京时间02:20:52），Android完成1、三分区不变，本轮无查询/设备动作。缓存机制是工作判断，未宣称修复成功；不重复启动旧包。下方旧构建和已完成流程仅供历史参考。

设备构建源a6e9a4c9766c05bd25c07e481b98e61c246ba8d5（后续文档/审计脚本提交不改变该产物）；固件分支codex/nuwa-sec-handoff-trace，固定6176a822e66b846620b5bcd2739a0666814ee663；Mu cfb93724a06ff86ff5ba971413368a7809ee42a5；上游UniXNU 75bc13dd34dc4e403826793739e316a264ce00dd。CI40000310916 success：https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/40000310916 。源码和证据均已按里程碑提交，勿混入原先无关untracked。

## 严格新包与静态证据

报告reports/hob-stage-audit/40000310916/package.json。
镜像out/trial-boot/hob-stage-audit-40000310916/boot-fv-probe-v4.img。
SHA256 2273bdecab25410dc290df84b031871f1f18d8dd2dbe57eea89dffd741813d61，3153920B。
FD74ad39a67305944849b09935b80e457ac46e3016fa74e3ea22a93a9636d34051，3145728B。
Shim8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，112B、text_offset0；FAT资源c097413d/4MiB仅配置，无XNU/ADT/追加DTB或ramdisk。

47原始输入、10补丁、14后哈希整链通过。精确新增C及包装的ASan/UBSan/保护页覆盖336截断、原图+0x118零长、长度/终点/条数上限、可信PHIT关系及失败不更新last-good。主机PIE+ASan最初偶发exit139，verbose止于初始化；仅主机改-fno-pie/-no-pie后单测及同一二进制20次通过。未借此更改目标固件，未声称定位宿主启动器根因。

实际SEC全部HOB阶段字符串、CreateHob前后两次检查、GetFirstGuidHob入口一次检查、错误到CpuDeadLoop直接分支均通过；检查器直接调用未发现allocator/cache维护或间接分支（不是完整传递调用图证明）。实际SEC表41行2952B SHA7694de6cf91ac305c82b3a2a82ad717a3155f88d59a185093a2a74a1a42bbdda与基线一致。memory-map-identical内firmware_commit是表布局参考ddd794f；本候选源6176a82见package/inputs。整包头+shim+FD+填充逐字节重建一致，缺preflight新包在设备子进程前拒绝。所有报告reports/hob-stage-audit/；仅静态/主机，未实测。

## 要拍的阶段与结果边界

0018使用InitializeMemory已有arena初始化可信边界，阶段为hob-constructor、create-before/create-after、resource-filled/allocation-filled、before-mmu/after-mmu、memory-peim-return、before-platform/after-platform、entry-arg-filled、before-constructors/after-constructors、guid-query。坏头输出[NUWA-HOB-STAGE] bad phase/context/reason/off/type/len、last-good phase/context/count/end/hash、PHIT及最多4个界内原始8字节字，然后停机。非里程碑成功检查保持安静，避免逐条刷屏；原0014保护仍保留。

record context在create阶段为(type<<16)|length；resource/allocation为现有描述符地址。reason1格式/跨度、2坏长度、3跨终点、4结束不符、5计数上限、6PHIT关系。hash为头部FNV32辅助，非全内容或无碰撞证明。额外扫描/日志可能改变时序，不复现不等于修复；首次检测区间不等于首次写坏指令。未改变Heap、TTBR、缓存策略、MMIO或HOB内容。

## 最近真实设备状态

a2dc8195上轮单次临时boot，原图BAB00118/type4/len0触发保护，未到ReadyToBoot。与旧成功87b14624实际SEC仅构建时间字符串4字节不同，掩蔽8字节时间后全SEC一致，根因未定。照片/差分见reports/boot-input-audit-trial/2026-10-24/。postcondition.at=2026-10-23T17:48:19.683937+00:00，即北京时间10-24 01:48:19；nuwa/kalama、Android完成1、slot_a、三分区SHA和当轮preflight一致，恢复闭环。不能当此刻实时状态。

## 已完成的2273bdec流程参考（勿重复执行）

下列本轮已执行完毕，仅留作新包流程参考；新包不得复用本轮录像许可。使用bundled Python，设PYTHONUTF8=1；PATH加D:/Code/PortingiOS/common/tools/platform-tools。始终唯一选择nuwa/kalama，不操作同时接入的enuma。脚本要求fresh路径，不覆盖旧证据。

1. 离线复验：`python -B -c "import sys;sys.path.insert(0,'scripts');from embedded_probe_package import validate;print(validate('reports/hob-stage-audit/40000310916/package.json')['image_sha256'])"`。
2. 用户确认该包连续录像至少120秒及按键回fastboot可用后：`python -B scripts/record-nuwa-trial-state.py --output reports/hob-stage-audit-trial/2026-10-24/preflight.json --package reports/hob-stage-audit/40000310916/package.json --capture-confirmation '<本轮真实答复>'`。若无实际Android完成1或唯一nuwa，先识别并恢复，不绕过门。
3. 即时通知开始录像后：`python -B scripts/trial-v4-firmware.py launch --evidence reports/hob-stage-audit-trial/2026-10-24/launch.json --package reports/hob-stage-audit/40000310916/package.json --preflight reports/hob-stage-audit-trial/2026-10-24/preflight.json --observation-seconds 120`。照片/录像读bad、last-good、raw及最后结果；USB不替代具体阶段日志。
4. 保存画面，必要时电源＋音量下回fastboot；`python -B scripts/trial-v4-firmware.py recover --evidence reports/hob-stage-audit-trial/2026-10-24/recovery.json --package reports/hob-stage-audit/40000310916/package.json`。
5. 实际Android完成1后：`python -B scripts/record-nuwa-trial-state.py --output reports/hob-stage-audit-trial/2026-10-24/postcondition.json --before reports/hob-stage-audit-trial/2026-10-24/preflight.json`。

人工按键可等待，同时继续离线；恢复/日志未确认不启动下一包。无后续真实窗口/Apple ADT或XNU成功证据；分析预链接5a128fb2早期security initializer空、ABI未验收、loadable=false，不得加入菜单。
