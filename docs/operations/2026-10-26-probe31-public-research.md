# PROBE31 后公开实现与主线依赖核对

目的：用固定实现区分观测干扰、压缩读取等待及平台依赖，不照搬其他板子的值，不更换 iOS16/8796 身份。未新建/克隆仓库，仅下载必要公开文件到 `out/probe31-public-research/`；来源提交、URL与文件SHA在 sources.json 和 mainline-sources.json。公开说明不是 nuwa 实测。

## 已核对的来源

| 来源 | 固定版本 | 对本机的用途与限制 |
| --- | --- | --- |
| [GopFramebuffer/NativeGOPPresenter.cpp](https://github.com/UniXNU/GopFramebuffer/blob/33e941a878dcf01b98dbd9160d798bd56e7551ea/NativeGOPPresenter.cpp) | 33e941a878dcf01b98dbd9160d798bd56e7551ea；BSD-2-Clause-Patent，LICENSE另存 | 第85—95行检查几何、映射物理地址和长度，使用kIOMapInhibitCache；第120行dsb oshst。提示核对实际映射/可见性；它是IOKit presenter，不等于本机早期直接写Device映射，未复制其驱动或换内存属性。 |
| [ishtar PORTING](https://github.com/markakash/UniXNU-ishtar/blob/a23c94bab4ea94e11f90525d02a1244f04d76f4f/PORTING.md) | a23c94bab4ea94e11f90525d02a1244f04d76f4f | 同SM8550的作者记录指出早期FB地址、16KiB/32MiB映射对齐、残留IRQ及timer INTID问题。目标是iOS18.7.8/XNU11215，nuwa是4KiB/XNU8796；不能照搬loader对齐或板值。其UFS、锁屏结果仅为该仓作者记录。这里只引用文档，未复用代码。 |
| [ArmCpu.cpp](https://github.com/UniXNU/ArmCpu/blob/1951cc8444b340d7d8879e9418220cf29eb711d7/ArmCpu.cpp) | 1951cc8444b340d7d8879e9418220cf29eb711d7；文件SHA3c87b3bd617be5582a6a24ff797c359497ee9feaa702ee883ecee4270db21c9f | 与本地kernel-merged-profile及live-dt-contract固定源摘要相同。第90行启用PPI27，第568行按INTID27分派，随后计数并调用rtclock_intr。不能将ishtar“19改27”当作本机修复；计数器/中断实际送达仍需运行时证据。未改驱动。 |
| [Apple decmpfs.c](https://github.com/apple-oss-distributions/xnu/blob/1b191cb58250d0705d8a51287127505aa4bc0789/bsd/kern/decmpfs.c)、[decmpfs.h](https://github.com/apple-oss-distributions/xnu/blob/1b191cb58250d0705d8a51287127505aa4bc0789/bsd/sys/decmpfs.h)、[vfs_vnops.c](https://github.com/apple-oss-distributions/xnu/blob/1b191cb58250d0705d8a51287127505aa4bc0789/bsd/vfs/vfs_vnops.c) | xnu-8796.141.3 / 1b191cb58250d0705d8a51287127505aa4bc0789；APSL源文件头 | 与当前源内核系列对应，用于读取/压缩接口与等待条件比较；实际本地补丁及donor仍须单独绑定。未将早先浏览的8796.101.5或main当作当前版本。 |

## 主线判断

1. 目前首先要恢复可靠的读取过程证据。PROBE31没有新增原生读取返回/入口证明；单张黑条不区分显示覆盖、写入异常、异步中断和CPU真实停点。
2. Apple `_decmp_get_func` 在注册表项非NULL时直接检查版本/函数槽，不进入“等待type注册”的循环。因此既有A033非零削弱了“同一次稳定type4注册仍单纯等待注册”这一解释，但它不是进入decmpfs的证据，更不是回调执行或返回证明。
3. `decmpfs_read_compressed` 先取压缩数据锁；之后涉及缓存/UPL和fetch，另有转换状态等待。不能用注册成功推导这些阶段成功。现有观察已覆盖APFS调用decmpfs（294/295）、读写锁边界和cluster_read（328/329），收到有效位置后应选对应实现处理，而非全局跳过锁/强制返回。
4. ArmCpu固定源已经使用27；未观察IRQ计数不能断定IRQ正常或异常。其计数器是后续精确观测的已有来源，不需要先改GIC板值。当前没有证据支持盲目修改timer/IRQ。
5. 当前实际根是RAMDisk；UFS驱动是否正常仍未验收。其他仓的UFS电源接管经验只能用于后续专门验收，不是当前RAMDisk读取卡点的直接解释。

当前没有找到可直接认定为nuwa同一故障的公开修复。下一包减少HEX重复写入，同时保留完整47调用/返回及原生exec路径；降低开销不是用户态里程碑，也不能用离线通过替代实测。

## 实际预链接映像核对

新增只读审计 `scripts/audit-read-mainline-contract.py`，证据 `reports/kernel-entry-probe/2026-10-26-v40/read-mainline-contract.json`。固定原内核SHA1aeebf13及emission报告SHAe10770f6；核对PROBE32候选与原映像中的注册表字节及五个目标入口字节一致：

| 表项 | ARM64偏移 | 固定映像目标 |
| --- | --- | --- |
| version | 0 | 3，8796接口接受的版本 |
| validate | 8 | 0xfffffff0056962a8 |
| adjust_fetch | 16 | 0xfffffff0056965d8 |
| fetch | 24 | 0xfffffff005696600 |
| free_data | 32 | 0xfffffff005696a7c |
| get_flags | 40 | 0xfffffff005696a88 |

表基址与照片A033一致：0xfffffff005f48ef8。五个非空目标均落在固定Zlib组件的原始__TEXT_EXEC范围，并各有对应预链接重定位记录。**这排除了当前文件映像中“未支持注册版本/空fetch/这些槽未重定位到Zlib代码”的具体静态缺陷；未读取实机表内容，不排除运行时变化，也不证明回调实际执行或返回。** 因此本轮没有依据替换解压器或强行绕过压缩读取。

同时解析到既有驱动计数器符号：timer=0xfffffff007ac0708、IPI=0xfffffff007ac0710、IRQ phase=0xfffffff007ac0788、IRQ id=0xfffffff007a10938。这里只固定以后精确观测的来源，没有读手机内存、增加IRQ写入或改变驱动配置。

## 访问边界

本轮对旧资料库 `D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng` 的 `git rev-parse HEAD` 遭遇Git dubious ownership拒绝（所有者与当前执行用户不同）。已停止该检出的Git操作，不修改safe.directory/权限、不改读.git来取得同一结果。若需该检出的Git元数据，由正式访问复核处理；本轮独立公开仓库资料不替代或冒充该本地检出的提交身份。
