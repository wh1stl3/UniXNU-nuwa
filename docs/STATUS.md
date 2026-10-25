# STATUS

更新：2026-10-25（北京时间）。主线 UniXNU / nuwa / iOS16，最高实机事实仍为 **PROBE16 到达 kernel_bootstrap 入口**；iOS未启动。

## 当前离线里程碑：PROBE17 / v24 密集路径

按用户要求一次性布密当前可见启动路径：kernel_bootstrap、vm_mem_bootstrap、vm_page_bootstrap、pmap_startup 中79个真实调用，158个调用前/后继位置编号，新增150个补丁位置。右侧10列网格与原左侧阶段/A字段分开；蓝色=调用前，绿色=到达后继位置。共享分支可绕过原调用到达后继，绿色不能单独证明返回。完整目录和语义绑定进包报告。

- 内核：6110c6fba2579eca0e3dfe84bd87a03869685645e98d6fbb75faa2b2a368e09b，58,404,864 B，199记录补丁；独立目录重复构建逐字节一致。
- 镜像：e3b8e0224a0f4f0421927780e2257fda0d892a6cecf1d153c94f3868bbd71aea，70,266,880 B。
- 最终ADT：572c4dbb22009ceae9fc27f1c61e3e5f4208f7db377b2a52cca32a18315127b5。
- 692逐点寄存器/指令/像素差分、42入口/MMU、18读数、5WFE、6静态walk、5ParseKernel、8稀疏阶段、2异常检查通过；最终ADT四切换场景12断言、6console策略及20绑定检查通过。
- TCR/板值/owned window/donor/_verified不变；loadable=false/runtime_qualified=false。

6000万指令连续模型完成133,696次页释放，参数按每对象48字节推进；1.2亿指令累计240,085次，越过pmap_startup/vm_page_bootstrap后继点并到zone_bootstrap调用路径，预算结束于SHA256压缩函数，无非法访存。支持此前20M为预算不足；不证明zone完成，也不是实机停点证明。新包最终镜像回读与绑定复验通过。

证据 reports/kernel-entry-probe/2026-10-25-v24/，包 reports/xnu-first-entry/entry-probe-17.json；实现、读图、边界与续接命令见 [v24操作记录](operations/2026-10-25-v24-dense-bootstrap.md)。当前新包未启动，设备基线需试前刷新。

## 设备与下一步

最近设备核验仍为2026-10-25 16:44:29北京时间：PROBE16试后Android完成1/A槽，boot_a/vendor_boot_a/init_boot_a三SHA不变；这是历史记录，不代表持续查询。原证据 reports/xnu-entry-probe-trial/2026-10-25-v23/。无flash/erase/改槽。

PROBE17实机前需要本包录像与按键恢复就绪，再刷新preflight、即时通知后单次临时boot。菜单电源键Enter触发，无固定180秒；保留整个网格与A字段。试后恢复Android完成1和三SHA核验。等待人工不阻断离线主线。

正式源码的DT panic补丁仍需整核配置接入与重建。当前缺pram诊断桥接保留screen/console，pram存在明确拒绝；不冒充通用动态panic缓冲支持。最高实机入口不证明VM完成、调度、驱动、root或iOS。

官网QR/AdvancedLogDxe覆盖UEFI/EBS前，nuwa尚未接入；Format2/共享SM8550迁移独立评审，保持iOS16身份，见 operations/2026-10-25-official-porting-update.md。原始音视频/截图仅本地，无push。
