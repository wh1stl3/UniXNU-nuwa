# PROBE41：当前最大疑点与验证范围

当前最大疑点是**首次 ResourceFork 块表读取的调用边界及内部路径**。PROBE40 的 535 调用前条带可见，536 续接条带在未遮挡位置未辨出；这比“第二次分配未返回”更符合最新证据。535 仍是调用前观察，不能单凭它认定辅助函数入口已执行，更不能认定 APFS 死锁。新版41因此同时观察辅助函数入口、内部各调用和返回。

## 最近几轮怎样缩小范围

| 轮次 | 本轮可靠证据 | 不能由此推出 |
| --- | --- | --- |
| 36 | 压缩读取路径到 fetch 调用前 | type4回调已进入 |
| 37 | 固定type4回调入口、第二处IOMallocData调用前 | 第二次分配已返回 |
| 38 | 至少一次分配器RET及非零路径 | 返回一定属于第二次分配 |
| 39 | 稳定照片中部分HEX未完整更新 | 原生路径比38稳定地倒退或malloc失败 |
| 40 | 第二次请求0x28，分配器/调用方非零值；多个向量准备点、decode入口、535块表读取调用前可见 | 536续接、完整解压/文件读取、exec或EL0已完成 |

40完整指针受Logo遮挡仍标暂定，只使用可见非零及对应续接证据。细条带补充在`reports/xnu-entry-probe-trial/2026-10-27-v48/screen-supplement-resource.json`，不覆盖原screen、媒体或历史验证。

## 代码对应与疑点排序

固定输入SHA256：`1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6`。

1. **资源读取链为首要范围。** `0xFFFFFFF005697154`调用`0xFFFFFFF005696D2C`，首块表项为offset `0x108`、length `8`。后者准备UIO，调用`VNOP_GETXATTR`读取`com.apple.ResourceFork`，flags `0x20`，然后释放UIO并检查错误与长度。代码和535/536条带使这一范围优先于codec算法本体。
2. **内部首先区分UIO创建与文件系统属性读取。** 先前普通读取使用的栈上UIO及已返回的IOMallocData都不能替代这里的`uio_create`。源码参照中的UIO创建包含等待型分配；`VNOP_GETXATTR`则委派vnode操作表。当前没有足够证据在两者之间作确定归因。
3. **错误打印与观察器开销仍保留。** 辅助函数在errno非零或返回长度不符时会调用真实名称辅助函数、printf及释放。静态照片不提供完整时序；跨轮可见前沿变化说明显示影响不能忽略。
4. **第二次分配失败、输入损坏、必需文件缺失目前优先级较低。** 40第二次分配非零；固定根38文件、188压缩块、188读取窗口已完成宿主闭包及摘要对照。宿主通过不能替代原生资源读取、解压或认证通过。

`0x2FF`来自decode上下文+8，原生用它选择解码分支；它不是这次读取的errno，也不是磁盘decmpfs类型值4。ResourceFork块表布局及首块偏移与宿主导出一致，不据此修改数据或绕过原生检查。

实际指令与stub解析：`reports/kernel-entry-probe/2026-10-27-v49-r2/{resource-native,resource-edges}.json`。本地XNU源码只作机制参照，其固定摘要和位置见[详细操作记录](2026-10-27-probe40-result-probe41-preparation.md)。尚未捕获本次属性读取的运行时v_op目标。

本轮进一步核对固定APFS操作表：4个getxattr描述符引用中，与实测read候选`0xFFFFFFF0051A5858`同一静态操作表的getxattr候选为`0xFFFFFFF00519CB28`。报告`reports/kernel-entry-probe/2026-10-27-v49-r4/resource-vnode-candidates.json`保留完整引用与固定wrapper指令窗口。此结果用于后续定位准备，不将静态表成员关系当作运行时目标，不据此宣称该handler或某把锁已卡死。

## 重出的PROBE41做什么

