# nuwa / iOS16 主线交接（2026-10-25，PROBE19后）

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
