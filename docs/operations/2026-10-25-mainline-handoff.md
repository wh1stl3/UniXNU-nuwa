# nuwa / iOS16 主线交接（2026-10-25，PROBE19后）

> PROBE24照片683cc91b已保留本地，A02D/E仍未知哨兵、A02F=0，未证明激活/签名/任务切换或用户态成功；完整格点及exec返回码尚待逐项注册核对。用户已回fastboot，固定原厂临时boot恢复完成；后验2026-10-25T14:25:22.341342+00:00确认Android1/A槽/三SHA与试前一致，无待恢复，不重复启动24。代码7269f20、启动1b4fe71；本轮证据v32b/screen、recovery、postcondition.json。下一项分析真实exec停点，不按成功阶段停止，不放行未审阅恢复服务。


> 实时：PROBE24于2026-10-25 22:21:36 +08已仅一次临时boot ACK，代码7269f20；等待菜单电源Enter后完整画面，重点最右侧220至239及A02D/E/F/A030/A032。ACK不是内核执行证据，不重复启动，尚无本轮恢复后验。镜像eed726b2，预检Android1/A槽/三SHA一致，用户本包录像恢复就绪。取图后trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-24.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v32b/recovery.json；随后record-nuwa-trial-state.py --before reports/xnu-entry-probe-trial/2026-10-25-v32b/preflight.json --output reports/xnu-entry-probe-trial/2026-10-25-v32b/postcondition.json。人工恢复等待继续离线分析，不启动第二候选。证据v32b/launch.json；下方启动前快照为历史。


> 当前PROBE24已离线完成，尚未启动；用户本轮录像/恢复就绪，22:19:42 +08预检Android1/A槽/三SHA与v31后验一致。连续真实exec/激活/签名/错误回退，只有真实故障或已提交恢复任务FINAL_WAIT释放边界才停；239品红/A02B239不等于exec成功。镜像eed726b2406e4809196aefd03ee91a166bd0fbbde3eb749cc0dc25d83fcd935e，204484608B；内核e8032e02，ADT3196efde。21项串行验证、独立逐字节重建、实际FAT回读及旧包23复验通过，代码父a785eed，无push/新CI。最近实际设备预检Android1，无待恢复，最近内核实测仍PROBE23到首次exec前。下方旧实时状态是历史快照，以STATUS及本段为准。续接：trial-v4-firmware.py launch --package reports/xnu-first-entry/entry-probe-24.json --preflight reports/xnu-entry-probe-trial/2026-10-25-v32b/preflight.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v32b/launch.json --observation-seconds 0；仅一次临时boot。取图后同驱动recover绑定包24，补Android1/A槽/三SHA，不把ACK当内核证据；日志或恢复条件失效先按AGENTS §3停在启动前。详见2026-10-25-v32-native-exec.md。


> **当前PROBE23已实机到首次init exec前，21:50:51 +08 Android1/A槽/三SHA一致，恢复关闭。** 原图624b4cda仅本地，110/111 bsd_init返回、168/169安全根调用返回、174/175 devfs、176/177 bootstrap均亮，214–216黄、217蓝/218品红，A02B217；未执行___mac_execve/Mach-O/AMFI或用户态，不将调用返回提升为Apple可信根验证。证据v31/{screen,recovery,postcondition}.json，代码91175af/启动d644d7a。用户最新“之后都要连续推进”已写AGENTS：诊断只记录继续、成功不主动停、不机械每轮后移终点；只在真实故障/明确硬停/未授权设备写入边界停，已有日志恢复条件有效直接继续。下一项真实exec/激活/签名/任务释放，原生exec_activate_image不可回退失败也可能返回0，须核对实际语义。无需重复启动23；旧未取图/待恢复是历史，STATUS与v31实测段为准。

> **实时状态：PROBE23于2026-10-25 21:47:10 +08仅一次临时boot ACK，待用户菜单电源Enter后最终画面，本轮恢复后验未取得。** 代码91175af，镜像7e24257b，用户本包录像/恢复已确认，新鲜Android1/A槽/三SHA与v30后验相同。挂载点不停止，继续原生安全根/BSD/PID1准备；214–217为新点、218品红为唯一首次exec前终点、A02B217。未取画面不声称任何新阶段成功，不启动第二候选。取图后trial-v4-firmware.py recover绑定包23、输出v31/recovery.json，再对比v31/preflight补postcondition；人工恢复等待不阻断离线工作。证据v31/launch.json与[v31记录](2026-10-25-v31-continuous-bsd.md)。

