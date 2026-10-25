# nuwa / iOS16 主线交接（2026-10-25）

接手顺序：仓库根目录AGENTS.md → docs/STATUS.md → 本文 → v25操作记录。本文替代2026-10-23交接文件作为当前续接入口；旧文件保留历史，不再把其中“未进入内核”“待恢复”等快照当作当前状态。

## 1. 当前结论

**PROBE18实机已运行首线程，PE_init_iokit已返回，走过中断使能调用及commpage初始化，在mac_policy_initmach内的Image4策略初始化panic。BSD/root和iOS用户态尚未进入。**

- 横纹已在本轮实机消失，Logo与白/青校验带完整。A02A=0、A02B=4、A02C=1。
- panic为AppleImage4 5.0.0的`failed to get mix-n-match policy: %d`，参数2。
- 首要缺项为`/chosen/mix-n-match-prevention-status`。保留二进制读取器与原生SecureDT读取同一出货ADT，复现返回2；5个隔离用例通过。
- **尚未选择或写入运行时策略值**，没有以空字段或绕过认证消除panic。
- 最近设备后验：2026-10-25 **18:19:42北京时间**，Android `sys.boot_completed=1`，A槽，boot_a/vendor_boot_a/init_boot_a三SHA与试前相同。当前无待人工恢复任务。这是证据时间，不是实时轮询。
- 实际硬件IRQ递送、计时器/控制器、驱动完整性、BSD/root/用户态、长期稳定性均未验证。一次使能调用返回不能证明IRQ工作。

## 2. 仓库、提交与范围

所有命令明确在`D:/Code/UniXNU-nuwa`执行，聊天默认cwd可能不是此目录。

| 对象 | 状态 |
| --- | --- |
| 设备仓main | 本文记录基准为`5fd74e414f553b3bed333d0fa6105e8376914cfc`；本文及收口核验随后单独提交 |
| `75daa59` | PROBE17密集bootstrap观察、692差分 |
| `a1fc1a4` | PROBE17实机到load_context调用前、恢复闭环 |
| `280c198` | 用户提供的通用规范合并为AGENTS第10节，原nuwa约定保留 |
| `9a5961f` | PROBE18横纹/向量修复、178点与740差分、最终包 |
| `5fd74e4` | PROBE18实机到MAC策略panic、恢复闭环及Image4审计 |
| PR100独立分支 | `codex/pr100-linux-8796`仍在`b8872cb`，不自动切换、合并或拿其产物替换当前基线 |
| 固件仓 | `D:/Code/uefi-nuwa`，HEAD `a155c495c863e06d400b515315e3b8f7791dc308`，交接核对时工作区干净 |
| 集成源码 | `D:/Code/UniXNU-integration`，HEAD `e553e467ebfe7642e9f483d3977a57066c6d1aef`，工作区干净 |

未push，未触发新CI。本地origin/main缓存相对记录基准落后51提交，未fetch；交接提交后的计数用`git status -sb`重查，不代表远端实时状态。用户要求本地收口，没有授权本轮发布。

`D:/Code/PortingiOS`和`D:/Code/PortingiOSWithUniXNU`只读。上游源码不复制入设备仓。编译、测试脚本串行。内存/基址、既有IPSW身份边界和`*_verified=true`按AGENTS处理；保持`loadable=false/runtime_qualified=false`。没有新增Image4审批项，不把未决设计自行升级成新的全局权限门。

## 3. 唯一有效候选与本地依赖

权威包报告：`reports/xnu-first-entry/entry-probe-18.json`。不要使用未跟踪的`entry-probe-18-vectors.json`：它是打包中间报告，摘要绑定可能已过期。

| 产物 | 本机路径 | SHA256 / 字节数 |
| --- | --- | --- |
| 临时boot镜像 | `out/trial-boot/xnu-entry-probe-18-vectors/boot-xnu-first-entry.img` | `c89cfa52c165562693ab0868dddeeb1225995bb5f30e3899df58a888197e8dde` / 70,266,880 |
| 探针内核 | `out/kernel-entry-probe-25-vector2/kernel-entry-probe.macho` | `d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e` / 58,413,056 |
| 最终ADT | `out/trial-boot/xnu-entry-probe-18-vectors/kernel.macho.adt` | `9846c7dadd23bf544190c45ba3db437fb83265cb180ad6c54cd3a3fedee20d93` |
| 固定输入内核 | `out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho` | `1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6` |
| 内核重复构建 | `out/kernel-entry-probe-25-reproduce/kernel-entry-probe.macho` | 与探针内核逐字节一致 |

FD仍为固定CI40014018074产物，SHA `2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f`；BootShim为`8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462`。打包输入目录`out/upstream-firmware-40014018074/nuwa-firmware-40014018074`，不要因源码仓HEAD不同就无依据重建替换FD。

