# STATUS

> 新候选 **6b3e5bfd** 已完成完整 CI 与下载产物独立验收，尚未实机启动。下一步确认本轮录像和恢复条件，再通知用户并临时启动。

诊断改为固件内 NuwaFileAuditDxe 的一次性 ReadyToBoot 回调，自动只读 58335232 字节 READTEST.BIN 并验证完整 SHA-256；结果显示 30 秒后返回固件。无需选择菜单、Enter、键盘或 OTG。数据不执行，不调用 ExitBootServices。详见 [诊断记录](operations/2026-10-24-fv-file-audit.md)。

最终报告 reports/fv-file-audit/40080439083/package.json；镜像 out/trial-boot/fv-file-audit-40080439083/boot-fv-file-audit-v3.img，70266880 字节，SHA-256 **6b3e5bfd3a8e1d5a8e8abbda3268872a6fc69b287c144df70387012d46a41dc7**。64MiB 数据 FAT 只含固定文件和退出配置，无外部 EFI 应用或 XNU 启动项；xnu_included=true 如实标记 MachO 数据存在，kernel_execution_enabled=false。

完整 CI **40080439083 / dbbdc02247df0bba08183df97f3775286ef96271 success**；下载后独立复查 710 个 inventory 文件和 7 个模块，整包逐字节重建一致。FD52ab071e/3145728B 与首轮构建相同。首轮40078257763编译成功、原检查因 LTO 内联失败，失败证据保留；修正后检查真实 Ready 回调四次 BL 到 572B SHA 压缩体，并确认驱动专属 BaseCryptLib/OpenSSL 链接。19项软件协议场景及一次性回调、23项门控/拒绝回归通过。静态链接和软件执行均不等于目标固件密码实现或实机文件 SHA 已通过。

固件源固定 a155c495c863e06d400b515315e3b8f7791dc308；诊断 profile 为57输入/12补丁/15后哈希，原11保护补丁保持。完整 SEC7192fd3f3f37061ebaf466d2e98ef0e661abf29fe5b38eaa60cba99f0d40fd90 与此前实测缓存交接修复逐字节一致。Heap/HOB 坏条目保护、缓存维护、板值及原验签库/0x04拒绝策略均保持，默认 profile 不变。新增 DXE 调度和目标文件校验仍待实机确认。

最近真实手机结果仍为18ebd838外部 EFI 条目返回 Access Denied。首要判断是外部未签名应用被实际固件认证策略拒绝，置信较高；具体拒绝 API/runtime SecureBoot 值未捕获，不作唯一根因证明。此次通过既有固件链内诊断验证文件读取，不关闭策略或修改信任库。最近恢复证据时间 **2026-10-24T08:14:06.606976+00:00（北京时间16:14:06）**，nuwa/kalama、Android完成1、槽_a、boot/vendor_boot/init_boot 三分区 SHA 与试前一致。之后无新设备动作，不冒充当前查询。证据 reports/file-read-audit-trial/2026-10-24-01/；[失败分析](operations/2026-10-24-file-audit-access-denied.md)。

USB v3 运输8177783e单次实测已通过独立64MiB卷/FAT：envelope result=1、块设备Success；偏移减64B等于历史vendor ramdisk长度，支持拼接路线，v4替代和重复性仍未对照。菜单本身不作数据读取证据。[运输记录](operations/2026-10-24-usb-v3-trial.md)。

上游已审查更新固定 UniXNU e553e467ebfe7642e9f483d3977a57066c6d1aef、21模块；固件40014018074和内核40015845083构建通过。内核bf14e530/20188216B为Darwin22.6.0/iOS16.0、64补丁、零未定义。分析预链接eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定和代码范围读回检查通过，但 **loadable=false**。完整初始化/回调/C++ ABI、真实ADT和实际分配的OS内存窗口未资格化，文件校验成功也不等于内核或iOS启动。ST FTS路线、身份和所有_verified保持原状。[集成](operations/2026-10-24-upstream-integration.md)、[AMFI分析](operations/2026-10-24-amfi-phase-and-slots.md)。

下一轮使用绿色CI40080439083报告，不沿用旧包录像确认。启动前新preflight与最近恢复证据核对、唯一nuwa/kalama、至少120秒可录像及按键恢复条件；明确通知后只临时启动。采集 NUWA-FV-FILE 的 read/actual SHA/PASS/final/exit 画面，结束恢复Android完成1并复核三分区哈希。不flash、不erase、不改槽位。[交接](operations/2026-10-23-mainline-handoff.md)。
