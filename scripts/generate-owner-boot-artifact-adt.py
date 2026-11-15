"""Generate an opt-in owner-defined host ADT; does not package or access devices."""
import argparse
from pathlib import Path

from owner_bnch import generate_candidate, read_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--dtb', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True, help='Resolved ordered configuration JSON')
    p.add_argument('--keywords', type=Path, required=True, help='JSON containing all five generate keywords')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--enable-owner-bnch', action='store_true')
    p.add_argument('--reuse-record', type=Path)
    a = p.parse_args()
    report = generate_candidate(a.base, a.dtb, read_json(a.config), read_json(a.keywords),
                                a.output, a.enable_owner_bnch, a.reuse_record)
    print('self-checked:', a.output, 'enabled=' + str(report['enabled']))


if __name__ == '__main__':
    main()
