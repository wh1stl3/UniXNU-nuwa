# Owner BNCH：固定 prepared-kernel 主机 payload 包装

2026-11-11，**wrapper主机静态审查及独立机械验证已获主控接受；本次文档更新self-checked，不放行设备**。
后续显式冻结diagnostic profile（仅`6671…`/55386112B）的新增实现、schema2绑定与布局见
[诊断离线包装检查点](owner-pmap-ret-package-20261111.md)，仅self-checked待独立复核；
下文“新hash消费未完成/尚未交付”属于该后续检查点之前的记录，不批准其他新hash。
当前冻结profile及官方外层、最终静态范围的独立主机验收已获主控接受，见
[外层最终记录](owner-vendor-boot-20261111.md)及[范围更正链](owner-pmap-ret-range-acceptance-20261111.md)。
主机候选验收完毕不等于设备实测；当前无设备授权，待当轮授权及身份/槽位门禁，EFI map/GOP条件保留。
依据主控转述 reviewer `ses_e39826988ffesahapCtE5ov1rB` 批准的窄 wrapper。
设备 HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a` 上未提交实现，保留既有混合差分。
已重读 context-brief/治理/AGENTS；无设备、bootimg、native kernel 修改、commit/push。
另一 reviewer 的原生 return-stop 位点不属本实现，未来 probe 新 hash 未获本包装批准。

## 接口与隔离

- `scripts/owner_payload.py`：固定基座 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`。
  每文件同次读取 bytes 核对脚本内完整 SHA256 pin 与该 revision Git blob（仅允许 checkout
  CRLF/LF差异参与 blob比较，原始 SHA 仍严格），同 bytes parse/compile。
  明确加载顺序：util → config → profiles → feeds → components → ipsw → patches → kernel
  → devicetree → payload。完整 pin 表随代码及每份 payload-record.json 保存。
- 每次新 `_nuwa_owner_payload_<uuid>` package，空 `__path__`，显式注册子模块/包属性、
  `__package__` 和基座真实 `__file__`；所有相对导入限该闭包。标准库正常导入；
  不改 sys.path/import hook/正式模块，退出清理私有登记。UUID仅命名隔离，不是BNCH。
- 唯一 AST 差分：payload.build format2 中 `write_bytes(generate(dtb, ctx.board, ...))`
  的 callee 改 `_owner_generate`。精确核对整个 format2分支、两个位置参数、五关键词、
  write_bytes结构、唯一调用数；逆变换整 AST 相同。`compile_hardware(ctx)` 真实执行。
- bridge 恰好一次调用原已审 `owner_bnch.generate_candidate`，实际新 DTB/完整运行态 board/
  identity/五关键词传入候选 `adt-generation/`，返回本次 final.adt bytes；不复制历史旁置ADT，
  不替换 owner generator 的隔离 devicetree。禁用无实验token/record；启用/显式复用沿用已审语义。
- `build-owner-payload.py` 是设备显式主机入口，默认禁用BNCH，显式开关才启用；
  不是修改基座默认CLI或正式board。本次接通的是这个显式 wrapper 内的正式 payload.build。

## Context 与文件边界

新 ignored 候选根独占预留，拒已有、越界、`..`、symlink/junction/reparse ancestry。
WSL的 `/mnt/<drive>` 路径除 lstat 外，调用现有 powershell.exe 只读检查 Windows
祖先 ReparsePoint；检查工具不可用/失败即拒绝，不把 Linux symlink 检查冒称全标签覆盖。
所有 work/logs/stage/输入快照/FAT回读均在候选根；失败保留，不重入/覆盖。

使用真实私有 Context(args)，显式字段在 namespace() 列全：
config指向候选 `[build]` 空受控TOML，out=候选/build，device=本设备仓，os固定20H392，
command=status（不dispatch），jobs=1，local_module仅核验的 sm8550；local及五local-kind=None，
target=DEBUG，kernel=None（build显式传 prepared），kernel_arg=[]，trust/data/addon显式输入，
owner_trust_cache=None、skip_setup=False、unique_chip_id=显式JSON非零u64、uefi=None。
因此不隐读基座 unixnu.local.toml，不从环境默取identity；实际 namespace字段、
effective device/schema/name/os/config/profile_roots/work及配置输入hash在包装记录中保存。
SoC固定 `a9f45dc60c035084b95463781538380f4c3606c9`，核对本地path/HEAD及soc.toml/dts工作字节与blob。
Context command=status且显式本地SoC，禁fetch/组装tree/保存state；logs预建。
不伪造.config，保留 check_data_input 从真实 nuwa_defconfig 回退的原语义。

