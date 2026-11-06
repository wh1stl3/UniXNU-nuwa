"""派生 P0-VNOP-DISPATCH r3 上机准备包（不碰设备、不建 trial/、不发 boot）。

复用 r2 已实机验证过的启动流程（多设备拓扑核验、reboot bootloader、
单次受控 getvar 组、恰好一次 fastboot boot、恢复后验），换绑 r3 的
精确 SHA、字段语义门、单一变量差异与判读矩阵。

用户 20:39 授权「继续直到下一轮实机录像确认」：本脚本只做离线准备，
停在录像确认门内。
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

R = Path(__file__).resolve().parent.parent
R2 = R / 'reports/p0-vnop-pair-20261105-r2'
OUT = R / 'reports/p0-vnop-dispatch-20261105-r3'
SCRIPTS = OUT / 'trial-scripts'
GATE = OUT / 'offline-gate'
MEDIA = R.parent / 'Media-nuwa' / 'P0-VNOP-DISPATCH-r3'

Q = json.loads((OUT / 'qualification.json').read_bytes())
S = json.loads((OUT / 'field-semantics.json').read_bytes())
BUILD = json.loads((R / 'out/p0-vnop-dispatch-20261105-r3/build.json').read_bytes())

IMAGE_SHA = Q['image_sha256']
KERNEL_SHA = Q['kernel_sha256']
SEM_SHA = Q['field_semantics_sha256']
REG_SHA = Q['regression_sha256']
CASES = Q['regression']['case_count']

# 全局替换：路径 / 候选名 / 精确 SHA / 常量
GLOBAL = [
    ('reports/p0-vnop-pair-20261105-r2', 'reports/p0-vnop-dispatch-20261105-r3'),
    ('out/p0-vnop-pair-20261105-r2', 'out/p0-vnop-dispatch-20261105-r3'),
    ('Media-nuwa/P0-VNOP-PAIR-r2', 'Media-nuwa/P0-VNOP-DISPATCH-r3'),
    ('boot-p0-vnop-pair-20261105-r2.img', 'boot-p0-vnop-dispatch-20261105-r3.img'),
    ('P0-VNOP-PAIR r2', 'P0-VNOP-DISPATCH r3'),
    ('P0-VNOP-PAIR-r2', 'P0-VNOP-DISPATCH-r3'),
    ("'cf4b0d8d4e8a0c6bf8de301c3e466753b3f8cacd1e65007c6156015a38229ae4'",
     "'%s'" % IMAGE_SHA),
    ("'1a7ad049a93de9c7cd80c008745d0a2003a2ad29fec65ce2dbefc475708dc72d'",
     "'%s'" % KERNEL_SHA),
    ("'81490ac7a42199935ee3bd1cc12fefb693ca421d85d1b8637cbfac596f7497a7'",
     "'%s'" % SEM_SHA),
    ("'1eb0d1e5d5bb1216cdc133c2213182c421cba52cc8c085275f4b5f036246a21d'",
     "'%s'" % REG_SHA),
    ('CASES = 78', 'CASES = %d' % CASES),
    ("q['status'] == 'OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE'",
     "q['status'] == 'OFFLINE_QUALIFIED_AT_RECORDING_CONFIRMATION_GATE'"),
    ("EXPECTED_FB03 = '56504E52'",
     "PHASE = dict(ENTR='0x454E5452', EARL='0x4541524C',\n"
     "             EPIL='0x4550494C', GUAR='0x47554152')"),
]

# preflight：字段语义门（r3 的 FB03/FB06/FB0F 写入源不再是 1）
OLD_FIELDS = """    for n in (3, 6, 7):
        assert by_id[n]['screen_label'] == 'FB%02X' % n
        assert by_id[n]['writer_count'] == 1, '字段 %d 写入源冲突' % n
    assert by_id[3]['expected'] == EXPECTED_FB03
    assert len(s['decision_matrix']) == 6
