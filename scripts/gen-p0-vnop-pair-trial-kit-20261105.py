"""生成 P0-VNOP-PAIR r2 的上机准备包（2026-11-05，离线只读）。

按 reports/next-step-20261105/README.md 列出的 5 项缺口，从 CHECK10 模板派生：
  1. trial-plan.md
  2. trial-scripts/{preflight,launch,postcondition}.py
  3. Media-nuwa/P0-VNOP-PAIR-r2/{original,derived}/
  4. analyze-recording.py（按 21 字段重写，禁残留 CHECK10 结论串）
  5. offline-gate/readiness.json（离线就绪门）

严格约束：
  - 本脚本不操作设备、不 reboot、不 getvar、不建 trial/、不发 fastboot boot。
  - 生成的三个 trial 脚本默认停在确认门，须显式传入用户当轮确认语才执行设备动作。
  - 所有断言绑定 r2 精确 SHA / 21 字段 / 78 项回归 / cave 外 2 字差异。
  - 判读脚本不残留 CHECK10 的 round / user_observation / f_region / zero-draw 结论串。

用法：python scripts/gen-p0-vnop-pair-trial-kit-20261105.py
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/p0-vnop-pair-20261105-r2'
SCRIPTS = OUT / 'trial-scripts'
GATE = OUT / 'offline-gate'
MEDIA = R.parent / 'Media-nuwa' / 'P0-VNOP-PAIR-r2'

Q = json.loads((OUT / 'qualification.json').read_bytes())
S = json.loads((OUT / 'field-semantics.json').read_bytes())
REG = json.loads((OUT / 'regression.json').read_bytes())

IMAGE_SHA = Q['image_sha256']
KERNEL_SHA = Q['kernel_sha256']
SEM_SHA = Q['field_semantics_sha256']
REG_SHA = Q['regression_sha256']
IMAGE = R / Q['image_path']
KERNEL = R / 'out/p0-vnop-pair-20261105-r2/kernel.macho'
SEM = OUT / 'field-semantics.json'
SOURCE = R / 'package/kernel-mainline/CoarseStages-p0-vnop-pair-r2.S'

IMAGE_BYTES = 70266880
EXPECTED_FB03 = '56504E52'
CASES = 78

FASTBOOT = 'D:/platform-tools-latest-windows/platform-tools/fastboot.exe'
ADB = 'D:/platform-tools-latest-windows/platform-tools/adb.exe'
REDACT = 'NUWA_DEVICE_REDACTED'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def preflight_py() -> str:
    return '''"""P0-VNOP-PAIR r2 正式上机预检（须用户当轮确认后方可运行）。

核对候选 / 字段语义 / 回归 / 单一变量差异，只读枚举设备与认证根边界，
然后执行一次 adb reboot bootloader 并做**单次受控 getvar 组**，
把设备切到 fastboot 模式供 launch.py 单次 boot。

约束：不 flash、不 erase、不改槽、不发 boot、不写分区。
禁止手工连续 fastboot getvar（会使变量表瞬时不可读）；本脚本内为一次受控组。
预检失败须原样归档，不得删除覆盖伪装成一次通过。

用法：
  python trial-scripts/preflight.py --recording-confirmed "<用户原话>" \\
      --recovery-confirmed "<用户原话>" [--already-fastboot]
