# nuwa / iOS16 主线交接（2026-10-26，PROBE27收尾）

## 接手状态

PROBE27照片核验与恢复收尾完成。264黄色/265绿色，A02A=0，A033=FFFFFFF005F48EF8（用户纠正末尾EF8，原图已复核），证明观察到了类型4表项已存在的分支；加载请求蓝色未见，不能把A02A0说成一次真实加载调用返回0。250文件头读取调用亮、251后继暗，Mach-O/dyld未到；缺少类型4空表项已不能解释当前观察停点。2026-10-26T00:16:10.211478+08:00恢复驱动确认Android完成1；2026-10-26T00:19:12.450574+08:00后验确认Android1/A槽/三分区SHA与本轮预检一致，恢复关闭，无待人工操作。按用户要求本轮到照片验证、文档与提交为止，不构建或启动下一候选。

原图62f86fe67cad0e6f0facb9a4262f78d5b26ee1947d5957a6ca7080ea9a76736d（4898922B）仅本地out/trial-evidence/entry-probe-27/user-screen.jpg；文字/采样reports/xnu-entry-probe-trial/2026-10-25-v35/screen.json。A02C=2，A02D/A030=2，A02E=0xF2/242、A032=2是跨尝试保留结果，不能当作本次未返回读取的errno。A02F0，未观察任务切换/签名或239释放守卫。候选静态0xfffffff005f48ef8为version3及五个非零回调地址，与读数相符；这不是运行时内存转储或解压执行证明。

本轮不是新增受审内存/身份硬停项；结束点是用户明确要求本轮核图后完成交接与提交。没有待恢复设备、待按键项或下一试包。下一轮先读AGENTS.md和STATUS.md，不重复启动27。

## 固定产物、提交与检查

包reports/xnu-first-entry/entry-probe-27.json；镜像out/trial-boot/xnu-entry-probe-27-fscompression/boot-xnu-first-entry.img，204484608B，SHA256 06913eaf3124e2634a2c9e654f66b374ece2caf2fed790dea8b6578b0d34955d。内核bca646e7498e6dc2b2efa7fa02a248c717067313eb0958707b8e27989175cdbc、58449920B；ADT34acf64bacffe26f602d62b3bc84b8d415bac1695c3cef832e6d9248926f3b34；APFS d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a、106954752B，192MiB运输、-v rd=md0。代码45a57de，启动ab489f4，收尾提交见本文件所属Git提交。

22项串行验证见reports/kernel-entry-probe/2026-10-25-v35/execution.json：1052透明差分、25Image4、6pthread、15exec边界、8FS启动模型、7根输入、36绑定及既有回归全部通过。独立重建reproduce.json逐字节一致；实际FAT读回内核/ADT/APFS/菜单及旧包26复验通过。loadable/runtime_qualified和板级_verified保持原值。正常OSKext加载分支只有模型边界检查，本轮照片观察的是已注册分支，不能声称正常加载实机成功。

当前有效代码链：5263bbb（26路径观察）→7153e06（26启动）→d5878f0（26实测修正与压缩属性）→45a57de（27条件初始化）→ab489f4（27启动）→本交接所属收尾提交。未push、未创建新CI。远端状态未由本次收尾刷新，不以本地ahead计数宣称远端实时状态。

## 设备恢复闭环

恢复结束：2026-10-26T00:16:10.211478+08:00，Android启动完成值1。后验：2026-10-26T00:19:12.450574+08:00，nuwa/kalama，槽位_a，与v35/preflight.json逐项相同。

| 分区 | SHA256 |
| --- | --- |
| boot_a | ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31 |
| vendor_boot_a | 5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23 |
| init_boot_a | 19e95d952ded5172e8a17bd1af907a8d6b08b29734881c370961b09bbaf78f96 |

证据reports/xnu-entry-probe-trial/2026-10-25-v35/{preflight,launch,screen,recovery,postcondition}.json。原图和有声/无声录像只留本地，不commit/push/上传CI。用户先报告fastboot，本代理随后只临时加载固定原厂boot并完成Android后验；不能将用户fastboot确认时间当作Android完成时间。

## 当前技术判断与下一项

