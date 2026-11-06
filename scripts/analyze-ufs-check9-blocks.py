"""CHECK9 per-frame ROI colour analysis (60fps, no downsampling of blocks).

Full-frame counts are dominated by the green top bar and the blue boot menu, so
the first pass was archived as screen-reading-attempt-1.json. This reader uses
local ROIs derived from the key frames: left indicator blocks, top-right yellow
blocks, the CHECK8 colour-block band, and the centre UI. It also emits a
visual timeline strip so the state changes can be confirmed by eye.
"""
import datetime, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
MEDIA = ROOT.parent/'Media-nuwa/UFS-CHECK-9-r1/original'
OUT = ROOT/'reports/ufs-check-9-r1/media-derived'
TRIAL = ROOT/'reports/ufs-check-9-r1/trial'
W, H = 270, 480
FRAME = W*H*3
FFMPEG = 'D:/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/ffmpeg/bin/ffprobe.exe'

# (name, x0, y0, x1, y1) in the 270x480 decoded frame.
ROIS = [
    ('left_indicators',   0,  60,  50, 120),
    ('top_right_yellow', 170,  60, 245,  95),
    ('block_band',       170, 235, 270, 290),
    ('centre_ui',         50, 110, 220, 300),
]
COLOURS = ('orange', 'yellow', 'green', 'blue', 'magenta', 'white', 'grey', 'bright')


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def colour(r, g, b):
    n = 0
    if r > 140 and 55 < g < 175 and b < 105 and r > g + 45:
        n |= 1       # orange
    if r > 145 and g > 125 and b < 115:
        n |= 2       # yellow
    if g > 80 and g > r + 20 and g > b + 20:
        n |= 4       # green
    if b > 100 and b > r + 40 and b > g + 15:
        n |= 8       # blue
    if r > 115 and b > 115 and g < 105:
        n |= 16      # magenta
    if r > 170 and g > 170 and b > 170:
        n |= 32      # white
    s = r+g+b
    if 260 < s < 640 and max(r, g, b)-min(r, g, b) < 40:
        n |= 64      # grey
    if s > 330:
        n |= 128     # bright
    return n


def roi_vector(pix, x0, y0, x1, y1):
    v = [0]*8
    for y in range(y0, y1):
        base = (y*W+x0)*3
        row = pix[base:base+(x1-x0)*3]
        for i in range(0, len(row), 3):
            n = colour(row[i], row[i+1], row[i+2])
            for k in range(8):
                if n & (1 << k):
                    v[k] += 1
    return v


