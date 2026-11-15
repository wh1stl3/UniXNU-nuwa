# nuwa root inputs — 2026-11-13

Self-checked host work; no device access or Apple trust claim.

The local UniXNU profile at base `693f5d9cae8a408dd18b39f3f9fdc4228c934241`
selects iPhone10,3 / d22ap erase, 16.7.16 / 20H392 and the Apple restore URL
in `profiles/os/ios-16.7.16-20H392/profile.toml`. The device lock pins XNU
`1b191cb58250d0705d8a51287127505aa4bc0789`. Profile `[ipsw.sha256]` pins
DeviceTree and trustcache, not OS or SystemOS; the root UUID is a placeholder.
The documented layout has OS and optional Cryptex1,SystemOS windows; OS UDIF
must be decoded to raw disk bytes before hashing/signing, not signed as a DMG.

Bounded checks covered Windows Administrator Downloads, device `.cache/firmware`
and `out`, base `out/ipsw/20H392`, and WSL `/home/wh1stl3/.cache` to depth 4.
No matching image or archive was found there; this is not a whole-machine search.
D: had 700765282304 free bytes before acquisition.

An experimental nuwa software-owner RSA3072/e65537 key was generated with
OpenSSL, and the official VerifiedRoot `974f043d0c71ba2e60331483a41c6c6d35274ee3`
`tools/manifest.py` public-anchor function produced the 395-byte anchor. Private
key and public files are in ignored `out/root-inputs-20261113/owner/`; Windows
ACL now limits access to current Administrator and SYSTEM. SHA256 of public DER
SubjectPublicKeyInfo is `717c2e0323dd356862829180a026f825fab1650d9eadaa3e5a301a513bf9fb43`;
anchor SHA256 is `6546a28755f44ab823c70f2da5e7e556b01a1fffe75275e02a26ab6e80625043`.
OpenSSL key check succeeded. The directory inherited broader Windows access
briefly at creation, before the ACL was restricted; no claim of prior secrecy
against other local principals is made. This is not an Apple trust anchor.

Official `unixnu ipsw fetch OS` and `unixnu ipsw fetch Cryptex1,SystemOS`
extracted from the profile's Apple URL into the exclusive output directory.
The extractor validated the d22ap erase identity and ZIP CRC, and these SHA256s
were independently recomputed; there is no profile pin for either image:

| IPSW member | Bytes | SHA256 |
| --- | ---: | --- |
| `087-86698-044.dmg` | 4730814044 | `80f426d5b8fca8552f95be427434f1911dbb4c2c6d28aad94f2426ddd0c92483` |
| `087-86593-047.dmg` | 2743074816 | `9cd738f3b0169055549df84ad6d8d13e50a2da39af618ce0522ca4e06df86849` |

The official UDIF reader decoded OS into `out/root-inputs-20261113/os-window.raw`,
5635081728 bytes, SHA256
`6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906`.
The official reader identifies SystemOS as raw, size 2743074816 bytes and SHA256
as above. The first raw extraction command failed at Python line 1 from literal
newline quoting; the corrected command completed. Official `unixnu build userdata`
completed with the cached inputs: its 8380219392-byte `userdata-root.img` SHA256
is `2c2aca3feb7585c91b80ec6b50cc1888ac9315f4c77d981566de5dd902eabefa`;
the OS window begins at 1048576, and SystemOS at 5637144576. Its recorded OS
window digest independently matches the standalone decoded stream above. Image and
report are in `out/root-inputs-20261113/nuwa/ios-16.7.16-20H392/nuwa/userdata/`.
No device command was executed. Actual APFS volume UUID and signed policy remain pending. Official
UUID identification requires macOS `diskutil apfs list`; no compatible local APFS
inspection tool was found in the bounded PATH check.

Follow-up: both download jobs and the userdata assembly returned successfully;
no download was restarted. On WSL, `command -v` found none of `diskutil`,
`hdiutil`, `apfs-fuse`, `apfsutil`, `apfs-fsstat` or `fsstat`; bounded checks of
`/usr/bin`, `/usr/local/bin` and `/opt/unixnu-linux/bin` found no APFS-named
tool. This does not establish absence elsewhere. The existing raw OS window and
matching userdata layout are ready for the official macOS read-only image attach
and `diskutil apfs list` procedure. The actual root volume UUID has not been
observed, so no manifest or const policy table has been fabricated or signed.
The owner key was not regenerated or overwritten in this follow-up.
