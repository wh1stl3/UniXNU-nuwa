# PROBE36：压缩读取内部进展与恢复闭环

对应revision44，镜像SHA256 `b9ac9fb016166dc074bfc4b556ed8123c98077f3e4bcefc7383070fc9b5dd0b1`，已消费，禁止重发。

原件 `D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE36.jpg`、`PROBE36.mp4` 未修改或上传。原件与派生图摘要及FFmpeg命令见 `Media-nuwa/derived/PROBE36/review-01/manifest.json`，设备仓绑定见 `reports/xnu-entry-probe-trial/2026-10-27-v44/media-binding.json`。录像3.600104秒，本次看照片及2fps接触表；用户确认拍照前“已稳定，约3—10秒”，不是把视频长度作为稳定等待时间。

照片373起出现多组压缩读取调用/返回细线，最后可辨右线对应416，即原生 `decmpfs_fetch_uncompressed_data` 调用前。左415与白色Logo相交，不能仅凭其颜色确认返回；417及之后未见点亮。294可见、295未见点亮。完整手工复核HEX与35一致，记录在screen.json；A036/A037仍FFFFFFF0051A5858，A038/A039仍为延迟刷新默认值，不当作实际返回结果。

相较35只见373完整格/374部分青线，36已展示更多原生调用和返回。减少绘制量与本轮更深可见进度相关，尚不能证明唯一根因或稳定修复；不再以黑格外观为独立试验目标。也不能声称网格绝不影响执行：观察器写入会消耗时间，显示可见性仍不是CPU精确停点。

固定代码的416位于 `0xfffffff007480474`，目标 `_decmpfs_fetch_uncompressed_data` 为 `0xfffffff00747fd28`。该函数先处理范围，再取共享锁、查注册函数、执行真实间接回调，按原生返回处理错误及可选缓存维护。公开源与实际指令要区分：固定二进制优化了参数/分支，不能机械按公开C签名构造运行时ABI。源码参照为已有固定Apple 8796.141.3 `decmpfs.c`；新指令清单见v45-preparation/fetch-native.json，供体回调清单见type4-native.json。

首要待辨边界是fetch入口、注册函数选择和type4回调内部，而非之前的current_act或首个压缩锁。下一候选同时观察fetch与固定type4回调的主要调用、续接和返回，保留完整外层读取/exec观察，不跳过错误/认证/锁，不额外设置成功阶段停止。未捕获回调入口前，不宣布回调已经执行；未观察成对返回前，不认定解压完成。

2026-10-27 00:30:03 +08只读后验确认nuwa/kalama、Android完成1、A槽，boot_a/vendor_boot_a/init_boot_a摘要与36预检一致。用户自行恢复，无额外boot。证据postcondition.json；历史consumed的recovery_pending快照不改，由新后验闭环。未提交、未推送，UFS及真实用户态仍未实机验收。
