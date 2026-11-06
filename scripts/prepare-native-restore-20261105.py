"""Prepare the P0 native-restore patch triage. Offline only, no device access.

Uses out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho as the true native
byte reference (validated against 300 random non-patch words, zero mismatches),
NOT build.json 'before' (which is a previous-generation probe bridge at some sites).
"""
import sys, json, hashlib
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import flush_trace_inputs as trace

OUT = R / 'reports/native-restore-20261105'
CLEAN = R / 'out/ufs-check-4-r1-clean/kernel.macho'
CURRENT = R / 'out/ufs-check-10-r1/kernel.macho'
EARLY = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'
BUILD = R / 'out/ufs-check-4-r1-clean/build.json'
BUILD_CHECK10 = R / 'out/ufs-check-10-r1/build.json'
INVENTORY = R / 'reports/ufs-check-4-r1/patch-inventory-final.json'

# The ten coarse milestones already present in the current carrier. These are
# the "big stage" observers the user asked to keep (green band / HEX style).
BIG_STAGES = {
    0xfffffff0078e37a8: 'root_wait',
    0xfffffff007673098: 'root_return',
    0xfffffff0076732f4: 'root_auth',
    0xfffffff0076730e8: 'mount_return',
    0xfffffff00769d2a4: 'init_entry',
    0xfffffff00767356c: 'init_loaded',
    0xfffffff00769ce3c: 'exec_entry',
    0xfffffff00769bdd8: 'exec_namei',
    0xfffffff00769d624: 'exec_result',
    0xfffffff0073c3864: 'el0',
}
# Functional / adaptation sites that must NOT be restored blindly.
KEEP_FUNCTIONAL = {
    0xfffffff0078e331c: 'BSD root selector (mixed: observer + functional resume)',
    0xfffffff0084e56a0: 'mapped end / prelink adaptation',
    0xfffffff0084e5710: 'validate_increment / prelink adaptation',
    0xfffffff0084e5768: 'install_increment / prelink adaptation',
    0xfffffff0084e5740: 'map_permissions / prelink adaptation',
    0xfffffff00769d230: 'coarse_release_before: publishes ip_new_thread before FINAL_WAIT',
}


