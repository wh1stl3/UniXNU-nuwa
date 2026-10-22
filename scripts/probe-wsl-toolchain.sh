#!/bin/sh
# Read-only host inventory; only the transcript is written inside this workspace.
set -u
probe() {
printf 'date='; date -Iseconds
printf 'kernel='; uname -srmo
printf 'distro='; cat /etc/os-release
for name in python3 make clang clang-14 clang-17 clang-18 clang-19 clang-20 clang-21 ld64.lld llvm-ar llvm-nm llvm-objcopy cmake ninja unifdef xcrun xcodebuild ditto mig migcom iig ctfconvert ctfmerge codesign; do
    if path=$(command -v "$name" 2>/dev/null); then
        printf 'tool:%s=%s\n' "$name" "$path"
    else
        printf 'tool:%s=MISSING\n' "$name"
    fi
done
for name in python3 make clang ld64.lld llvm-ar; do
    if command -v "$name" >/dev/null 2>&1; then
        printf 'version:%s\n' "$name"
        "$name" --version 2>&1 | head -n 2
    fi
done
printf 'compiler-feature-probe=preprocess-only,no-object-or-image\n'
printf '%s\n' \
 'xnu_type_signature=__has_builtin(__builtin_xnu_type_signature)' \
 'xnu_type_summary=__has_builtin(__builtin_xnu_type_summary)' \
 'xnu_types_compatible=__has_builtin(__builtin_xnu_types_compatible)' \
 | clang -target arm64-apple-ios16.0 -E -P -x c - 2>&1
printf 'project-python='; /mnt/d/Code/PortingiOS/.venv-wsl/bin/python -B --version 2>&1
for path in \
 /usr/bin/xcrun /usr/bin/xcodebuild \
 /Applications/Xcode.app /opt/SDKs /opt/osxcross/target/SDK \
 /mnt/d/Code/PortingiOS/common/sdks \
 /mnt/d/Code/PortingiOS/common/cache/sdks \
 /mnt/d/Code/PortingiOS/.venv-wsl/bin/python \
 /var/tmp/portingios-1000/xnu-linux-tools-20261020T165202299904Z/install/bin; do
    if [ -e "$path" ]; then
        printf 'path:PRESENT:%s\n' "$path"
        if [ -d "$path" ]; then ls -1 "$path" | head -n 35; fi
    else
        printf 'path:ABSENT:%s\n' "$path"
    fi
done
# Discover only SDK-named directories at bounded known tool/input locations.
for root in /opt /usr/local /mnt/d/Code/PortingiOS/common/tools /mnt/d/Code/PortingiOS/common/cache; do
    if [ -d "$root" ]; then
        printf 'sdk-search:%s:maxdepth=5\n' "$root"
        find "$root" -maxdepth 5 -type d -name '*.sdk' -print 2>/dev/null
    fi
done
printf 'note=SDK search is bounded; absence does not prove no SDK exists anywhere on the host\n'
}
probe | tee /mnt/d/Code/UniXNU-nuwa/reports/darwin22-audit/wsl-toolchain.log