下一轮先分界vn_rdwr→vn_rdwr_64中的mac_vnode_check_read调用/返回与VNOP_READ调用/返回，再按真实结果深入APFS/decmpfs读取、锁/等待与块I/O完成链。首要调查文件系统/压缩数据读取内部等待，次要调查独立的MAC读取回调；现有照片不能直接区分。先做边界观察是最小证伪，保留原生控制流，不跳过权限/认证、不强制成功。不得继续以缺文件或空注册表作为已证根因；不因采样未返回就虚构永久卡死时长、IRQ或具体等待对象。

源码D:/Code/PortingiOS/common/sources/xnu-ios16-full（只读），固定1b191cb58250d0705d8a51287127505aa4bc0789，APSL-2.0。vfs_vnops.c的vn_rdwr_64先做MAC读取回调，再调用VNOP_READ；decmpfs.c的类型4表项存在不证明取数回调或内部等待正常。候选表项地址只能作为本包偏移，不跨包照搬。

本轮新增正常组件检查helper为patches/xnu-8796-candidates/fscompression-oskext-start.S；在实际init exec前、vfsinit之后读取_decompressors[4]，仅空时请求OSKextLoadKextWithIdentifier，不直接调用donor入口、不写假表。264/265位于最后一行，A02A/A033为本版特有语义；发生panic/fault时优先按实际异常布局解释。不要把黄色264当作“本轮加载过”，也不要把A02A0当作实际API返回。

推荐下一候选继续原生流程，在读取内部增加最少调用/返回观察，必要时记录当前线程/等待标识的真实值；先从固定符号和指令核对偏移，完成串行回归、来源固定、逐字节重建与包回读，再按设备门决定一次临时boot。当前没有名为PROBE28的已完成产物，不凭本交接直接启动。

## 可直接执行的只读续接命令

```powershell
Set-Location -LiteralPath D:/Code/UniXNU-nuwa
git status --short
git log -6 --oneline
Get-Content AGENTS.md
Get-Content docs/STATUS.md
Get-Content reports/xnu-entry-probe-trial/2026-10-25-v35/screen.json
Get-Content reports/xnu-entry-probe-trial/2026-10-25-v35/postcondition.json
rg -n 'vn_rdwr_64|mac_vnode_check_read|VNOP_READ' D:/Code/PortingiOS/common/sources/xnu-ios16-full/bsd/vfs/vfs_vnops.c
```

需要复验旧包时才运行（不会启动设备）：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-27.json
```

不得因上述命令通过而自动再启动27；新候选就绪后仍需具体过程日志和已确认恢复路径、新鲜Android1/槽位/三SHA对照与即时通知。脚本/编译/模拟测试串行；已有条件仍有效时不重复问是否继续，条件确实缺失才核对。

## 保留边界与工作区

保持现有iOS16/8796基线，暂不全量上游迁移。PortingiOS是只读共享源码/资料库，当前XNU固定1b191cb58250d0705d8a51287127505aa4bc0789（xnu-8796.141.3）；设备脚本/补丁/报告在本仓。FD/shim、板内存/TCR、身份和*_verified不变，loadable/runtime_qualified=false。无flash/erase/改槽、push/新CI或原始媒体上传。启动前具体日志/恢复门、内存身份审阅边界保持；getvar unknown command / Variable Not found保留日志、重进一次fastboot后重试，不单独硬停，不把未知值当已确认。

D:/Code/uefi-nuwa维护独立固件；D:/Code/UniXNU-integration是固定框架集成检出。PortingiOS/common/sources/UniXNU旧缓存不等于当前集成树；本轮上游只读评估后，用户决定先稳定启动，再分批迁移，未切换生产输入。只读评估缓存out/upstream-review-v35不进入构建/提交。

当前工作树若出现历史未跟踪报告/脚本和旧媒体，不要git add -A；本轮只提交相关文字报告与文档。不得提交原图或构建产物，不改写历史。旧10月23/25日交接保留历史快照，均以本文和STATUS为准。

平台曾出现Daybreak提示；客户端日志确认是模型服务Turn error，本地只读命令已返回成功。不能据此判断某个源码文件有害或将该提示当作设备故障；具体后台命中规则不可见，不更改安全设置以继续工作。如需反馈，保留时间/提示由用户选择分享范围。
