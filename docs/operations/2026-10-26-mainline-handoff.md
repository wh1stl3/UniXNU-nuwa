# nuwa / iOS16 主线交接（2026-10-26，PROBE28离线就绪）


本轮确认补充（2026-10-26T04:08:25.950811+00:00）：用户答复“能，已准备拍摄和按键恢复”；R-014当轮画面及按键恢复条件已满足。新preflight确认nuwa/kalama、Android1/_a/三SHA与v35一致，按既定范围单次临时启动同一PROBE28；不能重用本次已发送候选。待画面与恢复后验，不声称内核通过。

## 当前唯一现场结论：PROBE28完成读图与恢复

PROBE28/7a04626e已单次实测并consumed，禁止重发，未启动下一候选。原图A034=0x110/272、A035全F；266/268/270/272青、269绿，267/271/273未亮，swap274/275未亮。确定MAC已成对返回、到达VNOP_READ原生BLR x8调用点，未观察返回。272在BLR之前记录，目标函数体入口尚未直接证实；优先核对分派目标/入口与APFS/decmpfs读取等待。原先“已进入回调”的聊天表述已收紧，不能当作入口证明，也不能指定锁/IRQ为根因。

用户已提供照片并按键回fastboot，本轮先核对实际状态，再对显式nuwa执行原boot临时恢复。12:24:07上海时间postcondition确认nuwa/kalama、Android1/_a/三SHA与本轮preflight一致；当前Android恢复闭环，无人工恢复待办。R-014本轮approved A且完成，不等于未来候选免预检。没有操作enuma、没有flash/erase/改槽。证据reports/xnu-entry-probe-trial/2026-10-26-v36/{preflight,launch,consumed,screen,recovery,postcondition,evidence-binding}.json。

[完整实测记录](2026-10-26-probe28-device-result.md)。照片SHA8b25519f…，原图及Library属性只存本地out/trial-evidence/entry-probe-28/user-screen-library-complete.tar；未commit/上传原媒体。Windows/WSL读取兼容和临时源丢失后的保元数据归档均记录于evidence-binding；不能引用失效临时路径。A033本轮不作不可靠读数替换，历史EF8保留。未证明完整header/解压/Mach-O/dyld/用户态成功。

下一步仅离线审查固定v_op目标、入口与内部分解；没有构建或启动下一候选。原包/内核/ADT和全部受审门保持，下方“等待画面/恢复”“未启动/待确认”及暂停段落均为历史，当前以本节与STATUS为准。

## 当前现场：PROBE28已单次发送，等待照片后恢复

用户本轮答复“能，已准备拍摄和按键恢复”，R-014 answered A。新preflight绑定确认原文，Android1/_a/三SHA与历史v35一致。于2026-10-26T04:08:55.911780+00:00单次fastboot boot 7a04626e包，Sending/Booting均OKAY，exit0；仅证明传输接受，尚无内核画面证据。reports/xnu-entry-probe-trial/2026-10-26-v36/consumed.json已锁定该候选consumed，不能重发；launch.json保存实际命令与结果。当前设备启动后状态未知，不沿用启动前Android1；恢复尚未执行。

已通知用户在菜单电源Enter并发送完整诊断照片，先保留现场。读266..275/A034/A035后，按电源+音量下回fastboot；只对本轮明确选定nuwa用既有recover流程临时加载原boot，确认Android1/同槽/三SHA后验。所有preflight/launch/recover必须显式--serial，避免遍历查询其他设备。不得自动换包或把ACK当执行；无新媒体时保持等待，不重试候选。

下方预检待确认/设备暂停段落为前轮历史，由本节及当前STATUS覆盖。最新离线参数契约和全部包资格证据仍有效。

## 当前实测准备（2026-10-26）

用户最新明确“nuwa可以开展实测了”，解除此前设备操作暂停，范围仅既定PROBE28单次临时启动及安全恢复；没有授权无关刷写/改槽/换包。有效包7a04626e校验通过，现有仓库试验记录未发现已启动该包。

本轮新鲜只读状态：2026-10-26T04:01:35.029989+00:00，nuwa/kalama、Android完成1、_a，boot_a/vendor_boot_a/init_boot_a三SHA均与v35后验一致。证据reports/xnu-entry-probe-trial/2026-10-26-v36/state-before-confirmation.json。尚未临时启动，未消费候选；当前状态不能写为PROBE28实测通过。

