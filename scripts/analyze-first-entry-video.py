"""Analyse the recorded first-entry video and emit a machine-readable timeline.

The video is the only artefact that covers the whole boot: from the DarwinBoot
menu, through the prelink kext load, into the XNU entry, and finally to the
black screen that precedes the automatic reboot.

The analysis is deliberately image based. No OCR engine is used, because the
console text is rendered in a proportional boot font at very low resolution and
a wrong character is worse than no character. Everything the script claims is
derived from measurable pixel statistics; the textual readings are kept in the
companion markdown report and are cross-checked by hand against the exported
frames.

Metrics per sampled frame:
  green_ratio  share of pixels that match a saturated green bar
  white_ratio  share of near-white pixels, i.e. rendered console text
  mean_luma    overall brightness of the sampled screen area

Screen area is expressed in normalised coordinates of the phone display so the
numbers do not depend on the crop window being recomputed for every clip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

# The phone display occupies roughly the middle of the frame. Coordinates are
# given for a 1080x1920 portrait recording and are rescaled if the clip has a
# different size.
DEFAULT_DISPLAY_BOX = (255, 380, 900, 1290)


def load_display(path: Path, box: tuple[int, int, int, int]) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if image.size != (1080, 1920):
            scale_x = image.size[0] / 1080
            scale_y = image.size[1] / 1920
            box = (
                int(box[0] * scale_x),
                int(box[1] * scale_y),
                int(box[2] * scale_x),
                int(box[3] * scale_y),
            )
        crop = image.crop(box)
    return np.asarray(crop, dtype=np.int16)


def metrics(frame: np.ndarray) -> dict[str, float]:
    red = frame[:, :, 0]
    green = frame[:, :, 1]
    blue = frame[:, :, 2]
    green_mask = (green > 90) & (green > red + 40) & (green > blue + 40)
    white_mask = (red > 170) & (green > 170) & (blue > 170)
    return {
        "green_ratio": round(float(green_mask.mean()) * 100, 3),
        "white_ratio": round(float(white_mask.mean()) * 100, 3),
        "mean_luma": round(float(frame.mean()), 2),
    }


def segment(timeline: list[dict]) -> list[dict]:
    """Collapse the per-second timeline into contiguous screen states."""
    states: list[dict] = []
    for entry in timeline:
        if entry["green_ratio"] >= 1.0 and entry["white_ratio"] < 20.0:
            # The DarwinBoot marker is a solid bar at the very top of the
            # display with no boot text on it. The same hue shows up in the
            # Android wallpaper, so the text share has to be ruled out too.
            state = "green-bar"
        elif entry["white_ratio"] >= 3.0:
            state = "console-text"
        elif entry["mean_luma"] < 56.0:
            state = "dark"
        else:
            state = "dim"
        if states and states[-1]["state"] == state:
            states[-1]["end_second"] = entry["second"]
            states[-1]["frames"] += 1
            states[-1]["max_white_ratio"] = max(
                states[-1]["max_white_ratio"], entry["white_ratio"]
            )
            states[-1]["max_green_ratio"] = max(
                states[-1]["max_green_ratio"], entry["green_ratio"]
            )
            continue
        states.append(
            {
                "state": state,
                "start_second": entry["second"],
                "end_second": entry["second"],
                "frames": 1,
                "max_white_ratio": entry["white_ratio"],
                "max_green_ratio": entry["green_ratio"],
            }
        )
    return states


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame_dir", type=Path, help="directory of t_XXXX.jpg frames")
    parser.add_argument("--out", type=Path, required=True, help="json output path")
    parser.add_argument("--step", type=int, default=1, help="sampling step in frames")
    args = parser.parse_args()

    frames = sorted(args.frame_dir.glob("t_*.jpg"))
    if not frames:
        raise SystemExit(f"no frames under {args.frame_dir}")

    timeline = []
    for index in range(0, len(frames), args.step):
        path = frames[index]
        entry = {"second": index + 1, "frame": path.name}
        entry.update(metrics(load_display(path, DEFAULT_DISPLAY_BOX)))
        timeline.append(entry)

    report = {
        "source": {
            "frame_dir": str(args.frame_dir),
            "frame_count": len(frames),
            "sampling_step": args.step,
            "display_box": list(DEFAULT_DISPLAY_BOX),
        },
        "timeline": timeline,
        "segments": segment(timeline),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["segments"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
