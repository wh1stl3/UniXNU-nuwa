# 26ef8efd 缓存交接候选实测

用户新鲜确认录像后已即时通知，单次临时启动并完成至少120秒USB观察。构建CI40005057158/source bdcf4a2，固定固件6176a82加0019；整包26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051。原始执行/恢复记录提交747d8fc，文档对齐772465b；后续收到五张用户原图，原样保存并计算SHA256，详见reports/hob-cache-handoff-trial/2026-10-24/screen-observation.json。

## 本轮画面事实

1. cache-after-mmu.png：before-mmu ok/count56；cache-handoff-before ok/count84；HOB-CACHE invalidate标记及EL1、line64可辨。其下紧接着是`[NUWA-HOB-STAGE] ok phase=after-mmu context=0x0 count=84`，再下是memory-peim-return ok/count85和memory status=Success。SCTLR完整十六进制数及头链hash不作低清强行转录。
2. fv-and-boot-audit.png：内嵌块设备0x400000/Success，FAT安装，BOOT-AUDIT registered Success；独立旧initrd卷路径Not Found仍存在，未阻止FV后备成功。
3. ready-to-boot-map.png：ReadyToBoot EL1、MPIDR0x81000000、CNTFRQ19200000；map6144B/stride48/version1、128描述符、17 conventional/merged；最大及write-back范围base0x8C0000000、bytes0x240000000（9GiB）。日志明确snapshot only/no window allocated or reserved，不能当OS分配证明。
4. volume-probe-menu.png：唯一NUWA VOLUME PROBE配置菜单，Volume config loaded动作。
5. no-os-usb-fallback.png：Not Found及USB无设备后备。用户另报告“最后进入充电界面”，没有充电界面原图。

因此本轮缓存维护标记→after-mmu检查→ReadyToBoot→配置菜单链路**实机通过**。这是一次试验的阶段结论，不等同根因唯一性、稳定性或OS执行。

## 明确的故障判断

**早期HOB故障首要判断：缓存交接遗漏，使非缓存写入的HOB在启用MMU/D-cache后被旧缓存内容遮蔽。当前对此判断的信心已显著高于映射错误或HOB创建算法错误，应以它作为主要修复方向。** 原因是基线最后CreateHob有效、after-mmu立即坏；本候选保留Heap和检查，只加入切换前HOB范围IVAC后，after-mmu检查成功且走到ReadyToBoot和菜单。旧缓存遮蔽是最能统一解释这组现象的机制，但单次试验、布局/时序混杂尚不能彻底排除，暂不宣布稳定修复。

公开机制：ARM64维护者Catalin Marinas说明，MMU/cache关闭时写入的数据在启用后仍可能被旧cache条目遮蔽（2026-10-24复核：[原始讨论](https://lists.infradead.org/pipermail/linux-arm/2020-August/000605.html)）；[Linux v6.12启动代码](https://github.com/torvalds/linux/blob/v6.12/arch/arm64/kernel/head.S)采用相应屏障/失效处理，固定源码审查见此前cache-transition-audit/public-source-review。公开资料支持机制，nuwa本轮对照支持定位；二者不替代重复实测。

次要候选仍为映射/属性变化、代码布局与时序导致的覆盖差异；如果后续同候选再现坏链，应先检查真实SCTLR/TTBR/TCR/MAIR及走表结果，不随机换Heap或删保护。最小证伪是后续在新鲜日志/恢复门下重复同候选并对比完整before/after链；本次仅归档不自动启动。

**最后无OS/充电的直接原因判断：诊断探针配置timeout=60、唯一动作action=exit，且未携带XNU/ADT/系统负载，退出后固件继续搜索而找不到OS。** 菜单及Not Found/USB后备画面与该配置完全吻合，不是本轮HOB再次失败的证据。充电画面来自用户报告，精确电源路径尚未追踪；“没有操作系统可启动”是本包设计范围，不能通过删除HOB守卫解决。

## 恢复与后续

recovery/postcondition确认原Android完成1、nuwa/kalama、槽_a及boot_a/vendor_boot_a/init_boot_a SHA与启动前一致，postcondition.at=2026-10-23T18:55:45.904383+00:00（北京时间02:55:45）。收到原图不代表执行了第二次启动；当前设备状态不由历史充电画面倒推。无flash/erase/改槽位。

本轮画面待办关闭；保持Heap/坏条目保护，后续转向真实OS负载运输、ADT与窗口实际分配的离线准备，不用9GiB快照直接改board/_verified。固件仓文档6770fb9已同步；实际构建仍固定6176a82。根因重复性和稳定性待验。
