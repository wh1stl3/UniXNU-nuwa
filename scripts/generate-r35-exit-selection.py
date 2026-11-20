#!/usr/bin/env python3
"""Generate a separate r35 BootProgress.c with a narrower exit-ring filter."""
import argparse
import hashlib
from pathlib import Path

SHA = "c6e5655257e708a0b304b12fded80b81e38c10fc20f4c8119bfef58d91a45a35"
OLD = b"  if(status || ns) {\n"
NEW = b"  if(signal || ns) {\n"


def generate(data):
    if hashlib.sha256(data).hexdigest() != SHA or data.count(OLD) != 1:
        raise ValueError("input is not the pinned r35 BootProgress.c")
    return data.replace(OLD, NEW, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = generate(args.source.read_bytes())
    with args.output.open("xb") as output:
        output.write(data)


if __name__ == "__main__":
    main()
