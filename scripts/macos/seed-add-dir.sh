#!/bin/bash
set -euo pipefail
if [[ $# != 2 ]]; then
    echo "usage: sudo $0 RAW_IMAGE NEW_REPORT_DIRECTORY" >&2
    exit 2
fi
[[ $EUID -eq 0 ]] || { echo "ERROR: run with sudo for root:wheel ownership" >&2; exit 1; }
image=$1
report=$2
[[ -f "$image" && ! -e "$report" ]] || { echo "ERROR: image missing or report exists" >&2; exit 1; }
mkdir "$report"
device=
cleanup() {
    status=$?
    trap - EXIT
    if [[ $status -ne 0 ]]; then
        echo "ERROR: seed operation failed; recent APFS messages:" >&2
        dmesg 2>&1 | grep -i apfs | tail -40 >&2 || true
    fi
    if [[ -n "$device" ]]; then
        echo "+ hdiutil detach $device"
        hdiutil detach "$device" || status=1
    fi
    exit "$status"
}
trap cleanup EXIT
echo "+ hdiutil attach -readwrite -noverify -noautoopen -plist $image"
hdiutil attach -readwrite -noverify -noautoopen -plist "$image" > "$report/attach.plist"
device=$(/usr/libexec/PlistBuddy -c 'Print :system-entities:0:dev-entry' "$report/attach.plist")
mount=$(python3 - "$report/attach.plist" <<'PY'
import plistlib, sys
with open(sys.argv[1], 'rb') as f:
    mounts = [x['mount-point'] for x in plistlib.load(f)['system-entities'] if 'mount-point' in x]
if len(mounts) != 1:
    raise SystemExit('ERROR: expected exactly one mounted volume, got %d' % len(mounts))
print(mounts[0])
PY
)
base="$mount/containers/Data"
target="$base/Application"
[[ -d "$base" && ! -e "$target" ]] || { echo "ERROR: Data missing or Application already exists" >&2; exit 1; }
echo "+ diskutil apfs list"
diskutil apfs list > "$report/apfs-list.txt"
cat "$report/apfs-list.txt"
echo "+ inventory before"
inventory() {
    python3 - "$mount" "$1" <<'PY'
import hashlib, json, os, stat, sys
root, output = sys.argv[1:]
rows = []
for parent, dirs, files in os.walk(root, followlinks=False):
    for name in sorted(dirs + files):
        path = os.path.join(parent, name)
        rel = os.path.relpath(path, root)
        s = os.lstat(path)
        row = [rel, stat.S_IFMT(s.st_mode), stat.S_IMODE(s.st_mode), s.st_uid, s.st_gid]
        if stat.S_ISREG(s.st_mode):
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                for block in iter(lambda: f.read(1024*1024), b''):
                    h.update(block)
            row += [s.st_size, h.hexdigest()]
        elif stat.S_ISLNK(s.st_mode):
            row += [os.readlink(path)]
        rows.append(row)
with open(output, 'w', encoding='utf-8') as f:
    json.dump(sorted(rows), f, indent=1, ensure_ascii=True)
    f.write('\n')
PY
}
inventory "$report/before.json"
echo "+ mkdir $target"
mkdir "$target"
echo "+ chown root:wheel $target"
chown root:wheel "$target"
echo "+ chmod 0755 $target"
chmod 0755 "$target"
echo "+ inventory after"
inventory "$report/after.json"
echo "+ ls -ld Application System Data Bundle"
ls -ld "$target" "$base/System" "$base" "$mount/containers/Bundle" | tee "$report/siblings.txt"
python3 - "$report" <<'PY'
import json, os, sys
r = sys.argv[1]
with open(os.path.join(r, 'before.json')) as f: before = json.load(f)
with open(os.path.join(r, 'after.json')) as f: after = json.load(f)
added = [x for x in after if x[0] == 'containers/Data/Application']
if len(added) != 1 or added[0][1:] != [16384, 493, 0, 0]:
    raise SystemExit('ERROR: unexpected Application metadata')
if [x for x in after if x[0] != 'containers/Data/Application'] != before:
    raise SystemExit('ERROR: inventory changed beyond Application; inspect before.json and after.json')
with open(os.path.join(r, 'seed-diff.txt'), 'w') as f:
    f.write('Added: ' + json.dumps(added[0]) + '\n')
    f.write('Inventory entry count: %d -> %d\n' % (len(before), len(after)))
    f.write('Sibling comparison:\n' + open(os.path.join(r, 'siblings.txt')).read())
    f.write('\ndiskutil apfs list:\n' + open(os.path.join(r, 'apfs-list.txt')).read())
print('Inventory matches except new directory; see seed-diff.txt')
PY
echo "+ hdiutil detach $device"
hdiutil detach "$device"
device=
echo "DONE: $report/seed-diff.txt"
