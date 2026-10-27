# PROBE45实测与PROBE46缓存进度、预读及收尾

阶段S03/S05/S06/S12/S13。任务于2026-10-27开始，收尾跨至2026-10-28（Asia/Shanghai）；报告目录保留创建时日期，不改历史路径。用户要求本轮完成下一镜像、所有文档、本地提交及新会话prompt；不推送，不因收尾自动启动46。

## 实测及恢复证据

PROBE45单次临时启动已消费，镜像SHA256 `e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d`，内核SHA256 `2935ab6e53067a5daa4156510e158f3eebe765c50592abbd4b617375c2f05247`。`reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/postcondition.json`确认Android完成1、nuwa/kalama、A槽，boot_a/vendor_boot_a/init_boot_a摘要与45预检一致。不是沿用44后验。

用户七个阶段截图及原视频/照片均已归档。原件在`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/`；派生在同轮`derived/review-01/`，manifest保存原件及阶段截图摘要，source-frames.json保存源PTS，ffmpeg按源帧抽出227帧。未声称全部帧完成逐字符OCR。按用户既定约定，末态照片记录为稳定，等待秒数未知，不再追问。

清晰末态选定字段：A03D=`FFFFFFF00743CC74`、A03E=`0000000000000000`。其余有遮挡/歧义的指针不用于路线变更。该点是实际`_cluster_copy_ubc_data_internal`的RET前观察，不是异常PC；它证明已走入缓存辅助函数并到达返回边界，尚不能单凭画面证明RET完成、调用方消费了字节或整个ResourceFork读完。

## 原生代码、反证和最大疑点

实际原生函数范围743CB58—743CC74，在743CC1C调用memory_object_control_uiomove，随后用uio_resid前后差计算已复制量并更新调用方io_resid。返回0只表示未报错，不保证请求全部完成。调用方7438C38取回resid，7438C3C/40/44计算并扣除复制量，7438C48/4C决定继续缓存流还是转入UPL/错误路径。预读调用7438BDC及7438C7C、收尾锁/等待/释放也在同一个原生读取过程内。

首要待验证假设是缓存返回边界的观测干扰或遗漏，优先于直接认定UPL/IO死锁。支持：末态正好是辅助函数RET前；45在该辅助函数中插入6个观察点，每次命中重画两行，缺少独立的调用方进度量。反证：离线原生RET续接夹具成功，未复现普遍的寄存器/跳转损坏；不能把移除观察器称为已证实根因修复。第二假设是原生缓存循环/预读/收尾未产生可观察进展；当前没有请求量、残余量或等待点的实测值，不能确认具体锁或完成者。硬件异常/显示更新遗漏仍未排除。

已逐指令核对max_io_size的原生计算：743898C比较1MiB，较小时7438994直接选择1MiB；其后才按PAGE_SHIFT_CONST取整。不能因源码中的分段字段未知就认定max_io_size为0，也不能把PAGE_SHIFT_CONST文件初值0当实际运行值。没有猜改内存、页大小、UFS、IRQ或原生返回。

本地固定原始资料`D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/bsd/vfs/vfs_cluster.c`用于解释控制流，并回到实际部署指令核对。当前仍是rd=md0 RAMDisk；cluster接口不是UFS实测资格。此前公开访问403缺口保留，本轮未重新取得在线资料验证，未换通道绕过访问拒绝。

## PROBE46具体变化及同轮范围

移除缓存辅助函数内部全部6个观察钩子，恢复该函数原生字节（包括RET），以调用方的成对调用/续接证明返回。新增请求量、剩余量、缓存循环、预读及收尾观察；cluster组共79位置、128B状态（45为64位置/160B）。沿用A03D/E两行，不增加网格；其它已有诊断仍有开销，不宣称完全无干扰。

A03D是最新匹配检查点，不是停止PC。A03E默认原生x0；这些位置改用明确的数据：

