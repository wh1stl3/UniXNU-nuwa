# STATUS

> **6b3e5bfd 单次实机文件校验通过**：照片显示 PASS exact length, EOF and SHA256 / exit Success。已恢复 Android完成1、槽_a、三分区SHA不变（北京时间18:09:48）。下一步转入内核执行前资格检查；尚未执行内核。

诊断改为固件内 NuwaFileAuditDxe 的一次性 ReadyToBoot 回调，自动只读 58335232 字节 READTEST.BIN 并验证完整 SHA-256；结果显示 30 秒后返回固件。无需选择菜单、Enter、键盘或 OTG。数据不执行，不调用 ExitBootServices。详见 [诊断记录](operations/2026-10-24-fv-file-audit.md)。

最终报告 reports/fv-file-audit/40080439083/package.json；镜像 out/trial-boot/fv-file-audit-40080439083/boot-fv-file-audit-v3.img，70266880 字节，SHA-256 **6b3e5bfd3a8e1d5a8e8abbda3268872a6fc69b287c144df70387012d46a41dc7**。64MiB 数据 FAT 只含固定文件和退出配置，无外部 EFI 应用或 XNU 启动项；xnu_included=true 如实标记 MachO 数据存在，kernel_execution_enabled=false。

完整 CI **40080439083 / dbbdc02247df0bba08183df97f3775286ef96271 success**；下载后独立复查 710 个 inventory 文件和 7 个模块，整包逐字节重建一致。FD52ab071e/3145728B 与首轮构建相同。首轮40078257763编译成功、原检查因 LTO 内联失败，失败证据保留；修正后检查真实 Ready 回调四次 BL 到 572B SHA 压缩体，并确认驱动专属 BaseCryptLib/OpenSSL 链接。19项软件协议场景及一次性回调、23项门控/拒绝回归通过。静态链接和软件执行均不等于目标固件密码实现或实机文件 SHA 已通过。

固件源固定 a155c495c863e06d400b515315e3b8f7791dc308；诊断 profile 为57输入/12补丁/15后哈希，原11保护补丁保持。完整 SEC7192fd3f3f37061ebaf466d2e98ef0e661abf29fe5b38eaa60cba99f0d40fd90 与此前实测缓存交接修复逐字节一致。Heap/HOB 坏条目保护、缓存维护、板值及原验签库/0x04拒绝策略均保持，默认 profile 不变。新增 DXE 调度和目标文件校验本轮单次实机通过，重复性尚未验证。

最新实测 reports/fv-file-audit-trial/2026-10-24-01/：自动固件回调打开唯一文件、普通pool分配、读取固定数据、精确长度/EOF/SHA256校验PASS并Success退出；数据菜单随后显示。三张原图及SHA存档，未收到完整连续视频文件。原图摘要略模糊，不逐字转录完整实际digest；固定源码仅在预期digest匹配后打印PASS。单次候选启动，随后用户按键回fastboot，临时原厂恢复。postcondition.at=2026-10-24T10:09:48.744209+00:00（北京时间18:09:48），Android完成1、槽_a、三分区SHA与本轮preflight一致。无flash/erase/改槽。首次命令把--evidence误传成目录，在设备动作前拒绝，修正后只启动一次。

工程判断：本轮将USB数据运输、FAT普通文件读取、约58MB普通分配和完整SHA链路提升为单次实机通过。上包18ebd838 Access Denied的首因仍排外部未签名EFI认证拒绝，保留原认证策略的固件内读取成功进一步支持；具体拒绝API/runtime SecureBoot值仍未捕获。认证/LoadImage路径与数据读取应分别处理，不宣称已唯一定位。[失败分析](operations/2026-10-24-file-audit-access-denied.md)。

USB v3 运输8177783e单次实测已通过独立64MiB卷/FAT：envelope result=1、块设备Success；偏移减64B等于历史vendor ramdisk长度，支持拼接路线，v4替代和重复性仍未对照。菜单本身不作数据读取证据。[运输记录](operations/2026-10-24-usb-v3-trial.md)。

上游已审查更新固定 UniXNU e553e467ebfe7642e9f483d3977a57066c6d1aef、21模块；固件40014018074和内核40015845083构建通过。内核bf14e530/20188216B为Darwin22.6.0/iOS16.0、64补丁、零未定义。分析预链接eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定和代码范围读回检查通过，但 **loadable=false**。完整初始化/回调/C++ ABI、真实ADT和实际分配的OS内存窗口未资格化，文件校验成功也不等于内核或iOS启动。ST FTS路线、身份和所有_verified保持原状。[集成](operations/2026-10-24-upstream-integration.md)、[AMFI分析](operations/2026-10-24-amfi-phase-and-slots.md)。

下一步先离线审计真实原生内核加载链、ADT及普通/连续内存分配要求，维护分析MachO loadable=false边界和初始化/ABI待办。不得把当前数据诊断PASS直接变成执行分析内核的许可；新候选另完成离线检查、日志/恢复条件确认并通知后再测试。原Heap/HOB保护、认证策略、板值和_verified保持。[交接](operations/2026-10-23-mainline-handoff.md)。
