# nuwa seed 与 merlinx Data seed 规格集合差（2026-11-24）

状态：self-checked；仅离线只读遍历，未修改 seed、重新打包或访问设备。merlinx 是规格，不代表其设备实际卷；对齐清单不代表推荐在 nuwa 创建。

## 输入及方法

- 参照：`Dracen-W/UniXNU-merlinx@fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json`，原文 SHA-256 `28180c89b7887ed685c7b96eda67a2d011824014b7dc2df742f1a73f244dd18a`；directories 85 项，files 13 项。
- 我方 raw：`out/seed-raw-20261124/seed.raw`，8,589,934,592 B；SHA-256 `2a7e965a8c625cfe57e723b07dd582e96114d857c0cbd1857ce3863072f43479` 为既有展开记录，本次未重算。
- WSL 本地 `sgan81/apfs-fuse@66b86bd525e8cb90f9012543be89b1f092b75cf3`，命令：
  ` /home/wh1stl3/apfs-work/apfs-fuse-66b86bd525e8cb90f9012543be89b1f092b75cf3/build/apfs-fuse -o ro /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/seed-raw-20261124/seed.raw /tmp/nuwa-seed-merlinx-20261124`。
- `findmnt` 输出：`/tmp/nuwa-seed-merlinx-20261124 /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/seed-raw-20261124/seed.raw fuse ro,nosuid,nodev,relatime,user_id=1000,group_id=1000`。挂载卷的 `root/` 是 `/private/var`，不计根目录自身；不跟随符号链接，递归错误即中止；mode 为 `lstat` 权限和特殊位的八进制，uid/gid 为数字；严格区分大小写，不展开规格未列父目录。
- 卸载命令 `fusermount -u /tmp/nuwa-seed-merlinx-20261124` 成功；`mountpoint -q` 和 `findmnt -rn -M` 均确认不再挂载，输出 `UNMOUNT_OK`、`NOT_MOUNTED`、`FINDMNT_NO_ENTRY`。
- 完整排序导出在 `out/merlinx-spec-20261124/{our-var-tree.txt,their-var-tree.txt}`，格式 `相对 /private/var 的路径 | mode | uid:gid`。

## 计数

| 集合 | 数量 |
|---|---:|
| 我方目录 | 274 |
| 对方规格目录 | 85 |
| 对方有、我方无 | 37 |
| 我方有、对方未列 | 226 |
| 共有但 mode/uid/gid 不同 | 10 |

## 对方有、我方无：完整新增清单

路径相对 `/private/var`；同名非目录冲突单独标出，不应直接当可 mkdir 路径。

```text
Library | 0755 | 0:0
PersonaVolumes | 0755 | 0:0
containers/Bundle/Application | 0755 | 0:0
containers/Data/Application | 0755 | 0:0
containers/Data/InternalDaemon | 0755 | 0:0
containers/Data/PluginKitPlugin | 0755 | 0:0
containers/Data/SystemGroup | 0755 | 0:0
containers/Data/Temp | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library/Caches | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/Caches | 0755 | 0:0
db/com.apple.xpc.launchd/disabled | 0755 | 0:0
db/com.apple.xpc.launchd/log | 0755 | 0:0
db/com.apple.xpc.launchd/system | 0755 | 0:0
db/com.apple.xpc.launchd/user | 0755 | 0:0
db/dslocal | 0755 | 0:0
db/dslocal/nodes | 0755 | 0:0
db/dslocal/nodes/Default | 0755 | 0:0
db/dslocal/nodes/Default/config | 0755 | 0:0
db/dslocal/nodes/Default/groups | 0755 | 0:0
db/dslocal/nodes/Default/users | 0700 | 0:0
db/uuidtext | 0755 | 0:0
dmd | 0755 | 0:0
keybags/backup | 0700 | 0:0
local | 0755 | 0:0
lock | 0755 | 0:0
mobile/Containers | 0755 | 501:501
mobile/Containers/Data | 0755 | 501:501
mobile/Containers/Data/Application | 0755 | 501:501
mobile/Containers/Data/InternalDaemon | 0755 | 501:501
mobile/Containers/Data/PluginKitPlugin | 0755 | 501:501
mobile/Containers/Shared | 0755 | 501:501
mobile/Containers/Shared/AppGroup | 0755 | 501:501
mobile/Documents | 0755 | 501:501
mobile/Library/Caches/com.apple.IconsCache | 0755 | 501:501
mobile/Library/Caches/com.apple.LaunchServices | 0755 | 501:501
preboot | 0755 | 0:0
spool | 0755 | 0:0
```

## 我方有、对方未列

一级分类（各条仅计入其第一个路径分量）：

| 一级分类 | 数量 |
|---|---:|
| `.fseventsd` | 1 |
| `Managed Preferences` | 1 |
| `MobileAsset` | 61 |
| `MobileDevice` | 1 |
| `audit` | 1 |
| `buddy` | 1 |
| `containers` | 100 |
| `datamigrator` | 1 |
| `db` | 32 |
| `dextcores` | 1 |
| `log` | 3 |
| `logs` | 3 |
| `mobile` | 12 |
| `preferences` | 3 |
| `protected` | 2 |
| `select` | 1 |
| `wireless` | 2 |

其中 `containers/`、`mobile/Containers/`、名称含 LaunchServices 的完整条目：

