# Darwin22 入口输入与 ADT 契约：离线验证

## 当前结果和边界

本轮继续主线的独立离线工作，没有设备命令、固件重编、boot.img或目标nuwa ADT生成，没有修改board/feed/bringup-plan或任何验证标志。三个问题分别取得证据：当前源内核能否通过固定加载器的文件格式解析、ADT哪些占位符随负载条件变化、已有nuwa快照能提供哪些CPU/GIC输入。

**固定DarwinBoot的实际纯解析函数在Linux主机上执行：20个ADT正反例均得到预期结果，当前20187912B内核通过ParseKernel。** 这只属于主机解析/静态检查通过，不是UEFI、QEMU、EL1交接或XNU实机通过，尤其不证明完整NativePrelink ABI。

证据目录 `reports/darwin22-input-contracts/`；解析最终结果为 `uefi-types-results.json`，其余为 `readiness.json`、`cached-cpu-dt.json`、`official-placeholder-context.json`。

## 实际解析函数，而非另写一份Python判据

脚本 `check-darwin22-input-contracts.py` 先以只读git show核对UniXNU75bc13dd的DarwinBoot.c及WindowSize.h，在内存严格应用既有0005 Darwin22 boot_args补丁，并核对编译配方中的post-patch SHA。ParseKernel和AdtNode函数文本原样送入本机WSL clang14的标准输入，不在仓库落地上游源码副本。

主机适配仅提供UINT8/32/64、LP64 UINTN、8位BOOLEAN和内存/字符串原语；不提供假的硬件驱动。编译使用-Wall/-Wextra/-Werror及UBSan，生成的Linux ELF和合成输入仅留忽略的out。本轮修正了初稿主机适配层缺少ZeroMem/CHAR8定义的问题；未为此修改被测DarwinBoot函数。最终报告记录完整编译参数、stdin SHA、函数SHA、各次执行stdout和stderr。

复现（工作目录和报告路径须为新路径）：

```powershell
python -B scripts/check-darwin22-input-contracts.py --work out/darwin22-input-contracts/host-probe-uefi-types --output reports/darwin22-input-contracts/uefi-types-results.json
python -B scripts/audit-kernel-entry-readiness.py
python -B scripts/audit-cached-nuwa-cpu-dt.py
```

覆盖内容：无可选sidecar、RAMDisk/PackedRAMDisk/TrustCache槽位，256MiB与8GiB解析边界、越界/非2MiB对齐、窗口属性重复/宽度错误/节点位置错误、槽位长度错误/两种ramdisk名冲突、重复name、非NUL结尾键、截断、尾随字节及把Linux FDT输入Apple解析器的反例。20项全部符合预期，最终运行无UBSan报错。这些合成树根名明确为parser-fixture-only，没有平台完整节点，不可当nuwa ADT或内核可启动证据。

当前内核SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8，被同一ParseKernel接受；10个非零映射段、虚拟跨度21037056B。文件本身有18条LC_SEGMENT_64，零尺寸段不计入上述10段。接受文件不代表预链接组件初始化、安全扩展或ABI已合格。

## 占位符是逐输入契约

