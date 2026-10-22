# nuwa平台FDT与已链接驱动的ADT契约

## 输入与结论

只读分析本轮实际Android FDT f4636276与合并版内核77742999，不生成ADT、预链接、固件或板字段。源码ArmCpu SHA3c87b3bd617be5582a6a24ff797c359497ee9feaa702ee883ecee4270db21c9f、ArmDTPlatform SHA07f96a42bdd638022960f5fcaf9e3a07dd73a82c869a70815781cac6d4873b3b，与实际archive审查记录逐项相同；不是用另一版本源代码解释二进制。

实际内核_gIOKernelConfigTables指针解析到文件1178110处的589B catalogue，包含ArmCpu/IOPlatformDevice/score2000、ArmDTPlatform/IOPlatformExpertDevice/device-tree/score5000。ArmVirtPlatform personality也仍在catalogue，但该类不在本次强制链接库中；未因此把它当作已链接或实机平台。存在匹配描述不等于IOKit启动/匹配成功。

## 实机属性与目标契约

| Android实际声明 | 实际驱动消费 | 转换/验收门 |
| --- | --- | --- |
| /cpus八个CPU的reg为0、0x100、…、0x700，8B大端 | ArmCpu::probe取reg开头的本机序32位，device_type为cpu加NUL | 不能原样复制Android 8B reg；须经官方ADT工具编码，boot CPU/SMP执行仍未验证 |
| /soc/psci method=smc | ArmCpu::psciConduit读取/psci/method | 路径迁移，不把Android节点路径原封不动使用；当前次核启动仍opt-in |
| /soc/interrupt-controller@17100000，GICD 0x17100000/0x10000，GICR 0x17180000/0x200000，stride0x40000 | /arm-io/intc、compatible精确11B arm,gic-v3加NUL，reg四个native uint64、/arm-io/ranges三个native uint64 | Android父/soc的地址/长度各1cell（原reg16B），驱动要求32B，必须按目标ADT重新编码；不推导或写入新的地址 |
| /soc/timer arm,armv8-timer，clock-frequency声明19200000，interrupts原48B | ArmCpu使用cntvct_el0/cntfrq_el0与GIC INTID27 | FDT声明不证明实际CNTFRQ、EL权限或中断送达；不更改定时器/IRQ开关来宣称通过 |

实际构建仍为XNU_NATIVE_ARCH_TIMER=0、XNU_BOOT_PROGRESS=0；此次两库重链接刻意保留运行设置。后续必须审查首个计时器路径、provider初始化顺序、13项boot-progress和watchdog，不直接把这些开关翻成1，也不能用缺失provider空实现消除链接/运行错误。核验源码位置、原始属性hex、父cells解码和实际catalogue见reports/runtime-platform/live-dt-contract.json。

## 复核

```powershell
python -X utf8 -B scripts/audit-live-platform-contract.py --fdt out/live-nuwa-dt/live-dt-map-comparison/android-live.dtb --output reports/runtime-platform/live-dt-contract.json
```

这一步只清点输入与源码消费契约。board仍example=true，CPU/PSCI/GIC属性尚未写入正式配置，未制造已验证ADT或实际运行记录。Memory/owned window、donor身份、feed和_verified全部保持。

## 并行固件构建

重跑39805110487固定设备提交0b9dbd6、固件0a3a51a。安装从15:28:16Z到15:32:39Z成功，现进入真实构建步骤；只证明这轮依赖安装成功，不能称所有网络阻塞已解决。继续等待实际编译/链接/产物结果。
