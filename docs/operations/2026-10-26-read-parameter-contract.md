# PROBE28 参数契约与模拟夹具修正

2026-10-26，基线19e096f。用户最新授权继续必要的离线测试/诊断改进；此前“只分析、不实现”限制在这个最小范围内被后续要求替代。设备操作仍全部暂停。没有重建内核、改包、操作设备或推送。

## 本轮结论

实际交付DarwinBoot把同一个owned window写入memSize和memSizeActual；当前ADT值为1GiB。固定内核arm_init中的已定位初始化块写PAGE_SHIFT_CONST=12；实际header参数准备指令据此产生4096字节、UIO_SYSSPACE=2、IO_NODELOCKED=8。新增9组原生/探针对照全部通过，参数完整传到uio_addiov和VNOP回调，权限/错误返回保持。

这是指令块执行、原生包装器模拟与静态检查通过。不是完整EFI或arm_init执行，更不是实机页大小、MAC/APFS读取或解压成功。最早未验证卡点仍为250到达、251未观察。

## 固定输入及真实ABI

证据：reports/kernel-entry-probe/2026-10-26-v36-parameter-contract/contract-final.json、validation.json。候选内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07保持。ADT458232d6保持，其/chosen/darwinboot-memory-size为0x40000000。不能把设备总DRAM当作这个字段。

实际EFI：out/upstream-firmware-40014018074/nuwa-firmware-40014018074/build/AARCH64/DarwinBoot.efi，SHA256 3313e8568b97432675c33e76dc3b8a7240cfff66a1cd0559ba33e2f512440145。Boot的RVA0x233c..0x2364读取栈中同一窗口值x9，分别str到args+0x2d8和stp到args+0x18。4组窗口输入执行该实际指令块，两个字段相等，0x478保持零；这些是存储块边界案例，不是物理分配成功证明。

DarwinBoot固定上游d099354d0eab34df5088ca1ba89c9c88bc3260bb原头文件为Darwin23布局。交付固件应用patches/loader-candidates/0005-darwin22-boot-args.patch，iOS16/8796的memSizeActual实际偏移为0x2d8。源文件LF哈希与固件inputs.json匹配，补丁及EFI字节分别绑定，不把上游未补丁头文件当成交付ABI。

发现scripts/test-probe-transition.py仍把memSizeActual模拟值写到1144/0x478。本轮只修正该夹具到0x2d8，并显式输出UTF-8/LF；不修改loader或任何受审板值。修正后从实际入口重新执行normal路径，5项检查通过，到_kernel_bootstrap，无非法内存访问，最终FB/probe/vector映射与旧报告相同。旧报告保留，不再作为Darwin22该字段透传的证明。

新旧transition完整快照不相同：除ABI元数据外，x15/x16快照和_pmap_bootstrap入口x0存在跨次变化。validation.json保留全部6处差异。本轮没有确定其变化来源，也不声称整个启动模型逐字节可复现。每次执行内的TTBR0/1寄存器保护断言保持，5项验收均通过。

## 页大小与读取长度

固定原始内核SHA1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6。0xfffffff007972e74..e88实际指令执行后_PAGE_SHIFT_CONST从测试哨兵变为12。0xfffffff00769bf40..bf90执行真实header参数准备，模型只替代其中两个context API；x3=1<<12=4096、w6=8，offset=0、rw=0，凭据及栈参数透传。

Apple固定[xnu-8796.141.3 arm_init.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm/arm_init.c)包含memSize>1GiB的通用选择逻辑。这不能代替本候选实际指令；本轮定位块为直接写12。未完整执行arm_init，也未证明后续不存在其他写入或实机一定读取该值，因此当前4KiB是固定初始化/读取契约证据，实机运行时值仍待观测。

已有bootstrap报告TCR=0x22a51a251a，独立解码TG0=0、TG1=2，两者均为4KiB翻译粒度；PAGE_SHIFT_CONST则由另一组指令读取。Arm[Memory management 101811 v1.0，第7节](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/LearnTheArchitecture-MemoryManagement-101811_0100_00_en.pdf)明确区分TG0/TG1及其不同编码。两种值在当前证据中数值一致，不构成通用等式；没有修改TCR、内存窗口或板值。

16KiB仅作负对照：在隔离模型中把global设为14，真实header指令产生16384，因不符合当前初始化契约被识别；不据此声称当前镜像支持16KiB运行。另把真实mov w6,#8在内存中改为#0，参数断言拒绝。交付内核未改。

## 读取覆盖与失败纠正

scripts/test-read-boundaries.py只增加可选参数与API事件捕获；原默认调用/输出保留。新测试scripts/test-read-parameter-contract.py覆盖success、MAC拒绝、读取EIO、swap、MAC未返回、文件系统未返回、短读且接收/不接收残余长度、既有NOAUTH控制。普通路径flags8仍调用MAC；NOAUTH只作为既有原生分支对照，未加入生产旁路。

9组均比较候选与12处恢复原指令的参考路径：31通用/32SIMD寄存器、SP/NZCV/FP状态、线程、调用方栈、活跃原生写入及API参数完全相同。uio_addiov的buffer/4096长度、实际VNOP参数结构中的flags8（NOAUTH对照为0x8008）得到显式核对。MAC/APFS函数体由API模型替代。

短读首轮错误预期为“外层aresid=NULL则EIO”，测试失败已记录initial-failure.json。实际[固定vfs_vnops.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/vfs/vfs_vnops.c)中vn_rdwr总向vn_rdwr_64传局部int64残余指针，外层NULL只跳过最终拷贝，因此本入口仍返回0。直接vn_rdwr_64的NULL-resid分支不在本入口范围。短读128的两种外层指针案例均与原生参考一致；不把返回0等同于读取4096完整成功，后续exec残余处理仍需单独核对。

默认旧11组重跑输出与原read-boundaries.json逐字节相同；原24项全套未机械重跑。原23份绑定报告、包权威报告及包/内核/ADT重新核对SHA均保持。初次附加检查曾错误要求整个transition跨次相等，该断言失败及实际差异已保留，不计为通过；最终只报告实际验证过的5项及最终映射。

## 续接与验收

复核入口：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/test-read-parameter-contract.py --build reports/kernel-entry-probe/2026-10-26-v36/build.json --output reports/kernel-entry-probe/NEW-FRESH-DIRECTORY/contract.json
```

输出必须新建，不覆盖既有证据。所有脚本/构建/模拟继续串行。

离线本项完成，没有证据要求改有效PROBE28。中午有人在场不自动授权设备动作；待明确当轮画面拍摄/读取、恢复与临时启动范围后，重新检查设备身份、Android1、槽位和三SHA，才可按原门禁使用同一有效PROBE28。观察266..275/A034/A035，先判断MAC或VNOP/APFS哪一侧未返回；272到而273未到才把内部锁/UBC/认证/UPL/fetch列为下一项实机分解对象。权限/认证、239恢复用户态门和_verified保留；不跳到Mach-O/dyld或iOS用户态成功结论。
