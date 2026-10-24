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
