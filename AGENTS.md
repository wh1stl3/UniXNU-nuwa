# AGENTS.md — UniXNU-nuwa 工作约定

本仓库唯一目标：**以 UniXNU 为底座，让小米 13 Pro（nuwa / SM8550）跑起 iOS 16**。
不是继续在旧的自建 P16 链路上打补丁。

## 1. 目录与只读边界

| 路径 | 关系 |
| --- | --- |
| `D:\Code\UniXNU-nuwa`（本仓库） | 设备仓工作目录：脚本、补丁、配置、报告、提交 |
| `D:\Code\uefi-nuwa` | 用户2026-10-22要求补齐的独立固件仓本地检出；固件源码在此维护，设备仓保留引用和证据 |
| `D:\Code\PortingiOS` | **只读资料库**。上游源码副本（`common/sources/`）、旧路线存档、DBC/分区/实测记录都在这里，只准读，不准写、不准提交 |
| `D:\Code\PortingiOSWithUniXNU` | **只读参照**。上一轮探针的产物（`docs/P0-PROBE-REPORT.md`、`device/observed/`），已拷入本仓库 `docs/inherited/`；不要再往那个目录写任何东西 |

上游源码**不复制进本仓库**，用路径引用或符号链接。路径大小写必须照抄真实名：
`UniXNU`、`UniXNU-sheng`、`xnu-ios16-full`、`ios-sweet`（最后一个全小写）。
Windows 不敏感，但构建全在 WSL 里跑，`/mnt/d/Code/...` **区分大小写**，写错报错点会离根因很远。

## 2. 版本管理

- `git init` 已完成，分支 `main`。**每个里程碑一个提交**，不攒大提交。
- 提交信息格式：

  ```
  [unixnu-nuwa][<area>] <一句话结论>

  [Change] 改了什么
  [Evidence] 凭什么（日志/文件:行号/命令输出）
  [Risk] 未验证的部分
  ```

  `area` ∈ `docs` / `build` / `kernel` / `firmware` / `loader` / `device`。
- **不提交**：构建产物（`build/`、`out/`、`*.img`、`*.fd`、`*.o`、`*.a`）、上游源码副本、`*.dtb` 原件、凭据（`.ghtoken`、序列号）、`~10 MB` 以上二进制。见 `.gitignore`。
- 不 `git push --force`，不 `--no-verify`，不改写已推送历史。
- 实测原始记录（`/proc/iomem`、`getvar` 输出）**要提交**，它们是证据，不是产物。

## 3. 硬停四类（写 `docs/NEED-REVIEW.md` 后停下等确认）

1. 修改任何 `bringup-plan.json` / `board.toml` 里与内存大小、基址有关的字段；
2. `fastboot boot` 我们自己的镜像、`flash`、`erase`、改槽位；
3. 新建或重写任何诊断 / 固件镜像；
4. 把任何 `*_verified` 置为 `true`。

停下时在 `NEED-REVIEW.md` 写：编号、背景、**至少两个候选方案**、各自代价、你倾向哪个及理由、需要用户批准的最小范围。只写「要不要继续」不算合格条目。

## 4. 人能等、机器不能停

- 只差**用户本人按实体键**的项（如长按电源强制重启演练）→ 写 `docs/PENDING-HUMAN.md` 记为待办，**继续下一项**，不要停。
- 只有**会改变设备内容且必须用户在场**的动作 → 写 `docs/NEED-HUMAN.md` 并停。
- 恢复类操作（`adb reboot`、`fastboot reboot`、`fastboot getvar`、TWRP 往返）在已授权范围内可直接执行，但**每次结束必须把设备送回 Android 并确认 `sys.boot_completed=1`**。

## 5. 文档机制（五个文件，各有唯一职责）

| 文件 | 职责 | 更新时机 |
| --- | --- | --- |
| `docs/STATUS.md` | 当前唯一真相：做到哪、下一步、已知坑 | **每里程碑全文重写**，只保留当下有效信息 |
| `docs/WORKLOG.md` | 时间线，**只追加不修改** | 每完成一项加一行：`时间 · 结论 · 提交号 · 证据路径` |
| `docs/DECISIONS.md` | 已定技术决策 `D-xxx`，含代码/实测证据 | 定一个写一个，不可删；被推翻时标 `superseded by D-yyy` |
| `docs/NEED-REVIEW.md` | 待用户拍板的 open 项 | 有则写、批则改 `approved` 并落地 |
| `docs/PENDING-HUMAN.md` | 只差人按键/在场的待办 | 随时追加，完成划掉 |

长篇分析放 `docs/operations/<日期>-<主题>.md`，`STATUS.md` 只留一句结论 + 链接。

## 6. 证据纪律

- 报告任何结论必须能指到：命令原文、文件路径:行号、日志片段、提交号。
- **QEMU / 模拟器 / 静态分析 一律不得写成「实机通过」**。三级用词固定：
  `静态检查通过` < `QEMU 执行通过` < `实机通过`。
- 拿不到的结论就写「未验证」，不要用「应该」「预计」填空。
- 上游有新提交时先 diff 再决定是否跟进，跟进要单开提交。

## 7. 驱动来源（用户 2026-10-22 补充）

- 驱动尽可能复用 UniXNU、其他开源项目及其他机型适配中的真实实现，优先核对同 SoC 来源。
- 记录仓库、固定提交、文件哈希、许可及依赖；复用通用实现与最小适配，不复制整棵上游源码。
- 同 SoC 不等于同板；MMIO、IRQ、触控 IC、面板、电源时序、donor 绑定等仍须 nuwa 证据，未知值写 TODO。
- 构建、符号闭包和实机验收分别记录；不以空实现替代硬件驱动。
