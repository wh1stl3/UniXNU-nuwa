# v30 / PROBE22：真实APFS RAMDisk，原生挂载后停止

> **实测完成：真实RAMDisk/md0路径到原生vfs_mountroot返回0，按预定终点停止；21:30:50 +08 Android1/A槽/三SHA后验一致，恢复关闭。** 原图fc1c4ade仅本地，196/197、204/205、206/207、164/165、166/167均亮，A0350、212绿、213暗；入口8黄、9用户态未到。运行时FS名称/root vnode及整盘哈希未读回，不扩大结论。下方未实测/待恢复为试前快照。

本轮21:30:22观察Android1，21:30:50后验完成，无flash/erase/改槽或重复候选。证据v30/screen.json、recovery.json、postcondition.json。用户随后要求减少类似阶段停止、一次推进更多进度：下一候选取消挂载后终点，保留累计标记，推进安全根/BSD收尾/首进程准备，仅在恢复镜像首次执行用户态前设置明确边界，不直接运行恢复程序。

## 当前依据与授权

PROBE21照片b412ba53确认初始IOBSD资源等待184/185已返回，默认IOMedia/Apple_HFS匹配构造208–211已达，200介质等待调用亮而201后继未到。实际无RAMDisk/根选择，缺介质为本轮明确推进对象；未到挂载。196/198调用暗、197/199绿由原生其他前驱到后继解释，不视为实际调用返回。

第一次恢复监测超时保留；用户确认fastboot后只复位bootloader一次、临时加载固定原厂boot一次，21:12:18 Android完成1、21:13:15 +08后验A槽/三SHA与本轮preflight完全一致。用户报告多次重启，但随后明确“继续新的临时启动 先不管这个重启”；因此暂停重启归因，继续新包。没有在该恢复等待期间启动第二候选，旧结果不写成新包成功。

## 固定真实根介质与运输

原清单phone iOS16.7.16/20H392的RestoreRamDisk，IM4P类型rdsk，container ac9634ab03f37f3a8e02bd3d14e5f886ded374245aaef5ef0d7d489da01e4d2b。payload d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a，106,954,752B，APFS NXSB/4096B块/26112块。固定Apple archive、BuildManifest、ZIP CRC和清单SHA384已核对；主机只读APFS挂载确认真实launchd/dyld/restored_external并卸载，失败和成功报告都保留。不是Apple签名、完整iOS或nuwa挂载资格证明。

PROBE22 FAT从64MiB增加至192MiB，容纳约58MiB内核和102MiB真实APFS；保持相同FD/shim、v3 envelope/CRC、只读BlockIo/FAT合同。未改板级内存表、dram_size/owned_memory_size、bootimg base/offset、IPSW身份或*_verified。扩大运输只读介质的实际固件内存范围/分配结果尚需nuwa过程日志，不从64MiB成功外推。固件若无法满足原有映射/容量检查必须保留错误，不绕过检查。

菜单只一项PROBE22，`args = "-v rd=md0"`，`initrd = "Payloads/root-restore.apfs"`；真实APFS字节在FAT内。ADT按相同受审参数生成，仅启用既有RAMDisk侧车16B零占位及临时存储标识；固定DarwinBoot d099354d按原实现加载并填实际地址/长度，原生IOFindBSDRoot据此mdevadd/md0查找。不是凭空写rd=md0或伪造UUID。

## 挂载返回后的诊断终点

新内核SHA `7f699af6e3f2ce70f0d55450661a0e70b62e2404cebc8194a47f693b2ec538d3`，58,421,248B。原1ae基线、31组件真实pthread、Image4兼容和root内部30点均保留。只在原生`vfs_mountroot`调用后的0xfffffff0076730e8增加显式诊断终点：记录原生x0到A035，0返回亮ID212绿，非0亮ID213红，然后停在probe_root_mount_stop。错误不改为成功，不执行被替代的后继指令，不进入恢复镜像用户态。

