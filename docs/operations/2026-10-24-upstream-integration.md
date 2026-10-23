# 合并全部已审查上游更新

用户要求“合并所有更新”。已在独立D:/Code/UniXNU-integration检出完成真实双亲merge并推送wh1stl3/UniXNU main=e553e467ebfe7642e9f483d3977a57066c6d1aef，父提交76dd6414和上游1a01c2af。54处改写历史冲突选择审查过的上游版本，保留3份nuwa工作流，完整索引树与“全部上游+三工作流”逐项完全相同。21模块gitlink均纳入并实际检出验证；feeds.toml与此前fork相同。旧两资料库严格只读。

## 设备接入与补丁

新增firmware-upstream-merged-profile，固定合并源，CI逐项初始化并验证21模块；51输入/11补丁/15后哈希完整链静态检查通过。固件部分和已实测26ef8efd保持相同Heap/HOB保护及全部11补丁，仅UniXNU/DarwinBoot输入/输出哈希随新版更新。旧实测profile不改，以免改写历史包来源。新增upstream-merged固件CI选项与全部保护检查，不是另起一套无保护构建。

kernel-merged-profile改指合并源与21模块；最新签名哈希缓存补丁采用固定新SHA，完整新版GpuAddon补丁只规范原上游裸空上下文行后严格应用到8796，保留Data父目录修复与新增GpuAddon消费。不使用旧简化候选冒充新功能。加入lookup trace、union lower-directory及set-properties grant三补丁；其余Darwin22移植保留。实际构建词法顺序63项完整内存apply通过；Bash适配语法检查通过。上下文通过不是语义或完整编译证明，正准备固件/内核CI。

板值、Heap、IPSW身份和_verified不改。ST FTS触控路线不替换成Novatek；源更新纳入不等于全部硬件驱动已激活/实机通过。不执行Data清空、分区脚本或手机命令。当前手机最新恢复证据仍02:55:45 Android完成1/三分区一致。

## 证据及待完成

reports/upstream-integration/2026-10-24/merge.json、firmware-profile-check.json、kernel-patch-check.json；新固件与Darwin22编译结果待后续归档。原始审查reports/upstream-review/2026-10-24/review.json。收到用户合并指令后替代此前“不采用”审查决定，历史审查原文保留。完成编译前不宣称更新已通过，实际启动另需本轮录像/恢复门。

## 固件成功、首轮内核修复与主机核验

固件CI40014018074/source5abdde1成功，697项实际产物检查通过，FD2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3MiB，shim8a3b5476/112B。新旧SEC SHA7192fd3f相同，整个SEC逐字节一致，包含Heap/内存表/HOB保护；实际DSB/IVAC/DSB/ISB、CreateHob2次/查询1次checkpoint与失败停机复核通过。默认固件profile切为upstream-merged，旧profile保留作历史。

主机：最新Darwin22解析24项含GpuAddon、新分析内核5a128fb2解析通过；实际packed C解析/拷贝与Python稀疏打包、1TiB逻辑边界/13拒绝通过；SMMU真实页表/stream软件夹具ASan/UBSan通过。额外GPU VM完整主机执行未通过：最新上游夹具缺IODirection/持久内存常量，在忽略输出适配中按固定8796头补声明后，x86编译仍因实际AArch64 dsb指令拒绝；未删除目标屏障，不称GPU通过或真实持久内存生命周期已验。失败和适配范围原样存gpu-vm-host.json。

首轮内核CI40014023191在最终链接失败，唯一缺符号native_sandbox_grant(IOService*)。原因是接入清单漏了新增set-properties补丁的前置zzw-native-adreno-sandbox-grant，不是弱化链接规则可解的问题。现补入完整真实上游实现及SHA，64项完整词法序列和唯一辅助函数定义在内存通过；接下来重建内核。首轮失败记录kernel-first-failure.json不覆盖。尚不把整次内核编译写成成功。

## 最终闭环

第二轮内核40015845083/source6070627成功。独立下载检查bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，Darwin22.6.0/iOS16.0、零未定义符号，ArmCpu/ArmDTPlatform五个导出及三份实际归档哈希与runner报告一致。内核尚未预链接/实机运行。新源内核的后续analysis不能直接沿用7774旧绑定；旧5a128fb2保留为历史分析，未修改其loadable=false。

上文x86 GPU执行限制后来通过保留目标DSB的AArch64交叉链接和用户态QEMU软件夹具补充验证：8192-span别名/属性拒绝、映射/持有/释放、13前置拒绝和poison隔离通过。运行时包仅提取到忽略out目录，未安装系统包或改目标驱动；夹具补了8796真实头中IODirection和持久选项声明，不证明真实持久页生命周期。首轮失败报告保留，gpu-vm-a64-link.json/gpu-vm-qemu-user.json记最终范围。

NativePrelink工具入口改用合并源e553e46/独立2b6ffb50模块，只读git对象加载；两个工具源SHA仍与原实现相同，常量池4项回归通过。9项真实grant助手字符串策略主机测试通过，不等于实际sandbox/IOKit调用。24项解析为主机，不是目标ADT。

全部21模块和上游源码更新已合入可复现基线；这不意味着开启全部硬件/根卷功能。实际make参数仍CS_HASH_CACHE=0、owner/Data/RamBlock分支为0，相关导出为空与此一致；kernel-new-feature-exports.json保留实测。没有通过默认profile构建来声称这些未开启分支已编译或运行。后续逐项功能激活仍需真实nuwa配置、ABI与存储保护资格。

固件默认upstream-merged；新FD和新内核都没有执行实机测试，既有录像/恢复门不放宽。固件仓ca2f043文档已同步。最终结构化结论integration-result.json、当前入口STATUS和主线交接已全文对齐。
