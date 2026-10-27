# v36 / PROBE28：原生读取边界，离线完成

## 结果与来源

在真实 Windows 主机 DESKTOP-S8M2VOR、D:/Code/PortingiOS/nuwa/UniXNU-nuwa 接续 a78e7591d90f3e442608e284083bb7acee6fc5cb。AGENTS、STATUS 和唯一最新10月26日交接已读取；原交接SHA256 a0b1db7f93b5c463f745f61982fc3ad718779325abaef3df787c768ea44cca3b。仓库没有 .agents/skills。初始已跟踪文件干净、28项历史未跟踪保留。本轮只写设备仓，不改只读源码、独立固件或其他项目，不创建第二写入者，不联系旧会话。environment.json记录主机、目录和来源。

PROBE28完成静态检查、Unicorn边界模型回归、独立重建及实际包回读，尚未实机。24项串行检查最终通过；其中1092透明比较、25 Image4、15 exec边界、11读取路径、38绑定。execution.json保留一次验证器版本名单缺36的失败及后续成功，不将初始失败抹去；execution-initial.json为失败当时快照。没有执行真实MAC策略、APFS/decmpfs主体或解压回调，不写成QEMU或实机通过。

固定公开源码：apple-oss-distributions/xnu，提交1b191cb58250d0705d8a51287127505aa4bc0789，xnu-8796.141.3，APSL-2.0。只读文件 bsd/vfs/vfs_vnops.c SHA256 ea24edd54bb7428d77ba880b1150b17cbbb6cca4518977536153f585552a6b9b，994行MAC检查、1006行VNOP读取。来源及指令见 read-boundary-source.json；工具 scripts/audit-read-boundary-source.py。原生输入仍为1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6。

PROBE27实测仍是264黄/265绿、A033 FFFFFFF005F48EF8、250亮/251暗。表项已有不能证明实际回调正常。首要调查读取主体/APFS/decmpfs内部等待，次要是独立MAC读取检查；当前证据不足以把两者区分。此排序是工程推断，不能由模型升级成硬件结论；不再将空类型4表项解释为当前根因。

## 原生指令与公共汇合点

| ID 调用/返回 | 原生调用PC | 目标 | 直接后继 |
| --- | --- | --- | --- |
| 266/267 | 0xfffffff0074669b0 | vn_rdwr → vn_rdwr_64 | 0xfffffff0074669b4 |
| 268/269 | 0xfffffff007466acc | mac_vnode_check_read | 0xfffffff007466ad0 |
| 270/271 | 0xfffffff007466b20 | VNOP_READ | 0xfffffff007466b24 |
| 272/273 | 0xfffffff00746c688 | VNOP_READ的真实 blr x8 | 0xfffffff00746c68c |
| 274/275 | 0xfffffff007466b08 | vn_read_swapfile备用路径 | 0xfffffff007466b0c |

0xfffffff007466ad0 是 cbnz w0, 0xfffffff007466b24；MAC拒绝直接到达VNOP_READ的后继。因此“在b24画绿块”不构成VNOP已返回证明。初版未配对候选 dfa16e70…被真实包装器模型抓到：MAC拒绝仍错误亮271。修正为同帧调用/返回配对；拒绝仍原样返回13，且270/271/272/273均暗。旧候选复跑预期失败原始stderr与命令见 post-build-validation.json，build-unpaired.json仅为失败负对照，禁止启动或当作有效包。

## 实现与观测语义

scripts/read_boundary_sites.py延续冻结exec路径。仅250文件头调用开始时初始化112字节诊断状态，保存当前TPIDR_EL1、vnode和调用栈归属；251后继清active。_current_thread的真实指令是 mrs x0, tpidr_el1; ret，已从固定二进制核对，未猜线程结构偏移。vn_rdwr保存的原始LR必须等于250+4；MAC/VNOP检查rdwr64 FP，文件系统分派检查VNOP FP。原生FP几何与176字节PROBE_SAVE在来源审计中固定。

每次header尝试清266..275的诊断旗和画面，并将5个返回槽初始化为全1。每个返回只有本次同帧调用置位后才记录，再清配对位。其他线程、其他帧和MAC公共汇合点不冒充成功。状态只面向当前单一首进程header调查；不声称支持任意并发exec的独立记录。

新十格位于x832..1295、y784..799，保留既有0..265编号；264/265仍在右侧最后一行。A034现在是最近读取阶段，A035是实际返回的低32位；调用尚未返回时A035显示全1。开始header后覆盖旧A034/A035含义；发生panic/fault时仍按真实异常布局解释。267是最外层rdwr64返回，正常完整返回后可覆盖内部阶段结果；亮格的成对关系用于回看内部经过。

保留真实MAC错误、IO_NOAUTH原生分支、swap路径、UIO残余量/错误处理和全部被替换指令的实际控制流；不强制返回0，不改权限、认证、板内存/TCR、iOS16/8796身份或_verified。loadable/runtime_qualified仍false。既有原生任务切换后的恢复用户态释放守卫未变，没有新增成功停止点。

