> **当前续接入口已迁至[2026-10-25主线交接](2026-10-25-mainline-handoff.md)。** PROBE22实机真实RAMDisk/md0路径、原生根挂载返回0，A0350/212绿，未进入用户态。21:30:50 +08 Android1/A槽/三SHA一致，恢复关闭。用户最新要求减少阶段停止、一次推进更多；下一候选取消挂载后停止，连续推进安全根/BSD收尾/首进程准备，在首次执行恢复用户态前保留唯一明确边界。代码fb76965、启动b6a80c1，实测v30 screen/recovery/postcondition。下方均历史，STATUS、新交接和v30记录为准。

> PROBE23连续版离线完成：镜像7e24257b/204,484,608B，内核2e1f5d4a、ADT531c915c，旧挂载终点取消，仅首次init exec前保留边界。21项串行任务、872差分、重建/回读/旧包复验通过；用户本包录像恢复就绪，新鲜Android1/A槽/三SHA一致，准备一次临时boot。未有23实机结果，后续恢复绑定包23并对比v31/preflight。完整状态/SHA/命令以新交接和v31记录为准。

> v29续接：PROBE21镜像f005f7ed离线完成，用户已确认本包录像/恢复；preflight Android1/A槽/三SHA与v28后验一致，准备单次临时boot。新增root内部30点，860差分等19项串行任务通过。真实102MiB APFS恢复介质只下载/主机只读检查，未装入试包，未改内存/身份。日志门R-013已解除；新试验画面/后验未取得时不启动第二候选。命令、SHA、待办以新交接与v29记录为准。

> 21:03:14 +08更新：PROBE21单次临时boot已ACK，代码7faf565；等待用户菜单电源Enter后的画面，本轮恢复后验未取得，不启动第二候选。ACK不作内核执行结论，证据v29/launch.json。新交接含原厂恢复和postcondition续接命令，人工恢复不阻断离线工作。

> 最新：PROBE21照片b412ba53确认初始IOBSD等待返回，最终到默认Apple_HFS IOMedia等待200蓝/201暗，未挂载。21:13:15 +08后验Android1/A槽/三SHA与试前一致，恢复关闭。用户最新“继续新的临时启动 先不管这个重启”，已暂停重启调查，继续PROBE22真实APFS RAMDisk挂载后停止候选；尚未新启动。详细实测、命令记录和后续边界见STATUS、当前交接与v29/v30记录。

> PROBE22离线完成：镜像1b24ff82/204,484,608B，内核7f699af6、ADT15cf608b、真实APFS d180c38d。21项串行任务、独立重建、实际四文件回读、旧包21复验通过；新鲜Android1/A槽/三SHA预检一致。准备一次临时boot，挂载返回后停止，不进入恢复用户态；192MiB运输和APFS实机挂载尚未证明，内存/身份/_verified未改。新交接与v30记录为续接入口。

> 21:26:08 +08设备更新：PROBE22单次临时boot ACK，代码fb76965，待菜单电源Enter后的画面；本轮恢复后验未取得，不启动第二候选。ACK不证明运输/挂载，当前交接含绑定包22的原厂恢复与三SHA后验命令。人工恢复等待不阻断离线工作。

## 历史快照：PROBE18结果

> PROBE18实机进入首线程/IOKit，MAC/Image4缺项panic（2026-10-25）：镜像c89cfa52/内核d6f101e4，代码9a5961f；81格亮，PE_init_iokit已返回，中断使能调用和commpage完成相关路径，到88 mac_policy_initmach，BSD未到。横纹消失，A02A=0/B=4/C=1。panic `failed to get mix-n-match policy: %d` 参数2，已定位AppleImage4 `/chosen/mix-n-match-prevention-status`；实际读取器+当前ADT复现2，5契约用例通过。0/空属性会允许mix，32位1禁止，尚未选择运行时策略/修改ADT。下一步完整核对Image4输入与manifest/hash来源，保持可信链/板值/资格边界，不能将模型bzero停止当实机故障。
>
> 18:19:42北京时间已恢复Android1/A槽/三SHA与试前一致，无待人工恢复；实测证据reports/xnu-entry-probe-trial/2026-10-25-v25/，审计v25/image4-policy-audit.json。原始有声视频、照片和帧仅本地，无push、新CI未触发。新候选独立建包和完整离线验证后，再确认新包录像/恢复、新preflight与即时通知；不复用本轮许可。详见STATUS及2026-10-25-v25-first-thread-display.md，下方旧未启动/待恢复描述均为历史。
> **当前有效交接：v25 / PROBE18离线完成（2026-10-25）**：内核d6f101e4/58413056B/211补丁，镜像c89cfa52/70266880B，ADT9846c7da，包reports/xnu-first-entry/entry-probe-18.json。修复HEX清屏1920/1280错算与临时向量入口，178新点覆盖首线程到BSD/root，首线程入口交回原生VBAR；A02A像素不符数、A02B检查ID、A02C向量状态。740差分及全部新/旧回归、同ADT检查和镜像回读通过。最终模型进入PE_init_iokit后，在OSKext摘要清零STP产生未处理CPU异常，原因未区分；BSD未到，不改参数/补假RAM。详见2026-10-25-v25-first-thread-display.md及STATUS。
>
> PROBE18未启动，最近设备后验仍为17:18:00北京时间PROBE17恢复Android1/A槽/三SHA一致。下一次临时boot需本包录像/按键恢复就绪、新preflight与即时通知，不复用旧确认。先 `python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-18.json`，再按record-nuwa-trial-state.py和trial-v4-firmware.py单次试验/恢复后验。原始媒体仅本地；通用AGENTS合并提交280c198，原nuwa边界保留，无push。下方旧候选/状态为历史。
> **当前唯一有效进度：PROBE17读图/恢复闭环（2026-10-25 17:18:00北京时间）**：原图哈希31f4ed27…、本地out保留；126亮/32未亮，ID0–60均亮，实机到load_context调用前，已越过VM、sched/task/thread初始化与首线程创建路径。61缺块符合noreturn，不作停因；157是共享后继，不能称cold.1执行。原厂恢复Android1/A槽/三SHA与试前一致，本轮无待按键任务、无第二候选。新证据reports/xnu-entry-probe-trial/2026-10-25-v24/{screen,trial,recovery,postcondition}.json。下一主线密集观察load_context内部、machine_load_context/continuation与kernel_bootstrap_thread，先排查切换后日志映射失效，不把无新点直接当hang。媒体仅本地，无push。下方进行中/未恢复均为历史快照。
> **PROBE17正在实测（2026-10-25 17:12:30北京时间）**：代码/离线证据75daa59，用户本包录像/恢复就绪；17:11:45新基线Android1/A槽/三SHA与上轮一致，已即时通知并完成单次临时boot ACK。等待菜单电源Enter后的网格与A字段，ACK不算阶段证明；恢复Android及三SHA后验待做，不启动第二候选。新证据reports/xnu-entry-probe-trial/2026-10-25-v24/；取得画面后按trial-v4-firmware.py recover和record-nuwa-trial-state.py --before闭环。下方“未启动”是历史快照，当前以此段和STATUS为准。
> **当前有效交接：2026-10-25 v24 / PROBE17（优先于下方历史）**：已一次性布密 kernel_bootstrap/VM/pmap 启动可见路径，158编号/150新增位置，692差分及全部入口、映射、console、绑定回归通过。内核6110c6fb/58404864B/199补丁，镜像e3b8e022/70266880B，最终ADT572c4dbb；包 reports/xnu-first-entry/entry-probe-17.json。绿点为后继位置到达，不能单独证明调用返回。6000万模型指令进入页释放133696次；1.2亿累计240085次，越过pmap/vm_page后继位置并进入zone调用路径，无非法访存。zone完成和实机同路径未验证。详见2026-10-25-v24-dense-bootstrap.md和../STATUS.md。
>
> 本轮无设备动作，最近实机事实仍为PROBE16 kernel_bootstrap入口和16:44:29北京时间恢复Android1/A槽/三SHA一致，不冒充当前查询。新包需本包录像/按键恢复就绪、刷新preflight后单次临时boot；菜单电源Enter、无180秒等待。先运行 `python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-17.json`；再按 record-nuwa-trial-state.py 与 trial-v4-firmware.py 新鲜门执行，不复用PROBE16录像许可。原始媒体只留本地，不push。正式源码整核重建、scheduler/驱动/root/iOS仍未验证。
> **最新闭环（2026-10-24 20:53:19，北京时间）：** 入口探针ab3c092b单次临时启动，原图5716899a独立确认绿/蓝/黄/品红，入口首字与候选一致；实机确认到XNU页表生成后、开启MMU前。recovery/postcondition确认Android1/A槽/三SHA与本轮preflight一致，无flash/erase/改槽，无需继续按键。原图约10MB在out/trial-evidence/kernel-entry-probe-01/，元数据在reports/kernel-entry-probe-trial/2026-10-24-01/screen-evidence.json。当前代码里程碑为本轮新增入口探针提交，固件仍旧已验收CI40014018074。下一步离线准备MMU后/C入口标记；不重启本包，不复用旧录像许可。下方进行中条目为历史。

