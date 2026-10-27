# PROBE34 / revision42 压缩读取连续路径

当前为准备记录，资格汇总及设备启动以STATUS和试验报告为准。主线目标真实header读取返回→init/exec→用户态，不给成功阶段增加人为停点；原生错误、锁、认证和239恢复用户态释放门保留。

## 依据与范围

[PROBE33](2026-10-26-probe33-device-result.md)已观察到294调用前标记、未见295接续。固定二进制确认目标为_decmpfs_read_compressed，入口0xfffffff007480028。原生函数含锁、缓存、压缩头、获取函数、UPL映射/拷贝及错误清理路径，不能仅凭294指定某把锁死锁。

代码已确定的入口、直接调用、导入绑定、原生参数/栈及显示布局先离线核对，不单独进行实机测试。一次新包保留外层读取与exec全部观察，另加入入口、33组调用/接续和RET，成功继续原生控制流。

固定[Apple xnu-8796.141.3 decmpfs.c](https://github.com/apple-oss-distributions/xnu/blob/1b191cb58250d0705d8a51287127505aa4bc0789/bsd/kern/decmpfs.c)用于解释压缩读取流程，实际站点仍以本地固定映像指令为准，不能把同名源码当成本机运行证据。来源副本与SHA见out/probe31-public-research/mainline-sources.json；本轮固定指令审计v42-preparation/decmpfs-native.json。

## 判读

新增格点位于HEX右侧和旧右侧格点之间：两列x736/784，从y224起每行24px，32×16px，最后行1016—1031，最低高度仍1040。编号373—440按行从左到右递增。新增格不会覆盖旧x0—191阶段标记、x256—735 HEX或x832起的旧格点。

| ID | 原生位置或调用 |
| --- | --- |
| 373 | 压缩读取函数入口插桩 |
| 374/375 | current_act调用/接续 |
| 376/377 | 首个IORWLockRead调用/接续；同线程持有排他锁时原生分支可能跳过 |
| 378—381 | uio_offset及uio_resid |
| 382/383 | cluster_copy_ubc_data |
| 388/389 | decmpfs_fetch_compressed_header |
| 390—403 | 注册表锁、decmp_get_func、可选adjust_fetch间接调用和解锁 |
| 404/405 | VNOP_VERIFY |
| 406—409 | 释放压缩头及解锁清理 |
| 410—415 | UPL创建、标记和映射 |
| 416/417、420/421 | decmpfs_fetch_uncompressed_data，两处原生调用 |
| 418/419 | 条件性的wait_for_decompress |
| 424/425 | 后续VNOP_VERIFY |
| 426—439 | UPL解除映射、提交、cluster_copy_upl_data及分支清理 |
| 440 | 原生RET之前；完整外层返回还需295、273等接续 |

调用青色、配对接续绿色。每格表示本次header尝试中至少观察到一次，不表示所有循环迭代都返回；可选分支未亮不是失败。373只证明入口插桩到达，随后的375/377等用于区分原生调用进展。两个fetch调用的返回不自动等于完整读取、exec成功或用户态。

原A038/A039仍在APFS原生RET时刷新，等待期间0/全F不能用来否定中间格点进展。新增32B状态只在探针自有区域保存上下文、配对位和最近站点/原始返回，不增加热路径HEX。限定active header、TPIDR_EL1、VNOP/APFS原生帧链、LR、外层pair8及各调用自己的配对位；每次header清旧状态和旧格。

## 离线核验与保留的失败

正式候选使用reports/kernel-entry-probe/2026-10-26-v42-r2/build.json，内核SHA256 9ebdb97ddf33b6df17150d4942fcf02e962a088d9d6bcaf57b65c156964cb91a；实际资格尚待全量结果。

首份v42候选SHA898c42d7…的左侧格点与早期stage区重叠，静态审阅发现后终止核验，禁止部署；候选、已产生报告和withdrawn-layout.json全部保留。r2移至空白区域，包含原布局负对照，不为该问题安排实机。

首轮前缀夹具把尚未初始化的原生栈槽也比较，寄存器完全相等但暂存字节不同；已改为原生确实初始化的局部量及保存帧比较。每个插桩的原生指令写入仍逐项检查，未放宽原生效果要求。initial-fixture-failure.json保留原因与差异位置。

新增模型检查每个位置的正常、其他线程、其他帧、错误LR、外层未配对、内部未配对、无视频、inactive和错误目标情形；另测旧状态清理、遗漏配对检查负对照、布局边界和真实原生prologue/current_act片段。片段在首个锁函数体前结束，不把模型夹具称为真实锁、APFS、IRQ或设备验收。

未改板内存、基址、iOS16身份、IRQ设置或任何_verified；RAMDisk输入及239门保持。本轮不提交、不推送、不触发CI。新包只有在串行回归、独立重建、证据绑定和最终包回读通过后才能进入新鲜实机预检。

## 最终资格与消费状态

实际v42-r2已通过31项串行检查、1744透明性、617压缩读取、53绑定、独立内核逐字节重建和最终包回读；资格v42-r2/qualification.json。包entry-probe-34.json，SHA256 586a12a37076a73d36a478a5f1202de436b734b1edf2f699856a7b753e77506f。23:03:57已单次消费，禁止重发，实测与恢复见2026-10-26-probe34-device-result.md；上文准备中的描述仅为准备阶段快照。
