# 唯一 verifier FAT → 官方 vendor_boot 外层

2026-11-11，**主控已接受外层review及独立verifier、最终静态范围PASS，主机候选验收完毕**。
本次文档/metadata变更self-checked；未设备实测，当前无设备授权，待当轮授权及身份/槽位门禁。
无设备授权、设备命令、网络、bootimg、payload生成、新BNCH、native修改或commit/push。
设备HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a` 上未提交差分，混合修改保留；
基座只读 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`。

## 已接受的输入，严格唯一选择

主控接受diagnostic profile静态review PASS WITH CONDITIONS无整改、verifier新5项及实际
CLI/FAT/relative layout PASS。本次**不使用**前轮self-checked `640830…` FAT：

| 输入 | 固定路径/绑定 |
|---|---|
| 独立verifier候选根 | `out/owner-pmap-ret-package-verifier-final-20261111/` |
| FAT | 根下 `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864B |
| FAT SHA256 | `500a639be732722ad55f135d30b60803c23eb6cb17e16ccdb5e4b41203789797` |
| ADT SHA256 | `ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736` |
| owner record | 同根 `adt-generation/record.json`，SHA256 `b0dcd72a8115bb29ae44c2458bb22a587c50a8bad7705b06d2d2f952df996c0b` |
| extracted/prepared kernel | `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`，55386112B |
| 独立布局 | `out/owner-pmap-ret-layout-verifier-20261111/layout.json`，实际candidate/ADT/kernel/r4绑定核对 |
| 独立r4 boot | `.cache/boot-stage12-v4-r4.img`，1495040B，SHA256 `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |

输入只读冻结；helper只允许该独立候选根及完整hash，不改变profile门禁，不调用owner生成算法。
record仍绑定本current board/DTB/identity/kwargs及实际kernel/profile；不抽新token。
固定r4只读hash绑定，不重建或将FAT放入boot ramdisk。

## Stock来源与真实容量门禁

官方 `scripts/unixnu/vendor_boot.py:87–158` 和 `cli.py:70–76,201–206,336–352`
已读确认；实际入口为基座cwd的官方unixnu vendor_boot，不复制生成实现。

- `.cache/stock/vendor_boot_b.img` 与a副本实际SHA256均为
  `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`，
  匹配现存 `.cache/stock/vendor_boot.json.stock_sha256` 和
  `docs/step5-firmware.md:250–255` 的nuwa本机历史stock A/B相同记录。
- 本机历史原始GPT `../.cache/device-evidence/20261107-recovery/gpt-sde.bin`：
  4096B逻辑块、header CRC/96×128B entry array CRC实际通过。
  vendor_boot_a LBA217670–242245；vendor_boot_b LBA495827–520402；
  各24576×4096=100663296B，匹配两stock文件实际长度。
  来源参考 `docs/device-evidence-2026-11-07.md`，不输出GPT GUID或设备序列号。
- 实际stock头为VNDRBOOT/v4/page4096、logical header2128、
  ramdisk30899943B/address0x01000000、DTB3885003B/address0x01f00000、
  table1×108B、bootconfig113B、vbmeta640B；header name为空。
  **空name不是机型证明**，身份依据上述nuwa捕获上下文/既有hash/GPT，不猜当前在线设备或槽位。
- 现存记录已记官方stock自身ramdisk重包byte-identical；本次不为旧测试另重包stock。
  本次新增外层容量直接以原始GPT和实际stock长度相互约束，不只依据manifest或猜96MiB。

## 实现与实际变化清单

新增 `scripts/build-owner-vendor-boot.py`，不改已有profile/owner/initializer脚本。
固定基座revision、官方unixnu/cli/vendor_boot源码SHA/blob核对；官方子进程显式
`-D`设备仓、`--out`候选context、`--config`候选受控空[build]文件、核验本地SoC、jobs1。
因此Context状态只写新设备ignored根，不隐写基座默认out，不fetch/dispatch其他build步骤。
新根拒已有/越界/链接及Windows reparse ancestry，旧产物不覆盖，失败保留。

实际外层比较不是只看vendor_boot.json：独立解析真实字节，核对全部组件及零padding。

