# nuwa containers seed 调查 — 2026-11-24

状态：仅只读调查，**未补目录、未出包、未操作设备**。当前环境缺少对现有 APFS seed 的可写挂载能力。旧包回滚目标 outer SHA-256：`92494535a871f8406606cd711e2a8d76a01eb82a53ccc6365d2fa0fedb4157dc`。

## 与官方 seed 的完整差异

**尚未完成与官方实际生成 seed 的完整比较。** 官方 `UniXNU/scripts/make-data-seed.py:59–71` 动态复制 donor `private/var`，并在 `:76–91` 根据参数合并偏好；生成文件受输入、参数和挂载环境影响。未取得以相同输入和参数生成的官方 seed，不能把 donor 原树与官方最终产物等同。

本次只读比较了 donor OS `/private/var` 与当前包实际 seed：前者 9613 条，后者 331 条；donor 单有 9416 条均在 `staged_system_apps`，该树被官方 `make-data-seed.py:60` 明确排除。seed 相对 donor 多 134 条，共有条目中 62 条的类型、权限、所有者、文件哈希或链接目标不同。逐项机器清单在本地 `out/nuwa-containers-seed-20261124-package/inventory.json`，它是 **donor vs seed** 而不是官方最终 seed vs seed；不包含 ACL、xattr 和 APFS 元数据比较。Apple 输入及清单仅留本地 out。

| 条目 | 方向 | 来源 | 本轮处理 |
|---|---|---|---|
| `containers/Bundle`, `containers/Data/System`, `containers/Shared/SystemGroup`, `containers/Temp` 和父目录 | 两边都有；当前 seed 均 `0:0/0755` | `make-data-seed.py:72–74`；`seed-data-skip-setup.py:87–91` | 保留；回挂确认已存在，不新增 |
| `containers/Data/Application` | QEMU fixture 有、当前 seed 无；不是首装脚本的字面目录 | `prepare-offline-data.py:25–27,82–86`，脚本 `:2–7` 称 QEMU-only | 未补；是否纳入本次权威范围待定，且缺可写 APFS |
| 34 个 `containers/Shared/SystemGroup/systemgroup.com.apple.*`，各含 `Library/ucrt`；mobileactivationd 另含 `Library/dcrt`、`Library/internal` | seed 相对 donor 有；官方首装脚本没有字面生成这些叶目录 | `out/nuwa-systemgroup-seed-20261122/apply.log`；当前 seed 只读回挂 | 保留；各完整路径见本地 inventory 的 `seed_only`；不伪造 MCM metadata |
| `.fseventsd` 及其 11 个文件 | seed 相对 donor 有；是否由官方 APFS 生成流程产生未证 | 同上 inventory `seed_only` | 保留，仅记录 |
| `keybags/systembag.kb` | seed 相对 donor 有；官方首装脚本仅字面创建 `keybags` 目录 | `make-data-seed.py:72–74`；当前 seed 回挂 | 保留；keybag 生成来源未证 |
| `mobile/Library/Preferences/{backboardd,com.apple.managedconfiguration.notbackedup,com.apple.migration,com.apple.purplebuddy.notbackedup,com.apple.purplebuddy,com.apple.springboard}.plist` | seed 相对 donor 有；官方按配置也生成这些名称，不能判定官方最终内容是否相同 | `make-data-seed.py:23–29,76–91`；`seed-data-skip-setup.py:32–38,71–86` | 保留，仅记录；不补非容器文件 |
| `root/Library/Preferences/{.GlobalPreferences,backboardd}.plist` | seed 相对 donor 有；官方也生成这些名称 | `make-data-seed.py:23–29,88–91` | 保留，仅记录；未比较官方最终文件 |
| `mobile/Library/Preferences/.GlobalPreferences.plist` | 两边都有；seed 与 donor 内容哈希不同 | `make-data-seed.py:23–29,88–91`；本地 inventory `different` | 保留；官方合并结果未比较 |
| 其余 61 个 donor/seed 同名差异 | 与 donor 的类型、mode、uid/gid、文件哈希或链接目标至少一项不同，不等于官方最终 seed 差异 | 本地 inventory `different`，逐项记录两边实际值 | 保留，仅记录；待获取官方生成结果再判定 |
| 运行时遍历的 `source` 下内容 | 官方运行时输入决定；不能仅由脚本字面完整确定 | `make-data-seed.py:40,59–71` | 跳过静态推断；已有 donor 实查仅供参考 |

### 权限和文件的显式设置

| 条目 | 官方设置 | 当前 seed 及处理 |
|---|---|---|
| `tmp` | `make-data-seed.py:75` 设置 `01777` | 回挂 `0:0/01777`，保留 |
| 被复制的目录 | `make-data-seed.py:62–63` 复制 donor mode；未显式 `chown` | donor 与 seed 逐项值见 inventory；未据此认定官方最终所有者 |
| `merge` 写出的 plist | `make-data-seed.py:23–29` 设置 `0644`；未显式 `chown` | 已有文件保留；未验证全部内容与官方最终产物相同 |
| skip-setup 写出的 plist | `seed-data-skip-setup.py:32–38` 设置 `0600`；未显式 `chown` | 仅记录，未修改 |
| skip-setup 新建四个容器叶目录 | `seed-data-skip-setup.py:87–91` 设置 `0755`；未显式 `chown`，父目录未显式设置 | 回挂四条均 `0:0/0755`，保留 |
| 首装脚本新建容器目录 | `make-data-seed.py:72–74` 未显式 `chmod/chown` | 回挂均 `0:0/0755`，保留 |

未见上述两个官方脚本字面创建 MCM `.metadata` 文件或 keychain 占位文件；动态复制的 donor 文件不能因此排除。`prepare-offline-data.py` 是单独的 QEMU fixture，不与首装 seed 等同。