> **本轮已取得XNU入口实机观察：** 用户报告绿/蓝/黄/品红四色，证明新探针的内核入口、页表生成后与开启MMU前路径执行；MMU成功开启/C初始化/iOS未验证。180秒观察完成，原图录像待交付，恢复程序已运行；若仍停画面用户保存后按键回fastboot。用户电源键可当Enter的现场观察已记，不再沿用旧绝对否定。见screen-observation.json及入口探针操作记录。

> **2026-10-24 20:4x 本轮进行中：** 单次临时启动入口探针ab3c092b（内核b1f532c1，FD仍2d606985/CI40014018074），用户已确认本包录像≥180秒及按键恢复，preflight新鲜Android1/A槽/三SHA。原内核含BCM2837专用0x40000040写入，软件对照已定位；新候选仅NOP专用写入及增加内核内色带/早期异常显示，16软件/5解析/31ADT检查通过。ACK0不是内核证据，正在观察；只读本轮画面并recover/postcondition，不再自动启动。命令、所有SHA和证据见 [入口探针记录](2026-10-24-kernel-entry-probe.md)。

> **2026-10-24 20:25 接手纠错，优先于下方历史条目：** SecurityLock/LockCapsuleInterface 已固定来源为Mu CapsuleRuntimeDxe的ExitBootServices回调；不是Apple安全链失败。实际DarwinEnter绿色写入早于br x1，不能证明XNU开始执行；slot-retry-count是剩余次数，不是累计失败数。当前确认到UEFI加载/窗口/DarwinEnter写屏，内核第一指令/退出口待定位。14项静态审计通过，见 [接手审计](2026-10-24-first-entry-provenance.md) 和 ../STATUS.md。本轮无设备动作、新包或新录像确认；最近设备事实仅继承下方旧记录，不当作当前查询。后续先离线设计交接尾部与XNU入口的独立标记，保留所有启动前日志/恢复门。

# 主线交接（2026-10-24，USB v3实测闭环）

当前设备仓main：运输实测已提交8de7b98bedd0778e7cf9b69544bf7a2cd6f8a113，新文件SHA探针Q-153待提交。先读AGENTS.md和STATUS.md。两旧资料库只读；firmware工作源D:/Code/uefi-nuwa，独立upstream检出D:/Code/UniXNU-integration。上轮恢复闭环，无需按键；新文件包未启动，待新鲜录像条件。

## 最新实际状态

8177783e v3包只临时启动一次，用户新鲜录像确认和启动前即时通知已取得。preflight唯一nuwa/kalama、Android完成1/A槽、三分区旧基线一致；实际120.0秒USB观察，ACK=0不是阶段证明。两原图确认独立NUWA-VOLUME result=1/bytes0x4000000/块Success及FAT挂载，之后才加载embedded 4MiB卷。菜单本身可能来自两卷之一，不用其判运输成功。

观察后临时加载固定原厂v4 boot ef558db2；recovery识别Android完成1，postcondition.at=2026-10-24T07:41:49.163107+00:00（北京时间15:41:49），完成1/A槽及boot_a/vendor_boot_a/init_boot_a三个SHA与preflight相同。本轮恢复闭环；不自动再启动候选或OTG。证据reports/usb-ramdisk-trial/2026-10-24-v3-01/，操作2026-10-24-usb-v3-trial.md。没有flash/erase/改槽位。原观察报告保留其当时pending状态，当前以postcondition及screen-observation为准。

## 运输结论与固定产物

本次64MiB封装CRC→只读BlockIo→FAT阶段实机通过，非真实大文件SHA/内核/OS通过。原图offset0x1d77f27减64恰等于历史vendor_ramdisk30899943B，强烈支持vendor+临时generic拼接；v4 init_boot替代为此前缺卷首因判断增强。同固件v4匹配对照和重复性未实测，不称唯一根因。完整chosen范围未拍到，推算地址不写板值。

v3候选8177783e1364caed71e0db82f4c91db720f9586f8bc0d05ca044e133be4ad898/70266880B，out/trial-boot/usb-ramdisk-40014018074/boot-ramdisk-v3.img；严格报告reports/usb-ramdisk/40014018074/package-v3.json。v4离线对照91e86ce4与它仅offset20/40两字节不同，不纳入启动scope。相同FD/shim/64MiB退出配置探针，无XNU/ADT。包device_executed=false是构建时元数据，不修改包；本轮执行单独报告。