"""
NEW_FIELDS = """    for n, expected_writers in ((3, 3), (6, 2), (15, 3), (7, 1)):
        assert by_id[n]['screen_label'] == 'FB%02X' % n
        assert by_id[n]['writer_count'] == expected_writers, \\
            '字段 %d 写入源数量异常' % n
    assert 'ENTR' in by_id[3]['expected'] and 'GUAR' in by_id[6]['expected']
    assert s['constants']['GUAR'] == '0x47554152'
    assert len(s['decision_matrix']) == 6
"""

# preflight：单一变量段（r3 相对 P0 r1 是 5 个新挂点 + 撤掉 2 个）
OLD_DELTA = """    # 单一变量：相对 P0 r1，cave 外差异恰好 2 个字（强制断言，字段缺失即失败）
    build = read(ROOT / 'out/p0-vnop-dispatch-20261105-r3/build.json')
    r2 = build['r2_delta']
    assert r2['p0_outside_cave_diff_words'] == 2, '相对 P0 的 cave 外差异字数异常'
    assert r2['all_bytes_outside_declared_ranges_unchanged_vs_p0'] is True
    assert len(r2['p0_outside_cave_diff']) == 2
    assert r2['observations_added'] == 2
    assert r2['security_model_changed'] is False
    assert r2['stop_gate_added'] is False
    assert r2['repair_patches_removed'] == 0
    assert r2['field_conflict_check'] == dict(n3_writers=1, n6_writers=1, n7_writers=1)
"""
NEW_DELTA = """    # 单一变量：相对 P0 r1，cave 外差异恰好 5 个字（5 个新挂点）
    build = read(ROOT / 'out/p0-vnop-dispatch-20261105-r3/build.json')
    d = build['r3_delta']
    assert d['p0_outside_cave_diff_words'] == 5, '相对 P0 r1 的 cave 外差异字数异常'
    assert d['all_bytes_outside_declared_ranges_unchanged_vs_p0'] is True
    assert len(d['p0_outside_cave_diff']) == 5
    assert d['observations_added'] == 5
    assert d['observations_withdrawn'] == 2
    assert d['security_model_changed'] is False
    assert d['stop_gate_added'] is False
    assert d['repair_patches_removed'] == 0
    assert d['field_conflict_check'] == dict(n3_writers=3, n6_writers=2,
                                             n15_writers=3, n7_writers=1)
    # 撤掉的 r2 挂点必须保持 P0 r1 原生字节
    for w in d['withdrawn_hooks']:
        assert w['native'] in ('e3030091', 'f40300aa'), w
"""

# analyze：三字段配对 + 常量护栏
OLD_ANALYZE = """        arrival_guard=dict(FB03=EXPECTED_FB03, note='FB03 为定值 magic，'
                           '出现即证明通道与入口可见'),
        paired_reading_required=dict(
            entry='FB03', join='FB06', mac='FB07',
            note='FB06 是四路共用汇合点，单点不得解释为 VNOP_READ 已执行'),
"""
NEW_ANALYZE = """        arrival_guard=dict(
            FB03='ENTR/EARL/EPIL', FB06='GUAR', FB0F='GUAR',
            constants=PHASE,
            note='H1 每次 _VNOP_READ 入口画 ENTR + 两次 GUAR，兼作三行位通道有效性护栏'
                 '并重置启动早段其它 vnode 读对值字段的污染'),
        paired_reading_required=dict(
            phase='FB03', dispatch='FB06', ret='FB0F', mac='FB07',
            note='FB03/FB06/FB0F 必须三字段配对；单点不得解释为 vnop 已返回。'
                 'FB03=ENTR + FB06=x8 值 + FB0F=GUAR 才判 blr x8 已分派且未返回'),
"""

TRIAL_PLAN = """# P0-VNOP-DISPATCH r3 · 实机验证计划

2026-11-05 · 由 P0 r1 派生，把 r2 实机证实的「`VNOP_READ` 已进入未返回」
下钻到 `_VNOP_READ` 包装器的 `v_op` 分派点。

## 一、候选

