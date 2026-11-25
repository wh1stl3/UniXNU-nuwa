# seed 之外横向摘录（2026-11-25）

`?` 为本次未找到，不表示不存在。版本：cepheus master（归档），merlinx fb616afa1231b0ad2b6a6f4832a299b76b64031c，sheng e8937177，alioth 与 munch main 未固定。不同项目的配置、历史运行记录、主机候选不能混为同一次启动。本表只摘录，不建立故障因果。nuwa 工作树 `board.toml` 默认 args 不是当前设备参数。

来源缩写：[C](https://github.com/YangQi0408/UniXNU-cepheus/blob/master/board.toml)、[CR](https://github.com/YangQi0408/UniXNU-cepheus/blob/master/README.md)、[M](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/board.toml)、[MS](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json)、[S](https://github.com/UniXNU/UniXNU-sheng/blob/e8937177/board.toml)、[A](https://github.com/FFT-infra/UniXNU-alioth/blob/main/board.toml)、[U](https://github.com/WuBarlynn/unixnu-munch/blob/main/board.toml)、[N](nuwa-smp-gate-20261123.md#L160)（文件第 160 行，主机候选）。

## 1 boot args

| 项目 | 全文与来源 |
|---|---|
| nuwa 候选 | `-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1`；[N](nuwa-smp-gate-20261123.md) :160，未上机。最新禁用实验另加 `disable-jobs=com.apple.iconservices.iconservicesagent`，[观察](nuwa-icondisabled-20261125-observation.md):10，完整 args ? |
| cepheus | `debug=0xc serial=3 cpus=8 keepsyms=1 startup_debug=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetusb=2 sweettouch=0 sweetkeys=0 sweetfb_noconsole=0 sweetfb_hz=30 sweetgpu=3 sweetlogdump=1`；[C]，这是配置基线，不是触摸验证镜像参数。 |
| merlinx | `-v serial=3 debug=0x14e -no_slto_panic validation_disables=0x10 dk=0 sheng-pmgr=2 sheng-aks=1 native-emmc-root=1 offline-mobile-graphics-load=1 offline-mobile-graphics-client=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-unit-scale=2 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-transfer=1 offline-legacy-validate=1 offline-legacy-cpu-present=1 sheng-vsync=60 sheng-gpu-addon=1 sheng-no-lc=1 launchd_unsecure_cache=1 ignition_level=1 wdt=-1 fts-touch=3 sheng-touch-hid=1 sheng-fb-diff=1 boot-ui-focus=lsd boot-ui-focus2=SpringBoard boot-ui-focus3=backboardd boot-ui-focus4=lsd boot-ui-chrono=1`；[M]。 |
| sheng | iPadOS 27 默认 `-v serial=3 debug=0x14e kt_fixed_zones=120 -no_slto_panic use_contiguous_hint=0 native-source-storage=1 native-ufs-root=1 offline-mobile-graphics-load=1 offline-mobile-graphics-client=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-unit-scale=2 offline-legacy-pm=1 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 offline-legacy-phase=4 offline-key-events=1 aks=1 aks-sls=3 offline-hid-input=1 offline-hid-home=1 touch=4 touch-hid=1 buttons=1 keyboard=1 log=1 smp=1 armcpu-spi-ipi=1 armcpu-self-ipi=1 data-persist=2 adsp=2 audio=12 wifi=5 bluetooth=1 backlight=1 cpufreq=4 gpu-power=9 gpu-metal=1 fb-gpu=1 fb-bgra=1 dpu-scanout=2 no-lc=1 vsync=120 vsync-fixed=1 gpu-dcvs=1 disable-watchdogd=1 lite=1 gpu-addon=1 usb=1 appsync=1`；17.7.11 为独立 override，全文见 [S]，不等于默认。 |
| alioth / munch | 全文 ?；均见各自 [A] / [U] 的 `kernel_args`，未在此逐项转录。 |

与 [N] 候选逐字比较，cepheus 特有项：`debug=0xc cpus=8 keepsyms=1 startup_debug=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetusb=2 sweettouch=0 sweetkeys=0 sweetfb_noconsole=0 sweetfb_hz=30 sweetgpu=3 sweetlogdump=1`；merlinx、sheng、alioth、munch 的完整差集 ?。比较为字符串，不等同语义差异。

## 2 内核补丁和组件

| 项目 | 摘录 |
|---|---|
| nuwa | `GopFramebuffer` 被选但 embedded 选择不生成归档，见 [board.toml](../board.toml):16–18；SMP 候选 `8796-nuwa-smp-affinity.patch`、`nuwa-smp-one-secondary.patch`，[SMP](nuwa-smp-gate-20261123.md):40–71；其他分类完整清单 ? |
| cepheus | `xnu/0082-cepheus-touch.patch` 改触摸编译清单、`0082-stage-cepheus-touch.sh` 暂存驱动；[CR]。其余显示、存储、launchd、激活、日志、watchdog 补丁清单 ? |
| merlinx | `offline-component-load-probes.patch`、`offline-legacy-start.patch`、`offline-owner-systemos-mount.patch`、`offline-owner-launchd-exit.patch`、`offline-owner-launchd-fault.patch`、`zzz-boot-progress.patch`、`zzzh-merlinx-osd-and-usb-cmds.patch` 均列于 [series](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/patches/xnu/series)；逐文件作用 ?。`NativeEmmc`、`GopFramebuffer`、`FocalTechTouch`、`MaliG52` 见 [M]。 |
| sheng | `ShengUfs`、`GopFramebuffer`、`Adreno740`；17 profile 另选 `ShengHidInput`、`ShengNovatekTouch`、`QcomGeniSpi`，见 [S]。补丁清单 ? |
| alioth / munch | `ShengUfs`、`GopFramebuffer`、`ShengHidInput`、`QcomXnuUsbDebug`，以及 `build-gop-legacy-display.py`；[A]、[U]。逐补丁清单 ? |

## 3 显示

| 项目 | 摘录 |
|---|---|
| nuwa | r34 诊断页 `vinfo` 直绘，显示服务未接；[userspace](nuwa-userspace-20261119-observation.md):181–188。后续候选含 CPU-present 参数 [N]；运行效果 ? |
| cepheus | CPU 软渲染桌面，GPU 硬件合成未实现；[CR]。基线 `sweetfb_hz=30 sweetgpu=3 sweetfb_noconsole=0`；[C]。 |
| merlinx | `GopFramebuffer` + `offline-legacy-*`、`sheng-vsync=60`、CPU present，另选 MaliG52；[M]。单次运行是否依赖 GPU ? |
| sheng | `GopFramebuffer`，默认 `fb-gpu=1 gpu-metal=1 vsync=120`；[S]。 |
| alioth / munch | `GopFramebuffer`；各自 `offline-legacy-*`、alioth `vsync=120`、munch `sheng-vsync=60`；[A] [U]。CPU transfer 及 GPU 构建两者均有，具体运行依赖 ? |

## 4 用户态 job

| 项目 | 摘录 |
|---|---|
| nuwa | r34 watchdog 禁用文件，[userspace](nuwa-userspace-20261119-observation.md):162；最新候选 `disable-jobs=com.apple.iconservices.iconservicesagent`，读取生效未证，[观察](nuwa-icondisabled-20261125-observation.md):10–23, 80；完整名单 ? |
| cepheus | 系统根卷 `launchd.plist` 是否修改、完整禁用列表 ? |
| merlinx | `/private/var/db/com.apple.xpc.launchd/disabled.plist` 和 `disabled.501.plist` 规格含相同 31 项、值均 true：[完整列表](nuwa-open-deltas-20261125.md):84–86,103，另含 `com.apple.iconservices.iconservicesagent`；[MS]。规格不是实机读入证明。根卷 `launchd.plist` 修改 ? |
| sheng | `lite=1 disable-watchdogd=1` [S]；`lite=2` 的 agent 观察见 [deltas](nuwa-open-deltas-20261125.md):51–52；完整名单和文件路径 ? |
| alioth / munch | alioth `disable-jobs=com.apple.liveactivitiesd,com.apple.routined`、munch `sheng-disable-jobs=com.apple.liveactivitiesd,com.apple.cryptexd,com.apple.routined`；另均有 lite 策略；[A] [U]。完整列表及文件路径 ? |

## 5 激活与 Setup

| 项目 | 摘录 |
|---|---|
| nuwa | `data_ark` 当前状态 ?；旧 raw 迁移 plist 未找到，运行卷未知；[deltas](nuwa-open-deltas-20261125.md):28–37。 |
| cepheus | data_ark / purplebuddy / migration 路径和键 ? |
| merlinx | `/private/var/mobile/Library/Preferences/com.apple.purplebuddy.plist`：`SetupDone=true`、`SetupFinishedAllSteps=true`、`SetupVersion=11`、`SetupState=SetupUsingAssistant`、`ForceNoBuddy=true`、`daemonizeNeedsToRun=false`；`com.apple.DataMigration.plist` 与 `com.apple.migration.plist`：`LastSystemVersion=21H461`、`DMLastMigrationResults.success=true`、`buildVersion=21H461`、`DMUserDataDisposition.SyntheticDidUpgrade=false`；[MS]。data_ark ? |
| sheng | `skip_setup_tool=scripts/seed-data-skip-setup.py`、`skip_setup=true` [S]；具体键 ? |
| alioth / munch | 均配置 `skip_setup_tool=scripts/seed-data-skip-setup.py`；[A] [U]；具体键和 data_ark ? |

## 6 输入

| 项目 | 摘录 |
|---|---|
| nuwa | `nuwa-hid-standin=1` 为候选参数 [N]；真实触摸和按键链路 ? |
| cepheus | ST-FTS `0x49`、GPIO 开漏 I²C、L1C 电源、iOS HID；项目称用户确认可用；[CR]。同仓基线 [C] 却为 `sweettouch=0 sweetkeys=0`，不可混为同次镜像。 |
| merlinx | `FocalTechTouch`、`fts-touch=3 sheng-touch-hid=1`；[M]；运行触摸状态 ? |
| sheng | 17 profile `ShengNovatekTouch`、`QcomGeniSpi`、`ShengHidInput`；[S]。 |
| alioth / munch | alioth FT5652 probe + GENI SPI + `ShengHidInput`；munch 编译 `build-munch-touch.py` + HID，见 [A] [U]；munch 实测 ? |

## 7 根卷和存储

| 项目 | 摘录 |
|---|---|
| nuwa | 真实 UFS `userdata` 根，`native-ufs-root=1`；[交接](nuwa-launchd-reached-20261115.md)；Data 当前读写状态 ? |
| cepheus | UFS userdata HFS+ 组合根；`ufsrw=1 rootrw=1`；[CR] [C]。 |
| merlinx | NativeEmmc + APFS Data，无 role、规格 16 GiB；设备记录称 Data 可写；[MS] [设备记录](https://unixnu.com/devices/merlinx)。 |
| sheng | ShengUfs、`data-persist=2`、persistent_data；[S]。各卷实际读写属性 ? |
| alioth / munch | UFS OS/SystemOS；RamBlock 发布 Data；alioth `data-persist=2`，munch 配置无该参数；[A] [U]。munch 实际读写状态 ? |

## 8 CPU/SMP

| 项目 | 摘录 |
|---|---|
| nuwa | r16 `req=0 run=0 cond=0 boot=0`，[userspace](nuwa-userspace-20261119-observation.md):188；单次核门为未上机候选，[SMP](nuwa-smp-gate-20261123.md):60–71。 |
| cepheus | `cpus=8`，源码注释称八核到达 bsd_init；[C]。 |
| merlinx | 启用状态 ?；`native-smp-secondary.patch` 在 [series](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/patches/xnu/series)。 |
| sheng | `smp=1 armcpu-spi-ipi=1 armcpu-self-ipi=1`；[S]。 |
| alioth / munch | alioth 同三项；munch 该版本注释写首次映像关闭 SMP；[A] [U]。 |

## 9 日志

| 项目 | 摘录 |
|---|---|
| nuwa | r34 vinfo 诊断页，[userspace](nuwa-userspace-20261119-observation.md):181–188；候选 `boot-progress=2` [N]；其他通道 ? |
| cepheus | `sweetusb=2` CDC-ECM，UDP 到 `192.168.7.1:5140`；`sweetlogdump=1`；[C]。 |
| merlinx | `zzzh-merlinx-osd-and-usb-cmds.patch` 在 [series](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/patches/xnu/series)；运行通道 ? |
| sheng | 默认 `log=1 usb=1`；[S]。协议及实际结果 ? |
| alioth / munch | `qcom-usb-debug=1 qcom-usb-ctl=1`；板文件描述 DWC3 CDC-ACM 以及 printf/IOLog/kprintf/panic drain；[A] [U]。 |

## 「我们缺的东西」：按已有记录的对象归档，不表示因果

| 档 | 摘录 / 代价 |
|---|---|
| 直接相关：无画面 | r34 显示服务未接，而对方列 GOP 显示路径；代价：完整 IOKit 显示生命周期与实机效果未证；[userspace](nuwa-userspace-20261119-observation.md):181–188、[M]。候选已有参数，不能称代码完全不存在。 |
| 直接相关：无图标 | sheng `lite=2` 禁 agent 的记录称图标 artwork 缺失；代价即图标缺失；[deltas](nuwa-open-deltas-20261125.md):51–52。nuwa 当前并非缺该禁用候选，生效未证。 |
| 间接 | USB CDC/ECM 日志：cepheus [C]、alioth [A]；nuwa 实际同类通道 ?，接入代价 ? |
| 间接 | 多核：r16 未请求，候选门默认关闭；代价：主机候选、次核运行未验；[SMP](nuwa-smp-gate-20261123.md):60–71,98–104。 |
| 无关 | ?；未发现来源直接将所列差异判为与指定三个症状无关。 |

## 未找到

1. 当前设备启动载荷的完整 boot args；alioth/munch 完整转录及各对方全部逐项差集。
2. 各机完整分类补丁及每项作用、nuwa 对应逐项有无。
3. cepheus 根卷 launchd.plist 和全量禁用 job；sheng/alioth/munch lite 实际全量；nuwa 当前全部 job。
4. cepheus、sheng、alioth、munch 的 data_ark 与完整 Setup 键；nuwa 当前运行卷对应键。
5. nuwa 当前真实触摸、按键与 USB 日志实机状态；merlinx 触摸、SMP 实测；munch 独立实测。
6. 跨各配置的 GPU 必要性、各卷运行态读写属性；各项实施代价除明确记录外均未知。
7. lsd 崩溃与上述差异的直接因果证据。

状态：仅静态摘录；未改代码、未操作设备、未提交 Git。
