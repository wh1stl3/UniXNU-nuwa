#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下一步（继续适配移植）就绪度审计（2026-11-05，纯离线只读）。

从固定输入重算：当前卡点、唯一候选资格、上机前置门槛、
离线尚缺的准备项、以及四种实机读数各自对应的下一候选方向。
不操作设备、不改内核、不构建、不写分区、不提交。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'reports/next-step-20261105'
OUT.mkdir(parents=True, exist_ok=True)

IMAGE = R / 'out/p0-vnop-pair-20261105-r2/boot-p0-vnop-pair-20261105-r2.img'
KERNEL = R / 'out/p0-vnop-pair-20261105-r2/kernel.macho'
QUAL = R / 'reports/p0-vnop-pair-20261105-r2/qualification.json'
SEM = R / 'reports/p0-vnop-pair-20261105-r2/field-semantics.json'
REGR = R / 'reports/p0-vnop-pair-20261105-r2/regression.json'
R2_README = R / 'reports/p0-vnop-pair-20261105-r2/README.md'
HANDOFF = R / 'docs/HANDOFF-2026-11-05.md'
PENDING = R / 'docs/PENDING-HUMAN.md'
STATUS = R / 'docs/STATUS.md'
ROOT_INSTALL = R / 'reports/kmain-4-r1/installation/root-install-complete.json'
ROOT_RECOVERY = R / 'reports/kmain-4-r1/installation/post-root-recovery.json'
CHECK10_SCRIPTS = R / 'reports/ufs-check-10-r1/trial-scripts'
CHECK10_ANALYZE = R / 'scripts/analyze-ufs-check10-recording.py'
AGENTS = R / 'AGENTS.md'
MEDIA_ROOT = R.parent / 'Media-nuwa'
WORKLOG = R / 'docs/WORKLOG.md'
ROOT_ROUTE = R / 'docs/operations/2026-11-01-ufs-root-recovery-route.md'
READBACK = R / 'reports/ufs-root-readback-20261105/readback.json'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    inputs = {}
    for k, p in dict(image=IMAGE, kernel=KERNEL, qualification=QUAL,
                     field_semantics=SEM, regression=REGR, r2_readme=R2_README,
                     handoff=HANDOFF, pending=PENDING, status=STATUS,
                     root_install=ROOT_INSTALL, root_recovery=ROOT_RECOVERY,
                     check10_launch=CHECK10_SCRIPTS / 'check10-trial-launch-20261105.py',
                     check10_preflight=CHECK10_SCRIPTS / 'check10-trial-preflight-20261105.py',
                     check10_postcondition=CHECK10_SCRIPTS / 'check10-trial-postcondition-20261105.py',
                     check10_analyze=CHECK10_ANALYZE, agents=AGENTS,
                     worklog=WORKLOG, root_route=ROOT_ROUTE,
                     readback=READBACK).items():
        inputs[k] = dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size)

    q = json.loads(QUAL.read_text(encoding='utf-8'))
    s = json.loads(SEM.read_text(encoding='utf-8'))
    reg = json.loads(REGR.read_text(encoding='utf-8'))
    inst = json.loads(ROOT_INSTALL.read_text(encoding='utf-8'))
    rec = json.loads(ROOT_RECOVERY.read_text(encoding='utf-8'))

    by_id = {f['field_id_decimal']: f for f in s['fields']}
    img_sha = sha(IMAGE)
    assert img_sha == q['image_sha256'], 'image changed since qualification'
    assert sha(KERNEL) == q['kernel_sha256'], 'kernel changed since qualification'
    assert reg['passed'] and reg['case_count'] == 78
    assert q['status'] == 'OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE'
    assert q['device_gate']['candidate_consumed'] is False
    assert q['device_gate']['device_actions_performed'] is False
    assert all(by_id[n]['writer_count'] == 1 for n in (3, 6, 7))
    assert by_id[3]['expected'] == '56504E52'
    assert s['generated_by_formula'] is True

    # 上机前置：认证根写在 userdata 前缀，用户此前说「userdata 已经刷掉了」
    root = dict(
        image_sha256=inst['image_sha256'],
        authorized_bytes=inst['authorized_bytes'],
        target=inst['target'],
        edge_samples=rec.get('prefix_edge_samples'),
        note=('认证根写入 userdata 前缀 [0, 8445681664)；r2 的 FAT args 为 '
              '"-v native-ufs-root=1 launchdsuffix=release"，依赖这份根。'
              '若 userdata 此后被重刷/格式化，根可能已丢失，'
              'r2 上机会在根发现阶段失败、FB03/FB06 全空且无法归因。'
              '上机前须先只读核验前缀（或至少两处 64 KiB 边界抽样）与 4096 逻辑扇区几何。'),
    )

    # 用户 2026-11-05 14:50 澄清：「userdata 刷掉」= Android data 分区被刷成
    # nuwa 认证根，之后未再动过该分区。核对 WORKLOG 里 11-01 之后的所有轮次。
    wl = WORKLOG.read_text(encoding='utf-8', errors='replace').splitlines()
    userdata_lines = [
        dict(line=i + 1, text=l.strip()[:200])
        for i, l in enumerate(wl)
        if re.search(r'userdata|沿用UFS根|重写userdata|刷成', l, re.I)
        and re.search(r'2026-11-0[1-5]|^\d{4}-11-0', l)
    ]
    no_rewrite = [
        dict(line=i + 1, text=l.strip()[:180])
        for i, l in enumerate(wl)
        if re.search(r'(未|无|不).{0,12}(flash|erase|改槽|重写userdata|userdata写入)|沿用UFS根', l)
    ]
    clarification = dict(
        user_statement='userdata刷掉指的是Android的data分区被刷成我们的了 之后应该还没有动过这个分区',
        resolved_case='三情况中的情况 A：11-01 那次写入认证根前缀，旧 Android Data 失效；之后无二次写入',
        single_install_record='docs/WORKLOG.md:933 — 11-01 按明确授权安装认证根 userdata 前缀 8,445,681,664 字节，全量原始读回 SHA 一致',
        post_install_rounds_explicitly_no_userdata_write=len(no_rewrite),
        examples=no_rewrite[-6:],
        set_active_note=('KMAIN-18 的 set_active a 只更新 A/B 启动元数据（清 unbootable、重置 retry），'
                         '不写 userdata；WORKLOG:1023 明确「未刷写分区镜像」。'),
        device_readback_done=True,
        device_readback=json.loads(READBACK.read_text(encoding='utf-8'))['comparison'],
        consequence=('认证根逐字节完好，r2 的 -v native-ufs-root=1 前提实测成立；'
                     '不需要重写根、不触发分区写入授权门。'
                     '2026-11-05 15:05 已在 TWRP 下完成设备侧只读读回：'
                     '完整前缀 8,445,681,664 B SHA 与 11-01 基线一致，'
                     '两处 64 KiB 边界与前缀后紧邻 64 KiB 亦一致，几何未漂移。'
                     '该项抽查已关闭，不再作为上机前置。'),
        remaining_risk=('仍只证明字节完好，不证明 XNU 根发现/挂载成功或 r2 能到 EL0；'
                        '设备状态在本轮未改变（仍在 TWRP recovery）。'),
    )

    agent = AGENTS.read_text(encoding='utf-8')
    gate = dict(
        required_before_boot=q['device_gate']['required_before_boot'],
        hard_stop_flash_erase_slot='flash、erase、改槽位等仍须有具体目标、日志和恢复依据' in agent,
        no_guest_data_not_authorization='放弃旧数据也不等于授权格式化、分区写入或改槽' in agent,
        stage_boot_preauthorized='这个阶段开启实机无需授权' in agent,
        log_manual_loop_first='持久日志必须先手工writer/sync/reader与恢复闭环，再自动循环' in agent,
    )

    gaps = dict(
        r2_trial_plan_exists=(R / 'reports/p0-vnop-pair-20261105-r2/trial-plan.md').exists(),
        r2_trial_scripts_dir_exists=(R / 'reports/p0-vnop-pair-20261105-r2/trial-scripts').exists(),
        r2_media_original_exists=(MEDIA_ROOT / 'P0-VNOP-PAIR-r2/original').exists(),
        r2_media_derived_exists=(MEDIA_ROOT / 'P0-VNOP-PAIR-r2/derived').exists(),
        r2_analyze_script_exists=(R / 'scripts/analyze-p0-vnop-pair-20261105.py').exists(),
        check10_templates_available=all(
            (CHECK10_SCRIPTS / f).exists() for f in (
                'check10-trial-launch-20261105.py',
                'check10-trial-preflight-20261105.py',
                'check10-trial-postcondition-20261105.py')),
        note=('派生 CHECK10 模板时须替换候选 SHA、字段语义门（FB03/FB06/FB07）、'
              '单一变量差异字数与判读矩阵；禁止残留上一轮 round/user_observation/'
              'f_region/zero-draw 结论字符串（AGENTS §6）。'),
    )

    branches = [
        dict(case='FB03 出现 + FB06 出现',
             meaning='VNOP_READ 已调用且返回，后端完成链正常',
             next_candidate=('卡点下移到 exec 续接 / EL0：转向 process_signature → '
                             'FINAL_WAIT → proc_exec_switch_task → 0x3c3994 ERET 接线；'
                             '此时日志落盘价值上升（系统仍在跑、writer 能调度）。'
                             '不要再动 VNOP_READ 后端。')),
        dict(case='FB03 出现 + FB06 空白 + FB07=0',
             meaning='VNOP_READ 已进入但未返回（首要嫌疑证实）',
             next_candidate=('沿 APFS/decmpfs 锁、cluster/UPL、IOKit IOStorageCompletion '
                             '做下一层配对观测；查 UFS 完成事件与 gHost.lock 生命周期。'
                             '禁止靠静态嫌疑叠加认证绕过或换文件系统。')),
        dict(case='FB03 空白 + FB06 出现 + FB07 非零',
             meaning='MAC-read 拒绝直跳汇合点，VNOP_READ 未执行',
             next_candidate='按 FB07 的原生 AMFI errno 定位策略；两公开仓 L2 零覆盖，无现成补丁可抄。'),
        dict(case='FB03 空白 + FB06 出现 + FB07=0',
             meaning='write/swap 等直跳路径或挂点覆盖不全',
             next_candidate='回查挂点是否覆盖所有返回路径，补阳性对照后再下结论。'),
        dict(case='FB03/FB06 全空白',
             meaning='未到 0x7466B10，含 _vn_rdwr 入口 len<0 早退',
             next_candidate=('连续两轮以上阴性证据，按 AGENTS §6 必须安排阳性对照：'
                             '入口到达 + 早退路径 + 正常 epilogue 三路配对，先证函数被调用。')),
    ]

    ev = dict(
        schema='nuwa/next-step-readiness/1',
        question='为了继续适配移植，下一步做什么',
        inputs=inputs,
        answer=('唯一主线动作是消费已离线合格、未消费的 P0-VNOP-PAIR r2，'
                '单次临时启动取得 FB03/FB06 配对读数，把当前首要嫌疑'
                '「VNOP_READ 内部未返回」与「MAC errno 直跳」区分开。'
                '在此之前不做新候选、不引入日志落盘/permissive/文件系统切换。'),
        current_position=dict(
            furthest_confirmed='CHECK5：vfs_mountroot=0 (FB0A)、launchd namei (FB13=0)、mac_vnode_check_exec (FB12=A0000005)',
            ebs='2026-10-25 entry-probe-02 六色带，早就过了',
            el0='FB0D/FB0E 各轮 FFFFFFFF，阶段 H（EL0/ERET）从未实机验收',
            primary_suspect='0x7466B20 bl _VNOP_READ 内部未返回（APFS/IOKit 完成链）',
            alternatives=['_vn_rdwr 入口 len<0 早退绕过 epilogue',
                          '自建改道链（P0 已恢复，待实机验证）',
                          'Apple 原生 APFS 本身有 bug（几乎可排除）'],
        ),
        candidate=dict(
            name=q['candidate'], image_sha256=img_sha,
            image_bytes=IMAGE.stat().st_size,
            kernel_sha256=q['kernel_sha256'],
            status=q['status'], regression=reg['case_count'],
            fields=len(s['fields']),
            gate=q['device_gate'],
            four_state_matrix='见 reports/p0-vnop-pair-20261105-r2/README.md 判读矩阵'),
        root_prerequisite=root,
        userdata_clarification=clarification,
        authorization=gate,
        offline_gaps=gaps,
        post_boot_branches=branches,
        explicitly_not_now=[
            '内核日志落盘：producer 缺失、boot-arg 未传、reader 未闭环；且写入链与当前嫌疑链同源',
            'permissive 替身：服务 EL0 之后，amfi 替身不覆盖 mac_vnode_check_read',
            '换 HFS+ / BSD 裸 bdevsw：只对 ios-sweet 系成立，sheng 同样要过 APFS VNOP_READ',
            '再加观测挂点：r2 已是最小配对设计，上机前不动以免破坏单一变量',
            '改 board.toml 内存/基址字段、flash/erase/改槽、置 *_verified',
            'git 提交或推送',
        ],
        boundaries=[
            '本轮为路线与就绪度审计，未操作设备、未改内核、未构建、未写分区、未提交。',
            '候选单次消费、不重发；上机前必须确认认证根前缀仍在。',
            '离线合格不等于实机通过；判读须 60fps 逐帧局部 ROI RGB，不得只看末帧。',
        ],
    )
    (OUT / 'evidence.json').write_text(json.dumps(ev, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print('image/kernel match qualification: True')
    print('regression:', reg['case_count'], 'passed', reg['passed'])
    print('fields', len(s['fields']), '| FB03/06/07 writers',
          [by_id[n]['writer_count'] for n in (3, 6, 7)])
    print('gate:', q['device_gate']['status'], '| consumed', q['device_gate']['candidate_consumed'])
    print('gaps:', {k: v for k, v in gaps.items() if k.endswith('exists')})
    print('branches:', len(branches))
    print('written:', OUT / 'evidence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
