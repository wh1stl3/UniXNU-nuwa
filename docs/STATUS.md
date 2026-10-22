# STATUS

> 当前唯一真相；更新：2026-10-23T02:07:20+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**R-010 A与D-021日志/恢复门已落地。首轮39826580758缺Mu嵌套依赖，已修复；重试39827372451已进入真实编译，首错为DxeMain.c缺两个私有锁函数声明。已把加锁封装留在Page.c，仍只改两文件、保持锁语义和原内存图；新patch bb8bf3ec及35项输入静态检查通过，待重跑。当前手机已只读确认nuwa Android完成1，尚未启动R-010候选。**

[本轮审查和候选](operations/2026-10-23-dxe-allocation-source-audit.md)，reports/dxe-allocation-audit/。上轮已证实到候选DXE但断言、未进入BDS/XNU；最后Android完成1为R-009恢复记录，本轮已只读重新确认Android完成1，尚无R-010启动结果。

## 本轮新证据与持久约定

当前AllocatePoolPages失败来自FindFreePages搜索最终为0；按类型bin/默认bin/全允许区、alignment、guard和资源提升约束尝试，失败不能仅解释为物理内存不足。源码声明69MiB是初始资源，不是运行空闲量；原厂209.75MiB有同机xbl_config证据，也不等于已批准修改。233页仅954368B。

固定Mu_Basecore@cfb93724与实际R-009子模块一致；缓存源码与git对象一致。0008候选只改Page.c/DxeMain.c，在首pool失败及最终ASSERT前记录参数/当前内存类型/空闲与最大块。Helper不分配、不改map，不跳过原错误和断言；最大块为未裁剪raw值。现有帧缓冲栈输出已有源码证据，但锁内flush时序影响/实际编译/运行仍未验证。补丁保留原CRLF，本次已增加仅两个固定raw哈希目标保留CRLF的CI接线，35项输入核验通过，原版已进入编译但私有锁调用报错；修订版编译待验证。

同SM8550固定来源已评估：sheng@0eb4514d也用209.75MiB且加其他bank、vendor条件门；fuxi@bb25ad75使用同大小但最小vendor=0且无既定真机运行证明。只借鉴结构和诊断方向，不抄nuwa无证据地址/驱动结论。用户要求已写入AGENTS.md§7：遇到难题主动评估同SoC UniXNU/UEFI仓库，并记录适用性/依赖/许可/验证状态，作为后续任务可读取的仓库记忆。

## 固定源码、CI与真实产物

| 项目 | 当前状态 |
| --- | --- |
| wh1stl3/UniXNU@76dd641 | 保留nuwa补丁的合并基座；8796内核CI39793231214成功，真实内核静态核验通过 |
| 设备仓 | board仍example=true，普通基座-D完整入口尚未打通；feed不变 |
| wh1stl3/uefi-nuwa | 当前codex/nuwa-no-auto-abl@2ab6827d；父910ee079的正确相对头保留，仅RAW输入改本地CFG并注释AUTO ABL；已发布，源码工作树干净 |
| 旧分支 | 稳定0a3a51a、SEC诊断5e4a8c8、相对偏移910ee079均保留，未重写历史 |
| 首轮39819452729 | 工具安装从Azure慢下载，360秒超时124；编译未开始，无固件产物，失败日志保留 |
| 重试39820752081 | 固定设备424513d、固件2ab6827d、pil-no-auto；全活跃APT源换源后工具安装47秒，CI总5m57s成功，665项产物/输入静态检查通过 |
| 新FD | 3145728B/SHA5ad08040a420608119d1d4cc72b2f54150d1fd33e111460fef711153aa2a3a45；四EFI及SEC标记/DEPEX/HOB验收通过 |
| 新配置/PIL | 实际RAW6930B/SHAdbc9ee6e…，AUTO空；PILDxe原PE SHA89e030af…保持；未删除驱动或改二进制跳过panic |
| shim/临时包 | shim112B/SHA8a3b5476…与R-008相同；v4包3153920B/SHAb60f96c0b69e8be6a36b3c74f919fb6a3c88eac7d0c8d3f785c26272cc3e864e，无新增DTB/ramdisk/FAT/XNU |

