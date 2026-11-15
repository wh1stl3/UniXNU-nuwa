# PMAP continuation 外层 vendor_boot：主机冻结包装与回读

2026-11-11，**仅 self-checked；主机候选闭环，无设备授权、无设备命令、不 commit/push**。
复用已审 diagnostic outer 的官方 `vendor_boot` 调用、stock/GPT 校验与 outer→ramdisk→FAT 比对
（`scripts/build-owner-vendor-boot.py` 保持只读不改），新增独立 continuation wrapper
`scripts/build-owner-continuation-vendor-boot.py`，旧 diag/旧 FAT/旧 profile 明确拒绝。
未重生成 BNCH/FAT/native/renderer，未重跑旧 native/BNCH/FAT 矩阵。

## 唯一输入（独立 verifier 的 continuation 包）

`out/owner-pmap-ret-continuation-verifier-final-20261111/`，逐项绑定：

| 项 | 实际值 |
|---|---|
| FAT | `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864 B，`9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c` |
| kernel | `inputs/kernel.macho`，55386112 B，`7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4` |
| ADT | `adt-generation/final.adt`，13256 B，`885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |
| owner record | `adt-generation/record.json`，1077 B，schema2，`a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57` |
| `payload-record.json` | `fcd18fa74d2fa99bb262a1104984aacdaf539b6d9815d4b0e0e7c78883557bb9` |
| profile / args | `pmap-ret-continue-20261111-r1` / 仅 `-v serial=3` |
| continuation 证据 | diag 源 `6671…613f269`，仅 RET/observer 两处 8B 逆差分，renderer span `0x3ee5c0/2607` |

wrapper 要求 profile、`execution_mode=continue-original`、`continuation_only`、`readback_complete`
及三项 restored/unhooked/retained 标志齐全，并按 `P.CONTINUATION_SOURCE/SITES/RENDERER_SPAN`
复核记录中的 8B 逆差分；旧 diagnostic profile、旧 FAT、任意 hash/大小均拒绝。
实际 owner 记录用 `O.binding(dtb, runtime-board, keywords, artifact)` 精确复绑，未重抽 token。

## 固定输入

- stock template：`.cache/stock/vendor_boot_b.img`，100663296 B，
  `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`；
  `.cache/stock/vendor_boot_a.img` 同 hash；`.cache/stock/vendor_boot.json` 同 pin；
  GPT `vendor_boot_b` 容量 100663296 B（`.cache/device-evidence/20261107-recovery/gpt-sde.bin`）。
- 固定 r4 loader：`.cache/boot-stage12-v4-r4.img`，1495040 B，
  `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`，仅校验绑定，不重建、不嵌入。
- 独立 verifier layout：`out/owner-pmap-ret-continuation-verifier-layout-20261111/layout.json`，
  绑定同一 candidate/kernel/ADT/r4、`relative_ranges_disjoint=true`、`runtime_ret_executed=not observed`，
  `device_release=false`。

### stock template 不是当前设备备份（不静默替换）

本轮 r4 恢复所用 stock 备份 `out/pmap-ret-run-pmap-ret-20261111-r4/vendor_boot_b.stock.img`
是另一对象：100663296 B，`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`。
它与旧 template `5ad2…` 的实际差异（本轮只读核对，未改任一镜像）：

| 字段 | 旧 template 5ad2 | 当前备份 493ca |
|---|---|---|
| ramdisk size | 30899943 B | 30904915 B |
| DTB | 3885003 B，`62fb9c29…` | 3885131 B，内容不同 |
| bootconfig | 113 B | 113 B，逐字节相同 |
| vbmeta | 640 B | 640 B，内容不同 |
| footer | original_size 34799616 | original_size 34807808 |

上表只是**两个 stock 分区对象**（历史 template `5ad2…` 与本轮 r4 备份 `493ca…`）的只读比较：
二者各自内嵌不同 ramdisk，DTB/vbmeta/footer 也因此不同；它**不描述** 5ad2 模板生成新 outer 的
允许变化（后者见下节）。沿用 5ad2 与已接受 diagnostic outer 同一模板与同一打包路径，未引入新的
字段改写；**不声称该 template 等同当前设备备份**，也不擅自改用 493ca。若未来设备动作认为当前
备份 revision 更合适，属另行审查决策，本轮不扩大。

## 新输出（独占 ignored 目录）

`out/owner-continuation-vendor-boot-20261111-final/`：

| 项目 | 路径 / hash |
|---|---|
| outer | `vendor_boot.img`，100663296 B，`4a52ddbc2cc06401f76676f480eb1b0e4b1dfafce0a8d07b453dd53967a05618` |
| ramdisk 实提 | `actual-vendor-ramdisk.img`，67108864 B，`9ff5c272…e523d04c`（= 输入 FAT） |
| outer 记录 | `outer-record.json` |
| 官方命令 | `official-command.json`（exit 0）、`vendor_boot.json`（工具回执，image/stock hash 与上表一致） |
| 回读 | `extracted/EFI/UniXNU/`、`extract-command.json`（mcopy exit 0） |

官方子进程 cwd `/mnt/d/Code/PortingiOS/UniXNU`，argv 与 exit 在 `official-command.json`；
ramdisk address `0x01000000`，table count 1；outer offsets：dtb `67112960`、table `71000064`、
bootconfig `71004160`、vbmeta `71008256`（stock 对应 `30904320/34791424/34795520/34799616`）。

## 允许变化与严格保留

复用已审 `compare`（`scripts/build-owner-vendor-boot.py:83-108`，本次只读加载、未改）与
`outer-record.json` 实际核对。旧 helper 按**同目录显式加载**（`importlib` 指向
`scripts/build-owner-vendor-boot.py`），但该加载没有运行时自身 hash 拒绝；依赖版本由独立
verifier 绑定。continuation metadata 不是本层重新执行 8B 差分验证，而是复用已验固定
baseline hash `7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4`。

