# 本机 ABL 交接审查与 BootShim 相对偏移候选

时间：2026-10-23 00:13–00:35，Asia/Shanghai。前序提交3731c4b，R-007 A试验结果仍是黑屏/fastboot持续、未验证SEC。本轮只读设备和既有二进制；没有编译、生成镜像、重启、flash或改槽位。

## 结论

**发现一处确定的头字段语义问题，以及一条强但有条件的拒绝路径。** 当前112B BootShim在Linux Image头+8填入绝对FD目标地址0xa7100000。ARM64协议定义此处为相对装载偏移；本机ABL确有读取它并加到KernelBaseAddr的分支。若本次走普通平台路径、两个UEFI变量可读取，且其值来自同机Kernel描述符，则计算得到0x14f100000，超过该窗口末端0xb8000000；后续空间检查返回EFI_BUFFER_TOO_SMALL，早于内核复制/入口跳转。

这不是从上次试验取得的实际错误码。变量运行值、SetVariable成功、平台选择分支、本次执行PC仍未观测；尚不能宣布黑屏根因已实测确认。源码候选仅把头字段改0，FD拷贝目标仍0xa7100000，尚未应用到固件检出或编译。下一镜像范围列R-008。

## 输入、复现与地址纪律

1. `reports/abl-handoff/live-inputs.json`：以ADB产品属性唯一筛选nuwa，再读取实际DT model/compatible；nuwa/kalama、Android完成1。当前abl_a/b SHA均为38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188，与只读备份相同。pstore为空，三个常规bootloader_log节点没有输出。串号仅在进程内使用，命令记录替换为`<selected-nuwa>`。
2. `scripts/audit-abl-handoff.py`在RAM解包只读备份ABL，未输出PE/固件文件。LinuxLoader GUID f536d559-459f-48fa-8bbc-43b554ecae8d，1134592B；Capstone5.0.6、skipdata开启，原指令字节与反汇编同存`disassembly.json`。**下述地址均为PE首选地址，不是实机PC。** 字符串交叉引用仅作定位，判断依据是保留的控制流/指令。
3. `scripts/audit-live-uefi-variables.py`从ADB读取现有uefi_a到RAM，并核验两槽hash和长度；5242880B/SHA d95cd6c7e602a7a2b439ea3ae58b6c51621893c0d60a6a7fcc2477b3b1a7e30d。解析98个PE；最初只处理普通/LZMA段得到0PE的有限尝试保留在live-uefi-inventory.json，不能当最终清单。实际为Qualcomm GZIP guided section，GUID1d301fe9-be79-4353-91c2-d23bc959ae0c；后续使用zlib gzip严格EOF/尾部与上限校验成功，证据live-uefi-variables.json。识别依据：[UEFITool ffs.h](https://github.com/LongSoft/UEFITool/blob/new_engine/common/ffs.h)。
4. xbl/xbl_config现有两槽hash也与备份一致，见xbl-inputs.json。xbl_config SHA686bce68b672213c749eea1efbf4575ff7d56c3a0b2326375fb70fd7a952db21，与此前factory提取来源相同。原厂文本Kernel行见`reports/loader-integration/factory-uefiplatLA-original.txt:31`；完整提取offset101928、长度8342B及原表hash见该目录audit.json的factory对象。

复现（PowerShell；Python路径按本机配置）：

```powershell
$py = 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe'
& $py -X utf8 -B scripts/audit-live-uefi-variables.py
& $py -X utf8 -B scripts/audit-abl-handoff.py --quiet --range 0x7d00:0x7db0 --range 0x8b40:0x8b80 --range 0xfde0:0xfe80 --range 0x87eb4:0x87ef8 --range 0x80884:0x808a8 --range 0x8aa08:0x8aff0 --range 0x9cc0:0x9ce8 --range 0x9d30:0xa340 --range 0xaa64:0xaad0 --range 0x10390:0x104f0 --range 0x8b2e4:0x8b328 --range 0x8c64:0x8d10 --range 0x1bda0:0x1bef0 --range 0x141a4:0x142d0 --value 0x96ad7:ascii --value 0x9ba9f:ascii --value 0xa6216:ascii --value 0xa069d:ascii --value 0xa8634:utf16 --value 0xa853e:utf16 --value 0xe5a18:guid --value 0xe5934:u32 --value 0xe5938:u32 --value 0xe593c:u32 --value 0xe5940:u32 --calls-to 0x6ef0
& $py -X utf8 -B scripts/preview-bootshim-relative-offset.py
```

脚本依赖已放ignored `out/python-tools`的Capstone5.0.6，以及设备仓现有FV解析器；不会安装或写入两个只读来源仓。第一条需唯一nuwa ADB，后两条仅本地静态分析；preview内部只执行`git show`及`git apply --check`，不实际apply。任何新增地址均未写入board/bringup-plan。

## UEFI发布变量 → ABL消费 → 空间检查

| 环节 | 二进制证据 | 能证明的内容 |
| --- | --- | --- |
| QcomBds | GUID5a50aa81-c3ae-4608-a0e3-41a2e69baf94，PE SHAea5d2798b42b5e2055cd887516f58a9c554c8fe293f6c917b00b3f35baaf901d；0x7840–0x7854 | 以字符串Kernel查找描述符，状态0进入发布分支 |
| 变量发布 | QcomBds0x7890–0x78dc，KernelBaseAddr/KernelSize；GUID882f8c2b-9646-435f-8de5-f208ff80c1bd | SetVariable表偏移0x58，属性2、长度8，数据指向描述符+0x20/+0x28。两次返回值未在此检查；不等于运行成功 |
| ABL查询 | 0x103f0–0x104ec | GetVariable表偏移0x48，同名/同GUID；两次状态都0才返回true |
| ABL装载地址 | 0x9e2c–0x9f48，重点0x9ed8–0x9eec | 普通平台、raw64、image_size非0时，KernelLoadAddr += Image.text_offset；End=KernelBaseAddr+KernelSize |
| 无变量回退 | 0x9f50–0xa1c4，常量e5934=0x80000/e5938=0x5600000 | 另走ABL基址与编译偏移路径；该分支不使用本头字段，不能声称改头对所有路径均有效 |
| 边界检查 | 0xa1c4–0xa22c，失败0xa2ec–0xa2f8 | 从End扣除ramdisk/page及DT余量，只有DTAddr > KernelLoadAddr才成功，否则返回0x8000000000000005 |
| 原始复制 | 0xaa64–0xaa84 | 以计算的KernelLoadAddr为CopyMem目标，早于该分支的错误会阻止复制 |

属性2是仅BOOT_SERVICE_ACCESS，未带NON_VOLATILE或RUNTIME_ACCESS。因此不能通过当前Android的efivarstore读取来证明上次启动的两个易失变量值。本轮没有盲读/修改efivarstore。

原厂Kernel表描述为[A8000000,B8000000)，大小10000000。候选的条件算术结果见relative-offset-preview.json：

```text
当前：A8000000 + A7100000 = 14F100000 > B8000000
候选：A8000000 + 00000000 = A8000000
```

这里假定扣减不发生无符号回绕；不把任意畸形ramdisk的算术也算作本次场景。该推导不等于运行变量读取，不是新的板级基址选择。

## ACK、最终交接和仍缺的执行观测

fastboot boot调用点0x87edc之后，先调用0x8b2e4→0x80884，后者引用0x96ad7的OKAY，再经清理调用到0x87ef0的BootLinux(0x6ef0)。BootLinux返回后直接跳epilogue，未在这里把其错误作为主机FAIL返回。**因此命令OKAY与加载过程早退可以同时成立。** 这解释了为何上次ACK不能用来排除ABL拒绝，但不证明实际早退发生。

若确实到最终跳转，ABL0x8c64调用PrepareHardware(0x1bda0)，保存的静态路径包括内存/cache处理、IC IALLU、关闭SCTLR C/I/M与TLBI；0x8ce4–0x8d00以x0=DTB、x1=x2=x3=0并BLR内核入口。这些是代码契约，**实际EL/DAIF/MMU/cache/SPSel、运行装载地址和PC仍未验证**，不能把存在这些指令写成已实机交接。

## 既有日志回收结果

- logfs：8MiB/SHA723cce1421d7c34ae6949af55e28cae3d050d4b05bfae6e39824a71254c4f1a0，VBLG头；仅选出offset178242的“No bootable slots found enter fastboot mode”。没有会话归属，不能算R-007错误。
- ABL0x8aa08–0x8aff0的lplog代码引用blackbox/minidump、logmagic整数及Raw_Dmp!签名，**并非仅凭字符串把它认作logfs写入器**。当前blackbox不存在，minidump存在96MiB。
- minidump：整分区只读到RAM，SHAe367ac9bce6420c4327f68758d5f68bfe282176cc756db351f65664c66cb10f3；已有五个Raw_Dmp!头，窄范围明文加载错误/NUWA-ENTRY检索为0。未解码各dump内部结构、压缩负载和会话，不能由0匹配断言从未记录。报告minidump-selected.json记录筛选局限；未落盘固件/诊断镜像或完整RAM/日志内容。
- 收尾仍nuwa Android boot_completed=1，见log-partitions-and-final-android.json。此轮没有改变设备模式；两只读仓、固件源码检出均未修改。

## 可审阅修复与下一步

`patches/firmware-candidates/0006-bootshim-relative-text-offset.patch`只把BootShim头的`.quad FD_BASE`改`.quad 0`，指令、image_size、FD_BASE拷贝目标/入口不变。原源码LF SHA40ff434f…，候选985a6876…，patch SHA7409eecd0c6956becab01f7efb426cde2437de807ec5ebbf15f8a286058adf05；实际112B shim SHA9346a527…解析确认旧字段A7100000和image_size300070；`git apply --check`通过。

语义依据：[Linux ARM64 booting protocol](https://docs.kernel.org/arch/arm64/booting.html)中64B Image header和相对装载偏移说明。这里只引用协议，不把shim变成Linux内核，也不采用其余未验证硬件假设。

倾向下一次只编译修正后的shim、复用R-007同一FD9ea347a4，受限打包同类v4容器，严格比较变更仅头的8B字段范围（实际改变字节数以新产物为准），按D-016进行一次临时对照并恢复Android。现有检查器/输入门中固定旧头值的部分需显式更新，不能用旧profile宣称新shim已通过。**尚未生成这些产物**；R-007仅SEC改动已完成，新BootShim镜像需R-008审批。若拒绝生成，继续解码现有dump/寻找独立观测路径，不能用更多屏幕DEBUG替代入口证据。
