# nuwa retained v1 Data — 主机记录 2026-11-28

**构建时 self-checked，未接设备、未刷写。** 后续 r3 终审及单次刷写见 [观察](nuwa-v1-retained-reset-flash-20261128-observation.md)；本文两份旧 outer 已被 r3 替代。`--data-v1-retained` 接通上游无日志 `PersistOverlay` mode 2，不使用 `dataProvider`，不定义 `NUWA_DATA_CANDIDATE`、`NUWA_DISPOSABLE_DATA`。复用 `UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1` / `PersistOverlay.h`、`DirectDisk.h`（BSD-2-Clause-Patent），不改 overlay 算法。UniXNU 构建 pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`；UniXNU、nuwa 远端 HEAD 前后分别是 `fdf81eaa832ce5c850d3c53c698407aa722a4653`、`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`，未合并。设备基座 `46437c1` 加本轮修改；期间并行提交 `a8ba712` 只改无关记录。

## 产物

| | 日常 | reset |
| --- | --- | --- |
| args ASCII 字节，不含 NUL（含 NUL） | 580 (581) | 599 (600) |
| `vendor_boot.img` SHA-256 | `751651713b188800939c4660a33558265cde20f3d34cc42a185a63a8f410d12d` | `695c7abab1fa7c276d6b6ce1edf538ef4bd50fbed23a927fd12484c2aa261e5c` |
| `readback-fat.img` SHA-256 | `4319f5169235db438edb2b23878164602bae5ee0294e6314866eaf0bdabda2f1` | `ffcfa84db9076faa54828135f9c8cb4c2dbf9d4c92901dff5e897e385d8fa2fb` |
| CHMH（SHA-384 值） | `73358feaa04f5d7733972fde642dd2dfe6f82db883fb3a89c391a5fb39545b6dbc524d4792017dbc5950d89cf5e9901a` | `6b8b4a898130c157f29e0173582d8284e4232c81782512141352e3a7117b0f9b6f9c462ad364836b8d9975a6acc4d0d8` |

两包共用 kernel SHA-256 `826e6726b8a0c59885e62746ff0289da606ffd6e98dda4bfd59c96d436c49ecc`（52,207,616 B）；outer 各 100,663,296 B，FAT 各 67,108,864 B。模板 FAT 只替换 kernel、ADT、配置，seed/trust 原样。reset 不是自清除标志，继续用该包启动会再次请求 reset。CHMH 按两套实际 args 分别绑定，不是认证证据。

日常 FAT 实测 args，reset 仅追加 ` sheng-data-reset=1`：

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=v1-retained boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 nuwa-sb-stack=900 disable-jobs=com.apple.iconservices.iconservicesagent nuwa-ufs-neon=1
```

## 轨迹与边界

默认相对窗口对应绝对 LBA `[59491258, 61588475)`，按 `last + 1 - reserve - blocks` 计算，验证根卷、log/export 尾区、预期 seed、LU0/4 KiB、主备 GPT 和相交的旧 v3/disposable 标记后才发布。日常错 v1 header seed 不初始化；显式 reset 按上游语义重建 v1，仍拒绝重叠的已识别 v3/disposable 标记。

真实生成的 encoder / response parser、store 和 RamBlock `StoreOps` 的 ASan/UBSan 模型轨迹：

```text
writeRun: 2a/08 59491332 n=32 -> 2a/08 59491364 n=1 -> 2a/08 59491259 n=1 (bitmap)
reset:    2a/08 59491259..59491322 n=1 each -> 35/00 LBA=0 n=0
          -> 2a/08 59491258 n=1 (header) -> 35/00 LBA=0 n=0
```

模型检查数据成功后才置位并写 bitmap，根读等同一 `gHost.lock`；越窗、错包 seed、日常错 header seed、旧两种格式、根或 log 重叠均零写。首个 flush 注入 CHECK CONDITION、超时、错误 tag 都不给 Overlay 成功，不写 header；第二个 flush 失败时虽已提交 header，Overlay 仍报 `Failed`。超时保留 orphan，不重新提交。

对最终 Mach-O 的 `llvm-objdump -d` 检查：`CombinedRead::issue` 的 `0xfffffff0079afbf0` 调用 `write10`，在 `0xfffffff0079afbf8` 写入 UPIU CDB；`write10` 在 `0xfffffff0079b0788` 装 `2090 = 0x082a` 并半字存储（LE `2a 08`），调用处不清 FUA。`0xfffffff0079afcfc`–`0xfffffff0079afd00` 写入 `53 = 0x35`，剩余 CDB 字节为零。

未改 DMA/IOMMU、锁实现或导出签名；沿用 Slot 0、现有 128 KiB 缓冲、`CombinedRead::issue` 与 1 s 命令期限。仍是上游 reset 顺序，未先作废旧 v1 header；中断 reset 不是原子回滚。未验证硬件 flush 时延、介质 FUA 耐久或断电恢复，未补旧固件 DMA 排除证据。两包 `device_release=false`，终包 review 和独立 verifier 未完成。

## 复跑

WSL Ubuntu-22.04 root，从设备工作树执行；最终构建、12 情形 fixture、两包、两次 `--audit-only`、两次 `fsck.fat`、post-event 和旧 retained 回归均 exit `0`。`test-nuwa-data-write.cpp` ASan/UBSan 亦 exit `0`。独立复跑请换新输出目录。

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
b=out/nuwa-v1-retained-20261128-build-r2
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
$p -B scripts/build-nuwa-display-native.py --base "$base" --cpo "$cpo" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --crashcap --pixsig \
  --data-persist-diag --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --data-v1-retained --post-event --out "$b"
$p -B tests/test-nuwa-v1-retained.py "$base" "$b"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-retained-entry.py out/nuwa-v1-shape-20261128-build "$base" --output out/nuwa-v1-retained-old-recheck
c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -no-pie -pthread \
  tests/test-nuwa-data-write.cpp -o out/test-nuwa-data-write-retained-v1
out/test-nuwa-data-write-retained-v1
for v in daily reset; do
  output="out/nuwa-v1-retained-20261128-$v"
  flags=()
  if [ "$v" = reset ]; then flags+=(--v1-reset); fi
  cmd=("$p" -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho"
       --out "$output" --v1-retained-template "$template" --post-event "${flags[@]}")
  "${cmd[@]}"
  "${cmd[@]}" --audit-only
  fsck.fat -vn "$output/readback-fat.img"
done
```
