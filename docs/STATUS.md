# STATUS

更新：2026-10-25。**PROBE22已于21:26:08 +08单次临时boot ACK，等待菜单电源Enter后的实机画面；不能据ACK声称192MiB运输、APFS装载或root挂载通过。** 代码fb76965，新鲜preflight确认Android1/A槽/三SHA与v29后验相同，按用户最新“继续新的临时启动 先不管这个重启”执行。当前本轮恢复后验尚未取得，不启动第二候选。原PROBE21确认初始IOBSD等待返回、停在默认IOMedia等待，尚未挂载。

## 最新设备实测

PROBE21照片b412ba53c34999701b9c351d277d3e0e5defa98e64d5ad9eb4d9fa8d37f906ea仅本地。184/185初始IOBSD资源等待均亮，208–211默认Apple_HFS IOMedia构造均亮，200调用蓝/201后继暗，挂载入口8暗。196/198暗、197/199绿由原生其他前驱直达后继解释，不视为mdevadd/waitQuiet返回。A02A0/B6/C1，无新panic/fault。

首次恢复监测超时未加载原厂boot，用户回fastboot后只复位bootloader一次、临时加载固定原厂boot一次；21:12:18观察Android1，21:13:15 +08后验确认Android1/A槽/三SHA与试前一致。该恢复待办已关闭。用户报告重启数次，未归因；最新明确暂不调查并继续新临时启动，已按该指令执行。当前PROBE22新鲜preflight也确认Android完成1/A槽/相同三SHA。

## PROBE22实际输入与离线结果

权威包reports/xnu-first-entry/entry-probe-22.json。镜像out/trial-boot/xnu-entry-probe-22-real-apfs/boot-xnu-first-entry.img，204,484,608B，SHA1b24ff82048f7ff29a6c6381889ba6806cce942a3fe79fa22f8db4256ad9397a。内核7f699af6e3f2ce70f0d55450661a0e70b62e2404cebc8194a47f693b2ec538d3；ADT15cf608bffbf62b450f0223fc61b3ee13b6e66c878bfe4a96fa2fd8907c67518；真实102MiB APFS payload d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a。

同一固定phone iOS16/20H392 RestoreRamDisk已核对ZIP/Apple清单摘要，主机只读APFS检查真实launchd/dyld/restored_external后卸载。当前FAT由64增至192MiB以实际携带内核与根镜像；FD/shim/board内存表、1GiB窗口、IPSW身份、bootimg base/offset不变。菜单-v rd=md0及initrd路径、ADT真实RAMDisk零占位由原DarwinBoot填实际地址/长度，根镜像和挂载停止策略写入扩展诊断测量，未改冻结v1生产器。

21项串行任务通过：856透明差分、25完整Image4、6pthread、3挂载停止、7根输入、34绑定及入口/MMU/向量/显示/同ADT回归。独立内核重建逐字节一致，实际FAT回读kernel/ADT/APFS/菜单并重新测量通过；旧PROBE21复验通过，历史报告不改。

## 运行边界与续接

原生vfs_mountroot返回后在0xfffffff0076730e8停止：A035显示真实返回值，ID212绿为0，213红为非0；不把错误改成成功，不进入恢复镜像用户态。此单个hook是显式行为变化，独立测试并从透明性集合排除。其余root内部标记182–211保持。尚无PROBE22实机结果，192MiB运输和实际APFS挂载仍待验证；不能把主机只读检查或离线执行写成实机挂载。

执行新启动前即时通知，仅临时boot一次；图像采集后恢复固定原厂boot，确认Android1/A槽/本轮三SHA。人工恢复等待继续离线工作，但恢复未确认不启动第二候选。loadable/runtime_qualified及所有*_verified保持false，未flash/erase/改槽，无push/新CI/原始媒体上传。

当前提交cd21655之后的v30里程碑以git log为准；上一实机资料reports/xnu-entry-probe-trial/2026-10-25-v29/，新预检v30/preflight.json。[v30完整记录](operations/2026-10-25-v30-real-apfs-mount.md)、[当前交接](operations/2026-10-25-mainline-handoff.md)含SHA、source pin、指令和未验证边界。
