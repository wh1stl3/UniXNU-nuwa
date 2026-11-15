# 冻结 PMAP RET-stop profile：离线 FAT 包装与相对布局

2026-11-11，**profile/外层/最终静态范围独立主机验收已获主控接受**；本文保留首次实现自检记录。
本次metadata/文档更新self-checked；当前无设备授权，不称已设备ready实测，不发起授权。
后续主控已接受profile静态PASS WITH CONDITIONS及独立verifier五测试/CLI/FAT/relative layout PASS。
唯一供外层消费的候选改为verifier FAT `500a639be732722ad55f135d30b60803c23eb6cb17e16ccdb5e4b41203789797`，
不是本文保留的self-checked `640830…` 包；官方vendor_boot新产物及读取期范围限定见
[外层包装检查点](owner-vendor-boot-20261111.md)。主控已接受外层独立verifier和最终静态范围PASS，
原错误__BOOTDATA引用导致的FAIL已撤回，corrected boundary及native-flow A–E闭合见
[范围汇总](owner-pmap-ret-range-acceptance-20261111.md)。主机候选验收完毕；当前无设备授权，
待当轮授权及设备身份/槽位门禁，实时W/SP/GOP未测、EFI map/GOP契约条件保留，不称设备通过。
本任务保留全部旧输入/产物，不重建外层、不改FAT/生成器/profile门禁或其他pmap-ret writer脚本。
设备HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a` 上未提交差分，基座只读
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`。
主控交付的冻结final已独立review PASS WITH CONDITIONS/verifier PASS；B→BL park的文字修正
由另一writer负责，本任务不改pmap-ret源码/说明/board/config/native/基座或任何二进制。

## 两个显式 profile，不接受用户任意hash

`build-owner-payload.py --profile` 默认 `baseline-prepared-fb1e`，仍只接受旧prepared
`fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`、55357440B。
诊断必须显式选 `pmap-ret-stop-20261111-r1` 并 `--enable-owner-bnch`，唯一接受：

`/root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho`，
55386112B，SHA256 `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`。

`pristine.macho` (`3a38…`)、`renderer-baseline.macho` (`7fd3…`)、baseline误选、
二次改写及其他hash/大小均拒绝，不因用户传`--kernel-sha256`而批准新输入。
原runtime overrides仍只有panic_screen=false/entry_probe_reset_delay=0；无二次renderer/entry patch。
私有payload依赖闭包、唯一callee AST接点及正式dtc/FAT路径保持不变，没有复制正式生成器。

## Owner记录的最小证据schema增量

仅 `owner_bnch.binding/load_record/generate_candidate` 的输入证据绑定新增可选artifact参数，
生成算法/AST/48-byte抽取流程/init均未改。旧 `KERNEL_SHA` 保持旧baseline，不改旧initializer checker。

- 旧独立调用不传artifact仍生成/read schema1（旧记录无version字段按1读），其历史baseline语义不变。
- 新wrapper两个profile都显式传actual artifact，写schema2：
  `input_binding.artifact={profile,kernel_sha256,kernel_bytes}`；
  旧字段改明确名称 `generator_validation_baseline_kernel_sha256=fb1e…`，不是本次实际kernel。
- DTB/保序current board/identity/五kwargs的内容hash仍参与exact绑定；schema2再绑定profile/实际kernel。
  schema1不能隐式升级给新wrapper，跨schema/profile/kernel/大小拒绝；新包需新记录，
  不把旧record重新标记成新kernel证据。同schema2、同全部内容时才可显式复用。
- 本最终CLI未传reuse，专属新目录/记录预留后**只抽一次48B**，不复用测试或旧artifact token。
  失败不覆盖/自动重抽。token/identity原值只留ignored文件，不写本说明。
- 包装记录明确profile/actual hash/diagnostic_only=true、new_kernel_initializer_validated=false、
  authentication=NOT REACHED/device_release=false。旧initializer checker仍拒绝新kernel；本任务未运行它。

## 新实际FAT产物（全部ignored）

根 `out/owner-pmap-ret-package-20261111-final/`：

