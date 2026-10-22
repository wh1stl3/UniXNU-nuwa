# R-008 A相对偏移试验及PIL阻塞点

时间：2026-10-23 00:37–00:51，Asia/Shanghai。用户在R-008具体方案提交后回复“授权通过 继续主线”；一次试验后又回复“你直接启动就好 我随时录像”，授权同一包复试。设备端未flash/erase/改槽，恢复阶段完成实际nuwa Android boot_completed=1核对。

## 构建与范围

固件独立分支`codex/nuwa-relative-offset@910ee079fbaef736c49c14fd24501b132e98bb90`从5e4a8c8建立，只改BootShim.S的一行头字段。源码对象通过GitHub API逐blob/tree/commit等同发布，见reports/relative-offset/source-publish.json。稳定分支0a3a51a和SEC分支5e4a8c8保持。

使用本机WSL Ubuntu22.04的clang14与llvm-objcopy，按BootShim Makefile相同方式编译，不依赖Xcode/iphoneos SDK；**这是112B ARM64汇编shim构建通过，不是本机完整XNU构建通过**。确切命令、版本和输出见build-commands.json；symbols.txt/disassembly.txt留存文本证据，二进制仅在ignored out/。

`scripts/build-relative-offset-trial.py`先固定source SHA985a6876及固件提交，再对原CI39809636575的665项输入/实际FD做旧产物复查；新shim独立检查头0、ARM64 magic、image_size、_Payload位置、实际复制长度和全字节对比，不拿旧header profile验收新shim。原FD SHA9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf完全复用，未重建四EFI或FD。

| 项目 | 实际结果 |
| --- | --- |
| 新shim | 112B，SHA8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462 |
| shim差异 | 对旧9346a527只有offset10、11变化，均在text_offset字段内；全部指令/FD目标不变 |
| image_size/_Payload/复制数 | 3145840 / 112 / 3145728B |
| v4临时容器 | 3153920B，SHA8b420abe64ac1738685879497d6a3e167a40873887b2122db01e8ae864ed2dfb |
| 对R-007包差异 | 仅容器offset4106、4107两个字节；长度、原v4头、FD、padding均相同 |
| 内容 | raw shim+同一FD；无新增DTB/ramdisk/FAT/XNU，header仍4 |

package.json记录完整输入、来源区别和检查结果。试启动脚本新增R-008专门门：报告路径/审批/source commit/FD SHA/112B/零偏移/差异范围等；R-007旧路径保留。

## 两次真实试启动与收尾

- 首次launch.json：00:40:34开始，先Android实际DT筛选nuwa/kalama，Android=1，再adb reboot bootloader并额外fastboot reboot bootloader隔离；product/unlocked/slot重查后临时boot。Sending OKAY0.075s，Booting OKAY0.117s；15次采样nuwa fastboot均为false，与R-007十五次均true不同。USB快照只有其他Android设备，不能将它误认nuwa。
- 用户直接反馈：“很多日志 Auto calling什么 什么panic 也许可以再来一次然后我录个视频”，原话见screen-observation.json，不自行补全未看清的阶段。
- 首次recovery.json在00:41:49确认实际nuwa Android=1；这份记录没有fastboot恢复boot下发命令，仅ADB识别/等待。不能描述为本轮临时加载原boot完成，也不能确定是自动回返或用户按键。
- 用户明确准备录像后，同包复试launch-repeat.json：00:42:33开始，Sending/Booting再次OKAY；15次fastboot采样仍全false。没有重新打包或改第二个变量。
- recovery-repeat.json在00:43:49再次确认实际nuwa Android=1，同样没有下发恢复boot。postcondition.json的boot_a/vendor_boot_a/init_boot_a全分区hash与precondition.json一致；logfs/minidump SHA也与此前只读取证完全一致，不能指望这两份未变的记录含本轮新日志。两个boot reason属性均为bootloader，仅保存原值，不据此定位复位来源。

所有ADB/fastboot目标按产品与实际DT筛选，序列号只驻内存；enuma未作为目标。没有设置任何_verified，也没有改board/feed/内存图。未知实际L/EL/MMU/cache、运行变量和入口PC继续未验证。

## 用户照片与PIL分析

照片原字节保存在reports/relative-offset/user-screen.jpg，SHA277bae54e8607eadebcb68a42e192f9c2a758a03e26012381ad936c0cc6dfe17。可读末尾是：

```text
Pil_abl Failed to read from partition
Pil_abl Failed to load ELF file
Auto processing of uefipil.cfg failed. Calling target panic
```

上方显示DXE驱动调度，包括PILProxyDxe、PILDxe、DisplayDxe等。因此**这是Qualcomm PIL/ABL加载错误，不是XNU panic**。同帧没有NUWA-ENTRY或可确定试验时点的标记；不能仅凭这张图把所有DXE输出直接归为咱们FD，或宣称BDS/UniXNU已运行。需要首屏/连续录像进一步核对启动先后关系。

`scripts/audit-trial-screen-origin.py`独立解包实际候选FD，158FFS。画面四个驱动的GUID在当前原厂UEFI和候选FD内均存在，**不是只出现在原厂UEFI**；该脚本匹配原固件报告中的PE身份/GUID，不能把GUID相同写成字节SHA相同。实际候选PILDxe含uefipil.cfg、Calling target panic、Failed to read from partition字符串。更关键是候选本身的RAW配置：

```text
[AUTO]
ABL
```

