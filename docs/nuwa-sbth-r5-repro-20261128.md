# SBTH r5 重建输入与时间戳复放 — 2026-11-28

状态：**host self-checked；独立 verifier 尚未复跑**。本轮无设备操作。
从归档源码重建的 r6 内核与 r5 相同；普通打包得到的 r6 outer 因 FAT
目录项时间不同而不相同。将已记录的三个 FAT 时间字段复放到新 r7 包后，
`cmp` 与 SHA-256 均确认 r7 outer 逐字节等于 r5。
这不是认证、FUA 耐久或设备运行证据；CHMH 仍为实验值，认证 NOT REACHED。

| 产物 | 字节数 | SHA-256 | 说明 |
| --- | ---: | --- | --- |
| `out/nuwa-sbth-20261128-package-r5/vendor_boot.img` | 100663296 | `2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677` | 现存历史包，重新实算 |
| `out/nuwa-sbth-20261128-build-r6/kernel.macho` | 52207616 | `d2a673dc5b7c91f7cddafd8b33c54097815ad71cbab091b1444afee04098729c` | 与 r5 内核相同 |
| `out/nuwa-sbth-20261128-package-r6/vendor_boot.img` | 100663296 | `e3811ef4ba8f7e6e6ecb1521b97d6749e00ba72e79b2b1b2b8a67569c1029e86` | 未归一化 FAT 时间 |
| `out/nuwa-sbth-20261128-package-r7/vendor_boot.img` | 100663296 | `2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677` | 仅复放 FAT 时间，逐字节等于 r5 |
| `out/nuwa-sbth-20261128-package-r10/vendor_boot.img` | 100663296 | `2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677` | 按本文跨日复放脚本生成，逐字节等于 r5 |
| `out/nuwa-sbth-20261128-package-r12/vendor_boot.img` | 100663296 | `2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677` | 用合成次日 FAT 输入测试复放，逐字节等于 r5 |
| r7 `readback-fat.img` | 67108864 | `1c554cdc51fc3c75107636df918f8c29f7c8ab6677b82c2e530941bdb2145727` | 与 r5 FAT 相同 |
| r7 `kernel.macho.adt` | 13680 | `02ad65061e73b1dd5e64d62870cc80f694f394920720aecca60419cd0dfb1c46` | 与 r5 ADT 相同 |

## 源码和输入清单

- 历史 r5 的 device 基线是 `964d7e09c9397dcc306caba88fdbacc2ab82f35f`
  加当时的混合工作树；不是对归档提交的历史构建。r6 使用
  `46437c12cd58a667d7bbb904f7100d0eaace5d9a` 的 Git archive，tree
  `8869e6fb7bcdf5bf1acfa25531a4163bdc4d47b2`，没有把当前脏工作树当源码。
  该归档能重现内核，**不等于已还原全部历史未提交源码**。
- 关键归档源码 SHA-256：`scripts/build-nuwa-display-native.py`
  `b991a3fc6d4542f8afbfa3cc81d2e34fa903bb437d8f6a90b51b1ad0c21c2f82`；
  `scripts/generate_nuwa_postevent.py`
  `e22ea434067f19b0061be5963bf10ffdfdbaa6a28141d7e56c1968d292bd7a62`；
  `package/nuwa-ramblock/NativeRamBlock.cpp`
  `2e9904549a4dee31a17b0fb52924f7baa373c6b5aa7617991d0acd562d6ff64e`；
  `scripts/package-nuwa-crashcap.py`
  `73fbe0d98836f5a65ed17a7c2095b777b12e162fa63137e02a0129dc7e104994`。
