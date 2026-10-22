# STATUS

> 当前唯一真相；更新：2026-10-23T02:39:24+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**R-010诊断已完成编译、实机取证和Android恢复。最新清晰照片确认候选DXE实际执行：27次分配失败，最终仅25页/100KiB空闲，最大8页/32KiB，5段；随后缺核心架构协议并在DxeMain.c(586)断言Not Found。尚未进入BDS或XNU。**

**02:30:04实际nuwa/kalama Android boot_completed=1，02:30:05复核三个分区SHA与试前相同。** 未flash/erase/改槽，未再次启动候选。当前等待R-011具体内存图范围选择；已有单行原厂Heap候选diff和静态区间审查，未应用。

[构建、试验与恢复报告](operations/2026-10-23-dxe-allocation-build-trial.md)，证据reports/dxe-allocation/39829943950/。以clear-screen-1/2.jpg这次较清晰原图为数值权威；原始字节/哈希已保存，未用低清图猜数。

## 本轮真实结果

| 项目 | 结果 |
| --- | --- |
| CI39826580758 | Mu嵌套依赖mipisyst缺失，未编译核心；补丁前递归初始化原gitlink修复 |
| CI39827372451 | 已到真实C编译，DxeMain私有锁声明缺失；加锁包装移回Page.c修复 |
| CI39828647170 | 工具安装360秒超时，编译跳过；发现mirror+file间接选择Azure并修复 |
| CI39829943950 | c9d538f、6m51s成功；666项下载/输入/实际固件静态检查通过 |
| 固定源码 | uefi-nuwa@2ab6827d，UniXNU75bc13dd，Mu cfb93724；0008诊断patch4a859ab6 |
| 实际FD / 核心 | 3145728B SHA d9c3eaa0d5eefd9e237dfd74f7d98402d93764d47cf4126a3c9bba9e4f5b860f；核心167936B/c0135047，实际包含诊断标记 |
| shim / PIL | shim112B/8a3b5476、relative offset0保持；实际空AUTO配置dbc9ee6e与原PILDxe89e030af保持 |
| v4包 | 3153920B SHA9197fed24748e1fa2b79da879e3c58c2018e3db943526d65641f86cb2226c0d6；仅shim+FD，无XNU/FAT/新DTB/ramdisk |
| 唯一临时启动 | 02:27 Sending3080KB/Booting OKAY，15次nuwa fastboot均false；阶段结论另由照片支持，ACK不替代 |
| 恢复 | 用户按电源+音量下回fastboot，恢复等待脚本实际接管，复位bootloader后仅临时加载原boot ef558db2，Android完成1 |

## 运行时证据与边界

最新图断言前`missing-arch-before-assert failures=27 free=25 largest=8 ranges=5 special=0`，5段页数2+3+6+8+6一致；该状态下9页连续申请已超过8页raw最大块，对齐/guard不会增加可分配容量。上方可见type7=208页，紧随1153页申请失败，但完整第一请求type/align/guard/caller/bin头部缺失，仍TODO。

已证实本轮DXE资源不足并有碎片，不是手机12GB DRAM不足，也不是XNU ADT窗口问题。不能据此定位全部开销/泄漏、认定所有协议缺失和SPSS Load Error只有同一个原因，或宣称扩Heap后必进入BDS。Security/BDS/Variable/Variable Write/Capsule/RTC未安装，UniXNUDxe/DarwinBoot被发现但未加载。

当前固件源码初始SYS_MEM/Conv Heap69MiB。单行候选恢复同机原厂209.75MiB：BAE00000/04500000 → BAB00000/0D1C0000，其他内存行/属性保持；严格apply检查通过、未应用。固件其他行无重叠；历史同机Android DT覆盖候选，reserved reg/当时initrd不重叠，未解析节点0。**这只是静态检查，不证明候选ABL实际DT或扩展范围的运行所有权。**

## 下一步

1. 等待[NEED-REVIEW R-011](NEED-REVIEW.md)选择。倾向A：只恢复已知同机原厂Heap一行，保留真实驱动及R-010诊断；B：保持69MiB先审查可选vendor依赖/占用，再给出裁剪diff。
2. 仅在新范围获批后修改独立uefi-nuwa、固定提交并更新CI输入。生成镜像本身无需暂停；设备动作仍须D-021具体日志/恢复门，试后恢复Android完成1。
3. 未知第一请求参数、实际ABL x0 DT/所有权及后续协议/SPSS问题继续TODO；不再为补一张图重复R-010试验。H-005已完成，H-001独立按键演练/H-003历史可选连续录像不阻塞当前文档收尾。

## 已完成内核与后续目标

基座wh1stl3/UniXNU@76dd641保留nuwa补丁，8796内核CI39793231214成功。源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8，Darwin22/iOS16、4KiB段起始、五平台导出、零undefined、三archive哈希及65348项donor指针零失败。完整NativePrelink/运行ABI未验证，历史payload输入仍CI15 a9e08c69，未自动切换；本轮包不含XNU。

Darwin22的608B CommandLine/0x2e0 boot_args已真实编译链接DarwinBoot EFI，运行ABI未验证。目标ADT/provider/定时器/watchdog/13回调仍待验收，ARCH_TIMER/BOOT_PROGRESS仍0；Android DT不能当Apple ADT。ramoops与FD保留区重叠，未占为日志区。本机WSL只编译过shim，不是完整XNU本机构建通过。

## 当前约定

用户已批准R-010 A，生成诊断/固件镜像无需硬停；设备动作前缺过程日志或已确认恢复路径必须停，保留受审内存/身份字段及_verified=true边界，见AGENTS§3/D-021。R-011改变R-010明确排除的原内存图，具体范围另审。

board/feed/当前实际内存图和_verified均不变；board仍example=true，普通基座-D入口未完整打通。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5、硬上限8GiB。两个旧仓只读，Git/GitHub/workflow持续授权；当前Android为原有rooted/custom系统，非完整原厂恢复，既有A槽标志未改。

遇难题主动评估同SoC UniXNU/UEFI来源，固定提交/许可/依赖/验证状态，借鉴实现而不机械抄板值；本次sheng0eb4514d/fuxibb25ad75评估见dxe-allocation-audit。所有QEMU/静态/实机结论分开。
