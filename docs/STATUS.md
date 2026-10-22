# STATUS

> 当前唯一真相；更新：2026-10-22 19:06（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**本仓四EFI/FD/BootShim已编译并静态验收；首个v4固件入口试启动包已准备、未执行。nuwa当前已通过临时加载原厂boot回到Android，boot_completed=1；持久A槽启动状态尚未修复。** DT/initrd静态核对已完成当前Android观测范围，新候选的物理放置/DT访问/DXE运行仍未验证。

- 固件CI [39764322744](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39764322744) success；四EFI真实进入FD且独立/内嵌hash一致，SEC/HOB/PCD/DEPEX/FV/shim检查通过。FD3145728B/SHA a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83；BootShim112B/SHA9346a527…。R-004 A完成。[构建报告](operations/2026-10-22-firmware-candidate-build.md)。
- 源内核CI15 [39755850870](https://github.com/wh1stl3/UniXNU/actions/runs/39755850870)真实链接ArmCpu/ArmDTPlatform、五导出/零undefined；20187888B/SHA a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a，65348个donor指针零缺失。当前试启动包不含XNU，完整ABI/执行未验证。
- 候选out/trial-boot/firmware-v4/boot-firmware-v4.img：3153920B/SHA12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9；v4原厂头仅改kernel_size，raw shim+FD，无附加DTB或新增FAT。静态容器检查通过，ready_to_execute=false表示运行条件未验收。[恢复/映射/试启动报告](operations/2026-10-22-trial-boot-preflight.md)。

## 实机与映射事实

- 最初ADB为enuma/SM8250，只读元数据未用于nuwa输入。随后fastboot确认nuwa、unlocked=yes、slot=a；fastboot reboot又回fastboot，A同时successful=yes/unbootable=yes。用户说明此前另一对话推送镜像、未按音量键；不把这当作根因证明。
- 临时fastboot boot原厂nuwa备份ef558db2…被ABL接受，DT确认nuwa/kalama/KALAMA且Android boot_completed=1。当前boot_a/init_boot_a整分区hash与原始备份/锁定记录相同；未flash、未改槽位。不能把临时恢复扩大为持久启动已修复，或新固件实机通过。H-001按键恢复演练仍open；H-002 unlocked核验已完成。
- nuwa当前boot/init_boot/vendor_boot均v4，原厂v4备份临时启动有真实证据。当前Android initrd[0xb5fb2000,0xb7fff1d4)处于静态Kernel保留区[0xa8000000,0xb8000000)，源码映射WB/XN；该事实不替代新候选ABL布局。DT实际地址、SEC访问及initrd生命周期仍未验证。
- RamManager会将EFI图中空隙加入Conventional；发布器不保留新initrd。固定上游DT自带旧initrd属性、默认ramdisk5B，不直接复用为有效运行地址。原厂cfg NoMap/AddDynamicMem、209.75MiB DXE Heap与参考C表有差异；未继承高地址6GiB或整表策略。

## 下一步

1. 对准备好的v4固件入口候选核验ABL实际放置、BootShim/SEC入口、DT访问与DXE/BDS结果；按用户已授权临时试启动范围推进，保留原厂boot恢复路径。EFI ResetPlatformSpecific只回退PSCI普通reset，不保证回fastboot。H-001实体键项记待办继续软件项。
2. 新FAT initrd加入前落实映射/保留与RamManager交互。当前包只有固件，Android ramdisk不能视作FAT负载；不能因容器检查通过宣称UniXNU菜单/配置读取成功。
3. CI15 runtime crypto/pthread provider、ARCH_TIMER/startup/GIC/PSCI、13项boot-progress、watchdog scratch及NativePrelink布局/12处Libm编码继续审查；旧CI13 plan不能直接继承。XNU负载另立实际验收门。
4. 若要修复A槽持久启动，先核实具体槽位动作及授权，不在临时固件测试时顺带改动。board/bringup-plan内存/基址和_verified继续按原规则，未知值TODO。

## 既定边界与证据

board/feed不变、example=true；4KiB，iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3，ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5、上限8GiB。两个旧仓/源树只读，构建产物留out；Git/gh/workflow已授权，不强推、不改写历史。

本轮reports/trial-boot-preflight含原始命令、目标身份、恢复、启动头/分区hash、静态映射和包检查；config/trial-boot-candidate.json是审计清单而非board schema。新固件未QEMU/实机执行，未置_verified=true。内核仍为macOS CI构建，WSL完整内核构建未验证；源CI运行开关不变，根卷与iOS用户态未验证。