复验命令：bundled Python -B scripts/usb_ramdisk_package.py --validate reports/usb-ramdisk/40014018074/package-v3.json。7容器/新门控和10历史门控通过，16原始ABL门字节用户QEMU夹具通过；版本来源+0x28写context+0x458另有静态证据。当前不重复构建/试同一菜单包。历史脚本trial-v4-firmware.py仅对严格新scope支持v3；旧控制台v4固定文字已改未来按metadata打印，原日志不改。

## 上游与内核资格

用户要求的全部审查更新已合并到wh1stl3/UniXNU@e553e467ebfe7642e9f483d3977a57066c6d1aef（原76dd6414与上游1a01c2af双亲merge），完整树等于上游+3工作流，21模块固定。固件CI40014018074/source5abdde1、内核40015845083/source6070627成功；原内核40014023191失败因前置zzw缺失已修，保留失败记录。详见2026-10-24-upstream-integration.md。

FD2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3145728B，shim8a3b5476/112B。SEC7192fd3f与26ef8efd字节相同，原Heap/HOB坏链保护/缓存维护/内存表不改，697静态检查通过；本轮已实测独立卷/FAT/菜单。firmware source pin6176a822+11补丁，固件仓文档HEAD ca2f043不替代镜像来源。

内核bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，64补丁、Darwin22.6.0/iOS16.0、零未定义/5平台导出及真实归档匹配。新分析eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定读回/代码范围不变/24解析，loadable=false、initializer空。AMFI实际注册入口/局部conf80B/23项写入到335策略槽有静态证据，12项源码时序检查下调单纯DATA_CONST写保护风险；完整构造/start/once-guard/参数和C++ABI仍缺。不要把原分析内核当可启动OS。

## 可继续的离线工作与下次设备门

先在已通过USB v3上准备真实大文件只读读取/SHA诊断，不执行分析内核；继续AMFI构造/start间接调用和回调ABI、真实ADT及实际连续窗口资格。9GiB仅快照，不是已分配窗口。ST FTS路线保持，不照搬sheng板值/Novatek/存储清空动作；board/bringup身份/内存及任何_verified不变。

用户现有OTG线并授权择优，USB v3已通过所以当前不用OTG，保留备选。任何新包都需新鲜用户录像条件、严格包校验、唯一nuwa/kalama、Android完成1/三分区基线与具体恢复路径，启动前即时通知；结束恢复完成1及三SHA一致。当前轮次文件不可覆盖或复用，不自动做v4对照/第二候选。

## 已完成下一步离线准备：文件SHA包18ebd838

Q-153新增独立6144B ARM64 EFI app def33a4a，菜单type=efi，来源卷固定路径READTEST.BIN为原分析MachO的58335232B普通数据（eb66542c），不执行数据。无新FD源码/镜像行为，正常AllocatePool完整缓冲/最大1MiB每读/4096调用，精确长度+EOF+SHA，释放关闭后结果保留30秒并返回。复用原样NativeAdreno b686b905 MIT SHA，许可随最终FAT。实际28个Mu头固定git对象校验。

完整系统AArch64 QEMU以QEMU_EFI.fd加载真实PE，从最终fat-02读取全部数据/SHA匹配/返回Boot0000，13软件协议场景/3向量/15门控通过；不等于nuwa EFI加载策略/文件阶段通过。最终包18ebd83865eb0026655fddbfcea6a4f824c80cd4f65bf692528726d06a2389a8/70266880B，out/trial-boot/file-read-audit-02/boot-file-audit-v3.img；严格报告reports/file-read-audit/package-02/package.json。FAT b44d22bc/64MiB，app/数据/config/MIT均完整读回相同。早期fat-01/包01由含许可fat-02/包02取代，不可用于后续启动。

续接先 bundled Python -B scripts/file_audit_package.py --validate reports/file-read-audit/package-02/package.json。新scope USB-FILE-SHA-OFFLINE元数据如实xnu_included=true，但strict验证只允许该固定文件作数据、kernel_execution_enabled=false/无XNU entry/无ADT，不能编辑JSON启用OS。原trial脚本其他scope仍禁止XNU。当前无新手机查询，最近实际恢复仍本轮v3-01北京时间15:41:49。

需本包新鲜录像≥120秒/必要时按键回fastboot确认，之后刷新preflight并即时通知再单次launch。计划新轮目录reports/file-read-audit-trial/2026-10-24-01/，不得用旧v3-01 preflight。应拍FILE SHA新菜单和NUWA-FILE-SHA实际SHA/PASS/final bytes，旧embedded菜单不算成功；正常返回也需原恢复+postcondition三SHA闭环。更详细源码/证据/命令和未验边界见2026-10-24-file-read-audit.md。当前不需要OTG，无新启动已在运行。

## 文件SHA第01轮正在执行

用户本轮已答可以现在准备录像；新鲜preflight确认nuwa/kalama、完成1/A槽及三SHA旧基线一致。已即时通知后单次18ebd838临时启动ACK=0，120秒观察进行中，目录reports/file-read-audit-trial/2026-10-24-01/。若中断先检查本轮launch/recovery/postcondition，不重复launch；实际文件画面和恢复待补，不把启动前完成1或QEMU结果当本轮实机文件通过。当前ACK是命令接受，不是阶段证明。

当前有效进度：launch.ended_at=2026-10-24T08:09:23.864382+00:00，120秒观察已结束。用户文字报告Read 58MB新菜单，问是否选entry；已说明Enter一次（或支持的空格/1），固定Menu.c任何键会停止倒计时。没有实际SHA/FAIL原图，不假设已执行或未执行；实体ButtonsDxe二进制映射尚未确认，不猜电源键。为避免中途打断仍待菜单操作的应用，本轮recover尚未运行；Android恢复/三SHA待补，人工操作待办不阻止离线分析，禁止重新launch。

## 最新有效状态：Access Denied已收图且恢复闭环

原图user-access-denied.jpg明确新配置、Read58MB条目及returned Access Denied，条目已尝试执行而非等Enter；已纠正前述用户操作判断。screen-observation.json保留原图SHA、真实BUILD_REPORT中SecurityStubDxe/DxeImageVerificationLib和0x04介质拒绝policy、实际app certificate table=0。首因高置信为外部无签名EFI认证拒绝，但未捕获准确LoadImage/StartImage返回点/runtime SecureBoot变量；不称SHA实机通过，不把QEMU认证环境当nuwa。

recover实际临时加载原厂v4 boot，postcondition.at=2026-10-24T08:14:06.606976+00:00（北京时间16:14:06），完成1/nuwa/kalama/A槽和三分区SHA相同；当前恢复已闭环，无需按键/键盘/录像。不要重复18ebd838试验，不启动第二候选。详细操作2026-10-24-file-audit-access-denied.md，目录reports/file-read-audit-trial/2026-10-24-01/。

