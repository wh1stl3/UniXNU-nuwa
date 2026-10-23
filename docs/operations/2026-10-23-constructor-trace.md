# 库构造链细化诊断

2026-10-23T18:59:02+08:00，用户“继续，还有要实机做的验证吗”。本轮先离线构建，不执行ADB/fastboot或启动新包。晚间实际Android完成1及三分区不变结论保持。

## 审查结果

晚间新图已显示入口HOB调用返回非空data，最后before-library-constructors。固定实际BUILD_REPORT列四库构造；源码和先前link-map含内联调用，不能把报告列出顺序误当作运行PC采样。

firmware ddd794fc的FrameBufferSerialPortLib.c:326函数SerialPortInitialize仅return EFI_SUCCESS，BaseDebugLibSerialPortConstructor直接返回该调用；没有清屏或硬件配置代码。此结论仅排除该固定函数具有重置实现，不排除其他日志路径异常。

Mu cfb93724四个构造：Debug调用SerialPortInitialize；Extract三次AllocatePool及BuildGuidDataHob；ArmMmu通过GetFirstGuidHob取替换入口或WriteBackDataCacheRange；Lzma注册GUIDed handlers并返回原状态。原错误码、分支和顺序必须保留，不能为通过而跳过任何构造。

## 候选

0011-mu-constructor-trace.patch在四个构造添加NUWA-CTOR的Debug/Extract/Mmu/Lzma enter与leave status=%r。Debug/Lzma用局部变量暂存原返回状态，其余成功/失败返回前打印。新DebugPrint调用本身不调用构造函数，不在SerialPortInitialize里递归输出。所有调用及返回表达式经去除日志、归一化临时变量后与原函数严格一致；不是时序或运行等价证明。

范围：共享Mu库，既影响SEC也影响链接对应库的其他模块，非SEC-only二进制修改。没有改内存表、构造生成器AutoGen、固件源码仓HEAD、PIL配置或BootShim；保留既有分配诊断。新profile constructor-trace从sec-handoff派生，39个固定输入和4个post-patch新哈希、其余配方不变检查通过。CI在一次性源码中严格git apply --check再应用；本地只在内存应用，不写旧仓/上游。

源码来源microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5，四文件头BSD-2-Clause-Patent，逐文件SHA/原构造行号见reports/constructor-trace/proposal.json。同SoC uefi-sheng@329b473d的相同顺序审查仍见reports/sec-handoff/same-soc-order.json；本次不移用其板值或构造顺序。

## 构建和实测门

workflow增加constructor-trace选项；实际SEC检查要求8条新marker、4条HANDOFF及原ENTRY，原Heap、PIL、shim、四个加载器模块、PCD和DXE分配诊断门全部保留。共享库日志可能改变DXE核心哈希，必须按新实际产物记录，不能沿用8fccb5c9。

新构建结果与实际41行内存表回归待检查。输入/源码静态检查不是编译或实机成功。下一次实机有必要，但应等新包通过检查后，只验证“最后进入哪个构造、是否返回以及状态”，再跟踪DXE/SHENGMEM；重复2d833461不会增加单构造信息。具体启动前仍需人在场拍摄、通知及fresh身份/恢复门；本轮没有启动新候选。

命令：python scripts/prepare-constructor-trace.py（新目录，仅生成本仓补丁/profile/JSON），python scripts/check-constructor-trace.py；39项静态检查通过。未来实际启动载荷、ADT、NativePrelink和iOS系统卷不混入此轮对照。没有board/feed/bringup-plan/验证标志修改。
