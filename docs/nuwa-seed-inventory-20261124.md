# nuwa Data seed inventory — 2026-11-24

范围：只读调查和本文；不构建、不接触设备、不修改 seed。**self-checked**；实机读数为主控转述。路径大小写按镜像保留：Data 根对应 `/private/var`，实际容器根是小写 `/private/var/containers`，不是 `/private/var/mobile/Library/Containers`。

## 身份、来源与证据边界

- `out/nuwa-systemgroup-seed-20261122/data-8g-sg.dbr` 和 `out/nuwa-sb-stack3-flash-20261124/seed.img` 本次均只读 SHA-256：`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`；后者大小 2,121,888 B。`apply.log` 记录逻辑 APFS 大小 8,589,934,592 B。前者及本轮 lsd 包中的 seed 身份见 `nuwa-lsd-stack-20261124.md:35-37`。
- 系统生成源：`scripts/build-ufs-apfs-root-chmh-r35.py` 消费预建 seed；先前生成器 `make-data-seed.py` 创建 APFS 并复制 donor OS 的 `/private/var`，位置和过程见 `nuwa-systemgroup-seed-20261122.md:31-37`；工作区现存副本 `.cache/ci-porting-134fd4e/tools/scripts/make-data-seed.py`。SystemGroup 修改记录是 `out/nuwa-systemgroup-seed-20261122/apply.log`，打包脚本为同目录 `repack-seed-only.py`，非 `scripts/` 下 seed 生成器。34 项清单来自 `nuwa-systemgroup-seed-20261122.md:9-11,55-90`，系从已解析 launch daemon 程序的两种 system-group entitlement 求并集；不覆盖未解析程序及非 daemon。
- 本次查看的现成只读挂载 `/tmp/nuwa-seed-ro-mount/root` 的 SystemGroup 为空，是旧内容而非当前 34 项镜像；其到原始 seed 的逐字节身份本次未核对。下面旧树为该挂载实查，当前 seed 中的对应树根据 `nuwa-systemgroup-fix-result-20261122.md:9-13` 所述 104 个新增目录及未改变顶层计数推断，**不是当前镜像的完整只读回挂清单**。旧挂载其他目录在当前镜像是否逐项完全一致，缺完整差异清单，不能证明。`apply.log` 记录 34 项和目标子目录；报告的独立检查是主控转述，不是本次独立复跑。

## 目录清单

现成旧只读挂载根目录 29 个名称（历史报告的 Data 顶层 **30 项**计数包括何种条目未核实；不能把 `ls` 目录名数量等同于该报告的计数）：`Keychains`, `Managed Preferences`, `MobileAsset`, `MobileDevice`, `MobileSoftwareUpdate`, `audit`, `buddy`, `containers`, `datamigrator`, `db`, `dextcores`, `empty`, `folders`, `hardware`, `installd`, `keybags`, `log`, `logs`, `mobile`, `msgs`, `networkd`, `preferences`, `protected`, `root`, `run`, `select`, `tmp`, `vm`, `wireless`。

旧挂载中含子目录的第二、第三层汇总（其余顶层无可见子目录；文件、符号链接不在此表）：

| 父目录 | 直接子目录；分号后为第三层 |
| --- | --- |
| `Managed Preferences` | `mobile` |
| `MobileAsset` | `PreinstalledAssetsV2`; `PreinstalledAssetsV2/InstallWithOs` |
| `MobileDevice` | `ProvisioningProfiles` |
| `containers` | `Bundle`, `Data`, `Shared`, `Temp`; `Data/System`, `Shared/SystemGroup` |
| `db` | `DumpPanic`, `ExtensibleSSO`, `Sandbox`, `UpdateMetrics`, `accessoryupdater`, `analyticsd`, `astris`, `biome`, `com.apple.dt.automationmode`, `com.apple.xpc.launchd`, `com.apple.xpc.roleaccountd.staging`, `coreml`, `darwindaemon`, `datadetectors`, `diagnostics`, `diskimagesiod`, `findmydevice`, `fpsd`, `gpsd`, `knowledgegraphd`, `lockdown`, `lsd`, `mmaintenanced`, `nearbyd`, `ondemand`, `reportmemoryexception`, `rmd`, `sysdiagnose`, `systemstats`, `timed`, `timezone`; 第三层 `ExtensibleSSO/Configuration`, `com.apple.xpc.launchd/config`, `darwindaemon/Library`, `sysdiagnose/com.apple.ScreenshotServicesService`, `sysdiagnose/com.apple.sysdiagnose` |
| `log` | `asl`, `com.apple.xpc.launchd`, `mDNSResponder`, `ppp` |
| `logs` | `Baseband`, `hidfw-crashlogs`, `mediaserverd` |
| `mobile` | `Applications`, `Library`, `Media`, `tmp`; `Media/DCIM`, `Media/PhotoData`, `Media/Photos`；`Library` 见下 |
| `preferences` | `Logging`; `Logging/Processes`, `Logging/Subsystems` |
| `protected` | `trustd` |
| `root` | `Library`; `Library/Preferences` |
| `wireless` | `Library`, `baseband_data` |

旧挂载 `/private/var/mobile/Library` 直接子目录：`AddressBook`, `Application Support`, `Caches`, `Cookies`, `ExternalAccessory`, `Inboxes`, `Keyboard`, `Logs`, `Preferences`, `Safari`, `WebClips`；另有文件 `.localized`。**无 `Containers`**。本次看到 `Caches` 空、`Preferences` 有 7 项；历史记录报告新旧 seed Preferences 均 7 项，但未报告逐项名称相同。