下一步离线优先评估将同一只读校验核心纳入独立固件诊断profile、沿既有认证启动链运行，继续读取外来FAT；另一个方案为已有信任链签名资格/准确API状态，不能假造签名或改信任变量。当前尚未实现/构建新固件包，不默认关闭Secure Boot/放宽policy，不改Heap/HOB/板值；新包需重新SEC/保护验收及新鲜录像确认。

## 最新离线实现：FV文件诊断待实际CI

固件源a155c495c863e06d400b515315e3b8f7791dc308已推送（NuwaFileAuditDxe/INF/docs），19实际C源AArch64软件协议场景+一次性Ready回调通过，空枚举清理亦覆盖。设备新增独立fv-file-audit profile，前11guard补丁与全部非选择post-image保持，57输入/12补丁/15后哈希通过；新增0020仅选择新驱动。SOURCE_DATE_EPOCH显式1792776324与真实旧build-settings一致，避免无关SEC日期变化。认证库/keys/拒绝policy源固定，不关闭SecureBoot。

实际CI尚待验收：必须新模块GUID/PE/DEPEX/屏幕marker、SEC SHA7192fd3f逐字节一致、实际认证库/介质0x04策略和驱动map Sha256HashAll。软件fixture用NativeAdreno SHA回调而目标链接BaseCryptLib，不能混为目标库已执行。相关scripts/check-fv-file-audit.py、test-fv-file-audit.py和reports/fv-file-audit/；操作2026-10-24-fv-file-audit.md。

当前没有新镜像包/设备动作；18ebd838失败和Android16:14:06恢复仍为最近实机真相。下一步触发firmware-candidate.yml profile=fv-file-audit，检查失败保留日志且修复，不能跳过新增检查。CI后才准备USB v3数据FAT+退出菜单包，避免重复执行外部app；新包另需严格scope/录像/恢复门。不要重复启动旧18ebd838，不要求用户键盘/OTG。

## 实际首轮构建与严格LTO修正

40078257763/source2b7328b编译成功，初始检查要求Sha256HashAll包装名未考虑LTO而失败，保留initial-ci-failure.json。下载产物在修正后的本地强检查通过：FD52ab071e/3MiB，SEC7192fd3f与旧完整字节一致、原Heap/HOB/cache/认证库0x04策略/7模块及真实BaseCryptLib/OpenSSL链接通过。Ready实际四次BL→sha256_block_data_order/572B，crypto-linkage.json记录PE/map/bodySHA；新的检查拒绝移除调用或4B stub，不简单删条件。待新检查CI完整重跑后固定实测包，不将首轮CI写成绿色。

已生成纯数据FAT5ea19e90/64MiB及首轮本地重验包6b3e5bfd/70266880B，严格报告reports/fv-file-audit/40078257763/package.json。无外部app，只READTEST.BIN与退出菜单；FV自动检查无需Enter。fv_file_audit_package.py继承原所有保护并固定数据用途，新scope FV-FILE-SHA-OFFLINE；原脚本加入scope但仍必须新鲜capture/preflight，不能编辑JSON启用XNU。最近手机仍18ebd838失败后Android16:14:06恢复，没有新设备操作。

完整CI第二轮40080439083已在dbbdc02247df0bba08183df97f3775286ef96271触发，profile=fv-file-audit。该版本含LTO实际BL/函数体/真实库检查和23项门控；请等其结果/独立下载复核，不重复触发。首轮40078257763仍保留为检查失败，不改写为成功；当前无新手机动作或下一轮录像确认。

## 最新有效状态：最终6b3e5bfd离线验收完成，待录像

40080439083/source dbbdc02247df0bba08183df97f3775286ef96271完整success并独立下载检查710项/7模块通过。FD52ab071eaa6cdb06f1902464923f1fab11f55d169f0494a58165ceed8894be51/3MiB与首轮完全相同，SEC7192fd3f与旧已实测固件逐字节相同；原Heap/HOB/cache/认证库和0x04介质策略、真实BaseCryptLib/OpenSSL/Ready四次SHA压缩BL通过。acceptance.json、ci.json、crypto-linkage和artifact-inspection在reports/fv-file-audit/40080439083/。旧CI40078257763仍失败，不改记录。

最终包6b3e5bfd3a8e1d5a8e8abbda3268872a6fc69b287c144df70387012d46a41dc7/70266880B，严格报告reports/fv-file-audit/40080439083/package.json，out/trial-boot/fv-file-audit-40080439083/boot-fv-file-audit-v3.img。沿原USB v3，只数据READTEST.BIN和退出菜单，无外部EFI app/XNU启动项；FV ReadyToBoot自动诊断，无需Enter/键盘/OTG。普通数据仍是58335232B分析MachO/eb66542c，loadable=false且不执行。

续接先 bundled Python -B scripts/fv_file_audit_package.py --validate reports/fv-file-audit/40080439083/package.json。需新包录像≥120秒及必要时按键恢复条件；刷新record-nuwa-trial-state.py --package <本报告> --capture-confirmation <本轮答复> --output reports/fv-file-audit-trial/2026-10-24-01/preflight.json，唯一nuwa/kalama、Android完成1/三SHA新基线及恢复路径通过后，即时通知再单次trial-v4-firmware.py launch。旧18ebd838/任何之前preflight不可复用，尚未取得本包录像确认，禁止现在启动。

目标画面NUWA-FV-FILE Ready/unique/read/actual SHA eb66542c/PASS/final bytes0x37a2000与exit状态，保留30秒后继续退出菜单。只有菜单/ACK不算通过，失败按具体阶段留证。结束用本包recover及record --before刷新Android完成1/三SHA相同。最近真实手机恢复仍2026-10-24T08:14:06.606976+00:00（北京时间16:14:06），本轮全离线无新设备查询。新诊断驱动实机/完整OS仍未验，不改Heap/HOB/板值/_verified或认证策略。

## 最新实机闭环：6b3e5bfd文件SHA通过

6b3e5bfd已单次实机PASS exact length/EOF/SHA256，固件内读取退出Success，data-only菜单出现。证据reports/fv-file-audit-trial/2026-10-24-01/含preflight/launch/三原图/screen-evidence/recovery/postcondition；源和构建仍a155c495、CI40080439083/dbbdc02，包报告不变。用户本包录像条件确认并已提前通知启动，120秒USB观察不冒充视频。首次evidence目录误参被设备前拒绝，随后仅一次候选启动。

最新实际状态2026-10-24T10:09:48.744209+00:00/北京时间18:09:48：nuwa/kalama、Android1、槽_a、boot/vendor_boot/init_boot SHA与试前一致，无flash/erase/改槽。无需再回fastboot或按Enter。原认证/Heap/HOB/板值不变，分析MachO仍数据文件，不执行。

下一步离线检查原生内核加载链、ADT、实际OS窗口与初始化/ABI资格。不要重复文件探针或从文件PASS直接执行loadable=false分析内核；新包先离线验收，新录像/恢复门及即时启动通知。具体实测和旧认证拒绝首因判断更新见operations/2026-10-24-fv-file-audit.md。

