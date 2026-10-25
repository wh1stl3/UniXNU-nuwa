# STATUS

更新：2026-10-25。**PROBE18实机已执行首线程，越过PE_init_iokit、中断使能调用及commpage初始化，到mac_policy_initmach后panic。BSD/root/iOS尚未进入。**

## 当前实机结果

- 内核d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e，58,413,056 B，211记录补丁；镜像c89cfa52c165562693ab0868dddeeb1225995bb5f30e3899df58a888197e8dde，70,266,880 B。
- 本包录像/恢复确认、新基线后单次临时boot，用户菜单电源Enter触发。81格亮，0–5入口、10/11上下文恢复点可见；74/75 PE_init_iokit、80/81中断使能调用、84–87commpage可见，88 mac_policy_initmach有调用无后继。
- 横纹实机消失，白/青校验带完整；A02A=0、A02B=4、A02C=1。证明一次读回一致及该点原生VBAR交接，不代表长期显示或实际硬件IRQ递送已验证。
- 2026-10-25 18:19:42北京时间已恢复Android完成1/A槽，三分区SHA与试前一致；当前无人工恢复待办。此为该时刻记录，不代表持续查询。

## 当前卡点：Image4启动环境契约

panic完整匹配donor AppleImage4 5.0.0：`failed to get mix-n-match policy: %d`，参数2。不是模型中bzero未处理异常的实机复现；本轮已实际越过OSKext摘要初始化。

首要缺项为`/chosen/mix-n-match-prevention-status`。保留二进制读取器+原生SecureDT，使用同一出货ADT，复现返回2。5个隔离用例确认32位1表示禁止mix-n-match，0或空属性会允许，8字节超限返回84。当前仅审计，未选择运行时值、未修改ADT或绕过认证；IOKit runtime-provider动态路线尚未单独复现。

下一主线是完整列明Image4策略与manifest/hash依赖，再形成可追溯的非Apple平台输入契约；不能以空字段、伪造fuse/可信链或跳过MAC检查推进。继续保持板值/TCR/owned window/donor/_verified不变，loadable=false/runtime_qualified=false。BSD/root、必要驱动和用户态随后仍需工作。

## 修复、验证与证据

HEX清屏每行写1920却只退1280的漂移已修正；临时异常槽位改为首指令分支，首线程入口交回捕获并核对的原生VBAR。178点新布局和A02A–A02C含义与PROBE17不同，见绑定包报告。

740差分、42入口/MMU、18读数、5WFE、6静态walk、5ParseKernel、8稀疏阶段、2异常处理器、6精确矩形、10上下文/显示、5真实向量、同ADT切换12断言、6console与26绑定检查、镜像回读/重复构建通过；新增Image4契约5例通过。均与实机结论分开记录。代码/离线提交9a5961f；通用AGENTS合并280c198。未push，未触发新CI。

实测reports/xnu-entry-probe-trial/2026-10-25-v25/；离线reports/kernel-entry-probe/2026-10-25-v25/；包reports/xnu-first-entry/entry-probe-18.json；[完整操作记录](operations/2026-10-25-v25-first-thread-display.md)。原图/有声视频/提取帧仅本地out或用户原路径，不上传。新候选再按本包录像、基线与恢复门执行，不复用旧确认。