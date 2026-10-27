# PROBE39结果与PROBE40低写入HEX准备

PROBE39原图Media-nuwa/PROBE39.jpg为556347字节，SHA256 d3e9dc845c1dbdf485c656d6dcadd4edb455894d16d861cbd1fd114d93af2668。用户明确确认稳定后拍摄且已回Android，具体秒数未知。原图不改，最近邻裁剪及manifest在Media-nuwa/derived/PROBE39/review-01；screen/media-binding在reports/xnu-entry-probe-trial/2026-10-27-v47。

照片A034=0x110（272，分派调用前），A037/A038/A03A/A03D/A03E为0，A03B全F。A03C末尾受Logo遮挡；A036仅能辨认FFFFFFF005前缀、一个不完整/有歧义的字形和零后缀，不能将其当作新的完整函数地址。没有本轮固定callback入口或第二次分配结果证据。最深历史证据仍是38的分配器RET/非零路径，本轮较早的可见边界不抹去历史实测，也不能将38的读数复制到39。

首次只读Android后验未通过identity/boot-completion联合门，原工具未保存查询中间值，未猜测具体缺失属性；独立postcondition-initial-failure.json保存实际失败。稍后只读复查2026-10-27 10:01:13 +08确认Android完成1、nuwa/kalama、A槽、三分区SHA与预检一致，postcondition.json和retry-console保留。无额外恢复boot、无权限拒绝、无设备写入。

工程判断：多轮稳定画面的可见前沿不同，本轮目标HEX似乎未完整更新，因此优先排除观察器开销和记录不完整，不再据这张图推断malloc返回零。固定模板与软件模型把framebuffer身份映射设计为AttrIndx3/Device-nGnRnE；没有本轮实际MAIR/页表读回，不采用未经证明的CPU缓存根因，不改变缓存属性、IRQ、锁、错误或分配策略。

PROBE40 / revision48只改普通共享HEX的重绘工作量，保留全部既有读取、fetch、allocator、decode、结果/错误分支和exec观察。新增scripts/probe_delta_hex.py，29个实际逻辑字段各16字节记录上一完整显示值与valid；首次/无效记录完整画字段，后续只画不同的4位数字，间隙和字体/字号/位置与旧版本相同。字段绘制完成后返回原生流程，记录的valid在绘制后提交；A035仍受header清理门约束。异常HEX保留无栈实现，不改变32位成对显示存储，不引入新的内核阶段停止。普通显示额外保存X18/LR的16字节栈，普通调用总显示栈32字节，完整hook回归检查原生状态恢复。

新增scripts/test-delta-hex.py对照已归档PROBE39候选，29字段×25次=725次更新，逐像素比较整个字段、间隙和边界；覆盖每个数字位置、全F/0/高位值、无视频、不支持行回退、A035跨header清理、无效valid、写入前不提交valid以及破坏字形负对照。37项专项通过，模型写入量7405440字节，对照27801600字节；单数字1920字节而非整行38400字节。不是硬件吞吐/时序或用户态通过证明；显示值记录不改变CPU数据缓存策略，软件像素等价不证明实机scanout时序。

首专项因夹具仅允许一次8字节Unicorn写回调而拒绝，模型会把STP W的两个32位存储分别回调为4字节；检查改为允许4/8字节模型事件并保留完整矩形和对齐约束。候选二进制未改变，原delta-smoke-console保留，delta-smoke-r2.json通过。实际显示指令仍使用原HEX_DIGITS中的STP W，没有增加硬件存储宽度。

候选out/kernel-entry-probe-48-delta/kernel-entry-probe.macho，58630144字节，SHA256 4237d18ca1c4d1ac95d464c8828330ef8f833a53a6dd0942fd5c26c1a24099b5。ADT out/exec-mainline-v48/launch/kernel.macho.adt，SHA256 3ff810754831ff184f6499a2637da7dc8faa5057e0940781ddfaaf82e4177d4e。准备时完整37项串行作业尚在运行；该阶段状态已被下方最终资格记录取代，未启动。

239未审restore用户任务释放门保留；受审内存/身份/_verified不改，无提交/推送/CI。到首次用户态仍需完整读取/解压、原生exec装载和依赖/认证、首线程实际切换，不能将观察器优化升级为内核功能修复。UFS仍未验收，根RAMDisk/md0。

续验记录：完整回归在single-pass-hex旧夹具处停止，拒绝地址0xfffffff0084cd3a0，位于A037新增16字节显示值记录槽。夹具仅允许该槽两个8字节写入，逐项核对最终值/valid，无视频时要求无写入且槽保持零；第二次直接复查因Unicorn 64位写回调对全F值使用有符号整数而断言失败，按64位无符号位型归一后7项通过。两次均未改变候选内核。第一次原execution.json/regression-console保留；第二次工具返回AssertionError于state_writes精确值断言，此处记录工具事实，无伪造不存在的原始日志。后续独立execution-continuation.json与execution-qualified.json绑定原失败摘要，不覆盖原执行记录。


最终资格（2026-10-27T10:43:07.3489306+08:00）：37项核验作业合格，独立重建内核逐字节一致，启动包FAT内容回读通过。资格qualification.json与execution-qualified.json位于reports/kernel-entry-probe/2026-10-27-v48。包204484608字节，SHA256 bc895d41c3308884a82c653e89c99226a81911d036c01ccb328389fce625bc8b，报告reports/xnu-first-entry/entry-probe-40.json。本轮diff为out/probe40-source.diff。用户明确暂时不上机，未做40设备预检或启动，未消费；最后设备后验仍为39的Android恢复记录。后续恢复实测须重新取得新鲜目标/槽位/三SHA与可用拍摄、恢复条件。本轮无新增硬停触发，因用户安排暂停设备动作。
