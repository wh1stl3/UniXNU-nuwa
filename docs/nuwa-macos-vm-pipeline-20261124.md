# macOS VM 离线流水线 — 2026-11-24

**未完成：WSL 原始 seed 编解码已 self-checked，VM 编辑和完整流水线尚未验证。** Windows 原生 `python` 仍未验证；VM、APFS 挂载、outer 重打包及设备均未执行。

## 实测边界

- WSL `/home/wh1stl3/.local/bin/python3.11` 使用官方 `packed_ramdisk.regions()` 按 extent 展开当前 vendor_boot readback seed：2,121,888 B、SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`。raw 为 8,589,934,592 B，SHA-256 `2a7e965a8c625cfe57e723b07dd582e96114d857c0cbd1857ce3863072f43479`；展开 0.174 秒，SHA-256 另耗时 38.665 秒。头部 `NXSB`、块大小 4096、16 个卷槽中 1 个非零卷 OID；不证明卷可挂载。产物 `out/seed-raw-20261124/seed.raw`。
- 原样 raw 用官方 `packed_ramdisk.py RAW OUTPUT` 编码得到 2,121,888 B，SHA-256 与上述编码 hash 完全相同，`cmp` 相等；为 self-checked，独立 verifier 尚未复跑。大镜像输出的 `sha256` 字段是 `SHNGSEED2` 身份而非 raw SHA-256。
- `/mnt/d` DrvFs 的 `SEEK_DATA`/`SEEK_HOLE` 系统调用可用，但本 raw 上将整个文件报告为 data、只在文件末报告 hole；编码仍正确但须扫描 8 GiB，不能依赖稀疏跳过。若文件系统返回不支持，编码器会吞掉 `SEEK_DATA` 错误，可能静默输出空 extents；应在 WSL 原生文件系统建稀疏 raw、检验 seek 后编码，再拷回 `out/`。
- WSL 未安装 `apfs-fuse` 或 APFS 挂载工具，因此只读挂载未实测；当前环境无已验证的 APFS 读写挂载能力，编辑需 macOS。VM `hdiutil attach -readwrite`、编辑、detach 与 fsck 尚未执行。
- 编辑后的编码不应与原 seed hash 相等；预期是编辑后的 raw → 编码 → 展开后的 raw 逐字节及 SHA-256 相等。前提是成功 detach、raw 完整一致、4 KiB 对齐、非零页和 extent 数在格式上限内，且编码运行环境的 seek 正确；实际必须复测并分别只读检查、fsck，不能从未编辑回环推断 VM 成功。

## 格式与阻塞

固定 seed 为 `out/nuwa-systemgroup-seed-20261122/data-8g-sg.dbr`，2,121,888 B，预期 SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`；逻辑长度 8,589,934,592 B。`D:/Code/PortingiOS/UniXNU` HEAD `693f5d9cae8a408dd18b39f3f9fdc4228c934241` 的 `drivers/DarwinBoot/Test/packed_ramdisk.py:14-35,102-160` 表明这是 DBRDISK1 v1：4096 字节页、零页省略、有序 extent，并非 LZFSE。`inspect()` 中大于 2 GiB 的 `sha256` 是 `SHNGSEED2` 内容身份，**不是 raw 文件 SHA-256**。官方反向编码命令：

```text
python D:/Code/PortingiOS/UniXNU/drivers/DarwinBoot/Test/packed_ramdisk.py RAW_IMAGE OUTPUT.dbr
```

该脚本大于 2 GiB 时依赖 `os.SEEK_DATA`/`os.SEEK_HOLE`（第 87–117 行），Windows 原生兼容性未证明；WSL 实测见上。官方 `UniXNU/scripts/seed-data-skip-setup.py` 含展开逻辑及 macOS `hdiutil`，原样不是 Windows 展开 CLI。现有 `out/nuwa-systemgroup-seed-20261122/repack-seed-only.py` 是旧固定基线、固定 seed 和输出路径的封装，不是适用于任意 edited seed 的安全工具。它调用 r35 构建链并校验 outer/FAT/seed 回读，不能将它未修改地用于新 seed。未写通用 seed-prep/seed-pack，未产生新 vendor_boot。

官方上游 HEAD 本轮只读查询 `8542980d02b4d2cc5c32ee3542de1760b2562aac`，未更新本地 pin。无新增第三方依赖；两个 VM 脚本使用系统工具和 Python 3。

## 用户执行步骤（先做 dyld；seed 暂停）