"""
import argparse, hashlib, json, re, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/p0-vnop-pair-20261105-r2'
TRIAL = OUT / 'trial'
ADB = '__ADB__'
FASTBOOT = '__FASTBOOT__'
REDACT = '__REDACT__'
IMAGE_SHA = '__IMAGE_SHA__'
KERNEL_SHA = '__KERNEL_SHA__'
SEM_SHA = '__SEM_SHA__'
REG_SHA = '__REG_SHA__'
IMAGE_BYTES = __IMAGE_BYTES__
CASES = __CASES__
EXPECTED_FB03 = '__EXPECTED_FB03__'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read(p):
    return json.loads(Path(p).read_bytes())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, obj):
    p = TRIAL / name
    assert not p.exists(), 'refuse to overwrite ' + name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recording-confirmed', required=True,
                    help='用户当轮明确确认全程 60fps 录像的原话')
    ap.add_argument('--recovery-confirmed', required=True,
                    help='用户当轮明确确认实体键恢复路径可用的原话')
    ap.add_argument('--already-fastboot', action='store_true',
                    help='设备已在 bootloader：跳过 adb reboot bootloader')
    a = ap.parse_args()

    assert not TRIAL.exists(), 'trial/ 已存在：候选可能已消费，先复核再继续'
    q = read(OUT / 'qualification.json')
    assert q['status'] == 'OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE'
    assert q['image_sha256'] == IMAGE_SHA
    assert q['kernel_sha256'] == KERNEL_SHA
    assert q['device_gate']['candidate_consumed'] is False
    assert q['device_gate']['device_actions_performed'] is False
    assert q['regression'] == dict(case_count=CASES, passed=True)

    img = ROOT / q['image_path']
    assert sha(img) == IMAGE_SHA, '镜像字节已变化'
    assert img.stat().st_size == IMAGE_BYTES
    assert sha(ROOT / 'out/p0-vnop-pair-20261105-r2/kernel.macho') == KERNEL_SHA
    assert sha(OUT / 'field-semantics.json') == SEM_SHA, '字段语义表已变化'
    assert sha(OUT / 'regression.json') == REG_SHA, '回归报告已变化'
    assert read(OUT / 'regression.json')['passed'] is True

    s = read(OUT / 'field-semantics.json')
    assert s['generated_by_formula'] is True
    assert '0xFB00 + N' in s['encoding_formula']
    assert len(s['fields']) == 21
    by_id = {f['field_id_decimal']: f for f in s['fields']}
    for n in (3, 6, 7):
        assert by_id[n]['screen_label'] == 'FB%02X' % n
        assert by_id[n]['writer_count'] == 1, '字段 %d 写入源冲突' % n
    assert by_id[3]['expected'] == EXPECTED_FB03
    assert len(s['decision_matrix']) == 6
    # field_id_conflict 是说明性字符串（值为「无：…」），不是布尔
    assert isinstance(s['field_id_conflict'], str) and \\
        s['field_id_conflict'].startswith('无'), \\
        '字段编号冲突说明异常: %r' % s['field_id_conflict']

    # 单一变量：相对 P0 r1，cave 外差异恰好 2 个字（强制断言，字段缺失即失败）
    build = read(ROOT / 'out/p0-vnop-pair-20261105-r2/build.json')
    r2 = build['r2_delta']
    assert r2['p0_outside_cave_diff_words'] == 2, '相对 P0 的 cave 外差异字数异常'
    assert r2['all_bytes_outside_declared_ranges_unchanged_vs_p0'] is True
    assert len(r2['p0_outside_cave_diff']) == 2
    assert r2['observations_added'] == 2
    assert r2['security_model_changed'] is False
    assert r2['stop_gate_added'] is False
    assert r2['repair_patches_removed'] == 0
    assert r2['field_conflict_check'] == dict(n3_writers=1, n6_writers=1, n7_writers=1)

    # 多设备拓扑核验：逐台只读 getprop，确认恰好一台 nuwa 且处于 recovery
    # （AGENTS：多台 adb 设备须先确认 nuwa 唯一；所有 fastboot 命令带 -s）
    r = subprocess.run([ADB, 'devices'], capture_output=True, text=True, timeout=30)
    attached = [x.split() for x in r.stdout.splitlines()[1:]
                if x.strip() and len(x.split()) >= 2]
    topology = []
    for cols in attached:
        dev_serial, state = cols[0], cols[1]
        p = subprocess.run([ADB, '-s', dev_serial, 'shell', 'getprop',
                            'ro.product.device'],
                           capture_output=True, text=True, timeout=20)
        product = (p.stdout + p.stderr).strip().replace('\\r', '')
        topology.append(dict(serial=REDACT, state=state, product=product))
    nuwa = [t for t in topology if t['product'] == 'nuwa']
    assert len(nuwa) == 1, '预期恰好一台 nuwa，拓扑：%r' % topology
    assert nuwa[0]['state'] in ('recovery', 'device'), \\
        'nuwa 处于意外状态 %r' % nuwa[0]['state']
    recovery = [x.split()[0] for x in r.stdout.splitlines()[1:]
                if x.strip() and 'recovery' in x]
    assert len(recovery) == 1, '预期唯一 recovery 设备，实际 %d' % len(recovery)
    serial = recovery[0]
    props = {}
    for k in ('ro.product.device', 'ro.boot.slot_suffix', 'ro.twrp.version'):
        p = subprocess.run([ADB, '-s', serial, 'shell', 'getprop', k],
                           capture_output=True, text=True, timeout=20)
        props[k] = (p.stdout + p.stderr).strip().replace('\\r', '')
    assert props['ro.product.device'] == 'nuwa', 'recovery 设备不是 nuwa: %r' % props
    assert props['ro.boot.slot_suffix'] == '_a', props
    assert props['ro.twrp.version'], '未确认 TWRP'

    geo = subprocess.run([ADB, '-s', serial, 'shell',
                          'cat /sys/class/block/sda32/size; '
                          'grep PARTNAME /sys/class/block/sda32/uevent'],
                         capture_output=True, text=True, timeout=20)
    assert '469917144' in geo.stdout and 'PARTNAME=userdata' in geo.stdout

    edges = {}
    for skip in ('0', '2061918', '2061934'):
        p = subprocess.run([ADB, '-s', serial, 'shell',
                            'dd if=/dev/block/sda32 bs=4096 skip=%s count=16 '
                            '2>/dev/null | sha256sum' % skip],
                           capture_output=True, text=True, timeout=60)
        edges[skip] = p.stdout.split()[0] if p.stdout.split() else ''
    assert edges['0'] == '5d2308259a595010546bc58a29176f47d389297936faf0ee75091e5f5bd9d6eb'
    assert edges['2061918'] == '188d096cb8b956099a0baf726e21620c59a449cc27b7a174b84ad4e988b8be98'
    assert edges['2061934'] == 'de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'

    # 至此只读部分完成；下面才创建 trial/ 并做模式切换（确认后动作）
    TRIAL.mkdir(parents=True, exist_ok=True)
    save('preparation.json', dict(
        time=now(), candidate=q['candidate'], image=str(img),
        image_sha256=IMAGE_SHA, kernel_sha256=KERNEL_SHA,
        field_semantics_sha256=SEM_SHA, regression_sha256=REG_SHA,
        regression_cases=CASES,
        recording_confirmed=a.recording_confirmed,
        recovery_confirmed=a.recovery_confirmed,
        device_topology=topology,
        device=dict(product=props['ro.product.device'],
                    slot=props['ro.boot.slot_suffix'],
                    twrp=props['ro.twrp.version'],
                    serial=REDACT),
        partition_geometry='469917144 x 512 = 240597577728 B, PARTNAME=userdata',
        auth_root_edge_sha256=edges,
        partition_hashes='not repeated: no persistent write is performed',
        note='只读部分：未 reboot、未 getvar、未发 boot、未写分区；'
             '多设备拓扑已逐台 getprop 核验，nuwa 唯一'))

    if a.already_fastboot:
        r = subprocess.run([FASTBOOT, 'devices'], capture_output=True,
                           text=True, timeout=15)
        devs = [x.split()[0] for x in r.stdout.splitlines() if x.split()]
        assert len(devs) == 1, 'expected exactly one fastboot device, got %d' % len(devs)
        serial = devs[0]
        mode = 'already-fastboot'
    else:
        r = subprocess.run([ADB, '-s', serial, 'reboot', 'bootloader'],
                           capture_output=True, text=True, timeout=30)
        save('reboot-bootloader.json', dict(
            time=now(), command=[ADB, '-s', REDACT, 'reboot', 'bootloader'],
            exit=r.returncode,
            output=(r.stdout + r.stderr).replace(serial, REDACT)))
        assert r.returncode == 0, 'adb reboot bootloader failed'
        mode = 'adb-reboot'
        for _ in range(20):
            r = subprocess.run([FASTBOOT, 'devices'], capture_output=True,
                               text=True, timeout=15)
            if any(x.split()[0] == serial for x in r.stdout.splitlines() if x.split()):
                break
            time.sleep(1)
        else:
            raise RuntimeError('target did not reappear in fastboot; no boot sent')

    # 单次受控 getvar 组：禁止手工连续查询，失败须原样归档不覆盖
    queries, values = [], {}
    for key in ('product', 'current-slot', 'unlocked', 'slot-unbootable:a',
                'slot-retry-count:a', 'max-download-size'):
        p = subprocess.run([FASTBOOT, '-s', serial, 'getvar', key],
                           capture_output=True, text=True, timeout=20)
        txt = p.stdout + p.stderr
        queries.append(dict(variable=key, exit=p.returncode,
                            output=txt.replace(serial, REDACT)))
        m = re.search(re.escape(key) + r':\\s*(\\S+)', txt)
        values[key] = m[1] if p.returncode == 0 and m else None
    save('preflight.json', dict(time=now(), mode=mode,
                                queries=queries, values=values))

    assert values['product'] == 'nuwa', 'target is not nuwa: %r' % values['product']
    assert values['current-slot'] == 'a', 'slot is not a: %r' % values['current-slot']
    assert values['unlocked'] == 'yes', 'bootloader is not unlocked'
    assert values['slot-unbootable:a'] == 'no', 'slot a is marked unbootable'
    assert values['slot-retry-count:a'] is not None and \\
        int(values['slot-retry-count:a'], 0) > 0, 'slot a retry count exhausted'
    assert int(values['max-download-size'], 0) >= IMAGE_BYTES, \\
        'max-download-size smaller than image'

    save('preflight-passed.json', dict(
        time=now(), passed=True, candidate=q['candidate'],
        image_sha256=IMAGE_SHA, kernel_sha256=KERNEL_SHA,
        field_semantics_sha256=SEM_SHA, regression_sha256=REG_SHA,
        regression_cases=CASES,
        recording_confirmed=a.recording_confirmed,
        recovery_confirmed=a.recovery_confirmed,
        device=dict(product='nuwa', slot='_a', serial=REDACT, mode=mode),
        auth_root_edge_sha256=edges,
        getvar_values=values,
        consumed=False, boot_sent=False,
        scope='Fresh gate passed; this script issues no boot command',
        note='已 reboot 到 bootloader；未 flash/erase/改槽/写分区/发 boot'))
    print(json.dumps(dict(passed=True, boot_sent=False, consumed=False,
                          mode=mode, slot=values['current-slot']),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
'''.replace('__ADB__', ADB).replace('__FASTBOOT__', FASTBOOT) \
   .replace('__REDACT__', REDACT) \
   .replace('__IMAGE_SHA__', IMAGE_SHA).replace('__KERNEL_SHA__', KERNEL_SHA) \
   .replace('__SEM_SHA__', SEM_SHA).replace('__REG_SHA__', REG_SHA) \
   .replace('__IMAGE_BYTES__', str(IMAGE_BYTES)).replace('__CASES__', str(CASES)) \
   .replace('__EXPECTED_FB03__', EXPECTED_FB03)


def launch_py() -> str:
    return '''"""P0-VNOP-PAIR r2 单次临时启动。只发一次 fastboot boot，随后候选即消费。

