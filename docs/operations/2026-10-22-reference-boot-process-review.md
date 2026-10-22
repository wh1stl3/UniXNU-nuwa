# 并行boot容器与过程文档复核

2026-10-22，来源仓D:/Code/PortingiOSWithUniXNU仅只读。本报告将来源文档作为待核对资料；其中的授权、下一步及已选板值不转移到本仓。

结论：**可复用打包修正、路径处理和UEFI对账方法；已有boot.img取得容器/内容静态证据，尚不能确认能加载XNU。** VFS补丁此前已独立审查，本轮在本仓真实内核中消除了全部已观测的指针名缺口。没有复制或生成任何镜像，没有运行参考脚本或设备命令。

## 实际产物及版本

- 参考运行[39745511080](https://github.com/wh1stl3/PortingiOSWithUniXNU/actions/runs/39745511080)确为success，2026-10-22 16:17:27结束，设备源码37615547b7aaa977fd57c065d4df6f825c7aebee。运行元数据见reports/parallel-progress-review/boot-run.json。
- 只读检查文件`.work/artifacts/nuwa-boot/out/nuwa/boot/boot.img`，203,157,504字节，SHA256=70d6b97acf6a2ce059dff381b46b0ccf69fc0cda581e4421f689b9c9fb6395fb。
- Android boot v1/4096字节page；gzip解压为112字节BootShim+3,145,728字节FD，附加131,437字节FDT；shim image_size确为3,145,840，覆盖自身及FD。核对仅描述文件，不确认ABL接受v1。
- ramdisk是192MiB FAT32，实际只有unixnu.toml、kernel.macho和kernel.macho.adt三个文件。内核53,014,528字节，SHA=e3cfe478117720307799fcc4201a83e9f30695785ff4f3fb27f23008f0cfb491，确为此前审查的候选。没有trustcache、数据ramdisk或任何.efi文件。
- 本次嵌入FD的SHA=21c029eb7fa432b040ae5d06872f963fee4d8454cf98503ab0423ca3b5afcad3，与原先单独构建FD的f58d5754…不同。产物hash及来源报告均匹配，不混用二者。

可复现命令：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/ci/inspect-reference-boot.py --reference D:/Code/PortingiOSWithUniXNU/.work/artifacts/nuwa-boot --output reports/parallel-progress-review/boot-container-inspection.json
```

检查器仅在内存解析Android header/gzip/FAT32/ADT并写JSON；不提取或重写镜像，不输出unique-chip-id、random-seed或序列号值。实际boot、FD、payload、kernel、ADT五项hash均匹配原报告。FAT文件名/目录链及文件长度经过校验；不把这些检查扩大为文件系统全面验收。

## 过程文档中值得复用的部分

| 来源 | 可用内容 | 在本仓的处理 |
| --- | --- | --- |
| docs/build-findings.md:5，F-014 | BootShim image_size必须含shim长度；FD_SIZE仍为实际拷贝长度 | 已核对源BootShim.S:15,29及实际头部。后续固件源修正的依据，当前不创建固件或改板地址 |
| 同文件:29起 | ADT工具换cwd导致相对输出路径失效 | 后续适配器入口resolve所有输入输出路径；这不依赖板级数值 |
| 同文件:81，F-013；uefi-nuwa/README.md | 对账DTB保留区、UEFI描述符、FD/stack及Conventional容量 | 复用判据及原始来源追踪；四项未覆盖仍待仲裁，不能照搬6GiB声明或把Android iomem等同实机UEFI图 |
| 同文件F-006/F-008 | 二次make可能复用旧对象，广义pmap*.o会混入测试对象；删除“缺失源”会误删MIG生成物 | 与本仓逐对象记录/精确pmap.o、start.o证据相互印证；继续禁止用宽glob或删清单凑通过 |
| 同文件:246，F-010 | codeless元数据、真实VFS接口缺口 | 已独立审查真实VFS函数；本轮CI13实际65,348绑定零缺失，官方只读plan通过。参考roots/slide仅用于分析，不能写入本仓board |
| 同文件:167，F-012 | 内联常量与PC-relative误识别确是需审查的问题 | 9池hash及12处剩余编码已有独立记录；不采纳“非函数入口即数据”的通用豁免 |

build-findings的KPC“不能关”结论不能作为本仓依据：本仓已有关闭KPC/KPERF并补调用条件保护的真实成功构建。参考兼容实现读值恒零，不作为硬件PMU实现引入。已定D-010继续有效。

## 三个必须区分的缺口

1. **加载器接线未验证。** 实际payload无EFI文件，unixnu.toml无driver条目；FD编译日志中DarwinBoot、UniXNUDxe、UniXNUPkg三个名称均0次。运行源码nuwa.dsc/nuwa.fdf没有这些集成项。参考board注释称loader在firmware里，注释不足以证明已集成。固定基座的DarwinBoot.inf是UEFI_DRIVER；UniXNUDxe.inf说明还须把UniXNU应用放入同一FV并注册Boot选项。后续需真实FV模块/协议注册及启动入口证据。没有执行或完整解压所有固件压缩模块，故不把名称计数写成对FD全部内容的形式化缺失证明。
2. **容器目标被缩减。** F-014及payload.json明确panic_screen_patched=false，去掉native-ufs-root=1和sheng-pmgr=2，缺少_sheng_pmgr_run。这保留了产物生成路径，但不验收panic输出、UFS根卷、驱动或用户态启动。大量sheng boot args也不证明相应实现已链接。
3. **现有镜像不包含后来源码新增功能。** 对照运行SHA抓取源文件，而不是用当前工作目录反推16:17产物。当前workflow新增信任缓存输入、SOURCE_DATE_EPOCH及firmware-only步骤；运行的步骤清单没有firmware-only，实际FAT没有trustcache。来源hash和相关原始行见boot-source-provenance.json；CRLF差异另列，不把换行差异当功能变化。

ADT实际darwinboot-memory-size=6GiB，dram-size=9GiB，仅记录为来源事实；本仓D-002仍是先512MiB–1GiB过阶段5、最大8GiB。ipad_identity对应安全属性，不改变iOS/iPhone平台身份；解析器已读到四项属性，不改它们。本轮不重开容量问题。

## 对当前进度的具体帮助及下一步

现在可直接利用的是VFS实现及容器诊断方法；可以省去重新定位shim/cwd两类打包故障，并将“编出boot”细分成容器、loader、ADT窗口、XNU阶段和根卷的独立证据。

本仓继续修复CI13唯一实际平台编译错误，重跑三个archive的真实构建/闭包；VFS已通过实际绑定与只读plan，仍不通过emit绕过12处编码。随后优先完成DarwinBoot/UniXNU固件接线审查、boot-progress及watchdog接口，再建立正式nuwa配置。板值/镜像/上机仍按本仓硬停办理，不因来源仓已获批准而自动继承批准。

已核对资料：来源build-findings.md、STATUS.md、NEED-REVIEW.md、PENDING-HUMAN.md、uefi-nuwa/README.md、BootShim.S、nuwa.dsc/fdf、payload构建脚本与workflow。文档快照hash及运行源码hash均在reports/parallel-progress-review/boot-source-provenance.json；文档里残留的“尚未编译”和“只有按键即可”按真实产物及接线缺口重新限定。
