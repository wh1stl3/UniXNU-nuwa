# USB v3大文件读取/SHA探针（18ebd838，离线准备）

## 当前进展与判断

上一轮8177783e已经以两张原图证明64MiB独立封装CRC/BlockIo/FAT挂载，Android于北京时间15:41:49完成恢复且三分区SHA不变。该阶段不再需要重复菜单试验。下一处应先验证**实际文件读取和完整哈希**，而不是立刻执行仍loadable=false的内核；运输已通也不能消除文件系统读取、EFI加载策略、分配和真实OS资格的独立问题。

本候选沿已通过的USB v3装载，固件FD/shim/Heap/HOB保护/内存表完全不变。通过UniXNU支持的type=efi调用独立应用，应用只读取自身LoadedImage.DeviceHandle对应卷的固定路径，不遍历/写内部UFS，不执行READTEST.BIN；没有XNU菜单项、ADT、内核跳转或ExitBootServices。原分析预链接作为普通数据文件改名READTEST.BIN，**实际包含Mach-O/XNU字节**，包元数据如实记录xnu_included=true、analytical_macho_data_only=true、kernel_execution_enabled=false，不用“没有内核字节”掩盖数据用途。

首要工程判断：现有运输已足够承载完整约58MiB分析文件，当前最短路径是沿同一FAT→EFI app→文件读取资格逐级推进，暂无必要引入OTG host变量。如果新菜单仍是旧Volume config，首先检查配置卷选择/fallback；若LoadImage拒绝，查固件镜像加载策略；若app已进入但分配失败/短读，按具体状态定位。不能把这些新阶段问题归为此前HOB或未执行过的AMFI。

## 来源与实际构建

自有源码package/NuwaFileAudit/FileAudit.cpp、Memory.cpp和最小include/string.h。独立交叉构建，不修改固件源树、不复制完整上游；只从git对象抽取SHA实现/头/许可到忽略的out目录。初次编译遇到C++ wchar_t与CHAR16类型不同，已加16位大小静态断言和明确转换；没有改变UEFI协议结构。有效产物来自build-02，失败build-01保留在out。