> **v31 / PROBE23连续推进版离线完成，准备单次临时boot。** 按用户要求取消挂载后停止，累计记录并连续执行安全根/BSD收尾/PID1准备，唯一终点在0xfffffff00769d5f4首次___mac_execve前；214–217为新入口/调用点、218品红为终点、A02B217。镜像7e24257b/204,484,608B，内核2e1f5d4a、ADT531c915c、APFS d180c38d；21项串行任务/872差分等、独立重建、实际四文件回读及旧包22复验通过。用户“PROBE23录像与恢复仍就绪，继续”，新鲜preflight Android1/A槽/三SHA与v30后验一致。最近实机仍PROBE22挂载返回0、21:30:50恢复闭环；尚无23安全根/首进程/用户态结果。父7057d1d，输入/命令见[v31记录](2026-10-25-v31-continuous-bsd.md)。

> **当前：PROBE22实机真实RAMDisk/md0→原生根挂载返回0，21:30:50 +08 Android1/A槽/三SHA一致，恢复关闭。** 原图fc1c4ade本地，196/197、204/205、206/207、164/165、166/167均亮，入口8黄、A0350/212绿；213错误与9用户态未到。未直接读回FS名称/root vnode/整盘哈希，不宣称iOS已启动。证据v30/{screen,recovery,postcondition}.json，代码fb76965/启动b6a80c1。用户最新要求减少阶段停止、一次推进更多：下一候选取消挂载后终点，保留累计标记，推进安全根/BSD收尾/首进程准备，唯一边界放在首次执行恢复用户态之前。无需重复启动22；旧ACK/待图/待恢复仅历史。详见STATUS与v30记录。

> **实时状态：PROBE22于2026-10-25 21:26:08 +08单次临时boot ACK，等待用户菜单电源Enter后停止画面。** 代码fb76965，镜像1b24ff82，preflight确认Android1/A槽/三SHA与v29后验相同，用户最新授权原文保留。ACK不能证明192MiB运输/实际APFS装载/root挂载；本轮Android后验尚未取得，不启动第二候选。截图重点为菜单PROBE22、root点、A035与212/213；取图后运行trial-v4-firmware.py recover绑定reports/xnu-first-entry/entry-probe-22.json，输出v30/recovery.json，再对比v30/preflight补postcondition。人工恢复不阻断离线工作。证据v30/launch.json，完整输入见[v30记录](2026-10-25-v30-real-apfs-mount.md)。

> **v30 / PROBE22已离线完成，准备一次新的临时boot，尚无本包实机结果。** 镜像1b24ff82/204,484,608B，内核7f699af6、ADT15cf608b、真实APFS d180c38d；192MiB FAT实载内核/根镜像，-v rd=md0，原生挂载返回后A035真实返回码、212绿/213红并停止，不进入恢复镜像用户态。21项串行任务含856差分/25Image4/6pthread/3停止/7根输入/34绑定通过，独立重建、实际四文件回读、旧包21复验通过。新鲜v30/preflight Android1/A槽/三SHA与v29后验一致，按用户“继续新的临时启动 先不管这个重启”推进，不再调查重启原因。上一轮21:13:15后验恢复已完成。现有内存/身份/_verified保持，192MiB运输和实际APFS挂载尚待实机。权威包reports/xnu-first-entry/entry-probe-22.json，完整命令/SHA见[v30记录](2026-10-25-v30-real-apfs-mount.md)；代码父cd21655，无push/新CI。

> **当前实测及用户指令更新：PROBE21照片b412ba53确认184/185初始IOBSD资源等待已返回，208–211默认Apple_HFS IOMedia匹配构造已达，200蓝/201暗定位介质匹配等待；挂载入口8暗。** 196/198调用暗、197/199绿由原生其他前驱直达后继解释，不当作RAMDisk创建/等待调用返回。第一次恢复监测超时保留，用户确认fastboot后21:10:06只临时加载一次固定原厂boot，21:12:18观察Android1，21:13:15 +08 postcondition确认A槽/三SHA与本轮preflight相同，恢复关闭。证据v29/{screen,recovery,recovery-retry,postcondition}.json。用户最新“继续新的临时启动 先不管这个重启”优先执行：暂停重启归因，继续PROBE22真实APFS RAMDisk挂载后停止候选；尚未离线完成/尚未新启动，不把主机APFS检查写成实机挂载。内存/身份/_verified边界与日志/恢复门保持；旧等待照片/未恢复段落是历史。

