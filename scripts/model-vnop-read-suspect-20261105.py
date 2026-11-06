"""P0-VNOP-PAIR r2 嫌疑点定向 Unicorn 模型（2026-11-05，离线只读）。

目的：把「FB03 出现 / FB06 空白」这一实机读数，与当前上机内核的实际机器码对上，
判断卡点究竟在哪一段。模型只执行 r2 内核的真实字节，不模拟 APFS / UFS 硬件。

三个受控实验：
  A. 从 0x7466B10（FB03 hook 挂点）起跑，给 VNOP_READ 打桩立即返回，
     验证 hook 正确重放原生指令并返回 0x7466B14，最终到达 0x7466B24（FB06 hook）。
     -> 排除「观测 hook 自身损坏 / 跳错」这一解释。
  B. 同 A 但 VNOP_READ 打桩为「永不返回」（停在自己地址），
     验证 FB06 hook 不被触发（FB06 空白）而 FB03 已画出。
     -> 复现实机读数形态，证明「VNOP_READ 未返回」与读数一致。
  C. 枚举 0x7466B10..0x7466B24 之间的所有控制流，确认除 bl _VNOP_READ
     外没有任何可绕过 0x7466B24 的分支或早退。

用法（WSL Ubuntu-22.04，python3 有 unicorn 2.1.4）：
  wsl -d Ubuntu-22.04 -- bash -lc 'cd /mnt/d/.../UniXNU-nuwa && python3 scripts/model-vnop-read-suspect-20261105.py'

不操作设备、不改内核、不构建、不写分区、不提交 git。
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import unicorn as U
from unicorn.arm64_const import *

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/p0-vnop-pair-20261105-r2/model'
OUT.mkdir(parents=True, exist_ok=True)

KERNEL = R / 'out/p0-vnop-pair-20261105-r2/kernel.macho'
PROOF = R / 'out/p0-vnop-pair-20261105-r2/kernel-proof.json'
EXPECTED = '1a7ad049a93de9c7cd80c008745d0a2003a2ad29fec65ce2dbefc475708dc72d'

# r2 实际地址（从 kernel-proof.json 的 targets / symbols 与实际机器码解出）
P_FB03_SITE = 0xfffffff007466b10
P_FB03_RESUME = 0xfffffff007466b14
P_BL_VNOP_READ = 0xfffffff007466b20
P_FB06_SITE = 0xfffffff007466b24
P_FB06_RESUME = 0xfffffff007466b28
P_VNOP_READ = 0xfffffff00746c628
P_VNOP_READ_BLR = 0xfffffff00746c688
P_MACSITE = 0xfffffff007466acc
P_FB07_SITE = 0xfffffff007466ad0

MEM = 0x20000000
STACK = MEM + 0x38000
SENTINEL = MEM + 0x3f000
THREAD = MEM + 0x1000
FRAMEBUFFER = MEM + 0x20000


def segments(raw: bytes) -> list[dict]:
    out = []
    offs = 32
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, offs)
        if cmd == 0x19:
            va, vs, fo, fs = struct.unpack_from('<QQQQ', raw, offs + 24)
            name = raw[offs + 8:offs + 24].split(b'\0')[0].decode()
            out.append(dict(name=name, va=va, size=vs, fileoff=fo, filesize=fs))
        offs += sz
    return out


class Machine:
    def __init__(self, raw: bytes, proof: dict, vnop_mode: str):
        self.raw = raw
        self.segs = segments(raw)
        self.sy = proof['symbols']
        self.vnop_mode = vnop_mode
        self.u = U.Uc(U.UC_ARCH_ARM64, U.UC_MODE_ARM)
        self.u.mem_map(MEM, 0x40000)
        self.pages = set()
        self.callbacks = {}
        self.visits = {}
        self.draws = []
        self.stopped = None
        self.events = []
        self.u.hook_add(U.UC_HOOK_MEM_UNMAPPED, self.fault)
        self.u.hook_add(U.UC_HOOK_CODE, self.hook)
        self.u.reg_write(UC_ARM64_REG_SP, STACK)
        self.u.reg_write(UC_ARM64_REG_LR, SENTINEL)
        self.u.reg_write(UC_ARM64_REG_TPIDR_EL1, THREAD)
        self.u.reg_write(UC_ARM64_REG_CPACR_EL1, 3 << 20)
        self.callbacks[SENTINEL] = lambda: self.stop('returned-to-sentinel')
        self.callbacks[self.sy['draw']] = self.draw
        self.callbacks[P_FB06_SITE] = lambda: self.stop('reached-FB06-join-point')
        self.callbacks[P_VNOP_READ] = self.vnop_stub
        # 让 FB03/FB06 hook 用到的 framebuffer 地址可写
        self.u.mem_write(FRAMEBUFFER, b'\0' * 0x1000)

    def fault(self, u, access, addr, size, value, data):
        page = addr & ~4095
        seg = next((s for s in self.segs
                    if s['va'] <= page < s['va'] + s['filesize']), None)
        if seg is None:
            return False
        off = seg['fileoff'] + page - seg['va']
        n = max(0, min(4096, seg['filesize'] - (page - seg['va'])))
        u.mem_map(page, 4096)
        u.mem_write(page, self.raw[off:off + n] + bytes(4096 - n))
        self.pages.add(page)
        return True

    def x(self, n, value=None):
        reg = UC_ARM64_REG_X0 + n if n < 29 else (
            UC_ARM64_REG_X29 if n == 29 else UC_ARM64_REG_LR)
        if value is None:
            return self.u.reg_read(reg)
        self.u.reg_write(reg, value & ((1 << 64) - 1))

    def ret(self, value=0):
        self.x(0, value)
        self.u.reg_write(UC_ARM64_REG_PC, self.x(30))

    def stop(self, reason):
        self.stopped = reason
        self.u.emu_stop()

    def draw(self):
        self.draws.append(dict(field=self.x(0) & 0xffffffff,
                               value=self.x(1) & 0xffffffff))
        self.ret(self.x(0))

    def vnop_stub(self):
        self.events.append('entered-_VNOP_READ')
        if self.vnop_mode == 'return':
            self.ret(0)          # 模拟 VNOP_READ 成功返回
        elif self.vnop_mode == 'hang':
            self.stop('VNOP_READ-did-not-return')
        elif self.vnop_mode == 'real':
            self.u.reg_write(UC_ARM64_REG_PC, P_VNOP_READ + 4)
        else:
            raise ValueError(self.vnop_mode)

    def hook(self, u, pc, size, data):
        self.visits[pc] = self.visits.get(pc, 0) + 1
        if pc in self.callbacks:
            self.callbacks[pc]()

    def run(self, start, count=20000):
        try:
            self.u.emu_start(start, 0, count=count)
        except U.UcError as e:
            self.stopped = 'uc-error:%s@%s' % (e, hex(self.u.reg_read(UC_ARM64_REG_PC)))
        return dict(
            stop=self.stopped,
            draws=self.draws,
            events=self.events,
            pc=hex(self.u.reg_read(UC_ARM64_REG_PC)),
            visited_FB03_resume=hex(P_FB03_RESUME) in [hex(p) for p in self.visits],
            visited_bl_vnop_read=hex(P_BL_VNOP_READ) in [hex(p) for p in self.visits],
            visited_FB06_site=hex(P_FB06_SITE) in [hex(p) for p in self.visits],
            executed_instructions=sum(self.visits.values()),
            visited=[hex(p) for p in self.visits],
        )


def static_flow() -> list[dict]:
    """0x7466B10..0x7466B28 的静态逐字解码（不依赖 Unicorn）。"""
    raw = KERNEL.read_bytes()
    segs = segments(raw)

    def off(va):
        for s in segs:
            if s['va'] <= va < s['va'] + s['filesize']:
                return s['fileoff'] + va - s['va']
        raise KeyError(hex(va))

    rows = []
    for va in range(P_FB03_SITE, P_FB06_RESUME, 4):
        w = struct.unpack_from('<I', raw, off(va))[0]
        kind = 'other'
        target = None
        if w & 0xfc000000 == 0x94000000:
            imm = w & 0x3ffffff
            imm -= (1 << 26) if imm & (1 << 25) else 0
            kind, target = 'bl', hex((va + 4 * imm) & 0xffffffffffffffff)
        elif w & 0x7c000000 == 0x14000000:
            imm = w & 0x3ffffff
            imm -= (1 << 26) if imm & (1 << 25) else 0
            kind, target = 'b', hex((va + 4 * imm) & 0xffffffffffffffff)
        elif (w >> 24) & 0x9f in (0x34, 0x35, 0xb4, 0xb5):
            kind = 'conditional-branch'
        elif w == 0xd65f03c0:
            kind = 'ret'
        rows.append(dict(address=hex(va), word='%08x' % w,
                         kind=kind, target=target))
    return rows


def main() -> None:
    raw = KERNEL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED, '内核 SHA 不匹配'
    proof = json.loads(PROOF.read_bytes())

    flow = static_flow()
    branches = [r for r in flow if r['kind'] in ('b', 'bl', 'conditional-branch', 'ret')]

    experiments = {}
    for name, mode in (('A_vnop_returns', 'return'),
                       ('B_vnop_hangs', 'hang')):
        m = Machine(raw, proof, mode)
        # 从 FB03 挂点进入：该处实际字节是 b -> p0_vnop_read_entry
        experiments[name] = m.run(P_FB03_SITE)

    ev = dict(
        schema='nuwa/p0-vnop-pair-r2/vnop-suspect-model/1',
        question='结合前面分析与当前实际运行内核代码，判断当前嫌疑点',
        kernel=dict(path=str(KERNEL.relative_to(R)).replace('\\', '/'),
                    sha256=EXPECTED),
        unicorn_version=U.__version__,
        method='Unicorn 2 执行 r2 内核真实字节；draw 打桩记录字段写入；'
               'VNOP_READ 打桩为「立即返回」或「不返回」两种受控条件；'
               '不模拟 APFS / IOKit / UFS 硬件',
        static_flow=dict(
            range=[hex(P_FB03_SITE), hex(P_FB06_RESUME)],
            rows=flow,
            branch_count=len(branches),
            branches=branches,
            note='FB03 挂点 0x7466B10 到 FB06 汇合点 0x7466B24 之间只有 '
                 '3 条 mov + 1 条 bl _VNOP_READ；无其他分支或早退'),
        call_targets=dict(
            mac_vnode_check_read='0xfffffff007916d5c',
            vnode_isswap='0xfffffff00746ad24',
            vn_read_swapfile='0xfffffff007466b94',
            VNOP_READ='0xfffffff00746c628',
            VNOP_READ_indirect_dispatch='0xfffffff00746c688 blr x8 (v_op table)',
            uio_resid='0xfffffff0076bc878'),
        experiments=experiments,
        interpretation=dict(
            A='若 VNOP_READ 返回，控制流必然经过 0x7466B24（FB06 hook）；'
              '因此 FB06 空白不能由「返回后走了别的路」解释。',
            B='若 VNOP_READ 不返回，FB03 已画出而 FB06 不触发，'
              '与实机读数形态一致。',
            excluded=['MAC 拒绝（FB07=0）', 'len<0 早退（FB03 已到达）',
                      'write / swap 直跳汇合点（那些路径也会触发 FB06）',
                      '观测 hook 自身跳错（实验 A 验证可返回到 0x7466B14）'],
            primary_suspect='0x7466B20 bl _VNOP_READ 内部，具体在 '
                            '0x746C688 blr x8 间接分派之后的文件系统 vnop → '
                            'APFS / decmpfs / cluster·UPL / IOStorageCompletion 链中某处未返回',
            not_determined='该链中具体哪一层、哪种机制（锁 / 完成事件 / DMA / 超时）；'
                           '模型没有真实 vnode、uio、APFS 卷与 IOKit 完成事件'),
        boundaries=[
            'Unicorn 是受控静态模型，不是实机 trace；不证明真实硬件行为。',
            '实机读数来自 5.982 s 录像，零变化只证明该窗口内稳定。',
            'FB06 挂点本轮无阳性命中，空白按 AGENTS §6 只写「未观察到」。',
            '本轮未操作设备、未改内核、未构建、未写分区、未提交 git。'])

    (OUT / 'suspect-model.json').write_text(
        json.dumps(ev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('unicorn', U.__version__)
    print('static branches between FB03 and FB06:', len(branches))
    for k, v in experiments.items():
        print(k, '| stop:', v['stop'], '| draws:', v['draws'],
              '| FB06 reached:', v['visited_FB06_site'],
              '| bl reached:', v['visited_bl_vnop_read'])
    print('written:', OUT / 'suspect-model.json')


if __name__ == '__main__':
    main()