最小实机证伪：268亮269暗时优先调查MAC读取内部；270亮271暗而272未到时调查VNOP包装器/分派准备；272亮273暗时优先调查实际文件系统回调及APFS/decmpfs/锁与块I/O完成链。先检查异常布局，不把“未见返回”写成永久卡死时长或具体锁/IRQ证明。266亮但MAC未到也需回查UIO准备等更早路径；274/275是原生swap分支，不预先排除。

## 离线验证与失败保留

scripts/test-read-boundaries.py从实际250入口执行vn_rdwr、vn_rdwr_64、VNOP_READ和真实间接分派指令；MAC及文件系统主体是明确API替身。11项覆盖成功、MAC拒绝、读错误、MAC未返回边界、分派未返回边界、swap、IO_NOAUTH、其他线程、其他帧、重复尝试和无视频。模型“pending”是显式停止在API边界，不能证明硬件正在等待。验证实际错误、SP恢复、状态清零、画面和无原生表/代码写入。1092透明检查另核对寄存器/NZCV/SP/后继与原生内存作用。缺新证据、删一项后重封SHA均被拒绝。

构建过程中修正了模板初始化先后和汇编常量定义阶段错误。失败汇编输入保留于out/kernel-entry-probe-36-read-boundaries/probe.S；post-build-validation.json完整保留同输入原始clang错误。最终输入在r3中构建，独立 out/kernel-entry-probe-36-reproduce 逐字节相等，reproduce.json固定SHA。未将初次构建失败当作硬件故障。Image4/pthread/绑定验证器仅补充明确revision36白名单，不删检查。后续串行检查复用已经通过且输入未变的前16项，补齐余项；最终24项均通过。

实际FAT回读PROBE28内核、ADT、APFS和菜单通过；旧PROBE27回读也通过。两个错误输入均按预期拒绝，见post-build-validation.json。原始媒体不复制、不提交或上传。

## 固定产物

- 包 reports/xnu-first-entry/entry-probe-28.json；镜像 out/trial-boot/xnu-entry-probe-28-read-boundaries-lf/boot-xnu-first-entry.img，204484608B，SHA256 7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f。
- 内核58462208B，54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07。
- ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0；测量上下文使用新nonce/内核测量，base.adt仍6270ea69…、板字段不改。
- APFS d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a，106954752B；192MiB运输及-v rd=md0保持。
- FD2d606985…、shim8a3b5476…沿用，独立固件仓无修改。无push、新CI、flash、erase或改槽。

## 设备门与续接

本轮没有任何设备命令；实际当前设备状态未重新读取。最后确认仍是v35/postcondition.json的2026-10-26T00:19:12.450574+08:00：Android完成1/A槽/三SHA一致。不能把该历史值称本轮新鲜预检。PROBE28未启动，PROBE27不重复启动。

R-014为open：尚未在本会话确认当轮菜单Enter后的可读/可拍画面及可按键恢复条件。只暂停下一设备启动，离线工作已完成。按AGENTS §3.2，不凭ACK或过去录像记录替代本轮日志门。取得条件后先用真实用户原文建立新鲜Android1/目标/槽位/三SHA预检并与v35后验对照，即时通知后才按既有范围单次临时boot。采样后沿原厂临时boot恢复，再确认Android1/同槽三SHA。新条件有效时不重复询问；不增加flash/erase/改槽或其他受审授权。具体命令见最新mainline-handoff，旧10月23/25交接只作历史参考。

## Git字节绑定修正与最终重封

提交42cf7d1时发现部分Windows报告为CRLF，Git存为LF，原包按CRLF计算的证据SHA不能用于干净检出。新版验证器在绑定前固定当前报告JSON为LF，构建/包/绑定与新增模型/来源报告输出显式LF。38项绑定复跑通过；23份包绑定报告的暂存Git blob SHA逐一等于包内值，再用这些Git字节替代报告运行完整验证通过，见git-evidence-binding.json。没有实际切换检出或创建第二工作树。仅修正报告传输字节，不改变内核生成控制流。

首包a8cb4595…保留为重封前本地记录；最终权威包是7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f，路径以entry-probe-28.json为准。重封与首包仅83字节、5页不同：4字节运输CRC，目录项14/15及22/23时间字段共40字节，FAT空闲簇97915中39字节。FAT表确认该尾簇为0/未分配；其工具生成来源未进一步核对，不宣称整镜像逐字节可复现。内核、ADT、FD/shim和菜单相同，APFS及全部有效载荷实际回读通过。差异与FAT几何见repack-difference.json；最终包回读命令/原始输出追加于post-build-validation.json。内核独立重建逐字节一致结论保持。不得再按a8cb首包安排设备动作。