| 项目 | stock → 新外层 |
|---|---|
| 文件/分区容量 | 100663296 → 100663296B，等于（不是小于）已有partition容量 |
| vendor ramdisk | 30899943 → 67108864B，从offset4096开始，address保持0x01000000 |
| header | 除允许的ramdisk size/address字段外整4096B相同；address实际未变，仅size变化；其余版本/地址/name/cmdline/header/table等字段保留 |
| v4 table | 单entry size改67108864、offset保持0；其余type/name/board_id字节完全相同 |
| DTB位置 | 30904320 → 67112960；内容逐字节相同 |
| table位置 | 34791424 → 71000064 |
| bootconfig位置 | 34795520 → 71004160；内容逐字节相同 |
| vbmeta位置 | 34799616 → 71008256；内容逐字节相同 |
| AVB footer | 最后64B位置固定；original_image_size/vbmeta_offset改71008256、vbmeta_size保持640，其他footer字节相同 |
| padding | 新布局各alignment/partition空隙实际全零、互不重叠，符合官方bytearray重建规则 |

DTB SHA256 `62fb9c297dbd006d5a604f42badc8415c27d24d7b6545021e2f3308df710f58f`；
bootconfig `30a78d38c8db39b1c415ebdb17939e194c8326e8af3b2a6239283a22e9096959`；
vbmeta `98775627a304d3d678830eac03652e8402911d46d3b8b8dce29fe69d610be7b8`。
保留vbmeta/签名blob及重定向footer **不是AVB认证通过**；不据此降低后续设备门禁。

## 新外层与outer→ramdisk→FAT实读

输出根 `out/owner-vendor-boot-20261111-final/`：

- `vendor_boot.img`，100663296B，SHA256
  **`a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0`**。
- 实际解析提取 `actual-vendor-ramdisk.img`，逐字节等于唯一冻结verifier FAT，SHA256 `500a639b…789797`。
- 再从这个外层提取的ramdisk运行mcopy到 `extracted/EFI/UniXNU/`，核对kernel逐字节=冻结final、
  ADT=指定ADT/owner记录、trust=冻结输入、unixnu.toml所有header/args/path/sidecar关系。
  实际FAT集合为kernel/trustcache/ADT/unixnu.toml，无未声明sidecar。
- **一个XNU entry + 三个action entries（reset/shutdown/tools），default=xnu**，不是“只有一个entry”。
  args精确 `-v serial=3 sheng-platform-stage=5`。
- runtime卷选择不由FAT内部证明：Config优先启动卷，否则首个有效卷；
  “此卷default=xnu”不等于已证明真机选中此卷，不暗示设备启动结果。
- `outer-record.json` 保存实际hash/partition/每组件对比/条目数/选择边界；
  `official-command.json` 保存官方完整command/cwd/真实exit/stdout/stderr；
  `extract-command.json` 保存外层ramdisk再次mcopy的实际命令/exit0。
  两个仅内存header/ramdisk篡改拒绝检查通过，未修改输入/新外层文件；无旧五测试/22矩阵重跑。

## 实际命令、退出及复核

Windows启动cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；helper WSL cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，Ubuntu-22.04/root。实际helper **exit0**：

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-vendor-boot.py --base /mnt/d/Code/PortingiOS/UniXNU --candidate out/owner-pmap-ret-package-verifier-final-20261111 --stock .cache/stock/vendor_boot_b.img --loader .cache/boot-stage12-v4-r4.img --layout out/owner-pmap-ret-layout-verifier-20261111/layout.json --output out/owner-vendor-boot-20261111-final
```

官方子进程cwd=`/mnt/d/Code/PortingiOS/UniXNU`，实际exit0（完整记录在JSON）：

```sh
/home/wh1stl3/.local/bin/python3.11 -B /mnt/d/Code/PortingiOS/UniXNU/unixnu vendor_boot --stock /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/stock/vendor_boot_b.img --ramdisk /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-package-verifier-final-20261111/build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img -o /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-20261111-final/vendor_boot.img -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-20261111-final/context --config /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-20261111-final/build-input.toml --local-module soc:sm8550=/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common -j 1
```

收尾仅本新增helper语法编译到ignored out、porting-record check、git diff --check，
实际均exit0（record为14区域），同设备仓cwd；不再次打包或运行范围audit：

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -c "import py_compile; from pathlib import Path; out=Path('out/owner-vendor-boot-20261111-final/pyc'); out.mkdir(); py_compile.compile('scripts/build-owner-vendor-boot.py',cfile=str(out/'build-owner-vendor-boot.pyc'),doraise=True); print('outer helper syntax compiled in ignored out')"
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
git diff --check
```

