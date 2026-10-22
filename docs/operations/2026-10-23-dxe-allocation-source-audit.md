# DXE分配失败的静态审查与下一诊断候选

范围：用户要求恢复主线并遵守硬停；本轮仅源码/已下载产物/同SoC固定来源分析，未操作设备、未生成镜像、未修改固件检出或board/feed。用户追加的“遇难题时评估同SoC UniXNU/UEFI仓库”已写入AGENTS.md§7，作为仓库持久约定。

## 当前可证实的内容

上轮实机照片与候选专属GUID确认执行至DXE；UniXNUDxe/DarwinBoot为discovered/not loaded，存在AllocatePoolPages失败和缺失架构协议，最终DxeMain断言。R-009最后恢复Android完成1是历史已验证结果，本轮没有重新读取设备，不称刚刚确认在线。根因仍未实测确定。

本轮固定固件2ab6827d及Mu_Basecore子模块cfb93724a06ff86ff5ba971413368a7809ee42a5。只读缓存Mu HEAD与该子模块一致，相关源码逐git对象比较（规范化CRLF）一致；未对来源执行任何写操作。source-audit.json保留文件hash/行号；实际构建库选择依据CI39820752081的BUILD_REPORT.txt，而非任意版本EDK文档。

| 问题 | 证据与结论 |
| --- | --- |
| 当前初始SYS_MEM/Conv来源 | MemoryMapLib.c只有DXE Heap符合SYS_MEM+Conv，BAE00000/04500000，69MiB；其他Conv的MMIO/NoHob不是额外系统可分配RAM |
| SEC/HOB路径 | Sec.c以DXE Heap构造HOB；MemoryInitPei.c按原表发布资源及分配HOB，Runtime/Reserved/BsData不会因为物理属于DRAM就自动全部变成ConventionalMemory |
| 原厂差异 | 已匹配安装xbl_config的原表DXE Heap为BAB00000/0D1C0000，209.75MiB；取自同机原表，不是新猜地址，但当前配置与原表差异不等于运行故障根因 |
| 错误日志含义 | Page.c:2355起CoreAllocatePoolPages以FindFreePages搜索，Start=0才打印失败；Pool.c包装层已持gMemoryLock |
| 搜索限制 | FindFreePages先尝试类型bin、默认bin、全允许区，再PromoteMemoryResource并重试；底层只看Conventional且排除EFI_MEMORY_SP，并做地址、对齐、guard检查。失败不能只归因总容量 |
| 最终断言 | DxeMain.c先CoreDispatcher，再显示缺失协议/未分派驱动，CoreAllEfiServicesAvailable后ASSERT；照片的Not Found是服务检查结果，不能误当最早分配API状态 |

照片233页请求按UEFI4KiB页为954368B；它不是“请求了233MiB”。当前运行时空闲页/最大连续块、失败PoolType/Alignment/NeedGuard和调用者均TODO；物理12GB不能替代UEFI分配器的可见资源。

## 同SM8550来源评估

此次只读既有固定提交，不追最新、不自动合并；片段/行号/SHA/永久链接见sm8550-references.json。

- [uefi-sheng@0eb4514d内存表](https://github.com/UniXNU/uefi-sheng/blob/0eb4514db0744b8136a3897ab1af93b713c2c27b/Platforms/Xiaomi/shengPkg/Library/MemoryMapLib/MemoryMapLib.c)：同样209.75MiB Heap，并存在该平板独有的额外低地址gap/高地址bank。其APRIORI使用vendor硬件条件门；额外bank注释中的验证状态不一致，不能全部看成已验证，更不转移为nuwa证据。帮助：提示审查资源发布与驱动负载；不采用其额外地址。
- [uefi-fuxi@bb25ad75内存表](https://github.com/hanzi123-bilp/uefi-fuxi/blob/bb25ad75eedf2c224951c71767a077976b721793/Platforms/Xiaomi/fuxiPkg/Library/MemoryMapLib/MemoryMapLib.c)：同样209.75MiB Heap，最小vendor=0分派；源码文字并不构成其真机验收。帮助：评估最小驱动链与堆需求；不能据此删nuwa真实驱动或声称恢复该大小就能启动。

许可证元数据BSD-2-Clause见此前同固定仓审计；本轮只保留片段与评价，未导入二进制或整树源码。Mu诊断目标文件自身SPDX为BSD-2-Clause-Patent。

## 源码诊断草案：0008

`scripts/preview-dxe-allocation-trace.py`从只读Mu的固定git对象在RAM生成两文件patch，不apply：

1. Page.c首次pool页搜索失败时记录请求类型/页数/对齐/guard/包装层调用地址、类型和默认bin边界；遍历现有gMemoryMap汇总非SP的Conventional页数/原始最大空闲区间，各EFI类型页数，以及前8条自由区间。汇总包括所有区间，打印列表限8条。
2. DxeMain.c在服务检查失败、最终ASSERT之前再次打印当前快照，避免首次失败信息滚出屏幕后完全丢失。保留原有错误返回和断言，不跳过服务检查。

Helper不调用AllocatePool/AllocatePages/GetMemoryMap，不增加内存/修改资源。首失败调用已处gMemoryLock内，最终快照显式持同一锁。实际CI的BaseDebugLibSerialPort用栈缓冲格式化、FrameBufferSerialPortLib走现有显示路径；源码没有新增pool分配，但仍存在锁内打印/时序/整屏cache flush开销。不能声称无扰动或独立USB日志；实际编译及运行未验证。调用地址是CoreAllocatePoolPages调用层，未承诺立即识别最上层驱动。

最大自由区间是未按该请求alignment/guard裁剪的raw范围，不等于保证能满足请求。快照只针对失败时点，没有成功分配历史/早期完整运行map，仍可能需后续进一步取证。

复现：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/preview-dxe-allocation-trace.py
```

preview.json记录目标原/候选LF SHA、patch SHA、精确命令和限制。`git --no-optional-locks -C <只读Mu> apply --check -p2 <0008>`通过，**没有执行git apply**。固定Mu原blob带CRLF，最初LF补丁检查失败；现补丁保留其CRLF上下文、.gitattributes只为这份patch设-text以保持哈希和严格适用性。未用ignore-whitespace绕过检查。**现有CI统一LF正规化与该原样patch不兼容；获批后的具体接线须只对这两个目标保留原行尾，并检查原始/变更后hash，不能直接塞旧管线。**

本轮仅静态检查通过，未编译任何新Mu/EFI/FD/shim，未改独立固件分支。新诊断固件属于硬停第3类，列R-010后等待批准。

## 路径比较

倾向A：保持当前内存图/驱动链，编译上述分配器诊断并在一次受限临时启动后恢复Android，先辨别总量、碎片和类型/限制。代价是新一次构建/观察，帧缓冲日志仍需照片；收益是避免先猜堆参数。

B：基于同机原厂表审查恢复209.75MiB Heap，暂不加分配器诊断。代价是改变固件分配范围，必须核实Android保留区、ABL交接、MMU/HOB、动态RamManager与其他区域重叠；它不是只加一个数，也不能拿同SoC仓作为nuwa运行证明。此方案本轮未准备修改内存图，更未生成镜像。

待R-010具体选择。board/feed、D-002窗口、4KiB及donor身份保持，不因UEFI分配问题重开已废止的容量讨论。