USB清单存在其他设备，本轮仅按明确选中的nuwa serial执行身份/Android/槽位/三SHA读取，没有向其他设备发送查询或状态命令。给record-nuwa-trial-state.py和trial-v4-firmware.py添加--serial目标筛选，外来设备混接/所选设备缺失的3项隔离测试通过；记录中不持久化序列号。后续preflight/launch/recover均必须传本轮选定nuwa目标，不使用自动遍历其他设备的默认路径。

R-014仍缺本轮菜单Enter后的拍摄/读取与按键恢复确认；已发出只针对这两个必要条件的问题，等待答复。不是再次询问一般实测授权。条件明确后才生成带真实确认原文的新preflight；若超时先刷新Android/三SHA。候选未启动时不执行无必要恢复或回刷。下一步仍为同一PROBE28的266..275/A034/A035观测，原日志/恢复/239/verified/权限门保留。

## 最新离线里程碑：读取参数契约

本轮依据用户后续明确要求落实最小离线测试/夹具修正；旧“只分析、不实现”的轮次描述不再限制本项，设备暂停仍有效。基线19e096f，最终提交以Git最新提交为准。

完成9组flags8/4096原生与探针对照、4组实际EFI存储案例及2个负对照。交付Darwin22 ABI为memSizeActual/0x2d8，修正transition夹具旧0x478后从入口重验normal，5项通过到_kernel_bootstrap。原生初始化定位块写shift12，header指令据此构造4096/flags8；bootstrap TG0/TG1独立解码，16KiB仅负对照，未实机验证运行时值。短读首次错误EIO预期失败及修正理由已留档。新旧transition完整快照除ABI元数据还有5处变化，未宣称跨次字节一致；最终映射和5项验收相同。

原默认11组输出逐字节相同；原23份绑定报告、权威包报告、包/内核/ADT SHA重核保持；没有重建或替换有效PROBE28，没有重复全套24项。证据：reports/kernel-entry-probe/2026-10-26-v36-parameter-contract/contract-final.json、transition-final.json、validation.json；详见[参数契约记录](2026-10-26-read-parameter-contract.md)。本轮只改模拟/测试及文档，FD/uefi仓、板值/内存/TCR/身份/_verified和239门未动，无设备操作/推送，28项历史未跟踪保留。

本离线项完成；最早实机卡点仍为250到达/251未观察。中午有人不构成自动启动授权，当前设备状态未知。下一步仍先确认当轮画面/恢复与具体临时启动范围，再取新鲜身份/Android1/槽/三SHA，按原门禁使用有效PROBE28观察266..275/A034/A035。未获这些条件前继续暂停设备命令，不能把本轮模拟当作MAC/APFS或iOS启动成功。

## 上一轮激活审计及分析记录（历史轮次）

2026-10-26接续079488f；本轮新增11场景/12对激活上下文差分及x8/x9泄漏负对照，默认11项输出与原证据逐字节一致；原包和23份绑定报告均原字节保留。6个源码函数/5个独立原生符号的MAC/decmpfs等待地图已审计。没有重跑全套24项，没有新内核/新包或设备操作。

用户最新要求为“先离线分析下一阶段”和公开资料检索。已有检查已完成，此后不扩展新实现；设备操作全部暂停，包括adb/fastboot查询/状态变化、临时启动和刷写。本文件后面的旧设备续接命令只作后续条件核对参考，不是本轮执行许可，不能因存在命令而自动运行。R-014仍open，最后Android后验仍是历史v35，不是当前预检。

新增真实参数覆盖边界：250调用w6=8、len来自运行时PAGE_SHIFT_CONST，现有普通fixture为4KiB/flags0；磁盘初值0不是运行时证据。下一最小离线规划项为固定loader memSize→arm_init→PAGE_SHIFT→len契约，未实施参数扩展。最早未验证点仍是实际header读取；类型4表项已有不证明锁/验证/UPL/fetch返回。等待转换只在fetch错误且CONVERTING条件下进入，不能以采样未返回直接指定它。

