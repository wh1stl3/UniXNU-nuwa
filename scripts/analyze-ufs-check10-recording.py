"""UFS-CHECK-10 r1 recording reader (60fps, per-frame field rows + local ROIs).

Reads the single recording in Media-nuwa/UFS-CHECK-10-r1/original, decodes every
frame, then:

* calibrates the FB field row grid from the FINAL frame (FB00..FB14 visible,
  FB07/FB0F blank), and extrapolates N=21..23 -> FB15/FB16/FB17;
* counts bright pixels in every field row band in EVERY frame, so a value that
  only appears for a few frames cannot be missed;
* classifies four local ROIs (indicators / top-right / block band / centre) to
  reproduce the small-colour-block timeline the user reported;
* writes a visual strip of the field column every 15 frames.

Full-frame statistics are NOT used: the green top bar and the blue boot menu
dominate them (lesson from CHECK9).
"""
import datetime, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path('D:/Code/PortingiOS/nuwa/UniXNU-nuwa')
MEDIA = ROOT.parent / 'Media-nuwa/UFS-CHECK-10-r1/original'
OUT = ROOT / 'reports/ufs-check-10-r1/media-derived'
TRIAL = ROOT / 'reports/ufs-check-10-r1/trial'
W, H = 540, 960
FRAME = W * H * 3
FFMPEG = 'D:/ffmpeg/bin/ffmpeg.exe'
FFPROBE = 'D:/ffmpeg/bin/ffprobe.exe'

# Field column in the 540x960 decoded frame (calibrated on the final frame).
FIELD_X0, FIELD_X1 = 395, 510
FIELD_Y_LO, FIELD_Y_HI = 260, 560
ROW_HALF = 4

# Local ROIs (x0, y0, x1, y1) - CHECK9 coordinates doubled to 540x960.
ROIS = [
    ('left_indicators',   0, 120, 100, 240),
    ('top_right_yellow', 340, 120, 490, 190),
    ('block_band',       340, 470, 540, 580),
    ('centre_ui',        100, 220, 440, 600),
]
COLOURS = ('orange', 'yellow', 'green', 'blue', 'magenta', 'white', 'grey', 'bright')


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bright(r, g, b):
    return r > 150 and g > 150 and b > 150


def colour(r, g, b):
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


def row_counts(pix, centres):
    """Bright-pixel count for each field row band, in one pass per row."""
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


def roi_vector(pix, x0, y0, x1, y1):
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


