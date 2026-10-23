# 当前内核预链接分析候选（离线）

## 本次进展

固定UniXNU75bc13dd NativePrelink工具以只读git对象在内存加载，设备仓仅提交一个常量池补丁，无上游源码副本。原工具/补丁/补丁后完整SHA见config/native-prelink-analysis-profile.json。BSD-2-Clause-Patent，使用现有native_prelink.py/emit_prelink.py，不重新实现绑定器。

当前源内核77742999与同一iPhone donor2ec297ba生成分析候选SHA5a128fb282009fa7f24fc35574d2199baa010edb650c50c5f903b8351e61f5e6，58335232B，虚拟跨度74174464B。重新计算41095项kernel与24253项component绑定（共65348），发射后逐项读回目标一致；30段donor可执行代码和native可执行字节保持完全相同。完整大JSON与二进制留out/native-prelink-current/analysis，不提交。精简清单见reports/native-prelink-current/emission.json。

## Libm 12处拒绝的处理

12处全部在Libm [0xfffffff005b8c054,0xfffffff005b8c51c) 的1224B常量区域。证据不依赖“不是已知函数入口”：前一指令RET；后4B填充、下一函数STP/MOV；代码ADR/LDP读取64项16B查表，LDR读取scalar，ADR/LD1读取80B系数。完整前缀+1224B SHA12d22dca要求精确相同，Libm内唯一匹配。选中模块的直接分支与原始重定位指针表未发现指向该区域的入口。

补丁仅向既有MATH_LITERAL_POOLS增加一项完整指纹，不新增按地址/单条指令或入口oracle的豁免，不重写任何指令；其他外部指令仍拒绝。4项测试覆盖完整池接受、前缀不变而中间单字节变化拒绝、池外外部指令拒绝、无常量池的未知外部指令拒绝。静态证明有边界：模块无LC_DATA_IN_CODE/LC_FUNCTION_STARTS，直接分支与指针扫描不能穷尽间接控制流，完整ABI和运行仍未验收。

## 加载器格式检查

扩展已有check-darwin22-input-contracts.py，允许显式指定本仓out内的候选及必需SHA；默认源内核固定不变。重新编译固定DarwinBoot纯解析函数并在WSL主机执行，20项原ADT正反例回归通过；本次58MB预链接候选被ParseKernel接受（15个非零段，跨度74174464B）。这是主机解析执行，不能称EFI、QEMU、EL1或XNU实机通过。

## 保留边界与下一步

组件/slide沿用既有只读分析选择，slide=-16MiB仅为虚拟布局分析，不写board或物理地址配置。没有采纳旧候选AMFI initializer：本次early_security_initializers为空，未完成initializer身份/调用ABI，不把它称可启动预链接。loadable=false，runtime_qualified=false。真实Apple ADT、连续可分配内存窗口、大负载运输及donor/native结构和C++ ABI仍是缺口。

下一项先取得UEFI在临近OS加载时的真实可分配内存描述符和CPU入口只读寄存器，再据此准备具体窗口/ADT方案；不从Android物理DRAM总量推导连续可用窗口，不改board/bringup/验证标志。新实机动作另需新鲜录像与恢复门。本轮没有设备命令或模式切换。
