# STATUS

更新：2026-10-25。**PROBE22实机通过真实RAMDisk→md0→原生根挂载路径，vfs_mountroot返回0，并在预定诊断终点停止，未进入恢复用户态。21:30:50 +08后验确认Android完成1、A槽、三分区SHA与试前一致，无待恢复任务。** 尚未启动iOS用户态，不将本轮当作完整驱动/长期运行资格。

## 当前实机结论

照片fc1c4ade8efa484b2e0362067e1d68b997f76477a297a6d41f77c79b1ecbe58b仅本地out/trial-evidence/entry-probe-22/user-screen.jpg。A035=0000000000000000，ID212绿、213暗；是原生挂载返回后主动停止，不是panic。196/197真实mdevadd、204/205 mdevlookup、206/207 setRootMedia、164/165 IOFindBSDRoot、166/167 vfs_mountroot调用/后继均亮，入口8黄，后续IOSecureBSDRoot168及用户态bootstrap9未到。184/185初始IOBSD等待返回，200/201默认介质等待暗，符合实际rd=md0分支，不再等待不存在的HFS IOMedia。A02A0/B6/C1；B保持6是root入口不更新DISPLAY_CHECK。

实载的是固定102MiB APFS恢复介质，经真实md0路径且原生根挂载返回0。还未直接读回运行时文件系统名称、root vnode内容或RAMDisk完整哈希；不把这部分未采集数据填成实测。192MiB运输本次已支撑菜单、内核和该路径，但不是192MiB运行时逐字节哈希认证或稳定性资格。

用户确认fastboot后，恢复流程只复位bootloader一次、临时加载固定原厂boot一次；21:30:22观察Android1，21:30:50后验确认A槽/boot_a、vendor_boot_a、init_boot_a三SHA与v30/preflight相同。无flash/erase/改槽或重复候选启动。用户此前要求暂不调查重启现象，此要求保持；当前无新重启归因结论。

## 有效包及输入

权威包reports/xnu-first-entry/entry-probe-22.json；镜像out/trial-boot/xnu-entry-probe-22-real-apfs/boot-xnu-first-entry.img，204,484,608B，SHA1b24ff82048f7ff29a6c6381889ba6806cce942a3fe79fa22f8db4256ad9397a。内核7f699af6e3f2ce70f0d55450661a0e70b62e2404cebc8194a47f693b2ec538d3，ADT15cf608bffbf62b450f0223fc61b3ee13b6e66c878bfe4a96fa2fd8907c67518，真实APFS payload d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a。

代码fb76965、启动记录b6a80c1；本轮实测提交号以git log为准。原固定FD/shim、31组件iOS16 prelink、Image4兼容及受审1GiB窗口/板值/TCR/IPSW身份不变。FAT192MiB实载kernel/ADT/APFS/菜单，-v rd=md0；冻结v1生产器不改，扩展诊断测量绑定实际根字节、参数和挂载后停止策略，不宣称Apple IM4M/TSS、硬件nonce或防重放。

离线21项串行任务通过：856透明差分、25Image4、6pthread、3停止、7根输入、34绑定及入口/MMU/向量/显示回归；独立内核重建、实际四文件回读和旧包21复验通过。唯一非透明hook在真实vfs_mountroot返回后0xfffffff0076730e8显示原生返回值并停止，不伪造成功、不进入恢复镜像用户态。

## 下一项与边界

用户最新要求减少类似阶段停止、一次尽可能推进更多。下一候选取消挂载后停止，标记继续记录并连续执行安全根/BSD收尾/首进程准备，唯一明确边界放在首次执行用户态之前；同时尽量读回运行时根身份，不再为每个观察点安排独立启动。恢复镜像不能直接当完整正常iOS root。完整系统根约4.73GB和Cryptex等后续输入需要真实存储/运输方案，不能默认扩大受审窗口或更换身份。

loadable/runtime_qualified与所有*_verified保持false；IRQ/计时器实际递送、驱动完整性、后续安全根和iOS用户态未验证。新试包独立离线验证、刷新日志/恢复条件及preflight后才启动。无push/新CI/原始媒体上传，资料库只读。无需重复启动22。

证据reports/xnu-entry-probe-trial/2026-10-25-v30/{screen,recovery,postcondition}.json；[v30完整记录](operations/2026-10-25-v30-real-apfs-mount.md)、[当前交接](operations/2026-10-25-mainline-handoff.md)。