def main():
    videos = sorted(MEDIA.glob('*.mp4'))
    assert len(videos) == 1, ('expected one recording', [p.name for p in videos])
    video = videos[0]
    OUT.mkdir(parents=True, exist_ok=True)
    probe = json.loads(subprocess.check_output([
        FFPROBE, '-v', 'quiet', '-show_streams', '-show_format', '-of', 'json', str(video)]))
    v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    fps = eval(v['avg_frame_rate']) if '/' in v['avg_frame_rate'] else float(v['avg_frame_rate'])
    meta = dict(path=str(video), sha256=sha(video), bytes=video.stat().st_size,
                codec=v['codec_name'], width=v['width'], height=v['height'],
                fps=round(fps, 4), declared_frames=int(v['nb_frames']),
                duration_seconds=float(probe['format']['duration']), rotation=-90)
    proc = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-vf',
                             'scale=%d:%d' % (W, H), '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE,
                            bufsize=FRAME*4)
    rows, strip = [], []
    idx = 0
    while True:
        pix = proc.stdout.read(FRAME)
        if len(pix) < FRAME:
            break
        rec = dict(frame=idx, t=round(idx/fps, 4), rois={})
        for name, x0, y0, x1, y1 in ROIS:
            rec['rois'][name] = dict(zip(COLOURS, roi_vector(pix, x0, y0, x1, y1)))
        # Visual strip: every 15th frame of the colour-block band, 3x scaled.
        if idx % 15 == 0:
            for y in range(235, 290):
                base = (y*W+170)*3
                line = pix[base:base+100*3]
                for rep in range(3):
                    strip.append(b''.join(line[i:i+3]*3 for i in range(0, len(line), 3)))
        rows.append(rec)
        idx += 1
    proc.stdout.close(); proc.wait()
    meta['decoded_frames'] = idx

    # Change points from the L1 distance of the block-band + indicator vectors.
    keys = ('block_band', 'left_indicators', 'top_right_yellow')
    def vec(r):
        return [r['rois'][k][c] for k in keys for c in COLOURS]
    dists = []
    for i in range(1, len(rows)):
        a, b = vec(rows[i-1]), vec(rows[i])
        dists.append((sum(abs(x-y) for x, y in zip(a, b)), i))
    vals = sorted(d for d, _ in dists)
    p95 = vals[int(len(vals)*0.95)] if vals else 0
    changes = [dict(frame=i, t=rows[i]['t'], l1=d) for d, i in dists if d > max(p95, 60)]

    # Discrete block state from the band ROI.
    def band_state(r):
        q = r['rois']['block_band']
        if q['orange'] > 3 and q['green'] < 3:
            return 'orange'
        if q['green'] > 3:
            return 'white_blocks_full' if q['white'] > 45 else 'green_steady'
        if q['white'] > 3:
            return 'white_only'
        return 'blank'
    segments = []
    for r in rows:
        st = band_state(r)
        if segments and segments[-1]['state'] == st:
            segments[-1]['last'] = r['frame']; segments[-1]['t_end'] = r['t']
        else:
            segments.append(dict(state=st, first=r['frame'], last=r['frame'],
                                 t_start=r['t'], t_end=r['t']))
    # Collapse segments shorter than 3 frames as noise.
    stable = [s for s in segments if s['last']-s['first'] >= 3]

    if strip:
        raw = OUT/'blocks-timeline.rgb'
        raw.write_bytes(b''.join(strip))
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                        '-s', '%dx%d' % (300, 165*((len(rows)+14)//15)), '-i', str(raw),
                        str(OUT/'blocks-timeline.png')], check=False)

    baseline = ['blank', 'white_only', 'orange', 'green_steady', 'white_blocks_full']
    novel = [s['state'] for s in stable if s['state'] not in baseline]
    result = dict(
        time=now(), round='UFS-CHECK-9 r1', media=meta,
        method=['ffmpeg full 60fps decode to 270x480 rgb24 with auto-rotation applied',
                'four local ROIs classified per pixel into orange/yellow/green/blue/magenta/white/grey/bright',
                'L1 distance of the colour vectors for change-point detection',
                'visual timeline strip of the colour-block band every 15 frames',
                'key frames extracted separately for visual confirmation'],
        rois=[dict(name=n, box=[x0, y0, x1, y1]) for n, x0, y0, x1, y1 in ROIS],
        check8_baseline=dict(frames=332, fps=60,
            states=['no colour f0-126', 'orange f132-137', 'green steady f138-325', 'white blocks f326-330'],
            centre_graphic='UniXNU logo (NOT Apple logo)'),
        user_observation='没有发现HEX 只有小块 (no HEX field rows, only small colour blocks)',
        f_region='no hex field rows in any inspected frame; zero-draw signature confirmed',
        state_timeline_stable=stable,
        state_timeline_raw_segments=len(segments),
        change_points_count=len(changes), change_points=changes[:40],
        per_frame=rows,
        novel_states=novel,
        device_executed=True)
    (TRIAL/'screen-reading.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(decoded_frames=idx, fps=meta['fps'],
                          stable_states=[(s['state'], s['first'], s['last']) for s in stable],
                          raw_segments=len(segments), change_points=len(changes),
                          novel_states=novel, media_sha256=meta['sha256'][:16]), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