| A03D后缀 | A03E含义 |
| --- | --- |
| 74389B0 | x21，原生max_io_size |
| 7438A7C | x24，初始io_req_size |
| 7438B38 | x19，缓存循环剩余io_size |
| 7438C1C | x20，本次请求复制字节数 |
| 7438C3C | 高32位=requested，低32位=residual；不是errno |
| 7438C4C | x8，原生error OR residual分支条件 |
| 7438CD0 | x0，缓存辅助返回错误值 |
| 7438E18 | x19，已加载的_PAGE_SHIFT_CONST；不是可变_page_shift |
| 7439A00 | x19，缓存流完成分支的剩余量 |
| 7439A80 | x0，进入收尾时原生状态 |

同一次启动连续覆盖：缓存快路径消费量→必要UPL/cluster IO→预读/等待与收尾→APFS read/ResourceFork返回→type4解码→Mach-O/load_machfile→dyld查找、授权、读取→任务切换/签名与239受控释放边界。正常路径不增加阶段停止；原生错误照常传播。后半链沿用已存在的实际观察点，仍须用本轮镜像静态登记及资格报告核对，不能把计划算作运行成功。

证伪方式：若移除内部钩子后看到7438C38及7438C3C，即获得实际调用方续接和消费量；后续读取返回则推翻读取未完成假设。若请求/残余及循环记录反复无进展，再依据原生尺寸、UIO与预读条件分析；若落到确定等待调用，再追完成provider、初始化与唤醒。只有调用前没有返回仍不证明callee进入或死锁。239保持，不能借“推进更远”释放未审阅Restore用户任务，不宣称EL0或桌面。

## 离线验证边界

先前45的null-object返回夹具保存在`reports/kernel-entry-probe/2026-10-27-probe45-analysis/return-chain-fixture.json`。它是原生辅助函数到调用方的连续执行，不是实机IO结果。

46专项963项已通过：79位置的12种作用域/指令差分情况、reset和外线程负对照、6种缓存边界场景×有/无画面的连续原生执行、恢复原生UBC函数字节检查。连续场景包括空对象、零请求、缓存未命中、部分复制、全部复制、原生错误；只在ubc_getobject和VM uiomove边界提供明确夹具，不模拟真实缓存/物理IO。核对原生寄存器、UIO副作用、残余值、返回路径及打包字段；没有放宽断言。

完整资格见下节；上述专项检查不单独替代整包资格。

## 最终离线交付（2026-10-28T00:54:02.611557+08:00）

PROBE46 boot为`out/trial-boot/xnu-entry-probe-46-progress/boot-xnu-first-entry.img`，204484608字节，SHA256 `5f05da60910590111089d196dda0160dee2ecccb8cd3112fd6adf977d72c7cbf`；内核SHA `ee2c130fd0e184e4d262f4b0eec86e65c370c3d323413570c761aabe91eca70f`。38项串行作业、3084透明性、2988调用流程（包含963专项）、67绑定全部通过；另29 x18和9向量连续路径通过，独立内核字节复现与整包回读通过。本轮execution.json的38条stderr均为空；历史WSL/GBK异常仍留在旧报告，不写成当前失败。

实际镜像已核对后续6段目标、12对exec/dyld调用与续接及239条件边界，见同目录expanded-trial-objectives.json。46未启动/未消费，当前45已恢复Android；不存在新增实机或EL0完成结论。45原镜像、媒体、原资格和绑定源码均保留，快照清单见reports/session-closeout/2026-10-28/probe45-source-archive.json。PROBE46媒体目录已按实际包创建。

## 收尾校验提示

Git暂存源码/证据逐字节审计通过；初次文档助手因默认GBK读取UTF-8中文失败，已仅修正out助手的显式编码并完成，原失败及初次暂存清单保留，最终清单/字节审计另存final版本。没有改镜像或重写运行检查来消除该宿主文档错误。

`git diff --cached --check`仍报告`scripts/resource_cluster_sites.py:97`一处行尾空格。它是非执行格式提示，保留当前已绑定源码字节；没有屏蔽该检查、改写已有摘要或把格式检查称为通过。后续真正修改该源码时可清理并按新候选重新绑定。38项回归、专项、独立重编及整包回读通过与此格式提示分别记录。

最终提交号和两仓清洁状态记录在项目根`D:/Code/PortingiOS/nuwa/SESSION-CLOSEOUT-2026-10-28.json`（提交后生成，不入本次Git）。前一日receipt是历史快照，不覆盖。