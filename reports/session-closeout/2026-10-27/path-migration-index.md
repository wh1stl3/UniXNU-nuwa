# Local path migration — 2026-10-26

<!-- path-migration-policy-2026-10-26 -->
## 后续路径统一约定（2026-10-26）

nuwa工作根为 `D:/Code/PortingiOS/nuwa`，enuma工作根为 `D:/Code/PortingiOS/enuma`；各自设备仓与独立固件仓的准确位置见下表。所有后续工作、新文档、脚本调用示例和交接都必须使用新路径，两个机型目录隔离，不可混用。旧资料库为 `D:/Code/PortingiOSLegacy`；历史证据中的旧路径只用于追溯，不能作为当前操作位置。原2395份保留记录未被统一改写，旧验证不会自动对迁移后文件生效。未移动的WithUniXNU/integration仍保持原位置。

This file is a relocation index, not new build/device validation or authorization.
The two project directories are `D:/Code/PortingiOS/nuwa` and
`D:/Code/PortingiOS/enuma`. Repository names retain their device suffixes.

| Previous location | Current location |
| --- | --- |
| `D:/Code/PortingiOS` (old reference/material tree) | `D:/Code/PortingiOSLegacy` |
| `D:/Code/UniXNU-nuwa` | `D:/Code/PortingiOS/nuwa/UniXNU-nuwa` |
| `D:/Code/uefi-nuwa` | `D:/Code/PortingiOS/nuwa/uefi-nuwa` |
| `D:/Code/UniXNU-enuma` | `D:/Code/PortingiOS/enuma/UniXNU-enuma` |
| `D:/Code/uefi-enuma` | `D:/Code/PortingiOS/enuma/uefi-enuma` |

Apply the same mapping to Windows backslashes, escaped JSON backslashes,
file URIs and `/mnt/d/Code/` paths. The old material tree's `common/`, `nuwa/`
and `enuma/` material moved to Legacy; it must not resolve to this new container.
`PortingiOSWithUniXNU`, `UniXNU-integration`, `Android` and both Videos folders
were not relocated. External repository URLs and source revisions are unchanged.

## Current entry points

- [nuwa instructions](nuwa/UniXNU-nuwa/AGENTS.md), [status](nuwa/UniXNU-nuwa/docs/STATUS.md), [handoff](nuwa/UniXNU-nuwa/docs/operations/2026-10-26-mainline-handoff.md).
- [enuma instructions](enuma/UniXNU-enuma/AGENTS.md), [status](enuma/UniXNU-enuma/docs/STATUS.md), [handoff](enuma/UniXNU-enuma/docs/HANDOFF.md).
- [Legacy reference tree](../PortingiOSLegacy/README.md).

## Preserved originals and limitations

Raw experiment logs, generated artifacts/build caches, hash-bearing reports,
pinned manifests, imported snapshots and append-only historical worklogs retain
their original bytes and historical paths. Resolve those paths with the table;
do not claim their hashes or successful validation describe modified source files.
No evidence hash, binary, archive, database, Git internal file or dependency tree
was rewritten. Changed scripts were not executed; no build, device operation,
commit or push was performed. A future implementation session must explicitly
review any source-hash qualification impacted by path-only source changes.

The enuma device repository's `firmware/` remains its existing relative Git
submodule checkout (`gitdir: ../.git/modules/firmware`); the separately moved
`uefi-enuma` checkout is not a replacement for it. Git status access was denied;
this maintenance did not retry it, alter Git/OS permissions, or repair Git metadata.

The scoped inventory covered the four migrated repositories, Legacy,
PortingiOSWithUniXNU, UniXNU-integration and both Videos directories, excluding
Git internals, private/credential/memory areas and fixed imported dependency/tool
trees. Unknown binary formats and three undecodable text candidates were retained.
Full per-file before/after hashes, retained-path inventory and exclusions are in
the maintenance audit at
`C:/Users/Administrator/Documents/Codex/2026-10-25/task/path-migration-audit/`.
Retained originals require an explicit derivative-copy/requalification decision;
they have not been silently converted into new evidence.
