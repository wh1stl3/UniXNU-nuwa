"""P0-VNOP-DISPATCH r3 红色横条 / A 区 HEX 逐帧时间线（只读已落盘录像）。

目的：回答「本轮实机红色色带与 A 开头 HEX 是什么时候出现的、是否与四个新
FB 行位同时出现」。方法沿用 r3 判读脚本的全帧 60fps rgb24 解码，只统计两个
局部 ROI 的颜色/亮像素数量，不做全帧统计、不预设语义、不改已有判读结论。

不操作设备、不重发 boot、不写分区、不提交 git。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent.parent
MEDIA = R.parent / 'Media-nuwa/P0-VNOP-DISPATCH-r3/original'
OUT = R / 'reports/p0-vnop-dispatch-20261105-r3/media-derived'
OUT.mkdir(parents=True, exist_ok=True)

W, H = 540, 960
FRAME = W * H * 3
FFMPEG = 'D:/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/ffmpeg/bin/ffprobe.exe'

# 画面坐标来自 frame694-full.png（540x960 解码尺寸）。
RED_ROI = (0, 90, 420, 150)       # 顶部绿条区域内的红横幅
ATEXT_ROI = (80, 160, 340, 235)   # 左上方 A022/A027/A028/A029 白字区
ATEXT2_ROI = (90, 280, 330, 340)  # A031/A034 白字区


def now() -> str:
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def is_red(r: int, g: int, b: int) -> bool:
    return r > 150 and r > g + 80 and r > b + 60 and g < 130


def is_bright(r: int, g: int, b: int) -> bool:
    return r > 150 and g > 150 and b > 150


def region(pix, box, pred) -> int:
    x0, y0, x1, y1 = box
    n = 0
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        row = pix[base:base + (x1 - x0) * 3]
        for k in range(0, len(row), 3):
            if pred(row[k], row[k + 1], row[k + 2]):
                n += 1
    return n


def first_over(series, threshold):
    hits = [i for i, v in enumerate(series) if v > threshold]
    return dict(first_frame=hits[0] if hits else None,
                last_frame=hits[-1] if hits else None,
                frames_over=len(hits),
                max_value=max(series) if series else None,
                contiguous_from_start=bool(hits) and
                len(hits) == hits[-1] - hits[0] + 1)


def main() -> None:
    videos = sorted(MEDIA.glob('*.mp4'))
    assert len(videos) == 1, ('expected one recording', [p.name for p in videos])
    video = videos[0]
    probe = json.loads(subprocess.check_output([
        FFPROBE, '-v', 'quiet', '-show_streams', '-show_format',
        '-of', 'json', str(video)]))
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    fps = eval(v['avg_frame_rate']) if '/' in v['avg_frame_rate'] else float(v['avg_frame_rate'])

    proc = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-vf',
                             'scale=%d:%d' % (W, H), '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE,
                            bufsize=FRAME * 4)
    red, atext, atext2 = [], [], []
    while True:
        pix = proc.stdout.read(FRAME)
        if len(pix) < FRAME:
            break
        red.append(region(pix, RED_ROI, is_red))
        atext.append(region(pix, ATEXT_ROI, is_bright))
        atext2.append(region(pix, ATEXT2_ROI, is_bright))
    proc.stdout.close()
    proc.wait()
    assert red, 'no frames decoded'

    out = dict(
        schema='nuwa/p0-vnop-dispatch-r3/redband-timeline/1',
        generated_at=now(),
        candidate='P0-VNOP-DISPATCH r3',
        recording=dict(path=str(video),
                       sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                       fps=round(fps, 4), decoded_frames=len(red),
                       decoded_size=[W, H]),
        method='ffmpeg full-rate 60fps rgb24 decode; two local ROIs only; '
               'red = dominant R channel; A-text = bright pixels. '
               'No full-frame statistics, no semantic interpretation.',
        rois=dict(red=list(RED_ROI), a_text=list(ATEXT_ROI),
                  a_text_lower=list(ATEXT2_ROI)),
        thresholds=dict(red=1000, a_text=100, a_text_lower=100),
        red_band=first_over(red, 1000),
        a_text=first_over(atext, 100),
        a_text_lower=first_over(atext2, 100),
        per_frame=[dict(frame=i, t=round(i / fps, 4),
                        red=red[i], a_text=atext[i], a_text_lower=atext2[i])
                   for i in range(len(red))],
        limitations=[
            'ROI 只覆盖画面左上部分；不证明其它位置没有红色像素',
            '红色像素数量受相机曝光、OLED 拍摄伪影与视频压缩影响，'
            '首现帧按单调跳变判读，不给毫秒级精度',
            '本脚本不解释红条来源，也不修改 trial/result.md 已有结论'],
        status='MACHINE_READING_ONLY_NOT_VERDICT',
    )
    p = OUT / 'redband-timeline.json'
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(dict(red_band=out['red_band'], a_text=out['a_text'],
                          a_text_lower=out['a_text_lower'],
                          frames=len(red), output=str(p)), indent=2,
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