> **设备实时状态：PROBE21已于2026-10-25 21:03:14 +08单次临时boot ACK，待用户菜单电源Enter后的root内部标记照片。** 代码7faf565，本轮preflight录像/恢复门已确认，Android1/A槽/三SHA与v28后验相同。当前不能确认内核新阶段，本轮Android恢复后验尚无，不启动第二候选。图像采集后执行 `trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-21.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v29/recovery.json`，再record-nuwa-trial-state.py对比v29/preflight补postcondition。ACK不代替画面，人工恢复不阻断离线工作。启动证据reports/xnu-entry-probe-trial/2026-10-25-v29/launch.json。

> **v29增量：PROBE21离线完成，用户本包录像/恢复就绪已确认，新鲜preflight Android1/A槽/三SHA与v28后验一致，即将一次临时boot。** 包21镜像f005f7ed/70,266,880B，内核dc496abe，ADTb6bb6c88；860差分/25Image4/6pthread/31绑定及独立重建、实际FAT回读通过。新增root内部30点182–211，184/185为初始IOBSD等待、200/201为介质等待。真实102MiB APFS恢复介质已只下载/主机只读检查并卸载，未塞入试包，不改变内存/身份。尚无本包实机画面/恢复后验；证据v29/build/execution/preflight，续接见[v29记录](2026-10-25-v29-root-waits.md)。无push/新CI，父6797bd5。

> **当前：PROBE20实机进入IOFindBSDRoot，pthread原生初始化返回，未到vfs_mountroot。** 照片36983517中180/181亮（已注册，备用请求跳过），160–164为IOKitBSDInit/net_init_run后继和root调用，7号root入口亮、8号挂载入口暗。A02A=0/B=6/C=1，B不随root入口更新。20:45:31 +08后验确认Android1/A槽/三SHA一致，无待恢复任务。无需再启动20；主线转真实root介质/提供者和匹配输入。7项审计确认-v、无root-matching/boot-uuid/RAMDisk，默认等待Apple_HFS IOMedia；内部具体等待位置和IRQ/计时器仍未证明。详见[v28实测段](2026-10-25-v28-pthread-to-root.md)、STATUS和v28/screen.json、recovery.json、postcondition.json、root-inputs.json。下方未取画面/未恢复为历史快照。

> 设备动作更新：2026-10-25 20:42:51 +08，PROBE20镜像365216ae单次fastboot boot ACK。本包用户录像/恢复就绪，新鲜preflight Android1/A槽/三SHA与v27后验一致。等待菜单电源Enter后的画面，不以ACK声称pthread已注册；本轮恢复后验未取得，不启动第二候选。证据v28/launch.json，代码f0f4ea6。画面取证后运行trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-20.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v28/recovery.json，随后record-nuwa-trial-state.py --before本轮preflight --output本轮postcondition。人工恢复不阻断离线工作。

> 续接增量：v28/PROBE20离线完成，镜像365216ae/70,266,880B、内核d34a5de9、独立ADT635d4f4d；正常OSKext加载helper与真实pthread选择已接入。19项串行任务全部通过（740差分/25Image4/6pthread/31绑定），独立重建一致、实际FAT回读和输入重测通过。权威包reports/xnu-first-entry/entry-probe-20.json，尚未实测；等待PROBE20当轮录像/恢复条件。命令和模型边界见[本轮记录](2026-10-25-v28-pthread-to-root.md)及reports/kernel-entry-probe/2026-10-25-v28/execution.json。设备仍以前轮20:03:58 Android后验为最近证据，不重复启动19。无push/新CI。

接手顺序：根目录AGENTS.md → docs/STATUS.md → 本文 → [v27完整操作记录](2026-10-25-v27-image4-to-bsd.md)。旧v25/v26及10月23日交接保留历史；不再把“未到BSD”“Image4仍是实机卡点”当作当前状态。

## 1. 当前实机结论

**PROBE19实机已越过MAC/Image4并进入bsd_init，停于pthread内核函数表未注册panic；root发现/挂载、用户态尚未进入。已恢复Android。**

- 照片MAC调用88及后继89亮、BSD入口6亮、root入口7/8未亮；A02A=0、A02B=6、A02C=1。完整panic匹配原生pthread_shims.c:318：`pthread kernel extension not loaded (function table is NULL). @%s:%d`。
- 用户确认本包录像/恢复条件；19:56:34北京时间刷新Android1/A槽/三SHA，19:57单次临时boot ACK，菜单电源Enter后取照。ACK本身不算内核执行。
- 第一次恢复监测超时，随后用户回Android；**20:03:58北京时间**后验确认Android完成1/A槽/三SHA与试前一致。当前无人工恢复待办，未持续轮询。保留失败recovery.json和成功recovery-retry.json，不改写失败。
- 无flash/erase/改槽、无第二试包、无push或新CI。IRQ真实递送、计时器/控制器、驱动完整性、root/用户态、长期稳定性继续未验证。