def word(macho, raw, va):
    off = trace.builder().backed(macho, va, 4)
    return raw[off:off + 4].hex()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    B = trace.builder()
    clean = CLEAN.read_bytes()
    current = CURRENT.read_bytes()
    early = EARLY.read_bytes()
    mc0, mc, me = B.macho(clean), B.macho(current), B.macho(early)
    build = json.loads(BUILD.read_text(encoding='utf-8'))
    check10 = json.loads(BUILD_CHECK10.read_text(encoding='utf-8'))
    inv = json.loads(INVENTORY.read_text(encoding='utf-8'))
    # CHECK4 is the clean parent; CHECK5/8/10 add cave hooks (notably
    # 0x769BF90/94, the self-built vn_rdwr detour). Merge by address so the
    # triage covers the whole currently-consumed carrier, not just the parent.
    changes = {}
    for src, tag in ((build, 'check4'), (check10, 'check10')):
        for c in src['changes']:
            va = int(c['address'], 16)
            if va not in changes:
                changes[va] = dict(c, first_seen=tag)
            else:
                changes[va]['seen_in_' + tag] = True
    # CHECK8/10 hook sites live only in the observer PATCHES tuples and are
    # absent from build.json changes; add them so the restore table is complete.
    for va, reason in {
        0xfffffff00769bfa4: 'CHECK8 c8_read_return (short-read path)',
        0xfffffff0074669c8: 'CHECK10 c10_vn_rdwr_ret epilogue witness',
        0xfffffff007673118: 'CHECK8 c8_selfcheck',
    }.items():
        changes.setdefault(va, dict(address=hex(va), before=None, after=None,
                                    reason=reason, first_seen='check8/10-observer'))
    live = {(int(x['patch']['address'], 16)): x for x in inv['entries']
            if x.get('status') in ('in-built-candidate', 'linked-in-candidate')
            and (x.get('patch') or {}).get('address')}

    rows = []
    for va, c in sorted(changes.items()):
        try:
            cur, nat = word(mc, current, va), word(me, early, va)
        except Exception as e:
            cur = nat = 'UNMAPPED:%s' % type(e).__name__
        before = c.get('before')
        if va in KEEP_FUNCTIONAL:
            cls, action = 'function', 'KEEP (review individually)'
        elif va in BIG_STAGES:
            cls, action = 'big-stage-observation', 'KEEP as big-stage milestone'
        elif nat != cur:
            cls, action = 'observer-or-bridge', 'RESTORE to native word'
        else:
            cls, action = 'already-native', 'NO-OP'
        rows.append(dict(address=hex(va), current=cur, native_from_earlysec=nat,
                         build_before=before,
                         build_before_is_native=(before == nat),
                         reason=c.get('reason'), first_seen=c.get('first_seen'),
                         seen_in_check10=bool(c.get('seen_in_check10')),
                         classification=cls, action=action,
                         inventory_category=live.get(va, {}).get('category')))

    counts = {}
    for r in rows:
        counts[r['classification']] = counts.get(r['classification'], 0) + 1
    lies = [r for r in rows if not r['build_before_is_native'] and r['current'] != r['native_from_earlysec']]
    result = dict(
        schema='Nuwa.NativeRestoreTriage.v1',
        purpose='P0 classification: what to restore to true native, what to keep',
        native_reference=dict(path=str(EARLY.relative_to(R)), sha256=hashlib.sha256(early).hexdigest(),
                              bytes=len(early),
                              validation='300 random non-patch words: 0 mismatches vs CHECK4 clean'),
        candidate_reference=dict(path=str(CLEAN.relative_to(R)), sha256=hashlib.sha256(clean).hexdigest(),
                                 bytes=len(clean)),
        current_consumed_carrier=dict(path=str(CURRENT.relative_to(R)),
                                      sha256=hashlib.sha256(current).hexdigest(), bytes=len(current),
                                      note="'current' column is read from the consumed CHECK10 kernel, not CHECK4 clean"),
        cave_only_hook_sites={hex(v): n for v, n in {
            0xfffffff00769bfa4: 'CHECK8 c8_read_return (short-read path)',
            0xfffffff0074669c8: 'CHECK10 c10_vn_rdwr_ret epilogue witness',
            0xfffffff007673118: 'CHECK8 c8_selfcheck',
        }.items()},
        build_sha256=hashlib.sha256(BUILD.read_bytes()).hexdigest(),
        check10_build_sha256=hashlib.sha256(BUILD_CHECK10.read_bytes()).hexdigest(),
        inventory_sha256=hashlib.sha256(INVENTORY.read_bytes()).hexdigest(),
        total_sites=len(rows), counts=counts,
        false_native_before_count=len(lies),
        false_native_before_examples=[r['address'] for r in lies[:12]],
        big_stages={hex(k): v for k, v in BIG_STAGES.items()},
        keep_functional={hex(k): v for k, v in KEEP_FUNCTIONAL.items()},
        sites=rows,
        limitations=[
            'earlysec is a donor-prelinked kernel, NOT a from-scratch Apple kernelcache; identical in 300 sampled non-patch words.',
            'segment geometry differs (59006976 vs 58335232 bytes); VA->offset mapping handled by macho().',
            '4 sites in 0x84e5xxx are unmapped in one of the two images (linked object region); flagged UNMAPPED.',
            'This is a static classification. No kernel rebuilt, no image emitted, no device accessed.',
        ])
    (OUT / 'patch-triage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('sites', len(rows), 'counts', counts)
    print('build.before != true native at still-patched sites:', len(lies))
    print('examples:', ', '.join(r['address'] for r in lies[:8]))
    for va, name in BIG_STAGES.items():
        r = next((x for x in rows if int(x['address'], 16) == va), None)
        print(' stage %-14s %s current=%s native=%s' % (name, hex(va), r['current'] if r else '?', r['native_from_earlysec'] if r else '?'))


if __name__ == '__main__':
    main()
