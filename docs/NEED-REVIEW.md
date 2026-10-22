# NEED-REVIEW

> 需要用户拍板才能落地的改动。**没有 open 项时，这里保持空表。**
> 硬停四类：改内存相关字段 / 设备写入类 fastboot 动作 / 新建或重写镜像 / 置 `_verified=true`。

## 判定规则

立项必须写清：编号、背景、**至少两个候选**、各自代价、你的倾向及理由、需要用户批准的最小范围。
只写「是否继续」不算合格条目。

## Open

| 编号 | 主题 | 需要用户做什么 |
| --- | --- | --- |
| — | 无 | — |

## 后续授权记录（2026-10-22）

用户在官方CI接入核验后指定GitHub账号`wh1stl3`，确认目标仓库尚未创建，并明确“Git的所有命令都允许”。此前仅允许status/diff/log/show的Git命令限制已解除，不再为云端checkout/clone/apply范围重复请求批准。两个旧仓及上游来源树仍只读；四类硬停、feed不变、未知板值TODO及证据纪律继续有效。Actions主机方向见DECISIONS D-008，R-003 A保留为历史审批记录。

## 审批记录：R-003

### R-003 · WSL工具链与Darwin22构建路线（approved A，第一阶段进行中）

用户本轮选择A，批准保留WSL的工具链预检/适配第一阶段；并确认没有额外Linux clang、IIG或sysroot输入。继续本仓内工作，原暂停解除；来源树、Git、feed、board和镜像边界保持。预检与非执行式适配计划已落地，9项自身测试通过，现有MIG后端代码生成及宿主头文件语法样例通过；完整工具输入仍未落实，详见[本轮报告](operations/2026-10-22-wsl-firststage-adapter.md)。以下保留审批时背景与候选。

触发来源：用户本轮第2项明确要求“要么拿出可在本机跑通内核构建的证据，要么列为不可行并写进docs/NEED-REVIEW.md……后停”。这次停下不是新增板值审批，也不是认为WSL先天不能构建XNU。

**现状结论：当前本机输入、现有基座入口和不执行Git写操作的约束下，直接完成8796内核构建不可行；没有完整内核构建通过证据。** 主线暂停于工具链门，未启动默认clone/apply入口。

背景与证据：

- [审查报告](operations/2026-10-22-darwin22-interfaces-and-wsl.md)及 `reports/darwin22-audit/interfaces.json`：8796产出.unstripped，多个基座消费者使用.unstripped.noctf；archive/编译记录生产者仍绑定Darwin23/ios17或来自sheng；13项回调只在参考树找到实现。NativePrelink kmod局部布局静态一致，但目标符号/完整ABI未验证。
- `reports/darwin22-audit/wsl-toolchain.log`：WSL可运行；默认clang14对三项XNU内建的__has_builtin探测均为0；xcrun/xcodebuild/IIG等不在PATH；有限范围没有找到已验证SDK。已有Linux MIG/cctools prefix与Python3.12可复用，没有被误判为缺失。
- watchdog参考实现有非union环境路径的scratch重叠风险；不能用导入sheng archive绕开接口适配。
- board仍example=true，feed未改。两个旧仓及上游源树保持只读，没有生成镜像或操作设备。

**候选 A：保留WSL要求，先建立经验证的Linux交叉构建输入与无Git写入适配器（倾向）。**

第一阶段交付应为：含所需XNU内建的Linux ELF编译器与版本/哈希/特征证据；MIG/IIG与宿主工具的Linux生产链；明确目标/宿主sysroot；设备仓中的8796产物/编译记录/archive调度适配设计。只用常规clang14或仅包一层xcrun脚本不算通过。随后才讨论完整源内核编译，必须单独提供真实compile/link日志、产物格式/符号检查，不能用生成数据库替代。

代价：需工具链移植或宿主提供已构建工具、对应头文件/sysroot；IIG、XNU内建与编译记录生成均是实际工作，时间和成功率未验证。还需宿主明确提供独立可写补丁应用视图，或另行批准构建视图方案，不能修改只读来源、在本仓复制整份上游源码或调用Git写命令。优点：保持当前所有构建在WSL的边界，避免引入第二个构建主机。现有Linux MIG/cctools可复查后复用，但不继承旧P16/SWEET内核结论。

**候选 B：批准仅内核与archive编译改用macOS/Xcode主机，WSL保留编排和证据审计。**

以同一8796输入和设备仓补丁选择集在用户提供的macOS主机/受控执行环境构建；回传编译记录、archive符号报告和内核哈希。本地只做读取、验证与后续集成。使用基座已有Xcode调用方式可减少宿主工具移植，但仍须修正8796产物名/版本依赖、重建driver/回调、处理watchdog风险，并核验编译器内建与SDK，不能把“有Mac”当作8796已通过。

代价：显式改变“构建全在WSL”的边界，需要额外主机/执行环境及传输、版本固定、成本与可复现性管理；主机是否可用、费用和交付时间均未验证。当前没有启动任何远端任务或外发源码/凭据，也没有新建CI workflow。