## 最新离线里程碑：ADT 生成器落地，board 仍缺受审字段

本轮全离线，无手机、USB 或固件动作；最近真实手机状态仍是 2026-10-24T10:09:48.744209+00:00（北京时间18:09:48）Android完成1、槽_a、三分区SHA与试前一致。

改动：新增 scripts/make-nuwa-adt.py、scripts/check-nuwa-adt.py、scripts/audit-nuwa-adt-inputs.py、scripts/test-nuwa-adt.py；board.toml [payload.adt] 增加 tool/cpu_regs/psci_method（非受审字段）。OS 入口 blocker 3 中"生成器缺失"部分解除，"运行时分配窗口"仍在。

证据：reports/adt-nuwa/2026-10-24/{min,full,inputs,test}.json；输入 out/live-nuwa-dt/android-dt-after-r011/android-live.dtb（4815节点）。结构审计最小12节点/20检查、完整21节点/35检查均0失败；常量对实机FDT 14项对照10项精确相等、0项不符；正负例8用例全部符合预期。操作记录 operations/2026-10-24-nuwa-adt.md。

两处判断留档：根 compatible 用实机值 qcom,kalama-mtp/qcom,kalama/qcom,mtp，因为 ArmDTPlatform.cpp:123-142 只校验四节点与 NVRAM proxy，不匹配根 compatible；iomem System RAM 跨度 0x23FFFF000 比 FDT /memory 跨度 0x240000000 只少最后 0x1000，此前"9216 MiB 与实测差55MiB"的印象不成立。

**当前唯一阻塞**：[payload] dram_size（payload.py:149 直接读取）与 [payload.adt] owned_memory_size 属 AGENTS §3.1 受审字段，未写入；已提 NEED-REVIEW R-012（A: 0x240000000/0x40000000 倾向；B: 0x23FFE0000/0x40000000；C: 只填 dram_size）。批准前 payload 步骤不可运行，board 保持 example=true，不改 bringup-plan/donor/固件/feed/XNU窗口，不置任何 _verified。

获准后可直接续接的离线命令：

```bash
python3 scripts/make-nuwa-adt.py --output out/adt-nuwa/<新目录>/kernel.macho.adt --dram-size <批准值> --owned-memory-size <批准值> --ipad-identity --cpu-regs 0,256,512,768,1024,1280,1536,1792 --psci-method smc
python3 scripts/check-nuwa-adt.py --adt <上一步产物> --output reports/<新路径>/audit.json
python3 scripts/audit-nuwa-adt-inputs.py --fdt out/live-nuwa-dt/android-dt-after-r011/android-live.dtb --output reports/<新路径>/inputs.json
```

未完成：固件能否满足 owned 窗口（需 UEFI 内存图与实际分配）、XNU 是否接受该树（无内核执行）、任何驱动是否绑定（未验证）。启动前仍须离线验收、新鲜录像与恢复条件、即时通知；不得从文件 SHA PASS 直接执行 loadable=false 分析内核。

## 最新：R-012 批准 A，board 受审字段已写入并复核组装

用户 2026-10-24 18:40 回复「批准A继续推进」。按最小范围只写两个字段：`[payload] dram_size = "0x240000000"`、`[payload.adt] owned_memory_size = "0x40000000"`。`example = true`、其余 TODO、所有 `_verified`、bringup-plan/donor/固件/feed/XNU 窗口均未动；无设备动作，最近真实手机状态仍是北京时间 18:09:48 Android 完成 1。

新增 `scripts/check-nuwa-adt-board.py`：基座因 `config.py:103` 拒绝 `example = true` 而跑不起来 payload 步骤，该脚本按 `payload.py:149-170` 的规则从 board.toml 组装同一条命令行离线重放。结果 board-only 21 节点/31 检查、带 sidecar 21 节点/34 检查，0 失败；证据 `reports/adt-nuwa/2026-10-24/board.json`、`board-with-sidecars.json`。

复核中发现并修正一处真实契约不兼容：旧实现强制 `--unique-chip-id` 与 `--chip-id` 成对，但基座分别从命令行/环境变量与 `[payload.adt]` 独立传入，board 的 `chip_id` 仍是 TODO，只给 seed 时会 exit 2 把整条 payload 卡死。已改为允许独立传入、仅告警，两者并存才写身份属性；`test-nuwa-adt.py` 增至 10 用例并加 `seed-without-chip-id` 锁住该行为。

续接命令（全部离线）：

```bash
python3 scripts/check-nuwa-adt-board.py --seed <hex> --sidecars --output reports/<新路径>/board.json
python3 scripts/test-nuwa-adt.py --output reports/<新路径>/test.json
python3 scripts/audit-nuwa-adt-inputs.py --fdt out/live-nuwa-dt/android-dt-after-r011/android-live.dtb --output reports/<新路径>/inputs.json
```

ADT 侧已齐备。board 剩余 TODO：`[ipsw]` url/chip_id/board_id/sha256、`[payload]` volume/size_mib/kernel_args、`[kernel]` defconfig/archives/prelink、`[firmware]`、`[bootimg.image]`。下一主线为原生内核加载链与初始化/ABI 资格审查，以及 owned 窗口 1 GiB 可用性的 UEFI 证据。**窗口可用性、XNU 是否接受该树、驱动是否绑定均未验证。**

## 最新：早期安全初始化器通路打通，blocker 1 只剩 ABI 资格

全离线，无设备动作；最近真实手机状态仍是北京时间 18:09:48 Android 完成 1。

三条实证（详见 operations/2026-10-24-early-security-init.md）：① 228 个 kext 的 `_PrelinkKmodInfo.start` 全是跳转桩，桩从 `__DATA/__common` 取地址；AMFI/IONetworkingFamily/AppleARMPlatform 的槽静态为 0，corecrypto 的槽是真实函数 —— **空槽即"无 kmod_start"**，AMFI 初始化不走这条路；② 三个 `__mod_init_func` 只调用 `OSMetaClass` 构造函数，与策略注册无关；③ 初始化由 `[kernel.prelink] early_security_init` 驱动，native bf14e530 导出 `_native_prelink_security_init_version = 1`（`0xfffffff007021760`）。

根因：`scripts/emit-current-prelink-analysis.py:18` 传 `{}`、第 43 行写死 `early_security_initializers={}`，这张表从未配置。用 `scripts/audit-early-security-init.py` 显式配置后，emit 的五项前置检查（marker/AppleSecurityExtension/RX 段/对齐/溢出）全过，记录 `0xfffffff004703c54` = 原 VA `0x5703c54` + slide `-0x1000000`；候选 `1aeebf13`/58335232 B 与 `eb66542c` 同长度，408983 字节差异全在 `__PRELINK_INFO`，三个可执行段零差异（`scripts/compare-prelink-candidates.py`）。

