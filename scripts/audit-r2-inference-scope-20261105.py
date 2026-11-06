"""P0-VNOP-PAIR r2 单次上机的判读能力边界审计（2026-11-05，离线只读）。

回答「这轮上机之后能判断什么、能对卡点位置和原因做出什么判断」。
从固定输入重算：三个挂点的取值语义、5 行判读矩阵、10 个大阶段、
阴性证据纪律条款、逐门实机状态、五条后续分支；输出 evidence.json。

不操作设备、不改内核、不构建、不写分区、不提交。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/r2-inference-scope-20261105'
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    'r2_readme': R / 'reports/p0-vnop-pair-20261105-r2/README.md',
    'r2_semantics': R / 'reports/p0-vnop-pair-20261105-r2/field-semantics.json',
    'r2_qualification': R / 'reports/p0-vnop-pair-20261105-r2/qualification.json',
    'r2_source': R / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S',
    'p0_readme': R / 'reports/p0-native-restore-20261105-r1/README.md',
    'next_step': R / 'reports/next-step-20261105/README.md',
    'apfs_hfs': R / 'reports/apfs-vs-hfs-stack-20261105/README.md',
    'gate_table': R / 'reports/mac-trust-chain-verdict-20261105/README.md',
    'wiring': R / 'reports/native-restore-20261105/exec-el0-wiring.md',
    'agents': R / 'AGENTS.md',
    'status': R / 'docs/STATUS.md',
    'check10_result': R / 'reports/ufs-check-10-r1/trial/result.md',
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def text(key: str) -> str:
    return FILES[key].read_text(encoding='utf-8', errors='replace')


def inputs() -> dict:
    return {
        k: dict(path=str(p.relative_to(R)).replace('\\', '/'),
                sha256=sha(p), bytes=p.stat().st_size)
        for k, p in FILES.items()
    }


def observation_semantics() -> dict:
    sem = json.loads(text('r2_semantics'))
    by_id = {f['field_id_decimal']: f for f in sem['fields']}
    src = text('r2_source')

    assert '0xfffffff007466ad0' in src, 'MAC-read 挂点丢失'
    assert '0x7466B10' in src and '0x7466B24' in src, 'VNOP 配对挂点丢失'
    assert 'movz w1,#0x4e52' in src and 'movk w1,#0x5650,lsl #16' in src, \
        'FB03 定值 magic 实现丢失'
    assert 'mov w1,w0' in src, 'FB06 / FB07 的 w0 快照丢失'

    return dict(
        field_count=len(sem['fields']),
        fields=[
            dict(id_decimal=3, screen_label='FB03',
                 name=by_id[3]['name'], site='0x7466B10',
                 value_type='定值 magic 0x56504E52',
                 carries_errno=False,
                 proves='到达 _vn_rdwr_64 内 UIO_READ 分支的 VNOP_READ 入口',
                 limit='不携带参数、errno 或时间戳；只在 read 路径经过'),
            dict(id_decimal=6, screen_label='FB06',
                 name=by_id[6]['name'], site='0x7466B24',
                 value_type='w0（32 位）',
                 carries_errno=True,
                 proves='到达四条路径共用的汇合点',
                 limit='MAC errno / VNOP_WRITE / swap / VNOP_READ 四路共用；'
                       '单点出现不能证明 VNOP_READ 执行过，必须与 FB03 配对'),
            dict(id_decimal=7, screen_label='FB07',
                 name=by_id[7]['name'], site='0x7466AD0',
                 value_type='w0（32 位，mac_vnode_check_read 返回码）',
                 carries_errno=True,
                 proves='MAC-read 分派点已到达；0 = 放行，非零 = 原生 AMFI errno',
                 limit='空白只能写「未到达该分派点」，不等于「MAC 拒绝」'),
        ],
        coarse_milestones=10,
        coarse_note='10 个大阶段只给出「最后一个到达的阶段」，'
                    '颗粒度是阶段级，不是函数级或指令级',
        el0_fields=dict(
            FB0D='init_loaded / exec_result 共用行位，各轮 FFFFFFFF',
            FB0E='el0 大阶段，各轮 FFFFFFFF（从未实机验收）'),
        observation_medium='末态屏幕字段 + 60fps 逐帧局部 ROI RGB；'
                           '无调用栈、无寄存器快照、无时间戳、无内核日志、无运行时断点',
    )


def position_grid() -> list[dict]:
    matrix = [l.strip() for l in text('r2_readme').splitlines()
              if l.strip().startswith('- FB03=')]
    assert len(matrix) == 5, ('r2 判读矩阵应为 5 行', len(matrix))

    return [
        dict(
            reading='FB03 出现 / FB06 出现 / FB07 任意',
            position='VNOP_READ 已调用且返回；卡点在 read 之后',
            granularity='区间级：exec 续接 → EL0 之前这一整段',
            cause_excluded=['后端整体未返回', 'APFS 原生实现本身有 bug',
                            'len<0 早退', 'MAC errno 直跳'],
            cause_not_determined=['卡在 process_signature / FINAL_WAIT / '
                                  'proc_exec_switch_task / ERET 中哪一步',
                                  'EL0 之后任何阶段'],
            strength='位置：强（阳性证据）；原因：仅排除法',
            matrix_row=matrix[0]),
        dict(
            reading='FB03 出现 / FB06 空白 / FB07 = 00000000',
            position='VNOP_READ 已进入但未返回',
            granularity='区间级：0x7466B10 → 0x7466B24 之间',
            cause_excluded=['MAC 拒绝', 'len<0 早退', '自建改道链造成 read 前卡住',
                            'MAC errno 直跳导致 epilogue 空白'],
            cause_not_determined=['APFS vnop / decmpfs / cluster·UPL / '
                                  'IOStorageCompletion / gHost.lock / DMA 哪一层',
                                  '锁未释放 / 完成事件丢失 / DMA 超时 / 重入',
                                  '永久挂死 vs 录像窗口内超时'],
            strength='位置：强（首要嫌疑证实）；原因：仍为零',
            matrix_row=matrix[1]),
        dict(
            reading='FB03 空白 / FB06 出现 / FB07 非零',
            position='MAC-read 拒绝，直跳汇合点；VNOP_READ 未执行',
            granularity='门级：第 6 门 mac_vnode_check_read',
            cause_excluded=['后端/文件系统/存储栈卡住', '自建改道链'],
            cause_not_determined=['AMFI 内部哪条策略产生该 errno',
                                  '该 errno 是否可通过配置合法消除'],
            strength='唯一能把「原因」推进到具体数值的分支：FB07 即原生 AMFI 错误码',
            matrix_row=matrix[2]),
        dict(
            reading='FB03 空白 / FB06 出现 / FB07 = 00000000',
            position='从 write / swap 或其它直跳路径到汇合点；VNOP_READ 未执行',
            granularity='门级，但归因未定',
            cause_excluded=['VNOP_READ 后端卡住'],
            cause_not_determined=['是哪条直跳路径', '挂点是否覆盖所有返回路径'],
            strength='位置：弱；需回查观测覆盖',
            matrix_row=matrix[3]),
        dict(
            reading='FB03 空白 / FB06 空白 / FB07 空白',
            position='未到 0x7466B10；含 _vn_rdwr 入口 len<0 早退与更前',
            granularity='区间级，但为阴性证据',
            cause_excluded=[],
            cause_not_determined=['文件系统/存储栈完全无关（早退）',
                                  'MAC-read 之前停住', '观测挂点本身未生效'],
            strength='几乎不增加信息量：重演 CHECK10 阴性；'
                     '按 AGENTS §6 连续两轮阴性必须安排三路阳性对照',
            matrix_row=matrix[4]),
        dict(
            reading='guard: 10 个大阶段全空白 + trace_1 初始化字段也空白',
            position='framebuffer 通道或入口未执行',
            granularity='无',
            cause_excluded=[],
            cause_not_determined=['本轮全部读数'],
            strength='本轮读数全部无效',
            matrix_row='(guard 行，见 r2 README 第 27 行)'),
    ]


def discipline() -> dict:
    agents = text('agents')
    r2 = text('r2_readme')
    check10 = text('check10_result')
    clauses = {
        'blank_requires_three_proofs':
            '空白读数必须同时证明「通道有效」「行位可见」「挂点覆盖所有返回路径」三件事'
            in agents,
        'negative_two_rounds_requires_positive_control':
            '连续两轮以上靠阴性证据收窄区间时，必须安排**阳性对照**' in agents,
        'recording_duration_is_boundary':
            '录像时长不足计划值须写进证据边界' in agents,
        'check10_only_6_13s': '6.13' in agents or '6.13' in check10,
        'single_point_not_vnop_read':
            '单点读数不得解释为「VNOP_READ 已执行」' in r2,
        'blank_not_equal_not_happened':
            '不许写「未发生」' in agents,
    }
    assert all(clauses.values()), ('纪律条款缺失', clauses)
    return dict(clauses=clauses,
                positive_control_three_routes=['入口到达', '早退路径', '正常 epilogue'],
                note='空白只能写「未观察到」；本轮为单次临时启动、单候选单次消费、'
                     '禁止重发，无重复实验与严格对照组（CHECK10 是不同内核）')


def gates() -> dict:
    g = text('gate_table')
    return dict(
        passed=[
            'Image4 / MAC 早期初始化',
            'vfs_mountroot（FB09=0 / FB0A=0）',
            'FSIOC_KERNEL_ROOTAUTH（FB04=50 / FB05=1）',
            '/sbin/launchd namei（FB13=0）',
            'mac_vnode_check_exec（FB12=A0000005）'],
        undistinguished=['mac_vnode_check_read（第 6 门）',
                         'VNOP_READ → APFS/UPL/UFS 后端（第 7 门）'],
        never_device_verified=['process_signature / exec_mach_imgact（FB0D）',
                               'FINAL_WAIT / 新线程 EL0 / ERET（FB0E）'],
        el0_after=['trust cache / entitlements / Sandbox / KeyStore'],
        gate_table_anchored='逐门状态表' in g or '## 三、逐门实机状态' in g,
        note='本轮只可能在第 6–7 门内收敛；即使 read 返回，'
             '第 8–10 门仍为「从未实机验收」，不得写成已过',
    )


def p0_control() -> dict:
    lines = text('p0_readme').splitlines()
    sections: dict[str, list[str]] = {}
    cur = None
    for l in lines:
        s = l.strip()
        if s.startswith('### '):
            cur = s
            sections[cur] = []
        elif cur and s.startswith('- `0xfffffff'):
            sections[cur].append(s)
    retired = [k for k in sections if '恢复真原生' in k]
    observed = [k for k in sections if '必要观测' in k]
    assert len(retired) == 1 and len(observed) == 1, ('章节边界变化', list(sections))
    restored = sections[retired[0]]
    milestones = sections[observed[0]]
    assert len(restored) == 11, ('恢复点应为 11 个', len(restored))
    assert len(milestones) == 11, ('必要观测应为 10 大阶段 + 1 个 MAC-read 标记',
                                   len(milestones))
    assert any('mac_read_return' in m for m in milestones), 'FB07 标记缺失'
    p0 = '\n'.join(lines)
    return dict(
        restored_native_sites=len(restored),
        coarse_milestones=len(milestones) - 1,
        extra_marker='FB07 mac_read_return（不计入 10 大阶段）',
        is_diagnostic_control='P0 是诊断对照（看原生最远到哪一段）' in p0,
        added_judgement='与 CHECK10 同口径比较「最后一个到达的大阶段」：'
                        '若最远点前移，说明恢复 11 个自建改道字节移除了某个阻碍；'
                        '若最远点不变，说明自建改道链不是最远点的成因',
        limit='CHECK10 是不同内核且观测形态不同，这不是严格 A/B，'
              '只能作形态对照，不能据此宣称因果',
    )


def downstream() -> list[dict]:
    ns = text('next_step')
    rows = [l for l in ns.splitlines()
            if l.startswith('| 出现') or l.startswith('| 空白')
            or l.startswith('| 双空白')]
    assert len(rows) >= 5, ('五分支表缺失', len(rows))
    return [dict(branch=r, note='见 reports/next-step-20261105/README.md 第五节')
            for r in rows]


def main() -> None:
    ins = inputs()
    obs = observation_semantics()
    grid = position_grid()
    disc = discipline()
    gate = gates()
    ctl = p0_control()
    down = downstream()

    ev = dict(
        schema='nuwa/r2-inference-scope/1',
        question='这轮上机之后能判断什么，能对卡点位置和原因做出什么判断',
        answer=('位置：能。把当前「第 6–7 门未区分」收敛到 5 个互斥区间之一，'
                '颗粒度是门/区间级，不是函数级或指令级。'
                '原因：基本不能。即使证实「VNOP_READ 已进入未返回」，'
                '后端内部任何一层都没有观测点；唯一例外是 MAC 拒绝分支，'
                'FB07 会给出原生 AMFI 具体 errno。'),
        scope_split=dict(
            position='可收敛（阳性证据 + 排除法）',
            cause='只能排除，不能定性；单次上机无重复、无严格对照、无运行时状态'),
        candidate=dict(
            name='P0-VNOP-PAIR r2',
            kernel_sha256=json.loads(text('r2_qualification'))['kernel_sha256'],
            image_sha256=json.loads(text('r2_qualification'))['image_sha256'],
            gate_status=json.loads(text('r2_qualification'))['device_gate']['status'],
            candidate_consumed=json.loads(text('r2_qualification'))[
                'device_gate']['candidate_consumed'],
            kind='纯诊断候选，零修复；离线合格 ≠ 实机通过'),
        observation=obs,
        position_grid=grid,
        what_can_be_determined=[
            '最后到达的 10 个大阶段之一（最远点，阶段级）',
            'mac_vnode_check_read 是否到达 / 放行 / 拒绝，及具体 errno（FB07）',
            '是否到达 VNOP_READ 入口（FB03，布尔）',
            '是否到达共同汇合点及汇合点 w0（FB06）',
            '把卡点收敛到 position_grid 的 5 个互斥区间之一',
            'P0 恢复 11 点原生字节后，最远点相对 CHECK10 是否前移（形态对照）',
            '若 MAC 拒绝，拿到原生 AMFI 具体错误码（唯一落到具体数值的原因信息）'],
        what_can_be_excluded=[
            'MAC errno 直跳导致 epilogue 空白这一 CHECK10 替代解释',
            '自建改道链是卡点成因（若最远点与读数形态不变）',
            'len<0 早退（若 FB03 出现）',
            '后端整体未返回 / APFS 原生实现本身有 bug（若 FB03 与 FB06 都出现）'],
        what_cannot_be_determined=[
            'VNOP_READ 后端内部哪一层：APFS vnop / decmpfs / cluster·UPL / '
            'IOStorageCompletion / NativeUfs gHost.lock / DMA / IOMedia',
            '机制类型：锁未释放、完成事件丢失、DMA 超时、vnode 重入、线程饿死',
            '永久挂死 vs 录像窗口内超时（CHECK10 仅 6.13s 已记为限制）',
            '空白 = 未发生（按 AGENTS §6 只能写「未观察到」）',
            'EL0 / ERET 之后任何阶段（FB0D / FB0E 各轮 FFFFFFFF）',
            '修复方案是否有效（r2 不含任何修复）',
            '根因与因果证明（单次上机、单次消费、无重复、无严格对照组）',
            '是 nuwa 接线问题还是 donor 原生问题（只能排除前者的一部分）'],
        single_boot_limits=disc,
        gates=gate,
        p0_diagnostic_control=ctl,
        downstream_branches=down,
        honest_downside=(
            '若 FB03/FB06 双空白，本轮几乎不增加信息量，只是把 CHECK10 的阴性'
            '在同一形态下再确认一次；此时唯一正确动作是按 AGENTS §6 安排'
            '「入口到达 + 早退路径 + 正常 epilogue」三路阳性对照，'
            '而不是继续叠加静态分析或引入认证绕过。'),
        boundaries=[
            '本轮为离线判读能力审计，未操作设备、未启动内核、未改内核、'
            '未构建、未写分区、未改槽、未提交 git。',
            '设备连着、认证根已实测完好，但 r2 仍停在实机确认门，未消费。',
            '所有读数须由 60fps 录像逐帧局部 ROI 判读，不得只看末帧。'],
        inputs=ins,
    )

    (OUT / 'evidence.json').write_text(
        json.dumps(ev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('inputs:', len(ins))
    print('position grid rows:', len(grid))
    print('discipline clauses:', len(disc['clauses']),
          'all true:', all(disc['clauses'].values()))
    print('P0 restored sites:', ctl['restored_native_sites'])
    print('downstream branches:', len(down))
    print('written:', OUT / 'evidence.json')


if __name__ == '__main__':
    main()
