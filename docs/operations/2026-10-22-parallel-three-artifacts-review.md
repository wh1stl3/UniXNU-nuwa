# 并行仓库三件产物：方案及可用性核验

核验时间：2026-10-22 15:54。D:/Code/PortingiOSWithUniXNU仅只读；没有执行该仓脚本、没有复制或重写任何内核/FD/容器，没有设备操作。该目录已产生新的有效研究成果，不能继续把它只当作早期P0存档。

## 结论

**三件真实产物已确认，可用作开发基线；尚未确认形成可启动的nuwa/iOS16闭环，更没有进桌面证据。** 推荐复用donor核验、VFS兼容实现和UEFI构建流程，在本仓补齐真实驱动及启动链。两边都已编出8796；下一步的收益来自补齐接口，而非再单独追求裸内核编译。

| 产物 | 独立核验 | 当前可用范围 |
| --- | --- | --- |
| run24源内核 | 14,867,248字节，SHA89d8ff86…；普通ARM64/MH_EXECUTE、8796.141.3/Darwin22.6.0、未解析符号0、两项NativePrelink标记1 | 源内核构建/静态分析基线；实际可选驱动被清空，尚无nuwa硬件闭环 |
| kernel-prelinked.macho | 53,014,528字节，SHAe3cfe478…；与JSON的candidate hash一致；原内核hash精确匹配run24，donor hash也匹配实际文件；30有代码组件 | 预链接候选确已生成；未验收完整重定位、ABI和运行时 |
| SILICIUM_UEFI.fd | 3,145,728字节，SHAf58d5754…，与记录一致；本地构建日志末尾Success | nuwa UEFI构建基线；4项保留区预检仍报错，DarwinBoot集成尚未取得证据 |

完整路径、SHA和命令输出来源见reports/parallel-progress-review/artifacts-review.json与run24-inspection.json。旧.work/nk/kernel.macho是run22输入，不能把它错当当前预链接输入。

## 已确认的接入差异

1. **真实驱动选择**：对方macos-kernel-probe.yml明确清空out/sheng/.config，只保留NativePrelink子模块；run22/run24的linkarchives只有firehose，实际内核也未导出armcpu/armdt/armvirt的状态标记。device/nuwa/configs/nuwa_defconfig写了很多=y，不代表这批二进制已带上它们。当前本仓也处于源构建基线，正在用第十一轮补真实archive验证。
2. **版本参数**：对方run24实际LC_BUILD_VERSION最低系统和SDK metadata为17.0，本仓第十轮为16.0。两者源码都是8796.141.3；该metadata差异不能独立证明运行失败，但后续构建应统一既定iOS16目标，不能混写成同一套参数。
3. **真正可复用的VFS桥接**：本仓第十轮内核与同一真实donor、参考roots/slide做只读plan，实际首错是_vfs_getvfs_with_vfsops无native候选。对方run24已导出这个符号。其补丁的函数定义与本地10063上游vfs_subr.c:1955归一化后相同，实际查找mount并验证mnt_op，不是空stub；可作为回移候选，仍需本仓实际编译及锁/调用语义复核。此次只读plan不采纳参考板的slide/roots，也不写board。
4. **donor身份可以复用证据**：独立读取Restore.plist/BuildManifest.plist确认iPhone10,3、16.7.16、20H392、d22ap、CPID0x8015、BDID6及KernelCache成员名；实际解码文件SHA为2ec297ba…，与预链接报告一致。原始文件/manifest哈希见donor-and-relocation-review.json。没有改本仓IPSW身份字段或继承其下载URL。
5. **预链接工具豁免还需收口**：0001的窗口外放行条件没有限制page=False；实际报告12处豁免中4处解码为ADRP。0002用“不是已知函数入口”判为常量，不能独立排除合法ADR/字面量读或跳到函数内部的指令。需要逐区间完整字节hash、代码/常量边界及真正引用目标证明；不能把emit成功当成指令语义已证明。此次未执行修改后的emit。
6. **false标记的准确含义**：loadable/abi_qualified/runtime_qualified等在官方plan/emit中就是保守的字面默认值（native_prelink.py:246、emit_prelink.py:305）。它们意味着尚未验收，并非emit发生失败的错误码；本次产物hash确已核对。
7. **固件尚有独立门槛**：preflight.json保留4项未覆盖区（xbl-dt-log、aop-config、adspslpi、rmtfs），workflow将预检设continue-on-error。完整日志没有DarwinBoot编译项，当前平台FDF也未见直接接入；尚未解包全部包含文件/FD证明缺失，故结论是“DarwinBoot集成未验证”，不是凭字符串缺失断言绝对不存在。对方6GiB窗口和内存图不能直接替代本仓D-002先512MiB–1GiB的阶段5方案。

## 具体推进方案

**路径A（采用）：复用成果，补齐本仓设备闭环。**

1. 收取第十一轮真实四项编译记录和三项平台archive结果，按实际首错修复；验收对象ARM64/iOS16、ar成员、定义/导入闭包。通过后仍需明确接入时序及正式nuwa配置，不把“库存在”当“已链接”。
2. 复审并回移VFS符号实现/声明/导出，重新做真实donor只读plan；从本轮native/donor段范围计算可行布局，核对AMFI initializer来源。已定位参数可作为候选输入，不直接复制进board。
3. 审计预链接的代码/常量豁免，关闭未知站点的宽泛放行；继续核对组件依赖、指针绑定、kmod入口及跨版本ABI。先只读分析；新生成预链接候选按镜像边界另审查。
4. 复用Mu-Silicium钉版/nuwa包/厂商模块构建方法，先只读对账4项保留区，核对DarwinBoot实际模块及加载配置；保持D-002的小窗口目标，未知装载地址不填。
5. 前置证据齐全后，按硬停规则提交镜像生成/临时启动的具体范围和恢复方案；QEMU和实机分别验收。当前未执行此步。

代价：还需至少驱动、预链接和UEFI接线三类接口收口；好处是沿用已成功的固定内核输入，能逐项定位失败，不依赖未审查板值。

**路径B：以对方现有三件作为独立候选，先做其启动闭环审查。**

可减少重建已有产物，但仍要补驱动闭包、DarwinBoot、保留区和预链接语义；现有6GiB策略、KPC恒零兼容实现及17.0链接参数还会扩大差异。它适合对照，不具备绕过上述门槛直接承诺进桌面的证据。两个仓库保持分开，不写入对方目录或复用凭据。

本轮未触及四类硬停，无需为只读核验新增批准问题。后续涉及board身份/内存/基址、新镜像、设备动作或_verified=true时仍单独停审。