**方法论警告**：把 23 MB 段一次性交给 `capstone.disasm()` 会在首个无法解码字节处静默停止，本轮首轮扫描因此错误地得出"注册函数无人调用"。现改为 `array` 按位模式逐字检查并报告覆盖方式；负结果必须带覆盖率才可信。另注意 `adrp`+`add` 的地址一律用代码相加，手打多写一位会读到不受段覆盖的区域。

仍未验证：`0x5703c54` 的调用约定与返回语义、完整构造/start 间接路径、C++ 结构 ABI（blocker 2）、owned 窗口可用性（blocker 3）、大负载装载（blocker 4）。两个候选 `loadable` 均 false。

续接命令（全离线）：

```bash
python3 scripts/audit-amfi-callgraph.py --output reports/<新路径>/amfi-callgraph.json
python3 scripts/audit-early-security-init.py --work out/<新目录> --output reports/<新路径>/early-security-init.json
python3 scripts/compare-prelink-candidates.py --old out/native-prelink-merged/analysis/kernel-prelinked-analysis.macho --new out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho --output reports/<新路径>/diff.json
```

下一步：核对 `0x5703c54` 调用约定与返回语义（结合 23 项 ops 槽位与 `mac_policy_register` 导入），再决定是否把配置接入 `emit-current-prelink-analysis.py`。任何实机动作前仍须离线验收、新鲜录像与恢复门、即时通知。

## 最新：首次内核进入实机试验，内核入口执行后在启动链锁阶段重启

本轮有真实设备动作（`fastboot boot` 临时启动，未 flash/erase/改槽）。

**结果**：DarwinBoot 打印 `Exiting boot services. A green bar across the top means the kernel entry code ran.`，屏幕顶部出现绿色横条；XNU 自身输出 `AppleARMPlatform: IODTNVRAM from …`、`SecurityLock::LockType: SOFTWARE_LOCK, Module: 42857F0A-13F2-4821-8A23-53D3F714B940, Function: LockCapsuleInterface`、`[ML] dump table info not found, Status = (0x0)`、`App Log Flush : 0 ms`，此后无输出；设备自动重启回 Android。

**2026-10-24 20:1x 更正（据完整录像）**：绿条只持续 **6 秒**（118–123 s），不是 235 秒 —— 它只是 ExitBootServices 的瞬时标记，不代表内核存活时长；`Module` UUID 首位应为 `42857F0A`（上轮读作 `42B57F0A`）。录像同时确认 `App Log Flush` 之后**内核静默退出**：124 s 起黑屏 19 秒，无 panic 文本，167 s 回到 Android 桌面。详见[录像取证](2026-10-24-first-entry-video-forensics.md)。

确切读数（原图 881×1920 裁剪放大，reports/xnu-first-entry-trial/2026-10-24/crop-*.png）：`kernel va 0xfffffff003DC8000 pa 0x8C01C8000`、`args pa 0x4C408000 window 0x40000000 bytes`、`video base 0xB8000000 1440x3200 row 5760 bytes 32 bpp`、`CurrentEL 1 SCTLR_EL1 0x3D0018D0 TCR_EL1 0x28003518`、`ID_AA64MMFR0_EL1 (PARange 2, 4 KiB granule supported)`。

意义：① **1 GiB 连续窗口被 UEFI 成功给出**（ADT 的 `darwinboot-memory-size` 生效），blocker 3 的窗口可用性得到肯定答案；② 内核物理基址落在主 bank `0x8c0000000` 内；③ 4 KiB granule 与 D-003 一致；④ 内核入口代码确实执行了。

恢复：设备自动重启回 Android，无需人工按键；`postcondition.json` 确认 nuwa/kalama/`boot_completed=1`/槽_a 且 boot_a、vendor_boot_a、init_boot_a 三分区 SHA 与试前一致。

失败点判断（置信中高）：内核在 Apple 启动链安全锁阶段终止，最后可见输出是 `SecurityLock::LockType: SOFTWARE_LOCK` 与 `LockCapsuleInterface`，这类校验需要 SEP/硬件密钥/Apple 信任链。**反证空白**：`SecurityLock`、`LockCapsuleInterface`、`SOFTWARE_LOCK`、`App Log Flush`、`dump table info not found` 在 XNU 8796 源码树（全部类型含 blob）、UniXNU 基座源码与补丁、donor kernelcache、native 内核、预链接产物中均搜不到（ASCII 与 UTF-16），来源未定位；主机只有 COM1（ACPI 物理串口），**没有手机 9008 串口**，拿不到 panic 串志。

**下一步**：① 复现时观察窗口延到 600 秒，请用户把镜头对准屏幕直到重启，拍下重启前最后画面（当前照片停在 `App Log Flush`）；② 若能接手机 UART/9008 串口，串志是定位退出口最直接手段；③ 评估 `amfi-only-platform-code` 与启动链锁的关系。

包与证据：`reports/xnu-first-entry/package-01.json`（镜像 `aa2dfb5d…`、内核 `1aeebf13…`、ADT `e7a03577…`、FAT `f0cec54b…`）；`reports/xnu-first-entry-trial/2026-10-24/{preflight,launch,postcondition}.json` 与 `screen-01.jpg`（SHA256 86b7d300…）+ 三张放大裁剪图。操作记录 `operations/2026-10-24-xnu-first-entry.md`。



## 上游日志方案审阅追加

2026-10-24：main@bd127c0未找到二维码日志实现/PR；PR88是giulia协议的主机USB终端，PR100为Linux构建且默认iOS17。当前工作树仍e553e467，未采用变更，无新设备动作。下一步继续正式入口修正与早期C诊断；Linux/USB分别资格化。证据和决定见2026-10-24-upstream-debug-review.md。

## PR100完整适用性评估追加

推荐隔离WSL支线，保留已验收macOS CI。32局部fixture和LLVM/IIG两份严格上下文通过；当前工具链未安装。关键阻塞为新IIG split RPC与Darwin22适配、helper显式iOS17及新clang类型语义/完整8796验收。原PREFIX仍写系统路径，建议独立环境+原生ext4。不把工具链迁移当MMU实机修复；无新设备动作。完整证据在operations/2026-10-24-pr100-assessment.md和reports/pr100-assessment/2026-10-24/。

## 入口探针02：MMU后与arm_init标记（2026-10-24 23:55，main）

全离线，无手机/USB/固件动作；最近真实设备状态仍是 2026-10-24T12:53:19Z（北京时间20:53:19）nuwa/kalama、Android 完成 1、槽_a、三 SHA 与试前一致，本轮未刷新。