SHA实现复用[UniXNU/NativeAdreno@b686b9054f57d393c80195b82568a09f8ca106a2](https://github.com/UniXNU/NativeAdreno/blob/b686b9054f57d393c80195b82568a09f8ca106a2/NativeAdrenoSha256.cpp)，源文件原样SHAee624a48、头4c4f1a23，MIT；许可证与版权全文随FAT放在EFI/UniXNU/Payloads/SHA256-LICENSE.TXT。只复用无分配/无I/O的单次SHA算法，未引入Adreno硬件/板值。UEFI声明读取只读mu-nuwa-firmware/Mu_Basecore固定cfb93724a06ff86ff5ba971413368a7809ee42a5，实际28个依赖头逐项与git blob对比，未修改旧资料库。来源/哈希/命令见reports/file-read-audit/build-02.json。

clang++生成ARM64 COFF，lld-link /subsystem:efi_application /entry:EfiMain /nodefaultlib /timestamp:0；无动态imports。EFI app SHA **def33a4add6f162a5726bba050a4c143c8ba38ea25f436f46ce4331811bb469f**，6144B。自有内存helper仅提供上游源依赖的memcpy/memset，完整UEFI QEMU已运行目标PE中的实际实现，不是靠主机libc替代证明目标helper。

## 读取约束与阶段日志

文件EFI/UniXNU/Payloads/READTEST.BIN来自eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca，58335232B（0x37a2000）。GetInfo限4KiB，拒绝目录、超长/短结构、错误长度；应用使用正常AllocatePool(EfiLoaderData)取得完整缓冲区，不填写物理地址或扩大板级内存窗口。硬上限64MiB，本次申请58335232B；分配失败报告并返回。

每次Read最多1MiB、总调用最多4096，允许正数短读；拒绝提前EOF、返回长度超过请求和读取错误。读满后再请求1B确认EOF，随后对全部实际字节计算上游SHA并与固定期望逐字节比较；成功/失败均释放pool、关闭打开的file/root，保留屏幕30秒后返回固件。不执行数据文件，不写文件、不安装/修改协议、不关闭boot services。底层同步Read若本身阻塞，应用不能抢占它，不能把调用数上限写成硬件超时保证。

成功画面应同时具有actual sha256=eb66542c...、`PASS exact length, EOF and SHA256`和final bytes=0x37a2000。菜单新标题`NUWA FILE SHA PROBE - NO XNU EXECUTION`只能证明配置选择，不能单独验收文件SHA；旧embedded菜单保留，若走fallback须据实记录。EFI/BOOT/BOOTAA64.EFI也放置同一只读应用，供标准removable路径发现，仍不是OS。

## 离线验证

- 实际app + 软件UEFI协议回调，在AArch64用户QEMU执行13场景：正常全读、正数短读、提前EOF、错误长度、尾字节、pool失败、目录、读错误、缺文件、短GetInfo结构、过量返回、4096次限制、数据位翻转。全部返回预期结果且分配/关闭平衡。额外核对empty/abc/million-a三个SHA已知向量。host-cases-01.json和tests/file_audit_host.cpp记录原命令/源码，不代表真实硬件或完整固件服务。
- **完整AArch64系统QEMU+实际QEMU_EFI.fd**，标准EFI boot路径加载该ARM64 PE，实际FAT协议读完58335232B，56次数据Read及额外EOF检查，实际SHA与eb66542c一致，打印PASS，30秒后返回Boot0000 UiApp。最终fat-02已带MIT许可，并再次完成该完整路径。qemu-uefi-final.json/.log包含实际固件/EFI/FAT/日志SHA和命令；进程由外部50秒timeout结束，工具exit1不是应用失败或验收依据，PASS/返回标记才是阶段证据。这是**QEMU执行通过**，不是nuwa实机通过或该机安全加载策略通过。
- 全部受影响门控15项通过：新增严格数据用途元数据/禁止启用XNU项、缺新鲜preflight/录像在任何设备子进程前拒绝；原有10项回归保留。gates-final.json记输出。没有新设备查询/模式切换。

## 最终包与校验

FAT64MiB SHA b44d22bcf599414e29f940872506fc2215f359e4ff82228c0a010be3d0772166；真实数据、两份同EFI应用、唯一type=efi配置及MIT许可均从FAT完整抽取读回SHA一致，fat-02.json记命令。早期fat-01/包01缺随包许可，已由fat-02/包02替代，不可作为下一轮启动输入。

最终USB v3包 **18ebd83865eb0026655fddbfcea6a4f824c80cd4f65bf692528726d06a2389a8**，70266880B，out/trial-boot/file-read-audit-02/boot-file-audit-v3.img；固定报告reports/file-read-audit/package-02/package.json。FD2d606985和shim8a3b5476与本轮已实测运输包不变；相同v3头/cmdline和有界CRC封装。未重编固件，也没有新板级配置。

file_audit_package.py验证完整原固件profile/SEC保护、SHA/源身份、64MiB FAT和整包每一字节，strict新scope USB-FILE-SHA-OFFLINE只接受此报告及固定数据用途。通用试验脚本只对该严格校验scope允许xnu_included=true作为数据，其他scope仍禁止；不能靠编辑JSON开启XNU。运行时SHA结果待新一轮实机录像，不修改构建报告的runtime_verified/device_executed字段。

## 下一步与实机门

离线构建与新包已就绪，待本包新鲜连续录像≥120秒及必要时电源＋音量下恢复条件确认，启动前即时通知。然后刷新唯一nuwa/kalama、Android完成1/三分区基线，单次临时启动；观察后恢复固定原厂v4 boot并确认完成1及三SHA不变。OTG不用接，不自动第二次启动。当前手机最近真实恢复仍15:41:49，不将此后离线QEMU当成设备查询。

复验：bundled Python -B scripts/file_audit_package.py --validate reports/file-read-audit/package-02/package.json。UEFI/host复现命令见报告；源码构建build-file-read-audit.py --work out/<新目录> --output reports/<新文件>.json，拒绝覆盖。FAT脚本记录本次固定输出路径，重放须先选择新的输出名，不覆盖已验收fat-02；未宣称FAT目录时间戳跨重建确定性，实际完整SHA固定。启动门脚本仍trial-v4-firmware.py（历史名），该包要求header3。

完整OS资格仍保留loadable=false/空initializer：AMFI构造/start/once-guard/完整ABI、真实ADT和实际OS窗口待补。Heap/HOB缓存维护/坏链保护、ST FTS路线、board/bringup内存/身份及_verified全部不变；无flash/erase/改槽位。

公开契约：[UEFI 2.10文件协议](https://uefi.org/specs/UEFI/2.10/13_Protocols_Media_Access.html)支持LoadedImage来源卷上的只读文件操作；[NIST FIPS180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)是SHA-256算法规范，复用实现不声称FIPS认证。实际UniXNU Boot.c固定e553e46实现type=efi的LoadImage/StartImage，与本次独立应用衔接；AOSP/ABL运输依据沿用已实测v3记录。

实测更新：18ebd838第01轮已执行，原图新菜单returned Access Denied，文件SHA未实机通过；实际固件验签库/0x04拒绝policy与app无签名支持外部认证拒绝为首因，普通QEMU没有覆盖这一环境差异。Android于北京时间16:14:06完成1及三SHA不变，当前无需录像或Enter，不重复同包。以[本轮失败诊断](2026-10-24-file-audit-access-denied.md)和STATUS为准。
