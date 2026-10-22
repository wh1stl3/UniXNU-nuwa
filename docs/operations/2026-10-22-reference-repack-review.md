# r6模板重打包脚本复核

2026-10-22。用户转述另一对话的repack-nuwa-boot.py及F-016结论。本轮只读来源脚本/文档/模板，在内存独立重压和解析；不执行参考仓脚本，不生成或启动镜像。脚本/模板hash和自动核对结果见reports/repack-reference-review.json。

## 可以吸收的修正

固定Mu所带AOSP Resources/Scripts/mkbootimg.py:79-85、:225-240证实：v1 ID对kernel、ramdisk、second分别喂“内容+u32长度”，再计recovery_dtbo；缺失时只计0长度。tags_addr不参与。ID存储32B，SHA1为20B，余12B补零，不能缩短header的bytearray切片。参考修正正确，但其v1_id实际只覆盖无recovery_dtbo的v1子集。

独立脚本scripts/ci/audit-reference-repack.py没有import或执行来源脚本。读取r6模板SHA ed8c401576fcf5ed3cd5ca871457d7a38038d9f02bbf22875b24d5d301295acd，验证v1/4096B页、空second/recovery_dtbo、1648B头、精确总长及gzip EOF/FDT边界。模板原ID与AOSP算法一致。解压后112B shim的SHA9346a527…与咱们相同，旧FD SHA9a788b48…，真实附加DTB SHAd865e662…。

同FD重压的kernel长度不变；相对完整镜像唯一kernel差异在4105（0x1009），gzip OS由3变255，ID前20个字节随之变化。重新计算的32B ID保持尾12B补零，原ramdisk保持不变，计算出的整体布局仍203157504B。复现了对方的这个有限回环结论；它只证明该输入下的字节/布局一致性，不证明启动或任意FD都安全。

同FD改完ID后不可能全镜像SHA不变，OS字节区别也应保留为构建工具差异；不要把gzip头统一值当成无依据的硬件修复。

## 不能沿用的整体判断

1. **“nuwa ABL只吃v1+大ramdisk”证据不足。** F-016覆盖几个特定v1/v3容器，至多说明这些组合的结果。reports/trial-boot-preflight/stock-temporary-boot.json及identity-gate.json已有本机原厂v4临时启动进入Android=1的反例。这个反例证明v4存在可接受输入，不证明咱们未运行的v4固件候选一定成功。没有实测ramdisk大小阈值，也不能把0/5B与192MiB之间的差异唯一归因为大小。
2. **Booting OKAY不是UEFI通过。** 对方F-016原文说明30s后仍回fastboot；没有SEC/DXE/BDS日志，不能确定是否跳入目标、在哪里异常或由什么原因复位。更不能仅凭这一现象归因6GiB、页表或显示。
3. **不能将原192MiB ramdisk原样用于本仓入口验证。** 实际FAT含旧kernel.macho（SHA e3cfe478…）、ADT、trustcache和unixnu.toml；不是空白占位。配置timeout=3、default=xnu；ADT窗口6442450944（6GiB）、dram-size9663676416（9GiB）。咱们FD现在含应用/注册器/DarwinBoot/发布器，与当时缺加载链的旧FD行为可能不同；配置卷若发布并扫描成功，会尝试参考旧内核。不能因此继承其内核、donor重定位豁免或内存决定。本仓主内核仍是CI15 SHAa9e08c69，D-002初始512MiB–1GiB。
4. **换FD后总长可以变。** 用咱们FD SHAa0bbb964…在内存替换、同参数gzip并保留参考DTB，kernel字段1861373B，按页对齐推算总长203194368B；旧模板kernel1824838B、总长203157504B。差36864B是布局变化，脚本应按新kernel位置搬ramdisk，不能强制“必须等长”。本轮没有写出这个混合镜像，也不会把旧负载试算结果用于设备。

boot.json的dtb_sha256记的是patch_dtb前的输入文件hash，而本轮列的是实际附加DTB hash；固定base scripts/unixnu/bootimg.py:89、:111展示这一差别，不将两者不同误判为打包损坏。

## 来源脚本仍需补强的边界

| 位置 | 现状 | 在本仓适配时的要求 |
| --- | --- | --- |
| read_v1:46 | 允许v0，但v1_id总计recovery零长度，verify又强制v1 | 限定v1，或真正分开实现/验证版本；拒绝在写出后才发现版本不支持 |
| read_v1:39-76 | 切片未严格核对分段边界、完整长度、recovery字段 | 明确拒绝截断/非零second或recovery/未知尾部，或完整实现并更新所有offset |
| split_kernel_field:79-88 | 只检查尾部FDT magic，允许空DTB，未检gzip eof/完整FDT总长 | 对拟使用模板钉hash，严格核对压缩结束与完整DTB边界，保留来源元数据 |
| build:107-128 | 保留旧shim，未核对新旧FD等长和shim image_size/拷贝量 | 当前两FD均3MiB且shim一致可作为事实；大小变化时必须重编/重新审计shim，不能静默继承 |
| main:163-169 | 把FD偏移0x28与ARM64 magic比较 | FD该处应是FV签名_FVH；ARM64 magic在外部shim偏移56。应用已有FV/FFS检查器，不用这条警告判固件 |
| verify:131-151 | 不检ID、完整header保留、shim/DTB一致、完整总长/填充等 | 采用独立重解析及hash校验，不把同一构建过程重跑当独立验证 |
| main:176-180 | 先写--out再verify，无输出边界或覆盖保护 | 本仓只写out独立新目录，核对通过后输出，拒绝覆盖模板/只读来源 |

源脚本一般性输入边界未充分，并不推翻本轮对固定r6无second/recovery输入的字节核对结果；两者分别记录。

## 对主线的处理

保留“已知模板参数+严格分段重算+独立回验”的方法，以及32B ID/分段SHA规则。当前已有v4固件入口候选，继续以实际ABL/SEC/DXE结果判断，不因参考几个失败样本提前宣布v4不可用。若需要v1对照，先准备本仓控制的安全配置/负载并审查initrd映射保留，不原样携带参考旧内核和6GiB ADT；未知板值不编造，board/feed保持。

本轮属于源码与静态检查，没有设备动作，没有新镜像或_verified修改；参考仓原件未动。
