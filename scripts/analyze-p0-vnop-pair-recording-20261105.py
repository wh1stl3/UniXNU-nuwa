"""P0-VNOP-PAIR r2 录像逐帧判读（2026-11-05，离线，只读取已落盘录像）。

方法沿用 CHECK10 的 60fps 全帧解码 + 字段列亮像素行带 + 4 个局部 ROI
颜色分类；不使用全帧统计、不按 2fps 抽样、不只看末帧。

本脚本只产出机器读数（每帧各行带亮像素数 + ROI 颜色向量），
**不预设任何结论**、不写正式 screen-reading.json；结论须由人工按
trial-plan.md 六态矩阵复核后落 trial/result.md。

不操作设备、不重发 boot、不写分区、不提交 git。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent.parent
MEDIA = R.parent / 'Media-nuwa/P0-VNOP-PAIR-r2/original'
OUT = R / 'reports/p0-vnop-pair-20261105-r2/media-derived'
OUT.mkdir(parents=True, exist_ok=True)

W, H = 540, 960
FRAME = W * H * 3
FFMPEG = 'D:/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/ffmpeg/bin/ffprobe.exe'

FIELD_X0, FIELD_X1 = 395, 510
FIELD_Y_LO, FIELD_Y_HI = 260, 560
ROW_HALF = 4

ROIS = [
    ('left_indicators', 0, 120, 100, 240),
    ('top_right_yellow', 340, 120, 490, 190),
    ('block_band', 340, 470, 540, 580),
    ('centre_ui', 100, 220, 440, 600),
]
COLOURS = ('orange', 'yellow', 'green', 'blue', 'magenta', 'white', 'grey', 'bright')


def now() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bright(r, g, b) -> bool:
    return r > 150 and g > 150 and b > 150


def colour(r, g, b) -> int:
    n = 0
    if r > 140 and 55 < g < 175 and b < 105 and r > g + 45:
        n |= 1
    if r > 145 and g > 125 and b < 115:
        n |= 2
    if g > 80 and g > r + 20 and g > b + 20:
        n |= 4
    if b > 100 and b > r + 40 and b > g + 15:
        n |= 8
    if r > 115 and b > 115 and g < 105:
        n |= 16
    if r > 170 and g > 170 and b > 170:
        n |= 32
    s = r + g + b
    if 260 < s < 640 and max(r, g, b) - min(r, g, b) < 40:
        n |= 64
    if s > 330:
        n |= 128
    return n


def row_counts(pix, centres) -> list[int]:
    out = [0] * len(centres)
    for i, cy in enumerate(centres):
        c = 0
        for y in range(max(0, cy - ROW_HALF), min(H, cy + ROW_HALF + 1)):
            base = (y * W + FIELD_X0) * 3
            row = pix[base:base + (FIELD_X1 - FIELD_X0) * 3]
            for k in range(0, len(row), 3):
                if bright(row[k], row[k + 1], row[k + 2]):
                    c += 1
        out[i] = c
    return out


def roi_vector(pix, x0, y0, x1, y1) -> list[int]:
    v = [0] * 8
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        row = pix[base:base + (x1 - x0) * 3]
        for i in range(0, len(row), 3):
            n = colour(row[i], row[i + 1], row[i + 2])
            for k in range(8):
                if n & (1 << k):
                    v[k] += 1
    return v


def calibrate(pix) -> dict:
    proj = []
    for y in range(FIELD_Y_LO, FIELD_Y_HI):
        base = (y * W + FIELD_X0) * 3
        row = pix[base:base + (FIELD_X1 - FIELD_X0) * 3]
        proj.append((y, sum(1 for k in range(0, len(row), 3)
                            if bright(row[k], row[k + 1], row[k + 2]))))
    bands, cur = [], None
    for y, c in proj:
        if c >= 8:
            if cur is None:
                cur = [y, y, c]
            else:
                cur[1] = y
                cur[2] = max(cur[2], c)
        elif cur is not None:
            bands.append(cur)
            cur = None
    if cur is not None:
        bands.append(cur)
    centres = [(b[0] + b[1]) // 2 for b in bands]
    gaps = [b - a for a, b in zip(centres, centres[1:])]
    small = [g for g in gaps if 5 < g < 20]
    assert small, ('no row pitch found', gaps)
    step = round(sum(small) / len(small))
    c0 = centres[0]
    assigned = {round((c - c0) / step): c for c in centres}
    assert 0 in assigned, ('grid calibration failed', assigned)
    grid = [c0 + step * n for n in range(24)]
    return dict(bands=bands, centres=centres, step=step, c0=c0,
                assigned=assigned, grid=grid)


def main() -> None:
    videos = sorted(MEDIA.glob('*.mp4'))
    assert len(videos) == 1, ('expected one recording', [p.name for p in videos])
    video = videos[0]

    probe = json.loads(subprocess.check_output([
        FFPROBE, '-v', 'quiet', '-show_streams', '-show_format',
        '-of', 'json', str(video)]))
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    fps = eval(v['avg_frame_rate']) if '/' in v['avg_frame_rate'] else float(v['avg_frame_rate'])
    meta = dict(path=str(video), sha256=sha(video), bytes=video.stat().st_size,
                codec=v['codec_name'], width=v['width'], height=v['height'],
                fps=round(fps, 4), declared_frames=int(v['nb_frames']),
                duration_seconds=float(probe['format']['duration']),
                decoded_size=[W, H], rotation=-90)

    proc = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-vf',
                             'scale=%d:%d' % (W, H), '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE,
                            bufsize=FRAME * 4)
    frames = []
    while True:
        pix = proc.stdout.read(FRAME)
        if len(pix) < FRAME:
            break
        frames.append(pix)
    proc.stdout.close()
    proc.wait()
    meta['decoded_frames'] = len(frames)
    assert frames, 'no frames decoded'

    cal = calibrate(frames[-1])
    grid = cal['grid']

    per_frame = []
    for i, pix in enumerate(frames):
        counts = row_counts(pix, grid)
        per_frame.append(dict(
            frame=i, t=round(i / fps, 4),
            rows=counts,
            rois={name: dict(zip(COLOURS, roi_vector(pix, *box)))
                  for name, *box in ROIS}))

    # 每行带的出现时间线：首次超过阈值、最大值、超过阈值的帧数
    threshold = 8
    timeline = []
    for n, cy in enumerate(grid):
        hits = [r['rows'][n] for r in per_frame]
        over = [j for j, c in enumerate(hits) if c > threshold]
        timeline.append(dict(
            field='FB%02X' % n, row_y=cy,
            max_bright=max(hits),
            frames_over_threshold=len(over),
            first_frame_over=over[0] if over else None,
            first_t_over=round(over[0] / fps, 4) if over else None,
            final_bright=hits[-1]))

    # 关注行：N=3 FB03, N=6 FB06, N=7 FB07（21 字段语义表）
    focus = {}
    for n in (3, 6, 7):
        focus['FB%02X' % n] = timeline[n] if n < len(timeline) else None

    # 通道有效性：初始化行 N=0 与任意已定义行的出现情况
    channel = dict(
        initialised_row_n0=timeline[0],
        any_row_ever_over_threshold=any(t['frames_over_threshold'] > 0
                                        for t in timeline),
        note='通道有效性还须结合非字段指示状态与 10 个大阶段行位可见性，'
             '本脚本只给机器读数')

    out = dict(
        schema='nuwa/p0-vnop-pair-r2/recording-reading/1',
        generated_at=now(),
        candidate='P0-VNOP-PAIR r2',
        recording=meta,
        calibration=dict(row_pitch=cal['step'], c0=cal['c0'],
                         assigned=cal['assigned'], bands=cal['bands']),
        rois=[dict(name=n, box=list(b)) for n, *b in ROIS],
        colours=list(COLOURS),
        method='ffmpeg full-rate decode of every frame to 540x960 rgb24 '
               '(auto-rotation applied); per-frame bright-pixel rows on field '
               'column x=395..510; four local ROIs colour-classified; '
               'full-frame statistics deliberately excluded',
        threshold=threshold,
        focus_fields=focus,
        timeline=timeline,
        channel=channel,
        limitations=[
            '录像时长 %.3fs < 计划 ≥9s；零变化点只证明该窗口内稳定' % meta['duration_seconds'],
            '空白只能写「未观察到」，不得写「未发生」',
            'FB03/FB06 必须配对；单点不得解释为 VNOP_READ 已执行',
            '行位可见性须由非字段指示状态与历史实机佐证，本脚本不独立证明'],
        status='MACHINE_READING_ONLY_NOT_VERDICT',
        note='本文件只含逐帧机器读数，不含任何阶段结论或根因判断；'
             '结论须人工按 trial-plan.md 六态矩阵复核后写 trial/result.md')

    p = OUT / 'recording-reading.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n',
                 encoding='utf-8')

    # 字段列每 15 帧一条可视条带（与 CHECK10 同法，供人工复核）
    strip_path = OUT / 'field-strip.ppm'
    with strip_path.open('wb') as f:
        strip_w, strip_h = 140, 300 * ((len(frames) + 14) // 15)
        f.write(('P6\n%d %d\n255\n' % (strip_w, strip_h)).encode())
        for i in range(0, len(frames), 15):
            pix = frames[i]
            for y in range(260, 560):
                base = (y * W + 380) * 3
                f.write(pix[base:base + 140 * 3])

    print(json.dumps(dict(
        decoded_frames=len(frames), fps=round(fps, 4),
        duration_seconds=meta['duration_seconds'],
        row_pitch=cal['step'],
        focus={k: dict(max=v['max_bright'], over=v['frames_over_threshold'],
                       first=v['first_frame_over'])
               for k, v in focus.items() if v},
        written=str(p)), ensure_ascii=False))


if __name__ == '__main__':
    main()