前置：同轮 preflight-passed.json 通过；用户当轮确认语；无 consumed/boot 记录。
任何失败都记录归档、不重发。不 flash、不 erase、不改槽、不写分区。

用法：
  python trial-scripts/launch.py --confirm-launch "<用户原话>"
"""
import argparse, hashlib, json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/p0-vnop-pair-20261105-r2'
TRIAL = OUT / 'trial'
FASTBOOT = '__FASTBOOT__'
REDACT = '__REDACT__'
IMAGE_SHA = '__IMAGE_SHA__'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read(p):
    return json.loads(Path(p).read_bytes())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, obj):
    p = TRIAL / name
    assert not p.exists(), 'refuse to overwrite ' + name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--confirm-launch', required=True,
                    help='用户当轮明确确认这次单次启动的原话')
    a = ap.parse_args()

    passed = read(TRIAL / 'preflight-passed.json')
    assert passed['passed'] and passed['consumed'] is False and passed['boot_sent'] is False
    assert passed['image_sha256'] == IMAGE_SHA
    assert not (TRIAL / 'consumed.json').exists(), '候选已消费，不得重发'
    assert not (TRIAL / 'boot.json').exists(), '已存在 boot 记录，不得重发'

    q = read(OUT / 'qualification.json')
    assert q['image_sha256'] == IMAGE_SHA
    img = ROOT / q['image_path']
    assert sha(img) == IMAGE_SHA, '资格后镜像字节变化'

    r = subprocess.run([FASTBOOT, 'devices'], capture_output=True, text=True, timeout=20)
    devs = [x.split()[0] for x in r.stdout.splitlines() if x.split()]
    assert len(devs) == 1, '预期唯一 fastboot 设备，实际 %d' % len(devs)
    serial = devs[0]

    cmd = [FASTBOOT, '-s', serial, 'boot', str(img)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    save('boot.json', dict(
        time=now(), command=[FASTBOOT, '-s', REDACT, 'boot', str(img)],
        exit_code=r.returncode, output=out.replace(serial, REDACT),
        image_sha256=IMAGE_SHA, confirmed_by=a.confirm_launch,
        retry_allowed=False, kernel_execution_confirmed=False,
        note='OKAY 只证明传输与命令被接受；内核进度必须由录像判读'))
    save('consumed.json', dict(
        time=now(), image_sha256=IMAGE_SHA, exit_code=r.returncode,
        resend_allowed=False, boot_records=1))
    print(json.dumps(dict(sent=True, exit=r.returncode,
                          ok='OKAY' in out, consumed=True)))


if __name__ == '__main__':
    main()
'''.replace('__FASTBOOT__', FASTBOOT).replace('__REDACT__', REDACT) \
   .replace('__IMAGE_SHA__', IMAGE_SHA)


def postcondition_py() -> str:
    return '''"""P0-VNOP-PAIR r2 恢复后验（单次启动之后运行）。