## 2. 目录与固定范围

所有命令明确在D:/Code/UniXNU-nuwa执行，聊天默认cwd可能不同。设备仓main本轮父提交df90f14；本次里程碑提交号以git log为准。origin/main未fetch，不把本地ahead计数当作远端实时状态。

D:/Code/uefi-nuwa仍为a155c495c863e06d400b515315e3b8f7791dc308；D:/Code/UniXNU-integration仍为e553e467ebfe7642e9f483d3977a57066c6d1aef。本轮未修改它们。PR100独立分支codex/pr100-linux-8796仍不自动切换、合并或替换产物。

D:/Code/PortingiOS与D:/Code/PortingiOSWithUniXNU只读，不复制整棵源码进设备仓。保持iOS16/8796、板值/TCR、内存基址/容量/窗口、IPSW身份及*_verified审阅边界，loadable=false/runtime_qualified=false。脚本、编译和测试串行；媒体仅本地。

## 3. 唯一有效试包19

权威报告reports/xnu-first-entry/entry-probe-19.json；不能把31组件pthread离线产物当作已试包。

| 对象 | 本机路径 | SHA256 / 字节数 |
| --- | --- | --- |
| 临时boot | out/trial-boot/xnu-entry-probe-19-image4/boot-xnu-first-entry.img | f1febc069f45bcf22d88c91f571e4c5fa8d84e1a7e4368c7375adf525cb787a6 / 70,266,880 |
| 探针内核 | out/kernel-entry-probe-27-image4/kernel-entry-probe.macho | f3c33194973fc6469b3bc3e4aa5f72595083ef4560c5979a860415ebec918984 / 58,413,056 |
| 最终ADT | out/image4-mainline-v27/launch/kernel.macho.adt，与包内相同 | ace998436500149856a0f41838aa8a4e3dd8dedbb6cfb716922a5baad544ec4d |
| 固定基础内核 | out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho | 1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6 |
| 内核重复构建 | out/kernel-entry-probe-27-reproduce/kernel-entry-probe.macho | 与探针逐字节一致 |

FD仍为CI40014018074固定产物2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f；BootShim仍为8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462。来源目录out/upstream-firmware-40014018074/nuwa-firmware-40014018074，未因当前源码HEAD不同重建替换。

nonce原像仅out/image4-mainline-v27/launch/nonce.bin；实际launch-manifest.json、base.adt和最终ADT保留同目录。Git报告没有nonce原像。Git也不包含内核/镜像/原始媒体，换机器只clone不能复现实测包，需单独保管这些本地依赖并核对SHA。

## 4. 软件输入与v26修正

scripts/nuwa_launch_context.py从主机OS CSPRNG新取32字节nonce，BNCH为其SHA-384。Nuwa.DiagnosticLaunch.v1规范清单绑定实际FD/shim/新内核/基础ADT及nonce hash；boot-manifest-hash为清单逐字节SHA-384。禁止混配策略为32位LE1。

这是**无签名的非Apple诊断启动测量**，不是Apple IM4M/TSS票据、硬件nonce或可信启动链；nonce按候选包存续，不提供每次开机防重放。没有用其他机型常量摘要、空字段或随机摘要冒充真实来源。原认证/MAC失败路径保留。包回读重新核对实际四项组件、ADT投影、BNCH和清单关系。

v26强制缓存切片把x19设为pmap runtime，不能据此断言真实初始化只补AMNM仍在原点失败；本轮完整原生prologue实际加载Darwin IOKit runtime。完整入口对照为：原ADT AMNM panic → 仅合法AMNM BNCH panic → 实际新输入初始化RET；实机随后已到BSD。D-048纠正D-047的完整路线判断。

dtless在后续AMNM/CHMH公开查询中仍不支持这两个标识符；新包集成两处明确provider路由，调用原生Darwin getter并保留2/84/96等错误。其他缓存/SecureDT不变。donor只有两处4字节hook变化，build.json明确列出，不能声称新包donor整段未变。

## 5. 检查、来源与读图

