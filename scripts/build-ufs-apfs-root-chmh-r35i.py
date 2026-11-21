#!/usr/bin/env python3
"""r35h packaging with an experimental chosen display scale."""
import importlib.util
import sys
from pathlib import Path

SOURCE = Path(__file__).with_name("build-ufs-apfs-root-chmh-r35b.py")
spec = importlib.util.spec_from_file_location("r35b_profile", SOURCE)
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)
ns = profile.load_profile()
X = ns["X"]
A = X.C.C
previous_derived = X.derived
previous_check = X.check_adt
value = (3).to_bytes(4, "little")


def derived(parent, digest):
    tree = A.parse(previous_derived(parent, digest))
    chosen = A.find(tree, "/chosen")
    if "display-scale" in A.properties(chosen):
        raise ValueError("parent already has /chosen/display-scale")
    if A.properties(A.find(tree, "/product")).get("artwork-scale-factor") != value:
        raise ValueError("/product/artwork-scale-factor is not u32 3")
    chosen["properties"].append(("display-scale", 0, value))
    return A.encode(tree)


def check_adt(parent, actual, digest):
    previous_check(parent, actual, digest)
    chosen = A.find(A.parse(actual), "/chosen")
    if [p for p in chosen["properties"] if p[0] == "display-scale"] != [
        ("display-scale", 0, value)
    ]:
        raise ValueError("/chosen/display-scale is not u32 3")


X.derived = X.C.derived = derived
X.check_adt = X.C.check_adt = check_adt

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    ns["M"].main()
