# nuwa Apple logo milestone — 2026-11-22

本记录的实机读数及对照调查均为主控转述；未由本记录作者独立复核，状态为 self-checked（记录整理），非独立 verifier 验收。

- **现象**：约 290 秒诊断页消失，出现 Apple logo 并保持至少 560 秒；底部横幅仍在且持续刷新。横幅仅在 `display.bound==0` 时绘制，因此其存在证明显示所有权已交出，但不识别提交 logo 的进程。来源：主控转述的用户实机观察和横幅绘制条件；状态：实机转述 / 仅静态审查。
- **原因与修复**：先前包的 ADT 缺 `/chosen/display-scale`；提交 `ba94aa2` 补入 4 字节 LE `3`。此前 SpringBoard 稳定崩在 FrontBoardServices `FBSDisplayMode`，PC 低位 `0xbd4`；补后不再出现这一崩溃。outer SHA-256 `02850b20ceabd842aabd4c05090bc2ec9f42a672359ddb2cd936bac4842bd068`，ADT SHA-256 `ae717c64726d95b0edddf6a3316edc897f2e8a61ca9d3c9c29db2e72f649ec2d`。来源：主控转述崩溃定位与实机对照；[主机打包记录](nuwa-resume-display-scale-20261122.md)。状态：实机转述 / 主机 self-checked；面板物理 scale 未证。
- **ADT 对照**：三份 ADT diff 显示 `display-scale` 为相对 r35i 的唯一缺失项；`display-rotation` 三方均缺，不作为原因。来源：主控转述三份 ADT 对照；状态：self-checked，未独立复跑。
- **交接前读数**：`PROP 00ff`，八项属性均存在；`SC n=0` 为交接前读数，不能用于判断交接后的提交。来源：主控转述诊断页；状态：实机转述。
- **当前卡点**：Apple logo 不变；约 100 秒内横幅 `crashes` 由 4→13、`exits` 由 9→18；CRASH 全为 `mobileactivationd`，`status=5 sig=5 ns=2 sub=5`，约每 13 秒一次。SpringBoard 无 EX 行；`LOAD user≈35% sys≈65% idle=0%`。来源：主控转述横幅读数；状态：实机转述，不证明 SpringBoard 已完成初始化。
- **seed 排除项**：skip-setup 偏好存在，包括 `com.apple.purplebuddy`、`migration`、`springboard` 等，build 为 `20H392`；不支持缺少这些偏好作为本次解释。来源：主控转述 seed 检查；状态：self-checked，未独立复跑。
- **公开对照**：主控所查项目均未禁用 `com.apple.mobileactivationd`；sheng 用 skip-setup + AKS，sweet 用 data_ark，hakios 按需启动。sheng 记录 `fairplayd.A2` 与 `adid` 同时启用会阻塞 SpringBoard，而本项目 `nuwa-lite` 已禁用两项。来源：主控转述公开项目与本项目配置对照；具体公开 revision 未提供，结论限已查范围；状态：未独立复核。
- **未证**：logo 由 backboardd 提交的具体证据、SpringBoard 是否完成初始化、Data 是否持久（`DS=4`）均未建立；持久交互及断电重启验收未达成。来源：上述实机证据边界；状态：尚未验证。
