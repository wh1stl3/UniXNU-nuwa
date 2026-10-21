# UniXNU 官方移植指南要点（2026-10-22 抓取）

> 来源：官方文档站，抓取时间 2026-10-22 02:56–03:00。
> 本文只是**摘录 + 对本仓的影响**，不是替代品；一切细节以原文为准。
> 原文链接集中在本文件末尾。

## 0. 三句话结论

1. 官方移植是 **两个仓库 + 一份板级配置**：`UniXNU-<device>`（设备仓）+ `uefi-<device>`（Mu-Silicium 固件仓），两者都以 `UniXNU` 基座仓为父。
2. **官方栈是 4 KiB XNU**（UniXNU 自带「4 KiB XNU 补丁」；sheng、fuxi 都是 4K）——与旧仓自建的 P16/16K 不是同一条路。
3. **同 SoC 已有社区移植**：`fuxi`（小米 13，SM8550）、`vermeer`（Redmi K70，SM8550）、`sheng`（小米平板 6S Pro，SM8550，官方维护、功能最全）。nuwa 不用从零开始，但要自己出板级数值。

## 1. 仓库结构（本仓目前缺两环）

| 仓库 | 内容 | 本机现状 |
| --- | --- | --- |
| `UniXNU`（基座） | 构建驱动、UEFI 启动管理器、DarwinBoot、通用驱动、4 KiB XNU 补丁 | 旧仓有副本 `D:\Code\PortingiOS\common\sources\UniXNU`，**未确认为官方最新** |
| `UniXNU-nuwa`（设备仓） | `board.toml`、`configs/*_defconfig`、驱动、kit、补丁、脚本、package | **= 本仓，已有骨架** |
| `uefi-nuwa`（固件仓） | Mu-Silicium 移植：设备配置、DSC/FDF、预检、厂商输入 | **缺，需新建** |

设备仓布局（官方）：

```
UniXNU-<device>/
  board.toml                 板级描述
  configs/<name>_defconfig   内核配置
  feeds.toml                 可选外部源码
  local.toml                 可选本地覆盖（Git 忽略）
  drivers/  kits/  patches/  scripts/  package/
  .gitmodules  .cache/firmware/（专有输入，不跟踪）  unixnu.lock
```

构建时设备仓以 `-D` 传入基座仓，输出到基座仓的 `out/<board>/`。

## 2. board.toml 的关键段（决定我们能改什么）

- `[board]`：`name`（`out/` 子目录名）、`soc`、`kit`、`description`；`example = true` 会让 `build`/`bootimg` 拒绝执行。
- `[ipsw]`：`url` / `product` / `version` / `build` / `device_class` / `chip_id` / `board_id` + `[ipsw.sha256]`，必须全部匹配才能用。
- `[userdata]`：`first_lba` / `last_lba`（取自设备 GPT 的 `userdata` 条目）、`lba_bytes`、`windows`（`OS`、`Cryptex1,SystemOS`）。
- `[kernel]`：`defconfig`、`archives`（链接前按序执行的静态库脚本）、`[kernel.prelink]`（`slide`、`early_security_init`、`roots`、`kernelcache_sha256`）。
- `[firmware]`：`config`、`dsc`、`fd`、`preflight`、`submodules`、`patches`、`packages`、`[firmware.defines]`。
- `[bootimg.image]`：`base`、`kernel_offset`、`tags_offset`、`pagesize`、`header_version`；`[[bootimg.dtb_node]]` 用来给原有 ABL 补节点（sheng 必须补 `/reserved-memory/splash_region`，否则 ABL 关屏）。
- `[payload]`：`volume`（≤11 字符）、`size_mib`、`loader`、`title`、**`dram_size`**、`panic_screen`、`kernel_args`。
- `[payload.adt]`：`tool`、`chip_id`、**`owned_memory_size`**、`root_match_volume_uuid`、`cpu_regs`、`psci_method`、`packed_data_ramdisk`、`ipad_identity`、`unique_chip_id`。

## 3. sheng 的实测数值（写 board.toml 时照这个形状抄）

```toml
[board]
name = "sheng"
soc = "SM8550"
kit = "sheng"

[ipsw]
product = "iPad7,1"           # iPadOS 17.7.11 / build 21H461 / device_class j120ap
chip_id = 0x8011
board_id = 12

[userdata]
first_lba = 0x2f3840
last_lba  = 0x3d0abfa
lba_bytes = 4096

[payload]
volume = "SHENGESP"
size_mib = 192
dram_size = "0x80000000"        # 2 GiB

[payload.adt]
owned_memory_size = "0x130000000"   # 4.75 GiB
cpu_regs = "0,0x100,0x200,0x300,0x400,0x500,0x600,0x700"
packed_data_ramdisk = true
ipad_identity = true
unique_chip_id = "required"
```

