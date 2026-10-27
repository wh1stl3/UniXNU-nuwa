# revision37 离线验收进度

本记录覆盖交接中“尚无实现／尚未运行”的历史状态，但不将离线结果升级为实机通过。不提交、不操作设备，保留迁移修改与原始证据。

## 最终结果

本轮离线准备完成。最终上下文目录 `reports/kernel-entry-probe/2026-10-26-v37-context-qualified/` 的41项绑定已实际通过。唯一当前包报告 `reports/xnu-first-entry/entry-probe-29-qualified.json`，镜像 `out/trial-boot/xnu-entry-probe-29-read-dispatch-qualified/boot-xnu-first-entry.img`，204484608字节，SHA256 `663e804ba927586253ad8f4c5c7cb54006a89d168d388bb87f58a594ab8d446e`。独立 `build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-29-qualified.json` 成功解析包并回读真实FAT载荷；控制台见 `reports/kernel-entry-probe/2026-10-26-dispatch-review-01/package-qualified-validation-console.txt`。首版29报告保留为失败资格，不使用。

下一步设备动作缺本轮观测／恢复条件，按R-015停止；不启动、不查询、不发送候选。当前HEAD基线仍为855daaf，改动未提交，未触发CI。后文测试“尚须执行”是过程记录，以本节及最终报告为准；没有新的用户态实测结论。

## 固定候选与范围

构建报告：`reports/kernel-entry-probe/2026-10-26-v37-review-final/build.json`。候选路径 `out/kernel-entry-probe-37-read-dispatch-review-r2/kernel-entry-probe.macho`，58462208字节，报告SHA256为 `d9a9c6c4655244aa3dba895225943e0804058387207fde7bd3c35154633c4dee`；透明性测试独立校验候选字节摘要。

新增 A036 显示同一读取作用域的实际 x8；A037 与276标记仅记录固定候选入口，不能证明其他目标是否进入。保留原生调用、返回与错误路径。真实文件系统函数体未在模型执行；未证明完整header、解压、dyld或用户态。

## 已有证据与新发现

- `reports/kernel-entry-probe/2026-10-26-v37-review-final/execution.json` 保留原完整串行执行：前15项成功，第16项透明性在旧画面边界断言失败。不得覆盖这份失败记录。
- `reports/kernel-entry-probe/2026-10-26-v37-review-r2/read-dispatch.json` 是此前11用例结果的历史快照；测试源码再次修改后，不沿用其源绑定资格。
- 本次为透明性检查增加 revision37 的三个精确矩形：A036 `(256,784,480,20)`，A037 `(256,812,480,20)`，276 `(832,808,32,16)`；保留旧版本边界，检查相邻行、跨矩形和跨行写入被拒绝。第一版遗漏A036末尾四行，仍失败；再次修正后需以实际新报告判定。
- 集成模型此前以原型代码范围筛选画面写入；原型为空时计数缺失。现检查实际帧缓冲写入，正常用例必须有非零写入且达到第831行。此为测试覆盖修复，不是设备故障根因。
- 证据绑定测试新增缺分派报告、删用例后重封摘要、取消错误寄存器负对照三种拒绝检查；尚须实际执行通过。

## 验收缺口及边界

最终上下文补验目录为 `reports/kernel-entry-probe/2026-10-26-v37-context-qualified/`。因首次包 `reports/xnu-first-entry/entry-probe-29.json` 的转场报告绑定旧ADT，独立验收明确拒绝，**该首包未验收，禁止启动**。失败日志 `reports/kernel-entry-probe/2026-10-26-dispatch-review-01/package-validation-initial-console.txt` 原样保留。新目录的 `inherited-evidence.json` 记录未受ADT变化影响的报告逐字节拷贝来源，不冒充重跑；早期标记、四类转场及控制台策略全部针对新ADT重新执行，最终绑定另行执行。原目录报告不覆盖。

独立重建 `reports/kernel-entry-probe/2026-10-26-v37-reproduce/build.json` 生成相同58462208字节内核及同一完整SHA256；日志 `reports/kernel-entry-probe/2026-10-26-dispatch-review-01/reproduce-console.txt`。此前review-final绑定41项已通过，不能因此替代新上下文最终包的实际回读验收。

本次实际新增通过：`transparency.json` 1096组原生状态对照及矩形负对照，`read-dispatch.json` 11用例（含实际画面写入计数、旧入口标记清除及错误寄存器负对照），`image4-launch.json` 25项，`pthread-startup.json` 6项，`root-stop.json` 15项，`root-inputs.json` 7项，`fscompression-startup.json` 8项，`read-boundaries.json` 11项及 `read-boundary-source.json` 5个位置静态核对。以上路径均位于 `reports/kernel-entry-probe/2026-10-26-v37-review-final/`。

续跑曾误用v36启动清单，触发 `Manifest component mismatch: kernel`，原始失败保存在 `execution-continuation.json`。随后误把已带身份的最终ADT当base，生产器拒绝 `Refuse to replace an existing platform/firmware identity`；未移除或绕过检查。最终定位 `out/exec-mainline-v36/launch/base.adt`，独立核对13212字节、SHA256 `6270ea69b086b6c9a103163c71e311fec547de7c42918db57d81da3815a08742`，与原清单输入一致，再生成新的上下文。新ADT位于 `out/exec-mainline-v37-review-context/launch/kernel.macho.adt`，SHA256 `32565b70b2c56c42e9b18ab39c58475de3a118cb9e2d3ac82532dcea4230dbd2`；新nonce及清单独立生成，旧证据不变。

pthread测试最初因版本白名单未含37拒绝；只增加明确的37支持，原模型和断言保留，6用例实际通过。失败见 `execution-context-corrected.json`，后续串行结果见 `execution-remaining.json`。最终绑定结果仍须以 `binding.json` 实际存在且通过为准。

透明性重跑及剩余串行测试以新报告为准；完整绑定、独立重建、打包回读均不得假称完成。临时续跑控制器 `out/continue-v37-review.py` 保留原失败 execution，只向尚不存在的报告路径输出；拒绝覆盖已有续跑记录。不可盲目重复执行历史启动命令。

历史最后设备后验仍为2026-10-26 12:24:07上海时间，Android恢复及三分区摘要一致；本次未查询。PROBE28已消费，禁止重发。用户当前无法拍摄及按键恢复，设备动作保持暂停。内存／基址／身份、`*_verified`、239门不变。离线候选资格不替代下一轮观测、恢复和预检条件。

迁移后本轮执行仅覆盖明确列出的脚本与固定输入，不是全量迁移验证；旧报告和固定工具链配置保持原证据意义。