深拷贝运行态board，只覆盖payload.panic_screen=false、entry_probe_reset_delay=0，
记录原值/新值，正式board不改。当前窄范围拒install/非firmware-loader/skip_setup/native-root路径。
以 `build(ctx, kernel=prepared_path)` 调用；首次stage/image/report须不存在。
只接受当前已批准prepared kernel SHA256
`fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`、55357440B。
即使将来原生probe获批，也须另更新审查/输入约束；不放宽旧initializer checker的固定kernel门禁。

## 真正的 FAT 回读门禁

build成功后，mcopy从实际image提取EFI树；严格检查member集合、kernel逐字节等于prepared、
ADT逐字节等于本次bridge输出/owner记录、唯一BNCH或默认无BNCH、AMNM u32=0、无CHMH。
实际trust/data/addon/root-policy存在时全部提取并按实际输入字节及hash绑定；
unixnu.toml用tomllib解析核对所有header/menu/args/path/initrd引用，配置引用的文件须存在。
核对正式payload.json与实际kernel/ADT/payload/可选输入；readback全部完成且私有模块清理后
才写独立payload-record.json成功状态。owner记录中的原KERNEL_SHA只是既有绑定，
包装另存实际prepared hash，不将其当新probe hash。

## 本轮产物（ignored，本地主机用途）

根：`out/owner-payload-20261111-final/`。

| 产物 | 路径 / 绑定 |
|---|---|
| payload | `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864B |
| payload SHA256 | `de5a6df54b9131a93d7eb1ee3c795a057e513b67562a3ab0e7d22b23c6a0682a` |
| ADT | `adt-generation/final.adt`，SHA256 `22a54f62234f333c241ea76df32e15f4162901e8517d3d8d17c08abd6790c849` |
| owner记录 | `adt-generation/record.json`，SHA256 `80184cb288c5a7ef33f320a066febbda65cb1ebd56674bea093392004c71abee` |
| 包装记录 | `payload-record.json`：bridge_calls=1/readback_complete=true/device_release=false |
| 回读/命令 | `extracted/EFI/UniXNU/`、`extract-command.json` |
| 输入/覆盖 | `inputs/`、`runtime-board.json`、`overrides.json`、`build-input.toml` |

token及identity原值只在ignored输入/owner记录，不输出到本说明。最终CLI显式复用本次r2
enabled记录，未抽新token。正式payload打印的“next: run ./unixnu bootimg”只是固定提示，未执行。

## 已实际运行的自检（全部 self-checked）

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；WSL子命令 cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，Python3.11、现有dtc/mtools/PowerShell，无安装/下载。

```powershell
# 最终版本5项增量测试，实际exit0，45.215s。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-payload.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --identity-keywords out/owner-bnch-verifier-final-20261111/keywords.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --output out/owner-payload-20261111-selfcheck-r2

# 最终主机包装，实际exit0；固定prepared kernel，显式复用本次记录。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-payload.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --kernel-sha256 fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd --identity-file out/owner-payload-20261111-selfcheck-r2/explicit-identity.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --output out/owner-payload-20261111-final --enable-owner-bnch --reuse-record out/owner-payload-20261111-selfcheck-r2/enabled/adt-generation/record.json
```

r2 `tests.json`：5/0errors/0failures。覆盖依赖/AST漂移、缺失闭包、无正式模块/sys.path污染/
退出清理、真实DTB/FAT、旧out/越界/symlink/Windows junction拒绝、固定kernel约束；
同runtime board/DTB/identity/五关键词的正式/禁用/启用保序比较（仅random-seed256及BNCH）；
DTB/config/identity/kwargs复用错配、实际identity错配构建失败无新owner目录/抽取，保留failure记录；
真实FAT mdel缺件、mcopy换kernel、损坏boot sector均拒绝（`fat-negative-checks.json`）。
测试专用只读函数profile观察不改任何模块/RNG/import hook，
`observed-build-calls.json`记录compile_hardware/write_volume实际执行，
fetch/skip_setup_seed/_save_state及kernel/patches/ipsw函数未执行；util命令仅dtc/mformat/mcopy，
无patch/seal命令。r1为早期同类5项通过证据，保留不覆盖，最终以r2为准。
未重跑旧BNCH11项/26矩阵/genericledger，也未运行native initializer或修改kernel。

收尾对新3脚本语法编译、porting-record及diff检查实际均exit0（record为14区域）；
不重跑包装。编译产物仅写新ignored out子目录，命令如下（同cwd）：

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -c "import py_compile; from pathlib import Path; out=Path('out/owner-payload-20261111-board-integration/pyc'); out.mkdir(); files=['owner_payload.py','build-owner-payload.py','test-owner-payload.py']; [py_compile.compile('scripts/'+f,cfile=str(out/(f+'.pyc')),doraise=True) for f in files]; print('3 new scripts syntax compiled inside ignored out')"
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
git diff --check
```

