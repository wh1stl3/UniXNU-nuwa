# nuwa iOS-only handoff — 2026-11-10

## 本轮完成

- 最新本地 checkpoint `63769f208783769f7fa4ec5cffc14d3eba37b21a` 已纳入 UFS 脚本/文档及 ledger 主控单脚本静态审查记录，未 push/merge；研究脚本未集成。本次仅记录整改，不重跑研究、不构建、不操作设备、不外发，self-checked。
- 已有设备主机基线 `8ae344cc05879a27cf77b5103e30b2ca51a6d41d`；固件日志组件 DEBUG mask `0x8007EE4F` 提交 `719afa67e3aebbf058c2a8beff4c801057fb2b20`。两仓不 push/merge。
- BNCH 四矩阵/26 evidence robustness、consumer-parse 的已有独立结果见 [离线证据](image4-bnch-offline-20261110.md)，未重复运行。此次文档记录自检仅 self-checked，不提升阶段验收。

## 当前状态

- 官方第 7 步，目标 iOS 16.7.16-20H392 / XNU 8796.141.3。实机 AppleImage4 `failed to get mix-n-match policy: 2`，显示后 park，不证明 stage5；AMNM-only 及任何 BNCH 运行候选仍禁止设备放行。
- firmware-evaluate 的 helper/issuer 到原生摘要及 RSA 准备边界。受限 Data 首2584字节 native bzero/clear各全覆盖，零内容/原size free及生命周期闭合；第二5152请求来源未准入，BLOCKED。OOM 原internal -13→evaluate80，无成功alloc/free；13项隔离模型负例不是认证负例。
- 上述 helper/issuer及ledger/OOM已独立机械执行/schema核验（父会话提供）；ledger exit2/BLOCKED、errno null，OOM exit0、原生errno80，脚本固定状态self-checked不否定独立复跑。两报告绑定脚本SHA256 `94d09c6bebd7367d3b3211eb54fbd7453756af5742d78a366b965d6a48c7e73c`。纠正JSON字段后断言exit0，逐项dependencies核对；退出码仅有会话工具回包，无独立断言落盘日志。详情及正确字段路径见研究证据末节。
- 认证、签名阳性及nonce闭环未证；不能把解析/摘要/资源生命周期结果称认证成功。现有固件mask静态review/机械PASS不等于完整EDKII解析/AutoGen/编译或设备验收。
- [UFS 独立 verifier](nuwa-ufs-input-audit-20261110.md#independent-verification-2026-11-10) 已完成：self-test 7、audit 32 nodes/59 refs/0 issues、py_compile/diff 均 exit0，独立输出 `out/verifier-ufs-20261110`。仅离线资源审计，`driver_readiness=BLOCKED`；未启用驱动，iOS16/8796 ABI、UEFI资源/队列交接、DMA/SMMU资格未闭合，区域等级不变。
- ledger 主控静态 PASS WITH CONDITIONS 仅覆盖 SHA256 `94d09c6b…` 单脚本的 harness 安全/模型一致性，不是完整依赖或原生 ABI 独立审查，不能笼统关闭适用门禁。随机 BNCH 不导致固定 Issuer 模式的自身证书/manifest 随运行变化；固定 key/cert/payload 与生成路径见研究记录末节。
- 固件隔离环境终态为 self-checked/BLOCKED：已取得固定 Mu_Basecore/edksetup，随后 brotli fetch rc128，准备 wrapper rc1，已结束而非仍运行；未执行 BaseTools 或 EDK 解析/AutoGen/编译。证据为设备仓 `.cache/fw-mask-719afa67-20261110/RESULT.md`。

## 下一步第一动作

- 先只读明确完整消费者契约及 apin/IM4M 输入边界。本地基座的完整绑定与结论范围见[2026-11-11 只读补核](#local-base-readonly-20261111)；原 reviewer 的 revision 未记录，不能倒填当前 HEAD。nuwa 已设置 AMNM-only，native-trust-cache-runtime/AMFI 属性不能替代缺失契约。
- 资产 reviewer 仅查基座 `out/ipsw/20H392` 十二文件未见 apin/IM4M；其他缓存未查、另有 agent 定位，不能推断全机无资产。接收该定位结果，不重跑已有研究。
- UFS 下一步只读准备 iOS16/8796 ABI 及固件资源/队列交接输入 brief；固件只读核对已交付 RESULT/result/fetch 日志，不重跑网络准备（下载重试预算已耗尽）。本地主机工作按各自授权继续；不扩张5152准入、不猜nonce或替换安全结果。

<a id="local-base-readonly-20261111"></a>
## 本地基座只读补核（2026-11-11，self-checked）

- 本次新读取 `D:/Code/PortingiOS/UniXNU` 当前 HEAD：`693f5d9cae8a408dd18b39f3f9fdc4228c934241`；不是原 reviewer 时点的 HEAD 证明，原 review revision 未记录，也不代表最新远端。
- 完整文件路径 `D:/Code/PortingiOS/UniXNU/scripts/unixnu/devicetree.py:335–340`：335 行合入 `platform.chosen` typed properties，340 行创建空 `node('manifest-properties')`。仅该行段可确认没有在此生成 AMNM/BNCH，不据六行推断全仓无 producer。
- 对该文件执行 `git status --short -- scripts/unixnu/devicetree.py`、`git diff -- scripts/unixnu/devicetree.py` 和 `git diff --cached -- scripts/unixnu/devicetree.py` 均无输出、exit0：该文件无已暂存/未暂存修改；不表示整个基座 clean。`git rev-parse HEAD` exit0，文件行段另经只读读取确认。
- 同期父会话搜索记录（未重查）：WSL 三个 nuwa 目录存在；深度6、仅 `*.ipsw` 的搜索未返回匹配，未明确记录退出码，不能据此判定全局缺失或其他缓存无资产。

## 阻塞项与未提交内容

- ledger 委派静态审查被服务端 `cyber_policy` 拦截；后续主控单脚本限定审查不替代完整依赖/原生 ABI 独立审查。`scripts/research-current-image4-firmware-evaluate.py` 保留工作区且不集成、不删除/移动，5152来源仍 BLOCKED，无认证/nonce/设备放行证据。
- UFS 脚本/文档已在上述 checkpoint，独立离线验证已完成，不代表驱动就绪；固件环境已最终交付失败终态，解除 brotli 下载阻塞需新决定，不能预称构建通过。
- 既有设备AGENTS/README/porting工作区混合差分原样保留且不暂存；未知文件、固件脏子模块不清理。含Apple内容的输入/产物及媒体只留ignored本地目录。公开资料只读，不向外发消息；设备写入仍须当轮授权和既有身份/目标/回读门禁。
