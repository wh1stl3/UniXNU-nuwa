# v22：跨页表诊断映射修复及实机 pmap 入口

2026-10-25。执行阶段沿用不commit/push；用户随后明确授权提交本轮结果，代码/证据已本地提交597baed，仍不push，不上传原始音视频。

## 验证结论

entry-probe-15镜像SHA256 `36969f945790452a9e9a7b2ba2785edd9afddda53c36106249623cf17c55144e`，内核`a8b8fc90e4b926830839f4f1a4b27bf19ae34c1736bd8f41d99724a768c74265`，58,372,096 B，47补丁；离线证据 `reports/kernel-entry-probe/2026-10-25-v22c/`。包内ADT `abb4be1929feac0382a5afbfeac8e8fbc238f37ecc2a3e798efe1fe452ba92d7`。

唯一nuwa/kalama、Android完成1/A槽与三SHA刷新通过后，单次临时启动。用户在PROBE15菜单用电源键Enter触发。照片/4.697625秒视频可见新出现的左列y480绿色`0xff00ff80`，对应`probe_pmap`（原函数入口0xfffffff0073a36c4）；这是**实机进入pmap_bootstrap**，不是pmap完成或返回。A032=4、A033=FFFFFFF00716E5F8；没有可读的异常/panic记录不等于没有后续异常。原底部菜单为背景残留，不据此断言返回UEFI。

2026-10-25 16:12:44北京时间恢复Android完成1/A槽，boot_a/vendor_boot_a/init_boot_a三SHA与试前一致；无flash/erase/改槽。证据 `reports/xnu-entry-probe-trial/2026-10-25-v22/`。原照片/音视频与FFmpeg派生物仅在out或用户原路径，不上传。

## 实现

- 在arm_vm_init中两个固定BL调用点（0xfffffff0073beb60/0xfffffff0073beb74）插钩；不钩全局set_mmu_ttb函数入口，后者也在pre-MMU且无有效栈的早期路径被调用，不能使用C钩子保存栈。一次错误候选22保留在out作为失败证据；正式22c采用调用点钩子。
- 进入TTBR1切换前，先遍历当前x0指定的新根表，核对探针8页所需L1/L2均为table、L3叶全部空。全数通过才写叶；遇占槽/错误结构不做部分修改。无需借用或分配新表页。
- 探针代码映射Normal WB/AF/inner-shareable，EL1只读可执行、EL0不可执行；独立snapshot/status、per-CPU与flag页为RW、PXN/UXN。所有地址由固定符号与运行时gVirtBase/gPhysBase求得，不猜板值。
- VBAR改为探针KVA：旧新TTBR1同时可译，避免TTBR0取消恒等映射后再跳失效的物理向量。TTBR0新根slot2为空才保留既有Device-nGnRnE framebuffer恒等块；占槽不覆盖，禁用renderer。
- 两钩子保存x9-x28/NZCV，回放BL时恢复原返回地址x30与原目标，不把BL编码原样搬移。

边界：占槽/错误结构的测试停在原切换函数入口，证明拒写及寄存器保留；**不证明该异常拓扑切换后仍能运行探针**。此修复是固定单CPU冷路径的诊断支持，不是通用pmap持久映射接口，后续pmap/console仍可能更改映射。没有增大内存声明、改变TCR或放宽认证/运行资格。

## 软件验收

42项入口/MMU；88项普通C钩子差分；18项渲染；5项真实WFE正负对照；8项稀疏夹具阶段；2项异常处理；5项ParseKernel；6地址bootstrap walk；15项绑定拒绝测试。

新增 `scripts/test-probe-transition.py` 使用加载器推导的args/ADT/topOfKernelData与既有1GiB owned RAM，在正常用例里没有主机页表补丁或跳PC。正常/占探针叶/错误L2类型/占FB槽四用例，共12断言；保存原始根/叶、寄存器、SP/NZCV、最后PC/错误。正常分支验证8页精确PA及代码RO可执行/数据RW NX，并继续实际执行pmap钩子；两次BL的x0-x30/SP/NZCV与native LR一致。

这四例在打包后用**同一份出货ADT**重跑，并重新绑定报告摘要（镜像字节未改），包验证强制ADT摘要一致。打包必须附全部四份transition报告，删检查后重封摘要仍拒。最终镜像回读通过。

复现（仓根目录；固定Python见此前记录；脚本串行）：

```powershell
python -B scripts/test-probe-transition.py --build reports/kernel-entry-probe/2026-10-25-v22c/build.json --adt out/trial-boot/xnu-entry-probe-15/kernel.macho.adt --case normal --output out/probe-v22-analysis/recheck-normal.json
# 其它case：occupied-probe / bad-topology / occupied-fb
python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-15.json
```

## 下一前线

相同出货内核的连续模型越过pmap探针后，停在`_PE_create_console+0x48`（0xfffffff0079091f8），实际读`0x3c0fc000`。出货二进制在0xfffffff0079091c4/1c8物化此地址，先调用映射函数、随后读header magic。只读参照XNU源码：`pexpert/pexpert/arm64/BCM2837.h:63`定义`PLATFORM_PANIC_LOG_PADDR=0x3c0fc000`；`pexpert/arm/pe_init.c:94-99`的check_for_panic_log使用它，PE_create_console:513调用。

首要工程判断：BCM固定panic日志区是下一处平台不匹配。实机未捕获该ELR/FAR，不能宣称唯一实机停点。源码中不定义该宏时走DT `pram`/`embedded-panic-log-size`，没有节点则自然return：优先评估迁回真实设备提供者/可选旧日志契约，而不是给nuwa捏造该物理区或把整个console初始化NOP。

下一轮先补PE_create_console入口、check_for_panic_log映射前后/首次解引用的少量可判定记录，并核对出货二进制与源构建平台契约；如做旧panic区诊断隔离，范围仅可选的旧日志恢复路径，保留新panic和真实console初始化，单独正反对照。当前设备已恢复，本轮不追加启动。

## 音视频隐私核查

`reports/media-privacy/2026-10-25/audit.json`：git fetch后可见引用的常见音视频路径为空；当前tracked为空；GitHub Releases=0、Issues=0；29个Actions制品名称为固件/内核/源码导入。ZIP内部未逐个审计，故不声称绝对没有上传或嵌入录像。新增.gitignore覆盖常见音视频扩展名。工作区修改、Git本地out证据和GitHub上传是不同状态，本轮无commit/push/附件上传。

官网复核补充：下一首选候选为上游native-dt-panic-region.patch，来源/配置边界见[官网更新复核](2026-10-25-official-porting-update.md)。该补丁尚未应用，不能把源码候选写成已修实机。
