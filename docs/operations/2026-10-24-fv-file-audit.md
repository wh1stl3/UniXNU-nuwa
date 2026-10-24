# 固件内ReadyToBoot文件SHA候选

背景：18ebd838外部EFI条目在新菜单返回Access Denied；实际固件验证库/0x04拒绝policy及app无签名支持认证拒绝首因，但精确API/runtime SecureBoot值未捕获。手机已于北京时间16:14:06完成Android恢复/三SHA不变。当前继续离线，不重复同包，不关闭或放宽认证策略。

## 实现和来源

固件新增NuwaFileAuditDxe（GUID45b28639-79a9-456d-afc5-edcfe78cdae1），只由设备仓新profile fv-file-audit的0020 selection补丁纳入DSC/FDF；固件默认选择不变。固定源wh1stl3/uefi-nuwa@a155c495c863e06d400b515315e3b8f7791dc308，前一实现2457860，后续补空枚举时不FreePool(NULL)并增加测试；源及docs/nuwa-file-audit.md已推送。MIT SHA外部app路径不再作为本诊断入口。

ReadyToBoot回调只执行一次，关闭自身事件；最多64个SimpleFileSystem，仅以READ打开固定READTEST.BIN。只有NOT_FOUND可略过，其余Open/协议错误明确返回；两卷含同名文件则先拒绝。GetInfo≤4KiB，拒绝目录/错长度/结构；普通AllocatePool(58335232B)，每次Read≤1MiB、最多4096次、允许正短读、拒绝提前EOF/超长返回，额外1B确认EOF。使用固件已有BaseCryptLib Sha256HashAll，比较固定eb66542c目标，屏幕打印进入/唯一文件/读进度/实际SHA/PASS/退出，保留30秒再继续。源数据仅普通文件，不执行分析MachO/内核，不关闭boot services，不读写未知物理地址/分区。

本候选保留SecureBoot库、拒绝policy和默认key源码，不改变认证函数。FV代码沿已有固件链调度，不以外部文件身份调用LoadImage；这改变诊断入口位置，不把数据文件变为可信OS。源来源为当前设备自有实现，复用固定UEFI协议与现有SHA库，不移植其他机型板值。

## 离线验收和CI要求

实际C代码编译ARM64 COFF通过。软件UEFI回调夹具使用实际C源交叉编译，在AArch64用户QEMU完成19个文件/卷/crypto场景及ReadyToBoot只执行一次，池/文件句柄清理平衡；包括正常/短读/EOF/尾字节/长度/目录/缺文件/读错/超返回/调用上限/hash错/重复文件/超卷数/协议失败/crypto失败/GetInfo错误/空枚举。该夹具crypto回调使用旧固定NativeAdreno SHA，**目标固件链接自己的BaseCryptLib**，两者不混称同一实现执行证明。源/命令/SHA见reports/fv-file-audit/host-tests.json。

profile固定57项输入、12项补丁、15项后哈希；前11补丁与upstream-merged完全一致，除选择DSC/FDF之外原post-image哈希全部相同，原Heap/HOB坏链/缓存维护不变。新增锁定验证库/头、SecureBoot-Keys.inc和DSC映射。SOURCE_DATE_EPOCH显式沿用真实旧固件6176a822的1792776324，避免仅因新提交日期改变SEC时间串；不改旧profile时间策略。profile-check-final.json记录静态检查，不能替代实际产物。

CI新增fv-file-audit选择，默认仍upstream-merged。实际FD验收继承全部原guard检查，并要求新GUID/驱动PE/DEPEX和屏幕marker、SEC SHA7192fd3f逐字节相同、实际构建报告认证库/0x04介质策略、驱动map存在Sha256HashAll。若编译或上述检查失败先保留证据并修复，不能跳过新守卫称通过。当前CI待执行/验收，新临时包尚未生成，无新实机。

独立新profile未来继续沿USB v3运输普通数据FAT；需重新打包但不执行外部EFI app，菜单应改退出动作避免再次Access Denied干扰。实际构建验收后再固定FD/SHA和数据FAT，新增试验scope保持录像/恢复门；当前不借旧许可启动。

复现静态：bundled Python -B scripts/check-fv-file-audit.py --output reports/<新文件>.json；软件夹具test-fv-file-audit.py --work out/<新目录> --output reports/<新文件>.json。CI build-firmware-candidate.py --profile fv-file-audit仅在受控Actions新树执行；固定源和补丁不复制到旧资料库。Heap/板值/内存/身份/_verified不改，当前无需用户按键/录像。

## 首轮实际构建与LTO验收修正