| 路径 | 旧挂载 | 当前 seed 证据 |
| --- | --- | --- |
| `/private/var/mobile/Library/Containers/Data/Application` | 不存在，计数不适用 | 没有直接回挂核对；历史记录仅称增量为 SystemGroup |
| `/private/var/mobile/Library/Containers/Shared/AppGroup` | 不存在，计数不适用 | 同上 |
| `/private/var/mobile/Library/Containers/Shared/SystemGroup` | 不存在，计数不适用 | 同上 |
| `/private/var/containers/Data/Application` | 不存在，计数不适用 | 未直接回挂 |
| `/private/var/containers/Shared/AppGroup` | 不存在，计数不适用 | 未直接回挂 |
| `/private/var/containers/Shared/SystemGroup` | 存在，0 项 | `apply.log` 记录 34 项；当前 seed 哈希与该日志一致，非本次回挂 |

34 个直接子目录均以前缀 `systemgroup.com.apple.` 开头，后缀如下：`AssetCacheServices.diskCache`, `DeviceActivity`, `ReportMemoryException`, `WiFiAssist`, `appstored`, `bluetooth`, `cfpreferences.managed`, `configurationprofiles`, `coreanalytics`, `dt.previews`, `geod`, `icloud.findmydevice.managed`, `icloud.ifccd`, `icloud.searchpartyd.sharedsettings`, `installcoordinationd`, `logd_helper.FTABHarvest`, `lsd`, `lsd.iconscache`, `lskdrl`, `media.books.managed`, `media.shared.books`, `mobile.installationhelperlogs`, `mobileactivationd`, `mobilegestaltcache`, `mobilestorageproxy`, `nearbyd.datastore`, `nsurlstoragedresources`, `ondemandresources`, `osanalytics`, `pisco.suinfo`, `powerlog`, `regulatory_images`, `sharedpclogging`, `userimagecache`。

历史结果称共新增 104 个目录、无 MCM metadata plist；`apply.log` 明确目标 `mobileactivationd/Library/{ucrt,dcrt,internal}` 存在，容器根实验性 `0:0/0755`，Library 及子目录 `501:501/0755`。其他 103 项逐路径内容未在本次直接核实，不凭 104 的算术推定具体结构。

## containermanagerd：能证与不能证

- **实机主控转述**：此前 `cm=61` 在进程采样中存在（`nuwa-mobileactivation-migration-20261122.md:9,26`），不证明它完成初始化或正在为 lsd 服务。本轮主控称 lsd T0 等待同步 Mach 回复、T1 空闲，UFS 高读；未识别回复方或读 I/O 进程，不可归因 containermanagerd。
- **静态线索**：`nuwa-systemgroup-seed-20261122.md:31-36` 记录 donor cache 的 SystemGroup 路径、identifier-to-path、`MCMMetadataIdentifier`、`MCMMetadataUUID`、metadata plist 和 ACL 相关字符串；`nuwa-systemgroup-fix-result-20261122.md:23-26` 记录 orphan 删除字符串 `Deleting orphaned data missing a metadata file at: %@`。这支持 MCM 具有元数据/路径管理及清理能力，**不证明此次执行了扫描或删除**。
- **无依据**：首次启动一定创建完整 `Containers` 骨架；逐 app 扫描 `.com.apple.mobile_container_manager.metadata.plist`；具体调用顺序、元数据格式和权限/保护类；缺某一目录会让 containermanagerd 或 lsd 阻塞。空目录不等于已注册容器，缺 metadata 也不能据此断言阻塞或必删。需要调用栈、服务端日志或同版本真实注册容器样本建立因果。

## 主机侧 LaunchServices 数据库

**目前不能产出可证明可用的 LS 数据库。** 当前只有 `db/lsd` 目录与 lsd 相关 SystemGroup entitlement 等线索；缺同版数据库格式/schema、版本和完整性规则、所有系统 app/插件清单及其注册信息、对应容器身份和元数据、构建/导入工具和可验证的消费者。无法证明简单建目录或复制数据库能被当前 lsd 接受，也无依据断言只能由 lsd 生成。可行路线需要取得同版本官方支持的生成/导入机制及上述输入，或在兼容 iOS 运行环境中让相应 lsd 及其依赖完成注册后导出并验证；后者只是待验证路线，非已证明充分条件。

## 若要预置目录：候选清单（5 条，均非已证明修复）

1. `/private/var/containers/Data/Application` — 旧挂载缺失；MCM 容器骨架调查候选；**无依据证明首次启动必须预建**。
2. `/private/var/containers/Shared/AppGroup` — 旧挂载缺失；与已存在的 `Shared/SystemGroup` 区分的骨架调查候选；**无依据证明必需**。
3. `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.lsd` — entitlement 清单来源 `nuwa-systemgroup-seed-20261122.md:9-11,72`，历史 seed 已有，不是新增建议；未证明元数据或写权限正确。
4. `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache` — 同源 `:73`，历史 seed 已有；未证明运行时请求或注册。
5. `/private/var/db/lsd` — 旧只读挂载存在；LS 相关调查候选，不能推断其为数据库路径、缺失或阻塞因素。

优先调查前 3 个路径并不表示已定位故障；尤其第 3 项已预置。不要猜测 UUID、metadata、ACL 或 ownership，也不要在本轮实际创建。精确确认当前 seed 全树需对该 SHA 的镜像做只读展开/回挂，并与已知原始 seed 做完整差异；本轮没有执行。