def calibrate(pix):
    """Find text row bands in the field column of the final frame."""
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
    # Assign every visible band a field index N by its distance from FB00.
    assigned = {round((c - c0) / step): c for c in centres}
    assert 0 in assigned and 20 in assigned, ('grid calibration failed', assigned)
    grid = [c0 + step * n for n in range(24)]
    return dict(bands=bands, centres=centres, step=step, c0=c0,
                assigned=assigned, grid=grid)


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
                duration_seconds=float(probe['format']['duration']), rotation=-90,
                decoded_size=[W, H])

    proc = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-vf',
                             'scale=%d:%d' % (W, H), '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE,
                            bufsize=FRAME * 4)
    frames, strip = [], []
    idx = 0
    while True:
        pix = proc.stdout.read(FRAME)
        if len(pix) < FRAME:
            break
        frames.append(pix)
        if idx % 15 == 0:
            for y in range(260, 560):
                base = (y * W + 380) * 3
                strip.append(pix[base:base + 140 * 3])
        idx += 1
    proc.stdout.close()
    proc.wait()
    meta['decoded_frames'] = idx
    assert idx > 0

    cal = calibrate(frames[-1])
    grid = cal['grid']
    series = []
    for i, pix in enumerate(frames):
        rec = dict(frame=i, t=round(i / fps, 4),
                   rows=row_counts(pix, grid),
                   rois={name: dict(zip(COLOURS, roi_vector(pix, *box)))
                         for name, *box in ROIS})
        series.append(rec)

    # N is DECIMAL in the source; the printed suffix is HEX: FB%02X of N.
    names = {n: 'FB%02X' % n for n in range(24)}
    fields = {}
    for n in range(24):
        vals = [r['rows'][n] for r in series]
        nz = [i for i, c in enumerate(vals) if c > 8]
        fields[names[n]] = dict(
            n=n, centre_y=grid[n], max_bright=max(vals), final_bright=vals[-1],
            first_nonzero_frame=nz[0] if nz else None,
            frames_nonzero=len(nz), nonzero_range=[nz[0], nz[-1]] if nz else None)

    def vec(r):
        return [r['rois'][k][c] for k in ('block_band', 'left_indicators', 'top_right_yellow')
                for c in COLOURS]
    dists = [(sum(abs(x - y) for x, y in zip(vec(series[i - 1]), vec(series[i]))), i)
             for i in range(1, len(series))]
    vals = sorted(d for d, _ in dists)
    p95 = vals[int(len(vals) * 0.95)] if vals else 0
    changes = [dict(frame=i, t=series[i]['t'], l1=d) for d, i in dists
               if d > max(p95, 60)]

    def band_state(r):
        # ROI areas are 4x the CHECK9 270x480 ROIs, so thresholds scale 4x too.
        q = r['rois']['block_band']
        if q['orange'] > 12 and q['green'] < 12:
            return 'orange'
        if q['green'] > 12:
            return 'white_blocks_full' if q['white'] > 180 else 'green_steady'
        if q['white'] > 12:
            return 'white_only'
        return 'blank'
    segments = []
    for r in series:
        st = band_state(r)
        if segments and segments[-1]['state'] == st:
            segments[-1]['last'] = r['frame']
            segments[-1]['t_end'] = r['t']
        else:
            segments.append(dict(state=st, first=r['frame'], last=r['frame'],
                                 t_start=r['t'], t_end=r['t']))
    stable = [s for s in segments if s['last'] - s['first'] >= 3]

    # Visual strip: field column every 15 frames laid out left-to-right.
    if strip:
        ntiles = len(strip) // 300
        flat = bytearray()
        for y in range(300):
            for f in range(ntiles):
                flat += strip[f * 300 + y]
        raw = OUT / 'fields-timeline.rgb'
        raw.write_bytes(bytes(flat))
        strip_w = 140 * ntiles
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                        '-s', '%dx300' % strip_w, '-i', str(raw),
                        '-vf', 'scale=%d:600:flags=neighbor' % strip_w,
                        str(OUT / 'fields-timeline.png')], check=False)

    result = dict(
        time=now(), round='UFS-CHECK-10 r1', media=meta,
        method=[
            'ffmpeg full-rate decode of every frame to 540x960 rgb24 (auto-rotation applied)',
            'final-frame bright-pixel row projection in the field column to calibrate the FB row grid',
            'bright-pixel count of all 24 field row bands (N=0..23) in EVERY frame, not only key frames',
            'four local ROIs colour-classified; full-frame statistics deliberately excluded',
            'visual strip of the field column every 15 frames'],
        field_grid=dict(c0=cal['c0'], step=cal['step'],
                        visible_bands=cal['bands'], assigned=cal['assigned'],
                        extrapolated_new_rows={names[n]: grid[n] for n in (21, 22, 23)},
                        x_band=[FIELD_X0, FIELD_X1]),
        fields=fields,
        guard_fields={k: dict(max_bright=fields[k]['max_bright'],
                              final_bright=fields[k]['final_bright'],
                              first_nonzero_frame=fields[k]['first_nonzero_frame'])
                      for k in ('FB03', 'FB06')},
        new_field_rows={k: dict(centre_y=fields[k]['centre_y'],
                                max_bright=fields[k]['max_bright'],
                                frames_nonzero=fields[k]['frames_nonzero'],
                                first_nonzero_frame=fields[k]['first_nonzero_frame'])
                        for k in ('FB15', 'FB16', 'FB17')},
        rois=[dict(name=n, box=list(box)) for n, *box in ROIS],
        state_timeline_stable=stable,
        state_timeline_classifier_caveat=(
            'The inherited CHECK9 colour thresholds were area-scaled to 540x960 but the '
            'recording framing differs; this classifier mislabels the selector frame as '
            '"orange" and is NOT used as a state conclusion. Only the 18 L1 change points '
            'and the six visually inspected key frames are used.'),
        state_timeline_raw_segments=len(segments),
        change_points_count=len(changes), change_points=changes[:40],
        per_frame=[dict(frame=r['frame'], t=r['t'], rows=r['rows'], rois=r['rois'])
                   for r in series],
        device_executed=True)
    (TRIAL / 'screen-reading.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(dict(decoded_frames=idx, fps=meta['fps'],
                          duration=meta['duration_seconds'],
                          grid=dict(c0=cal['c0'], step=cal['step'],
                                    visible_rows=len(cal['bands'])),
                          guards={k: result['guard_fields'][k] for k in ('FB03', 'FB06')},
                          new_rows=result['new_field_rows'],
                          fb14=dict(max=fields['FB14']['max_bright'],
                                    final=fields['FB14']['final_bright']),
                          stable_states=[(s['state'], s['first'], s['last']) for s in stable],
                          change_points=len(changes),
                          media_sha256=meta['sha256'][:16]), ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