```text
containers/Shared/SystemGroup/systemgroup.com.apple.AssetCacheServices.diskCache | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.AssetCacheServices.diskCache/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.AssetCacheServices.diskCache/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.DeviceActivity | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.DeviceActivity/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.DeviceActivity/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.ReportMemoryException | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.ReportMemoryException/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.ReportMemoryException/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.WiFiAssist | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.WiFiAssist/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.WiFiAssist/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.appstored | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.appstored/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.appstored/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.bluetooth | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.bluetooth/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.bluetooth/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.cfpreferences.managed | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.cfpreferences.managed/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.cfpreferences.managed/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.configurationprofiles/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.coreanalytics | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.coreanalytics/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.coreanalytics/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.dt.previews | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.dt.previews/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.dt.previews/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.geod | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.geod/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.geod/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.findmydevice.managed | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.findmydevice.managed/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.findmydevice.managed/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.ifccd | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.ifccd/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.ifccd/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.searchpartyd.sharedsettings | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.searchpartyd.sharedsettings/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.icloud.searchpartyd.sharedsettings/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.installcoordinationd | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.installcoordinationd/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.installcoordinationd/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.logd_helper.FTABHarvest | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.logd_helper.FTABHarvest/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.logd_helper.FTABHarvest/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.lsd | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.lsd/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.lsd/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.lskdrl | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.lskdrl/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.lskdrl/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.media.books.managed | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.media.books.managed/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.media.books.managed/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.media.shared.books | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.media.shared.books/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.media.shared.books/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobile.installationhelperlogs | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.mobile.installationhelperlogs/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobile.installationhelperlogs/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobileactivationd | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.mobileactivationd/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobileactivationd/Library/dcrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobileactivationd/Library/internal | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobileactivationd/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobilestorageproxy | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.mobilestorageproxy/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.mobilestorageproxy/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.nearbyd.datastore | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.nearbyd.datastore/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.nearbyd.datastore/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.nsurlstoragedresources | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.nsurlstoragedresources/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.nsurlstoragedresources/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.ondemandresources | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.ondemandresources/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.ondemandresources/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.osanalytics | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.osanalytics/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.osanalytics/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.pisco.suinfo | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.pisco.suinfo/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.pisco.suinfo/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.powerlog | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.powerlog/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.powerlog/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.regulatory_images | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.regulatory_images/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.regulatory_images/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.sharedpclogging | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.sharedpclogging/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.sharedpclogging/Library/ucrt | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.userimagecache | 0755 | 0:0
containers/Shared/SystemGroup/systemgroup.com.apple.userimagecache/Library | 0755 | 501:501
containers/Shared/SystemGroup/systemgroup.com.apple.userimagecache/Library/ucrt | 0755 | 501:501
```

## 共有目录元数据不一致

| 路径 | 我方 mode / uid:gid | 对方 mode / uid:gid | 差异字段 |
|---|---|---|---|
| `Keychains` | 0755 / 0:0 | 0755 / 64:0 | uid |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library` | 0755 / 501:501 | 0755 / 0:0 | uid, gid |
| `containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library` | 0755 / 501:501 | 0755 / 0:0 | uid, gid |
| `db/diagnostics` | 0751 / 0:0 | 0755 / 0:0 | mode |
| `empty` | 0755 / 0:0 | 0555 / 0:0 | mode |
| `mobile` | 0711 / 501:501 | 0755 / 501:501 | mode |
| `mobile/Library` | 0711 / 501:501 | 0755 / 501:501 | mode |
| `root/Library` | 0700 / 0:0 | 0755 / 0:0 | mode |
| `root/Library/Preferences` | 0700 / 0:0 | 0755 / 0:0 | mode |
| `run` | 0775 / 0:0 | 0755 / 0:0 | mode |

## 指定路径实测

| 路径（相对 /private/var） | 状态 | mode | uid:gid |
|---|---|---|---|
| `containers/Data/Application` | 不存在 | — | — |
| `containers/Data/PluginKitPlugin` | 不存在 | — | — |
| `containers/Data/InternalDaemon` | 不存在 | — | — |
| `mobile/Containers/Shared/AppGroup` | 不存在 | — | — |
| `mobile/Library/Caches/com.apple.LaunchServices` | 不存在 | — | — |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd` | 存在 | 0755 | 0:0 |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd/Library` | 存在 | 0755 | 501:501 |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd/Library/Caches` | 不存在 | — | — |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache` | 存在 | 0755 | 0:0 |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library` | 存在 | 0755 | 501:501 |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library/Caches` | 不存在 | — | — |

## 规格 files 中 plist

只检查同名路径是否为普通文件，不对比内容、权限或真实性；符号链接不按普通文件计。

| 路径 | 我方状态 |
|---|---|
| `mobile/Library/Preferences/com.apple.DataMigration.plist` | 不存在 |
| `mobile/Library/Preferences/com.apple.migration.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/com.apple.purplebuddy.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/com.apple.purplebuddy.notbackedup.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/com.apple.managedconfiguration.notbackedup.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/com.apple.springboard.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/com.apple.frontboard.plist` | 不存在 |
| `mobile/Library/Preferences/backboardd.plist` | 存在（普通文件） |
| `mobile/Library/Preferences/.GlobalPreferences.plist` | 存在（普通文件） |
| `root/Library/Preferences/backboardd.plist` | 存在（普通文件） |
| `root/Library/Preferences/.GlobalPreferences.plist` | 存在（普通文件） |
| `db/com.apple.xpc.launchd/disabled.plist` | 不存在 |
| `db/com.apple.xpc.launchd/disabled.501.plist` | 不存在 |

未比较 ACL、xattr、文件 flags、内容或运行态，也未据此证明这些目录与 lsd 行为存在因果关系。