离线reports/kernel-entry-probe/2026-10-25-v27/以build.json为准；25项Image4完整入口/错误检查、29绑定、740差分及入口/映射/上下文/向量/同ADT四切换/console/矩形等通过。新包实际镜像回读、内核重建一致，旧包18验证仍通过。execution.json保留串行命令，verification.json补齐后续证据。

source-audit.json固定DarwinBoot d099354d、VerifiedRoot 2854c61f、sweet fdad0de8、topaz d5dfb3b6、nuwa RNG a155c495的commit及各文件SHA/许可/依赖。前两模块/RNG读取文件为BSD-2-Clause-Patent；sweet/topaz只参照合成输入模式，未复制代码或采用摘要。DarwinBoot此Boot路径没有nonce/IM4M生产器；VerifiedRoot owner签名依赖真实key anchor/镜像/crypto，不直接替代早期Apple输入；EFI RNG consumer不证明nuwa provider运行资格。

178点布局与PROBE18相同：10列，x832起、列距48、行距24，32×16块；黄入口、紫红上下文、蓝调用、绿原后继。共享分支可直接到绿点，不单凭绿色称对应调用返回。A02A为白/青校验带不符数，A02B最后检查ID，A02C原生VBAR交接；本次A02B=6配合入口与panic证明已到BSD。实际IRQ尚未证明。

旧v25中模型OSKext bzero+0x1c异常不是实机卡点，不补假RAM、跳过bzero或重走旧T0SZ/MMU路线。包18及其preflight/摘要保留原字节，不重复启动。

## 6. 下一主线：pthread真实组件与生命周期

固定donor 2ec297ba中有iOS16.7 com.apple.kec.pthread，原30组件选择漏掉它。新增audit-pthread-prelink.py先重现原1aeebf13精确baseline，再只加入pthread：31组件绑定闭合，pthread指令原字节保留。11项模型检查执行真实kmod入口与原生pthread_kext_register，原生wrapper分派到真实donor初始化入口，重复注册按原生逻辑拒绝。

离线分析内核out/pthread-prelink-v28-analysis/kernel-pthread-analysis.macho，SHA256 52227410fd5ad0da9b8487a3fc3706a8f03042cc8256cfe99018897337f47e01。仅分析，**不是试包20，不可直接boot**。报告pthread-registration.json列真实入口/表/回调地址；尚未执行pthread初始化函数体、真实OSKext生命周期、锁/hash/thread-call/sysctl依赖，也未集成有效试包。

下一步把该组件加入有效选择，通过真正OSKext启动/注册路径在BSD pthread_init之前完成初始化并验证。不得跳过NULL表检查、灌假函数表，或直接把手工kmod入口模型升格成生命周期正确。固定集成源码build-libpthread-kernel.py是Darwin23/iOS17参考，不直接套用ABI；本机iOS16源码只读位于libpthread-ios16，HEAD a6c70ca0e544347a0377babf748f831577ec24f9，当前首选复用已有iOS16 donor组件。

## 7. 直接续接命令

```powershell
Set-Location D:/Code/UniXNU-nuwa
$py = 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe'
git status -sb
git log -5 --oneline
& $py -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-19.json
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
& $py -B scripts/audit-pthread-prelink.py --work "out/pthread-replay-$stamp" --output "reports/kernel-entry-probe/2026-10-25-v27/pthread-replay-$stamp.json"
```

新内核/新ADT必须新目录构建、绑定对应候选和最终ADT、完成必要测试、封新包后实际回读；不改旧试包记录。verify-image4-entry-candidate.py用于明确选定revision27候选的串行回归，完整命令见v27 execution.json。新nonce意味着新包清单/ADT/摘要，不能只复制旧metadata。

后续设备动作需新包当轮录像/恢复条件、新鲜preflight/最近三SHA及即时通知，单次临时boot。菜单电源Enter触发，不固定等180秒；捕获后恢复Android完成1/A槽/三SHA。当前已恢复，不再启动19。

## 8. 恢复与媒体

固定原厂恢复boot只读路径D:/Code/PortingiOS/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img，SHA见下表。三分区本轮前后相同：

| 分区 | SHA256 |
| --- | --- |
| boot_a | ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31 |
| vendor_boot_a | 5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23 |
| init_boot_a | 19e95d952ded5172e8a17bd1af907a8d6b08b29734881c370961b09bbaf78f96 |

原图/视频/提取帧仅out或用户路径，不commit、上传附件或CI artifact。历史未跟踪文件与.codex-remote-attachments保留原样，不批量git add/清理，也不以.gitignore隐藏历史。新增.gitattributes仅保留本次报告/试包/preflight字节绑定，避免换行归一化破坏证据。