固定原厂恢复boot：`D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img`，SHA见下表boot_a。只读资料库中的这个文件只用于临时boot恢复，未flash。

| 分区 | 本轮前后相同的SHA256 |
| --- | --- |
| boot_a | `ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31` |
| vendor_boot_a | `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23` |
| init_boot_a | `19e95d952ded5172e8a17bd1af907a8d6b08b29734881c370961b09bbaf78f96` |

Python：`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`，使用`-B`；Unicorn2.1.4/Capstone/Pillow等位于`out/python-tools`。WSL为Ubuntu-22.04，已有clang/ld.lld/llvm工具及mtools；FFmpeg在`D:/ffmpeg/bin`。

原生内核来源及donor pin见`config/native-prelink-merged-analysis-profile.json`，原生CI40015845083、native SHA前缀bf14e530、donor SHA前缀2ec297ba。只读原donor路径由`scripts/native_prelink_inputs.py`定义。Git不包含这些二进制、原始媒体或out依赖；换机器需单独保管/传递本地依赖并核对SHA，仅clone不能保证可运行。当前交接核验已确认四项核心产物存在且SHA匹配。

## 4. 权威证据与读图

- 当前状态：`docs/STATUS.md`。
- 代码与完整因果：`docs/operations/2026-10-25-v25-first-thread-display.md`。
- 内核构建、软件、向量、上下文、写屏负对照：`reports/kernel-entry-probe/2026-10-25-v25/`，以`build.json`为准，不选未跟踪的中间build报告。
- Image4审计：同目录`image4-policy-audit.json`；脚本`scripts/audit-image4-boot-policy.py`。
- 实机：`reports/xnu-entry-probe-trial/2026-10-25-v25/{preflight,launch,screen,trial,recovery,postcondition}.json`。
- 本次收口：`reports/handoff/2026-10-25/verification.json`，含15项报告摘要、四项产物SHA、复验及未跟踪文件分类。

PROBE18新网格178点，10列，x832起、列距48、行距24，块32×16。黄=入口，紫红=上下文检查，蓝=调用，绿=原后继；编号按函数分组，不是时间序列。共享分支能直接到达后继，绿点不能单独证明对应调用返回。

实机81格亮：0–5入口、10/11上下文点；74/75为PE_init_iokit；80/81为中断使能调用；84–87为commpage；88为mac_policy_initmach，89未亮；6 BSD入口未亮。37和43等noreturn调用后继不亮属于预期，不按第一缺块判故障。

A02A=校验带不符像素数；A02B=最后检查ID；A02C=向量交接状态（1成功、2拒绝）。它们覆盖旧DT/SoC字段含义。A028/A029拼接panic格式前16字节，A031=首个变参值。本轮前缀`failed to get mi`匹配唯一完整格式，A031=2。

## 5. 已修复、验证与不能回退的判断

1. HEX清屏240次STP×8=1920字节，却只回退1280，造成160px/行漂移。现改1920。精确矩形正反对照证实旧包越框、新包0越框；实机横纹消失。不能再用“拍摄伪影”解释本轮问题，也不扩大为整套显示驱动已完成。
2. 旧临时向量槽先零填充124字节再分支，真实入口无法到达报告器；已改成首指令B。16槽逐一执行及旧包反例通过。早期捕获原生VBAR，在kernel_bootstrap_thread入口核对0xfffffff0073c2000并交回，避免临时报告器拦截正常线程中断；原生IRQ控制器仍未验证。
3. 740逐点差分，含GPR/SIMD/SP/NZCV/原生内存写入；10上下文/显示用例含真实初始SP等于保存帧布局；6精确矩形、5真实向量及其它回归通过。完整检查集合、命令和中间失败说明见execution.json及各报告。
4. 最终模型曾在OSKext摘要bzero+0x1c的普通STP返回UC_ERR_EXCEPTION，ESR/ELR/FAR为0；实机已走到更后面。不要为此补假RAM、跳过bzero或把它当实机故障。
5. 原生TCR保持`0x22a51a251a`。Unicorn高EL需SCR_EL3.NS|RW=0x401、HCR_EL2.RW；默认高EL状态曾选择错误执行路径。不要重新采纳“原生T0SZ=26必然冷启动失败”的旧结论或改内核参数让模拟通过。
6. 缺pram时跳过旧BCM panic日志导入的诊断桥接保留。对应源码DT panic补丁只有函数体编译/边界验证，整核配置接入尚未完成；正式源码重建和诊断二进制不是一回事。
7. 官网QR/AdvancedLogDxe/OneSend是UEFI/EBS前日志；nuwa未接入，不替代当前内核日志。Format2/共享SM8550、iOS16 ABI迁移另行固定输入评审。

## 6. 下一主线：Image4契约，先消除未知输入