1. **Windows 准备**：在项目 `out/` 下建立共享目录，如 `D:\Code\PortingiOS\nuwa\worktree-display-dsp\out\vm-share`；将 `scripts/macos/dyld-extract.sh` 复制到共享目录。将同 donor 的 `087-86698-044.dmg` 或其已有解码产物 `os-window.raw` 放到同一目录。预期共享目录内看到脚本和输入；不移动原始唯一副本。
2. **VM 试候选**：共享目录假设为 `/Volumes/VMShare`，输出目录必须不存在：

   ```bash
   bash /Volumes/VMShare/dyld-extract.sh /Volumes/VMShare/087-86698-044.dmg /Volumes/VMShare/dyld-arm64e
   ```

   预期列出每个 `*arm64e*` 文件名称和字节数、复制数及 header/UUID 检查命令，然后 detach。源文件前缀 `bvx n`，尚不证明 macOS `hdiutil` 能直接挂载；失败会报密码、需解码或不支持。若已有可信解码产物，改用 `os-window.raw` 并选择**新的**输出目录重试。没有解码产物则停下，勿把压缩流当作 APFS。输出目录在失败后可能不完整；核对后手动处理，重跑用新目录。
3. **判断及拷回**：目录须包含主文件 `dyld_shared_cache_arm64e`、同源全部编号分片和 `.symbols`；仅看到 `dyld_shared_cache_arm64` 或没有任何 `*arm64e*` 即未命中。`087-86593-047.dmg` 已知只有 arm64，不能作为 arm64e 成功候选；仅需对照时另选新目录运行。对主文件执行脚本打印的 `xxd`/`dd` 命令，保留文件名、大小、magic 与 UUID；再用同一共享目录复制完整文件集回 Windows `out/`。文件名、magic 本身不足以证明 20H392 版本或分片集合完整，须与原镜像和版本元数据核对。
4. **seed 等待**：原始 seed 编解码已 self-checked；edited seed 的回环、outer 重打包与独立回读仍待完成。后续准备好独立副本 `seed.raw` 后，VM 可运行：

   ```bash
   sudo bash /Volumes/VMShare/seed-add-dir.sh /Volumes/VMShare/seed.raw /Volumes/VMShare/seed-report
   ```

   预期 `seed-diff.txt` 报新增 `containers/Data/Application`、数量加一以及目录对照；最后 detach。脚本要求原目录不存在，重复执行必须从未编辑 raw 副本开始并用新报告目录。权限 `root:wheel`、0755 是本轮指定的实验值，脚本列出 System、Data、Bundle 供实测对照；**本轮没有实测同级权限，不能称已一致**。

## 更严格的 seed 验证

`before.json` 和 `after.json` 记录每个路径的类型、模式、uid/gid、普通文件大小及 SHA-256、符号链接目标；程序要求仅 Application 新增。它不覆盖 ACL、xattr、资源分叉、文件标志、时间戳、硬链接关系、根目录元数据或 APFS 内部数据，因此不能证明“其他所有内容不变”。目录数量并非 inode 数量，硬链接可使两者不同。应另对原始副本与编辑后副本只读挂载，分别运行（将 `$MOUNT` 替换为实际挂载点）：

```bash
sudo find "$MOUNT" -xdev -exec ls -ldeO@ {} \; > metadata.txt
sudo find "$MOUNT" -xdev -exec stat -f '%i %N' {} \; > inodes.txt
wc -l inodes.txt
awk '{print $1}' inodes.txt | sort -u | wc -l
diskutil apfs list
# 先卸载该映像的所有卷，再在确认属于该映像的容器设备上：
sudo fsck_apfs -n /dev/diskN
```

`diskN` 必须从该映像的 `hdiutil attach` 输出与 `diskutil apfs list` 确认，不可照抄；原始和编辑镜像分别运行。比对 metadata 清单时允许新目录和父目录变动，并人工检查其余差异；使用唯一 inode 数时按 inode 数字去重（路径不同不能作为去重键），fsck 必须分别无错误。时间戳、APFS 挂载副作用和目录父项变化需单独解释。以上是检查方案，不是已验证结果。

## 输出清单

| 位置 | 名称 | 大小 |
|---|---|---|
| VM 共享目录 | `dyld-arm64e/dyld_shared_cache_arm64e*` | 依源文件变化，脚本打印 |
| 本地 `out/seed-raw-20261124/` | `seed.raw` | 8,589,934,592 B，尚未复制到 VM |
| VM 共享目录，未来 seed 阶段 | `seed-report/{before.json,after.json,siblings.txt,apfs-list.txt,attach.plist,seed-diff.txt}` | 依内容变化 |
| Windows `out/`，未来阶段 | encoded seed / `vendor_boot.img` | 未生成，大小与路径尚未确定 |

Apple 镜像、缓存及其他衍生产物仅放本机 `out/`，不进 Git、CI 或 Release。用户复制文件到 VM 是用户执行，非本轮已执行。
