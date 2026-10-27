# 按阶段规则重新审视主线与当前卡点

2026-10-27，离线工作：不用设备，仍查阅在线原始资料。适用S01/S04/S05/S06和S12/S13；依据AGENTS第0、6、8节及DEVELOPMENT-STAGES通用方法。没有修改板值、内核、镜像、认证、错误处理或239门，没有提交。PROBE41仍未消费。

## 结论与工程判断

当前最高优先级仍是**ResourceFork块表读取调用到返回之间的进度**。现有实测不足以把范围进一步确定为某个分配器、APFS锁或设备IO；也不足以说CPU已停止。不能继续按“第二次IOMallocData失败”或“codec算法已卡死”主导修复。PROBE40可见535调用前，536续接未辨出；后者不是完整时序证据。

本次有两项新增约束：固定内核确实使用另一条双分配UIO路径；`getxattr`描述符在初始化表中存在且未禁用。真实指令在明确夹具下能正确创建UIO、添加向量及分派参数，因此确定性的这些布局/包装错误目前排在等待型资源路径和观察不完整之后。实际分配器、文件系统处理器以及运行时操作表仍未执行或捕获，不能写成已排除。

| 排序 | 疑点与支持证据 | 反证/限制 | 最小证伪路径 |
| --- | --- | --- | --- |
| 1 | ResourceFork取数链内部未取得可观察的完成；535/536边界直接支持，链中有独立分配和文件系统操作 | 只定位到调用边界，不证明helper进入或确定等待；机制归因置信较低，范围定位置信较高 | 现有41区分6D2C入口、6D6C/70创建、6D9C/A0属性读取、6DA8/AC释放、6E80/7158返回；本轮不上机 |
| 1a，待区分 | UIO的等待型分配。固定指令调用`_kalloc_type_impl_internal`与`_kalloc_ext`，前次IOMallocData返回不能验收它们 | 没有内存压力或分配器内部等待证据；夹具不能证明真实分配返回 | 若41停留在创建调用前沿，再围绕实际分配调用/续接和线程状态取证，不猜改heap |
| 1b，与1a并列待区分 | vnode属性分派及APFS取数路径。属性来自ResourceFork，不等于先前普通read路径 | live v_op未知；静态候选不等于实测目标，不能指认某锁 | 若创建返回且VNOP未见续接，先取得live目标，再按实际处理器追踪 |
| 2 | 错误输出、释放或诊断显示延迟造成前沿假象；helper有真实日志/释放分支，既往跨轮显示前沿变化 | 尚无这些分支本轮进入证据；静态稳定照片不提供等待时长 | 利用41既有日志/释放配对点；保留时间与遮挡限制，不将最后记录点写成停止PC |
| 3 | UIO布局、描述符注册或包装参数的确定性错误 | 本次实际指令模拟支持所测参数正确，静态表含描述符且flags=0；不覆盖运行时损坏/初始化失败 | 若live index、v_op或UIO字段与固定初始化模型矛盾，再检查真实写入者 |
| 4 | 第二次分配失败、既定压缩输入损坏、codec本体 | 40已有第二次分配非零/向量/decode证据；宿主188块/窗口闭包降低输入损坏优先级；尚未观察到codec执行 | 保持原错误和认证路径，待资源读取返回后再以真实输入/错误定位，不先改解压算法 |

以上排序是工程判断。当前不能在1a与1b之间作可靠排序；没有足够事实支持确定死锁、UFS故障或确定调度故障。

## 新的代码证据

固定输入`out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho`，SHA256 `1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6`；APFS executable SHA256 `ebc47d686c6917c7fb154a0b2e2ed19e3d6a277d994d1395b02d3214142577cc`。本次使用原输入，不改历史证据。

- `scripts/audit-resource-progress.py`：声明窗口内保守控制流遍历，保留原指令、直接调用、间接边界和回边；不深入被调函数，不宣称完整CFG。`resource-paths.json`包括四个XNU函数和一个APFS静态wrapper候选。
- `uio_create`的`...76BCD48`传`0x8004`，实际调用`_kalloc_type_impl_internal`；第二次分配请求16字节，低16位flags为`4`。对照8796的zalloc定义，前者是WAITOK/ZERO/NOFAIL，后者WAITOK/ZERO（可含上层tag）。WAITOK是允许等待，不是已经发生等待。
- `scripts/test-native-resource-uio.py`实际执行固定`uio_create`和`uio_addiov`指令，三组(offset,length)=(264,8)、(336,23707)、(384,33021)。两个分配器仅由明确零填充返回夹具代替。初始化的iov、offset、segflg、direction、resid和flags符合检查；已满向量及NULL UIO返回-1，已满错误分支未修改原UIO/iov。
- 固定`_vfs_op_descs`有63项，getxattr位于表项51，描述符flags=0，磁盘初始offset=0。**磁盘offset不是运行时index**。Unicorn实际执行`_vfs_op_init`后，在本模型得到index51；再执行`_VNOP_GETXATTR`，以明确vnode/操作表/handler夹具核对参数，fixture errno93原样返回。未捕获实机index或目标，未执行APFS主体。
- APFS `0xFFFFFFF00519CB28`静态wrapper候选包括vnode_mount、vfs_fsprivate、vnode_fsnode、一次未解析间接调用和若干内部调用；不能仅凭这一层未出现具名lock调用，就排除其子调用里的锁或IO等待。

