# a22e9a44实测：卷运输与其他报错

## 已确认结果

用户六张原图、SHA、转录见reports/volume-status-trial/2026-10-24/screen-observation.json。NuwaBootMemoryDxe已调度；dtb=0xb5db1000/938800B；chosen=[0xb5fb2000,0xb7fff1d4)，33870292B；envelope result=0/offset0/bytes0，publisher exit Not Found。按当前代码，FDT/映射和initrd边界检查已越过，完整扫描未匹配封装，因此未安装该探针的BlockIo。后面的四个FAT挂载不能作为目标卷已出现的证据。

这个范围和长度与历史Android快照完全相同，而临时包声明ramdisk=67108928B。**事实是本次chosen没有探针；并未取得整段内存哈希，不能把地址/长度相同写成字节相同。**

固定安装ABL SHA38a837fa、LinuxLoader PE b489faff的离线指令补充：0x7660读取context+0x45c条件，0x7674-0x767c检查版本>=4，0x7690-0x769c以init_boot字符串调用0x8d50；后者遍历context的已加载镜像表，比较名称后返回对应buffer/size（0x8f28-0x8f60），后续读取该头+0xc的ramdisk_size（0x7aa0等）。这是支持init_boot选择的静态数据流，不是该分支在此次fastboot boot走过的动态证明，也未据此修改分区。固定指令证据在abl-init-boot-focused/dataflow.json。

## 其他错误是否处理

| 报错 | 证据与判断 | 处理优先级 |
| --- | --- | --- |
| NUWA-VOLUME Not Found | 当前目标卷的直接阻塞，已区分于CRC和映射拒绝 | 当前主线，处理运输路径 |
| CPU Vectors region not present | 字符串归属固定nuwa EnvDxe；当前MemoryMapLib无此命名项；同机归档uefiplat.cfg有一项 | 真实契约缺口，独立跟进；查清EnvDxe实际用途/映射再修，不借其他板地址、不静默吞掉 |
| SPSS MDT/metadata Load Error | 原图确认实际启动失败；固定vendor二进制来源已核对，完整源码不可用 | 保留并追踪固件文件/协议消费者；尚无证据解释本次封装缺失，不删驱动掩盖 |
| FeatureEnabler/TZ unsupported/SMC failure | 原图可见目标不支持和TA启动失败；后续显示、发布器、UniXNU继续运行 | 不能称无害；暂未证明为当前卷阻塞，后续核对vendor/TZ版本与依赖 |
| RscDxe No mapping | 真实驱动启动失败，后续继续执行发布器和BDS | 独立资源/协议映射问题；状态码不充分说明缺哪一个映射，不凭名称新增MMIO |
| BDS USB no handles/devices | 出现在UniXNU内置配置无启动项后回退路径 | 没有USB启动介质不能当作USB控制器坏；不以该行修改USB驱动 |
| Installed Fat filesystem四行 | 只能确认有FAT卷挂载，来源未辨识 | 不当作探针卷或XNU成功 |

二进制固定来源及同机原始CPU Vectors行在vendor-error-sources.json；归档Raw config不是安装xbl_config逐字节身份的证明。所有错误分别记录，不因后续到达BDS就称其已修复。

## 恢复

最初recovery.json等待超时保留。用户回fastboot后recovery-after-keys.json发送固定原厂boot并确认nuwa Android完成1；postcondition.json核对nuwa/kalama及三分区SHA与本轮preflight一致。无flash/erase/改槽。

## 后续动作

采用既有文档备选：独立profile内嵌配置探针，先验证FV读取→只读BlockIo→FAT→unixnu.toml，不靠ABL临时ramdisk选择。真实XNU/ADT和大负载运输仍需单独完成。此轮离线实现保持现有内存图/board/bringup-plan/_verified；CPU Vectors等列为后续真实缺陷，尚未应用内存改动。