资源版r4保留已有读取、分配、decode与exec观察，在辅助函数内部增加22个准确观察位置，使用32字节诊断状态，仍显示在原A03D/E矩形，不添加网格占用。作用域限定当前header、线程、实际callback/decode帧、准确父调用配对及资源函数自己的调用配对；重试清理状态。没有修改分配、锁、缓存、IRQ、认证或错误处理策略。

| A03D（前缀FFFFFFF00569） | 可区分的边界 |
| --- | --- |
| 7154 → 6D2C | 调用前观察是否继续到resource入口 |
| 6D6C → 6D70 | uio_create是否返回；A03E为原始指针值 |
| 6D7C → 6D80 | uio_addiov是否返回 |
| 6D9C → 6DA0 | VNOP_GETXATTR是否返回；A03E低32位为原生errno |
| 6DA8 → 6DAC | uio_free是否返回；不将void返回寄存器当errno |
| 6DE8 → 6DEC / 6E4C → 6E50 | 错误日志或长度不符日志是否返回 |
| 6E80 → 7158 | resource辅助函数返回及decode调用方续接 |
| 后续decode/外层read/exec点 | 同一轮继续显示主线运行结果，不在成功点主动停止 |

A03D是最后记录点，不是CPU停止PC；A03E为配对返回的原始x0，调用前通常为全F。不能把所有值统一解释为errno。A03A—C保留第二次分配事实。

资源版候选内核SHA256 `8757bc0c38449099e3d10b8fcd69ec0cbd830c263f99c77bce2ff191848e4418`。977项专项及9项连续路径/重置检查通过；最终整包资格以`reports/kernel-entry-probe/2026-10-27-v49-r4/qualification.json`为准，文件生成前仍是候选。早期r2虽完成回归但未部署，其结果不套给新版。

本轮只重新分析和出包，未启动41。保留239未审用户任务释放门、受审内存/IPSW身份和所有verified边界；当前未证明进入用户态。实际启动仍需新鲜设备预检与有效拍摄/恢复条件，已消费的40不重发。

## 最终包（2026-10-27T13:12:01.644370+08:00）

资源版r4的38项完整回归作业、独立内核逐字节复现、镜像内容回读均通过。包`out/trial-boot/xnu-entry-probe-41-resource/boot-xnu-first-entry.img`，204484608字节，SHA256 `8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a`。资格`reports/kernel-entry-probe/2026-10-27-v49-r4/qualification.json`，差异`out/probe41-source.diff`。41未启动，未消费；前述“候选/待资格”状态由此更新。

## 2026-10-27T18:29:35.355383+08:00 · r5替代当前候选

PROBE41已调整为实际ResourceFork分派版r5，未启动、未消费。镜像out/trial-boot/xnu-entry-probe-41-dispatch-r5/boot-xnu-first-entry.img，204484608字节，SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；内核89fdd0a831500ff2f28d2245824c47a0d1ad5e7d1719c42f7ede3b7e9237eaad，ADTfbc8ee7eabb52c2d1c0e4bca2dd581af6b107f0c2672fba33b8f455fa1e5e155。38项串行作业全部通过，2420透明性、1015专项（含新增38项分派检查）、9连续路径/重置、独立内核逐字节复现与镜像回读通过。新增A03D=FFFFFFF00746E1A4/A03E=原生实际x8目标，A03D=FFFFFFF00746E1A8/A03E=配对返回原始x0；调用前不是handler入口，A03D不是停止PC。仍使用原矩形，旧22点及后续主线继续；Restore根、239门、板值/内存/IPSW身份、verified边界不变。旧r4内核/ADT/整包摘要核对不变，旧资格保留且不套给r5。本轮没有设备操作、提交、推送或CI。详情docs/operations/2026-10-27-probe41-dispatch-r5.md，资格reports/kernel-entry-probe/2026-10-27-v49-r5/qualification.json，包报告reports/xnu-first-entry/entry-probe-41-r5.json。
