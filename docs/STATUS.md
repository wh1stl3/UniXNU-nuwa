# STATUS

> 固件内文件SHA诊断已实现并接CI：源a155c495，57输入/12补丁/15后哈希和19软件场景+一次性回调通过；SecureBoot/原Heap-HOB保护保持。实际固件CI/SEC字节/目标crypto链接待验，新包未生成，无新实机。

USB v3运输阶段已实机通过：8177783e单次原图显示独立64MiB envelope result=1、块设备Success，FAT挂载先于embedded 4MiB卷。offset0x1d77f27减64B恰等于历史vendor ramdisk30899943B，明显支持vendor+临时generic拼接，增强v4 init_boot替代为此前缺卷首因的判断；同固件v4匹配对照/重复性未验。菜单fallback不作运输证据。[实测记录](operations/2026-10-24-usb-v3-trial.md)。

运输实测已提交8de7b98。最近真实手机postcondition.at=2026-10-24T07:41:49.163107+00:00（北京时间15:41:49），nuwa/kalama、Android完成1、槽_a、三个启动分区SHA与试前一致。仅一次候选后临时原厂v4恢复，无flash/erase/改槽位。证据reports/usb-ramdisk-trial/2026-10-24-v3-01/；两原图/文字已收，完整连续视频文件未交付，不把120秒USB观察当视频。本轮后续工作仅离线，无新设备查询。

新的文件探针：独立ARM64 EFI应用def33a4add6f162a5726bba050a4c143c8ba38ea25f436f46ce4331811bb469f/6144B，以type=efi从LoadedImage来源卷只读READTEST.BIN。数据为原分析预链接eb66542c/58335232B（约58MB），不执行；精确长度/EOF/完整SHA，正常AllocatePool，最多1MiB/次及4096次，分配/读错返回，释放关闭后保留结果30秒再返回固件。固定NativeAdreno b686b905原样MIT SHA及随包许可；28实际Mu头依赖与固定git对象一致。[文件探针记录](operations/2026-10-24-file-read-audit.md)。

离线证据reports/file-read-audit/：13实际app软件协议场景和3已知向量通过；完整AArch64系统QEMU/QEMU_EFI.fd加载真实PE，从最终fat-02实际读58335232B/56次数据Read，额外EOF检查，SHA匹配/打印PASS后返回Boot0000。15项新增/历史门控通过，篡改XNU执行标记、缺新preflight/录像在设备子进程前拒绝。QEMU通过不等于nuwa EFI加载/分配/文件SHA实机通过；下一轮才验证。

最终USB v3包18ebd83865eb0026655fddbfcea6a4f824c80cd4f65bf692528726d06a2389a8/70266880B；严格报告reports/file-read-audit/package-02/package.json，镜像out/trial-boot/file-read-audit-02/boot-file-audit-v3.img。FAT64MiB SHA b44d22bcf599414e29f940872506fc2215f359e4ff82228c0a010be3d0772166，数据/两同EFI/config/MIT从FAT完整抽取读回SHA一致。xnu_included=true如实承认MachO数据字节，但strict scope限定data-only/kernel_execution_enabled=false、唯一type=efi无XNU项。最终fat-02/包02取代缺随包许可的中间fat-01/包01，后者不用于实测。

全部已审查上游更新已合并：wh1stl3/UniXNU@e553e467ebfe7642e9f483d3977a57066c6d1aef，双亲merge原76dd6414/上游1a01c2af，树为上游+3工作流、21模块固定。接入5abdde1/前置修复6070627。固件40014018074和内核40015845083 success；原内核40014023191失败因前置缺失已留档。[集成记录](operations/2026-10-24-upstream-integration.md)。

FD2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3145728B，shim8a3b5476/112B，697静态检查；SEC7192fd3f与已实测26ef8efd逐字节相同，原Heap/HOB保护/DSB-IVAC-DSB-ISB/内存表保持。该FD已实测独立卷/FAT/菜单；新app无需改固件。firmware source pin6176a822+11补丁，不用文档HEAD替代。ST FTS路线、board/bringup内存/身份/_verified不变。

内核bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，64补丁、Darwin22.6.0/iOS16.0、零未定义及5平台导出/归档一致。分析eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定读回、30 donor/native代码范围保持、24解析通过，loadable=false/initializer空。AMFI注册/局部conf80B/23写入到335槽有静态依据，12源码时序检查下调单纯DATA_CONST写保护风险；完整构造/start/once-guard/回调及C++ABI、真实ADT和实际OS窗口仍待资格。9GiB只是快照，不是分配；文件SHA通过也不等于内核/iOS执行。[AMFI记录](operations/2026-10-24-amfi-phase-and-slots.md)。

下一步触发并验收独立fv-file-audit固件CI：新模块GUID/PE/DEPEX/屏幕marker、实际SEC7192fd3f字节完全相同、原认证库及0x04拒绝policy、目标map中Sha256HashAll。不关闭策略、不改keys/Heap/HOB/板值。通过后才准备USB v3数据FAT和退出菜单的新诊断包；当前新包未生成。18ebd838原图Access Denied仍为最近实机文件结果，具体拒绝API/runtime SecureBoot值未捕获，不重复旧包。

当前固件内实现：NuwaFileAuditDxe ReadyToBoot只一次，最多64卷/唯一文件、GetInfo上限4KiB/精确58335232B/普通pool/最多1MiB读与4096次/EOF/原固件BaseCryptLib SHA；直接屏幕enter/read/hash/PASS/exit，停留30秒。固定源a155c495，57输入/12补丁/15后哈希，原11保护patch完全相同；16项设备门控回归通过。软件19场景用替身协议/crypto，不等于目标固件或硬件通过。详见operations/2026-10-24-fv-file-audit.md。