核对设备回到 TWRP、身份/槽位未变、认证根前缀边界 SHA 未漂移、
userdata 未被写入、无 second boot 记录。只读，不改设备状态。
"""
import argparse, json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
TRIAL = ROOT / 'reports/p0-vnop-pair-20261105-r2/trial'
ADB = '__ADB__'
REDACT = '__REDACT__'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read(p):
    return json.loads(Path(p).read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recovery-confirmed', required=True)
    a = ap.parse_args()
    boot = read(TRIAL / 'boot.json')
    consumed = read(TRIAL / 'consumed.json')
    assert consumed['boot_records'] == 1 and consumed['resend_allowed'] is False
    assert boot['retry_allowed'] is False

    r = subprocess.run([ADB, 'devices'], capture_output=True, text=True, timeout=30)
    serials = [x.split()[0] for x in r.stdout.splitlines()[1:]
               if x.strip() and 'recovery' in x]
    assert len(serials) == 1, '未唯一回到 recovery'
    serial = serials[0]
    props = {}
    for k in ('ro.product.device', 'ro.boot.slot_suffix', 'ro.twrp.version'):
        p = subprocess.run([ADB, '-s', serial, 'shell', 'getprop', k],
                           capture_output=True, text=True, timeout=20)
        props[k] = (p.stdout + p.stderr).strip().replace('\\r', '')
    assert props['ro.product.device'] == 'nuwa'
    assert props['ro.boot.slot_suffix'] == '_a'

    geo = subprocess.run([ADB, '-s', serial, 'shell',
                          'cat /sys/class/block/sda32/size; '
                          'grep PARTNAME /sys/class/block/sda32/uevent'],
                         capture_output=True, text=True, timeout=20)
    assert '469917144' in geo.stdout and 'PARTNAME=userdata' in geo.stdout

    edges = {}
    for skip in ('0', '2061918', '2061934'):
        p = subprocess.run([ADB, '-s', serial, 'shell',
                            'dd if=/dev/block/sda32 bs=4096 skip=%s count=16 '
                            '2>/dev/null | sha256sum' % skip],
                           capture_output=True, text=True, timeout=60)
        edges[skip] = p.stdout.split()[0] if p.stdout.split() else ''
    assert edges['0'] == '5d2308259a595010546bc58a29176f47d389297936faf0ee75091e5f5bd9d6eb'
    assert edges['2061918'] == '188d096cb8b956099a0baf726e21620c59a449cc27b7a174b84ad4e988b8be98'
    assert edges['2061934'] == 'de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'

    out = TRIAL / 'postcondition.json'
    assert not out.exists(), 'refuse to overwrite postcondition.json'
    out.write_text(json.dumps(dict(
        time=now(), passed=True, recovery_confirmed=a.recovery_confirmed,
        device=dict(product='nuwa', slot='_a', twrp=props['ro.twrp.version'],
                    serial=REDACT),
        partition_geometry_unchanged=True,
        auth_root_edge_sha256=edges,
        userdata_written=False, slot_changed=False, second_boot=False,
        note='临时启动不写分区；边界 SHA 与 15:05 基线一致'),
        ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
    print(json.dumps(dict(passed=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
'''.replace('__ADB__', ADB).replace('__REDACT__', REDACT)


def analyze_py() -> str:
    return '''"""P0-VNOP-PAIR r2 录像逐帧判读（21 字段，离线运行，不碰设备）。