- UniXNU 本地输入 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`；
  `drivers/ArmCpu@93a5030c5d983d0ef90f0fca93879d6e36ad1ba8`、
  `kits/XnuPrelink@f1d80d37528a33e24643583787123c652b70a268`、
  SM8550 common `a9f45dc60c035084b95463781538380f4c3606c9`。
  当前 XnuPrelink 检出中 `patches/xnu-10063.141.1-security-init.patch` 和
  `patches/xnu-10063.141.1-sparse-index.patch` 已脏；不能把其仅写成干净
  commit。实际本轮主机输入文件内容见下列 manifest，不能推断这两处改动影响了
  本包。开始及构建后远端 HEAD 均为 UniXNU
  `fdf81eaa832ce5c850d3c53c698407aa722a4653`、device
  `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`；未改变本地 pin。
- 原始只读模板
  `/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img`
  SHA-256 `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`；
  `--disposable-data-template` 从该模板重绑定 CHMH 和 args。
- CPO 为
  `/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json`，
  SHA-256 `d390eb4440c6854e0243d041f0cd329be419a10ef78facf9a90102f3822e0c70`；
  构建还依赖该本地 XNU tree 的 objects、headers、fakeroot 与 storage ABI，
  不能仅凭 CPO 文件重建。
- `--r35-dir out/nuwa-r35-20261119`、
  `--r35l-dir out/nuwa-r35l-regs-full-20261121`，以及
  `out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/`
  的 source、commands、provenance 与既有链接输入。r35 `build.py` SHA-256
  `c2e8bcc0aae8a6736592079b4f0bd1fba9032490ddfa432f30df9e6fbc619979`；
  r35l `commands.json` 为
  `1800c58e47041f25c580458f05e169c4803aa6fdb7b15513e6b7b068d44f0818`，
  `link.filelist` 为
  `f7ad5a33f2d9b924f18a8a367c7409e7e0b64c33faeba64910d3d9d1876ed19a`，
  `BootProgress.c` 为
  `bdfa725105977af83a9917be0209fe6701914587808d7f1b9c04a6fb4adb0c3e`。
  构建脚本还校验其余 r35l pins。
- donor `UniXNU/out/ipsw/20H392/kernelcache.decompressed` SHA-256
  `2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`；
  GPT 输入 `/mnt/d/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/gpt-sda.bin`
  SHA-256 `e96313e15bd43deeb7c871b863c27e8b253d2c6d9b2116f2f79347a4b030529c`。
  这些本地输入不入 Git。
- 打包其余输入：`.cache/boot-stage12-v4-r4.img` SHA-256
  `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`；
  `.cache/stock/vendor_boot_b.img`
  `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`；
  `out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt`
  `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`；
  `out/nuwa-peer-probe-20261125-staging/build-input.toml`
  `705d5240368d84bd0d9c0221af0fc86ba2093dbfe12a747a6af36fd8d0dd6261`。
  打包 wrapper 使用 device root 下的
  `scripts/build-chmh-only-payload.py`，本轮 SHA-256
  `e32a19c3e53911515d2a5bc56bda58ec4ff0b0ac29ef8c8572e14be705f7c0d4`，
  与归档相同。实验 CHMH SHA-384
  `b0fba4753e02a9ef53cbc1670271ff3b2c802ea807e85444295ff536d3e26fc70785d81f486a8cc5ef9b7d83dc8d734b`。
- WSL Ubuntu-22.04 root；Python 3.11.18；clang 24.0.0git commit
  `58c46bae21181fb4240cf964461bea738d96d50e`；ld64 956.6；mtools 4.0.32。
  clang/ld/Python/mcopy 可执行文件 SHA-256 依次为
  `ef33ad671b357e1542747fd6776e32c36b01c8ad08aa29fe9f95ff7804cca8f0`、
  `4f8a881dd4e4c1ff29c217a67bfd265582c1fb3bfebf989fdf5a3a4d9ba390a9`、
  `c5f068f0e33aa5ef0d8b2fccdc8cb91c78484ea15887937bd8c7b4585c3484a1`、
  `0aa5cae4b927d93519697abe281855a8d4847c93f03694e9fabb65dad807f512`。

为固定细粒度本地输入，`out/nuwa-sbth-20261128-repro-r6/` 保留：
归档 1216 文件的 `source.sha256`（文件自身 SHA-256
`fc0ef19e089fbce74378f9fa5ffea91058bb7730074bb82c2d4b19c963117555`）；
XNU tree 16475 文件的 `xnu-inputs.sha256`（
`961c29ca4de5fb1c9a3421f705c35d59efd6bcf48b60515d4487bee9b1ad570e`）；
主机基线 432 文件的 `host-inputs.sha256`（
`f79910141877cd33c2b14cceb21e11ec05e45612d90371495b9cdd41970b220b`）；
以及按顺序的 962 个 r6 链接文件 `link-inputs.sha256`（
`2b04871d796f3492ed569e343a0333d5661108d0a6b72409273fd23e44ee65d6`）。
四份 manifest 均已用 `sha256sum -c --quiet` 自检。后面三份是本轮实际本机状态，
不是对 r5 全部历史工作树的证明；丢失本地 XNU/模板等输入时不能仅靠 Git 重建。

## 参数与诊断

构建选择 `--cpu-only --no-software-vsync --candidate --mg-reset
--hid-standin --crashcap --pixsig --data-persist-diag --data-candidate-gpt
<GPT> --disposable-data --post-event --disposable-fua-permissive --sb-threads`。
`--sb-threads` 依赖 `--post-event`，是编译选项而不是 boot arg；
不选 `--smp-gate`、`--stage-channel` 或 v1 Data 选项。
`generate_r35_display_diag.py` 自动加入 banner 的 SpringBoard 行并删除字形
示例；`--crashcap` 增加 crash banner，`--post-event` 增加 DATA0/事件行。
没有独立 no-glyph 或 banner CLI 开关；`NUWA_GLYPH_SELFTEST` 默认仍为 1，
独立的非文字 pixel comb/bars 保留。没有添加 `boot-ui-trace` 参数。
`--disposable-fua-permissive` 是非耐久实验，不证明介质 FUA。

从实际 FAT `unixnu.toml` 读取的 args 为 602 字节文本，`nuwa-disposable-data=1`
恰好一次；无 `sheng-data-reset` 与 `sheng-smp`：

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=data-trial boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 nuwa-sb-stack=900 disable-jobs=com.apple.iconservices.iconservicesagent nuwa-ufs-neon=1 nuwa-disposable-data=1
```

