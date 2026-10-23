# 主线交接（2026-10-24 01:40更新）

## 当前执行状态（2026-10-24T02:01:55.720812+08:00）

用户要求先完成离线诊断和新包构建，实测时再通知录像。新增独立hob-stage-audit，固件固定6176a82，追加0018有界HOB阶段检查。47输入/10补丁/14后哈希、精确新增C诊断ASan/UBSan/保护页、336截断/原图坏头等主机检查及旧FD冒充/空录像拒绝通过；完整CI待触发。详见operations/2026-10-24-hob-stage-audit.md。

最近真实设备仍为a2dc8195试验的postcondition：UTC2026-10-23T17:48:19.683937，北京时间01:48:19，nuwa/kalama、Android完成1、三分区SHA不变。此次离线工作无设备查询/动作。HOB根因未知；不跳过检查，不改缓存/Heap/板内存。旧SEC差分和坏头原图见reports/boot-input-audit-trial/2026-10-24/。

直接续接：推送后 `gh workflow run firmware-candidate.yml --repo wh1stl3/UniXNU-nuwa --ref main -f profile=hob-stage-audit`；完整下载检查及41行表对比后 `python -B scripts/embedded_probe_package.py RUN --profile hob-stage-audit`。包就绪后新鲜录像/唯一nuwa/原Android恢复门及即时通知齐备才可单次试验。下方旧a2dc8195内容是历史事实/流程参考，不重启旧包。

## 当前提交与完整构建

设备构建源84c88f8057a808670fc84d151ad0b4128ce91013（本次文档提交在其后）；固件分支codex/nuwa-sec-handoff-trace，固定6176a822e66b846620b5bcd2739a0666814ee663，已推送。CI39995937843 success：https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39995937843 。独立profile boot-input-audit；正常固件DSC/FDF没有改动，新模块由设备补丁0017选择。

准备好的包：reports/boot-input-audit/39995937843/package.json。
镜像：out/trial-boot/boot-input-audit-39995937843/boot-fv-probe-v4.img。
SHA256 a2dc8195b4368da37276a4618dca90fd556f1d5de72fd58faff0b600936ba65b，3153920B。
FD SHA256 bfb02a6334f201778467ecc1f1a9042396dc1a3dcd2014c8c4118b88664f106b，3145728B。
BootShim仍8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，112B，text_offset=0。

实际模块/DEPEX/标记、FV RAW 4MiB FAT16 c097413d精确资源、41行2952B SEC内存表7694de6c一致通过。包按原始boot头+固定shim/FD重建逐字节一致，缺preflight时设备子进程调用0。10项固件C宿主UBSan测试及2项拒绝门回归通过。证据reports/boot-input-audit/；memory-map-identical报告firmware_commit是表布局参考源ddd794f，实际候选源以package/inputs.json的6176a82为准。

## 真实设备状态及尚未完成

最近一次确认时间UTC 2026-10-23T16:56:45.092564（北京时间10-24 00:56:45），来自reports/embedded-probe-trial/2026-10-24/postcondition.json；nuwa/kalama、Android完成1、slot_a、三分区SHA与preflight一致。本轮没有设备查询，不能声称实时状态不变。没有flash/erase/改槽位。

87b14624/CI39988591973/固件00a37d9已实测4MiB FV配置卷发现；菜单60秒action exit，无XNU/ADT。新a2dc8195仍只含该配置探针，加ReadyToBoot一次性只读EL、MPIDR、CNTFRQ和ConventionalMemory快照，打印后停10秒，再进入探针菜单。不分配/预留XNU窗口，不执行ExitBootServices。快照含自身map缓冲区，稍后释放；不代表后续AllocatePages成功或窗口所有权。本轮SEC停点导致新模块回调/快照尚未执行。保留至少120秒录像，需读取ready、conventional、summary、largest及最后结果，不能用USB ACK当阶段日志。

77742999当前内核分析候选5a128fb2/58335232B已完成65348项绑定读回、30段组件和native代码保持、固定DarwinBoot主机ParseKernel接受15非零段/74174464B跨度。early_security_initializers为空、完整ABI未验收、loadable=false，不得加入设备菜单。详见operations/2026-10-24-current-native-prelink.md。CPU Vectors/TZ/SPSS/Rsc独立问题未修复。

## 用户明确恢复后可用命令

下列a2dc8195步骤本轮已全部完成（失败画面及恢复闭环均已归档），禁止自动重复launch/recover。留作流程参考；新一轮仍需新包及新鲜录像。Windows使用bundled Python并设PYTHONUTF8=1，平台工具PATH加D:/Code/PortingiOS/common/tools/platform-tools；选择真实nuwa/kalama，绝不操作enuma。

1. 纯离线包复验：`python -B -c "import sys;sys.path.insert(0,'scripts');from embedded_probe_package import validate;print(validate('reports/boot-input-audit/39995937843/package.json')['image_sha256'])"`。
2. 取得本轮用户明确录像/按键可用答复；不可用则保持不启动。先检查实际Android身份/完成1/三分区并保存新preflight：`python -B scripts/record-nuwa-trial-state.py --output reports/boot-input-audit-trial/<fresh>/preflight.json --package reports/boot-input-audit/39995937843/package.json --capture-confirmation '<本轮真实答复>'`。
3. 立即通知开始录像，再执行：`python -B scripts/trial-v4-firmware.py launch --evidence reports/boot-input-audit-trial/<fresh>/launch.json --package reports/boot-input-audit/39995937843/package.json --preflight reports/boot-input-audit-trial/<fresh>/preflight.json --observation-seconds 120`。
4. 保存屏幕结果后回fastboot，执行原Android临时恢复：`python -B scripts/trial-v4-firmware.py recover --evidence reports/boot-input-audit-trial/<fresh>/recovery.json --package reports/boot-input-audit/39995937843/package.json`。
5. Android实际完成1后 `python -B scripts/record-nuwa-trial-state.py --output reports/boot-input-audit-trial/<fresh>/postcondition.json --before reports/boot-input-audit-trial/<fresh>/preflight.json`。若等待实体键，记录待办并继续离线工作（仅在用户已恢复主线时）。

每轮证据必须fresh；不得覆盖旧记录。窗口/board/bringup内存基址及_verified仍另受AGENTS硬停审阅约束。