详细结果：[激活读取审计](2026-10-26-read-active-transparency-and-waits.md)；规划/一手来源/适用边界：[下一阶段公开研究](2026-10-26-next-stage-public-research.md)；补充SHA清单reports/kernel-entry-probe/2026-10-26-v36-active-audit/audit-manifest-final.json。原PROBE28镜像7a04626e…保持，原24项、1092透明比较、38绑定、23 Git blob及内核逐字节重建结论保持；新结果不能升级为真实MAC/APFS或实机通过。无push/新CI、无原始媒体上传，28项历史未跟踪保留。

后续顺序：先参数契约分析；未来在当前设备暂停解除且当轮日志/恢复门、新鲜目标/Android1/槽位/三SHA均满足后，才考虑一次现有28观测；按最早未返边界只选一个内部调查。读取后才是Mach-O/dyld、原生任务切换/签名；239恢复用户态释放守卫保持，restore作业RunAtLoad风险与完整iOS系统根另审。本轮不执行这些规划。


## 当前唯一接续点

PROBE28/v36离线完成，尚未启动。真实主机DESKTOP-S8M2VOR，D:/Code/UniXNU-nuwa；接续父a78e7591d90f3e442608e284083bb7acee6fc5cb。当前提交见本交接所属Git提交。AGENTS、原STATUS和本日最新交接均已读，.agents/skills不存在；不联系旧会话、不触碰其他项目、不启动第二写入者。本会话没有后台构建或设备进程；工作区在本轮提交后核验。无push或新CI，远端实时状态未刷新。

24项串行检查最终通过，1092透明比较、25 Image4、15 exec边界、11读取路径、38绑定。execution.json保留修订36白名单初次失败及续跑；execution-initial.json原始快照；最终24项结果均为0。独立重建逐字节相同，新28/旧27包实际FAT回读通过；旧未配对候选被MAC拒绝负对照拒绝。证据reports/kernel-entry-probe/2026-10-26-v36/，详细指令/来源/失败分析见[本轮记录](2026-10-26-v36-read-boundaries.md)。模型未执行真实MAC策略、APFS/decmpfs或解压回调；不能称实机或QEMU通过。

## 新观测及工程判断

PROBE27原图实测仍为264黄/265绿、A02A0、A033 FFFFFFF005F48EF8（用户纠正EF8、原图复核），250亮/251暗。只证明类型4表项已存在，不能称本轮真实加载API返回0、解压成功、Mach-O/dyld或用户态到达。A02E F2/242、聚合ENOENT可为之前完成尝试，不能解释本次未返回读取。原图62f86fe6…只保存在本地out/trial-evidence/entry-probe-27/user-screen.jpg；文字证据v35/screen.json，原始媒体不上传。

首要调查读取主体/APFS/decmpfs内部等待，次要MAC读取检查；新探针是最小分界，尚无新实机读数。

- 266/267：vn_rdwr调用vn_rdwr_64及返回。
- 268/269：mac_vnode_check_read调用/返回。
- 270/271：VNOP_READ调用/返回。
- 272/273：VNOP_READ中真实文件系统blr x8调用/返回。
- 274/275：原生vn_read_swapfile备用路径。

0xfffffff007466b24是VNOP_READ后继，也是MAC拒绝公共汇合点；本轮以同帧调用配对避免假返回。新格x832..1295/y784..799，保留0..265。A034=最近读取阶段；A035=实际低32返回，调用未返回全1，header开始后覆盖旧含义。每次250开始清新格和状态，251后继清active，限定TPIDR_EL1、header caller LR和真实FP，不写原生表、不跳认证/错误、无新增成功终点；既有恢复用户态释放守卫保持。异常/panic仍按真实布局解释。诊断状态只覆盖当前首进程单个active header，不宣称通用并发exec记录。

268亮269暗优先调查MAC；270亮271暗而272未到调查VNOP包装器/分派准备；272亮273暗优先调查真实文件系统回调及其APFS/decmpfs/锁/块I/O链。若更早即未到MAC则回查UIO等准备。不得把未见返回直接写成永久卡死、IRQ或具体锁已证。

## 固定产物与边界

权威包reports/xnu-first-entry/entry-probe-28.json；镜像out/trial-boot/xnu-entry-probe-28-read-boundaries-lf/boot-xnu-first-entry.img，204484608B，SHA256 7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f。内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07（58462208B）；ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0。APFS d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a（106954752B），192MiB运输，-v rd=md0。

独立重建reproduce.json。build-unpaired.json对应失败负对照dfa16e70…，不得启动或误用。PROBE27旧包06913eaf3124e2634a2c9e654f66b374ece2caf2fed790dea8b6578b0d34955d只作回归，不重复启动。