## 在新目录复跑

以下 WSL 命令创建 r8/r9；若任一目录已存在，停止并换新名字。归档源码通过
`source/out` 链接到原本地输入的 `out`。此链接只用于读取既有基线和创建新输出；
不得把 r5/r6/r7/r10/r12 路径用于输出。

```sh
set -eu
root=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
gpt=/mnt/d/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/gpt-sda.bin
template=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
repro="$root/out/nuwa-sbth-20261128-repro-r8"
b="$root/out/nuwa-sbth-20261128-build-r8"
pkg="$root/out/nuwa-sbth-20261128-package-r8"
exact="$root/out/nuwa-sbth-20261128-package-r9"
test ! -e "$repro" && test ! -e "$b" && test ! -e "$pkg" && test ! -e "$exact"
mkdir -p "$repro/source"
(cd "$root" && git.exe archive --format=tar 46437c12cd58a667d7bbb904f7100d0eaace5d9a > "$repro/source.tar")
tar -xf "$repro/source.tar" -C "$repro/source"
ln -s "$root/out" "$repro/source/out"

cd "$repro/source"
"$p" -B scripts/build-nuwa-display-native.py \
  --base "$base" --cpo "$cpo" --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir "$root/out/nuwa-r35-20261119" --r35l-dir "$root/out/nuwa-r35l-regs-full-20261121" \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag --data-candidate-gpt "$gpt" \
  --disposable-data --post-event --disposable-fua-permissive --sb-threads --out "$b"
```

归档 packager 对 `ROOT/out` 做非 resolve 的路径检查，又需要原 device root 的
`.cache`、config 和本机输入。以下 wrapper 只在模块加载后将 `ROOT` 指回原
device root，未修改归档脚本；同时将归档的 scripts 放入 import 路径。
执行前核对上面的 live `build-chmh-only-payload.py` 哈希。

```sh
cat > "$repro/package-464.py" <<'PY'
import importlib.util
import sys
from pathlib import Path
here = Path(__file__).resolve().parent
device = here.parents[1]
sys.path.insert(0, str(here / "source/scripts"))
spec = importlib.util.spec_from_file_location(
    "sbth_archived_packager", here / "source/scripts/package-nuwa-crashcap.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ROOT = device
module.main()
PY
"$p" -B "$repro/package-464.py" --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --disposable-data-template "$template" --post-event
sha256sum "$b/kernel.macho" "$pkg/vendor_boot.img"
```

