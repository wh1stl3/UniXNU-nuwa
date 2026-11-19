# BootProgress (nuwa port)

来源：`https://github.com/UniXNU/UniXNU-sheng`，commit
`998d0cc5023d4eff54a1ef40cce6ec89dc10083c`（`git ls-remote` 核对 HEAD 同值，公开仓库；取件日 2026-11-15）。

| 文件 | 上游路径 | 许可 | SHA256 |
| --- | --- | --- | --- |
| `BootProgress.c` | `package/BootProgress.c` | MIT（文件头 `SPDX-License-Identifier: MIT`） | `6b49a811288703fb009f03e37eb26f601a64d6d62e08a3bda864a8ed3f64e213` |
| `BootProgressCore.h` | `package/BootProgressCore.h` | MIT | `b336397b7aa1e903705ecc78f668f67dd31d7136e8a47acfc801322ada30ee04` |
| `BootProgressDisplay.h` | `package/BootProgressDisplay.h` | MIT | `231f580758e4e98592fd7f41203be00ca5670b912508a520bf83fb82d3af10d9` |
| `BootProgressLifecycle.h` | `package/BootProgressLifecycle.h` | MIT | `a885fceac1215b4d18ae4e96d141586a257b734bd6a88d8945786f00d8a6b272` |
| `BootProgressPulse.h` | `package/BootProgressPulse.h` | MIT | `25700a256b60329dc297c85f36f2397d21062536342affa42568e4cfef1adcd4` |
| `LICENSE-UNIXNU-SHENG` | `LICENSE` | BSD-2-Clause-Patent（仓库根许可） | `5b1d3d911103cb0f41641ec0964c5ac1f7e229f57aa072b6ac38bae913a1307b` |

这五个文件按上游原样保留，未改一字；`scripts/build-boot-progress-nuwa.py` 重新编译前会核对上表哈希。
`BootProgress.c` 只依赖下列本仓以外部件：

- `Font.h`（`GLYPH_FONT`）：`../uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/Font.h`，构建时以 `-I` 引入，不复制。
- `kern/boot_progress.h`：来自 `patches/xnu/8796-nuwa-boot-progress.patch`（与上游同内容）。

本仓新增（非上游）：

- `nuwa_boot_progress_stubs.c` —— nuwa 内核没有的符号（`native_virtio_*`、`native_owner_root_accepted`、
  `boot_diag_scan`/`boot_diag_stream`）的桩定义，见文件内注释。
- 上游同目录的 `BootFaultProbe.c`、`BootWatchdogPolicy.c`、`BootDiagExport.c`、`BootLatencyTrace.c`、
  `AdspFirmware.c` 与 `BootLog.c` 未引入：它们依赖 sheng 的 `boot_log_*`/`boot_ui_trace_*`/watchdog/
  audio DSP 组件，nuwa 侧无对应消费者，`libBootProgress.a` 只含 `BootProgress.o` 与本桩对象。