只读XNU源码固定1b191cb58250d0705d8a51287127505aa4bc0789，APSL-2.0；vfs_vnops.c SHA ea24edd5…，来源审计含链接、指令和FP几何。无新上游迁移。D:/Code/uefi-nuwa本轮不改；PortingiOS/PortingiOSWithUniXNU只读。FD2d606985…、shim8a3b5476…、板内存/TCR、iOS16/8796身份、_verified均保持，loadable/runtime_qualified=false。不flash/erase/改槽、不push/新CI、不上传原始媒体。历史28项未跟踪保留；只提交本轮相关文字/代码。

## 当前设备与R-014日志门

本轮未执行任何设备命令，实际当前状态未刷新。最后恢复证据：v35/recovery.json于2026-10-26T00:16:10.211478+08:00 Android完成1，v35/postcondition.json于00:19:12.450574+08:00确认nuwa/kalama、_a及三SHA与预检一致：

| 分区 | SHA256 |
| --- | --- |
| boot_a | ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31 |
| vendor_boot_a | 5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23 |
| init_boot_a | 19e95d952ded5172e8a17bd1af907a8d6b08b29734881c370961b09bbaf78f96 |

R-014 open，停在下一设备启动前：尚未确认本会话当轮可读/可拍菜单Enter后的具体画面和可按键恢复条件，不能把旧记录或fastboot ACK当新日志门。离线构建/核验已完成；无待恢复设备或本轮待按键动作，当前状态未知不能据此声称现在已在Android。缺条件属于AGENTS §3.2，只停止相关设备动作，不停止独立离线工作。

A：用户确认当轮拍摄/读取及按键恢复条件有效后，先用真实原文生成新鲜preflight，目标/Android1/_a/三SHA对照v35后验通过，即时通知后按既有范围单次临时boot28。B：保持设备不动，保留已验证28包，继续只读源码分析，代价是不能获得MAC/VNOP分界实测。倾向A，最小范围是本包当轮日志/恢复条件及既有单次临时启动；不扩展flash/erase/改槽、内存、身份、verified或恢复镜像自动还原。条件仍有效时不重复问。

## 可直接执行的离线续接

```powershell
Set-Location -LiteralPath D:/Code/UniXNU-nuwa
git status --short
git log -4 --oneline
Get-Content -Encoding UTF8 AGENTS.md
Get-Content -Encoding UTF8 docs/STATUS.md
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-28.json
```

不得以validate通过自动启动。R-014条件确认后，record-nuwa-trial-state.py --package reports/xnu-first-entry/entry-probe-28.json --capture-confirmation必须采用用户本轮真实原文，输出新的reports/xnu-entry-probe-trial/2026-10-26-v36/preflight.json，并与v35/postcondition.json核对。不得伪造确认。再由trial-v4-firmware.py launch --package reports/xnu-first-entry/entry-probe-28.json --preflight上述新文件 --evidence该目录launch.json执行单次临时boot；菜单就绪后由电源Enter触发，不固定等180秒、不以ACK为内核计时起点。拍具体画面并只本地保留原始媒体。

恢复沿已授权trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-28.json --evidence该目录recovery.json，结束后record-nuwa-trial-state.py --output该目录postcondition.json --before该目录preflight.json确认Android1/同槽/三SHA。人工恢复等待记录PENDING-HUMAN并继续离线修复，不在恢复/日志门缺失时启动第二候选。fastboot缺变量保留失败、重进一次再试，不伪造缺失值。上述设备流程尚未执行，不把本段命令当设备授权或实测证据。

## 最终文字证据与包版本修正

在42cf7d1之后固定JSON证据为LF，38绑定复跑、23份Git暂存blob哈希及完整绑定验证通过（git-evidence-binding.json）。权威entry-probe-28现绑定这些Git字节，最终镜像7a04626e…，首包a8cb…已退为历史且不得启动。两包差83字节，均在运输CRC/目录时间字段/未分配FAT尾簇；有效载荷相同并已回读，内核独立重建逐字节相同。空闲簇字节生成来源未进一步核对，不宣称整个运输镜像可逐字节重建。详细差异repack-difference.json，最终包回读追加post-build-validation.json。R-014仍open，没有设备动作或新鲜预检。