| 项 | 值 |
|---|---|
| 内核 | `out/p0-vnop-dispatch-20261105-r3/kernel.macho` · `{kernel}` |
| 镜像 | `out/p0-vnop-dispatch-20261105-r3/boot-p0-vnop-dispatch-20261105-r3.img` · `{image}` |
| 离线状态 | `OFFLINE_QUALIFIED_AT_RECORDING_CONFIRMATION_GATE` · 回归 {cases} 项全通过 |
| 父候选 | P0-NATIVE-RESTORE r1（`ce75992b…`），**不是 r2** |
| 与 r2 关系 | 撤掉 r2 的 FB03/FB06 两个已消费 hook，新增 5 个下钻挂点；不构成严格 A/B |

## 二、五个挂点

| 挂点 | 原生指令 | 字段与值 | 作用 |
|---|---|---|---|
| `0x746C628` | `sub sp,sp,#0x70` | FB03=ENTR、FB06=GUAR、FB0F=GUAR | `_VNOP_READ` 入口 + 值字段重置 |
| `0x746C684` | `add x0,x0,#8` | FB06=`w8` | `0x746C680 ldr` 之后，x8 已是 v_op 分派目标 |
| `0x746C68C` | `mov x22,x0` | FB0F=`w0` | `blr x8` 返回首条，vnop 返回码 |
| `0x7466AC4` | `mov w0,#0x16` | FB03=EARL | `len<0` 早退阳性对照 |
| `0x7466B88` | `add sp,sp,#0xb0` | FB03=EPIL | `_vn_rdwr_64` 正常返回阳性对照 |

常量：`ENTR=0x454E5452`、`EARL=0x4541524C`、`EPIL=0x4550494C`、`GUAR=0x47554152`。

**挂点更正**：H5 原计划 `0x74669C8`，但它是 11 个真原生恢复点之一
（CHECK10 `c10_vn_rdwr_ret` epilogue witness），覆盖会撤销恢复点，
故改挂 `_vn_rdwr_64` 函数尾部 `0x7466B88`；`0x74669C8` 保持原生。

三行位全部复用已验证可见行位：FB03/FB06 在 CHECK10 实机作护栏出现，
FB0F 在 CHECK8/10 记为空白行位，FB07 在 r2 实机 `00000000`。
**未引入首次使用的行号。**

## 三、判读矩阵（必须三字段配对）

| FB03 | FB06 | FB0F | 判读 |
|---|---|---|---|
| ENTR | x8 值 | GUAR | **`blr x8` 已分派且未返回**；x8 给出 APFS vnop 目标地址 |
| ENTR | GUAR | GUAR | 卡在 `_VNOP_READ` 分派之前（`_uio_resid` 检查或 v_op 表读取）|
| ENTR | x8 值 | w0 值 | vnop 已返回；配合 FB07 与 10 大阶段判读卡点下移 |
| EARL | — | — | `len<0` 早退路径阳性对照命中 |
| EPIL | — | — | `_vn_rdwr_64` 正常返回阳性对照命中 |
| 全空白 | | | 按 AGENTS §6 只写「未观察到」，核对行位与挂点覆盖，不得写「未发生」|

H1 在每次 `_VNOP_READ` 入口重置 FB06/FB0F，末态只反映最后一次调用；
若存在并发读，值字段可能属于另一条读，须结合 10 大阶段时间线。

## 四、执行链（均需用户当轮明确确认后）

1. `trial-scripts/preflight.py --recording-confirmed "..." --recovery-confirmed "..."`
   - 离线断言（精确 SHA / {cases} 项回归 / 21 字段 / 5 差异字 / 安全模型）
   - 逐台 `getprop` 核验设备拓扑（可能同时有 `enuma` 与 `nuwa`）
   - `adb reboot bootloader` + **单次受控** getvar 组
     （`product` / `current-slot` / `unlocked` / `slot-unbootable:a` /
       `slot-retry-count:a` / `max-download-size`）
   - 设备已在 bootloader 时用 `--already-fastboot` 跳过 reboot
2. `trial-scripts/launch.py --confirm-launch "<用户原话>"`：**恰好一次** `fastboot boot`，
   写 `boot.json` / `consumed.json`，`resend_allowed=false`，禁止重发。