新文件另用 `git diff --no-index --check -- NUL <file>` 核对，返回1/零输出是新文件差异码。
保留所有旧输出，不把包装通过称初始化、认证、runtime或设备放行。
下一步独立review/verifier由主控派；native return-stop/新kernel及上机授权另审。

## 包装冻结后的 observer board 接线（同轮追加授权）

本次wrapper实际验证及最终CLI产物冻结后，主控授权本writer唯一追加board。
主控交付 observer 组件已有独立review/verifier结果；这里不修改其实现，也不运行native/prelink。
`docs/pmap-ret-observer-link-20261111.md:81–89` 的确切hunk已应用：

```diff
   "component:ArmCpu",
+  "build-nuwa-pmap-ret-observer.py",
 ]
```

完整既有4项archive保持原序，新增第5项；默认 `nuwa_defconfig` 不变。
observer只由新 `nuwa_pmap_ret_defconfig` 开关/链接flags启用，正常默认仍关闭。
`out/owner-payload-20261111-board-integration/board-before.toml` 保存追加前原始字节，
同目录 `frozen-wrapper.json` 将其hash与上表旧payload/ADT/记录绑定。
最终包装中的runtime-board、profile_file_hashes及owner记录都属于**追加前**输入；
新board的完整保序配置内容变化，即使ADT语义未变，也不允许悄然复用旧owner记录。
此次没有为这一记录变化重包；旧payload仍是固定prepared kernel、追加前配置的有效主机证据。

实际正常禁用检查（cwd同上，exit0）：

```powershell
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B out/owner-payload-20261111-board-integration/check-normal.py --output out/owner-payload-20261111-board-normal-check
```

该本地检查仅创建status Context，使用固定正式parse_config/resolve_path和已读
cli.cmd_defconfig:120–130的fragment+defconfig拼接顺序计算effective正常配置，
不伪造wrapper的.config、不dispatch defconfig/tree/build。
`out/owner-payload-20261111-board-normal-check/normal-disabled.json` 记录：
只发生archive append，default_defconfig=nuwa_defconfig，effective observer/link flags禁用；
真实builder子进程exit0且输出disabled，在传入不存在tree/clang/libtool时不创建任何输出；
专用诊断配置switch/flags存在；以新runtime配置核验旧owner记录实际拒绝
`Record actual input binding mismatch`，无新token或包装。
子进程完整argv/cwd/exit/stdout/stderr和前后board hash均在此JSON，未重新编译组件。

### 上一检查点的独立复核/诊断配置计划（未由本任务执行，当前进展见末节）

verifier运行上述增量测试时必须新建 `out/owner-payload-verifier-20261111`，
这会明确使用**追加后新board**产生新的测试record。若需新包装，CLI使用新输出
`out/owner-payload-verifier-final-20261111`，identity指向该新测试根explicit-identity.json，
reuse-record指向该新测试根enabled/adt-generation/record.json，不能沿用上表旧最终record。
旧冻结包装可直接复核hash/输入快照/实际FAT，不为改记录而重包。
本地normal-disabled脚本可用另一个新ignored输出独立复跑；不覆盖现有证据。

按已读官方 cli.py:16–26,54–55,111–134 / config.py:149–164接口，下一独立诊断out
建议 `/root/nuwa-pmap-ret-native-20261111`，预先确认全新。以下只是下一步命令，
**本轮未执行，不授权native/prelink或上机**；Linux cwd为固定基座：

```sh
./unixnu defconfig nuwa_pmap_ret_defconfig -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /root/nuwa-pmap-ret-native-20261111 --config /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-payload-20261111-board-normal-check/build-input.toml --local-module soc:sm8550=/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common
./unixnu status -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /root/nuwa-pmap-ret-native-20261111 --config /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-payload-20261111-board-normal-check/build-input.toml --local-module soc:sm8550=/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common
```

