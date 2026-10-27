# 只读基座与 nuwa 设备仓集成审查

时间：2026-10-22 06:30（Asia/Shanghai）。仅静态阅读，无构建或设备操作。

## 基线与上游状态

本地 UniXNU HEAD 为 `75bc13dd34dc4e403826793739e316a264ce00dd`，tracked 工作树干净，证据见 `reports/patch-portability-8796-recheck/results.json`。
只读命令：

```powershell
& 'C:/Program Files/Git/cmd/git.exe' -c safe.directory=D:/Code/PortingiOSLegacy/common/sources/UniXNU --no-optional-locks -C D:/Code/PortingiOSLegacy/common/sources/UniXNU remote -v
```

输出 origin 为 `https://github.com/UniXNU/UniXNU.git`（fetch/push，blob:none）。浏览器读取 GitHub commits/main 与 GitHub API commits?per_page=1 均失败（Cache miss / not accessible）。**远端最新提交与差异未验证，未跟进上游。** 本报告只对上述本地 HEAD 成立；不能写成“已与最新上游同步”。后续先取得远端提交与 diff，再另排跟进提交，不运行 fetch 修改旧仓。

## 路径与覆盖方式

以下源码路径均相对只读 `D:/Code/PortingiOSLegacy/common/sources/UniXNU/`。

| 证据 | 结论 / 执行约束 |
| --- | --- |
| `scripts/unixnu/cli.py:17-24` | 原生支持 `-D`、`--out`、`--local-module`、`--uefi`；不需要把基座源码复制入设备仓。 |
| `scripts/unixnu/config.py:66-89,97-99` | 默认 out 位于基座内，而且 Context 初始化即写 state.json；连 status 也不能在只读基座上省略 `--out`。本仓尚无 board.toml，当前不会成功创建 Context。 |
| `scripts/unixnu/feeds.py:37-51,142-155` | 设备 feeds 覆盖基座同名条目；设备同名 patch 模块优先于基座。整个 `patches/xnu` 目录是模块，不是逐个文件合并。8796 覆盖必须提供完整有效补丁集，不能只放11项失败补丁，否则遮掉其余38项。 |
| `scripts/unixnu/tree.py:21-25,52-67` | 模块链接回来源；脚本依次从基座、设备复制到输出树。适配脚本可在本仓 scripts/ 同名覆盖。不能向输出树链接的只读模块写文件。 |
| `scripts/build-xnu-4k-baseline.sh:14-25,36-47` | 脚本会 clone 和 apply，并在输出树建立可写 XNU 工作树；本轮“任何 Git 写操作均禁止”下不能执行。不得把只读 XNU 树直接作为待打补丁工作目录。 |
| `scripts/unixnu/kernel.py:38-43`、`scripts/unixnu/cli.py:205-206` | 当前入口要求 xcodebuild 与 Xcode iphoneos SDK；入口提示仅在 macOS 开发测试。WSL 构建尚无可用验证链，不能因存在 bash 脚本就认定可构建。 |
| `scripts/build-xnu-4k-baseline.sh:41` | 应用顺序为 xnu/*.patch 再 NativePrelink/patches/*.patch；49项独立检查不覆盖后者两项及顺序依赖。 |

获批 board 后的路径形式（**仅说明，未执行**；这不是获准构建或镜像生成的命令）：

```text
# 若将来在可写布局中，基座与设备仓为同级：
python3 ./unixnu status -D ../UniXNU-nuwa --out ../UniXNU-nuwa/out

# 当前只读基座位于旧资料库；WSL路径大小写必须保持：
PYTHONDONTWRITEBYTECODE=1 python3 /mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/unixnu status -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out
```

`PYTHONDONTWRITEBYTECODE=1` 防止导入基座 Python 模块时在资料库生成 __pycache__。`status` 本身会写本仓 out/state.json，不能称为完全无写入。不得将上述真实布局误写为在旧基座目录使用 `-D ../UniXNU-nuwa`：那个相对路径不指向本仓。

## uefi-nuwa 布局方案（未创建）

在唯一可写根内建议保留独立固件工作目录 `D:/Code/PortingiOS/nuwa/UniXNU-nuwa/firmware/uefi-nuwa/`，后续由 `--uefi` 指向。设备仓仍是根目录，不混成基座仓。该目录将来承载独立固件仓，宿主准备前先处理忽略边界；本轮没有 mkdir、git init、clone、固件配置或任何镜像产物。

候选目录仅为规划：`Platforms/`（nuwa DSC/FDF及设备配置，具体包名待Mu-Silicium参照确认）、`Resources/`（上游工具/资源）、预检脚本与专有输入（后者不跟踪）。这些不是 board.toml 字段，也不声称已满足固件入口检查。`cli.py:66-71` 要求固件树有 `Resources/Scripts/mkbootimg.py`，空目录不能当有效固件树。

## 下一道门

先审阅 `docs/NEED-REVIEW.md` R-002 的精确 board 占位方案；不在本轮创建 board.toml，不填内存/地址/IPSW 未知项。与此同时已识别的后续工作是：8796完整补丁覆盖及 NativePrelink 两项审查、Darwin22接口审查、WSL工具链方案。feed切换、完整应用、编译、QEMU与实机均未验证。
