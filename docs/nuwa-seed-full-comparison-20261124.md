# Data seed 三方对比（2026-11-24）

只读检索、对比；未操作设备，未重建 seed。`?` = 未找到，不代表不存在。版本注明 main 的来源未固定 commit。其他机型及其资产只作参照，不用于 nuwa。目录是否预置与启动是否成功不构成因果关系。

## 三方总表（12 行）

| 来源 | seed 来源方式 | `/private/var` 目录清单出处 | per-app 父目录 | LS 相关预置 | 首次可用耗时 / 二次重启 | APFS 工具链 |
|---|---|---|---|---|---|---|
| [N] nuwa | donor OS var + 官方生成器 + 本地 SystemGroup 增量；8 GiB，SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247` | `docs/nuwa-seed-inventory-20261124.md:11-45`；完整表为旧挂载，当前 seed 以用户所给回挂事实为准 | `containers/Data/Application` 不存在；其他未证 | 34 个 SystemGroup 含 `lsd`、`lsd.iconscache`；csstore 未证 | 尚未达到交互；? | macOS 官方工具 + 本地重打包脚本，见同文 :7-9 |
| [O1] 官方实际生成 | [make-data-seed.py @ f61fd6c1](https://github.com/UniXNU/UniXNU/blob/f61fd6c1/scripts/make-data-seed.py#L59-L74) 从 donor OS 动态复制 var，再创建路径 | 脚本 `:59-74` 是动态遍历和显式列表，不是完整字面清单 | 显式列表不含 Application、AppGroup、PluginKitPlugin；donor 动态内容未知 | 未显式生成 csstore 或 lsd 子目录；donor 内容未知 | ? / ? | macOS hdiutil/diskutil，打包后 grow |
| [O2] 官方 skip-setup | [seed-data-skip-setup.py @ f61fd6c1](https://github.com/UniXNU/UniXNU/blob/f61fd6c1/scripts/seed-data-skip-setup.py#L64-L91) 原地编辑已有 seed 的副本 | `:87-91` 四个叶路径，不是完整清单 | 显式列表不含上述三项；输入内容未知 | 未见显式预置 csstore；输入内容未知 | ? / ? | macOS hdiutil，保留原 seed |
| [O3] 官方 QEMU fixture | [prepare-offline-data.py @ f61fd6c1](https://github.com/UniXNU/UniXNU/blob/f61fd6c1/scripts/prepare-offline-data.py#L1-L32) 在已有 fixture 添加目录，原文 “QEMU-only test input” | `DIRECTORIES` 为完整添加目标字面表，不是完整卷清单 | `containers/Data/Application` 有；AppGroup、PluginKitPlugin 未列 | 未列 csstore；输入内容未知 | 仅 QEMU fixture，不是设备记录 | macOS hdiutil/diskutil |
| [M] merlinx iPadOS | [data-seed.json @ fb616afa](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json)，macOS 脚本生成；记录称 lsd 首次构建完成 | JSON `directories` 为完整**规格**，非对该次设备镜像的逐项回挂 | `containers/Data/Application`、`Data/PluginKitPlugin`、`Data/InternalDaemon`；`mobile/Containers/Shared/AppGroup`，注意不是 `containers/Shared/AppGroup` | `db/lsd`、`mobile/Library/Caches/com.apple.LaunchServices`、`systemgroup.com.apple.lsd.iconscache/Library/Caches`；规格 files 未列 csstore | 原文见下，绘出锁屏和 Dock；耗时 / 二次重启 ?；触摸解锁未证 | [macOS](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/scripts/make-data-seed-macos.py) 与 [Linux](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/scripts/make-data-seed-linux.py) |
| [F] fajita | [README main](https://github.com/johnpanos/UniXNU-fajita/blob/main/README.md#data-volume-seed)，自定义 JSON、Linux / macOS 构建，非真机 dd | [data-seed.json main](https://github.com/johnpanos/UniXNU-fajita/blob/main/data-seed.json) 规格清单 | `containers/Data/Application` 有；其他两项未列 | 未列 csstore | 仅记录到 root mount 等待，无 UI 成功 / ? | Linux `mkapfs` + 自写 catalog + `apfsck` + packer；未找到 WSL 运行记录 |
| [S] 官方 sheng | [board.toml @ e8937177](https://github.com/UniXNU/UniXNU-sheng/blob/e8937177/board.toml)；官方 [设备打包文档](https://unixnu.com/zh/porting/packaging) `--init-data` 从 IPSW 初始 var 建 seed | donor 动态内容，未找到实机完整清单 | ? | ? | ? / ? | 官方 macOS seed 工具；设备是 sheng/iPadOS 27，非 nuwa |
| [D] dby-w09 | [porting.toml @ 715814d0](https://github.com/WQSQW/UniXNU-dby_w09/blob/715814d07840c817317892d5a585f4a3e769e343/porting.toml) 描述 scratch Data 和官方 fixture 路线，但未绑定具体本次 seed | ? | ? | 旧调查记录称 `native_ls_store_drop` 一次重建 store；本次 `.cache/ci-porting-134fd4e/tools/docs/devices/dby-w09.md` 未检到该词，原始实现及当次版本未核实，不能当已证 | 原文称锁屏呈现，input 完成条件称可解锁；耗时及第二次重启 ? | 官方 fixture；原具体生成机 ? |
| [R1] raphael 独立采样 | [porting.toml @ 684cccb4](https://github.com/Gsjsjzhznsz/UniXNU-raphael/blob/684cccb40278bb5add0999e909af88e7f2eb407c/porting.toml) RAM Data，具体 seed 来源 ? | ?；记录有 226 seed entries，未见字面清单 | ? | 720 秒 LS 回复，属于运行时而非 seed 预置；csstore ? | 720 秒 loading bar、无桌面；另有 Hello UI，触摸未集成；二次重启 ? | ? |
| [R2] raphael SWEET iOS16 | [FLASH-ROOT.md main](https://github.com/JohnLeeeeeee678/UniXNU-raphael/blob/main/FLASH-ROOT.md)：iPhone X 16.7.16 IPSW，Linux 合并 OS/cryptex 为 HFS+ root，并自定义 tweaks/activation；不是 APFS Data seed | 文档列四个容器叶目录，不是完整 var 列表 | 明列 Bundle、Data/System、Shared/SystemGroup、Temp；动态 donor 其余 ? | 未找到 csstore；[seed_activation.py main](https://github.com/JohnLeeeeeee678/UniXNU-raphael/blob/main/scripts/seed_activation.py) 写 data_ark | 项目称达到桌面；该记录未给首次耗时 / 二次重启；touch 未接 | `apfs-fuse` 读取 IPSW，`mkfs.hfsplus` 建 HFS+；不是 APFS seed 生成 |
| [T] thyme | [README main](https://github.com/Liquidation0619/hakios-thyme-mi10s/blob/main/README.md)：iPhone10,3 iOS 16.5；RAM `/private/var`，var_store 保存到 darwin，启动恢复挂住 | ? | ? | 无 csstore 记录；另记 bindfs app 导致 LS 启动挂住 | 原文称 icons、gestures、apps launch；首次耗时 / 二次重启 ?；恢复不成功 | `mkapfs.py` 用于 system.apfs，不是 Data seed |
| [Odin] Odin3 | [README main](https://github.com/darkplace/UniXNU-Odin3/blob/main/README.md)：macOS 输入 Data seed，Linux 构建其余介质 | ? | ? | ? | 原文约 14 分钟到 SpringBoard，锁屏；触摸未演示，二次重启 ? | Data seed 需 macOS hdiutil；Linux 制作其余卷 |

## 原文摘录与证据限制

- [O1] `for current, dirs, files in os.walk(source, followlinks=False)`；`'containers/Bundle', 'containers/Data/System', 'containers/Shared/SystemGroup', 'containers/Temp'`。显式列表之外可能来自 donor。
- [O3] “QEMU-only test input; not a restore or provisioned device.” 清单另列 `PersonaVolumes`, `preboot`, `root`, `Library`, `db/dslocal/nodes/Default/{users,groups,config}`, `mobile/Containers`。
- [M] [官方设备记录 @ fb616afa](https://unixnu.com/devices/merlinx)： “lsd completes its first LaunchServices build and SpringBoard draws the Lock Screen and Dock. The macOS-generated Data seed mounts read-write” 与 “swipe-to-unlock ... to be confirmed”。规格摘录：`["containers/Data/Application",0,0,"0755"]`、`["containers/Data/PluginKitPlugin",0,0,"0755"]`、`["mobile/Containers/Shared/AppGroup",501,501,"0755"]`、`["mobile/Library/Caches/com.apple.LaunchServices",501,501,"0755"]`。同一 revision 的 Linux 生成器只处理 `directories`，其 read-back 明查 `num_files == 0`；macOS 生成器另遍历 `spec.get('files', [])` 写 plist，**两个生成器输出不等价**；记录中的成功是 macOS seed，不能归给 Linux seed。
- [F] “On Linux, scripts/make-data-seed-linux.py builds it without root, FUSE or a kernel module. mkapfs from apfsprogs formats the image.” 实际检查限于 README 和规格，未在 WSL 执行。
- [S] 官方文档：“首次安装 可用 ... --init-data，从 IPSW 的初始 private/var 生成 APFS seed”。保留原 seed 的要求亦见该文。
- [D] 原文：“For a seed produced by the official fixture workflow” 和 “The lock screen with its clock and home indicator is now on the panel on hardware”；前者是条件描述，不能证明当次 seed 一定来自该 workflow。旧 survey `:18` 有 `native_ls_store_drop` 转述，但此次本地相应文件无该词，无法提供原文，保留未核实。
- [R1] `.cache/ci-porting-134fd4e/tools/docs/devices/raphael-gsjsjzhznsz.md:619` / [evidence @ 684cccb4](https://github.com/Gsjsjzhznsz/UniXNU-raphael/blob/684cccb40278bb5add0999e909af88e7f2eb407c/evidence/native-io-window.json)： “active LaunchServices reseeding ... 720s snapshots ... loading-bar RGB,no desktop.LS serves store replies”。这不是 csstore 预置，也不是桌面完成。
- [R2] “read OS.dmg, Cryptex1,SystemOS and Cryptex1,AppOS with apfs-fuse” / “assemble them into one 16 GiB case-sensitive journaled HFS+ volume”；另列 `com.apple.migration`、Setup 偏好与 activation。记录称 “Touch: not wired up yet”。
- [T] “iOS desktop ... icons, gestures, apps launch” 与 “The save works; the load at boot hangs”；同 donor 型号但 16.5 不同于 nuwa 16.7.16。
- [Odin] “Boot time | ~14 min to SpringBoard” 和 “touch not demonstrated”；“A macOS host for ... the Data seed”。不能把 SpringBoard 出现时间等同图标齐或可交互时间。

## 差异清单（10 条；影响面为涉及对象，不推导效果）

1. [N] 相对 [O1]：34 个具体 SystemGroup 对显式仅列父目录；影响面：容器目录内容，官方 donor 动态内容未枚举。
2. [N] 相对 [O1]：额外 `mobileactivationd/Library/{ucrt,dcrt,internal}`；影响面：该 daemon 目录。
3. [N] 相对 [O3]：缺 `containers/Data/Application`；fixture 列有；影响面：per-app 父目录，O3 仅 QEMU。
4. [N] 相对 [M]：Application 缺 vs 规格列有；影响面：per-app 目录。
5. [N] 相对 [M]：nuwa `containers/Data/PluginKitPlugin`、`InternalDaemon` 当前状态未核实；M 规格列有；影响面：插件及 daemon 容器。
6. [N] 相对 [M]：M 规格列 `mobile/Containers/Shared/AppGroup`；N 当前该路径未核实；影响面：mobile 命名空间，不等同顶层 containers 路径。
7. [N] 相对 [M]：N 有 `systemgroup.com.apple.lsd` 和 `lsd.iconscache`；M 规格列后者及其 Library/Caches，但未列前者；影响面：LS SystemGroup，N 子层完整情况未核实。
8. [N] 相对 [M]：M 规格列 `mobile/Library/Caches/com.apple.LaunchServices`；N 当前该路径未回挂确认；影响面：LS 缓存目录。
9. [N] 相对 [R2]：APFS 单独 Data vs HFS+ 组合 root；R2 显式写 `data_ark.plist` 的 Activated 状态；N 同路径状态未核实；影响面：文件系统和激活数据，不证明真实认证。
10. [N] 相对 [T]、[Odin]：N 已知 8 GiB APFS seed；T var 为 RAM 且恢复挂起；Odin 使用 macOS seed 和持久 page store；影响面：var 存储与恢复记录。

## 可复用做法（只列出处与成本，不评价适配或因果）

1. [M] 获取带 UID/GID/mode 的完整 JSON 目录规格；成本：逐项对照当前 seed 与 donor 版本，规格不等于当次镜像回挂。包括 Application、PluginKitPlugin、LS cache 路径。
2. [F][M] Linux `mkapfs` + catalog 编写 + `apfsck` + 自读回 + DBR 打包；成本：固定 apfsprogs `1bd1c1c2140d13d1b6d2e03379316572bee70aa3`、编译工具和 packer；Linux 脚本仅目录，不写 [M] 规格 plist，现有 donor 文件的重建能力未证，WSL 未验证。
3. [R1] 720 秒进程与 LS store 回复采样的记录方式；成本：原项目为手机采样，原始日志和完整历史源码未公开，无法直接复现；本轮无设备操作。
4. [R2] 同 iPhone X 20H392 的 HFS+ 生成与 activation 记录；成本：不同根卷架构，且 data_ark 是预置状态而非真实认证；N 对应内容未知，不认定为 N 缺失。
5. [Odin] 显式区分 SpringBoard 耗时、锁屏画面和触摸状态；成本：需要实际计时与输入观察，本轮未执行。

## 未找到与检索范围

- 没有找到任何所查移植来源预置或从真机复制 `csstore` 的案例；[M] 有 LS **目录**，不是 csstore。动态 donor 内容未全量列举，不能证明所有 seed 均无 csstore。
- 未找到 [M] 同次生成 seed 的完整回挂报告及具体启动耗时、二次重启；未找到 [D] `native_ls_store_drop` 的可核验原始版本；[R1] seed 字面清单、[T] var 清单未找到。没有找到上述记录中从真机 `dd` Data seed 的证据。
- 没有找到 Linux 生成器在 Windows/WSL 上的实际运行记录；[F][M] 只声明 Linux，且不证明能原样重建当前 donor seed。未找到图标齐/可交互首次耗时与是否第二次重启的原文。
- 搜索了用户指定的本地两份 survey/inventory、`nuwa/.cache/ci-porting-134fd4e/tools/docs/devices` 的线索，以及公开 GitHub、unixnu.com 和搜索词 `native_ls_store_drop`、`APFS seed linux` 等；最初跨 `D:/Code/PortingiOS/nuwa`、`enuma`、`docs` 递归 `rg` 因主机无 `rg` 失败，**未完成全工作区/out/.cache 全量搜索**。既有 survey 自述前 220 条截断，不能作为穷尽证明。来源 main 未固定 commit，状态可能变更。

状态：仅静态摘录；未改 seed、未碰设备、未提交 Git。