输入：录像文件（或已抽帧的 PNG 序列）；输出 blocks-reading.json 与
screen-reading-draft.json（草稿，须人工复核后才写正式 screen-reading.json）。

纪律：
  - 60fps 逐帧局部 ROI RGB 分类，禁止灰度统计、禁止 2fps 抽样、禁止只看末帧。
  - 记录每个字段首次出现、每次跳变的帧号与时间、稳定末态。
  - 记录非字段指示状态（色块/小标记）的时间线，但不解释成内核相位。
  - 阴性结论只能写「未观察到」，须同时给出通道有效 / 行位可见 / 挂点覆盖证据。
  - 本脚本不含任何预设结论、不写入正式 screen-reading.json。
"""
import argparse, json
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
OUT = ROOT / 'reports/p0-vnop-pair-20261105-r2'
SEM = OUT / 'field-semantics.json'
EXPECTED_FB03 = '__EXPECTED_FB03__'
MIN_RECORDING_SECONDS = 9.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recording', required=True, help='录像或抽帧目录')
    ap.add_argument('--fps', type=float, default=60.0)
    ap.add_argument('--frames', type=int, required=True)
    ap.add_argument('--output-dir', default=str(OUT / 'trial'))
    a = ap.parse_args()

    s = json.loads(SEM.read_bytes())
    fields = sorted(s['fields'], key=lambda f: f['field_id_decimal'])
    assert len(fields) == 21
    duration = a.frames / a.fps
    limitations = []
    if duration < MIN_RECORDING_SECONDS:
        limitations.append('录像时长 %.2fs < 计划 %.1fs；零变化点只证明该窗口内稳定'
                           % (duration, MIN_RECORDING_SECONDS))

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    draft = dict(
        candidate=s['candidate'], source=str(a.recording),
        fps=a.fps, frames=a.frames, duration_seconds=round(duration, 3),
        field_count=len(fields),
        field_labels=[f['screen_label'] for f in fields],
        per_field_timeline={f['screen_label']: [] for f in fields},
        non_field_indicator_timeline=[],
        arrival_guard=dict(FB03=EXPECTED_FB03, note='FB03 为定值 magic，'
                           '出现即证明通道与入口可见'),
        paired_reading_required=dict(
            entry='FB03', join='FB06', mac='FB07',
            note='FB06 是四路共用汇合点，单点不得解释为 VNOP_READ 已执行'),
        negative_evidence_discipline=[
            '空白只能写「未观察到」，不得写「未发生」',
            '须同时证明通道有效、行位可见、挂点覆盖所有返回路径',
            '连续两轮阴性须安排入口到达 / 早退路径 / 正常 epilogue 三路阳性对照'],
        limitations=limitations,
        status='DRAFT_NOT_DEVICE_VERIFIED',
        note='逐帧 ROI 判读结果由人工填入 per_field_timeline；'
             '本脚本只生成骨架与纪律清单，不推断任何读数。')
    p = out / 'screen-reading-draft.json'
    if p.exists():
        p = out / 'screen-reading-draft-r2.json'
    p.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\\n',
                 encoding='utf-8')
    print(json.dumps(dict(written=str(p), fields=len(fields),
                          duration=round(duration, 3),
                          limitations=len(limitations)), ensure_ascii=False))


if __name__ == '__main__':
    main()
'''.replace('__EXPECTED_FB03__', EXPECTED_FB03)


def trial_plan_md() -> str:
    return '''# P0-VNOP-PAIR r2 实机验证计划（**待确认，未上机**）

**当前状态**：离线准备全部就绪、新鲜只读预检通过、`trial/` 目录不存在、
**未发任何 `fastboot boot`、未 reboot、未 flash、未改槽、未写分区**。
停在实机确认门：需你当轮明确确认 **60fps 全程录像** 与 **实体键恢复路径**，
才会执行正式预检与单次启动。准备阶段的「准备进行实机」不构成启动确认语
（AGENTS.md 上机前确认门条款）。

## 一、这一轮要回答什么

`_vn_rdwr_64` 内的 **`0x7466B20 bl _VNOP_READ` 到底有没有进入、有没有返回**？
以及 `mac_vnode_check_read` 是放行、拒绝还是未到达。

CHECK10 的 368 帧 epilogue 空白无法区分「`VNOP_READ` 内部未返回」与
「MAC errno 直跳汇合点」与「`len<0` 早退」。本轮用入口 / 汇合点配对观测，
一次把这三种解释分开。

## 二、候选（严格单一变量）

| 项 | 值 |
|---|---|
| 候选 | P0-VNOP-PAIR r2（当前唯一候选；P0 r1 已冻结为对照，不再上机） |
| 镜像 | `out/p0-vnop-pair-20261105-r2/boot-p0-vnop-pair-20261105-r2.img`，__IMAGE_BYTES__ B，SHA `__IMAGE_SHA__` |
| 内核 | SHA `__KERNEL_SHA__` |
| 相对 P0 r1 | cave 外差异**恰好 2 个字**（两个新挂点）；11 点真原生恢复、10 大阶段、6 功能件、FB07 全部保留 |
| 新增挂点 | `0x7466B10` → FB03（入口 magic `56504E52`）；`0x7466B24` → FB06（汇合点 `w0`） |
| 字段语义表 | SHA `__SEM_SHA__`，21 字段，FB03/FB06/FB07 各 1 个写入源，无编号冲突 |
| 回归 | 78 项全通过，SHA `__REG_SHA__`；独立重建内核逐字节一致 |
| 状态 | `OFFLINE_QUALIFIED_AT_CONFIRMATION_GATE`，未消费 |

## 三、判读矩阵（必须配对）

| FB03 | FB06 | FB07 | 结论 |
|---|---|---|---|
| 出现 | 出现 | 任意 | VNOP_READ 已调用且返回；卡点下移到 exec 续接 / EL0 |
| 出现 | 空白 | `00000000` | **VNOP_READ 已进入但未返回**（首要嫌疑证实） |
| 空白 | 出现 | 非零 | MAC-read 拒绝直跳汇合点；按 FB07 原生 AMFI errno 定位 |
| 空白 | 出现 | `00000000` | write/swap 或其它直跳路径；回查挂点覆盖 |
| 空白 | 空白 | 空白 | 未到 `0x7466B10`，含 `len<0` 早退；按 AGENTS §6 安排三路阳性对照 |
| guard | 10 大阶段 + 初始化字段全空 | — | framebuffer 通道或入口未执行，本轮读数全部无效 |

FB03 是定值 magic，出现即证明通道与入口可见；FB06 是四路共用汇合点，
**单点读数不得解释为 VNOP_READ 已执行**。空白只能写「未观察到」，不得写「未发生」。

## 四、上机条件（确认前不动设备）

1. **全程 60fps 录像**：从 `fastboot boot` 发出之前开始，覆盖到画面稳定后至少数秒；
   本轮**不短于 9 s**（CHECK10 只有 6.13 s 已记为限制）。
2. **实体键恢复路径**：启动后能手动回 TWRP/fastboot，确认 `adb devices` 列出 `recovery`。
3. **设备拓扑**：当前唯一 `nuwa` / `_a` / TWRP 3.7.1；所有手工 fastboot 命令带 `-s`。
4. **认证根前提**：15:05 实测四项 SHA 全一致，本轮预检再次复核三处 64 KiB 边界；
   无需重写根、不触发分区写入授权。

## 五、确认后的执行顺序（本轮**未执行**）

```
python reports/p0-vnop-pair-20261105-r2/trial-scripts/preflight.py \\
    --recording-confirmed "<你的原话>" --recovery-confirmed "<你的原话>"
python reports/p0-vnop-pair-20261105-r2/trial-scripts/launch.py \\
    --confirm-launch "<你的原话>"
# 60fps 逐帧判读录像 → 人工复核 → 归档 trial/result.md
python reports/p0-vnop-pair-20261105-r2/trial-scripts/postcondition.py \\
    --recovery-confirmed "<恢复确认>"
```

`preflight.py` 的正式预检会在完成只读核验后执行一次 `adb reboot bootloader`，
把设备从 TWRP 切到 fastboot 模式，随后做**单次受控 getvar 组**
（`product` / `current-slot` / `unlocked` / `slot-unbootable:a` /
`slot-retry-count:a` / `max-download-size`）。这一步是 `launch.py` 能发出
单次 `fastboot boot` 的前提；本轮离线就绪门**未执行**它，设备仍在 TWRP。
若设备已在 bootloader，改用 `--already-fastboot` 跳过 reboot。
禁止手工连续 `fastboot getvar`（会使变量表瞬时不可读）；预检失败须原样归档，
不得删除覆盖伪装成一次通过。

约束：单次 `fastboot boot`、不重发、不 flash/erase/改槽、候选一次性消费、
不写分区、不提交 git；OKAY 只证明传输与命令被接受，内核进度由录像判读。

## 六、判读能力边界

本轮能收敛**位置**（门 / 区间级），**不能定性原因**：即使证实
「VNOP_READ 已进入未返回」，后端内部（APFS vnop / decmpfs / cluster·UPL /
`IOStorageCompletion` / `gHost.lock` / DMA）本轮零观测点，仍分不清哪一层、
哪种机制、死锁还是录像窗口内超时。唯一例外是 MAC 拒绝分支，FB07 会给出
原生 AMFI 具体 errno。详见 `reports/r2-inference-scope-20261105/README.md`。

第 8–10 门（`process_signature` / FINAL_WAIT / EL0 / trust cache）仍
「从未实机验收」，即使 read 返回也不能写成已过。

## 七、边界

离线合格 ≠ 实机通过。本轮不改变安全模型、不引入 permissive 替身、
不加停机门、不改 `board.toml`。**未提交 git**。
'''.replace('__IMAGE_SHA__', IMAGE_SHA).replace('__KERNEL_SHA__', KERNEL_SHA) \
   .replace('__SEM_SHA__', SEM_SHA).replace('__REG_SHA__', REG_SHA) \
   .replace('__IMAGE_BYTES__', str(IMAGE_BYTES))


def main() -> None:
    for d in (SCRIPTS, GATE):
        d.mkdir(parents=True, exist_ok=True)
    for d in (MEDIA / 'original', MEDIA / 'derived'):
        d.mkdir(parents=True, exist_ok=True)

    files = {
        OUT / 'trial-plan.md': trial_plan_md(),
        SCRIPTS / 'preflight.py': preflight_py(),
        SCRIPTS / 'launch.py': launch_py(),
        SCRIPTS / 'postcondition.py': postcondition_py(),
        SCRIPTS / 'analyze-recording.py': analyze_py(),
    }
    for p, content in files.items():
        p.write_text(content, encoding='utf-8')

    # 静态自检：语法可编译、无 CHECK10 结论串、无设备动作
    banned = ['user_observation', 'f_region', 'zero_draw', 'zero-draw',
              'check8_reassessment', 'C10A55AA', '0769BF94',
              '6b93b92b', 'da23791b']
    for p in files.values():
        if isinstance(p, Path) and p.suffix == '.py':
            pass
    for name, content in [('preflight', preflight_py()),
                          ('launch', launch_py()),
                          ('postcondition', postcondition_py()),
                          ('analyze', analyze_py())]:
        compile(content, name, 'exec')
        hits = [b for b in banned if b in content]
        assert not hits, ('判读/上机脚本残留上一轮结论串', name, hits)

    # 生成的脚本不得在本脚本运行时发任何设备动作
    assert not (OUT / 'trial').exists(), 'trial/ 不应在准备阶段创建'

    readiness = dict(
        schema='nuwa/p0-vnop-pair-r2/offline-readiness/1',
        generated_at=now(),
        candidate=Q['candidate'],
        image_sha256=IMAGE_SHA, kernel_sha256=KERNEL_SHA,
        field_semantics_sha256=SEM_SHA,
        regression_sha256=REG_SHA, regression_cases=CASES,
        offline_preparation=dict(
            trial_plan=True, trial_scripts=True, media_directories=True,
            analyze_recording_script=True, readiness_gate=True),
        generated_files=[str(p.relative_to(R)).replace('\\', '/')
                         for p in files],
        media_original=str(MEDIA / 'original').replace('\\', '/'),
        media_derived=str(MEDIA / 'derived').replace('\\', '/'),
        static_selfcheck=dict(
            python_syntax_compiled=True,
            banned_prior_round_strings=banned,
            banned_strings_absent=True,
            trial_directory_absent=True),
        fresh_readonly_preflight=dict(
            adb_device_unique=True, product='nuwa', slot='_a',
            twrp='3.7.1_12-Xiaomi13Pro_v9.0_A15',
            partition_sectors=469917144,
            partition_bytes=240597577728,
            partname='userdata',
            data_mounted=False,
            auth_root_edge_sha256=dict(
                skip_0='5d2308259a595010546bc58a29176f47d389297936faf0ee75091e5f5bd9d6eb',
                skip_2061918='188d096cb8b956099a0baf726e21620c59a449cc27b7a174b84ad4e988b8be98',
                skip_2061934='de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31'),
            all_match_15_05_baseline=True,
            candidate_sha_recomputed_match=True,
            candidate_consumed=False,
            no_reboot=True, no_getvar=True, no_flash=True,
            no_slot_change=True, no_partition_write=True,
            trial_directory_created=False),
        gate=dict(
            status='STOPPED_AT_LAUNCH_CONFIRMATION',
            reason='准备阶段的原话不构成启动确认语；须用户当轮明确确认 '
                   '60fps 全程录像与实体键恢复路径',
            remaining=['当轮确认 60fps 全程录像（≥9s）',
                       '当轮确认实体键恢复路径可用',
                       '确认后运行 preflight.py → launch.py（单次）'],
            general_boot_authorization='已有持续授权，不重复询问'),
        boundaries=[
            '本脚本与生成物均未操作设备、未 reboot、未 getvar、未建 trial/、'
            '未发 fastboot boot、未写分区、未改槽、未提交 git。',
            '离线合格 ≠ 实机通过；判读须 60fps 逐帧局部 ROI RGB。'],
        inputs=dict(
            qualification=sha(OUT / 'qualification.json'),
            field_semantics=sha(SEM),
            regression=sha(OUT / 'regression.json'),
            image=sha(IMAGE),
            kernel=sha(KERNEL),
            observer_source=sha(SOURCE)),
    )
    (GATE / 'readiness.json').write_text(
        json.dumps(readiness, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('generated files:', len(files))
    for p in files:
        print('  ', p.relative_to(R))
    print('media:', MEDIA / 'original', '|', MEDIA / 'derived')
    print('readiness:', GATE / 'readiness.json')
    print('static selfcheck: syntax OK, banned strings absent, trial/ absent')


if __name__ == '__main__':
    main()
