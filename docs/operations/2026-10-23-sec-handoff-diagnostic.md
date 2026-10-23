# SEC HOB／构造边界离线诊断

本轮仅离线构建，留待晚上统一实测，无ADB/fastboot命令。新日志不是根因修复；屏幕最后一行不等于实际PC或唯一停机函数。

## 固定证据

- 旧R-011：CI39835052901，FD SHAaca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6；实际SEC SHA9f59f4473b6d2d09bf10ebcbdfa27df70ffb26ce0321c3b2635632687b81285c。
- reports/sec-handoff/actual-path.json保留原TE反汇编、link-map SHA414fa57f及真实调用；A710...是链接首选地址，不是采集的运行PC。platform-hobs日志之后可见入口HOB、提取器数组AllocatePool、后续GUID HOB与缓存操作，之后才是before-fv-decompress。不能用两条源码语句排除实际库调用或中断异常。
- reports/sec-handoff/library-dependencies.json逐文件保存microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5的SHA/行号及BSD-2-Clause-Patent许可。PrePiHobLib不依赖自己的构造函数，HOB列表通过PrePeiGetHobList／TPIDR取得；BuildGuidDataHob创建GUID HOB并复制数据。不能以DXE Heap总容量推导SEC HOB指针及可写边界正确。
- 实际BUILD_REPORT列出DebugLib、ExtractGuidedSectionLib、ArmMmuLib及Lzma构造函数；提取器构造涉及分配，MMU构造涉及GUID HOB和缓存操作。日志可能失效、后续显示接管或执行阻塞尚未区分。
- 同SoC UniXNU/uefi-sheng@329b473df1e53a3bfa64b2b39b79670c4c02279b的Sec.c SHA960823c3c59fd7cbf5f235468989bf4e06d8fef37658ec302c2228b611a1fb25，BSD-2-Clause-Patent，131/141/145行也是PlatformPeim→BuildGuidDataHob→ProcessLibraryConstructorList。只参考顺序，无nuwa运行证明，不复制板值；见same-soc-order.json。

## 最小改动

固件wh1stl3/uefi-nuwa新分支codex/nuwa-sec-handoff-trace@ddd794fc07e9bc64057222a9bffa4d79c8553af8，父1ccf760；只改Sec.c，保留调用顺序。补丁0010-sec-handoff-trace.patch记录：

1. before-entry-arg-hob list=%p：创建前HOB列表值。
2. after-entry-arg-hob data=%p：创建返回值，不增加指针解引用。
3. before-library-constructors：进入构造调用前。
4. after-library-constructors：调用返回后。

只记录返回值，无错误绕过、延时、构造重排或板级数值变化。既有before-fv-decompress等日志保留。GetHobList只读现有列表寄存器；新增DEBUG依赖原帧缓冲日志，仍可能受通道失效影响，不能将没有新日志自动判为阻塞。

source-local/source-publish.json确认全树和提交SHA与远程相同、原factory-heap分支未变。新profile从factory-heap严格派生，仅变源码提交与Sec.c输入SHA和说明；35项输入、两个已有补丁、board/feed固定值检查通过。旧profile保留，不能冒用旧包哈希。

## 构建与验收

命令：`python scripts/check-sec-handoff-profile.py`，35项静态输入检查通过；`python scripts/ci/inspect-firmware-candidate.py out/firmware-ci/39835052901/nuwa-firmware-39835052901 --publisher-name NuwaBootMemoryDxe --require-sec-trace --require-no-auto-abl --require-allocation-trace --allocation-profile factory-heap --output reports/sec-handoff/baseline-inspection.json`旧实际产物回归通过。

workflow firmware-candidate.yml新增sec-handoff选项；新profile必须核验四条新日志实际存在于SEC TE，同时保留旧ENTRY、工厂Heap、DXE分配日志、原PILDxe/空AUTO、PCD及四个加载器模块的检查。编译结果与下载检查另记，不把输入检查写为编译成功。新构建不含XNU负载、ADT或FAT，不承诺进入内核。

## 晚上实测计划与边界

构建检查通过后可离线准备唯一临时包，保存SHA及恢复依据。晚上用户在场、通知录像、刷新实际目标身份/恢复文件/分区基线后才允许启动。录像至少覆盖120秒并保留完整ENTRY→HANDOFF→DXE→菜单过程；若有具体失败，可提前记录并恢复，不为等待时长延迟恢复。以视频相对时间标注，不把USB ACK或枚举当执行日志；日志/恢复缺失则按AGENTS§3硬停。

本轮不新增实机成功，不改board/bringup-plan/feed/ADT或_verified。中午已恢复Android完成1是历史实测证据，不是今晚启动前门已通过。另一份未跟踪的跨设备诊断报告只视作建议：恒返Success和显示通道局限值得审查，但“真实卡点已确定”等因果结论不能据静态代码成立，固定地址持久日志也未取得恢复后保留与所有权证据；本轮不实施这些行为改动。
