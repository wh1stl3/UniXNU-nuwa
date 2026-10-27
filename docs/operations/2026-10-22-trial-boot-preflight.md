# nuwa恢复、DT/initrd核对与首个试启动包

2026-10-22，所有旧仓/源树只读。用户持续授权可恢复fastboot前提下的镜像推送，并明确要求“先核对恢复路径和DT/initrd映射，再准备试启动包”。本轮只临时加载原厂boot作恢复；新固件包未执行。

## 已取得的实机恢复证据

最初ADB是enuma/M2105K81C/SM8250/kona；只读启动头明确标记为非nuwa输入，未重启或写入enuma。用户随后接入处于fastboot的nuwa。nuwa-fastboot.json记录product=nuwa、unlocked=yes、current-slot=a、is-userspace=no、secure=yes、max-download-size=805306368。

`fastboot reboot`成功返回，但设备重新出现在fastboot；nuwa-after-reboot.json记录A同时successful=yes、unbootable=yes，B successful=no、unbootable=no。boot-reason变量不支持。用户说明此前另一对话推送过镜像、没有按音量键；这只能作为背景，不作为故障根因的证明。

只读备份D:/Code/PortingiOSLegacy/nuwa/backups/recovery-20261020T121245314787Z/boot_a.img为原始nuwa v4 boot，201326592B/SHA256 ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31，与旧锁定记录一致。确认fastboot product后执行`fastboot boot <原始备份绝对路径>`：发送与Booting均OKAY；随后按DT model/compatible选择nuwa而非ROM可变vendor属性，确认nuwa/kalama/KALAMA及sys.boot_completed=1。命令、哈希与结果见stock-temporary-boot.json及identity-gate.json。此处仅“原厂boot临时恢复Android”实机通过；候选固件未执行、正常持久启动未修复、H-001硬挂按键演练未完成。

Android内整分区sha256sum又证明：当前boot_a=ef558db2…、init_boot_a=19e95d95…，分别与已存原始备份/锁定记录相同。不能归因于boot内容替换，A槽不可启动状态仍需后续处理；本轮没有改槽位或flash。bootctl不存在，不能据此判断Android已自动清除槽位标志。最后确认仍在nuwa Android且boot_completed=1。

H-002仅关闭“fastboot unlocked读取与返回Android”这一核验，不把实际flash能力视为实测通过；Android侧flash.locked=1与fastboot unlocked=yes的差异保留原始记录。

## 启动格式与映射核对

nuwa-android-headers.json是明确选择目标后读到的头：boot/init_boot/vendor_boot均v4；boot的kernel40417792B、ramdisk0，init_boot ramdisk2969050B，vendor_boot page4096、kernel_addr0x8000、ramdisk_addr0x1000000、dtb_addr0x1f00000。原厂v4 boot已被本机ABL接受；这不能证明任意v4固件包都会执行。

本轮原厂Android的DT保存于忽略目录out/trial-boot/nuwa-android-live.dtb（938804B/SHA e3b6e6767527b4543872ba09d21ea7275137ff6f4ddf2077103aeded2582ca34），原件不提交，报告只列允许的model/compatible/initrd属性，不输出种子或序列号。

当前和归档nuwa Android的initrd均为[0xb5fb2000,0xb7fff1d4)，完全落入固定Mu静态表的Kernel区[0xa8000000,0xb8000000)，类型Reserv、WRITE_BACK_XN。MemoryInitPei.c:92-98创建资源/分配HOB、:131-146把非HobOnly项加入MMU表。因此对**这个Android观测范围**，源码描述的初始映射和非分配属性相符。其长度并非512字节整数倍，现有发布器会拒绝把它当作FAT块设备；本轮未新建FAT/数据ramdisk。

不能推广到新候选的ABL放置：候选DT实际物理地址和initrd保留范围尚未观测；静态Kernel区并不保证新FAT负载安全。RamManager.c:59/99/111将EFI图中的RAM空隙映成Conventional，GetUsableMemoryRanges从固件RAM partition协议取范围，不解析FDT reserved-memory。只读发布器不添加保留HOB或分配页，无法单独防止新initrd被覆盖。详见mapping.json固定输入hash和41项静态表；safe_to_boot=false表示这些运行条件尚未验收。

固定上游nuwa.dtb自带旧linux,initrd属性、默认Resources/ramdisk仅5B；其mkbootimg默认base0x10000000，而参考仓使用base0。四份参考fastboot日志一个Booting OKAY、三个Load Error，但日志没有硬件身份、OKAY也不证明进入UEFI，不能据此验收nuwa的v1或归因所有v3失败。报告按来源事实保留。

复位库警告不是空实现：固定ArmPsciResetSystemLib.c:48起调用PSCI SYSTEM_RESET，:129-135对平台专用重启只回退ResetCold；它不处理Android reboot-to-bootloader cookie。故不能依赖EFI普通reset保证回fastboot；物理键演练仍H-001，未因本轮原厂恢复而勾选完成。

## 已生成的固件入口试启动包

采用复用原厂v4头的最小容器：只改kernel_size字段，原cmdline/OS版本/保留字段不变，4096B固定页；raw ARM64 BootShim112B+CI39764322744的FD3145728B作为kernel，共3145840B。无附加DTB，DT/原始Android ramdisk由设备现有vendor_boot/ABL流程提供；未填任何board地址，未引入新的XNU/FAT负载。

文件：out/trial-boot/firmware-v4/boot-firmware-v4.img，3153920B，SHA256 **12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9**。包目录含package.json、SHA256SUMS、README.txt，另有out/trial-boot/nuwa-firmware-v4-candidate.zip。二进制均在out不入Git。重建脚本scripts/build-trial-firmware-package.py校验原厂备份、FD和shim固定hash，拒绝覆盖已有输出。

package-inspection.json独立重新解析v4头、尺寸、ARM64 magic、内嵌FD SHA、零填充、仅kernel_size改动，通过静态检查。没有执行新候选，ready_to_execute=false保留ABL实际放置/SEC x0映射/DXE/BDS/键恢复待验收，不声称内核或iOS启动。其BootShim text_offset沿用已批准FD来源值；ABL对此的解释仍需实际日志，不擅自改为新的板值。

## 后续起点

先在已授权的临时启动范围内核对候选实际ABL放置与固件入口；任何屏幕/USB观察按真实结果记录。H-001只差实体键不阻塞软件项，但未完成之前不能写硬挂恢复通过。原厂boot临时恢复命令及hash可复用；A槽持久状态未改，常规reboot是否仍回fastboot不能隐去。若后续决定改槽位/恢复持久启动，按具体授权范围单独明确动作，不在本轮准备包时顺带执行。

新FAT initrd必须补充映射与保留，不能只靠发布协议；CI15运行provider/时钟/boot-progress/watchdog及NativePrelink编码仍在XNU负载前核验。board/feed不变、未置_verified=true，未将旧P16或参考6GiB策略平移。