实际panic来自donor `com.apple.security.AppleImage4` 5.0.0。格式串VA `0xfffffff003e20262`；原donor到prelink的slide为-0x1000000。布尔读取器为`0xfffffff0046e9fe0`，enum12选择`/chosen/mix-n-match-prevention-status`，数据读取helper为`0xfffffff0046eae28`，GOT确实绑定原生SecureDTGetProperty/LookupEntry。

| 仅用于隔离审计的输入 | errno | allow-mix-n-match |
| --- | --- | --- |
| 实际出货ADT缺属性 | 2 | 输出未写，0xA5哨兵；165不是策略值 |
| 32位小端1 | 0 | 0，禁止混配 |
| 32位小端0 | 0 | 1，允许混配 |
| 空属性 | 0 | 1，不能拿空属性修复缺项 |
| 8字节属性 | 84 | 输出未写 |

审计未修改出货文件、未选择运行时策略。它执行的是SecureDT后备路线，**IOKit runtime-provider路线尚未动态复现**；下一步先核对实际provider、节点、OSData类型/长度，再整理AMNM/CHMH及manifest/hash等依赖，形成可追溯的平台输入。最小证伪：若实际provider能读到合法属性仍返回2，就要回查provider路由/来源，不能继续归因于缺字段。

不要只补一个默认值就重复实测。`EXTERNAL_HEADERS/img4/runtime.h`说明AMNM会影响nonce和前级manifest hash约束；ios-sweet/topaz的合成boot-manifest-hash只是其它移植的兼容模式参考，不是nuwa真实前级签名manifest。当前没有建立或宣称Apple可信启动链，没有更改资格标志。

本审计脚本专用于“当前出货ADT缺属性”的负对照。新ADT已有该属性时，应扩展成旧/新双输入审计与实际provider测试，不直接放宽现有断言。新候选仍保持iOS16/8796、内存/基址/资格边界。

## 7. 可直接执行的续接命令

以下只读输入并写out，不操作设备；先验证基线，再开始修改。交接时已串行复验通过。

```powershell
Set-Location D:/Code/UniXNU-nuwa
$py = 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe'
git status --short
git log -7 --oneline
& $py -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-18.json
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py -B scripts/audit-image4-boot-policy.py --adt out/trial-boot/xnu-entry-probe-18-vectors/kernel.macho.adt --output "out/handoff-image4-$stamp.json"
```

只需要重验时不要重复整套740检查。变更代码后按影响范围重跑；新包必须绑定对应候选、最终ADT四切换场景/console及所有必需报告。流程是新目录构建→候选测试→新包/新ADT→同ADT复验→更新**新包**metadata→镜像回读。菜单标签、probe_revision、布局与包编号保持一致。**不要直接运行out下临时final_checks脚本**：其中曾误用PROBE17文件名，历史报告已恢复原字节，错误与恢复记录在execution.json。已试包18及其历史preflight/摘要不重写。

实际设备动作须另有新包录像/恢复确认，刷新本包preflight、对照最近三SHA、即时通知后单次临时boot。菜单电源键Enter触发；无180秒固定等待；ACK不算内核执行。捕获素材后恢复原厂临时boot，再确认Android1/A槽和三SHA。脚本为record-nuwa-trial-state.py与trial-v4-firmware.py，新证据目录不能复用。当前不重复启动18。

## 8. 未跟踪文件与媒体保管

本轮有效代码/审计/实测均已提交。核验快照另有42个历史/中间未跟踪文件及10个本地附件文件；分类和非媒体SHA记录在verification.json。包括旧v11/v20–v23试验、v25中间build、过期包别名、两个旧审计helper和早期跨nuwa/enuma诊断草稿。它们保留原样，不纳入当前有效证明，不批量git add、删除或改写。

原图/视频/提取帧位于`out/trial-evidence/entry-probe-17/`、`entry-probe-18/`及用户原视频路径；git只保留脱敏读数、哈希和命令。禁止上传GitHub附件、CI artifact或提交原始媒体；旧未跟踪user-screen.jpg同样保留本地。不要通过.gitignore掩盖历史文件来声称工作区全部清空。

## 9. 可复制的接手指令

> 延续D:/Code/UniXNU-nuwa，先读AGENTS.md、STATUS.md与docs/operations/2026-10-25-mainline-handoff.md。当前PROBE18已实机运行首线程、PE_init_iokit返回并到mac_policy_initmach的AppleImage4 mix-n-match policy panic(2)，已恢复Android1/A槽/三SHA。横纹与临时向量问题已修；不要重复入口/MMU/T0SZ旧路线，不把模型bzero异常当实机故障。先复验包18和Image4审计，再核对实际IOKit provider与完整启动环境/manifest契约。当前未选择运行时策略；保持板值、iOS16身份、资格与只读资料库边界，脚本串行、媒体仅本地、不push。新包验证后再取得当轮录像/恢复条件做单次临时boot。阶段日志与模型/实机证据分开，所有结果同步STATUS、WORKLOG、DECISIONS和交接。