回查已保存且哈希一致的[官方设备树原文](https://unixnu.com/zh/porting/device-tree)：它说“每个输入都需要占位符”，并非无条件同时生成三个槽位。原摘录是压缩表述，本轮没有改写摘录；根据原文及固定加载器补足执行条件。网页读取工具本轮不可用，使用2026-10-22已抓取的官方HTML，SHA a96954fbbad28255c1df47c1c89142fcf4d92f2e5382fa9a24e6ccec6699d6d1，缓存校验见official-placeholder-context.json。

| 输入 | 固定Boot()源码条件 |
| --- | --- |
| dense ramdisk | 需要/chosen/memory-map下唯一RAMDisk槽，长度16，初始两个u64为0；有槽却没提供ramdisk返回EFI_UNSUPPORTED |
| packed ramdisk | 对应PackedRAMDisk并满足实际输入为packed；RAMDisk和PackedRAMDisk不能并存冒充两个独立载荷 |
| trustcache文件 | 需要对应16字节零槽，文件通过ValidTrustCaches；只有槽没有文件同样返回EFI_COMPROMISED_DATA |
| darwinboot-memory-size | /chosen下唯一8字节值，256MiB–8GiB、2MiB步进；本轮仅编码边界测试，不申请该大小内存 |

上述Boot()调用方条件由固定源码核对，没有执行完整Boot()，与20项AdtNode本体测试分开记录。D-002的实际bring-up512MiB–1GiB、最大8GiB不变，256MiB测试只验证解析器下界。

## 当前内核的真实符号与平台输入

独立读取当前内核LC_SYMTAB，过滤STAB调试记录再判断外部符号：未解析外部符号0，五个ArmCpu/ArmDTPlatform观测导出存在。三份静态库源文件与CI编译记录SHA相同；ArmCpu、ArmDTPlatform已链接，ArmVirtPlatform只是构建了archive，不说成已在本内核运行。

13个boot_progress回调均未定义在当前内核，nuwa源码也没有对应定义；现有make参数明确XNU_BOOT_PROGRESS=0、XNU_NATIVE_ARCH_TIMER=0，因此这不是当前链接失败，而是尚未完成的功能启用/验收。没有为了取得这些名字而加入空实现或打开开关。

同SoC参考固定UniXNU-sheng@a599a1a8a92093b5077543e071b72130769eb325的BootProgress.c、BootFaultProbe.c、BootWatchdogPolicy.c（MIT），记录SHA及定义行号。它们可作为真实诊断实现来源，但尚未适配编译为nuwa Darwin22对象。BootWatchdogPolicy是写scratch Data中launchd策略的临时用户态政策，不是硬件watchdog驱动，不能用该符号代替硬件后端验收，也没有执行文件写入。

匹配本次编译SHA的ArmDTPlatform实际configure要求/cpus、/arm-io、/defaults、/options，并要求/chosen里4字节nvram-bank-size及非空nvram-proxy-data；IODTNVRAM的完整CHRP检查仍不能由这两个形状检查代替。ArmCpu还要求CPU device_type为带NUL的4字节cpu、至少4字节reg、/arm-io的24字节ranges及/intc的32字节reg和11字节arm,gic-v3字符串。

当前下载的内核产物没有dSYM，也没有内嵌__debug_*节；完整编译boot_args类型证据仍来自历史CI15，不宣称本轮已重新完成当前内核的DWARF类型验收。608B/0x2e0修正已进入实际固件的既有证据保持，不以本轮格式检查扩大为完整ABI通过。

## 从已有nuwa快照取得的板级输入

源为09点恢复后Android FDT，SHA e7217b1575c7a7c2ca4bd758ab7fc20f580533cae4ea85631608997fede51e1d，原blob仍只在out。本轮不读取设备，不把此快照认作候选ABL x0。

| 项目 | 快照中实际声明 | 使用边界 |
| --- | --- | --- |
| CPU | 8个，reg依次0、0x100、…、0x700 | 是快照物理affinity输入，不擅自改成0…7；与XNU编号映射仍需核对 |
| GIC | /soc/interrupt-controller@17100000，arm,gic-v3；两段reg及父ranges均已记录 | 父bus一地址cell/一size cell，已按显式root映射解码；尚不输出Apple reg/ranges |
| redistributor stride | 8字节大端字段，声明0x40000 | 固定ArmCpu支持8字节该属性及此值；未来转换必须保留语义，不能复制另一板或QEMU默认值 |
| timer | /soc/timer，arm,armv8-timer，声明19200000Hz，原始interrupt cells保留 | DT声明不等于已读取CNTFRQ，更不证明中断能送达 |
| PSCI | /soc/psci，arm,psci-1.0，method=smc | 声明不是固件调用成功证据，不用QEMU的hvc代替 |

这些值仅进入带来源的报告，没有修改board、内存窗口、donor身份或生成目标ADT。GICD/GICR选择与所有权、CPU注册映射、中断/计数器/PSCI运行行为仍列TODO。

## 下一步

卷链路仍需SHENGMEM候选日志；已有离线工作已把它之外的条件分开。后续可针对新取得的CPU/GIC输入审查XNU编号与ADT转换规则，再形成真实目标ADT生成器的候选方案；未确认部分继续TODO。NativePrelink的donor组件运行ABI、安全初始化、13回调及硬件watchdog仍是独立验收项，不把主机解析通过写成已进入XNU。