下载的665项清单/文件SHA与内容检查通过；服务端ZIP digest已记录，未独立核对完整ZIP摘要，不混为一谈。本机WSL只编译过shim，不是完整XNU本机构建通过。

## 已完成的R-009实机结果

2026-10-23 01:21:19开始唯一一次R-009临时启动，实际nuwa/kalama、Android完成1和fastboot产品/解锁/槽位先核对，按D-016重进bootloader隔离。Sending/Booting OKAY，15次fastboot采样均false；ACK只作命令接受。

用户回复“停在报错了”并提供清晰照片。画面有UniXNUDxe GUID29b950cf…和DarwinBoot GUID1b64af87…的discovered but not loaded；实际候选包含而安装原厂98PE清单不含这两个GUID，支持候选DXE执行归属。最后屏已越过此前AUTO ABL的立即终止位置，出现SPSS metadata加载失败、连续AllocatePoolPages失败、Security/Bds/Variable/Variable Write/Capsule/RTC架构协议缺失，最终ASSERT_EFI_ERROR(Not Found)、[DxeCore]DxeMain.c(581)。

**已实机观察到候选DXE执行，不等于完整DXE/BDS实机通过。** UniXNUDxe/DarwinBoot未加载，未到XNU。页面分配失败的根因未确定：没有本轮运行时可用map/空闲量/最大连续块或分配轨迹，不能直接说12GB不够、认定唯一驱动或直接扩heap/ADT窗口。

## R-009恢复记录（本轮未操作设备）

初次recovery.json因启动时无nuwa fastboot/ADB，只等待ADB后180秒超时，原始失败保留。用户按电源+音量下并明确“已回fastboot”；H-004已完成。单独recovery-after-keys重新识别nuwa/复位bootloader后，临时发送已验证Android备份boot SHAef558db2…，Sending196608KB/Booting均OKAY；**01:25:30确认实际nuwa/kalama sys.boot_completed=1**，postcondition再次确认。

boot_a/vendor_boot_a/init_boot_a全分区SHA与紧邻试前值相同；未flash/erase/改槽，enuma未作为目标。当前是此前自定义/rooted Android，非完整原厂恢复，既有A槽持久标志未修复。H-001独立按键演练及H-003可选完整首屏录像留后续，不阻塞本轮收尾。

## 下一步

1. 发布R-010私有锁封装修订并重跑dxe-allocation CI，按实际第一处错误处理；不扩heap，不修改board/feed。
2. 成功后下载真实产物，检查实际DXE核心日志标记、四EFI、SEC、原PIL与空AUTO、相对shim，再制作v4临时包。
3. 用户已确认可录像，启动前通知；实际动作前重新核对nuwa身份、具体日志通道和Android/fastboot恢复证据。一次受限试启动后恢复Android并确认完成1，实测另记。
4. H-001/H-003历史人工待办不作为离线阻塞；当前尚未执行R-010启动/刷写动作。见operations/2026-10-23-dxe-allocation-build-trial.md。

## 内核与后续目标

源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8，Darwin22/iOS16、4KiB段起始、五平台导出、零undefined、三archive hash和65348项donor指针零失败。完整NativePrelink/运行ABI仍未验证，历史payload输入仍CI15 a9e08c69，未自动切换。[内核核验](operations/2026-10-22-merged-kernel-artifact-validation.md)。

608B CommandLine/0x2e0 boot_args修复已实际编译链接DarwinBoot EFI，运行ABI未验证。目标ADT/真实provider/定时器/watchdog/13回调仍待验收，ARCH_TIMER/BOOT_PROGRESS仍0。Android DT不能直接当Apple ADT；ramoops与FD保留区重叠，未占作日志区。入口/BDS之后还需完整负载，不能把本轮固件诊断当内核启动。

## 固定边界

board/feed/内存图及所有_verified不变；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，硬上限8GiB。未知板值不编造，不借其他donor的prelink数值。两旧仓只读；Git/GitHub/workflow持续授权，R-010 A已批准，按D-021设备日志/恢复门推进。
