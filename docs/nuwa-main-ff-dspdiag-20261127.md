# main 快进到 display/20h392-dsp-diag — 2026-11-27

纯仓库操作记录：无构建、无设备操作、无刷写、无重启。用户已同意以 `display/20h392-dsp-diag` 为主线，先把 `main` 快进到该分支 tip，暂不合并 Data 分支（等 DATA mnt 验收）。

- **前提核对**：`git merge-base --is-ancestor origin/main origin/display/20h392-dsp-diag` 退出 0（取推送前引用）；反向 `origin/display/20h392-dsp-diag..origin/main` 计数 0，`origin/main..origin/display/20h392-dsp-diag` 计数 143。来源：本轮 git 输出；状态：已验证。
- **快进**：`git push origin origin/display/20h392-dsp-diag:refs/heads/main` → `4548bbd..caac399`，退出 0；未使用 force，未产生 merge commit。本地 `main` 用 `git fetch origin main:main` 同步，退出 0。其他分支与各 worktree 检出未改动。来源：本轮 git 输出；状态：已验证。
- **快进前 main**：`4548bbd2be0d7bccc0c789ca62934842026c6384` 预置 r35 上机包：只写 vendor_boot_a 的 flash/rollback 脚本与 dry-run 自检。
- **快进后 main**：`caac3991ce2a4282f71951ad4a2af60ecfbd94fb` [nuwa] add opt-in retained UFS descriptor reads（即 `display/20h392-dsp-diag` tip）。
- **diff 统计**：`git diff --stat 4548bbd caac399` = 202 files changed, 28009 insertions(+), 130 deletions(-)。
- **Apple logo 证据所在分支**：`display/20h392-dsp-diag`；记录 [nuwa-logo-milestone-20261122.md](nuwa-logo-milestone-20261122.md)，提交 `57940ab8949feac5d6d283106d081b903f5c9e40`（`[nuwa] record Apple logo milestone`）。该证据为主控转述的用户实机观察，状态 self-checked，非独立 verifier 验收。
- **最后一次 Apple logo 的 outer SHA-256**：`c8abfda398ada2dab8ba915dc34659d2a16f0a9712f4596c62db27aafecc5b2a`；哈希出处 [nuwa-sb-restart-20261123.md](nuwa-sb-restart-20261123.md) 第 64 行（该包 args 仅多 `nuwa-sb-restart=400`）。「该包为最后一次到 Apple logo 的包」属主控转述，本记录未独立验证其画面归属。
- **合入后待办**：需一次实机确认默认包仍能到 Apple logo；该确认需当轮设备写入授权，且本次快进本身不构成上机证据。
- **不做**：未合并 Data 分支（`nuwa/dualbank-20261126`、`nuwa/ramblock-state-20261126` 等），等 DATA mnt 验收结论。
