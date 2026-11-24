# `/private/var` 与 LaunchServices 种子调查（2026-11-24）

范围：本地检索和公开文档摘录；未操作设备。公开来源主分支未固定提交时标明版本或分支。本地递归检索输出限制为前 220 条，未覆盖全部命中；未找到不等于不存在。

| 来源（仓库/文档 + 路径或 URL + commit/版本） | 对 `/private/var` 的做法 | 对 LaunchServices 库的做法 | 首次启动后是否需要二次重启 | 备注/代价 |
|---|---|---|---|---|
| [1] UniXNU [`scripts/make-data-seed.py` @ f61fd6c1](https://github.com/UniXNU/UniXNU/blob/f61fd6c1/scripts/make-data-seed.py#L40-L98)；本地同脚本 `D:/Code/PortingiOS/enuma/data-seed-ci-20261113/scripts/data-seed/vendor/unixnu/scripts/make-data-seed.py:40-98` | 新建 32 MiB APFS Data；复制 IPSW OS 挂载的 `private/var`，排除 `staged_system_apps`，保留符号链接和文件；创建 `keybags`、`mobile/tmp`、`tmp`、`run`、`containers/Bundle`、`containers/Data/System`、`containers/Shared/SystemGroup`、`containers/Temp`；打包、扩容。可选写 Setup 偏好。 | 脚本未见生成或拷贝特定 csstore 的代码。 | 未找到。 | 来源是 IPSW **OS** 模板而非已安装真机 Data；脚本要求保留后续使用的原 seed。 |
| [2] UniXNU [Userdata layout](https://unixnu.com/concepts/userdata) 与 [Skip Setup](https://unixnu.com/guide/skip-setup)，在线文档 | payload 输入 packed Data seed；`data-persist=1` 只读证明窗口，`=2` 可写；窗口位于 userdata 末尾。`seed-data-grow.py` 扩容；`--skip-setup` 修改 seed 副本。 | 未找到预置 csstore 的说明。 | 未找到。 | 文档原文：“A different size starts the Data volume over”；skip-setup 还创建四个 containers 目录。 |
| [3] [UniXNU-sheng `board.toml` @ e8937177](https://github.com/UniXNU/UniXNU-sheng/blob/e8937177309d88c93b305a57bad147fd5fac8a86/board.toml)；[payload.py @ f61fd6c1](https://github.com/UniXNU/UniXNU/blob/f61fd6c1/scripts/unixnu/payload.py) | SM8550 sheng iPadOS 27 配置 `data-persist=2`、`data_gib=215`、`skip_setup=true`；payload 将 seed 复制为 `scratch-data.img`，owner-Data 启动包括恢复持久 overlay 仍要求原 seed。 | 未找到。 | 未找到。 | 配置为 sheng/iPadOS 27，不是 nuwa/iOS 16 的实机结果。 |
| [4] [HackiOS thyme README，main](https://github.com/Liquidation0619/hakios-thyme-mi10s) | SM8250：RAM `/private/var` 在 run 结束经 `src/userland/var_store.c` 打包保存到 `darwin`；`var_store=1 ufs_write=1`。 | 文档称将 app 用 synthetic entry + bindfs 放入 `/Applications` 会使 LS 启动挂住；未找到预置 csstore。 | 未找到。 | 原文：“Persistence restore … The save works; the load at boot hangs”。报告三次写入 28672 B 回读一致，不等于恢复成功。 |
| [5] [HackiOS alioth README，2026-10-31](https://github.com/MrMoxing/ios-alioth) | SM8250 `darwin` 分区保存 var_store，双槽 2×2 GiB。 | 未找到。 | 未找到。 | 普通启动经 fastboot/RAM；数据卷保存另有 UFS 写入。 |
| [6] [Scion starlte README，main](https://github.com/Scion-Project/scion-starlte#privatevar-kept-between-runs-userdata) | `ufs_write=1 var_hfs=ufs_USERDATA_data`：USERDATA 上 HFS+；init 仅补 `etc/var.skel` 中缺失目录和文件，清空 `tmp`、`run`、`vm`，保留其他旧数据；失败退回 RAM。 | 未找到。 | 未找到。 | 原文：“what iOS keeps in `/private/var` is there at the next boot”；非 SM8550/SM8250。 |
| [7] [K90 annibale README，v0.2.2](https://github.com/iola1999/hackios-redmi-k90-annibale) | v0.2.0 起数据盘 APFS；README 称应用和文件跨正常重启保留。 | 未找到用户指定的“空 var → 重建 → 重启 SpringBoard 图标齐”出处、操作及耗时；不能将该说法作为已查证记录。 | 未找到。 | SM8750，版本不同；未找到拷贝真机 var 或预置 csstore 说明。 |
| [8] [JJTech0130/launchservices README](https://github.com/JJTech0130/launchservices) | iOS 16 数据库示例路径 `/private/var/mobile/Containers/Data/InternalDaemon/<UUID>/Library/Caches/com.apple.LaunchServices-<VERSION>-v2.csstore`。 | `csstore.py … dump` 用于逆向读取；macOS `lsregister -dump` 用于查看。原文：“a command line tool for reversing the LaunchServices database”。 | 未找到。 | 工具文档，非 Android 移植中的主机生成/移植案例。 |
| [9] nuwa `worktree-display-dsp/docs/nuwa-systemgroup-seed-20261122.md:31-37`、`nuwa-systemgroup-fix-result-20261122.md:5-13,15-27`，基线 `a2cd623d` | donor OS `/private/var` 无 `containers`；先前 seed 有空的 `/containers/Shared/SystemGroup`。后续 seed 预建 34 个 SystemGroup 子目录，另为 mobileactivationd 创建 `Library/ucrt`、`dcrt`、`internal`。 | 未找到该记录中预置 csstore 的证据。 | SpringBoard 重启与图标齐未在此记录中找到。 | 34 个目录无 MCM metadata；设备读数由主控转述，交互与持久化未证。 |

| [10] 本地 `.cache/ci-porting-134fd4e/tools/docs/devices/merlinx.md:205` | 文档称 macOS 生成的 Data seed 以读写方式挂载。 | 原文：“lsd completes its first LaunchServices build and SpringBoard draws the Lock Screen and Dock.” | 未找到。 | 记录为设备文档的转述。 |
| [11] 本地 `.cache/ci-porting-134fd4e/tools/docs/devices/dby-w09.md:523` | 音频 addon 使用 Data seed 目录。 | 文档称 `sheng-gpu-addon=1` 路径运行 `native_ls_store_drop`，“rebuilds the launchservices store once”。 | 未找到。 | 与音频挂载在同一门控内；原文描述不是本次设备验证。 |
| [12] 本地 `.cache/ci-porting-134fd4e/tools/docs/devices/raphael-gsjsjzhznsz.md:579,619`；[evidence @ 684cccb4](https://github.com/Gsjsjzhznsz/UniXNU-raphael/blob/684cccb40278bb5add0999e909af88e7f2eb407c/evidence/native-io-window.json) | 未找到。 | 原文：“active LaunchServices reseeding”；720 秒采样报告 LS 提供 store 回复，未到桌面。 | 未找到。 | 该行描述的是采样记录，不证明重建完成。 |
## 原文与可复制脚本摘录

[1] `make-data-seed.py:59-74,94-97`：
```python
for current, dirs, files in os.walk(source, followlinks=False):
    dirs[:] = [name for name in dirs if name != 'staged_system_apps']
    # 复制符号链接和文件；详见原脚本
for name in ('keybags', 'mobile/tmp', 'tmp', 'run', 'containers/Bundle',
             'containers/Data/System', 'containers/Shared/SystemGroup', 'containers/Temp'):
    (mount / name).mkdir(parents=True, exist_ok=True)
packed_ramdisk.pack(raw, base)
subprocess.run([sys.executable, ROOT / 'scripts/seed-data-grow.py', '--gib', str(args.gib), base, candidate], check=True)
```
[2] 原文：“The writable Data volume is separate from the userdata image. It comes from the Data ramdisk seed in the payload.”

[6] 原文：“On the kept volume init makes only the template's directories and files that are not there yet (`etc/var.skel`), and empties `tmp`, `run` and `vm`.”

## 共同做法

- 所查多个项目提供单独可写 Data/var，基于 seed 或模板初始化，而非将系统根卷直接作为可写 var [1][2][4][6]。
- 保留后续启动数据的方式分别是原 seed 加持久 overlay、存档到分区、或独立 HFS+；不能据此认定所有项目都已验证恢复成功 [2][4][5][6]。
- 多个来源补充预置目录或缺失模板文件；具体目录与实现并不相同 [1][2][6]。

## 有没有人预置 csstore

在本次已查看来源中，**未找到** Android 移植项目在主机生成或从真机拷贝并校验 UUID/版本后预置 csstore 的案例 [1]–[8]。`csstore.py` 原文为 “a command line tool for reversing the LaunchServices database”，展示的是 `dump`，不是生成 [8]。K90 指定记录未找到 [7]。

## 与我们现状的差异（事实）

- nuwa donor OS `/private/var` 的 `containers/` 整棵树不存在；官方生成脚本显式创建四个容器路径 [1][9]。
- nuwa 后续 seed 预置 34 个 `Shared/SystemGroup` 子目录、无 MCM metadata；[1] 脚本所列的是 `Shared/SystemGroup` 父目录 [1][9]。
- nuwa 后续 seed 单独创建 mobileactivationd 的 `Library/ucrt`、`dcrt`、`internal`；[1] 脚本列出的预建目录不含这三项 [1][9]。

状态：仅静态摘录；K90 原始记录及本地检索被前 220 条上限截断。