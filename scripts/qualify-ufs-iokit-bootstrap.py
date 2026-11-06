"""Re-execute the existing native startup model with the enlarged carrier.

This checks the actual loader-derived placement and TTBR reconstruction, then
checks every added leaf. It does not model UFS hardware or prove IOKit matching.
"""
import argparse
import json
import runpy
import sys
from pathlib import Path

import flush_trace_inputs as trace

parser = argparse.ArgumentParser()
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--case', choices=('normal', 'occupied-probe', 'bad-topology', 'occupied-fb'), default='normal')
args = parser.parse_args()
work = args.work.resolve()
proof = json.loads((work/'kernel-proof.json').read_bytes())
kernel = work/'kernel.macho'
build = trace.read(trace.BASE/'build.json')
build['candidate'] = dict(path=kernel.relative_to(trace.R).as_posix(), bytes=kernel.stat().st_size,
                          sha256=proof['kernel_sha256'])
build['overlay_scope'] = 'Parent startup metadata with candidate bytes replaced. Re-execution only.'
input_path = work/'bootstrap-input.json'
input_path.write_text(json.dumps(build, indent=2)+'\n')
report_path = work/('bootstrap-'+args.case+'.json')
adt = work/'launch/kernel.macho.adt'
sys.argv = ['test-probe-transition.py', '--build', str(input_path), '--adt', str(adt),
            '--output', str(report_path), '--case', args.case]
if (work/'kernel.macho.trustcache').exists():
    sys.argv += ['--trust-cache',str(work/'kernel.macho.trustcache'),'--loader-layout',str(work/'payload-loader-tests.json')]
runtime = runpy.run_path(str(trace.R/'scripts/test-probe-transition.py'), run_name='__main__')
if args.case == 'normal':
    walk = runtime['walk']
    targets = proof['targets']
    for va in range(targets['old_end'], proof['mapped_end'], 4096):
        result = walk(va)
        if va < targets['driver_text']:
            assert not result['mapped'], (hex(va), result)
            continue
        assert result['mapped'] and int(result['pa'], 16) == runtime['PA']+va-runtime['base']
        descriptor = int(result['rows'][-1], 16)
        writable = va >= targets['driver_data']
        executable = va < targets['driver_const']
        assert bool(descriptor & (1 << 7)) != writable
        assert bool(descriptor & (1 << 53)) != executable
        assert descriptor & (1 << 54)
    result = json.loads(report_path.read_bytes())
    result['overlay_checks'] = dict(passed=True, mapped_end=hex(proof['mapped_end']),
        exact_physical_addresses=True, rx_text=True, ro_nx_constants=True, rw_nx_data=True,
        guard_gap_unmapped=True, device_execution=False)
    report_path.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS actual native startup and extended leaf permissions')
