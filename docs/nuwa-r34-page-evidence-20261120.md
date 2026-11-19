# r34 页面时基读数与 r35 主机复现（2026-11-20）

状态标签：

- 页面读数来源＝用户实机拍照，**主控目视转录，未经 vision 独立确认**。
- 判读＝reviewer 静态审查（转录 + 源码），无设备命令。
- r35 主机复现＝coder self-checked，未经 verifier。
- 设备＝r35 **未上机**；上机授权在写入前由用户取消；取消前是否已有部分写入**待用户确认**。

## 1. 时基核对

- CLK 行格式串 `CLK cntfrq=%llu dt=%llu dv=%llums cv=%llums (equal=right)` 在 r34 kernel.macho（55717888 B，`ce24818e…7f6dd`，文件偏移 1269247）与 r35 kernel.macho（55721984 B，`78761018…12464`，偏移 1269240）中各出现 1 次。
- 源码位置 r34 `out/nuwa-r34-20261119/BootProgress.c`：L809 snprintf，L811 `line_or_wrap(40,41,…)`；无 `#if` 包裹，仅运行期 `if(&armcpu_irq_phase)`（L776）弱符号判断；渲染在 row 40 起、row 41 续行。
- 页面实测值：`cntfrq=19200000 dt=19200000 dv=6143960ms cv=6143960ms`。
- 结论：闭合 2026-11-07 遗留在 `docs/device-evidence-2026-11-07.md` 的 `cntfrq_readback stays unverified`；内核时基在 boot CPU 上自洽且 CNTFRQ 回读为 19.2 MHz；6144 s 窗口内 dv/cv 无漂移；TIMER 行 `cval-vct=0x1967e=104062 ticks ≈ 5.42 ms` 为健康在飞 deadline。
- 边界：不证明物理计数器速率（两条换算除同一标称频率）；SMP 未开，仅 boot CPU。
- 控制台积压路径排除：本板不采集控制台（`porting.toml:284`），页面秒数在事件时刻以 CNTFRQ 打点，渲染器忙时丢弃并计 `dropped`。

## 2. EX 异常环判据

以下均引自 `out/nuwa-r35-20261119/BootProgress.c`。

- 四笔画在行 0 一行内，模板 `EX%u %.6s %x:%x:%x`（L562-577、L569-571），新→旧。
- `comm6`＝`p_name` 前 6 字符（L1154）。
- `sig/ns/code` 只显 `&0xf/&0xf/&0xff`（L571）；精确值仅控制台，本板读不到。
- 入环条件 `if(status||ns)`（L1151）：**exit(1) 类 `status=0x100` 同样入环**，4 笔后被顶成 `0:0:0`；因此「EX 里没有 Spring」**不能**判为存活。
- `dropped`（L1146）只计 `exit_lock` 争用，不代表环溢出。
- 存活信号：行 0 保持原标题（环空）、行 1 `np=` 趋势（L584-590）、行 5 stage 推进。
- 关键窗口 t≈60–180 s；t=120 s 标题转 `LIVE: DEADLINE EXCEEDED`（L553、L1054）。
- `ns` 是 os_reason namespace（`scripts/run-pmap-ret-once.py:2142-2153` 的 r35 profile 说明）；`sig` 取值按 POSIX 信号号：5=SIGTRAP、6=SIGABRT、9=SIGKILL、11=SIGSEGV。
- 行 16 以下在 panic 清屏区。

| 判读 | 页面依据 |
| --- | --- |
| 存活 | 行 0 仍是原标题（环空）；行 1 `t=`/`np=` 缓慢变化；行 5 stage 文本推进 |
| 已挂 | 行 0 出现 `EX…`，同一 `comm6` 反复出现在 EX1；行 1 `t=` 停住；stage 不再推进 |
| 假象 | `exit(1)`（`status=0x100`）也入环，4 笔后顶成 `0:0:0`；`dropped` 只记 `exit_lock` 争用；`sig:ns:code` 只显低位，精确值仅控制台 |

## 3. r35 主机复现

- 四件命令全部 exit 0：`scripts/build-ufs-apfs-root-chmh-r35.py`（含 `--audit`）、`scripts/test-ufs-apfs-root-profile.py`、`scripts/test-ufs-apfs-root-chmh.py`、`scripts/run-pmap-ret-once.py --self-check`（157 组，`real_device_commands: 0`）。记录见 `out/verify-r35-20261120-02-logs/summary.txt`。
- 产物 `out/verify-r35-20261120-03/`：kernel.macho 55721984 B `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464`、vendor_boot.img 100663296 B `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed`、`derived.adt`、`payload.img`、`record.json` 与记录目录逐字节相同；新建 `audit.json` 与既有 `out/nuwa-ufs-apfs-root-chmh-20261119-r35-audit-r1/audit.json` 逐字节相同（`outer_sha256=c6e64820…`、`avb_authentication_claimed=false`）。
- 首次运行失败原因：`scripts/build-nuwa-pmgr-kernel.py:23` 硬编码读取 `/root/nuwa-pmap-ret-native-20261111/build-result.json`，普通用户 EACCES（`/root` 700），换 `wsl -u root` 复跑即全部通过——运行身份问题，不是产物差异。

## 4. 未决项

- 设备槽位实际状态待用户确认。
- SpringBoard/mobileactivationd 的 `sig:ns:code` 与退出时 nprocs/AKS 计数仍缺。
- 照片上的 `nprocs=161`、`nonzero=774`、`dv=6144s` 仅此一处来源、未落库，不得当基线引用。
