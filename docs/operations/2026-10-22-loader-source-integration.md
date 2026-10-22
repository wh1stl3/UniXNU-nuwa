# CI15 内核、原厂内存证据与加载器源码接线

2026-10-22 18:04（Asia/Shanghai）。本轮只修改设备仓的补丁、检查器、清单和文本证据；两个参考仓、三个源树均只读。没有生成 EFI/FD/BootShim 二进制、预链接内核或 boot.img，没有设备动作。

**结果：三份源码候选补丁完成，75 项静态检查通过；实际固件编译、分派与 XNU 启动未验证。** 不能把本轮称作完整启动链通过。下一步生成固件产物触发 AGENTS §3 第3类硬停，见 NEED-REVIEW R-004。

## 固定输入及交付

| 输入 | 固定版本 / 依据 |
| --- | --- |
| 本仓真实平台内核 | CI15 39755850870；20,187,888 B；SHA256 `a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a`，本轮重新读取下载文件校验；ArmCpu、ArmDTPlatform 已真实链接 |
| UniXNU | `75bc13dd34dc4e403826793739e316a264ce00dd`，读取 package/UniXNUPkg 与 drivers/DarwinBoot/DarwinBootPkg |
| mu-nuwa-firmware | `6c6755012728c9f7de748228758bad94d1e9a660`，nuwa DSC/FDF/DeviceBuild、BootShim、基础库 |
| uefi-sheng | `329b473df1e53a3bfa64b2b39b79670c4c02279b`，只复用 ShengBootMemoryDxe 的 initrd 发布部分 |
| 并行参考 | 开始观测 HEAD e3daf07，结束 d3dc3f8；两者 diff 只有 STATUS/WORKLOG。实际读取文件各自 SHA 固定，不由 HEAD 反推产物 |

`config/loader-candidate.json` 是本仓审计清单，**不是 board.toml schema 扩展，也不是可直接启动的板配置**。里面记录包链接计划、模块、许可、受保护 board/feed 哈希、原始输入和补丁哈希。源代码不复制进本仓，补丁在内存中应用；未来获批的构建树才建立包链接。

三份 `patches/firmware-candidates/` 补丁：

1. `0001-bootshim-image-size.patch`：针对 mu-nuwa-firmware，将 ARM64 header 的 image_size 改为 `(_Payload - _Head) + FD_SIZE`；搬运循环仍读取 `FD_SIZE`，不把 shim 长度误加到拷贝长度。没有改 FD_BASE/FD_SIZE 或板地址。
2. `0002-nuwa-loader-wiring.patch`：针对同一固件树，在 nuwa DSC/FDF 同一 FvMain 接入下表四模块；添加 UniXNULib、FdtLib 映射和 `.unixnu-packages` 搜索目录。保持原 PCD、FD、栈、内存表、RamManagerDxe。
3. `0003-initrd-publisher-only.patch`：针对固定 uefi-sheng，删除 ShengBootMemoryDxe 的 DRAM 扫描/GCD 扩展逻辑及两项不再需要的库，保留原只读 BlockIo 发布实现；读取入口 HOB 前检查长度，并使用 ReadUnaligned64。不继承 ADD_LIMIT/ADD_BELOW 或 sheng 内存策略。保留原模块名/GUID，方便追踪来源。

| 接线模块 | 作用与源码证据 |
| --- | --- |
| UniXNUPkg/Application/UniXNU/UniXNU.inf | UEFI_APPLICATION，GUID 9B665204-A133-47A2-9396-9E2B370A4E25 |
| UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf | DXE 注册同 FV 应用的 Boot####/BootOrder；等待 VariableArch 与 VariableWriteArch 协议；DEC 中应用 GUID 匹配 |
| DarwinBootPkg/Driver/DarwinBoot.inf | UEFI_DRIVER，安装 gUniXNULoaderProtocolGuid；UniXNULib/Boot.c:60 查找同一协议，再调用 Loader->Boot |
| shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.inf（裁剪后） | 从入口 DT 的 /chosen linux,initrd-start/end 发布只读块设备；供已有 PartitionDxe/Fat.inf 暴露文件系统，供 Config.c:1269/1505 枚举 |

未来包根链接：`.unixnu-packages/UniXNUPkg` 指向固定 UniXNU/package/UniXNUPkg；DarwinBootPkg 指向 UniXNU/drivers/DarwinBoot/DarwinBootPkg；shengPkg 指向已应用第3份补丁的 uefi-sheng/Platforms/Xiaomi/shengPkg。只编译指定模块，不引入 sheng DSC、板值、显示驱动或整套内存管理。

许可：UniXNUPkg/DarwinBoot 源头为 BSD-2-Clause-Patent；sheng README 的 License 节声明非 GPL 目录代码为 BSD-2-Clause，本模块位于 Platforms。清单固定许可依据与文件 SHA，未来发布构建仍保留来源声明。

## 内存表：采用原始证据，暂不转换成运行配置

