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
