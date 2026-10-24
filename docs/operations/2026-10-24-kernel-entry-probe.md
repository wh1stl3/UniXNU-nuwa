# XNU 入口探针01：排除BCM2837 MMIO并加入内核内阶段证据

2026-10-24，北京时间20:4x。承接 cd5e987 的日志归属纠错；用户要求“继续，尽量进入内核”。

## 首要故障判断

**当前首要候选是未排除的 BCM2837 专用寄存器写入（置信中高）。** 固定预链接内核1aeebf13的 `_start_first_cpu+0x2d0` / VA `0xfffffff0073c732c` 为 `str w1,[x0]`；前序实际指令算出 `x0=0x40000040+(MPIDR.Aff0*4)`、`w1=0xf0`，位于开启MMU前。原始XNU start.s:689起明确标为BCM2837的Core Timers路由；nuwa为SM8550，不可把该树莓派外设地址作为本板寄存器使用。

上游已提供 [architectural-timer-entry.patch](https://github.com/wh1stl3/UniXNU/blob/e553e467ebfe7642e9f483d3977a57066c6d1aef/patches/xnu/architectural-timer-entry.patch)，只有 XNU_NATIVE_ARCH_TIMER=1 才排除此块。本次CI40015845083的 kernel-make-command.json 实际为0。因此“源码已含修补”不等于产物已排除错误访问。参考为相同UniXNU实现；同SoC sheng检索未发现更具体的该入口修正，未照抄其板值或定时器资源。

支持：Unicorn 2.1.4以本次实际58MB Mach-O、同一高位物理装载基址和boot_args ABI执行，原版在该4字节写入处报未映射地址0x40000040。仅将这一条写入改为NOP的对照可继续到SCTLR_EL1开启MMU的指令前。

反对/限制：软件夹具只映射RAM和framebuffer，不模拟nuwa地址译码、总线、EL2/EL3、缓存、MMU翻译或看门狗；未映射异常不是实机异常。尚不能断言这条是唯一根因，也不能排除DarwinEnter缓存/关MMU尾部或XNU其他入口故障。备选顺序：交接尾部/首条取指；MMU开启后地址与CPU特性；后续ABI/平台初始化。旧SecurityLock归属不能作为AMFI/SEP故障依据。

## 最小候选

源输入：out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho，SHA256 1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6。

生成脚本 scripts/build-kernel-entry-probe.py；本仓自写汇编 package/entry-probe/entry-probe.S（BSD-2-Clause-Patent）。不复制上游源码到设备仓。固定原版哈希/原始指令前置条件，新增单页RX段并验证load-command padding确实未使用；原入口PC不变，仅将入口第一条分支导向有界诊断后返回原start_first_cpu。标记不使用栈、不调用固件、不改x0-x8/x18-x30的活跃寄存器。硬件访问只从原boot_args Video字段读取已交接framebuffer，不引入猜测地址。

- 行256，蓝色：实际XNU __start 分支及诊断入口已执行。
- 行352，黄色：bootstrap页表已生成，准备设置翻译控制。
- 行448，品红：经过原BCM块（专用写入被NOP），尚未执行开启MMU的MSR。
- 行544，红色：原物理LowExceptionVectorBase的16个死循环入口转入异常显示；其后三行分别为ESR_EL1 / ELR_EL1 / FAR_EL1，每行16个十六进制字符。

每条色带32行，分别保留，原DarwinBoot绿色条不当作内核证据。异常显示只覆盖物理早期VBAR阶段，后续虚拟向量不改。无framebuffer/几何不合格跳过色带；异常日志几何不合格仍停在原有同类死循环。没有添加复位、分区写入、关闭认证或修改AMFI。

原文件仅93字节发生变化（2处头部结构、20处native指令），追加4096B诊断页；所有PRELINK/PLK donor段逐字节保持。BCM写入仅4字节NOP，不启用尚未资格化的native timer/interrupt功能；今后正式源码构建应通过上游真实架构定时器与ArmCpu提供者接入，不把此诊断NOP当正式驱动。

候选SHA256 **b1f532c14e3d9428c167fe9d541fdd5799e87445cd5aa37bcff1f2474565eda2**，58339328B。仍loadable=false/runtime_qualified=false，未升格资格标志。新增诊断段不是board物理基址或内存声明修改。

## 离线验收

- reports/kernel-entry-probe/2026-10-24/build-v3.json：固定输入、22处精确patch、源码/编译命令、donor保持和段范围。
- software.json：16项软件执行检查通过；原版失败和单条NOP对照、三个色带、进入SCTLR写入前、活跃寄存器完全一致、bootstrap页表哈希一致、boot_args无修改、空framebuffer不影响控制流、强制早期向量三寄存器的绘制结果经独立像素采样解码一致。不是QEMU或实机通过。
- loader.json：固定DarwinBoot ParseKernel源体在宿主ASan/UBSan下执行，原版和新候选接收，重叠段/命令越界/文件越界3负例拒绝，共5项符合预期。不是完整EFI模块执行。
- adt.json：21节点/31检查，0失败；与旧树变化来自生成器明确规定的新random-seed，内存/身份/窗口参数保持。
- scripts/kernel_entry_probe_inputs.py 将包绑定build与software报告哈希，并重建所有原字节修改，拒绝未记录修改、重叠patch或资格标志变化。打包后再次从最终FAT导出内核/ADT并核对哈希。

初次汇编尝试的绝对分支equ被clang拒绝；改为ELF链接器绝对符号重定位后编译成功，没有忽略汇编错误。最终发布候选为03目录；前两次中间物均在忽略的out中。

## 实机包与当前过程

包报告 reports/xnu-first-entry/entry-probe-01.json。镜像 out/trial-boot/xnu-entry-probe-01/boot-xnu-first-entry.img，SHA256 **ab3c092b1ce5fa44475fbe40c3dc5b044963db8f0e664586178ff46ccf9ec149**，70266880B。FD与shim完全沿用原已实测版本：FD2d606985/CI40014018074，shim8a3b5476；没有新固件CI或固件仓改动。独立FAT/readback和USB-v3封装校验通过；菜单明确显示 XNU ENTRY PROBE 01 - BLUE YELLOW MAGENTA。

用户对本包确认“可以，现在准备录像，也能按键恢复”，要求连续≥180秒并持续到Android；新鲜preflight确认唯一nuwa/kalama、Android完成1/A槽、boot/vendor_boot/init_boot SHA与原基线一致。**本次su只读查询实际成功，旧“su不可用”描述不再作为当前事实。**

即时通知后已单次fastboot boot；ACK=0只代表接收。记录 reports/kernel-entry-probe-trial/2026-10-24-01/{preflight,launch}.json。启动开始2026-10-24T12:45:53Z（北京时间20:45:53），正在180秒USB观察，色带/异常原图录像及恢复闭环待补；无flash/erase/改槽。不据USB状态宣称实机进入内核。

续接只读取本轮证据与恢复：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-01.json --evidence reports/kernel-entry-probe-trial/2026-10-24-01/recovery.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/record-nuwa-trial-state.py --before reports/kernel-entry-probe-trial/2026-10-24-01/preflight.json --output reports/kernel-entry-probe-trial/2026-10-24-01/postcondition.json
```

不自动再次启动。需画面确定最远标记；若用户需按键恢复则记录并继续离线分析，不把等待人工恢复当主线结束。待恢复完成后追加真实时间和三SHA结果。


## 本轮实机观察更新

180秒USB观察已完成（ended_at=2026-10-24T12:49:12.205715Z，北京时间20:49:12）。用户明确报告“看到了绿 蓝 黄 品红 四条色带”；其原话已存screen-observation.json。**这是本候选XNU入口执行、bootstrap页表生成及到达开启MMU前的用户实机证据**，不再只依赖DarwinBoot绿色条。原图/录像尚未交付，尚未独立核对像素；无MMU已开启、C初始化、iOS或稳定性结论。

电源键：用户补充实机按下后倒计时停止并能完成本次启动。尊重本次现场观察，撤回旧“电源键不能作为Enter”的绝对判断；输入码与触发路径未捕获，倒计时停止本身也可由取消计时路径产生，后续按实测记录而不猜映射。

恢复程序已启动，等待可识别的nuwa Android/fastboot。已通知用户若仍停在诊断画面先保存录像，再按电源＋音量下；若已经回Android无需按键。不因等待人工恢复停止离线定位，不启动第二候选。


## 原图及恢复闭环完成（北京时间20:53:19）

用户提供3072×4096原图，10337304B、SHA256 5716899a991f424c9a2adb5e520e356a1cc147eb3dc191d740c64f09ebbd056a。已独立目视确认本包菜单、绿/蓝/黄/品红完整色带，未见红色异常区；入口首字14430E1E与候选分支patch一致。原图约10MB，按仓库大二进制约定保存在忽略的out/trial-evidence/kernel-entry-probe-01/screen-01.jpg，不向Git加入大图；可追踪的screen-evidence.json记录原图路径/长度/哈希及读数。完整录像文件仍未交付，原图足以确认本轮三个标记。

recovery.json确认回到Android完成1；postcondition.json时间 **2026-10-24T12:53:19.418885Z（北京时间20:53:19）**，唯一nuwa/kalama、Android1、槽_a，boot_a/vendor_boot_a/init_boot_a三SHA与本轮preflight完全相同。没有flash/erase/改槽，无需继续按键。本轮设备动作已闭环，不自动再启动。

本轮证明：原XNU入口第一分支已执行、bootstrap页表生成后路径已执行、修正后的BCM块已越过并到达SCTLR_EL1开启MMU前。**仍未证明：MMU开启成功、arm_init/C初始化、定时器中断、完整ABI、用户态/iOS。** 品红是最远已插桩位置，不是已定位故障PC；无红条不排除随后切换到虚拟向量后的异常。BCM专用写入首因获得支持，但因同时新增探针，不写成唯一根因或稳定修复。

追加软件页表核对：scripts/audit-entry-probe-pagewalk.py读取实际执行模型的TCR=0x22a51a251a（T0SZ/T1SZ=26，需按38位输入的初级表8位索引解析）；PC恒等映射、arm_init的KVA、栈、VBAR及boot_args KVA的五处软件页表均有条目，报告pre-mmu-pagewalk.json。这不是实机TCR或MMU验收，不能排除切换时硬件/权限/缓存问题；下一轮优先增加开启MMU后/arm_init的独立可观测标记与异常保存。首次scratch页表读取因API元组顺序和默认39位索引不适配而无效，已按Unicorn cpr_read接口及实际TCR修正后重新产生报告，未把scratch负结果当根因。