从参考仓现有 `.work/nuwa-xbl_config_a.img` **只读独立提取文本**：分区文件 524,288 B，SHA256 `686bce68b672213c749eea1efbf4575ff7d56c3a0b2326375fb70fd7a952db21`。ASCII 配置位于十进制 `[101928,110270)`，8,342 B，SHA256 `2adc494b0325278c5709f63e52cb4c9e7b2cf29812f67710ee40d2e719c77d12`。逐字文本见 `reports/loader-integration/factory-uefiplatLA-original.txt`；本轮没有重新采分区或复制二进制。

- 原文 `[Config] Version=3`、`MaxMemoryRegions=74`；实际 28 个 MemoryMap 行和14个 RegisterMap 行。74 不足以证明还有32个运行时区域，不能据此编造缺失条目。
- 隔壁整理 cfg 为8,280 B（CRLF），LF归一化为8,128 B；不是连续原文：删去了 Config/MemoryMap 头等内容，末尾另有 CfgVersion=1。**42行内存/寄存器数据与原文逐字段一致**，因此这部分可用；完整配置版本/字节数以原始提取为准。
- 原厂 DXE Heap 为 `0xBAB00000 + 0x0D1C0000`，精确 **209.75 MiB**，不能简称209 MiB后用于容量计算。DBI Dump、IMEM 虽有 Conv 标签，却是 MMAP_IO/NoHob/AddDev，不计为可分配 SYS_MEM。
- 原厂表未描述 >4GiB 银行。隔壁53行 C 表有4个原厂行被改变/拆分，另12行属于新增/拆分：2个 FD 子区、8个额外保留区、2个高地址区域。6GiB Conv 窗口是参考侧另加策略，不是原厂表直接提供。
- 原厂 `TZApps Reserved` 为 **AddDynamicMem**；隔壁变为 **AddMem**。Mu 当前枚举没有 AddDynamicMem，语义等价性未验证。原厂两个 NoMap 被变成 HobOnlyNoCacheSetting；Mu MemoryInitPei.c:92,131 的行为是建 HOB、跳过页表项，仍需对照原厂语义。
- 原厂 UEFI FD 一行4MiB被参考侧拆为1MiB保留+3MiB FD；只能记录为有意差异，不能写成逐字照抄。
- RamManagerDxe/RamManager.c:58起会根据 RAM partition 和当前 EFI map 补入未覆盖的区间；静态表不是最终 UEFI memory map。Android iomem 也不能代替它。

因此，本轮吸收的是**原始表及语义差异清单**，没有把隔壁 MemoryMapLib.c 整份套入。D-002 继续有效：首轮目标512MiB–1GiB，上限8GiB；具体可用窗口/映射/保留证据仍 TODO，不重问已作废容量选择，也不填写 board 值。

## 打包经验及仍然缺失的条件

已吸收 BootShim 长度修正。保留基座 `scripts/unixnu/bootimg.py:20-36` 的 `_Payload == len(shim)`、头部 magic/长度检查，以及 `verify()` 对 gzip、FD、附加 DTB、ramdisk 的回读对账。未来包装入口必须在切换 cwd 前 resolve 输入输出路径；不得复用参考脚本删掉 native-ufs-root/panic 等检查以凑出镜像。

本轮内核固定为咱们 CI15 的源内核；不能直接把它改名 kernel.macho 填进旧 FAT，也不采用隔壁的预链接内核替代。新内核的65,348项指针绑定零缺失已取证，但12处 Libm 外部 PC 编码、完整预链接/ABI、crypto/pthread provider、startup ARCH_TIMER、boot-progress/watchdog 仍未验收。

四模块接线只打通源码依赖：实际 ABL 是否提供 initrd 属性、SEC 是否保留正确 HOB、initrd 区间是否持续被保留并映射、FAT 是否挂载、DXE 分派顺序、BootOrder 是否生效、DarwinBoot 是否安装协议，都未验证。只读 BlockIo 不等于底层内存已受保护；这些必须在获批的后续验证中取证。仅把 FAT 放入 Android ramdisk 或仅看到 UniXNU 菜单，不能跳过此门。

## 复现与验收范围

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-loader-candidates.py
```

输出 `reports/loader-integration/audit.json`：75项静态检查，包含下载内核大小/SHA、输入/补丁/board/feed 哈希、RAM 精确应用、四模块位置/源文件/类型、GUID/协议、库/包路径、保留 PCD、只读发布和原厂表对比。代码不执行编译或被审查的参考脚本，不写输入树。

真实 `git apply --check` 在 mu-nuwa-firmware 和 uefi-sheng 两个只读工作树均退出0；完整 argv 在 `git-apply-check.json`。`source-state.json` 记录固定 HEAD 与 tracked clean。检查器不宣称 EDK 所有传递依赖、FV空间、PE/COFF重定位或实际硬件已通过。

当前停在 **R-004：仅构建加载器固件候选** 的审批门。board/example、feed、内存表与板值均未改，没有 *_verified=true，没有 QEMU 或实机 XNU 结果。
