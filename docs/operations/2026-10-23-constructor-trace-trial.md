# 逐构造诊断实测：Mmu enter

2026-10-23T19:50:49+08:00。用户“继续”后仅临时启动530f56b4候选一次；本轮已结束并确认Android。本次没有再次构建或修改固件、board/feed/bringup-plan及验证标志。

## 实测证据

fresh preflight核对nuwa/kalama、完成1、A槽及三分区与上一轮相同，严格候选/原boot/包报告校验通过。启动前通知录像；先前20秒倒计时被用户指出不准，随后明确改为“接下来立即发送启动命令”，未声称主机调度可精确倒计时。preflight中最初notice时间不是精确fastboot发送时间，实际命令时间以launch.json为准。后续采用“准备录像→实际发送后报告结果”，不再承诺精确秒数。

实际fastboot Sending3080KB/0.075s、Booting0.117s OKAY，仅是接受证明；记录120秒USB样本，共59条，最后相对秒数120.0。USB/ADB总数不是nuwa阶段日志。

用户先文字“mmu enter”，再提供本轮原图screen.jpg：9894395B、SHA520bdded72db7ec796f422356ae22ebfa1aded59a180c1a9b6581d8431dffb92。照片显示：

```text
[NUWA-HANDOFF] before-entry-arg-hob list=BAB00000
[NUWA-HANDOFF] after-entry-arg-hob data=BAB013B8
[NUWA-HANDOFF] before-library-constructors
[NUWA-CTOR] Debug enter
[NUWA-CTOR] Debug leave status=Success
[NUWA-CTOR] Extract enter
[NUWA-CTOR] Extract leave status=Success
[NUWA-CTOR] Mmu enter
```

本轮Debug与Extract构造返回Success已由实际画面确认；进入Mmu构造的日志已执行。未见Mmu leave/Lzma enter、总构造返回、FV解压或DXE/SHENGMEM。不能据此写成“已定位缓存指令故障”或“HOB损坏已确定”，因为没有运行PC，Mmu enter后既有GetFirstGuidHob，也有数据访问或cache路径，日志输出本身仍是候选。

## 恢复

recovery.json在19:46:21（Asia/Shanghai）直接检测到实际nuwa Android完成1，本轮没有发送原boot/fastboot恢复命令。如何回到Android未独立记录，不臆测自动重启或按键。postcondition.json随后再次核对nuwa/kalama、完成1、A槽以及boot_a/vendor_boot_a/init_boot_a SHA全部与试前一致。无flash/erase/改槽，不再试第二个包。

## 下一步离线检查

ArmMmuBaseLibConstructor固定Mu cfb93724，先GetFirstGuidHob(gArmMmuReplaceLiveTranslationEntryFuncGuid)。若找到，读取HOB中的函数指针；否则WriteBackDataCacheRange(ArmReplaceLiveTranslationEntry, ArmReplaceLiveTranslationEntrySize)，最后返回成功。

优先检查实际新SEC中的GUID HOB查询/字段访问、helper地址/size和缓存行操作，包括链接map与TE一致性、cache line步进以及当前异常级别要求。若仍需新诊断，按HOB查询前后、选定分支、cache维护前后拆分，只记录真实值，不跳过cache同步、不伪造HOB或构造成功。先静态产物核验再安排实测，仍需刷新用户录像及恢复门。

来源及许可保留于reports/constructor-trace/proposal.json，四文件microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5、BSD-2-Clause-Patent。同SoC来源仍可评估其HOB/helper/cache策略，但不得因同SoC复制板值。

本轮仅固件构造诊断，不含FAT/ADT/XNU，未进入XNU。原晚间2d833461到before-library-constructors与本轮530f56b4到Mmu enter是两个独立阶段证据，不能互相覆盖或误用图片。
