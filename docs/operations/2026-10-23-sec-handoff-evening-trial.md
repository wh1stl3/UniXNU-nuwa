# 晚间SEC handoff实测与恢复

更新：2026-10-23T18:36:32+08:00。用户明确“可以开始实机了”，沿已准备2d833461包只进行一次临时启动。本轮不再启动第二个包。

## 结果与证据

- fresh preflight核对实际nuwa/kalama、Android完成1、A槽、三分区与中午一致，严格包/FD/shim/原boot哈希通过；用户原有“可以，启动前通知我”配合当前开始实机指令，启动前已通知20秒录像。
- launch.json保存实际ADB进入bootloader、reset bootloader及fastboot boot路径；Sending3080KB/0.075s、Booting0.117s均OKAY，仅是接受证明。
- 120秒USB观察，共59条、最后seconds_after_ack=120.0；nuwa未回fastboot，ADB总数不能当作nuwa出现。该记录不是过程日志。
- 用户先误发中午照片，随后明确“图片搞错了”；user-screen.jpg SHA47637c0e是中午原图，不作为本次阶段证据。更正图actual-screen.jpg为9091065B、SHAf3cf95585d78cc4b41ac50850a6046b36ba7837634ff1949788e6c24a6914458，手机照片水印18:20，文件本身时间只作用户图片上下文，命令以UTC记录并转Asia/Shanghai。
- 更正图横幅Oct23 2026/06:50:55；可见memory/platform-hobs Success，before-entry-arg-hob list=BAB00000，after-entry-arg-hob data=BAB013B8，最后before-library-constructors。没有after-library-constructors或before-fv-decompress、DXE/SHENGMEM。

实机可证明新HANDOFF日志已执行，入口参数HOB创建返回非空数据，已打印库构造前日志。不能据此声称HOB全部语义正确、唯一阻塞PC或具体构造函数已定位，仍保留日志通道失效/异常等解释。不能再把本次称作“仍停platform-hobs”或认为误发旧图是加载了旧包。

## 恢复

用户收到保留画面后按键回fastboot请求，随后回复“已经回到Android了”。recovery.json检测实际nuwa Android，18:30:39 sys.boot_completed=1；本次恢复记录没有发送原boot或fastboot命令，不能写成本轮临时加载原boot恢复。设备如何回Android未取得独立按键/路径记录，不臆测。原boot ef558db2恢复备用仍校验通过。

postcondition.json再次核对nuwa/kalama、完成1、A槽，boot_a/vendor_boot_a/init_boot_a SHA与试前完全相同。无flash、erase或改槽。用户拍摄配合已完成；本轮视频文件未交付，仅照片及文字，不把120秒USB记录冒作120秒连续录像。

## 下一步

先离线检查实际SEC的构造调用顺序与四个库实现：BaseDebugLibSerialPortConstructor、ExtractGuidedSectionLibConstructor、ArmMmuBaseLibConstructor、LzmaDecompressLibConstructor。检查日志构造是否重置输出、提取器分配/HOB、MMU/cache与异常路径；如需细化日志，应在不重排、跳过或伪造成功的前提下只加单构造边界，独立构建与静态验收后再安排测试。

本轮未到DXE，SHENGMEM/载荷卷证据仍缺；不因入口HOB已返回而猜initrd地址或改内存窗口。XNU/iOS未进入。原下午预研及FAT→内核入口→原生根卷路线保留，今晚此包不含FAT/ADT/XNU。
