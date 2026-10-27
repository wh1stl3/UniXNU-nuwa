# PROBE36 / revision44 准备

目标：减少压缩读取观察器的帧缓冲写入，继续展示真实header读取、init/exec路径；不把显示改动当作原生故障修复。

输入保留v43-r2的固定prelink、固件、shim、RAMDisk和原生观察点。新增 `scripts/probe_compact_decmp.py` 与 `scripts/test-compact-decmp.py`，构建参数 `--compact-decmp`。只有373..440标记从32×16变为32×2，坐标、颜色、配对和重置条件不变。原生锁/错误/认证/IRQ、内存配置、IPSW身份及239释放门不变；不设置任何*_verified。

本轮编辑前源码原字节保存在 `out/before-probe36-source/`。旧报告不重算；新内核 `out/kernel-entry-probe-44-compact/kernel-entry-probe.macho`，SHA256 `a80af3c69311927a4d91a6d07b0ac4cb2463760309ba46fdb9329f390468a4fd`，58523648字节。新ADT `out/exec-mainline-v44/launch/kernel.macho.adt`，SHA256 `074c0c83dfefc4f287b1fe10bdea95064b5677971497e258f45354d68d80fd77`。

当前正在运行 `verify-image4-entry-candidate.py` 全部33项串行检查；报告目录 `reports/kernel-entry-probe/2026-10-27-v44`，原始控制台 `2026-10-27-v44-preparation/regression-console.txt`。尚未完成资格、独立重建及最终包回读，不可部署。

实机解释规则：新压缩读取标记本来就是短线，不再按16行满格判断；373入口，374调用_current_act前，375其原生续接，376/377第一处IORWLockRead调用/续接；后续原生缓存、压缩头、回调、拷贝、解映射、返回观察仍全部保留。440只表示RET前观察，需要295及273等外层返回证据继续闭合。没有成功阶段停点。

## 最终资格与部署

上述“核验进行中/不可部署”为准备阶段历史状态。最终33项全部通过，1744透明性、476原读取位置、617压缩读取、72短线像素、57绑定；独立内核逐字节一致，最终boot镜像/FAT回读通过。正式qualification.json位于2026-10-27-v44报告目录。

最终包reports/xnu-first-entry/entry-probe-36.json，镜像SHA256 b9ac9fb016166dc074bfc4b556ed8123c98077f3e4bcefc7383070fc9b5dd0b1，204484608字节。约00:27 +08完成单次临时发送，ACK0、consumed禁止重发，尚无本轮内核执行/恢复结论。证据reports/xnu-entry-probe-trial/2026-10-27-v44/{preflight,launch,consumed}.json。新鲜预检为Android1/nuwa/kalama/A槽/三SHA一致；启动后不能沿用为当前Android状态。

延续用户本阶段实机授权与最新媒体/自行恢复/继续指令所支持的拍摄恢复条件，未重复请求批准。预检脚本固定human_capture_source字段称Fresh confirmation，实际依据以human_capture_confirmation正文为准，不声称用户对36重新答复。下一轮仍需完整媒体和Android只读后验闭环。
