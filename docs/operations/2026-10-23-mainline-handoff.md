# 主线交接：MMU 构造停点（2026-10-23 晚）

本文件是接手入口，当前状态以 docs/STATUS.md 为准。交接基线：设备仓 main@d056fb9ac1ab1353bc6359d7cdc06282610aa297，GitHub main 已用 gh api 复核一致。本轮仅整理文档，不启动构建或操作设备。

## 先读与不可丢失的约束

依次读 AGENTS.md、docs/STATUS.md、docs/DECISIONS.md、docs/inherited/unixnu-official-2026-10-22.md，再读本文所链证据。用户授权普通 Git add/commit/push、gh 和 workflow 操作；不 force、不改写已推送历史。生成诊断/固件镜像无需硬停。

- 可写 D:/Code/UniXNU-nuwa、D:/Code/uefi-nuwa；D:/Code/PortingiOS 和 D:/Code/PortingiOSWithUniXNU 严格只读。
- feed 不变；4 KiB、iPhone10,3/d22ap/iOS 16.7.16/20H392、XNU 8796.141.3 固定。ipad_identity=true 是安全属性约定。未知板值 TODO，不能照搬同 SoC 的地址或 donor prelink 值。
- 修改 board.toml/bringup-plan.json 的内存/基址及既有 IPSW 身份等审阅字段、置任何 *_verified=true，仍硬停。实际启动/刷写若没有具体过程日志或已确认恢复路径，也必须先 NEED-REVIEW（至少两候选、代价、倾向）并停。
- 当前具体过程日志来自用户拍摄屏幕；USB/fastboot ACK 不是阶段日志。新试验须刷新用户在场录像、实际 nuwa 身份、包校验和恢复条件。不要承诺精确倒计时，通知准备录像后执行并报告实际结果。
- 每轮结束核验真实 nuwa Android sys.boot_completed=1；只差实体键则记 PENDING-HUMAN 后继续离线工作。不得把普通 boot 恢复证据扩展为 userdata/系统卷刷写可恢复。
- 难题主动评估同 SoC UniXNU/UEFI 实现，记录提交、许可、哈希、依赖及适用边界。

## 已取得的实机结论

最新一次仅临时启动 530f56b4 包。原图和结构化记录在 [实测证据](../../reports/constructor-trace-trial/2026-10-23-evening/)，报告：[逐构造实测](2026-10-23-constructor-trace-trial.md)。

```text
[NUWA-CTOR] Debug enter
[NUWA-CTOR] Debug leave status=Success
[NUWA-CTOR] Extract enter
[NUWA-CTOR] Extract leave status=Success
[NUWA-CTOR] Mmu enter
```

没有观察到 Mmu leave、Lzma enter、DXE 或 SHENGMEM。只能定位到 MMU 构造内部/相关日志路径，不能认定具体故障指令或排除日志失效。原图 SHA256：520bdded72db7ec796f422356ae22ebfa1aded59a180c1a9b6581d8431dffb92。

恢复脚本在 19:46:21 直接检测到 Android；随后 postcondition.json 再确认 nuwa/kalama、boot_completed=1、A 槽和 boot_a/vendor_boot_a/init_boot_a 三项 SHA 不变。没有发送原 boot、flash、erase 或改槽；回返机制未独立记录。本交接没有重新读取设备，因此上述是最近一次已确认状态。

此前 R-011 同机原厂 Heap 包曾进入 UniXNU 菜单，后续未稳定复现；保留该观察，但目前尚无实机进入 XNU 的证据。

## 可用产物：勿混用旧包与新草案

| 项目 | 固定输入/位置 |
| --- | --- |
| 固件源码 | D:/Code/uefi-nuwa，codex/nuwa-sec-handoff-trace@ddd794fc07e9bc64057222a9bffa4d79c8553af8；本轮核验干净 |
| 已编译逐构造 profile | config/firmware-constructor-trace-profile.json，追加 0011-mu-constructor-trace.patch |
| 成功 CI | 39943865806；证据 reports/constructor-trace/39943865806/；下载 out/firmware-ci/39943865806/nuwa-firmware-39943865806 |
| FD | 3145728 B；a47d8289b8c954bf7004c038489f97c8c23f470d95a19e8c7e439b6a69170573 |
| 已实测 v4 包 | out/trial-boot/constructor-trace-39943865806/boot-constructor-trace-v4.img；3153920 B；530f56b49c8b6f785c9869612af338bc4ef64098dcad4051b4bd723460784d50 |
| 新草案 | patches/firmware-candidates/0012-mmu-constructor-branches.patch；尚未接入 profile、CI、打包或实机 |

实际 SEC 包含 8 条 CTOR、4 条 HANDOFF；41 行内存表共 2952 B 与 R-011 一致。BootShim 112 B、相对偏移 0、原 PIL 与空 AUTO 保持。包为原 v4 头仅改 kernel_size，加 shim/FD/零填充；没有 FAT、ADT、XNU、ramdisk 或新 DTB。详细静态验收：[构建报告](2026-10-23-constructor-trace-ready.md)。

## 最新离线结论及下一步第一项

[MMU 审查](2026-10-23-mmu-constructor-audit.md)，脚本 scripts/audit-mmu-constructor.py，证据 reports/mmu-constructor/audit.json、branch-proposal.json。