不加 `--os`、不走release，避免后续命令重选per-OS默认配置；预期诊断work为
`/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret`。
tree/依赖解析/正常native relink需后续明确步骤和现有缓存核验，不自动fetch。
新诊断kernel生成后须重新绑定实际hash及final-layout/唯一RET+renderer branch审查，
当前wrapper对新hash仍拒绝；旧prepared包装绝不是新诊断候选。

## 主控接受的独立结果（2026-11-11，本次合并记录）

reviewer `ses_e39826988ffesahapCtE5ov1rB` 对wrapper三脚本及board接线最终静态
**PASS，无整改**。独立verifier结果如下；JSON内固定self-checked标签不改写，
本节独立执行结论来自主控交付，本次只读证据、不重复运行。

| 范围 | 现存证据 / 主控接受结果 |
|---|---|
| 增量5测试 | `out/owner-payload-verifier-20261111/tests.json`：5/0errors/0failures，device_commands=0；主控报告整体exit0 |
| 实际CLI/FAT回读 | `out/owner-payload-verifier-final-20261111/payload-record.json`：readback_complete=true，bridge一次；主控报告CLI exit0；`extract-command.json`实际mcopy exit0 |
| 正常禁用/旧record拒绝 | `out/owner-payload-verifier-normal-20261111/normal-disabled.json`：真实builder exit0、无输出、default_defconfig=nuwa_defconfig、旧record对新board拒绝 |

独立最终包装根 `out/owner-payload-verifier-final-20261111/`：

- `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864B，SHA256
  `cebc736cc8d5f248c7e57887dda94f904a13e0a29b4d45adb664c55235b2a5c3`。
- 提取kernel及prepared输入均为SHA256
  `fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`。
- 实际ADT SHA256 `a7141d6edc6faa755245ea6b2d96625bb0bff9230af76f5c9f0e34eb89fa73f9`；
  本次新owner记录SHA256 `ea51beab12b8bee6efabb84a3586e7e05daec0f5c83228d8b750d82f2307f7e6`。
  新record绑定**board追加后**内容SHA256
  `41b03980913af7ac42e6ee37c2790226fc60cc1f35f3f4efd266b779d2adf392`，不是悄然复用旧配置绑定。
- `payload-record.json.input_hashes` 实际member只有kernel、trustcache、ADT、unixnu.toml；
  **data/addon/root-policy并非全组合实测**。可选分支支持与已执行的固定输入验证分开表述。

命令出处（cwd均 `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`）：

- `tests.json.command`实际argv为
  `scripts/test-owner-payload.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --identity-keywords out/owner-bnch-verifier-final-20261111/keywords.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --output out/owner-payload-verifier-20261111`。
  该JSON无解释器/exit字段，整体exit0依据主控报告，不补造历史记录。
- `extract-command.json.command`为mcopy `-s -i` 指向该独立payload、`::/EFI`到其extracted目录，
  完整绝对argv/cwd/exit0在文件；payload-record本身不保存完整历史CLI argv，不倒填。
- `normal-disabled.json.command`保留Python3.11 `-B` 调builder的完整argv及
  absent-tree/effective-normal.config/disabled-output/absent-clang/absent-libtool参数，
  `exit=0`、stdout=`nuwa pmap RET observer disabled; no outputs touched`。

固定r4 loader的静态语义与独立机器来源链已另接受，见
[loader-r4绑定汇总](loader-r4-binding-20261111.md)。它不把本包装升级为新诊断候选。
当前新native/prelink/诊断最终布局**尚未交付**；observer另一任务仍推进，本次不轮询或改其树。
wrapper目前只接受旧固定prepared kernel，新hash消费能力未完成，不静默放宽。
无认证、runtime、stage5、设备通过结论。下一步接收新native/prelink交付，完成其实际
final-layout/分支绑定及独立核验，再另审新kernel消费/诊断包装和设备授权。

本次仅本说明、loader汇总及README/porting文档更新（self-checked）；
设备HEAD仍 `63769f208783769f7fa4ec5cffc14d3eba37b21a`，基座pin不变。
仅运行文档必要porting-record check、git diff --check，真实命令/cwd/exit在本轮最终报告；
不改实现/board/config/pmap-ret文档/构建树，不运行研究/测试/网络/设备，不stage/commit/push。