| 项目 | 路径 / SHA256 |
|---|---|
| FAT | `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864B |
| FAT SHA256 | `640830e458b17dc1f554253d776297b34f143bb75de216802e0997a80999c877` |
| ADT | `adt-generation/final.adt`，13256B，`20ee6b95e8b089684ba537b1e05f1c9eb8ffea8a1e2abe0a6906203a31c428f3` |
| schema2 owner记录 | `adt-generation/record.json`，`e209a0c713e4e7a3bc7895ab74d96d5e277d0f0e03387428c708c456ac371f38` |
| 输入/回读/记录 | `inputs/`、`runtime-board.json`、`extracted/EFI/UniXNU/`、`extract-command.json`、`payload-record.json` |
| 独立重提取布局 | `out/owner-pmap-ret-package-20261111-final-layout/layout.json`，同目录extract-command.json/extracted |

真实mcopy回读kernel逐字节等于冻结final，ADT等于本次bridge/record，trustcache等于本次输入。
unixnu.toml唯一xnu entry/default=xnu；args精确 `-v serial=3 sheng-platform-stage=5`，无sheng-smp或额外开关。
chosen无boot-manifest-hash，manifest-properties仅name+BNCH48，无love/CHMH。
**memory-map/DeviceTree实际不存在**：固定正式generator未生成、r4只做已审四类修补，
本任务不发明该属性；BootArgs.DeviceTree按loader公式计算的地址与该属性存在性是两件事。
仅trust sidecar，无data/addon/root-policy，不把本次audit泛化成所有可选组合或所有固件所有权证明。

## 固定r4公式与可证边界

布局审计显式绑定r4镜像1495040B SHA256
`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`，读取既有独立来源链和
source-pin-correction证据；公式源码取DarwinBoot固定commit
`3c75734014cdab0acd9541e88057b7606ee7ae08` 的DarwinBoot.c，去CR的SHA256必须为
`f3815791ad63b87b11ee28118ad1f35a7d0c5258ea70b7b76eda68914fa2b8cf`。
见[固定r4绑定](loader-r4-binding-20261111.md)，本次未重新解压固件或重做原静态语义review。
最初只读定位的旧基座out/tree源码路径已不存在；审计实际使用固定component Git blob，
不依赖过期构建树路径或拿当前HEAD冒充固定源码。

MachO使用**root LC_SEGMENT_64的VM区间**，不是文件长度：
VMBase=`0xfffffff003dc8000`，VMEnd=`0xfffffff0081b7000`，span=`0x43ef000`；
比旧baseline span增加`0x8000`。Root映射包含的fileset成员由冻结输入先前审查限定，
本审计不冒称泛用MachO/loader完整校验器。

设真实分配基址为未知W。AllocateWindow给出W mod2MiB=`0x1c8000`，
因此所有16KiB/4KiB对齐可在不猜绝对W下精确重算。DarwinBoot.c:724–732：

| 项目 | 实际相对W偏移 |
|---|---:|
| Args=align(W+VMspan,16KiB) | `0x43f0000`，分配页4096B |
| Tree=Args+4096 | `0x43f1000`，ADT13256B |
| Ramdisk=align(Tree+TreeSize,4096) | `0x43f5000`，本次RamdiskBytes=0 |
| TrustCache=Ramdisk+RamdiskBytes | `0x43f5000`，66272B |
| Addon=align(TrustCache+TrustSize,16KiB) | `0x4408000`，AddonSize=0 |
| Policy=align(Addon+AddonSize,16KiB) | `0x4408000`，PolicySize=0 |
| Top/Used=align(Policy+PolicySize,16KiB)-W | `0x4408000` |

window=`0x40000000`；Used<=window−2MiB=`0x3fe00000`，各相对区间不重叠。
BootArgs VA=`0xfffffff0081b8000`、DeviceTree VA=`0xfffffff0081b9000` 可由VMBase+offset确定，
**不代表其绝对PA已观测**。报告同时记录旧VMspan在相同sidecar大小下的相对布局以便增量比较。

结合nuwa资料：内存表/历史framebuffer为UEFI stack `0xa760d000+0x40000`、
Display `0xb8000000+0x2b00000`、DXE heap `0xbab00000+0xd1c0000`；
所读MemoryMapLib.c SHA256 `677967c096b5f789fc51191a867db821da2e35b08ddf7ff746a9a868959bc13c`固定核对。
这些低区间与ADT高DRAM `0x8c0000000+0x240000000` 机械判定不相交；
**仅在实际owned window完全位于该高DRAM的条件下**，可推出本次kernel/Args/ADT/sidecars不碰这些低区间。
docs/step5-firmware.md的first-fit推论不是本artifact实际allocation证据，不能倒填W。

尚缺：本候选实际window PA、live/native bootstrap栈范围/SP及生命周期、当轮GOP framebuffer和
回收pool绝对范围/时序。固定r4的已审释放对象是文件pool而非window，但不等于证明所有native回收路径。
**2MiB guard不当作已证明的stack保留**；4KiB Args区间不重叠也不证明BootArgs ABI/runtime消费正确。
memory-map/DeviceTree缺失明确留档。故absolute_conflicts_cleared=false；这些缺口不弱化为通过。

## 实际命令/cwd/exit及复核

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；以下WSL cwd均
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`、Ubuntu-22.04/root。无下载/网络/设备/bootimg/native构建。

