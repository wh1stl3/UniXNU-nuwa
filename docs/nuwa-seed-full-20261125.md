# nuwa 完整目录 seed 交接（2026-11-25）

状态：**self-checked，仅主机和 VM，未上机**；待另一条线合并进最终包，本轮不制作 vendor_boot。

- 从已含 8 条目录的基线副本增量补齐其余 29 条及额外 lsd cache：新建 30、已存在跳过 0；pre/post 全树 `lstat` 清单分别 330/360 条，含根与临时 `.fseventsd/no_log`。原有条目 mode/uid/gid 未变；不创建 plist。
- 清单内 `lsd.iconscache/Library/Caches` 与 `mobilegestaltcache/Library/Caches` 的属主由规格的 `0:0` 改为 `501:501`，与已有父目录一致以允许 501 写入；额外 lsd cache 按要求为 `501:501`，不计入偏离。只读重挂清单与 post 的差异仅为收尾移除的 `.fseventsd` 相关项。`fsck_apfs -n` exit 0，volume 和 container 均显示 appears to be OK。
- 编辑后 raw：8,589,934,592 B，SHA-256 `203a34d1c0bf3c82ec0a5b1f7d4864f2afb65aec3f5291af8b4bf909acb0bbfc`；宿主与 VM 一致。官方编码器生成 2,560,160 B，文件 SHA-256 `c6688cd179c4af965c825fb6bb31b0f71c0c48802e97efe11079e1ccb7043081`。解码回环 raw SHA-256 与编辑后 raw 一致；`SHNGSEED2` 身份不是文件哈希。
- 本机交接：`out/seed-full-20261125/HANDOFF.txt`。回滚 outer 为 `d8d57a241bfbda143b0d6b007a95da7ede1e18ffdc61ad79108f3d5e9e9d1ed6`；本轮未修改该包。
- reviewer 先前提示的空 `db/dslocal`、`PersonaVolumes`、`preboot` 已按用户指示补齐，未经运行时验证。未验证 ACL、xattr、flags、时间戳及文件内容；认证 NOT REACHED。
