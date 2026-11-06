"""CHECK9 60fps recording reader. Run AFTER the original mp4 lands.

Produces per-frame RGB classification, frame-difference change points and key
frames. CHECK9 has NO field values: a blank F region is expected. The verdict
is whether the non-field colour-block timeline advances to a fifth state or a
post-logo UI appears, compared with the CHECK8 four-state baseline.
"""
import datetime, hashlib, json, subprocess, sys
from pathlib import Path
import struct

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
MEDIA = ROOT.parent/'Media-nuwa/UFS-CHECK-9-r1/original'
OUT = ROOT/'reports/ufs-check-9-r1/media-derived'
TRIAL = ROOT/'reports/ufs-check-9-r1/trial'
W, H = 270, 480
FRAME = W*H*3
FFMPEG = 'D:/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/ffmpeg/bin/ffprobe.exe'
SAMPLE = 2  # classify every 2nd pixel; small colour blocks remain detectable


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def classify(pix):
    """Count orange/green/white/grey/bright pixels in one rgb24 frame."""
    orange = green = white = grey = bright = 0
    rs, gs, bs = pix[0::3][::SAMPLE], pix[1::3][::SAMPLE], pix[2::3][::SAMPLE]
    for r, g, b in zip(rs, gs, bs):
        mx = r if r > g and r > b else (g if g > b else b)
        mn = b if b < g and b < r else (g if g < r else r)
        if r > 120 and r > g + 35 and g > b and b < 110:
            orange += 1
        if g > 85 and g > r + 20 and g > b + 20:
            green += 1
        if r > 185 and g > 185 and b > 185:
            white += 1
        s = r+g+b
        if 300 < s < 630 and mx-mn < 38:
            grey += 1
        if s > 330:
            bright += 1
    return orange, green, white, grey, bright


def state(o, g, w):
    """Coarse 4-state classifier matching the CHECK8 timeline."""
    if o > 8 and g < 8:
        return 'orange'
    if g > 8:
        return 'green_steady' if w < 300 else 'white_blocks_full'
    if w > 40:
        return 'no_colour_white_ui'
    return 'boot_selector'


def main():
    videos = sorted(MEDIA.glob('*.mp4'))
    if len(videos) != 1:
        print(json.dumps(dict(waiting=True, reason='expected exactly one mp4 in',
                              media=str(MEDIA), found=[p.name for p in videos])))
        return 2
    video = videos[0]
    OUT.mkdir(parents=True, exist_ok=True)
    probe = json.loads(subprocess.check_output([
        FFPROBE, '-v', 'quiet', '-show_streams', '-show_format', '-of', 'json', str(video)]))
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    fps = eval(v['avg_frame_rate']) if '/' in v['avg_frame_rate'] else float(v['avg_frame_rate'])
    meta = dict(path=str(video), sha256=sha(video), bytes=video.stat().st_size,
                codec=v['codec_name'], width=v['width'], height=v['height'],
                fps=fps, frames=int(v.get('nb_frames', 0)),
                duration_seconds=float(probe['format']['duration']),
                rotation=str(v.get('side_data_list', '')))
    cmd = [FFMPEG, '-v', 'error', '-i', str(video), '-vf',
           'scale=%d:%d' % (W, H), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=FRAME*4)
    rows = []
    prev = None
    idx = 0
    while True:
        buf = proc.stdout.read(FRAME)
        if len(buf) < FRAME:
            break
        o, g, w, grey, bright = classify(buf)
        delta = 0
        if prev is not None:
            # sparse absolute difference over the frame
            for i in range(0, FRAME, 33):
                delta += abs(buf[i] - prev[i])
        rows.append(dict(frame=idx, t=round(idx/fps, 4), orange=o, green=g, white=w,
                         grey=grey, bright=bright, diff=delta,
                         state=state(o, g, w)))
        if idx in (0, 99, 126, 137, 150, 250, 325, 330) or idx % 60 == 0:
            Path(OUT/('frame-%04d.rgb' % idx)).write_bytes(buf)
        prev = buf
        idx += 1
    proc.stdout.close(); proc.wait()
    meta['decoded_frames'] = idx
    meta['decoded_duration_seconds'] = round(idx/fps, 3)

    # State timeline: collapse consecutive equal states.
    segments = []
    for r in rows:
        if segments and segments[-1]['state'] == r['state']:
            segments[-1]['last'] = r['frame']; segments[-1]['t_end'] = r['t']
        else:
            segments.append(dict(state=r['state'], first=r['frame'], last=r['frame'],
                                 t_start=r['t'], t_end=r['t']))
    # Significant frame-difference change points.
    diffs = [r['diff'] for r in rows[1:]]
    mean = sum(diffs)/len(diffs) if diffs else 0
    changes = [dict(frame=r['frame'], t=r['t'], diff=r['diff'])
               for r in rows[1:] if r['diff'] > max(mean*3, 200000)][:40]

    baseline = ['boot_selector', 'no_colour_white_ui', 'orange', 'green_steady', 'white_blocks_full']
    seen = [s['state'] for s in segments]
    novel = [s for s in seen if s not in baseline]
    result = dict(
        time=now(), round='UFS-CHECK-9 r1', media=meta,
        method=['ffmpeg full 60fps decode to 270x480 rgb24',
                'per-frame RGB classification (orange/green/white/grey/bright)',
                'sparse absolute frame difference for change-point detection',
                'collapsed state timeline compared with CHECK8 four-state baseline'],
        check8_baseline=dict(
            frames=332, fps=60, states=['no colour f0-126', 'orange f132-137',
                                         'green steady f138-325', 'white blocks f326-330'],
            centre_graphic='UniXNU logo (NOT Apple logo)'),
        state_timeline=segments,
        per_frame=rows,
        change_points=changes,
        f_region_expectation='entirely blank (zero-draw); verify visually in the key frames',
        novel_states=novel,
        verdict_hint=('ADVANCED: a state outside the CHECK8 baseline appeared; inspect key frames before concluding'
                      if novel else 'No state outside the CHECK8 baseline was detected by coarse classification; inspect key frames and change points'),
        device_executed=True)
    (TRIAL/'screen-reading.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # Also emit key frames as PNG for visual confirmation.
    for f in sorted(OUT.glob('frame-*.rgb')):
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                        '-s', '%dx%d' % (W, H), '-i', str(f), str(f.with_suffix('.png'))], check=True)
    print(json.dumps(dict(decoded_frames=idx, fps=fps, states=seen,
                          novel_states=novel, change_points=len(changes),
                          media_sha256=meta['sha256'][:16]), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