新候选 **db4aa1723c8c5c4f253452e6e74b44f9a1e421fecf9c68d80d7f0e04c1fa2b11**，58,339,328 B，24 补丁（v3 为 22）；`loadable=false`/`runtime_qualified=false` 未改，板值/认证/AMFI/`_verified` 未动。新增 cyan(y=736) 钩在 `msr sctlr_el1` 之后的 `isb`、white(y=832) 钩在 `_arm_init` 首指令；原有四色带与红/ESR/ELR/FAR 保持。

实现前提是先量出来的一条硬事实：MMU 后 framebuffer `0xB8000000` 未映射。因此由 pre-MMU 的 magenta 钩子在 V=P L1 slot 2 为空时装 1 GiB 恒等设备块（`0x6000008000040d`）并把屏幕几何快照进探针页；两个 post-MMU 钩子只读探针页、不依赖 boot_args 物理地址，无快照不画；槽被占用则不改映射。

证据 `reports/kernel-entry-probe/2026-10-24-v4/`：software.json 29 项（两钩子以真实页表+真实快照直接进入）、mapping.json（装映射后 FB 变恒等可译，独立复核）、loader.json（5 用例）。界限：Unicorn 拒绝执行 `msr sctlr_el1`，开启 MMU 本身无软件执行证据；cyan/white 只在实机出现才算。

下一步：① 打包 `build_xnu_boot_package.py --entry-probe` 指向本报告并做严格包校验（离线可做）；② 启动前须新鲜 preflight、即时通知、用户对本包的录像/恢复确认，`ab3c092b` 许可不可复用；③ 结果判读：有 cyan 无 white → 查 `ret` 到 arm_init 的 KVA 切换；两者皆无 → 查 MMU 开启本身；有 white → 转 pmap/arm_vm_init。PR100 Linux 构建支线独立在 `codex/pr100-linux-8796`（`b8872cb`），未合入。证据操作记录 `operations/2026-10-24-post-mmu-markers.md`。

## 入口探针v5：复核修正（2026-10-25 00:20，main）

全离线，无设备动作；最近真实设备状态仍是 2026-10-24T12:53:19Z（北京时间20:53:19）nuwa/kalama、Android 完成 1、槽_a、三 SHA 与试前一致。

独立复核对 v4 提出六点，其中三点是真缺陷并已修：占槽失败分支仍会保存几何并绘制（现 `x15=0` 关闭）、cyan 先画带后回放 isb（现改为先 isb）、walker 把 L1 block 记为 block:false（现按 desc&3 判定）。另修打包绑定：删掉 cyan/white 检查曾仍能通过，现要求具体检查名存在。

新候选 **8515068dcd6bd699a4301109b76b80022fb07120e6167b65b6169d52aeffcb6a**/58,339,328 B/24 补丁，`loadable=false` 未改；`software.json` 33 项（新增占槽哨兵场景与 isb 顺序静态断言）、`mapping.json`（装映射后 FB 恒等可译）、`loader.json` 5 用例、`unicorn-mmu-support.json` 三组实测。

归因二次更正：翻译本身可用（复核给出 TCR `0x280993519` 的成功取指，我复跑一致）；本构建的限制是 **T0SZ=26 时从 L2 起走且 ≥1 GiB 的 VA 不可译**，而 XNU 正是 T0SZ=26 + L1 根、内核在 `0x8c37c7378`，因此真实冷启动必然在第一条翻译取指处失败，重挂根表也救不了（A–H 矩阵见 `probe-unicorn-start-level.py` 与 `unicorn-mmu-support.json`）。故「真正穿过 MMU 切换」的测试**本轮未交付**，已列为阻塞；两个后 MMU 钩子仍是带真实页表的合成进入。`ParseKernel rc=139` 的原因撤回「并行内存压力」推断，未验证。

下一步：① 评估 QEMU system mode 作为第二执行通道（优先于继续调 Unicorn）；② 打包 v5 + 严格包校验，启动前须新鲜 preflight、即时通知、用户对本包的录像与恢复确认（`ab3c092b` 许可不可复用）；③ 判读规则不变。证据 `operations/2026-10-25-probe-v5-corrections.md`；v4 记录已标「被取代」。

## 实机里程碑：MMU 已开、进入 arm_init（2026-10-25 00:45，main）

**当前最高事实：入口探针02 单次 fastboot boot 后，用户拍到绿/蓝/黄/品红/青/白六条带。** 青 = SCTLR 写入+isb 同步完成，且该带在 MMU 开启状态下经 1 GiB 设备恒等映射写屏；白 = 到达 `_arm_init` 首指令（KVA 取指）。此前"MMU 到底开没开"的天花板已被突破，页表属性/MAIR/TCR 配置错误一类猜测可排除。

镜像 af5862be/内核 8515068d/ADT ed7235cb；原图 out/trial-evidence/entry-probe-02/screen-01.jpg（7030b14c，323,957B）；启动 16:37:52Z、ACK 16:38:10Z、180 秒观察、全程 adb 无 nuwa；恢复 16:43:19Z Android 完成 1，16:43:30Z 槽_a 与三 SHA 与 preflight 完全相同（three_partition_hashes_unchanged=true）。无 flash/erase/改槽。

未验证/边界：无红条不等于无异常（MMU 后 VBAR 已是内核 KVA 向量）；内核随后返回或复位回固件菜单并重新倒计时，`arm_vm_init`/pmap 停点未知，返回/panic/watchdog 未区分；固件可能自行重入同一内核（fastboot 只发一次）。

下一步：① C 内打点（arm_vm_init/pmap_bootstrap/kernel_bootstrap 首指令，沿用探针页+快照）；② magenta 钩子把 VBAR_EL1 换成探针页恒等地址，捕获 MMU 后 ESR/ELR/FAR；③ 串口/QEMU 仅作后备。任何新包仍须打包校验、新鲜 preflight、即时通知与用户对本包的录像确认。证据 operations/2026-10-25-entry-probe-02-trial.md。

## 软件侧补强：连续穿越 MMU 的测试（2026-10-25 00:55，main）

复核源码级定位：`arm_el_is_aa64()`（qemu/target/arm/cpu.h:2030）在默认 `SCR_EL3=0`/`HCR_EL2=0` 下为假，页表遍历走 AArch32 分支（helper.c:9925 取 T0SZ&7），这才是此前"T0SZ=26 走 L2、≥1GiB VA 不可译"的原因，不是引擎限制。设置 `SCR_EL3.NS|RW` 与 `HCR_EL2.RW` 后，真实 v5 候选从入口连续穿过 MMU 到达 `_arm_init`（374,399 条指令，两宿主一致），页表仅多诊断 slot 2、候选 SHA 不变，默认态保留为负对照。`software.json` 38 项通过。

这不改变实机结论（青/白已由真机确认），只是把"后 MMU 代码路径"从"合成进入"升级为"连续执行"，两者互相印证。仍未执行 arm_init 正文/arm_vm_init/kext/iOS。

## arm_init 之后：模型分析结论与 v6 目标（2026-10-25 00:56，main）

