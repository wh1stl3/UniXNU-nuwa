# R-007 A：SEC阶段诊断构建与临时试启动

## 授权与固定范围

用户明确批准R-007 A：构建SEC阶段诊断固件、检查产物并准备临时启动包，按既有授权试启动，结束恢复Android并确认boot_completed=1。不扩展为v1/FAT/XNU/刷写/槽位或板内存修改，不置_verified。

固件源码在独立仓wh1stl3/uefi-nuwa的codex/nuwa-sec-trace，固定5e4a8c814b89f62a4ba2bc145249314fed5db787，父0a3a51a；只改Silicon/Silicium/SiliciumPkg/Sec/Sec.c，其LF SHA6af8dd4d45476fb3b0a387b8d85913765c6d6b1bcdab99f3c6275cc9a5b1efaa。完整Git tree/commit通过GitHub API身份核对发布，稳定分支保持。初次本地commit因新检出无作者配置未成功；随后仅该命令使用设备仓相同身份，未改全局Git配置。

config/firmware-sec-trace-profile.json从稳定dedicated profile派生，只改作用域/审批/来源证据、固件提交和SEC hash；31项输入逐项检查通过，四模块/两包/一条Darwin22 ABI patch及board/feed保护相同。本地未初始化子模块仅借固定只读缓存作输入校验，不是本地完整构建。工作流显式选择sec-trace，默认dedicated仍保留。

## 产物审计准备

验收器增加--require-sec-trace，读取实际SEC TE里的六个阶段字符串与状态/x0格式；存在字符串不代替调用/执行证明。同时修正NuwaBootMemoryDxe改名后仍比较旧名字导致漏走HOB/DEPEX检查的问题，强制嵌入PE与独立EFI至少一份hash相同。对稳定CI39805110487补查665项通过，记录reports/sec-trace/stable-artifact-recheck.json；原报告保持。

## 后续受控执行

构建成功后下载，核对固定输入、全inventory、四EFI/FV/DEPEX/HOB/PCD、SEC阶段字符串和BootShim长度/机器码。包仅复用哈希锁定原厂v4头，修改kernel_size并放入该轮实际shim+FD，不加DTB、FAT或XNU；原厂恢复镜像SHAef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31。

设备动作前按实际Android DT nuwa/kalama筛选，排除同时连接的enuma。进入bootloader后验证product=nuwa、unlocked=yes和槽位观测；按D-016重新进入bootloader隔离状态。临时boot后记录命令接受/USB模式与用户屏幕观察，各自分开；不把ACK写成SEC通过。结束先重进bootloader再临时加载原厂boot，确认实际nuwa Android sys.boot_completed=1。只差实体键记PENDING-HUMAN，恢复若需要用户在场按NEED-HUMAN记录。

当前仅源码/profile与审查工具准备完成，尚未编出这份诊断FD、未生成新boot容器、未执行设备。实际结果随本轮取证追加。
