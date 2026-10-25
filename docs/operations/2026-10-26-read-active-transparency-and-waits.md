# PROBE28激活读取透明性与等待边界补充审计

2026-10-26，基线079488ff466f9ab9429f8772f42cb6a871a56e93。仅离线；没有设备命令、新内核、新包、板值/TCR/身份/认证或_verified改动。收到后续“只分析、不扩展实现”指令前，下面的测试夹具与检查已完成；之后只读取源码、联网资料与记录分析。

## 已完成的最小工作项

原1092透明性检查的通用fixture没有激活新读取状态；原11场景主要检查x0、SP、状态和画面。本次对相同11场景做12对激活路径差分（repeat两次）：候选观察代码与恢复12个固定原生指令的参考路径执行相同MAC/文件系统API模型。参考指令先逐一核对固定原始内核，不以报告自述作为唯一oracle。比较31个通用寄存器、32个SIMD寄存器、SP、NZCV、FPCR/FPSR、TPIDR_EL1、调用者栈、残余量及存活原生写入地址结果，均一致。诊断画面与临时诊断帧不作为原生输出比较。

在内存副本中将MAC探针恢复指令ldp x9,x10,[sp]的目标x9改为x8；原镜像文件不写。新检查确实发现x8/x9差异，x0和SP保持，证明能捕获原断言覆盖不到的上下文泄漏。没有在实际交付内核发现这一泄漏。额外种入旧275格像素，确认正常视频场景开始header时会清掉旧格。新报告differential-with-negative.json包含完整快照、源SHA和负对照。默认11项夹具另外输出到legacy-fixture-check.json，与原绑定read-boundaries.json逐字节相同。

原PROBE28包报告及23份绑定报告均与079488f逐字节一致，内核仍54179a87…，镜像仍7a04626e…；audit-manifest-final.json固定补充脚本/报告SHA。未重复24项全套、未重建或重封包。中间报告仅本地out/read-active-audit-preliminary保留。

可复核命令（输出必须选新路径，不覆盖有效报告）：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/test-read-boundary-differential.py --build reports/kernel-entry-probe/2026-10-26-v36/build.json --output reports/kernel-entry-probe/2026-10-26-v36-active-audit/differential-with-negative.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/audit-read-wait-chain.py --build reports/kernel-entry-probe/2026-10-26-v36/build.json --output reports/kernel-entry-probe/2026-10-26-v36-active-audit/wait-chain-with-conversion.json
```

上述已执行，不因本段示例重复运行。首条13次双边比较含12对正向及一组负对照，MAC/文件系统主体是明确替身，不是实机或真实解压通过。

## 静态调用边界

固定公开XNU1b191cb58250d0705d8a51287127505aa4bc0789、APSL-2.0。decmpfs.c工作区SHA9d5c0d48…，mac_vfs.c SHA51c6c39b…。审计6个源码函数、5个独立原生符号；compression_type_valid无独立符号，不能拿源码行直接当hook地址。每个BL/BLR及原始字记录于wait-chain-with-conversion.json。

| 机制 | 固定指令/源码证据 | 当前不能推导的结论 |
| --- | --- | --- |
| MAC策略处理 | 7916e0c/7916ed8为BLR x26；7916e4c调用策略列表busy管理 | 268亮不证明已进入某一个策略回调 |
| 压缩数据锁/UBC | decmpfs.c:1676、1691；原生7480090共享锁、7480100缓存拷贝 | 272亮不证明锁已获得或fetch已进入 |
| 解压器锁及adjust | 7480188、74801b8共享锁；74801ec间接调用 | 表项存在不证明锁/adjust返回 |
| 验证与UPL | 748023c验证、7480420建UPL、7480444映射 | 不得为推进跳过验证或伪造映射 |
| 真正fetch | 7480474/7480520调用helper；747fdc0间接调用 | 仍无实际目标、返回、bytes_read实机读数 |
| 转换等待 | decmpfs.c:1829-1837仅fetch错误且FILE_IS_CONVERTING才进入；74804d8调用747fe70；747fecc调用msleep | 未见读取返回不能直接指定该等待或其持有者 |

表内省略共同前缀0xfffffff00，完整地址以JSON为准。顺序包含条件分支，不能声称每项必经；APFS实际v_op表和本次间接目标尚无运行时证据。

## 新发现的参数覆盖边界

header-argument-analysis.json记录实际250前指令：w6=8（IO_NODELOCKED）、offset=0、UIO_SYSSPACE=2，x3来自1左移_PAGE_SHIFT_CONST。磁盘初值0不是运行时值。固定arm_init.c:395-410按boot_args.memSize和ARM_PGSHIFT初始化；不能以磁盘0声称本次请求1字节，也不能直接断言4KiB/16KiB。

现有夹具普通路径使用4KiB、flags=0，NOAUTH另有独立场景。这不推翻已通过的同输入透明性，但未覆盖完整真实header参数。下一离线最小项是串起固定DarwinBoot的boot_args.memSize生产、实际arm_init赋值与PAGE_SHIFT_CONST使用，再决定精确参数及必要负对照。当前只列计划，没有改内存字段、TCR、模型参数或交付内核。后续阶段计划另见2026-10-26-next-stage-public-research.md。