该RAW FFS GUID21e9bdd9-6c3f-4f10-84a5-bbec322741f1，6868B/SHA51facfcbe4c7a80be030ab061f94a30d924bad22f0056d53af372fe9f9c9f61e；[ABL]定义Type=elf_fv、固定PartiGuid。完整文本和二进制来源关系保存在screen-origin.json，未猜任何GUID/地址。固件源`Platforms/Xiaomi/nuwaPkg/Include/APRIORI.inc`在PILProxyDxe之后立即列PILDxe，BdsDxe位于其后；RAW.inc:248–250继续引用Binaries/nuwa的原配置。

据此得到可操作的源码问题：**二级UniXNU固件仍保留自动链载Android ABL的原厂策略**；这与画面报错一致。在取消该不需要的自动项之前，不通过刷ABL分区或重猜分区GUID去强行满足这条路径。也不能由取消AUTO推断UFS/BlockIo或后续负载挂载已通过；照片前部还有Qsee/FeatureEnabler错误，后续是否另阻塞仍未验证。

## 下一份源码候选与审批

`scripts/preview-pil-no-auto-abl.py`从同一FD的原始RAW ASCII校验SHA后准备0007-nuwa-disable-auto-abl.patch：将RAW.inc输入改为nuwaPkg本地配置，新配置逐字保留6868B原内容的全部RETAIL/镜像定义、GUID、内存地址，只将[AUTO]下ABL行改为注释。PILDxe/PILProxyDxe/APRIORI/DEPEX不删，不动安全调用返回。

patch SHAf3d6d9c76a7e6ec2531a7bdbc2aa185a86ad74808c55f73eb6b63f05f462faaf；候选配置SHAdbc9ee6e4c7728b32245453322f348c32d6a5eef0107f8c07662918bc3c23fdd。对910ee079的git apply --check通过，未实际应用/编译。空AUTO列表的解析与运行、后续依赖/BDS仍未验证，须在新构建前审查。

新FD已超出R-008“精确复用旧FD”的范围，按AGENTS§3第3类列R-009。倾向A：审查空AUTO解析，应用这份最小配置替换，固定新来源重新构建/静态验收并临时对照恢复。B：不生成，继续PIL/存储和连续录像取证。当前设备Android=1，未生成R-009镜像。实体录像回传记PENDING-HUMAN，不把它单独作为软件工作停因；真正的停点是新镜像审批。

## 同SM8550项目对照（用户追加要求）

只读GitHub API获取固定提交及相关include/define片段，含文件SHA256、blob与永久链接，见sm8550-pil-references.json；没有跟进上游、修改feed或复制其板值。API仓库许可证为BSD-2-Clause；本轮只阅读源码，不导入其二进制。

| 来源 | 固定证据 | 对本问题的帮助与限制 |
| --- | --- | --- |
| UniXNU/uefi-sheng@0eb4514db0744b8136a3897ab1af93b713c2c27b | sheng.dsc:34默认SHENG_VENDOR_HW=0；APRIORI.inc:76–80及DXE.inc:128–131把PILProxy/PIL/SPSS放在vendor硬件条件内；RAW.inc仅18行 | 说明UniXNU二级固件并非必须无条件沿用PIL/自动ABL链。全盘照搬vendor=0会改变显示/UFS等依赖，不能当nuwa现成可启动方案 |
| hanzi123-bilp/uefi-fuxi@bb25ad75eedf2c224951c71767a077976b721793 | fuxi APRIORI/DXE无PIL项；RAW.inc明确默认vendor=0、尚无原厂RAW文件，16行 | 可参考最小固件分层；[官方fuxi状态](https://unixnu.com/zh/devices/fuxi)明确未记录真机运行，不借此声称已验证空AUTO解析或nuwa可用 |
| 本机Mu nx729j模板@910ee079 | Platforms/ZTE/nx729jPkg/Include/{APRIORI,DXE,RAW}.inc保留PIL及原厂uefipil.cfg | 同SoC模板本身也可能沿用原链，不能机械复制；未检查其实际配置RAW内容和真机结果 |
| vermeer | [官方状态](https://unixnu.com/zh/devices/vermeer)仅记录一个仓的源码内核CI与另一派生仓未记录运行 | 当前没有可援引的PIL/启动运行结论，本轮未编造其固件实现 |

主要源码：[sheng默认开关](https://github.com/UniXNU/uefi-sheng/blob/0eb4514db0744b8136a3897ab1af93b713c2c27b/Platforms/Xiaomi/shengPkg/sheng.dsc)、[sheng PIL条件](https://github.com/UniXNU/uefi-sheng/blob/0eb4514db0744b8136a3897ab1af93b713c2c27b/Platforms/Xiaomi/shengPkg/Include/APRIORI.inc)、[fuxi RAW说明](https://github.com/hanzi123-bilp/uefi-fuxi/blob/bb25ad75eedf2c224951c71767a077976b721793/Platforms/Xiaomi/fuxiPkg/Include/RAW.inc)。

据此R-009补充一个具体B候选：参考sheng对PIL链做独立条件门，在APRIORI和DXE同时排除PILProxy/PIL/SPSS，保留其余nuwa驱动。它能避开自动ABL路径，但会去掉协议提供者及安全协处理器初始化，代价大于A；必须额外做DEPEX/协议依赖审查，不能直接禁用所有vendor硬件。A仍倾向先保留真实驱动、只取消AUTO的ABL项。两者都需要新FD审批；尚未执行任一方案。
