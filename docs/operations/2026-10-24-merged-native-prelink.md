# 合并后新内核预链接与AMFI入口追踪

## 新分析候选

新核bf14e530（CI40015845083）使用固定合并源e553e46/NativePrelink2b6ffb50及已限定Libm常量池补丁重新生成，输出out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho，SHA256 eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca，58335232B，虚拟跨度74190848B。源kernel41095+component24253共65348绑定逐项读回一致，30段donor可执行代码和native可执行代码原样保留。它不是给旧5a128fb2改标签。

新版DarwinBoot纯解析器24项主机用例通过，并接受新候选15个非零段。分析profile独立为config/native-prelink-merged-analysis-profile.json，历史7774分析fixture保留；emit-current-prelink-analysis.py默认新profile，也可显式选择历史profile。loadable=false、runtime_qualified=false，未打包作手机OS负载。

## AMFI入口实际证据

历史报告e9fe59f2中的early_security_initializers地址0xfffffff004703c54是slide=-16MiB之后的输出；逆slide后的donor原始候选为0xfffffff005703c54，落在AMFI原始RX段[0xfffffff0056fb000,+0x1d788)中。若把历史输出当原始VA再交给发射器会重复slide，不能照抄。

审计scripts/audit-amfi-initializer.py对固定donor2ec297ba只读反汇编，Capstone有符号立即数统一mod2^64，解析ADRP/LDR/BR导入stub及原kernel导出。候选0x400字节探索片段包含真实_mac_policy_register导入，并非仅凭“像函数序言”。模块中有两处直接BL指向它；原__mod_init_func为另外三个构造函数，kmod start是经全局槽间接跳转的包装器，不能混为同一个入口。完整地址/指令/哈希见amfi-initializer.json；没有调用任何组件代码。

实际新内核dSYM的mac_policy_conf为80B，10个字段偏移0/8/16/24/32/40/48/56/64/72。donor在注册前构建配置时前8字段写入位置一致，原始dump与mac-policy-abi.json留档。这只收窄局部结构ABI，未证明所有mac_policy_ops回调、IOKit/C++布局或调用约定完整一致。

## 明确判断与剩余工作

**AMFI注册入口已经有较强的静态定位证据，下一处更具体的风险是初始化阶段与DATA_CONST可写期，而不再是完全不知道入口在哪。** donor函数会写自己的配置/操作表，所属__DATA_CONST初始保护为只读。必须核对native预链接加载和OSKext启动阶段是否允许这些写入，以及构造/间接start路径是否已执行策略初始化，不能只验证指针在RX段就强行调用。

Apple同版本[mac_base.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/security/mac_base.c)包含mac_late与策略加载/注册约束；[OSKext.cpp](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/libkern/c%2B%2B/OSKext.cpp)区分C++构造、kmod start和服务生命周期。固定UniXNU的早期入口补丁只检查prelinked/AppleSecurityExtension/MAC阶段及RX边界，这些条件不能单独证明DATA_CONST写入时序。因此当前仍不把候选写入initializer映射，不伪造策略结果，不绕过原AMFI。

下一步继续追踪可写期/调用阶段，并准备独立大文件读取SHA探针，读取可来自任意SimpleFileSystem；OTG介质可用性已向用户询问，不自动写介质或启动。Heap/HOB保护、板内存/身份/_verified不改，本轮无设备查询或模式切换。

复现：bundled Python -B scripts/emit-current-prelink-analysis.py --work <out下新目录> --output <reports下新文件>；audit-amfi-initializer.py --output <reports下新文件>。dSYM命令与实际输出见mac-policy-abi.json/native-mac-policy-layout.txt。原始产物不覆盖。
