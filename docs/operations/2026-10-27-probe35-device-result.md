# PROBE35 媒体与恢复闭环

2026-10-27。对应 revision43-r2，镜像 SHA256 `91eb23a77759407dded15cb371e3578c9418e65fdb13975681193d2eecab0e76`，已消费，禁止重发。

## 实测记录

原照片和录像为 `D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE35.jpg`、`PROBE35.mp4`。原件未修改、未上传。摘要和派生命令见 `Media-nuwa/derived/PROBE35/review-01/manifest.json`；设备仓绑定见 `reports/xnu-entry-probe-trial/2026-10-26-v43/media-binding.json`。视频长9.179133秒；本次看照片与每秒一帧接触表，不冒称逐帧审查。

照片可见373绿色完整格，374只有青色细横线，375/376未见点亮。294青色、295未见点亮。A036/A037均为 `FFFFFFF0051A5858`，A034为110，A035为全F，A038为0，A039为全F。完整手工读数见同目录 `screen.json`。A038/A039按既有策略延迟到APFS返回才刷新，默认值不表示实际返回值。

与PROBE34相比，可见执行已经到压缩读取入口观察点；不能将374的部分绘制当作绘制完成或 `_current_act` 原生调用已经执行，更不能据此认定锁死。照片及抽样录像未提供header读取完成、exec或用户态证据。

用户报告黑色网格横纵都增多。固定代码 `read_decmp_sites.py:observe(FIRST)` 在每次header尝试时清黑68个32×16区域；这些区域落在原Logo之上，所以清黑本身能形成缺口。它能解释部分网格外观，尚不能解释374为什么仅显示部分高度。`DENSE_ONCE`在绘制前就设置once标记，故标记置位也不是绘制完成证据。

## 工程判断与下一候选

优先处理观察器绘制成本及显示证据完整性：33/34/35可见进度并非单调，35又出现部分高度标记，不能继续把最后可见像素等同最后原生PC。备选为绘制期间运行中断/异常，或帧缓冲可见性问题；当前没有寄存器或映射证据支持区分它们。原生压缩锁/解压逻辑故障仍未排除，但没有已进入相关锁调用的充分屏幕证据，不猜改锁、IRQ、页表或缓存属性。

PROBE36仅把373..440改成32×2短线，每标记2048→256字节；68个初始化区域139264→17408字节。所有地址、调用配对、原生重放及后续观察仍保留。完整像素、未触碰区域、重复不绘制、无视频、header重置及旧高度负对照加入强制验证。实机若越过375/376并继续展开后续短线，将支持减少观察器负担有帮助；若仍只见374，不足以直接确定根因，下一步需独立观察运行状态而非继续猜改原生流程。单次前进不等于稳定修复。

## 恢复

首次只读后验因身份/Android完成门失败，原失败保存在 `postcondition-first-failure.json`。未额外启动恢复镜像。2026-10-27 00:05:20 +08重新只读核对成功：nuwa/kalama、Android `sys.boot_completed=1`、A槽，boot_a/vendor_boot_a/init_boot_a三摘要与本轮预检一致。证据 `postcondition.json`。历史 `consumed.json` 中recovery_pending是当时快照，原样保留，由本次后验闭环。

未提交、未推送、未触碰其他机型。UFS和完整iOS用户态仍未实机验收。

## 固定公开实现对照

重新读取已有固定公开源码 `out/probe31-public-research/UniXNU-GopFramebuffer-NativeGOPPresenter.cpp`，提交 `33e941a878dcf01b98dbd9160d798bd56e7551ea`，SHA256 `7fcf53e5a971ad07d9259b93cc8eb4ecbce6962e5a1356c9cc7b39b1264becc0`。该实现使用 `mapDeviceMemoryWithIndex(0,kIOMapInhibitCache)` 和写后 `dsb oshst`；当前诊断早期映射声明Device-nGnRnE并使用 `dsb sy`。这说明映射属性需要有实际依据，不能仅凭黑格套用缓存清理补丁；后期实际页表属性尚未采集。本轮不改变映射或添加未经验证的缓存维护。公开文件只是参照，不代表该驱动在本轮实机已运行。
