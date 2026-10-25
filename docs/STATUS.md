# STATUS

更新：2026-10-25。最高实机事实：PROBE17已到load_context调用前；首线程运行/IOKit/BSD/iOS仍未实机验证。

## 当前候选：PROBE18 / v25

- 内核d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e，58,413,056 B，211记录补丁；新目录重建逐字节一致。
- 镜像c89cfa52c165562693ab0868dddeeb1225995bb5f30e3899df58a888197e8dde，70,266,880 B；包reports/xnu-first-entry/entry-probe-18.json。
- 最终ADT9846c7dadd23bf544190c45ba3db437fb83265cb180ad6c54cd3a3fedee20d93。
- 178新编号覆盖首线程上下文、kernel_bootstrap_thread、IOKit、BSD/root关键调用；右侧网格行距24，入口黄/上下文紫红/调用蓝/后继绿，不能沿用PROBE17编号。

## 本轮修复

用户确认横纹肉眼存在，菜单没有，触发后随色带/HEX出现。HEX_RENDER每行写1920字节却只减1280，导致每行漂移160像素，黑色覆盖Logo。已修正1920，旧包负对照有框外写，新包精确矩形检查为0；实机消失与否待验。原始有声视频/静态帧只留本地。

临时异常向量原来零填充在前、分支在槽末，实际入口无法可靠到报告器；修正分支在槽首，并逐个验证16入口及旧包负对照。首线程入口核对并恢复预先捕获的原生VBAR，避免探针长期拦住正常中断；错误捕获值A02C=2停住，成功1。原生中断控制器功能未验证。

y224白/青校验带在load_context绘制，后续只读回。A02A=不符预期像素数，A02B=最后检查ID，A02C=原生向量交接状态；这些字段覆盖旧DT/SoC含义，必须按PROBE18布局解释。CPU读回正确不代表扫描输出正常。

## 验证与模型边界

740逐点差分（GPR/SIMD/栈/标志/像素）、42入口/MMU、18读数、5WFE、6静态walk、5ParseKernel、8稀疏阶段、2异常处理器、6精确矩形、10上下文/显示、5真实向量检查通过；最终同ADT切换12断言、6console及26绑定检查通过。镜像回读/内核重建一致；板值/TCR/owned window/donor/_verified不变，loadable=false/runtime_qualified=false。

最终连续模型已跨过首线程、恢复原生VBAR并进入PE_init_iokit；随后OSKext::updateLoadedKextSummaries的bzero+0x1c普通STP报UC_ERR_EXCEPTION，ESR/ELR/FAR为0，无host bad_memory。BSD未到达；分配映射/权限与模型异常递送尚未区分，不改参数、补假RAM或跳过清零。模型不是实机结果。

证据reports/kernel-entry-probe/2026-10-25-v25/；详见[操作记录](operations/2026-10-25-v25-first-thread-display.md)。通用AGENTS规范已按用户要求合并为第10节，提交280c198，原nuwa约定保留。

## 设备与下一步

最近设备后验为2026-10-25 17:18:00北京时间：PROBE17恢复Android完成1/A槽/三分区SHA与试前一致；这是历史快照。PROBE18尚未启动，需本包录像/恢复就绪、刷新基线、即时通知后单次临时boot。菜单电源Enter触发，不固定180秒；观察校验带、网格0/1/2/3/4/5/6以及A02A–A02C，保存后恢复Android与三SHA。

正式源码整核接入、计时/中断、必要设备/存储/root和用户态仍需推进。QR/AdvancedLogDxe覆盖UEFI/EBS前，不替代内核日志。原始媒体只留本地，无push。