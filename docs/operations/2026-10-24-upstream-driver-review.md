# UniXNU最新驱动审查（2026-10-24）

## 核查范围与结论

直接读取GitHub官方API：主仓main=1a01c2afa197d975d04da892325c56b6b14aaecb，提交时间2026-10-23T15:24:05Z（北京时间23:24:05），最后一项是社区设备文档。近几日驱动确有实质更新，主要分布在独立模块；本次审查12个模块最新提交及主仓gitlink，两者当时全部一致，另查同SoC sheng与Novatek。报告reports/upstream-review/2026-10-24/review.json含固定提交、Git对象比较、许可文件SHA256和关键源文件SHA256。

与当前75bc13dd的GitHub比较为diverged，上游186、基线侧36个不同提交；不是线性“落后186”。大量文件变化来自驱动拆独立子模块，不能把原路径删除误认作功能删除，不能直接git pull或整仓升级。两个旧资料库未fetch或写入，当前源码/包pin不变，无构建或手机动作。

## 实际更新及nuwa价值

| 模块固定最新 | 核实的更新 | nuwa判断 |
| --- | --- | --- |
| NativeAdreno b686b9054f57 | GPU写入的导入内存改非一致映射，减少逐提交cache工作；保持IFPC关闭、导入页生命周期/对象限制等修复 | nuwa同Adreno740族，值得跟进；GMU/电源/SMMU/IO一致性仍须板级证据，不能因为HOB cache修复就启用GPU一致性捷径 |
| NativeMetal c6d29caad6d8 | 回到system-memory渲染、关闭硬件/并发binning、双平面IOSurface与扫描线程优先级 | 上游针对sheng合成停顿的实质更新；与Adreno、显示、桥接/Turnip/着色器缓存按配套版本审查，iOS16用户态ABI另验 |
| NativeMobileDisplay 8666a9950c96 | GPU复制swap提前retire、刷新率上报、swap队列推进 | 对未来显示合成有用，不替代nuwa面板/DSC/背光适配 |
| NativeHidInput ba03e5d14745 | DigitizerCollectionDispatch、多指有效性、消失手指按identifier抬起、按键事件 | 可复用通用HID层，优先纳入后续ST FTS事件桥；不能照搬sheng触控硬件驱动 |
| NativeNovatekTouch 717c866fca65（sheng） | 预测位置全局最小距离匹配、漂移基线、峰值筛选、停留/抬指稳定 | **不适合作nuwa直接驱动**：已有本机SPI绑定fts_touch_spi、st,spi/st_fts_m2.ftb证据，属于ST FTS，不是Novatek。可参考跟踪算法，不搬固件/MMIO/IRQ |
| DarwinBoot d099354d0eab + NativeRamBlock d4d22d9819b0 | packed seed逻辑上限扩展、seed/direct/sparse后端和GpuAddon交接；UFS存储尚未接入前可读seed | 近期最值得单独评估的配套，能改善后续Data/负载合同；逻辑1TiB不等于分配1TiB，也不解决ABL ramdisk运输或把58MB放进4MiB卷 |
| NativeUfs af785c177716 | Data store FUA写、log/export区域和sheng-log-reserve布局，SMMU交接相关修订 | 存储主线来源，但写入布局与nuwa userdata策略必须独立审查，绝不套sheng分区尾部地址 |
| ArmSmmu4K 4d0d6598b1a3 | owned route观察、whole-verification更新时才观察上下文 | 可作为未来UFS/GPU接管基础；stream ID/上下文归属仍依nuwa证据 |
| ArmCpu 1951cc8444b3 / ArmDTPlatform 0d544705c2e8 | 对比基线仅新增README，代码文件Git blob相同 | 没有新CPU/平台实现可直接解决当前ADT或入口问题 |
| NativeGeniSpi b5399b5646c4 | 对比基线仅README | 不是新增nuwa SPI硬件支持 |
| NativePrelink 2b6ffb50117e | 对比基线仅.gitignore/LICENSE/README，两个预链接工具实现未变化 | 不会自动解决我们early initializer、组件ABI资格或Libm常量池补丁问题 |

最近主仓另含shader-cache按translator版本标识、允许内核参数路径、union lookup和大文件代码签名读取优化。sheng最新251b291adf94调整CPU拓扑/调度，并更新背光与触控；这些都是具体板/版本策略，不照搬nuwa CPU列表或安装/清空Data菜单。

## 静态兼容性核对

用最新DarwinBoot固定对象在内存构造路径，严格模拟应用本仓0005-darwin22-boot-args.patch通过，输入文件SHA在报告darwin22_patch_against_latest。这仅证明补丁上下文能匹配，不是构建或Darwin22 ABI通过。尚未变更profile、CI、submodule、板值、验证标志或实机包。

README的sheng运行能力是上游作者报告，不能写成nuwa验收；本次未运行驱动测试/内核编译/实机。许可证逐模块检查：Adreno/Metal/ArmSmmu4K为MIT；NativeUfs BSD-2-Clause；DarwinBoot/ArmCpu/ArmDTPlatform/GENI/HID/RamBlock/Prelink为BSD-2-Clause-Patent，API的NOASSERTION以实际LICENSE文本为准。第三方桥接及固件依赖须继续逐项保留许可，不把顶层许可覆盖所有依赖。

## 跟进决定

当前不整体升版，也不在审查中偷偷引入代码。优先单开DarwinBoot+NativeRamBlock合同/测试迁移评估，保留现有HOB缓存候选和Darwin22补丁；HID/ST FTS为输入后续；Adreno/Metal/显示/SMMU作为配套图形栈排队。现阶段首要阻塞仍是大负载运输、真实ADT、prelink初始化/ABI和实际窗口分配，这些更新不会把它们自动补齐。

原始链接：[主仓固定HEAD](https://github.com/UniXNU/UniXNU/commit/1a01c2afa197d975d04da892325c56b6b14aaecb)、[GPU修复](https://github.com/UniXNU/NativeAdreno/commit/b686b9054f57d393c80195b82568a09f8ca106a2)、[HID修复](https://github.com/UniXNU/NativeHidInput/commit/ba03e5d147452b2166aab7435d219fa10877672b)、[DarwinBoot](https://github.com/UniXNU/DarwinBoot/commit/d099354d0eab34df5088ca1ba89c9c88bc3260bb)、[Novatek](https://github.com/UniXNU/NativeNovatekTouch/commit/717c866fca652407117447df7a7c7d5addc7bfc6)。
