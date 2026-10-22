# 8796候选选择集：内存顺序模拟与合并diff检查

## 结论

**48项候选在内存中的顺序模拟静态检查通过，最终合并diff的 `git apply --check` 返回0。** 其中包括NativePrelink两项；另有3项未选入（见D-007）。没有在磁盘工作树实际顺序应用补丁，没有编译、链接、QEMU或实机验证。feed仍为原版本，候选未接入基座构建模块。不能将此结果写成“51项补丁全部通过”或“8796已可启动”。

## 可复现证据

命令（仓库根，Windows PowerShell）：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B scripts/prepare-8796-context-candidates.py
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B scripts/check-8796-sequence.py
```

后一命令输出：

```text
Baseline virtual/Git pass-fail mismatches: 0
Selected sequence complete: True
Combined diff --check exit: 0
```

完整证据：[results.json](../../reports/xnu-8796-sequence/results.json)，含输入HEAD、每项原始SHA-256与选用SHA-256、顺序及逐hunk落点、合并diff的精确Git命令和输出、源树前后status。检查前后源树status均返回0且为空；基座tracked status为空。

基线保持XNU `1b191cb58250d0705d8a51287127505aa4bc0789`（8796.141.3）、UniXNU `75bc13dd34dc4e403826793739e316a264ce00dd`。脚本逐项校验51项上游补丁哈希与先前只读Git记录一致，避免对变化后的输入引用旧结论。

## 方法与限制

`scripts/virtual_patch.py` 只把受影响文件读进进程内存，按原始xnu/*.patch文件名顺序，再按NativePrelink/*.patch顺序模拟。hunk要求完整文本精确匹配，不忽略空白或删上下文；找不到或匹配歧义即失败，不继续声称后续通过。没有将上游源文件复制入本仓。

先用原51项分别对干净8796树模拟，与已保存的真实Git独立检查的成功/失败结果比较，差异为0。该比较只是对本次输入的交叉核对，不证明自写解析器在任意diff上等同Git。最终把48项的累计文本变化折叠为 [selected-combined.patch](../../reports/xnu-8796-sequence/selected-combined.patch)，再让真实Git对只读原树执行 `apply --check --verbose` 返回0，验证最终diff可匹配。所有Git调用均只读。

这一方法覆盖文本依赖和最终变更适用性；没有替代未来获准的真实工作树顺序应用、编译、ABI或运行测试。合并diff为审计证据，不是新的正式构建入口。

## 补全的三项候选

前5项见[第一批报告](2026-10-22-8796-context-candidates.md)。本次候选目录扩展至8项，仍不是完整xnu模块。

| 新候选 | 适配内容 | 未验证 |
| --- | --- | --- |
| public-entitlements-header.patch | 保留原CoreEntitlements公共定义；去掉8796 necp_client.c中不存在的CodeSignature include替换。不向8796引入17.x Web Browser Engine调用逻辑。 | 定义消费者及完整编译。 |
| offline-owner-systemos-mount.patch | 在8796现有kern_exec_internal.h后补CoreEntitlements include；根卷/exec补丁其余hunk保持原文。顺序模拟涵盖后续zzy GPU addon mount的依赖。 | 真正根卷挂载、授权路径及驱动接口。 |
| zzz-boot-progress.patch | 适配sleh.c版权上下文与Makefile导出列表；8796的proc_prepareexit无task局部变量，把exit观测放在既有局部变量声明后、critical-exit分支前。8796无self-restrict/JIT-fatal块，把用户abort观测放在原PAC分类后、exception_triage前（原树sleh.c:1484附近），不引入17.x JIT逻辑。PMGR/SystemOS依赖由前序补丁提供。 | 观测回调ABI、锁/中断上下文、watchdog策略与运行行为。 |

## 未选入项（D-007）

- `pgz-aligned-validation.patch`：8796没有其修补的zone_id_require_aligned，不能凭空补一个17.x allocator API。
- `offline-pgz-alignment-probe.patch`：可选诊断探针依赖上述缺失API，延期移植，不宣称兼容。未来defconfig不得启用该探针；本轮尚无defconfig。
- `published-freezer-condition.patch`：8796没有10063那段畸形条件式；保留原树 `memorystatus_freeze_enabled = FALSE`，不引入17.x freezer策略。

这是8796候选选择的技术决策，不是删除只读上游补丁或修改feed。原49项独立检查统计仍是38/11。

## board与基座入口

获批board用tomllib解析通过，并成功执行：

```text
python -X utf8 -B D:/Code/PortingiOS/common/sources/UniXNU/unixnu status -D D:/Code/UniXNU-nuwa --out D:/Code/UniXNU-nuwa/out
exit_code=0
device   D:\Code\UniXNU-nuwa (nuwa)  [EXAMPLE]
output   D:\Code\UniXNU-nuwa\out\nuwa
config   none (run defconfig)
```

日志见 [status.log](../../reports/board-integration/status.log)。默认Windows GBK编码读取中文TODO失败的记录另存 [status-default-encoding.log](../../reports/board-integration/status-default-encoding.log)；用 `-X utf8`解决，未改获批board内容。`-B`避免往只读基座写字节码，`--out`使state.json仅写本仓忽略目录。这个status只验证模块解析，不是tree装配、完整配置或构建验收。

下一步是8796静态库/driver与预链接ABI审查、适配构建脚本的实际输出及Darwin22接口、明确WSL工具链；满足门槛后才另开feed切换。board继续example=true，未知板值仍TODO；无镜像或设备动作。
