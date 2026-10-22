# 第一批8796补丁候选与接口风险

## 本次结果

在设备仓新增5个8796候选，全部独立 `git apply --check` **静态检查通过**；没有修改只读源树、完整应用补丁、编译或切feed。原49项统计不重写成43通过：那是不同输入集。候选不是完整覆盖模块，尚未接入构建。

命令：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -B scripts/prepare-8796-context-candidates.py
```

输入为基座 `75bc13dd34dc4e403826793739e316a264ce00dd` 与8796树 `1b191cb58250d0705d8a51287127505aa4bc0789`。脚本校验全部49个原补丁哈希未变化，只在内存读取源文件、构造diff，写到 `patches/xnu-8796-candidates/`。不复制上游源码文件，不调用任何Git写命令。源树前后status返回0且为空，日志、逐补丁原哈希/候选哈希、精确检查命令见 [results.json](../../reports/xnu-8796-candidates/results.json) 及同目录各patch.log。

## 逐项适配理由

源码证据相对 `D:/Code/PortingiOS/common/sources/xnu-ios16-full/`。

| 候选 | 8796证据与处理 | 验证限制 |
| --- | --- | --- |
| apple-only-cpu-tunables.patch | `osfmk/arm64/start.s:35-36,780`：保留assym.s，仅对原tunables include和MIDR/APPLY_TUNABLES块加Apple架构guard。 | 未汇编或验证启动。 |
| external-archive-dependencies.patch | `makedefs/MakeInc.kernel:147`：实际目标是`.unstripped`，8796无`.unstripped.noctf`目标；将外部archive依赖挂到实际目标。 | 不是单改行号；静态匹配不证明最终构建脚本的输出文件名/增量链接适配完成。 |
| native-aes-personality.patch | `iokit/KernelConfigTables.cpp:35-42`：表尾是IOPanicPlatform，非IOExclaveProxy；原补丁新增personality文本逐字提取并插到表尾。 | 驱动ABI与绑定未验证。 |
| source-machine-layer.patch | `config/MASTER:322-325`、`config/MASTER.arm64.bcm2837:19,53-54`、`osfmk/conf/files.arm64:28-29`：保留8796上下文，增加CONFIG_APPLE_AMCC声明、nos_arm_*选择，去掉两项sched_hygiene_debug，并只给实际存在的两项AMCC单元加gate。 | 不发明8796不存在的amcc/ctrr3文件；machine layer构建选择和符号集合尚未编译验证。 |
| zzx-pmap-sync-64bit-pa.patch | `osfmk/arm/pmap/pmap.c:6877-6880`：保留原ptoa扩宽修复及注释，仅删除8796不存在的SPTM分支。 | 不涉及板级内存数值；PA运行行为未验证。 |

完整有效补丁集还需要SystemOS、public-entitlements、boot-progress及依赖审查。现有5个不能替换完整xnu模块，见候选目录README。

## 新发现：独立apply通过不能替代API审查

原49项中 `offline-pgz-alignment-probe.patch` 虽独立检查通过，但新增函数调用 `zone_id_require_aligned`（原补丁第51、77行）。8796 `osfmk/kern/zalloc.c:1467` 的接口是 `zone_id_require(zid, esize, addr)`，不存在aligned接口；原 `pgz-aligned-validation.patch` 因而不能直接搬入。

复查命令：

```powershell
rg -n 'zone_id_require_aligned|zone_id_require\(' D:/Code/PortingiOS/common/sources/xnu-ios16-full/osfmk/kern/zalloc.c D:/Code/PortingiOS/common/sources/UniXNU/patches/xnu/offline-pgz-alignment-probe.patch
```

不能只丢掉失败的PGZ修补而宣称其probe可用：启用probe时有缺失API风险（这是静态接口分析，未实测编译失败）。下一步需在完整8796选择集中明确probe的禁用或等价移植；本轮没有新建API、改默认defconfig或跳过安全校验。`published-freezer-condition` 同样需按8796现有策略判定适用性，不能引入17.x策略只为凑通过数。

## 后续门槛

先完成剩余适配与明确不适用项、按真实顺序验证完整选择集，再审查Darwin22驱动/静态库与预链接接口。当前基座还依赖Xcode/iphoneos SDK，WSL可构建链未验证；不能把补丁文本检查当作编译证据。NativePrelink两项独立通过的报告另见 [补充检查](2026-10-22-native-prelink-8796.md)。板级未知值继续TODO；没有QEMU、镜像或设备动作。
