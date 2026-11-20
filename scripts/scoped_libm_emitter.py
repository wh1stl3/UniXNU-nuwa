"""Load the pinned emitter with a narrowly scoped, full-digest Libm region."""
import hashlib
from pathlib import Path
import types

SOURCE_SHA256 = "c3eddb81759dd4511c2f77a6fc3f2cf22282f29bd3688ded7855599d98405439"
DONOR_SHA256 = "2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221"
REGION_SHA256 = "12d22dca8e3a79e476ab128f73e28f630bf902d5189ed1d5317589930c0c8622"
START, END, FILE_OFFSET = 0xfffffff005b8c054, 0xfffffff005b8c51c, 0x1740054
SEGMENT_VA = 0xfffffff005b8b000
MODULE = "com.apple.kec.Libm"

INSERTION = """            literals = []
            # Exact 20H392 donor/module/segment/address/full-region identity.
            if (donor_sha256 == SCOPED_DONOR_SHA256 and identifier == SCOPED_MODULE
                    and segment['va'] == SCOPED_SEGMENT_VA
                    and segment['va'] <= SCOPED_START < SCOPED_END <= segment['va'] + len(blob)
                    and at + SCOPED_START - segment['va'] == SCOPED_FILE_OFFSET):
                start = SCOPED_START - segment['va']
                end = SCOPED_END - segment['va']
                if hashlib.sha256(blob[start:end]).hexdigest() == SCOPED_REGION_SHA256:
                    literals.append((start, end))
                    literal_ranges.append({'module': identifier, 'va': SCOPED_START,
                                           'size': end - start, 'sha256': SCOPED_REGION_SHA256})
"""


def load(base):
    path = Path(base) / "kits/XnuPrelink/emit_prelink.py"
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("pinned XnuPrelink emitter source SHA256 mismatch")
    source = raw.decode("utf-8").replace("\r\n", "\n")
    old = "    literal_ranges, instruction_count = [], 0\n"
    if source.count(old) != 1 or source.count("            literals = []\n") != 1:
        raise ValueError("pinned emitter patch anchors changed")
    source = source.replace(old, old + "    donor_sha256 = hashlib.sha256(original_data).hexdigest()\n")
    source = source.replace("            literals = []\n", INSERTION)
    module = types.ModuleType("scoped_emit_prelink")
    module.__dict__.update(SCOPED_DONOR_SHA256=DONOR_SHA256, SCOPED_MODULE=MODULE,
                           SCOPED_SEGMENT_VA=SEGMENT_VA, SCOPED_START=START,
                           SCOPED_END=END, SCOPED_FILE_OFFSET=FILE_OFFSET,
                           SCOPED_REGION_SHA256=REGION_SHA256)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module
