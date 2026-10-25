"""The audited iOS16 pthread addition, expressed as bounded baseline deltas."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'out/pthread-prelink-v28-analysis/kernel-pthread-analysis.macho'
SHA256 = '52227410fd5ad0da9b8487a3fc3706a8f03042cc8256cfe99018897337f47e01'


def load(original):
    image = PATH.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA256 or len(image) != len(original):
        raise ValueError('Audited pthread prelink bytes/extent changed')
    return image


def ranges(original, replacement):
    """Merge nearby changed bytes without hiding any bytes from the preimage."""
    start = end = None
    result = []
    for offset, (before, after) in enumerate(zip(original, replacement)):
        if before == after:
            continue
        if start is None:
            start = end = offset
        elif offset - end <= 32:
            end = offset
        else:
            result.append((start, replacement[start:end + 1]))
            start = end = offset
    if start is not None:
        result.append((start, replacement[start:end + 1]))
    return result
