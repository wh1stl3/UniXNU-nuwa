"""Differential execution of two pinned original APFS donors, not device qualification."""
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *

REF = ROOT.parent / 'references/kmain20-public-review/binary-comparison'
spec = importlib.util.spec_from_file_location('np', 'D:/Code/PortingiOSLegacy/common/sources/UniXNU/kits/NativePrelink/native_prelink.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
addresses = {
    '16': (0xfffffff00622d6cc, 0xfffffff0061f9ac8, 0xfffffff00616b1cc, 0xfffffff00622bac8, 0xfffffff00622bb4c),
    '17': (0xfffffff006727670, 0xfffffff0066ef974, 0xfffffff006664934, 0xfffffff006725b30, 0xfffffff006725bb4),
}
rows = []
inputs = {}
for version, (search, compare, diagnostic, fetch, lower) in addresses.items():
    meta = json.loads((REF / ('apfs' + version + '-metadata.json')).read_text())
    raw = Path(meta['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta['sha256']
    inputs[version] = meta['sha256']
    parent = P.macho(raw)
    for case in ['one', 'three', 'eight', 'below', 'above', 'variable', 'short-query', 'bad-key-range', 'empty', 'fetch-zero', 'fetch-old-flags', 'fetch-new-flags']:
        u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        u.mem_map(0x20000000, 0x20000)
        pages = set()
        def fault(uc, access, address, size, value, userdata):
            page = address & ~4095
            assert page not in pages
            seg = next(s for s in parent['segments'] if s['va'] <= page < s['va'] + s['size'])
            n = max(0, min(4096, seg['filesize'] - page + seg['va']))
            off = seg['fileoff'] + page - seg['va']
            uc.mem_map(page, 4096)
            uc.mem_write(page, raw[off:off+n] + bytes(4096-n))
            pages.add(page)
            return True
        u.hook_add(U.UC_HOOK_MEM_UNMAPPED, fault)
        def put(a, v, n=8):
            u.mem_write(a, v.to_bytes(n, 'little'))
        def reg(i):
            return u.reg_read(getattr(U.arm64_const, 'UC_ARM64_REG_X' + str(i)))
        node, header, fs, table, data, key, output = [0x20001000 + i*0x1000 for i in range(7)]
        stack, end = 0x20018000, 0x2001f000
        keys = [42] if case == 'one' else list(range(40, 48)) if case == 'eight' else [41, 42, 43]
        if case == 'empty': keys = []
        put(node, fs); put(node+8, fs); put(node+0xc0, header)
        put(node+0xc8, table); put(node+0xd0, data); put(node+0xe8, 8, 4)
        put(node+0x100, compare); put(node+0x108, fs)
        put(fs+0x24, 13, 2); put(fs+0x180, fs)
        variable = case == 'variable'
        put(header+0x20, 2 if variable else 6, 2)
        put(header+0x24, len(keys), 4); put(header+0x2c, 128, 2)
        for i, oid in enumerate(keys):
            put(table+i*(8 if variable else 4), i*8, 2)
            if variable: put(table+i*8+2, 8, 2)
            put(data+i*8, (3 << 60) | oid)
        if case == 'bad-key-range':
            for i in range(len(keys)): put(table+i*4, 128, 2)
        wanted = 39 if case == 'below' else 49 if case == 'above' else 42
        put(key, (3 << 60) | wanted)
        args = [node, key, 4 if case == 'short-query' else 8, output, output+8]
        if case.startswith('fetch-'):
            flags = {'fetch-zero': 0, 'fetch-old-flags': 0xe000, 'fetch-new-flags': 0x1c00}[case]
            put(node+0x10, flags, 4)
            args = [node, key, 0, 0, 0, 0, output]
        for i, v in enumerate(args): u.reg_write(getattr(U.arm64_const, 'UC_ARM64_REG_X'+str(i)), v)
        u.reg_write(UC_ARM64_REG_SP, stack); u.reg_write(UC_ARM64_REG_LR, end)
        u.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        logs, lower_flags, returned = [], [], []
        def hook(uc, pc, size, userdata):
            if pc == diagnostic:
                logs.append(pc); uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
            elif pc == lower:
                lower_flags.append(reg(1)); uc.reg_write(UC_ARM64_REG_X0, 0)
                uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_LR))
            elif pc == end:
                returned.append(True); uc.emu_stop()
        u.hook_add(U.UC_HOOK_CODE, hook)
        u.emu_start(fetch if case.startswith('fetch-') else search, 0, count=20000)
        assert returned and u.reg_read(UC_ARM64_REG_SP) == stack, (version, case)
        expected = 22 if case == 'short-query' else 92 if case == 'bad-key-range' else 0
        assert reg(0) == expected, (version, case, reg(0))
        result = dict(errno=reg(0), index=struct.unpack('<i', u.mem_read(output, 4))[0], found=struct.unpack('<I', u.mem_read(output+8, 4))[0], lower_flags=lower_flags, diagnostics=len(logs))
        if case in ('one', 'three', 'eight', 'variable'):
            assert result['found'] == 1 and keys[result['index']] == 42, (version, case, result)
        if version == '17':
            previous = next(x['result'] for x in rows if x['version']=='16' and x['case']==case)
            if case == 'fetch-new-flags':
                assert previous['lower_flags']==[0] and result['lower_flags']==[0x1c00]
            else: assert previous == result, (case, previous, result)
        rows.append(dict(version=version, case=case, result=result))
out = ROOT / 'reports/kmain20-public-comparison'
out.mkdir(exist_ok=True)
(out/'differential-machines.json').write_text(json.dumps(dict(passed=True, inputs=inputs, tests=rows, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), scope='Original search, extraction, bounds and inode comparator execute. Synthetic nodes; diagnostic sink and lower fetch modeled. No concurrency, UFS or device proof.'), indent=2)+'\n')
print('PASS', len(rows), 'cross-version machine executions; flag propagation difference reproduced')