注意 **`dram_size` 与 `owned_memory_size` 不是一回事**：前者传给 ADT 工具描述物理 DRAM，后者是 XNU 自己要占的连续区，sheng 是 2 GiB vs 4.75 GiB。

## 4. ADT 契约里与内存直接相关的两条

`/chosen` 属性（官方「设备树」页）：

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `dram-base` | 64 位 | 物理 DRAM 基址 |
| `dram-size` | 64 位 | 物理 DRAM 大小 |
| `unique-chip-id` / `chip-id` | 64/32 位 | 生成 `IOPlatformUUID`；缺失会让 `gethostuuid()` 无限等 |
| `root-matching` | 字典 | 根卷匹配 |
| `darwinboot-memory-size` | 64 位 | **连续窗口请求，256 MiB–8 GiB，2 MiB 步进** |

→ **`darwinboot-memory-size` 上限就是 8 GiB（8192 MiB）**。这直接修正了 D-001 里「9216 MiB」的写法，见 D-002。

必需顶层节点：`/chosen`（含 `random-seed`、CHRP NVRAM proxy、DRAM 描述、`osenvironment`）、`/cpus`、`/arm-io`（GICv3 在 `intc` 子节点）、`/defaults`、`/options`。缺一个平台专家 `configure()` 就失败。
`/chosen/memory-map` 必须留 `RAMDisk`/`PackedRAMDisk`/`TrustCache` 占位符，缺则 DarwinBoot 返回 `EFI_COMPROMISED_DATA`。

## 5. bring-up 七阶段（判据可直接当验收清单）

| 阶段 | 目标 | 关键检查 |
| --- | --- | --- |
| 1 UEFI | 进 shell/菜单 | 固件卷大小对上、`fastboot boot boot.img` 不复位、framebuffer 有输出、块设备可见 |
| 2 UniXNU | 菜单出现 | 串口行以 `UNIXNU:` 开头、报告 entry/driver/patch/kit 数量 |
| 3 负载 | 读到 `unixnu.toml` 和负载文件 | 哈希与卷内一致、ADT sidecar 在内核旁 |
| 4 DarwinBoot | 校验并退出 boot services | 串口 `DARWINBOOT:`、打印 virt/phys 基址与入口、EL1 |
| 5 内核入口 | 到平台专家 | 版本+启动参数、bootstrap 页表映射内核窗口、`/cpus`、`/arm-io`、`/defaults`、`/options` 都在 |
| 6 存储与根卷 | 挂载根卷 | UFS 打印链路速度、分区方案发布 `OS`/`SystemOS`、UUID 匹配 |
| 7 用户态 | `launchd` 起来 | Data 卷挂载、显示有输出、`boot-progress=2` 看最后检查点 |

**QEMU fixture 可在无设备时验证阶段 2–5**：`scripts/qemu-entry/make-dt.py` + `package/Scripts/qemu-run.py`，能抓串口日志、截图、模拟按键。这是本仓最便宜的验证门。

## 6. 对 nuwa 的直接可用情报

- **fuxi（小米 13，SM8550）**：`UniXNU-fuxi` 自称「基于 UniXNU-sheng 的板级数据分支，沿用 iPad7,1 iPadOS 17.7.11 镜像和 sheng 的内核预链接」，UEFI package/预链接/触控/defconfig 仍在进行中，移植记录见其 `PORTING-FUXI.md`。→ **这是最有价值的对照，nuwa 的第一版 board.toml 应当照它抄结构再换数值。**
- **vermeer（Redmi K70，SM8550）**：`mansar1337` 仓有源码 XNU 构建基线（CI 编译+链接通过，产物不是启动镜像）；`yyx2025` 仓是从 sheng 派生的设备仓。
- **sheng（官方，功能最全）**：触控/显示/UFS/GPU 已通，Wi-Fi/蓝牙/摄像头/音频/传感器/休眠未通。作为「官方数值形状」的唯一权威样本。

## 7. 原文链接

- 移植总览 https://unixnu.com/zh/porting/
- 设备仓库 https://unixnu.com/zh/porting/device-repository
- UEFI 固件 https://unixnu.com/zh/porting/uefi-firmware
- 设备树/ADT https://unixnu.com/zh/porting/device-tree
- bring-up 顺序 https://unixnu.com/zh/porting/bring-up
- 支持设备总表 https://unixnu.com/zh/devices/
- sheng https://unixnu.com/zh/devices/sheng ｜ fuxi https://unixnu.com/zh/devices/fuxi ｜ vermeer https://unixnu.com/zh/devices/vermeer
- 配置参考 https://unixnu.com/zh/reference/configuration ｜ 故障排查 https://unixnu.com/zh/reference/troubleshooting
