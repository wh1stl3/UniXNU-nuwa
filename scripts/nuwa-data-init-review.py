#!/usr/bin/env python3
"""Host-only disposable Data transaction model. No block-device backend or CLI writer."""
import hashlib

BLOCK = 4096
DISK_BLOCKS = 61850624
PART_FIRST = 3110976
PART_END = 61850619
META_FIRST = 57393401
META_BLOCKS = 770
META_SIZE = META_BLOCKS * BLOCK
PART_BLOCKS = PART_END - PART_FIRST
PREPARE_HASH = "6bdcd73dcf47f64038afbce5c14c7fb2817da9e2074a2597acb8852898e6c3d2"
COMMIT_HASH = "b227e878961df9b0d30ccdd73663206e396d3d2a0466141377439d11f74a86f5"


class Refused(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def geometry(kind, major_minor, logical, blocks, start_512):
    """Validate independently obtained facts; does not obtain or bind a claim."""
    require(logical == BLOCK, "logical block size")
    if kind == "partition":
        require((major_minor, blocks, start_512) ==
                ((259, 16), PART_BLOCKS, PART_FIRST * 8), "partition geometry")
        offset = (META_FIRST - PART_FIRST) * BLOCK
    elif kind == "whole":
        require((major_minor, blocks, start_512) ==
                ((8, 0), DISK_BLOCKS, 0), "whole geometry")
        offset = META_FIRST * BLOCK
    else:
        raise Refused("unknown target")
    require(offset >= 0 and offset + META_SIZE <= blocks * BLOCK, "metadata bounds")
    return offset


def artifacts(prepare, commit):
    require(len(prepare) == META_SIZE and
            hashlib.sha256(prepare).hexdigest() == PREPARE_HASH and not any(prepare),
            "prepare artifact")
    require(len(commit) == BLOCK and hashlib.sha256(commit).hexdigest() == COMMIT_HASH,
            "commit artifact")


def transaction(io, offset, prepare, commit):
    """Review model only; io must expose positioned read/write and sync.

    The caller owns lifetime and exclusion of io. This model cannot establish
    block claim, a cache-bypassing device read, or producer exclusion.
    Any short operation or exception stops; there are no retries.
    """
    artifacts(prepare, commit)
    require(offset in (META_FIRST * BLOCK, (META_FIRST - PART_FIRST) * BLOCK),
            "metadata offset")
    require(io.read(offset, META_SIZE) == prepare, "preimage")
    require(io.write(offset, prepare) == META_SIZE, "prepare short write")
    require(io.sync() is True, "prepare sync")
    require(io.read(offset, META_SIZE) == prepare, "prepare readback")
    require(io.write(offset, commit) == BLOCK, "commit short write")
    require(io.sync() is True, "commit sync")
    require(io.read(offset, META_SIZE) == commit + prepare[BLOCK:], "commit readback")


if __name__ == "__main__":
    print("Host-only review model: no device access, no write command.")