3. 全程 60fps 录像，从 boot 发出前开始，**不短于 9 s**
   （CHECK10 6.13 s / r2 5.982 s 均已记为限制）；原件投
   `Media-nuwa/P0-VNOP-DISPATCH-r3/original/`，派生帧投 `derived/`。
4. `trial-scripts/analyze-recording.py` 生成判读草稿 → 人工逐帧复核后写正式读数。
5. 实体键手动回 TWRP/fastboot 后跑 `trial-scripts/postcondition.py`。

约束：单次 `fastboot boot`、不重发、不 flash/erase/改槽、候选一次性消费、
不写分区、不提交 git；`OKAY` 只证明传输与命令被接受，内核进度由录像判读。

## 五、边界

本计划为离线准备：未发 boot、未 reboot、未 getvar、未建 `trial/`、
未改内核、未构建、未写分区、未改槽、未提交。
判读能力边界不变：本轮只收敛**位置**（到 `v_op` 分派目标地址），
不能定性原因（哪一层锁 / 完成事件 / DMA），也不能判断 EL0 之后。
阶段 H（EL0/ERET）仍「从未实机验收」。
""".format(kernel=KERNEL_SHA, image=IMAGE_SHA, cases=CASES)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    GATE.mkdir(parents=True, exist_ok=True)
    (MEDIA / 'original').mkdir(parents=True, exist_ok=True)
    (MEDIA / 'derived').mkdir(parents=True, exist_ok=True)

    changed = {}
    for name in ('preflight.py', 'launch.py', 'postcondition.py', 'analyze-recording.py'):
        text = (R2 / 'trial-scripts' / name).read_text(encoding='utf-8')
        for a, b in GLOBAL:
            text = text.replace(a, b)
        if name == 'preflight.py':
            assert OLD_FIELDS in text, 'preflight field-assertion block not found'
            assert OLD_DELTA in text, 'preflight delta block not found'
            text = text.replace(OLD_FIELDS, NEW_FIELDS).replace(OLD_DELTA, NEW_DELTA)
        if name == 'analyze-recording.py':
            assert OLD_ANALYZE in text, 'analyze semantics block not found'
            text = text.replace(OLD_ANALYZE, NEW_ANALYZE)
        # 禁串：不得残留 r2 专属路径、SHA 与结论常量
        banned = ['p0-vnop-pair-20261105-r2', 'P0-VNOP-PAIR', 'cf4b0d8d',
                  '1a7ad049', '81490ac7', '1eb0d1e5', '56504E52',
                  '5A5A5A5A', '0000C8A5', 'C10A55AA', 'user_observation',
                  'f_region', 'zero.draw', 'r2_delta']
        left = [x for x in banned if x in text]
        assert not left, (name, 'banned strings remain', left)
        (SCRIPTS / name).write_text(text, encoding='utf-8')
        changed[name] = dict(bytes=len(text.encode()), sha256=hashlib.sha256(
            text.encode()).hexdigest())

    (OUT / 'trial-plan.md').write_text(TRIAL_PLAN, encoding='utf-8')

    # 静态自检：4 个脚本语法可编译；离线断言演练（不碰设备）
    for name in changed:
        compile((SCRIPTS / name).read_text(encoding='utf-8'), name, 'exec')

    checks = []

    def ck(n, c):
        checks.append(dict(name=n, passed=bool(c)))

    ck('kernel_sha', sha(R / 'out/p0-vnop-dispatch-20261105-r3/kernel.macho') == KERNEL_SHA)
    ck('image_sha', sha(R / Q['image_path']) == IMAGE_SHA)
    ck('image_bytes', (R / Q['image_path']).stat().st_size == Q['image_bytes'])
    ck('sem_sha', sha(OUT / 'field-semantics.json') == SEM_SHA)
    ck('reg_sha', sha(OUT / 'regression.json') == REG_SHA)
    ck('regression_passed', Q['regression'] == dict(case_count=CASES, passed=True))
    r = json.loads((OUT / 'regression.json').read_bytes())
    ck('regression_all_checks_passed', r['passed'] is True and
       all(c['passed'] for c in r['checks']))
    ck('gate_unconsumed', Q['device_gate']['candidate_consumed'] is False and
       Q['device_gate']['device_actions_performed'] is False)
    ck('sem_21_fields', len(S['fields']) == 21)
    ck('sem_formula', S['generated_by_formula'] is True and
       '0xFB00 + N' in S['encoding_formula'])
    by = {f['field_id_decimal']: f for f in S['fields']}
    ck('writer_counts', [by[n]['writer_count'] for n in (3, 6, 15, 7)] == [3, 2, 3, 1])
    ck('phase_constants', S['constants'] == dict(
        ENTR='0x454E5452', EARL='0x4541524C', EPIL='0x4550494C', GUAR='0x47554152'))
    ck('decision_matrix_6', len(S['decision_matrix']) == 6)
    d = BUILD['r3_delta']
    ck('five_new_patch_sites', len(d['new_patch_sites']) == 5)
    ck('outside_cave_5_words', d['p0_outside_cave_diff_words'] == 5)
    ck('two_withdrawn', d['observations_withdrawn'] == 2)
    ck('security_unchanged', d['security_model_changed'] is False)
    ck('no_stop_gate', d['stop_gate_added'] is False)
    ck('no_repair_removed', d['repair_patches_removed'] == 0)
    ck('field_conflict', d['field_conflict_check'] == dict(
        n3_writers=3, n6_writers=2, n15_writers=3, n7_writers=1))
    ck('trial_absent', not (OUT / 'trial').exists())
    ck('media_dirs_ready', (MEDIA / 'original').is_dir() and (MEDIA / 'derived').is_dir())
    ck('trial_plan_exists', (OUT / 'trial-plan.md').exists())
    ck('scripts_syntax_ok', len(changed) == 4)

    readiness = dict(
        schema='Nuwa.OfflineReadinessGate.v2', candidate='P0-VNOP-DISPATCH r3',
        generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        status='READY_AT_RECORDING_CONFIRMATION_GATE',
        candidate_sha=dict(kernel=KERNEL_SHA, image=IMAGE_SHA,
                           field_semantics=SEM_SHA, regression=REG_SHA),
        offline_preparation=dict(
            trial_plan=True, trial_scripts=True, media_directories=True,
            analyze_recording=True, readiness_gate=True),
        generated_files=dict(scripts=changed, trial_plan='trial-plan.md'),
        static_selfcheck=dict(case_count=len(checks),
                              passed=all(c['passed'] for c in checks),
                              python_syntax_compiled=True,
                              banned_strings_absent=True,
                              trial_directory_absent=not (OUT / 'trial').exists()),
        checks=checks,
        gate=dict(
            status='STOPPED_AT_RECORDING_CONFIRMATION',
            reason='用户 20:39 授权「继续直到下一轮实机录像确认」；'
                   '离线准备完成，等用户当轮明确确认录像与实体键恢复',
            required_confirmations=[
                '全程 60fps 录像（≥9 s，从 fastboot boot 发出前开始）',
                '实体键恢复路径可用，启动后能手动回 TWRP/fastboot',
                '候选镜像 SHA 与未消费状态核验',
                '认证根前缀只读抽查（20:39 已实测完好，非阻断复核）'],
            boot_sent=False, candidate_consumed=False,
            device_actions_performed=False, partitions_written=False,
            slot_changed=False, git_committed_or_pushed=False),
        note='本生成器不碰设备、不建 trial/、不发 boot、不提交 git。')
    (GATE / 'readiness.json').write_text(
        json.dumps(readiness, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('scripts', len(changed), '| static checks', len(checks),
          'passed', all(c['passed'] for c in checks))
    for c in checks:
        if not c['passed']:
            print('  FAIL', c['name'])
    print('trial/ absent', not (OUT / 'trial').exists())
    print('media', MEDIA)
    print('gate', readiness['gate']['status'])


if __name__ == '__main__':
    main()
