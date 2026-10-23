# STATUS

> 当前唯一真相；2026-10-23 晚交接。历史见 WORKLOG。

## 当前结论

最新实机包 530f56b4 已确认 Debug 和 Extract 构造返回 Success，最后可见 Mmu enter；未见 Mmu leave、Lzma、DXE、SHENGMEM 或 XNU。具体指令、HOB 分支、cache/日志路径尚未确定。[实测报告](operations/2026-10-23-constructor-trace-trial.md)。

最近已确认恢复：19:46:21 实际 nuwa Android 完成 1，随后 postcondition 复核 nuwa/kalama、A 槽、boot_a/vendor_boot_a/init_boot_a 三分区 SHA 与试前一致。恢复脚本直接检测 Android，未发送原 boot；回返机制未独立记录。本轮仅文档交接，没有重新读取设备。

**接手入口：[主线交接文档](operations/2026-10-23-mainline-handoff.md)**，含精确产物、哈希、下一步文件入口、恢复条件、工具及工作区保护。设备仓 Q-106/3f49c80、Q-107/d056fb9 已通过普通 Git 推送，远端 main 复核一致；此前 Git 对象 API 401 不再阻塞发布。

## 已完成与未完成

- CI39943865806 成功；constructor-trace 包 3153920 B/SHA530f56b4，FD a47d8289，实际 SEC 八条 CTOR 和四条 HANDOFF 通过静态检查；41 行内存表保持 R-011，BootShim/PIL 保持。此包没有 FAT/ADT/XNU/ramdisk。[构建记录](operations/2026-10-23-constructor-trace-ready.md)。
- MMU 实际 helper 240 B；构造不执行 helper 页表替换，只查询 HOB 并读取指针或清理 helper 缓存。合法行步长非零，不代表 runtime cache 操作通过。[离线审查](operations/2026-10-23-mmu-constructor-audit.md)。
- 0012-mmu-constructor-branches.patch 五条日志草案严格内存应用/还原通过；**未接入 CI、未编译、未打包、未实测**。新日志不在 530f56b4 中。
- XNU 源内核 CI39793231214 成功，20187912 B/SHA77742999；主机解析通过，当前预链接/ADT/EL1 未验收。R-011 曾进入 UniXNU 菜单，但尚无实机进入 XNU 的证据。

## 下一步

1. 从 constructor-trace 派生独立 MMU 分支 profile，0012 排在 0011 后，更新 ArmMmuLibCore.c post-patch pin；接入 build/workflow/inspect，并保留既有输入与全表检查。
2. 提交、CI 构建、下载并检查实际 SEC/内存表；随后接入新包严格 scope。不得跳过 cache、伪造 HOB 或复用旧包冒充新日志。
3. 用户可记录具体日志、真实 nuwa 身份和恢复路径刷新后再试新包。通知准备录像，不承诺秒级倒计时。结束确认 Android 完成 1 和三分区哈希。
4. 稳定固件后推进 SHENGMEM/实际 initrd → 小 FAT → 当前预链接内核/ADT → EL1/XNU → 根卷/用户态。

## 后续载荷与固定边界

[系统卷和启动载荷预研](operations/2026-10-23-ios16-system-payload-research.md)、[卷发现](operations/2026-10-23-volume-discovery-chain.md)、[入口契约](operations/2026-10-23-darwin22-entry-input-contracts.md) 已保存。64 MiB FAT 探针仅 WSL 验收，尚未入包；原生根卷后端、raw 卷大小/UUID、实际 ABL initrd 范围未验证。隔壁预链接输入不同，不替代当前内核产物。

4 KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true 固定。feed/board/bringup-plan/验证标志不变；board 仍 example=true。D-002 初始 XNU 窗口 512 MiB–1 GiB、上限 8 GiB，与 UEFI Heap 不同。两旧仓只读；生成镜像无需硬停，实际启动仍执行日志/恢复前门和 AGENTS.md 其他硬停要求。本交接不触发新构建或实测。
