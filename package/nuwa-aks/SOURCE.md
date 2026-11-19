# AppleKeyStoreState for nuwa (vendored)

- Upstream: `https://github.com/UniXNU/AppleKeyStoreState` (catalog id `AppleKeyStoreState`),
  revision `8c70daf814aafdf4a3d35e40dde0322655fd0a83`, path `drivers/AppleKeyStoreState`.
- Licence: BSD-2-Clause-Patent (`LICENSE` in the upstream directory, "Copyright (c) 2026,
  NativeKeyStoreEvents contributors").
- Vendored file: `NativeKeyStoreEvents.cpp`, byte-identical to upstream
  (sha256 `a39c1d84d56afebdbb9ea41b5ddc3f42031b811a938c660520c561128cbbd12f`). Not edited here:
  the component keeps its class names (`AppleKeyStore`, `AppleKeyStoreUserClient`), its exported
  `native_keyevents_allocate()` and its selector ABI.

## Why it is here

The r30 device run ended with keybagd asking for a plain reboot (`boot=11/keybag/0`) at
`t=72109 ms`, with the Data volume mounted writable (`DATA st=4`, `kb=ooo`): the keychain had no
AppleKeyStore behind it (no SEP on this board), which is what the component's README calls out —
software key wrapping from a board identity, no hardware data protection.

## What the board has to provide

The component calls six board-side functions (declared at the top of the file); `nuwa_aks.c` in
this directory implements them:

| symbol | nuwa implementation |
| --- | --- |
| `native_aks_state_enabled()` | 1 when the boot argument `aks=1` was given, else 0 |
| `native_aks_lock_state()` | 0 (unlocked since boot; there is no passcode path here) |
| `native_aks_call()` | selector/last-result counters for the page and the console |
| `native_aks_opened()` / `native_keyevents_open_refused()` | open counters |
| `native_aks_device_id()` | 8 bytes of `/chosen/unique-chip-id` (falling back to the 4-byte `/chosen/chip-id`) from the Apple ADT the loader passed; 0 when absent, which makes the component refuse to wrap instead of wrapping with a constant |

`nuwa_aks_wrap.cpp` holds the two things the component itself must not carry: the
`OSMetaClass::preModLoad()` → `__GLOBAL__sub_I_NativeKeyStoreEvents.cpp` → `postModLoad()`
bracket (the r28 lesson: a bare static initializer leaves the metaclass name a raw string), and
the explicit instance creation (`native_keyevents_allocate()` → `attach(getResourceService())` →
`start()`), which runs after `bsd_autoconf()` like the Data mount.

## Recorded as a fork

The identity source is ours, not upstream's (the sheng board answers `native_aks_device_id` from
its own component). Consequences, recorded here and in the round notes: the device key is stable
per ADT identity, the keychain survives a restart, nothing protects that identity, and keybag,
passcode and reference-key operations stay unsupported. This is not hardware data protection.