普通 `mcopy` 在 FAT 中写入打包时的时间。以下独立步骤将三个**已实测**的
创建、访问和修改日期，以及创建和修改时间复放到新包，以支持跨日复跑；
不从 r5 拷贝镜像内容。它先核对目录项名称、FAT、最终 FAT 与 outer 哈希，
任何其他字节不一致时在创建输出目录前退出。

```sh
cat > "$repro/replay-r5-fat-times.py" <<'PY'
import argparse
import hashlib
import shutil
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--input", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
old, new = a.input.resolve(), a.out.resolve()
image = bytearray((old / "vendor_boot.img").read_bytes())
assert image[:8] == b"VNDRBOOT" and len(image) == 100663296
start, size = 4096, 67108864
assert image[start:start + size] == (old / "readback-fat.img").read_bytes()
assert image[start:start + size] == (old / "payload.img").read_bytes()
for offset, short, time in (
    (1054880, b"UNIXNU~1TOM", bytes.fromhex("5209")),
    (1055328, b"KERNEL~1MAC", bytes.fromhex("5109")),
    (1055424, b"KERNEL~1ADT", bytes.fromhex("5209")),
):
    assert image[offset:offset + 11] == short and image[offset + 11] == 0x20
    date = bytes.fromhex("7c5d")
    image[offset + 13] = 0  # r5 creation tenths
    image[offset + 14:offset + 20] = time + date + date
    image[offset + 22:offset + 26] = time + date
fat = image[start:start + size]
assert hashlib.sha256(fat).hexdigest() == "1c554cdc51fc3c75107636df918f8c29f7c8ab6677b82c2e530941bdb2145727"
assert hashlib.sha256(image).hexdigest() == "2c36f34a1d7b1d8371a96cb29a62d36ea7bc36142eaef9f0d7d453398a3ee677"
new.mkdir()
(new / "vendor_boot.img").write_bytes(image)
(new / "payload.img").write_bytes(fat)
(new / "readback-fat.img").write_bytes(fat)
for name in ("kernel.macho.adt", "unixnu.toml"):
    shutil.copyfile(old / name, new / name)
PY
"$p" -B "$repro/replay-r5-fat-times.py" --input "$pkg" --out "$exact"
"$p" -B "$repro/package-464.py" --base "$base" --kernel "$b/kernel.macho" \
  --out "$exact" --disposable-data-template "$template" --post-event --audit-only
fsck.fat -vn "$exact/readback-fat.img"
cmp "$root/out/nuwa-sbth-20261128-package-r5/vendor_boot.img" "$exact/vendor_boot.img"
sha256sum "$root/out/nuwa-sbth-20261128-package-r5/vendor_boot.img" "$exact/vendor_boot.img"
```

## 差异及本轮实际检查

r6 与 r5 outer 的 header、tail、FAT 中全部 5 个文件内容相同。逐字节
比较只有 12 字节不同：outer 偏移 1054880 的 `UNIXNU~1.TOM` 目录项、
1055328 的 `KERNEL~1.MAC`、1055424 的 `KERNEL~1.ADT` 各自的 FAT
创建时间和最后修改时间；r5 小端时间分别为 `5209`、`5109`、`5209`。
三项的创建、访问和修改日期均为小端 `7c5d`，创建百分秒字段均为 `00`；
r5/r6 这些日期字段本来相同。r7 实际仅改时间字段，上面的跨日复跑脚本
另外固定同值的日期和百分秒字段。
这解释 r6 的 outer 差异，不是内核或工作树导致的载荷差异。

有证据的构建输入/中间文件差异如下：

- r5/r6 生成的 `BootProgress.c` 有三处 disposable 条件编译 guard 差异，
  分别保护 FUA 声明和 `bp_fua_suffix`；r6 使用了归档
  `scripts/generate_nuwa_postevent.py`。本 profile 定义
  `NUWA_DISPOSABLE_DATA=1`，最终内核逐字节相同。不能据此声称已知道 r5
  历史工作树每个差异文件。
- 生成的 `nuwa-data-provider/NativeUfs.cpp`、`CombinedRead.h`、
  `PreservedNop.h` 的文本差异是指向归档快照的 include 绝对路径。
  其 `NativeUfs.o`、`NativeUfs.late.o`、`libObserveNativeUfs.a` 也不同。
