# PROBE44媒体与PROBE45缓存读取链

阶段S03/S05/S12/S13。用户确认末态稳定，并明确今后默认每次稳定后拍照、无需逐轮再问；未提供本轮等待秒数，记未知。44 postcondition确认nuwa/kalama、Android完成1、A槽及三分区SHA与44预检一致。44已消费不重发，本轮继续下一包离线交付。

## 观测前沿与实际代码

原件保留在`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/`，保留微信原文件名。402源帧与六张用户阶段截图保存到同轮`derived/review-01/`；manifest绑定原件/派生摘要，source-frames保存源PTS。初始截图存在字段尚未画完的时刻，不将不完整字符补成完整值；没有声称已逐帧转录全部HEX。

清晰末态A03D=`FFFFFFF00519C49C`。44匹配的read观察器已经进入APFS属性→ResourceFork vnode查找→文件读取链，记录该处原生x0，随后原生`bl FFFFFFF00525E6DC`导入stub，解析目标`FFFFFFF007438710`（`_cluster_read`）。这是调用前记录，不是异常PC，尚无callee入口或返回证据，不足以确定CPU停止或锁死。

固定44内核SHA为`49b913fc15e1517c51acc57af919c76d32187a1258a3a9fbb7f4890ebe2c74f1`。`reports/kernel-entry-probe/2026-10-27-probe44-analysis/native-cluster.json`保存实际指令/调用/导入解析。`_cluster_read`只有置x4/x5为零及尾分支到`_cluster_read_ext`三条指令。后者根据flags和UIO路径选择copy/direct/contig；固定ResourceFork helper使用SYSSPACE UIO，普通路径优先copy，但实际flags/对象状态仍需运行证据。

`_cluster_read_copy`包含：UBC快拷贝、UPL页面请求、有效页判断、缺页时cluster_io、IO完成等待、拷贝与UPL提交。`_cluster_io`有原生VNOP_BLOCKMAP、VNOP_STRATEGY、buf_biowait和cluster_wait_IO。当前根仍是rd=md0 RAMDisk，这些接口的存在不证明访问UFS。`_mdevstrategy`原生代码存在memmove/bcopy_phys和buf_biodone链，仍不能从静态存在推断本次已执行或完成。

有界CFG分析与线性指令扫描交叉核对：cluster_io调用实际位于743914C，保存到copy-linear-calls.json；ubc-copy-native.json保存缓存快路径。完整范围和分支不是仅凭函数名猜测，也不将保守CFG中panic后的顺序边当实际正常路径。

## 最大疑点、反证和下一轮证伪

首要疑点是缓存页面准备或下层IO完成等待未取得可观察返回。支持：末态稳定在原生cluster_read调用前，且read观察配对/帧/线程已匹配；APFS此前锁、属性处理及vnode查找已经被执行路径越过。反证/不足：没有cluster入口、UPL或IO内部位置；诊断绘制干扰或记录遗漏仍可能解释末态。不能认定某把锁、内存分配、IO提交或中断出了问题。

原生copy路径读取`_PAGE_SHIFT_CONST`用于页大小和UPL长度运算。45在该常量已加载到x19的位置记录寄存器，作为附带区分值；其余点A03E仍是原生x0，不能统一当errno。收尾符号核对澄清：地址715D118属于`_PAGE_SHIFT_CONST`，可变全局`_page_shift`位于7A77A48，并未被采样。早期文字及观察元数据中的“page_shift”是该页移位读数的泛称，不得解释成可变全局值。

45连续观察5个函数：cluster_read_ext、cluster_read_copy、cluster_copy_ubc_data_internal、ubc_create_upl_kernel、cluster_io。覆盖入口/返回、父子配对、缓存快拷贝、memory_object_upl_request、VM/IO等待、BLOCKMAP/STRATEGY及对应续接；保持后续原生读取、解压、exec。UPL函数的早期无栈返回与正常返回分别按实际前言/尾声处理。

若停在缓存快拷贝或UPL请求前且没有续接，优先分析VM/缓存页资源和等待条件；若走到STRATEGY、biowait或msleep，再按实际完成/唤醒链定位；若这些返回并出现APFS519C4A0/后续解压，则推翻“cluster读取未完成”，依据新前沿推进。仅有调用前点仍不证明callee入口。观察限定原read线程，异步完成在其它线程上没有独立观测，不能用“没记录到”否定完成。

64个新位置、160B新状态，沿用A03D/E两行，不加网格；观察器仍有绘制成本，未实现完整记录/显示分离。保留原生锁/错误/IO、Restore根和239限制，不凭速度跳过任何原生检查。完整资格未完成前不可部署。

本轮沿用已固定的XNU本地原始实现`bsd/vfs/vfs_cluster.c`及实际部署指令；此前公开资料工具403的访问缺口仍保留，没有更换通道绕过，也不称已经取得新的公开资料验证。

## 问题数量与基础依赖复核

用户提出“内核启动不应该有这么多问题”。这里必须区分：多轮推进的最后观测点，多数属于同一条首次ResourceFork读取尚未闭环的逐层定位；已经证实的独立诊断缺陷包括41的x18渲染指针问题，不能把每轮最后位置都写成一个新内核故障或修复。

