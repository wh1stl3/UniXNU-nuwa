# STATUS

更新：2026-10-26。PROBE27照片核验与恢复收尾完成。264黄色/265绿色，A02A=0，A033=FFFFFFF005F48EF8（用户纠正末尾EF8，原图已复核），证明观察到了类型4表项已存在的分支；加载请求蓝色未见，不能把A02A0说成一次真实加载调用返回0。250文件头读取调用亮、251后继暗，Mach-O/dyld未到；缺少类型4空表项已不能解释当前观察停点。2026-10-26T00:16:10.211478+08:00恢复驱动确认Android完成1；2026-10-26T00:19:12.450574+08:00后验确认Android1/A槽/三分区SHA与本轮预检一致，恢复关闭，无待人工操作。按用户要求本轮到照片验证、文档与提交为止，不构建或启动下一候选。

原图62f86fe67cad0e6f0facb9a4262f78d5b26ee1947d5957a6ca7080ea9a76736d（4898922B）仅本地out/trial-evidence/entry-probe-27/user-screen.jpg；文字/采样reports/xnu-entry-probe-trial/2026-10-25-v35/screen.json。A02C=2，A02D/A030=2，A02E=0xF2/242、A032=2是跨尝试保留结果，不能当作本次未返回读取的errno。A02F0，未观察任务切换/签名或239释放守卫。候选静态0xfffffff005f48ef8为version3及五个非零回调地址，与读数相符；这不是运行时内存转储或解压执行证明。

包reports/xnu-first-entry/entry-probe-27.json；镜像out/trial-boot/xnu-entry-probe-27-fscompression/boot-xnu-first-entry.img，204484608B，SHA256 06913eaf3124e2634a2c9e654f66b374ece2caf2fed790dea8b6578b0d34955d。内核bca646e7498e6dc2b2efa7fa02a248c717067313eb0958707b8e27989175cdbc、58449920B；ADT34acf64bacffe26f602d62b3bc84b8d415bac1695c3cef832e6d9248926f3b34；APFS d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a、106954752B，192MiB运输、-v rd=md0。代码45a57de，启动ab489f4，收尾提交见本文件所属Git提交。

22项串行回归通过：1052透明比较、25Image4、6pthread、15exec边界、8FS启动模型、7根输入、36绑定及入口/MMU/向量/显示回归。独立重建逐字节一致，实际包回读及旧26复验通过；模型未执行真实OSKext生命周期或解压函数，不提升为实机加载通过。

下一轮先分界vn_rdwr→vn_rdwr_64中的mac_vnode_check_read调用/返回与VNOP_READ调用/返回，再按真实结果深入APFS/decmpfs读取、锁/等待与块I/O完成链。首要调查文件系统/压缩数据读取内部等待，次要调查独立的MAC读取回调；现有照片不能直接区分。先做边界观察是最小证伪，保留原生控制流，不跳过权限/认证、不强制成功。不得继续以缺文件或空注册表作为已证根因；不因采样未返回就虚构永久卡死时长、IRQ或具体等待对象。

保持现有iOS16/8796基线，暂不全量上游迁移。PortingiOS是只读共享源码/资料库，当前XNU固定1b191cb58250d0705d8a51287127505aa4bc0789（xnu-8796.141.3）；设备脚本/补丁/报告在本仓。FD/shim、板内存/TCR、身份和*_verified不变，loadable/runtime_qualified=false。无flash/erase/改槽、push/新CI或原始媒体上传。启动前具体日志/恢复门、内存身份审阅边界保持；getvar unknown command / Variable Not found保留日志、重进一次fastboot后重试，不单独硬停，不把未知值当已确认。

唯一续接入口：[2026-10-26主线交接](operations/2026-10-26-mainline-handoff.md)。本轮证据目录reports/xnu-entry-probe-trial/2026-10-25-v35，恢复后验时间为10月26日。
