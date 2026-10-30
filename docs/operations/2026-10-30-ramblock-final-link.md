# iOS16 RamBlock source-kernel link and initialization

## Scope

Stages S03/S05/S06. This opt-in CI extends the successful private-header build from run 40870837215, commit 4eac58c6064d961e9d8db15245161bdfed49859c. User approved an independent CI branch, scoped commits/pushes and CI on 2026-10-30. No device activity is authorized by this record.

The production 190-slot vtable and private reference are pinned in `config/ramblock-ios16-link-contract.json`. Current CI objects must match both. Eleven original IOBlockStorageDevice bindings refer to the fixed iOS16 donor; they do not supply donor code or make a deployable prelink.

## Implementation

`ramblock_kernel_link_check=true` compiles the production late archive, then runs `scripts/ci/build-ramblock-kernel.py`. It reuses actual baseline make arguments, force-loads platform and late RamBlock archives with the original storage bindings, and enables only the personality and late-registration caller. Existing root/Data mount flags remain unchanged.

The initialization patch loads IOStorageFamily, explicitly registers NativeRamBlock, and only then publishes IOBSD. Failed registration propagates through bsd_autoconf instead of silently continuing. Final checks require resolved symbols, exact donor bindings, direct call order, an explicit constructor call, and absence of duplicate automatic constructor registration.

## Validation and remaining gates

Local six-case make-input/parser tests passed against the real successful CI kernel; workflow YAML parsed; the late-init patch replay and production ABI checks passed. These are not an executed final macOS link. New CI must establish that result.

Even a successful source link does not qualify donor prelink, runtime metaclass/provider matching, complete root/Data mounting, persistence, init execution, or an on-device image. Full OS/SystemOS require their reviewed read-only block windows; the separate packed Data seed remains volatile. PROBE60 and the iOS16 mainline are unchanged.
