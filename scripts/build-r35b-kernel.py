#!/usr/bin/env python3
"""Run the pinned r35 kernel recipe with the isolated r35b exit predicate."""
import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

BUILD_SHA = "c2e8bcc0aae8a6736592079b4f0bd1fba9032490ddfa432f30df9e6fbc619979"
HEADER_SHA = "86311631e7cf66881bd6d1a57a927c78db9ea9bb579deb025136252e3e218c72"
RENDERER_SHA = "a4163ecd10ecfd6bb429f2ce9c919f9a67a6dab85c936beeabb8f7fba2fe89be"
OLD_ASSERT = "assert ring_body.count('if(status || ns) {') == 1, 'ring must keep abnormal exits only'"
NEW_ASSERT = "assert ring_body.count('if(signal || ns) {') == 1 and ring_body.count('if(status || ns) {') == 0, 'ring must keep signal or reason exits only'"


def pin(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("pinned input mismatch: " + expected)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("r35", type=Path, help="original r35 directory")
    parser.add_argument("out", type=Path, help="new directory under the original repository out/")
    args = parser.parse_args()
    r35 = args.r35.resolve()
    out = args.out.resolve()
    if r35.name != "nuwa-r35-20261119" or out.parent != r35.parent or out == r35:
        parser.error("output must be a new sibling of the original r35 directory")
    build = pin((r35 / "build.py").read_bytes(), BUILD_SHA).decode()
    header = pin((r35 / "BootProgressDisplay.h").read_bytes(), HEADER_SHA)
    spec = importlib.util.spec_from_file_location("selection", Path(__file__).with_name("generate-r35-exit-selection.py"))
    selection = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selection)
    renderer = pin(selection.generate((r35 / "BootProgress.c").read_bytes()), RENDERER_SHA)
    if build.count(OLD_ASSERT) != 1:
        raise ValueError("r35 assertion anchor changed")
    out.mkdir()
    (out / "BootProgress.c").write_bytes(renderer)
    (out / "BootProgressDisplay.h").write_bytes(header)
    namespace = {"__file__": str(r35 / "build.py"), "__name__": "r35b_recipe"}
    exec(compile(build.replace(OLD_ASSERT, NEW_ASSERT, 1), str(r35 / "build.py"), "exec"), namespace)
    namespace["RENDERER"] = out / "BootProgress.c"
    sys.argv = [str(r35 / "build.py"), "--out", str(out)]
    namespace["main"]()


if __name__ == "__main__":
    main()