新未跟踪文件另用git diff --no-index --check检查：exit1/零输出仅代表新文件差异码。
上述外层独立复跑现已完成，证据和完整实际命令见下一节；本次不重新运行包装。

## 外层独立验收（主控接受）

review **PASS WITH CONDITIONS**，唯一整改为状态文字，未要求改变打包行为。
verifier `out/owner-vendor-boot-verifier-20261111/`：
`outer-record.json`、`official-command.json`、`extract-command.json`均已只读核对。
official/helper实际各exit0、两外层产物cmp0、实际ramdisk与唯一冻结FAT cmp0由主控交付；
official-command及extract-command中的exit0有实际JSON字段，helper外层argv/cmp退出日志未存于所读JSON，
不补造历史记录。JSON内固定self-checked标签不改写，不否定其已由独立verifier执行。

独立输出 `out/owner-vendor-boot-verifier-20261111/vendor_boot.img`：100663296B，SHA256
`a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0`，与首次外层完全相同。
实际ramdisk `500a639be732722ad55f135d30b60803c23eb6cb17e16ccdb5e4b41203789797`；
ADT `ff7d25234c1c6d3ed14e63e3e5489f26fdf65d1f7f649f20b8f6704f8b4ab736`；
kernel `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`；
stock `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`；
固定r4 `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`保持不变。

official-command.json实际完整命令，cwd `/mnt/d/Code/PortingiOS/UniXNU`，exit0：

```sh
/home/wh1stl3/.local/bin/python3.11 -B /mnt/d/Code/PortingiOS/UniXNU/unixnu vendor_boot --stock /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/stock/vendor_boot_b.img --ramdisk /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-pmap-ret-package-verifier-final-20261111/build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img -o /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-verifier-20261111/vendor_boot.img -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-verifier-20261111/context --config /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-verifier-20261111/build-input.toml --local-module soc:sm8550=/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common -j 1
```

extract-command.json实际完整命令，cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，exit0：

```sh
mcopy -s -i /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-verifier-20261111/actual-vendor-ramdisk.img ::/EFI /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-vendor-boot-verifier-20261111/extracted
```

## 范围状态，不扩大结论

最终范围已独立静态**PASS**，证据为
`out/pmap-ret-memory-ranges-verifier-20261111/correction.json`及`native-flow/result.json`；
详见[范围更正/闭合汇总](owner-pmap-ret-range-acceptance-20261111.md)。
原FAIL源于错误引用segment起点，现已撤回；原JSON和outer-record的pending文字仍保留历史，
不是当前阻塞。正确__BOOTDATA segment `[0xfffffff007ac0000,0xfffffff007b08000)`，
__data section `[0xfffffff007af0000,0xfffffff007b08000)`；相对W `[0x3cf8000,0x3d40000)`，
至Args间隔`0x6b0000`。更正边界与A getter、B先换栈/free参数、C非零PLK绕旧gap free、
D Top→avail_start/first_avail、E pmap游标递增的独立静态证据已闭合。

helper仅一处range_static_review改成稳定“本包装器不验证范围，见独立证据”措辞，
仅影响未来记录；没有重写任何历史outer-record或冻结二进制，没有重新包装或测矩阵。
主机候选验收完毕，当前无设备授权；待用户当轮授权及操作方案的设备身份/槽位等门禁。
实时W/SP/GOP未测，EFI map/GOP契约条件保留，不称runtime/认证/stage5/设备通过或已设备ready实测。
另reviewer准备操作方案；本任务不查询设备、不发起授权，最终执行/整合留主控。