重新查阅S04依赖及实际代码：向量交接、线程/分配路径可见，不等于timer/IPI/DMA/所有唤醒资格已完成；同样，缺独立验收不等于这些能力已经故障。当前RAMDisk的`bsd/dev/memdev.c:mdevstrategy`正常读取路径同步执行bcopy/bcopy_phys、buf_unmap并buf_biodone，错误/EOF路径也完成buffer；未含UFS DMA提交。因此优先区分VM/UPL页面资源、IO是否分派、完成/唤醒是否走到，不能从等待预先指定UFS或GIC。实际mdevstrategy是否命中仍未观察。

首次新增检查在原生参考单条指令执行时发生UC_ERR_READ_UNMAPPED，失败说明保存在cluster-checks-failure-01.txt。修正夹具：x19=12只用于page_shift点，原生指针使用已映射测试地址，原生执行与候选寄存器/控制流差分不放宽。第二次770项检查通过，完整输出cluster-checks-console-02.txt；这次夹具错误不记为实机新故障。完整38项串行资格正在进行，不能以专项通过替代整包。

后续若45命中VM/IO等待，优先核对该等待的完成者、provider注册/初始化和调度唤醒依赖，先解决代码能确定的缺口；没有新的分支证据时，不仅把单个观测点再向下细分。若所有读取续接可见，转向实际后续错误/解压/exec，避免长期停留在已经越过的层。

收尾首次静态符号检查错误地要求可变`_page_shift`地址等于715D118，已严格改为匹配`_PAGE_SHIFT_CONST`。失败及随后尝试读取BSS而发生StopIteration的记录保存在native-globals-failure-01.txt；未改内核指令、未改既有38作业证据。最终native-globals.json按修正后的符号语义记录，不把BSS磁盘值当运行值。

`_PAGE_SHIFT_CONST`文件初值为0；本地原始实现arm/arm_init.c:390起根据boot_args.memSize选择PAGE_MAX_SHIFT或ARM_PGSHIFT进行初始化，arm64/arm_vm_init.c将其声明为SECURITY_READ_ONLY_LATE。这个静态初值不等于实际运行时仍为0；本轮没有改任何内存/页参数，也不据此认定初始化失败。45对应点记录的是执行到缓存路径时x19中的实际值。

## 23:09 +08 整包离线完成

- 镜像`D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/trial-boot/xnu-entry-probe-45-cluster/boot-xnu-first-entry.img`，204484608字节，SHA256 `e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d`。
- 内核SHA256 `2935ab6e53067a5daa4156510e158f3eebe765c50592abbd4b617375c2f05247`；ADT SHA256 `052f0a91465cef62f78037555c4e29861e3a90805b69085bd1a50c1f9f44bbeb`。
- 38串行作业通过：3024透明性、2795调用流程（含770新增）、67绑定；另29 x18扰动及9向量连续路径通过。独立内核重编逐字节一致、整包回读通过，菜单PROBE45。
- 44旧内核/镜像、原媒体及六阶段截图摘要一致；Restore根、固件FD、shim和原boot保持。未改变媒体工作流源码，引用44的6项既有目录检查及原SHA，未冒称本轮重复执行该检查。PROBE45/original及derived已通过实际包元数据创建。
- 资格`reports/kernel-entry-probe/2026-10-27-probe45-cluster/qualification.json`；包报告`reports/xnu-first-entry/entry-probe-45.json`；差异`changes-from-probe44.diff`；native-globals.json只核对静态符号和文件常量，不证明timer/GIC运行计数。

45未启动/未消费，239保持；没有新的实机启动、flash/erase/改槽或提交。原生读取/解压/exec和EL0仍待闭环。WSL/GBK日志异常及两次宿主检查失败保留，不能把离线模型或修正夹具写成实机问题修复。

## 同轮扩大目标：读取返回后继续到exec受控边界

用户要求“下一轮在原定基础上推进得更远”。已回查45实际build的dense_bootstrap站点、exec_path_sites.py和exec_trace_sites.py，确认12对exec/dyld路径调用及续接、任务切换/签名/释放点均已在当前内核；fetch/decode/result点也已登记。root-stop的15项既有检查验证正常首次exec和错误返回继续执行，只有匹配任务、已观测切换和w1=2等条件成立才进入239。

同轮目标顺序：缓存/UPL/IO返回 → ResourceFork helper完成 → type4取数与解码回调 → Mach-O激活/load_machfile → dyld查找/授权/读取 → 任务切换/签名记录及239受控释放边界。每段根据配对续接及后续可信记录判断，不以单个静态格点代替完整时序。成功续接不中断，错误按原生路径处理并保留首项阶段/返回。

A02C为exec尝试数，A02D/A030为原生激活/exec返回，A02F为任务切换观察；A02E/A032保留对应尝试的首项非零阶段和原始返回，部分加载状态不是errno。239表示受控Restore释放门，不能升级为EL0或桌面结果。当前读取未完成仍是前置条件，扩大验收范围不代表已修复等待。

静态范围核对记录`reports/kernel-entry-probe/2026-10-27-probe45-cluster/expanded-trial-objectives.json`，绑定当前镜像和原资格SHA；6段目标、12对exec路径全部已有站点。镜像仍为e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d，沿用已完成的独立重编/38作业/包回读资格，无新运行结果。45尚未启动。
