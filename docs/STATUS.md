# STATUS

更新：2026-10-25（北京时间）。主线 UniXNU / nuwa / iOS16 已从pmap入口推进到 **kernel_bootstrap入口实机确认**；iOS仍未启动。

## 当前里程碑：PROBE16

- 镜像：6f0907b2ce684a70dd143664172bf083012bae5b31d3d4a195459d0c3f6400fa。
- 内核：167bd013da33a6a1e439b0dba5a4ec161ce5a90c781e14f446da6b520ec40753，58,372,096 B，49记录补丁。
- 本地代码/证据提交：b708494；未push。
- 单次临时启动，用户在菜单按电源键Enter触发；用户文字及原图确认左列y512橙色kernel_bootstrap入口标记出现。无固定180秒等待。
- 恢复核验：2026-10-25 16:44:29北京时间Android完成1/A槽，boot_a/vendor_boot_a/init_boot_a三SHA与试前一致，无flash/erase/改槽。当前无需人工恢复；这是该时刻的记录，不代表持续实时查询。

证据reports/xnu-entry-probe-trial/2026-10-25-v23/；包reports/xnu-first-entry/entry-probe-16.json。原图留本地out，只提交哈希/读数，无原始音视频上传。

## 当前修复的准确范围

旧模型在PE_create_console导入BCM固定旧panic区0x3c0fc000时读失败。上游DT panic区补丁已适配成8796源码候选，函数体AArch64编译与11个host边界场景通过；**未完成整核源码重建**。

当前二进制曾把panic_text_len常量折叠为1字节状态，不能直接套通用动态日志区。诊断桥接只实现“真实DT查询缺pram则跳过旧panic导入”，保留原initialize_screen/console和当前panic代码；pram存在则明确红色/A035=2停住。此为限定诊断路径，不是正式通用panic缓冲提供者。

原模型的0x3c0fc000失败被正反对照定位，PROBE16实机越过此前最高阶段，进入kernel_bootstrap；没有实机ELR/FAR证明旧包唯一停因，保留该边界。

## 软件验证

42入口/MMU、92普通钩子差分、18渲染、5WFE、8稀疏阶段、2异常、5ParseKernel、17绑定门；四切换场景12断言；6个console策略检查及11个源码DT guard用例。连续模型使用最终镜像同一ADT到达kernel_bootstrap，无非法访存；旧v22负对照仍在旧panic区读失败。最终镜像回读及Git报告字节摘要一致。loadable=false/runtime_qualified=false、板值/TCR/donor/认证/_verified保持。

## 下一主线

1. 收敛kernel_bootstrap内部和VM启动内存初始化阶段，验证其完成/返回，再看scheduler、驱动和root。橙色只证明入口，不证明完成。
2. 续跑模型20,000,000指令在_vm_page_release_startup+0x254达到预算，无错误；不能判死循环或硬件停点。先区分正常大循环与真实等待，再选少量阶段点，不盲目增加模型假RAM或跳过核心初始化。
3. 正式源码构建接入DT panic补丁/配置并做整核回归；诊断缺pram桥接不能冒充完整实现。

详细实现与复现：operations/2026-10-25-v23-dt-panic-console.md。前轮pmap映射修复保留，不重复旧试验。本轮没有第二次候选启动。

## 官网与日志

官网16e592ab的AdvancedLogDxe/OneSend二维码日志覆盖UEFI/EBS前，nuwa尚未接入；Format2/共享SM8550迁移保留独立评审、iOS16 ABI与板值。见operations/2026-10-25-official-porting-update.md。原始音视频仅本地，禁止自动GitHub附件/CI上传；历史Actions ZIP内部未逐个审计，不能对历史上传绝对保证。