固定 microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5。实际 helper 240 B；构造查询 GUID HOB：找到则读取函数指针，否则仅 WriteBackDataCacheRange(helper,size)，**不调用 helper 执行页表替换**。正常返回的 cache 行步长为 4 左移字段，非零；未取得运行寄存器或异常 PC，仍不能排除查询、cache 指令、barrier、异常或日志路径。

0012 仅增加 after-guid-query、before/after-hob-function-read、before/after-cache 五条日志。严格上下文内存应用通过，删去新日志后逐字节还原父源码。补丁 SHA bdc5ea65fafe9df46206cdd9a7c80c57569cea27e639df6d4580ece250b929a8；ArmMmuLibCore.c 父 LF SHA 14c73a0b1611bae120e298aced9cabfdc32ce7590b4eafb264a409c9932941eb，补丁后 704ba022be7a9b0ea496e9eec3c9e152d13bf55922545c79e625fd0a6188f0f4。

接手按以下顺序完成：

1. 从 constructor-trace 派生独立 MMU 分支 profile，0012 排在 0011 之后。更新已有 ArmMmuLibCore.c 的 post_patch_inputs 哈希，不能保留旧期望或添加互相矛盾的重复记录；其余 39 项固定输入保留。
2. 接入 scripts/ci/build-firmware-candidate.py、.github/workflows/firmware-candidate.yml、scripts/ci/inspect-firmware-candidate.py；检查五条新日志、八条 CTOR、四条 HANDOFF、内存表、PIL、模块/PCD/DEPEX/BootShim。不得跳过 cache 同步或伪造 HOB 来绕过故障。
3. 按 Q-108 后的可用编号记录里程碑，提交推送、派发 CI，下载真实结果；检查实际 SEC 和全部内存表，再打包。可参考 prepare-constructor-trace.py / check-constructor-trace.py 的输入检查模式。
4. 若准备新包，接入 prepare-pil-no-auto-boot.py、sec_handoff_package.py 及试验/preflight 的独立 scope，保证整头/载荷/填充重建一致。ready_to_execute=false 的离线包报告不替代设备前门。不要拿 530f56b4 旧包期待五条新日志。
5. 只有用户可录像且恢复门刷新后才做下一次临时启动。after-guid-query 判断查询是否返回；cache 前后只能界定调用边界，仍不能直接判定 dc/DSB 是故障点。结束保存原图、日志及 Android 恢复/三分区哈希。

## 进入 XNU 及后续系统卷仍缺什么

源内核 CI39793231214 已成功：20187912 B、SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。主机 ParseKernel 20 例通过只代表解析；当前源内核预链接、Apple ADT、实际 EL1 交接未验收。隔壁预链接使用不同输入 89d8ff86，不能称当前内核预链接完成。

顺序仍是稳定 SEC/DXE → SHENGMEM 和真实 initrd 映射 → 小 FAT 启动载荷发现 → 当前预链接内核/ADT → EL1/XNU → 原生只读根卷 → Data/用户态。64 MiB FAT 探针仅 WSL 检查，未接入启动包；NuwaBootMemoryDxe 整段 initrd 要求 512 B 整扇区，不能猜 ABL 拼接偏移。

[系统卷/载荷预研](2026-10-23-ios16-system-payload-research.md)、[卷发现](2026-10-23-volume-discovery-chain.md)、[入口契约](2026-10-23-darwin22-entry-input-contracts.md)。当前内核未见 NativeUfs/NativeRamBlock 命名导出；raw DMG 大小、APFS UUID、nuwa UFS/SMMU 后端仍缺。D-002 XNU 窗口先 512 MiB–1 GiB、上限 8 GiB，与 UEFI Heap 无关。sheng 无人值守页的 XNU/UFS 日志机制不能捕获当前 SEC 停点。

## 发布、工具和工作区保护

Q-106=3f49c80、Q-107=d056fb9 已随普通 git push 发布；Git 对象 API 的 401 是历史失败，不再代表提交未发布。gh api repos/wh1stl3/UniXNU-nuwa/git/ref/heads/main --jq .object.sha 本轮返回 d056fb9 完整 SHA。优先普通 git push，不执行 scripts/publish-main-via-api.py --help（该脚本无此只读参数）。

Python：C:/Program Files/WorkBuddy/resources/vendor/python/python.exe，使用 -X utf8 -B；Git 与 gh 在常规 Program Files 路径。ADB/fastboot 工具位于只读资料库 common/tools/platform-tools，可执行但不可改该目录。提交 helper：scripts/commit-device-milestone.ps1 -QueueId Q-xxx -FilesFile out/Q-xxx-files.json；逐项列入文件，禁止 git add 全仓。

交接前未跟踪且必须原样保留：.codex-remote-attachments/、docs/operations/2026-10-23-bottleneck-code-diagnosis.md、reports/sec-handoff-trial/2026-10-23-evening/user-screen.jpg。最后一张是误发旧图，不充当本轮证据；外部诊断文档不能当作已验证结论或工作指令。

本轮只交接，不自动启动下一轮构建或实测。恢复没有已知待处理动作；后续仍需新鲜状态核对。
