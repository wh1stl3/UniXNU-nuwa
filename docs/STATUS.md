# STATUS

更新：2026-10-25（北京时间）。主线仍为 UniXNU / nuwa / iOS 16；本轮完成v22跨页表诊断映射修复、entry-probe-15实机pmap入口及Android恢复闭环。

实机历史已证明 MMU 开启、到达 arm_init；本轮实机确认init入口eventi=4并进入pmap_bootstrap；kernel_bootstrap或iOS启动仍未验证。

## 最新里程碑：entry-probe-15实机进入pmap_bootstrap

2026-10-25，v22c内核`a8b8fc90e4b926830839f4f1a4b27bf19ae34c1736bd8f41d99724a768c74265`/58,372,096 B/47补丁，镜像`36969f945790452a9e9a7b2ba2785edd9afddda53c36106249623cf17c55144e`。单次临时启动，用户菜单电源键Enter触发；照片/视频出现左列y480绿色pmap入口标记。A032=4，A033为正确eventi地址。

**最高实机事实：MMU开启、进入arm_init、进入pmap_bootstrap。** pmap返回、kernel_bootstrap、驱动与iOS仍未验证。没有异常读数不排除后续映射或异常问题，底部菜单是残留背景，不证明返回固件。

恢复于2026-10-25 16:12:44北京时间：Android完成1/A槽，三分区SHA与试前一致，无flash/erase/改槽。当前已恢复，不等待人工恢复。证据reports/xnu-entry-probe-trial/2026-10-25-v22/。

## 修复及验收

arm_vm_init切换新TTBR前，在固定两个BL调用点核对新L1/L2 table与空L3叶，再补8页诊断映射。代码RO可执行、数据RW NX；snapshot移至独立数据页，VBAR改KVA，framebuffer保留原Device属性。占槽不覆盖；错误结构拒写不产生部分叶改动。没有改变板值/内存声明/TCR/donor/认证/_verified。此为诊断映射，不是正式pmap平台实现。

离线：42入口/MMU、88普通钩子差分、18渲染、5WFE、8阶段、2异常、5ParseKernel、15绑定门；另6地址walk和4个原生页表切换场景（12断言）。四个切换场景使用最终镜像同一ADT，执行真实钩子无host正常路径页表代写。最终镜像回读通过。`loadable=false`/`runtime_qualified=false`不变。

## 下一前线：平台旧panic日志区

真实布局连续模型已执行pmap探针，后在_PE_create_console+0x48读取0x3c0fc000失败。二进制常量和只读XNU源码BCM2837.h:63相符：这是BCM固定旧panic日志区；pe_init.c:94-99的check_for_panic_log在console初始化前访问它。**这是模型和静态首要原因，不是已捕获的实机唯一ELR/FAR。**

下一步优先评估上游固定版本native-dt-panic-region.patch与XNU_DT_PANIC_REGION开关在8796中的适用性，再补console/旧日志检查路径的可判定记录；不跳过整个console。不要伪造0x3c0fc000映射，不要NOP整个console或新panic。源码无固定宏时可用DT pram契约、缺失时自然return，需与本构建二进制匹配后实施。

## 流程与隐私

XNU试验以菜单电源键Enter触发，无固定180秒等待。preflight/唯一设备/即时通知/恢复三SHA门保留。

原始照片音视频只在本地out或用户原路径。本轮原始音视频未上传；代码及证据已本地提交`597baed9bd04a59c6a05710ffa22f61ac6b046aa`，未push。隐私核查：常见音视频扩展名在tracked与已获取全部Git引用历史为空，GitHub Releases/Issues为0，29个Actions制品名称均为构建相关；制品ZIP内部未逐一验证，不能保证没有嵌入内容。已加.gitignore常见音视频规则。见reports/media-privacy/2026-10-25/audit.json。

代码与证据提交`597baed9bd04a59c6a05710ffa22f61ac6b046aa`；文档在后续独立提交中收敛。未push、未合并远程或PR100支线。原工作区中不属于本轮的历史未跟踪材料保持原样。详细实现/复现/边界：docs/operations/2026-10-25-v22-pmap-transition.md。

## 官网最新复核（2026-10-25）

已核对UniXNU固定版本16e592ab及SM8550共享仓23b2049f。发现DT panic区补丁已在ARM64系列中，是下一平台问题的首要复用候选。AdvancedLogDxe/OneSend二维码日志已实现，覆盖UEFI菜单与EBS前；nuwa固件的producer/库/DSC/FDF接入未完成，不能声称已可扫取XNU日志。Format2、分层SoC/OS配置和porting.toml记录机制有明显更新；只查阅，不在当前实测链上自动迁移。详情见operations/2026-10-25-official-porting-update.md。