CI40078257763/source2b7328b固件编译成功，最初artifact inspection失败于要求map出现Sha256HashAll包装名；保留initial-ci-failure.json，不改原CI状态。实际LTO将包装函数及ReadAndHash/AuditVolumes内联进Ready，保留sha256_block_data_order。检查已改为实际PE/map的Ready→压缩函数直接BL、非平凡函数体及驱动专属实际链接报告的真实BaseCryptLib/OpenSSL（拒绝Null库），不通过删检查放行。

下载实际产物独立检查通过：FD52ab071eaa6cdb06f1902464923f1fab11f55d169f0494a58165ceed8894be51/3145728B；shim8a3b5476/112B，SEC7192fd3f与上一实测完整字节相同，全部原Heap/HOB/cache守卫、7模块GUID/PE/DEPEX/屏幕marker及原验证库/0x04拒绝策略通过。实际Ready在RVA18fc/192c/1994/19cc四次直接调用RVA36d8的572B SHA函数体，完整哈希见crypto-linkage.json；这只是静态实际链接，不宣称目标crypto实机执行。

新增移除所有SHA调用/把SHA体伪造成4字节stub的拒绝回归，避免把包装名消失当实现缺失或把占位函数当真SHA。当前独立重验报告artifact-inspection-local.json与真实初始CI失败分别保留；将用修正后的验收重新触发CI取得完整绿色结果，固件源/模块实现本身未改。

## 数据卷和候选包

新数据FAT64MiB SHA5ea19e90fa1b44d0f79041663e1b91a9d9e274c34a8beda594ac009d762fb9ed，只含READTEST.BIN（58335232B/eb66542c）与60秒退出配置，实际两文件完整抽取SHA一致；没有外部EFI app或XNU执行项。菜单只退出，校验由ReadyToBoot自动执行，不要求键盘或Enter。config/fv-file-audit/unixnu.toml、build-fv-audit-data.py和data-01.json记录输入及命令。

首轮本地重验包6b3e5bfd3a8e1d5a8e8abbda3268872a6fc69b287c144df70387012d46a41dc7/70266880B已完整重建/逐字节读回，reports/fv-file-audit/40078257763/package.json；尚不安排实测，待修正验收CI完整成功后固定最终包。新scope FV-FILE-SHA-OFFLINE严格验证源profile/原全部保护/最终FD/数据卷/数据用途和禁止外部app；无新鲜录像或preflight时在设备子进程前拒绝，不能编辑元数据重启XNU。当前无新设备查询，最近Android恢复仍16:14:06。

## 最终CI和独立验收闭环

第二轮CI **40080439083/source dbbdc02247df0bba08183df97f3775286ef96271 success**，完整编译/检查/产物上传通过，ci.json保留真实状态与步骤。独立下载后重跑严格检查通过：710项inventory、7模块，FD52ab071e与首轮编译结果逐字节相同；SEC7192fd3f与此前已实测固件完整相同，Heap/HOB/cache守卫不变。驱动实际BaseCryptLib/OpenSSL（非Null）、Ready四次BL→572B压缩体、原镜像验证库/介质0x04拒绝策略通过。acceptance.json与crypto-linkage.json保留具体SHA；认证策略源和产物均未放宽。

最终严格包报告 **reports/fv-file-audit/40080439083/package.json**，对应out/trial-boot/fv-file-audit-40080439083/boot-fv-file-audit-v3.img，SHA **6b3e5bfd3a8e1d5a8e8abbda3268872a6fc69b287c144df70387012d46a41dc7** /70266880B。与首轮本地包镜像内容相同，但使用第二轮绿色CI的来源报告；旧首轮CI仍失败，不改其结论。23项设备scope/旧guard/新真实SHA拒绝回归通过；本轮离线无新手机操作。

目前只待本包新鲜录像≥120秒和必要时按键恢复条件确认；确认后刷新preflight并即时通知再单次临时启动。检查自动在ReadyToBoot执行，不要求用户按Enter/接键盘或OTG；重点录像NUWA-FV-FILE enter/unique/read/actual SHA/PASS/exit。菜单只是退出，不能以菜单或USB ACK验收。目标SHA和完整OS资格仍分别处理，不能由固件静态验收称nuwa文件SHA或iOS通过。

复验：bundled Python -B scripts/fv_file_audit_package.py --validate reports/fv-file-audit/40080439083/package.json。首轮compile-success/check-fail日志和第二轮green/local-independent记录均保留，后续启动另建reports/fv-file-audit-trial/<新轮次>/，不可复用18ebd838 preflight或录像许可。
