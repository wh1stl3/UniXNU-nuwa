# r35 上机包（脚本与回滚），2026-11-20

主机侧准备，**未执行任何 adb/fastboot 命令**。设备仍跑 r34（`vendor_boot_a` `46aa4fd9…891e`），r35 未上机。

## 复用（未新造流程）

- 写入 / 回滚路线照 `out/nuwa-boot-payload-write-20261115-01/WRITE-r34.json`、`ROLLBACK-r34.md`、`ROLLBACK.md`、`BACKUP.json`：
  `fastboot -s <serial> flash vendor_boot_a <整镜像>`，按 `getvar product` 识别唯一 nuwa，`current-slot` 必须为 `a`，只写 `vendor_boot_a`，不改 slot，最多一次普通重启。
- 身份识别策略与 `current-slot` 解析复制自 `scripts/run-pmap-ret-once.py`（`identify()` / `current_slot()`）。
- 备份方式沿用 2026-11-15 的 TWRP `dd` + `adb pull` + 两次设备侧 `sha256sum`（`BACKUP.json`），不假设 `fastboot dump`。
- 授权留痕写法取自 `WRITE.json` 的 `authorization` 字段与 `scripts/nuwa-userdata-install.py` 的显式授权开关。

## 新增（工作树，`out/` 不入库）

| 路径 | 作用 |
| --- | --- |
| `scripts/nuwa-boot-payload-flash.py` | r35 写入；默认 dry-run，`--execute` 需固定 serial + 授权文本；本地哈希/`record.json`/`vendor_boot.json` 交叉核对；`out/.../nuwa-boot-payload-r35.claim` 防重放 |
| `scripts/nuwa-boot-payload-rollback.py` | 一条命令回 r34 或回原厂（`--to stock` 同时写 `vendor_boot_a` + `boot_a`） |
| `scripts/test-nuwa-boot-payload-flash.py` | 主机自检（假 runner，不触设备） |
| `out/.../ROLLBACK-r35.md` | 从 r35 到 r34 / 原厂两条路径 |
| `out/.../WRITE-r35.json` | 授权留痕骨架（值待执行时填） |

## 固定身份

- r35 `vendor_boot.img` 100663296 B `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed`；`kernel.macho` 55721984 B `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464`（在镜像内，不单独刷）。
- r35 CHMH `e767b49d…b94`、derived ADT `5a7df557…ddc`、payload `90a5447c…121e`，认证 NOT REACHED。
- r34 回滚目标 `46aa4fd9…891e`（kernel `ce24818e…f6dd`）；原厂 `493ca426…8dad` + `d530872b…c0d9`。

## 门禁（写入前）

槽位（唯一 nuwa、slot `a`、`partition-size` 读到时须为 `0x6000000`）→ 授权原文（`--authorization` 或 `NUWA_WRITE_AUTHORIZATION`）→ 本地哈希三处一致（镜像 / `vendor_boot.json` / `record.json` 的 kernel 输入）→ 回滚就绪（`ROLLBACK-r35.md` 两条路径的镜像在盘）。

## 验证状态

- 验证状态：**`self-checked`——脚本未经独立 verifier 复跑**，本轮只做了主机自检。
- `self-checked` 内容：`py_compile` 通过；`scripts/test-nuwa-boot-payload-flash.py` 9 正向 / 9 拒绝全过（含错误哈希、错误尺寸、篡改 `record.json`/`vendor_boot.json`、serial 不匹配、双 nuwa、slot b、无 OKAY 的 flash）；两个 CLI 的 `--help` 与 dry-run 正常；`--execute` 缺 serial / 缺授权 / 带 `--image` 均在触设备前拒绝（exit 2）；构造错误哈希镜像副本得 `REFUSED … exit 2`。
- 未验证（assumption）：`getvar partition-size:<part>` 实际输出格式按 `partition-size:vendor_boot_a: 0x6000000` 解析；**`boot_a.stock.img` 192 MiB 是否被 fastboot 接受未验证**；r35 上机行为本身。