输出统一在`reports/mainline-reassessment/2026-10-27-r1/`：`tests.json`、`resource-paths.json`、最终`native-uio-vfs-r2.json`和`qualification.json`。六项CFG控制测试通过；三组UIO正常/错误分支及一项VFS模拟通过。级别是静态检查与Unicorn执行，**不是QEMU或实机通过**。

## 以官网顺序重新检查依赖

| 阶段 | 当前能确认的范围 | 必须保留的缺口/实际影响 |
| --- | --- | --- |
| S01/S03 OS/装载契约 | 8796/iOS16固定诊断链已到原生文件读取；41有独立复现和包回读证据 | board.toml仍example=true，尚非合格Format2平台profile；不能把现有诊断链资格转授给模板迁移 |
| S04 平台 | 有内核执行、线程和分配路径可见 | 本次绑定的证据未提供启用CPU各自timer/IPI、设备DMA完成的独立验收；不等于全库不存在记录或它们已故障。等待问题出现时须回查实际消费者/唤醒路径 |
| S05 root/存储 | 当前`-v rd=md0`是RAMDisk路径；固定压缩输入可宿主解码 | 原生ResourceFork读取/解压尚未闭环；RAMDisk不验收UFS，UFS不能被直接定为本次根读取原因；可写Data/持久化未验收 |
| S06 用户态 | 38文件闭包；完整20H392的OS/两个cryptex已有只读输入盘点，含桌面程序/532主配置/44缓存文件 | 仍缺组合命名空间、cache主/子引用与UUID/路径闭包、Data/服务范围、原生exec认证/映射和EL0；239释放门保持，不批量放行恢复服务 |
| S07/S08 桌面接口 | 固件/诊断帧缓冲能观测部分内核进度 | 尚无iOS16 IOSurface/MobileFramebuffer生命周期、swap完成和HID到界面事件的验收；HEX/网格不是桌面呈现通过 |
| S12 日志/恢复 | 40原媒体与补充条带证据保留；最后恢复证据12:00:43+08 Android1及三SHA一致 | 不是本轮设备查询；静态照片有遮挡/时序限制。持久内核日志未建立闭环，不自动循环设备 |

这个顺序要求修复实际依赖，也允许提前完成后续静态工作。下一项可直接推进的离线任务是OS/cryptex虚拟命名空间与cache引用闭包；同时按实际资源读取调用完善证据，不为每个静态成功点增加实测。

## 命令、失败与交付边界

工作目录`D:/Code/PortingiOS/nuwa/UniXNU-nuwa`，Python实际运行文件`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`，使用`-X utf8 -B`。以下项目脚本串行执行，输出路径已存在，仅供追溯，续验须选择新路径：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/test-resource-progress.py --output reports/mainline-reassessment/2026-10-27-r1/tests.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/audit-resource-progress.py --output reports/mainline-reassessment/2026-10-27-r1/resource-paths.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/test-native-resource-uio.py --output reports/mainline-reassessment/2026-10-27-r1/native-uio-vfs-r2.json
```

初次CFG测试的模块名与连字符文件名不匹配，ModuleNotFoundError；改为按文件导入后六项通过。初次audit因重定向父目录不存在而未启动，创建新报告目录后通过。这两项是本轮工具输出转述，没有伪造原始日志。native初次失败`KeyError: dispatch_fixture`，原日志`native-console.txt`保留；补注册sys.modules后通过(`native-console-r2.txt`、初版`native-uio-vfs.json`)；随后增加已满/NULL错误检查，新结果保留在`native-console-r3.txt`、`native-uio-vfs-r2.json`，没有覆盖初版结果。

PROBE41包本轮新读SHA仍为`8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a`，204484608字节。观察范围已经覆盖本轮最小区分点，本次没有依据改动诊断内核或重编同一镜像。未触发硬停，未设备访问/启动，未改受审字段，现有迁移修改保留。资格文件绑定本轮源码、报告及包摘要，不重算历史报告来代替旧验证。

## 在线原始资料（2026-10-27查阅）

- [UniXNU驱动顺序与边界](https://unixnu.com/porting/drivers)、[平台资源](https://unixnu.com/porting/platform)、[启动验收分层](https://unixnu.com/porting/bring-up)：本地S04/S05/S06依赖和验收范围的依据；网站方法不是nuwa运行结果。
- Apple [kern_subr.c](https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8796.141.3/bsd/kern/kern_subr.c)、[kpi_vfs.c](https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8796.141.3/bsd/vfs/kpi_vfs.c)、[zalloc.h](https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8796.141.3/osfmk/kern/zalloc.h)，固定tag xnu-8796.141.3，APSL等原文件许可；作为机制参照，实际调用/参数以上述固定Mach-O指令为准，没有复制上游实现。
- 领先设备版本/许可和与iOS16的差异沿用`reports/desktop-readiness/2026-10-27-reference-r1/manifest.json`；本次没有新增导入或将第三方桌面结果升级为nuwa证据。
