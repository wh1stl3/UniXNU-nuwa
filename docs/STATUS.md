# STATUS

更新：2026-10-24 20:53（北京时间）。**nuwa实机已确认执行XNU入口、完成bootstrap页表生成，并到达开启MMU的指令前。iOS尚未启动。**

## 本轮结果

- 设备仓本轮基线cd5e987，原生内核CI40015845083/bf14e530加早期安全初始化预链接1aeebf13。固件仍用已验收CI40014018074/FD2d606985；固件仓codex/nuwa-sec-handoff-trace@a155c495未修改。
- 定位实际XNU入口保留BCM2837专用0x40000040写入（XNU_NATIVE_ARCH_TIMER=0）。软件对照：原版在该地址失败，单条NOP后到达开启MMU的MSR前。这是支持首因的诊断证据，不是唯一根因或正式定时器驱动。
- 新候选内核b1f532c14e3d9428c167fe9d541fdd5799e87445cd5aa37bcff1f2474565eda2，仅记录的93个原字节变化及追加单页RX探针；donor段保持。三个内核内阶段标记及早期异常ESR/ELR/FAR显示已实现，资格标志仍loadable=false/runtime_qualified=false。
- 16项软件执行检查、5项实际ParseKernel源体ASan/UBSan用例、ADT21节点/31检查及整包FAT导出验收通过。软件执行止于MMU开启前，不证明硬件翻译、缓存、中断或iOS。
- 包ab3c092b1ce5fa44475fbe40c3dc5b044963db8f0e664586178ff46ccf9ec149，70266880B，reports/xnu-first-entry/entry-probe-01.json；原固件/shim和USB-v3封装保持。

## 实机证据与恢复

用户本包录像/必要时按键恢复已确认；新鲜preflight唯一nuwa/kalama、Android1/A槽/三SHA基线通过。即时通知后单次fastboot boot，180秒USB观察完成，无flash/erase/改槽。

用户原图独立确认绿、蓝、黄、品红四色；入口首字14430E1E与候选patch一致：蓝行256为XNU入口，黄行352为页表生成后，品红行448在SCTLR_EL1开启MMU前。未见红色异常区。**品红是最远插桩位置，不是已定位故障PC；不证明MMU已开启或arm_init已执行。**

原图SHA5716899a991f424c9a2adb5e520e356a1cc147eb3dc191d740c64f09ebbd056a，约10MB，保存在忽略的out/trial-evidence/kernel-entry-probe-01/screen-01.jpg；元数据/判读存reports/kernel-entry-probe-trial/2026-10-24-01/screen-evidence.json。完整录像可后补，不阻断离线工作。

**20:53:19 postcondition确认恢复Android完成1、槽_a，boot_a/vendor_boot_a/init_boot_a三SHA与本轮试前完全一致；无需继续按键。** 本轮su只读查询实际成功，旧“su不可用”记录已过期。用户报告电源键可当Enter，按下后倒计时停止并完成此次启动，已留原话；未捕获EFI输入码，不再沿用实体键不能触发的绝对否定。

## 当前判断与下一步

旧SecurityLock已定位为Mu CapsuleRuntimeDxe的EBS软件锁审计，slot-retry-count是剩余次数；二者均不支持旧“Apple安全链失败/累计6次”的判断。见 [来源纠错](operations/2026-10-24-first-entry-provenance.md)。

本轮首要排查范围是**开启MMU到arm_init/更早C初始化**，也保留更后阶段无日志的可能。追加软件页表walk显示PC恒等映射、arm_init KVA、栈、VBAR、boot_args KVA五处有条目，不能替代实机MMU验收。下一步先离线增加MMU开启后与C入口的独立标记/异常保存，再准备新候选；不自动重复本包，不复用旧录像确认。

R-012已批准的dram_size=0x240000000和owned_memory_size=0x40000000保持，board仍example=true；其余TODO与donor/native完整ABI尚未解决。Heap/HOB、认证/AMFI策略、板值、所有_verified不变。

详细代码、SHA、软件与实机界限、恢复命令见 [本轮操作记录](operations/2026-10-24-kernel-entry-probe.md)；[主线交接](operations/2026-10-23-mainline-handoff.md)顶部有效，旧条目仅保留历史。