该hook是明确行为变化，单独从透明性比较排除，并强制三项真实指令模型：0返回、5错误、无视频均停在绑定endpoint并保留原始x0，视频标记对应实际返回值。它不模拟原生root mount成功；真实挂载尚待实机。原生vfs_subr.c:1154初始化根mount为MNT_RDONLY|MNT_ROOTFS，本包未改变该策略。停止发生在后续bsd_utaskbootstrap/launchd之前，恢复镜像内的restored_external不运行。

原生源码固定XNU提交1b191cb58250d0705d8a51287127505aa4bc0789，bsd/vfs/vfs_subr.c SHA b3f3090182bf5657cd01b03cbff881aea16bc2f3ee6bc09a8a325ab2405766c1（APSL-2.0）。vfs_mountroot遍历真实注册的vfsconf，实际调用各文件系统mount入口并返回原生错误；本包没有伪造该调用或把模型返回值植入出货代码。

## 真实启动测量与回归

保持scripts/nuwa_launch_context.py原字节，历史包可复验。新增nuwa_root_launch_context.py扩展同一诊断清单，加入真实root_ramdisk的长度/SHA和精确启动参数、挂载后停止策略及扩展生产器SHA；仍为无Apple签名的诊断启动测量。原nonce独立由主机CSPRNG生成，不宣称硬件nonce或防重放。

新ADT `15cf608bffbf62b450f0223fc61b3ee13b6e66c878bfe4a96fa2fd8907c67518`，清单SHA384 `5ba63ba27fb9d2fb42ce09c8a4dc746e03130b9bc696b4c0e6aba58a07f4dfd5bb70b17add1d7d3271f3170e34893b3f`。扩展生产器SHA36bcd82377a57ad97ca7ebe0ecc73b2cd5f21cb66cbb65633ce114a8165063ec。

root-launch/root-stop/root-inputs是v30强制打包证据。七项根输入对照包括真实输入、损坏根字节、删除测量、放行用户态、错误参数/生产器及非零占位；即使重新封清单摘要也拒绝。打包器必须从实际FAT回读kernel/ADT/APFS及unixnu.toml，再核对根测量、参数、initrd路径与挂载终点。

完整串行验证记录v30/execution.json；所有任务结束、独立重建和实际大镜像回读完成后才允许新临时启动。当前试前记录不等于已经挂载。本轮不上载原始媒体，不push或新CI，loadable/runtime_qualified保持false。

离线完成：21项串行任务通过，856透明差分、25Image4、6pthread、3root-stop、7root-inputs、34绑定及入口/MMU/向量/显示回归；独立内核逐字节一致。实际FAT回读kernel/ADT/APFS/菜单并重新测量通过，旧包21复验通过。包reports/xnu-first-entry/entry-probe-22.json；镜像204,484,608B，SHA1b24ff82048f7ff29a6c6381889ba6806cce942a3fe79fa22f8db4256ad9397a，FAT SHA52b012d8380e5b9020c79c5376a307c4cf047f3d29e144dc4be3f05e8f12f8cb。新鲜v30/preflight确认Android1/A槽/三SHA与v29后验一致，capture-confirmation保留用户最新原文。

## 启动与恢复门

按用户“继续新的临时启动”推进，实际启动前刷新preflight对比v29/postcondition，保持当前录像/菜单电源Enter/停屏采集与固定原厂恢复路径，即时通知后仅一次临时boot。画面同时需包含PROBE22菜单身份、原root标记、212/213和A035；ACK不作阶段结论。采集后绑定包22执行原厂临时boot恢复，再确认Android1/A槽/三SHA与本轮preflight相同。若人工恢复等待则记待办，继续离线工作，但不再启动新候选。

2026-10-25 21:26:08 +08：新鲜preflight通过，即时通知后镜像1b24ff82只执行一次fastboot boot，199692KB发送/Booting ACK。代码fb76965，等待菜单电源Enter后画面，本轮恢复后验未取得。不得将ACK提升为大运输、RAMDisk装载或APFS挂载实机通过；记录v30/launch.json。后续恢复命令绑定包22，后验以v30/preflight.json为基线。