- 962 条链接文件中，内容不同的对象为 `ux_handler.o`、`bsd_init.o`、
  `kern_exit.o`、`ux_exception.o`、`nuwa_systemos.o`、
  `nuwa_data_mount.o`、`nuwa_watchdog_policy.o`、`nuwa_mg_reset.o`；
  本轮未将各对象差异全部归因于调试路径。最终 kernel 相同是直接哈希证据。

本轮实际命令用上述构建选项，输出目录分别为 `build-r6`、`package-r6`，
时间复放输出 `package-r7`；从本文脚本另生成 `package-r10`。以下检查均
**self-checked**：

- 编译、r6 打包、r6/r7/r10/r12 的 `package-464.py ... --audit-only`、
  `fsck.fat -vn` 均 exit 0；r10 FAT 剩余 11021312 字节。
- `tests/test-nuwa-sb-threads.py` 单独 host fixture exit 0；
  `scripts/test-nuwa-postevent.py --renderer <r6>/BootProgress.c --kernel
  <r6>/native-with-stabs.macho` 指定
  `C_INCLUDE_PATH=/mnt/d/Code/PortingiOS/nuwa/uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib`
  后 exit 0。
- 对实际 r6 build 直接运行完整 SBTH 审计时，
  `tests/test-nuwa-sb-threads.py:199` 的旧 no-glyph 源码逐字节断言失败，
  原因正是上述 guard 差异；**未宣称该原始断言通过**。将 r6 的三处 guard
  逆向规范化并证明结果恰等 r5 `BootProgress.c` 后，隔离审计目录使用该
  规范化副本、链接指向实际 r6 `nuwa_systemos.o` 和 `kernel.macho`，
  完整 SBTH fixture、链接反汇编及 r7/r10 outer 对 no-glyph 对照审计 exit 0。
- 本文复放脚本从 r6 生成 r10；另把 r6 的三个目录项改为模拟次日的日期、
  时间和百分秒，合成输入 outer SHA-256
  `82ad9a6b1933f458b3890743857447a445934f6e1ac85a62818b8ca65e6e84a2`，
  再从该输入生成 r12。`cmp` r5/r7、r5/r10、r5/r12 outer 均 exit 0，
  SHA-256 如上；次日输入是 host fixture，不是次日实际 mcopy 产物。
  全部日志、四份 manifest、
  规范化审计目录及本轮 helper 留在 `out/nuwa-sbth-20261128-repro-r6/`。
  首次 wrapper 少了归档 scripts import 路径，`package-nuwa-crashcap.py:199`
  报 `ModuleNotFoundError: nuwa_launch_context`；补入路径后才打包成功。
  首次 post-event 自检因快照位置改变找不到 `Font.h`，加入上面的
  `C_INCLUDE_PATH` 后才成功。

以下为本轮最终输入的复验命令；`compare-r5-r6.py` 会断言 r6 逆向规范化
后的源码恰等 r5，审计目录中的 `BootProgress.c` 是该结果的副本：

```sh
root=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
r="$root/out/nuwa-sbth-20261128-repro-r6"
b="$root/out/nuwa-sbth-20261128-build-r6"
pkg="$root/out/nuwa-sbth-20261128-package-r10"
template=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cd "$r/source"
"$p" -B "$r/compare-r5-r6.py"
"$p" -B tests/test-nuwa-sb-threads.py \
  --build "$r/normalized-audit" \
  --baseline "$root/out/nuwa-no-glyph-20261128-build/BootProgress.c" \
  --outer "$pkg/vendor_boot.img" \
  --baseline-outer "$root/out/nuwa-no-glyph-20261128-package/vendor_boot.img"
C_INCLUDE_PATH=/mnt/d/Code/PortingiOS/nuwa/uefi-nuwa/Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib \
  "$p" -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" \
  --kernel "$b/native-with-stabs.macho"
"$p" -B "$r/package-464.py" --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --disposable-data-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
cmp "$root/out/nuwa-sbth-20261128-package-r5/vendor_boot.img" "$pkg/vendor_boot.img"
sha256sum "$root/out/nuwa-sbth-20261128-package-r5/vendor_boot.img" "$pkg/vendor_boot.img"
```

这些结果不改变历史 r5 上机记录，也不授权新设备操作。r7/r10/r12 为本轮纯主机复现；
审查与独立 verifier 仍由主控按后续授权决定。