```powershell
# 最终新增5项增量测试，实际exit0，18.549s；不跑旧22/BNCH矩阵。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-pmap-ret-package.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --final /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho --identity-file out/owner-payload-verifier-20261111/explicit-identity.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --loader-image .cache/boot-stage12-v4-r4.img --output out/owner-pmap-ret-package-20261111-selfcheck-r2

# 本最终artifact新抽一次token、新record，实际exit0，不带reuse。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-payload.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho --kernel-sha256 6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269 --profile pmap-ret-stop-20261111-r1 --enable-owner-bnch --identity-file out/owner-payload-verifier-20261111/explicit-identity.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --output out/owner-pmap-ret-package-20261111-final

# 实际重新从该FAT提取并审计，exit0（有明确绝对地址缺口，非device PASS）。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-pmap-ret-package.py --candidate out/owner-pmap-ret-package-20261111-final --base /mnt/d/Code/PortingiOS/UniXNU --loader-image .cache/boot-stage12-v4-r4.img --output out/owner-pmap-ret-package-20261111-final-layout
```

测试报告 `out/owner-pmap-ret-package-20261111-selfcheck-r2/tests.json`，5/0errors/0failures；
覆盖显式profile/默认拒绝/错误hash/大小/pristine/renderer-baseline/二次改写、schema/跨profile/kernel旧记录、
实际旧record桥接拒绝（无新owner目录/不重抽）、诊断FAT/ADT/config、篡改image hash及重算hash后的
实际kernel换件拒绝、VMspan/对齐/边界。r1是较早增量版本，保留不覆盖，最终以r2为准。
旧baseline gate只做本新增准入断言，不重包旧artifact；旧initializer文件保持原hash且未运行。

独立verifier由主控派：上述测试output改为全新 `out/owner-pmap-ret-package-verifier-20261111`；
本固定包布局复核改为全新 `out/owner-pmap-ret-layout-verifier-20261111`；
若需重做CLI包装，使用另一个新根且明确新record/token，不覆盖本包。
本轮收尾语法/porting-record/diff检查实际各exit0（record为14区域）；语法输出仅写ignored out：

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -c "import py_compile; from pathlib import Path; out=Path('out/owner-pmap-ret-package-20261111-final-layout/pyc'); out.mkdir(); files=['owner_bnch.py','owner_payload.py','build-owner-payload.py','audit-owner-pmap-ret-package.py','test-owner-pmap-ret-package.py']; [py_compile.compile('scripts/'+f,cfile=str(out/(f+'.pyc')),doraise=True) for f in files]; print('5 scoped scripts syntax compiled in ignored out')"
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
git diff --check
```

verifier按增量复跑这些检查，pyc输出换新目录；不重建冻结native/renderer、不运行设备。
最终vendor_boot外层统一另行安排，本轮不实现/执行。