模板 `5ad2…` → 新 outer 的允许变化只有：

- vendor ramdisk 起点固定为 `page=4096`；header **没有可变 ramdisk offset 字段**，只有
  ramdisk size（header offset 24，4 B）变化，address 保持 `0x01000000`；header 其余字节
  等于 stock。
- v4 table 总长固定 108 B（`count=1`/`entry=108`）；entry 的 ramdisk size 变化，offset
  保持 0；type/name/board_id 等其余字节等于 stock。
- AVB footer 仅重定向字段 `footer[12:36]`（original_size、vbmeta offset、vbmeta size）变化。
- ramdisk 本体（起点 `page=4096`）逐字节等于冻结 FAT。
- 严格保留：DTB、bootconfig、vbmeta 逐字节等于 stock；header/table/footer 其余字段等于
  stock；各区段之间 padding 必须为零；outer 长度 = 分区容量。
- 结果：`header_outside_ramdisk_fields_equal=true`、`table_outside_size_offset_equal=true`、
  `footer_outside_retarget_equal=true`、`zero_padding_checked=true`、`avb_authentication_claimed=false`。
  保留 hash：DTB `62fb9c29…`、bootconfig `30a78d38…`、vbmeta `98775627…`。

## 实际全链回读

从 outer 实提 ramdisk → mcopy 提取 `EFI/UniXNU` → 与 verifier FAT 的 `fat_hashes` 完全一致：

| member | hash |
|---|---|
| `Payloads/kernel.macho` | `7fd3d933…750b6f4`（55386112 B） |
| `Payloads/kernel.macho.adt` | `885094de…586d27a4`（13256 B） |
| `Payloads/kernel.macho.trustcache` | `367e0515…e24d98e`（66272 B） |
| `unixnu.toml` | `7b2ac4be…576e931` |

`verify_extracted` 同时复核 owner schema2 record 的 artifact/profile/kernel 绑定及 BNCH48/AMNM；
menu 为 **1 个 XNU + 3 个 action，default=xnu**；XNU args 精确 `-v serial=3`，
无 `sheng-platform-stage`/`sheng-smp`/`reset`/`panic`/`entry_probe`/`native-ufs-root`。
仅 trust sidecar；volume 选择仅有有限证据，不等于唯一性证明。

## 自检命令 / cwd / exit（self-checked）

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；WSL Ubuntu-22.04/root，子命令 cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，现有 Python3.11/mtools，无安装/下载/设备命令。

```powershell
# 2 个新脚本语法编译：exit0（输出仅 ignored out/owner-continuation-vendor-boot-20261111-pyc）。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -c "import py_compile; from pathlib import Path; out=Path('out/owner-continuation-vendor-boot-20261111-pyc'); out.mkdir(); files=['build-owner-continuation-vendor-boot.py','test-owner-continuation-vendor-boot.py']; [py_compile.compile('scripts/'+f, cfile=str(out/(f+'.pyc')), doraise=True) for f in files]; print('2 scripts syntax compiled in ignored out')"

# 外层包装：exit0；仅调用已审官方 vendor_boot，无 native/FAT/BNCH 生成。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-continuation-vendor-boot.py --base /mnt/d/Code/PortingiOS/UniXNU --candidate out/owner-pmap-ret-continuation-verifier-final-20261111 --stock .cache/stock/vendor_boot_b.img --loader .cache/boot-stage12-v4-r4.img --layout out/owner-pmap-ret-continuation-verifier-layout-20261111/layout.json --output out/owner-continuation-vendor-boot-20261111-final

# 最小增量 4 项：exit0，4/0 errors/0 failures，9.293s，device_commands=0。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-continuation-vendor-boot.py --base /mnt/d/Code/PortingiOS/UniXNU --candidate out/owner-pmap-ret-continuation-verifier-final-20261111 --stock .cache/stock/vendor_boot_b.img --loader .cache/boot-stage12-v4-r4.img --layout out/owner-pmap-ret-continuation-verifier-layout-20261111/layout.json --built out/owner-continuation-vendor-boot-20261111-final --output out/owner-continuation-vendor-boot-20261111-selfcheck-r1
```

测试覆盖：旧 profile/错误 execution_mode/非 host record、错误 FAT hash/大小、额外 stage/smp/reset/
panic/entry_probe/native-ufs-root args、错误 continuation 证据、错误 candidate 路径拒绝；
outer 的 header（ramdisk 字段外）、table（size/offset 外）、DTB、bootconfig、vbmeta、footer
（retarget 外）、padding、ramdisk 逐项单字节篡改均拒绝；输入绑定/stock 区分/全链回读与
entry/args/manifest 标志复核。build 自身另做 header/ramdisk 两项篡改拒绝并记录。

## 边界与剩余步骤

- **认证未验证**（`auth_verified=false`、`authentication=NOT REACHED`）；
  AVB footer 仅结构保留，不声称通过校验。`runtime_volume_selection_proven=false`。
- 冻结包**不依赖真实 RET 已执行**假设；`runtime_ret_executed=not observed`，
  不声称 runtime 映射/PMAP 返回/显示里程碑。EFI map/GOP 契约条件保留。
- 本包**无执行器**：`scripts/run-pmap-ret-once.py` 未改；旧 r4 `fastboot boot` claim
  已消耗、不可复用；无设备授权、无设备写入/上机，`device_release=false`。
- 剩余：独立 verifier 复核本 outer（脚本/CLI/4 测试/hash/回读），再由主控决定未来
  continuation 专用执行器增量与设备授权；本轮目标是主机候选闭环，不是自动上机。
