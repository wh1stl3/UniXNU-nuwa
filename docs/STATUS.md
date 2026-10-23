# STATUS

> FV配置卷发现已实机通过且Android恢复闭环。当前77742999内核已生成分析用预链接候选，静态绑定与DarwinBoot主机解析通过；尚未执行XNU。

新候选5a128fb2/58335232B，65348项重定位写后读回一致，30段donor与native可执行字节未变。Libm原12处拒绝已由完整1224B常量池指纹及数据引用/边界/无直接分支或重定位指针入口证据处理；4项拒绝回归通过。固定DarwinBoot主机ParseKernel接受15个非零段/74174464B跨度，20项ADT解析正反例通过。早期安全initializer未配置，完整donor ABI未验收，loadable=false，不用于设备启动。

最近实机仍为87b14624/CI39988591973/固件00a37d9：4MiB FV→BlockIo→FAT→唯一探针配置通过。recovery/postcondition确认nuwa/kalama、Android完成1及三分区SHA不变。当前无设备试验或刷写；内存图/board/bringup/_verified未改。

下一步：在独立诊断profile取得临近OS加载时UEFI可分配连续范围与CPU只读入口信息，形成有证据的窗口/目标Apple ADT方案；随后解决真实安全初始化/预链接ABI和大负载运输。详见operations/2026-10-24-current-native-prelink.md，证据reports/native-prelink-current/。

独立 boot-input-audit 已接入固件6176a82，ReadyToBoot内存/EL/MPIDR/CNTFRQ只读快照，静态链检查通过，完整CI待验。无新设备操作。详见operations/2026-10-24-boot-input-audit.md。
