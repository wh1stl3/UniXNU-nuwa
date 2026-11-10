# nuwa iOS-only handoff — 2026-11-10

## 本轮完成

- 落地本地 iOS 交接及[研究证据记录](image4-firmware-evaluate-20261110.md)，仅文档，不集成未审研究代码；不构建、不操作设备、不外发。
- 已有设备主机基线 `8ae344cc05879a27cf77b5103e30b2ca51a6d41d`；固件日志组件 DEBUG mask `0x8007EE4F` 提交 `719afa67e3aebbf058c2a8beff4c801057fb2b20`。两仓不 push/merge。
- BNCH 四矩阵/26 evidence robustness、consumer-parse 的已有独立结果见 [离线证据](image4-bnch-offline-20261110.md)，未重复运行。此次文档记录自检仅 self-checked，不提升阶段验收。

## 当前状态

- 官方第 7 步，目标 iOS 16.7.16-20H392 / XNU 8796.141.3。实机 AppleImage4 `failed to get mix-n-match policy: 2`，显示后 park，不证明 stage5；AMNM-only 及任何 BNCH 运行候选仍禁止设备放行。
- firmware-evaluate 的 helper/issuer 到原生摘要及 RSA 准备边界。受限 Data 首2584字节 native bzero/clear各全覆盖，零内容/原size free及生命周期闭合；第二5152请求来源未准入，BLOCKED。OOM 原internal -13→evaluate80，无成功alloc/free；13项隔离模型负例不是认证负例。
- 上述 helper/issuer及ledger/OOM已独立机械执行/schema核验（父会话提供）；ledger exit2/BLOCKED、errno null，OOM exit0、原生errno80，脚本固定状态self-checked不否定独立复跑。两报告绑定脚本SHA256 `94d09c6bebd7367d3b3211eb54fbd7453756af5742d78a366b965d6a48c7e73c`。纠正JSON字段后断言exit0，逐项dependencies核对；退出码仅有会话工具回包，无独立断言落盘日志。详情及正确字段路径见研究证据末节。
- 认证、签名阳性及nonce闭环未证；不能把解析/摘要/资源生命周期结果称认证成功。现有固件mask静态review/机械PASS不等于完整EDKII解析/AutoGen/编译或设备验收。
- UFS审计已主机交付（后续最终通知）：`scripts/audit-nuwa-ufs-inputs.py` 389行及 `docs/nuwa-ufs-input-audit-20261110.md` 184行，dtc/fdtget实查32nodes/59refs/0unresolved，7 self-tests、audit、py_compile exit0；证据 `out/ufs-input-audit-20261110/final/`。仅self-checked、未独立验证，未启用driver或操作设备；iOS16/8796 ABI、UEFI资源/队列交接、DMA/SMMU资格仍BLOCKED。

## 下一步第一动作

- UFS资源审计 `ses_e39ef5ef2ffeVMCa4md6XcUUUv` 已结束并主机交付：安排独立verifier按其文档复跑self-test，并用独立 `out/verifier` 输出执行审计；核对结果及适用审查后再决定集成。本次不运行该脚本或提交其实现/文档。
- 接收独立固件环境 `ses_e3a038a3cffedY0iFGoTU6dXYM` 最终交付；该任务尚未最终收尾，本次不poll、不重跑、不纳入未交付文件。
- 本地主机实现/验证按各自已授权边界继续，主线并未整体停止。研究适用静态审查未完成，保持该门禁；不换模型绕过服务端限制，不扩张5152准入、不猜nonce或替换安全结果。

## 阻塞项与未提交内容

- ledger最新静态review被服务端`cyber_policy`拦截，未完成，不记PASS；`scripts/research-current-image4-firmware-evaluate.py` 保留工作区且不集成、不删除/移动。文档提交仅保存证据与待办。
- UFS脚本/文档已交付但待独立verifier、尚未接受集成，默认保留未提交；独立固件环境任务尚未最终交付。两项后续可独立推进，不把研究审查阻塞泛化为停止主线。
- 既有设备AGENTS/README/porting工作区混合差分原样保留且不暂存；未知文件、固件脏子模块不清理。含Apple内容的输入/产物及媒体只留ignored本地目录。公开资料只读，不向外发消息；设备写入仍须当轮授权和既有身份/目标/回读门禁。