全离线。两个结论：① 模型停在 `___ubsan_handle_sub_overflow_minimal`（brk #0x1206）是**夹具缺 ADT** 造成的保真度缺口，不是实机根因（`pe_identify_machine.c:60` 因 `SecureDTFindEntry("name","arm-io")` 失败而提前返回，时基留在 0）；② 补入随包 ADT（`kernel.macho.adt`，ed7235cb）后 UBSan 消失，改在 `_current_percpu_base+0xc` 的 `ldr x0,[x0,#0xe0]` 停（374,951 条，`TPIDR_EL1=0`）。

v6（下一轮，批准后再打包）目标：恒等 VBAR + 页内 16 向量让 MMU 后异常自报 ESR/ELR/FAR；`_current_percpu_base` 入口一条带；`_arm_vm_init`/`_pmap_bootstrap`/`kernel_bootstrap` 各一条带。风险：pmap 重建可能替换 1 GiB 设备映射；探针页或需 2 页。证据 `reports/kernel-entry-probe/2026-10-25-post-arm-init/analysis.json`、`operations/2026-10-25-post-arm-init-analysis.md`。

## 2026-10-25 · v21探针语义修复与entry-probe-14（当前续接点）

此前D-037时基算术及旧ADRP回放推论以D-038为准。镜像42b42624460d5f0b974e4315bc50d615dce6111514184815724d2040adbd509f，内核0c1594215b534434221ddd16f10a8da6e4162bcc2d614d321f297425373723c4；45补丁，离线全套与镜像回读通过，未设备启动。新鲜preflight尚未执行；本轮未查询设备，不能沿用旧Android完成1作为当前状态。

本包录像提醒已发，等待回复；之后用record-nuwa-trial-state.py --package reports/xnu-first-entry/entry-probe-14.json创建新鲜preflight，再用trial-v4-firmware.py launch --observation-seconds 180单次临时启动。准确命令、读数表和恢复条件见operations/2026-10-25-v21-probe-transparency.md。未授权flash/erase/改槽，原有恢复与三SHA门仍适用。

## 2026-10-25 15:07 · entry-probe-14实测闭环，下一前线为跨TTBR诊断映射

本包已单次启动并恢复，15:07:42北京时间Android完成1/A槽/三分区SHA与preflight一致，无flash/erase/改槽。A032=4和后续阶段色块证实越过旧WFE问题。模型按真实加载器布局与1GiB owned RAM推进至pmap原入口；新TTBR1丢probe页、新TTBR0丢FB，跳probe_pmap=FFFFFFF00848A1A8取指异常。硬件pmap未证，禁止用无色块判未进入。证据reports/xnu-entry-probe-trial/2026-10-25-v21/。当前设备已恢复，本轮不再启动；下一步离线保留或迁移诊断代码/数据/FB在新页表中的映射，细节见最新STATUS与v21操作记录。

用户更正：无需固定180秒。XNU菜单后电源键=Enter才触发内核；后续trial脚本XNU scope默认post-ACK USB观察为0。原有新鲜preflight、即时通知和恢复三SHA门保留。

## 2026-10-25 16:12 · 当前续接：实机pmap入口已到，console旧日志路径待适配

entry-probe-15镜像36969f94、内核a8b8fc90/47补丁，用户菜单电源键触发，实机pmap入口绿色块出现。16:12:44北京时间Android完成1/A槽/三SHA不变，无待恢复任务。本轮只一次候选启动。

v22新页表诊断映射与最终包ADT的四场景执行回归通过，保留代码ROexec/数据RWNX/FB Device/VBAR KVA。源码/报告均留工作区，无commit/push。主线下一步核对_PE_create_console的BCM固定panic日志区0x3c0fc000（模型读失败），补入口/实际地址观察，实机尚未捕获该ELR/FAR。不要重测旧pmap色块或猜TCR/时基，不跳整个console。详见最新STATUS和operations/2026-10-25-v22-pmap-transition.md。

原始音视频禁止自动上传，均在out或用户路径，GitHub制品ZIP内容未验，不对历史绝对保证。新包试验仍须本包录像就绪与新鲜preflight；无需180秒等待。

## 2026-10-25 · 本轮归档提交与官网更新（最新续接）

代码/证据已本地提交597baed（完整SHA见git log）；本次用户授权覆盖本地commit，未执行push。随后docs提交更新README/AGENTS/STATUS/DECISIONS/WORKLOG/PENDING-HUMAN/COMMIT-QUEUE及v20-v22操作记录。当前无待恢复任务；最后设备核验仍2026-10-25 16:12:44北京时间Android1/A槽/三SHA不变，不代表现在重新查询了设备。

续接优先读operations/2026-10-25-official-porting-update.md：固定UniXNU16e592ab已有native-dt-panic-region.patch及XNU_DT_PANIC_REGION路径，优先评估8796适用性，保留console和当前panic；未应用。QR日志通过AdvancedLogDxe/Tools/Advanced Logger导出UEFI内存快照，需producer及QR/Logger库和DSC/FDF集成，仅覆盖EBS前；nuwa尚未验收。Format2/SoC共用迁移与porting.toml另开后续里程碑，不套用iPadOS17/板值。

检查命令：python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-15.json；python -B scripts/test-probe-transition.py --build reports/kernel-entry-probe/2026-10-25-v22c/build.json --adt out/trial-boot/xnu-entry-probe-15/kernel.macho.adt --case normal --output out/RECHECK.json。需本地已存的out输入；不要重写实机绑定报告。上游pin和文件SHA在reports/upstream-porting-review/2026-10-25/review.json。

## 2026-10-25 16:44 · 最新续接：kernel_bootstrap入口已实机确认

代码/证据b708494，PROBE16镜像6f0907b2/内核167bd013/49补丁。真实DT无pram时跳过旧日志导入，原console保留；有pram显式拒绝，通用缓冲需源码重建，不假称完整实现。用户原图确认左列y512橙色kernel_bootstrap入口，不证明完成。16:44:29北京时间Android1/A槽/三SHA与preflight一致，无待人工恢复，本轮仅一次候选启动。

下一步看kernel_bootstrap/VM启动内存初始化；续跑模型20M指令耗尽，无错误，不把vm_page_release_startup+0x254判hang。先建立阶段证据，保留pmap诊断映射。来源/测试/边界见最新STATUS、operations/2026-10-25-v23-dt-panic-console.md。复跑：python -B scripts/test-probe-transition.py --build reports/kernel-entry-probe/2026-10-25-v23c/build.json --adt out/trial-boot/xnu-entry-probe-16/kernel.macho.adt --case normal --output out/NEW.json；脚本固定预算，不能当持续系统仿真。

原始媒体本地，不push。新包仍需本包录像就绪与新鲜preflight。官网QR固件接入和Format2迁移仍独立，不替代内核诊断。
