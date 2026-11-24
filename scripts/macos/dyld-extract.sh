#!/bin/bash
set -euo pipefail

if [[ $# != 2 ]]; then
    echo "usage: $0 IMAGE OUTPUT_DIRECTORY" >&2
    exit 2
fi
image=$1
out=$2
[[ -f "$image" ]] || { echo "ERROR: image not found: $image" >&2; exit 1; }
[[ ! -e "$out" ]] || { echo "ERROR: output already exists: $out (choose a new path)" >&2; exit 1; }
tmp=$(mktemp -d "${TMPDIR:-/tmp}/dyld-extract.XXXXXX")
device=
cleanup() {
    status=$?
    trap - EXIT
    if [[ -n "$device" ]]; then
        echo "+ hdiutil detach $device"
        hdiutil detach "$device" || status=1
    fi
    rm -f "$tmp/attach.plist"
    rmdir "$tmp" || true
    exit "$status"
}
trap cleanup EXIT
echo "+ hdiutil attach -readonly -noverify -noautoopen -nobrowse -stdinpass $image </dev/null"
if ! hdiutil attach -readonly -noverify -noautoopen -nobrowse -stdinpass -plist "$image" < /dev/null > "$tmp/attach.plist"; then
    echo "ERROR: attach failed; image may require a password, decoding, or be an unsupported format." >&2
    exit 1
fi
device=$(/usr/libexec/PlistBuddy -c 'Print :system-entities:0:dev-entry' "$tmp/attach.plist")
mounts=$(python3 - "$tmp/attach.plist" <<'PY'
import plistlib, sys
with open(sys.argv[1], 'rb') as f:
    for entity in plistlib.load(f)['system-entities']:
        if entity.get('mount-point'):
            print(entity['mount-point'])
PY
)
[[ -n "$mounts" ]] || { echo "ERROR: attached but no mounted volume; encrypted or unsupported APFS volume." >&2; exit 1; }
mkdir "$out"
found=0
while IFS= read -r mount; do
    echo "+ find $mount -type d -name com.apple.dyld"
    while IFS= read -r -d '' dir; do
        echo "dyld directory: $dir"
        while IFS= read -r -d '' file; do
            name=${file##*/}
            [[ ! -e "$out/$name" ]] || { echo "ERROR: duplicate basename $name" >&2; exit 1; }
            echo "+ stat and copy $file"
            stat -f '%N %z bytes' "$file"
            cp -p "$file" "$out/$name"
            found=$((found + 1))
        done < <(find "$dir" -maxdepth 1 -type f -name '*arm64e*' -print0)
    done < <(find "$mount" -type d -name com.apple.dyld -print0)
done <<< "$mounts"
if [[ $found -eq 0 ]]; then
    echo "ERROR: mounted, but no *arm64e* files found; arm64-only or wrong image." >&2
    exit 1
fi
echo "Copied $found entries to $out"
echo "For each cache file, inspect header magic and UUID bytes:"
echo '  xxd -l 16 "FILE"'
echo '  dd if="FILE" bs=1 skip=88 count=16 2>/dev/null | xxd -p'
echo "Confirm the main dyld_shared_cache_arm64e, all numbered shards and .symbols are present."