倾向 A：符合用户既定WSL主线，并能把缺失输入与接口门槛逐项验证；若用户优先减少宿主工具移植工作，B是需要明确批准的替代路径，不自动切换。两条路径均保留iOS16/iPhone donor与4KiB，均不使用iOS17 donor绕过问题。

**需要批准的最小范围：选择 A 或 B 的方向与第一阶段范围。** 选择A仅批准本仓内无Git写入的工具链预检/适配工作及输入清单落实；工具安装、外部目录写入、来源树复制/覆盖视图等需明确范围后才做。选择B需明确批准macOS内核构建例外，再确认可用执行环境，不能直接启动外部任务。

本项不请求解除Git只读限制，不授权feed切换、board内存/地址修改、移除example保护、镜像生成、设备动作或_verified=true。原暂停已由用户选择A解除；工具链输入未落实时不能宣称构建可执行。

## 审批记录

### R-002 · 首版设备描述（approved，已落地）

用户本轮回复 A，批准候选 A 的精确范围。已创建根目录 board.toml，内容与下方获批代码块逐字一致（忽略末尾换行）。没有填写内存/地址、额外IPSW字段或prelink值；example=true 与 ipad_identity=true 保持。以下背景与候选保留为审批记录，不再是 open 待办。

审批前背景：49项检查已复现38通过/11失败，D-006继续适配8796。当时本仓没有 board.toml；基座 `scripts/unixnu/config.py:73-79` 在读取模块前就要求该文件和板名。用户本轮第六条明确把 **IPSW身份** 列为硬停字段，因此即使 donor 已定，也先提交具体写入范围再停，获批前没有创建 board.toml。

候选 A（倾向）：创建下列不可构建的最小占位文件，只写已定产品身份；未知项用注释 TODO，保留缺失而不填假的数值。代价：可以为后续 status/模块解析准备入口，但不能构建、生成ADT或镜像，完整性仍不合格；`example = true` 也会拒绝 build/bootimg（`config.py:101-103`）。

```toml
[board]
name = "nuwa"
soc = "SM8550"
description = "Xiaomi 13 Pro / iOS 16 bring-up"
example = true
# TODO: kit，尚无经审查的nuwa平台kit，不能照抄sheng实现。

[ipsw]
product = "iPhone10,3"
version = "16.7.16"
build = "20H392"
device_class = "d22ap"
# TODO: url/chip_id/board_id/sha256；缺donor BuildManifest及组件哈希核对。

[payload.adt]
ipad_identity = true
# TODO: tool/chip_id/cpu_regs/psci_method等，待nuwa ADT来源核对。
# TODO: owned_memory_size，缺UEFI可用连续区证据；D-002先512MiB–1GiB，上限8GiB。
# TODO: [payload] dram_size，物理DRAM描述尚需核对，不能当作窗口大小。
# TODO: [userdata] LBA与lba_bytes，缺本轮GPT证据核对。
# TODO: [kernel] defconfig/archives，缺8796配置及Darwin22接口审查。
# TODO: [kernel.prelink] 全部数值，缺donor kernelcache分析；不借sheng/fuxi值。
# TODO: [firmware] 配置/路径，uefi-nuwa尚未建立。
# TODO: [bootimg.image] 地址/offset/pagesize/header_version，缺nuwa装载证据。
```

这些都是官方现有键；TODO注释不作为TOML字段，不引入新schema键。身份依据 D-004，安全属性依据官方摘录与 D-004；schema依据官方摘录§2及上述本地基座入口。未声明完整板级配置静态检查通过。

候选 B：暂不创建 board，先完成8796补丁覆盖、NativePrelink/接口审查和donor manifest核对，再一次性审阅更完整配置。代价：模块状态只能继续静态阅读，完整 board 仍要等待UEFI内存/bootimg证据；优点是减少占位文件的后续修改。

倾向 A：已定身份有明确来源，`example=true`限制构建，能以最小配置为设备仓接入做准备；不提前选择任何内存/基址值。

**请求批准的最小范围：仅创建上述 A 的 board.toml 内容。** 不包含内存/地址数值、bootimg字段赋值、其他IPSW字段、prelink值、镜像生成、Git写操作、设备动作或任何 `_verified=true`。若批准仅对此范围落地，后续触及其他硬停项仍单独审阅。原暂停要求已由用户选择 A 解除；批准只覆盖上述最小文件内容。

## Closed

| 编号 | 主题 | 结论 |
| --- | --- | --- |
| R-001 | 内存窗口怎么声明（nuwa DRAM 不连续 11.22 GiB） | **answered by D-001 → 修正为 D-002**：单窗口为硬约束，排除「14 段全给」；原 A 提案区间不连续，不成立；首选主 bank `0x8c0000000` / 9216 MiB，退路 A′ 768 MiB。详见 `DECISIONS.md` D-001 |
| R-002 | 首版 board.toml 最小占位 | **approved，已落地**：用户选择 A；精确内容见上方及根目录 board.toml，未授权其余硬停项。 |
| R-003 | WSL工具链路线 | **approved A，范围已明确**：用户保持WSL主线；本仓预检/适配计划已落地，工具输入仍未落实；未批准安装或其他目录/源树写入。 |
