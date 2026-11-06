"""由 CHECK10 观测源码派生 P0 原生恢复候选的观测源码。

P0 只保留：入口初始化 + 10 个 coarse 大阶段 + phase_record
+ coarse_release_before（功能件），并追加 1 个 MAC-read 返回标记。
退役 8 个自建改道 hook（对应 11 个恢复点中的 CHECK4 部分）与
CHECK8/10 的 3 个细粒度 hook；相应挂点在 build 期恢复为真原生字节。

只写源码文件与切片证据，不改内核、不构建、不操作设备。
"""
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SRC = R / 'package/kernel-mainline/CoarseStages-ufs-check10-r1.S'
OUT = R / 'package/kernel-mainline/CoarseStages-p0-native-restore-20261105.S'
EVIDENCE = R / 'reports/native-restore-20261105/p0-observer-source.json'

M_GETATTR = '.global coarse_getattr_before\n'
M_RELEASE = '.global coarse_release_before\n'
M_CHECK8 = '// ===== CHECK8 =====\n'

# 挂在 _vn_rdwr_64 的 mac_vnode_check_read 返回后分派点 0x7466AD0。
# 原生指令是 cbnz w0,0x7466B24；本 hook 完整重放该分支语义。
NEW_HOOK = '''
// ===== P0 唯一新增观测：MAC-read 返回标记 =====
// 挂点 0xfffffff007466ad0，原生字 a0020035 = cbnz w0,0xfffffff007466b24。
// 上一句是 bl _mac_vnode_check_read (0x7466acc)，故 w0 是 MAC-read 返回码。
// FB07 (N=7) 是本候选中该编号的唯一写入源：值 = w0。
//   FB07 == 0        -> MAC-read 放行，继续 0x7466ad4 的 VNOP_READ 后端
//   FB07 != 0        -> MAC-read 拒绝，走原生错误汇合 0x7466b24
//   FB07 == FFFFFFFF -> 未到达该分派点（挂点之前已停）
// 保存/恢复 x0-x29、x30、NZCV；恢复后再按原生 cbnz 语义分派。
.global p0_mac_read_after
p0_mac_read_after:
    sub sp,sp,#256
    stp x0,x1,[sp,#0]
    stp x2,x3,[sp,#16]
    stp x4,x5,[sp,#32]
    stp x6,x7,[sp,#48]
    stp x8,x9,[sp,#64]
    stp x10,x11,[sp,#80]
    stp x12,x13,[sp,#96]
    stp x14,x15,[sp,#112]
    stp x16,x17,[sp,#128]
    stp x18,x19,[sp,#144]
    stp x20,x21,[sp,#160]
    stp x22,x23,[sp,#176]
    stp x24,x25,[sp,#192]
    stp x26,x27,[sp,#208]
    stp x28,x29,[sp,#224]
    str x30,[sp,#240]
    mrs x9,nzcv
    str x9,[sp,#248]
    mov w1,w0
    mov w0,#7
    bl draw
    ldr x9,[sp,#248]
    msr nzcv,x9
    ldp x0,x1,[sp,#0]
    ldp x2,x3,[sp,#16]
    ldp x4,x5,[sp,#32]
    ldp x6,x7,[sp,#48]
    ldp x8,x9,[sp,#64]
    ldp x10,x11,[sp,#80]
    ldp x12,x13,[sp,#96]
    ldp x14,x15,[sp,#112]
    ldp x16,x17,[sp,#128]
    ldp x18,x19,[sp,#144]
    ldp x20,x21,[sp,#160]
    ldp x22,x23,[sp,#176]
    ldp x24,x25,[sp,#192]
    ldp x26,x27,[sp,#208]
    ldp x28,x29,[sp,#224]
    ldr x30,[sp,#240]
    add sp,sp,#256
    cbnz w0,p0_mac_read_error
    .jump p0_mac_read_resume
p0_mac_read_error:
    .jump p0_mac_read_error_target
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    src = SRC.read_text(encoding='utf-8')
    assert src.count(M_GETATTR) == 1 and src.count(M_RELEASE) == 1 and src.count(M_CHECK8) == 1
    head, rest = src.split(M_GETATTR, 1)
    retired_dense, rest2 = rest.split(M_RELEASE, 1)
    release, retired_check8_10 = rest2.split(M_CHECK8, 1)
    out = head + M_RELEASE + release + NEW_HOOK

    # 10 个大阶段与功能件必须全部留在派生源码里。
    stages = ('coarse_root_wait', 'coarse_root_return', 'coarse_root_auth',
              'coarse_mount_return', 'coarse_init_entry', 'coarse_init_loaded',
              'coarse_exec_entry', 'coarse_exec_namei', 'coarse_exec_result',
              'coarse_el0', 'phase_record', 'coarse_release_before')
    for name in stages:
        assert (name + ':\n') in out, 'missing stage ' + name
    # coarse_state+104 的线程锁存写入源必须保留，否则 coarse_release_before 失效。
    assert 'str x10,[x9,#104]' in out, 'thread latch setter dropped'
    assert 'str xzr,[x9,#104]' in out, 'thread latch clearer dropped'
    # 退役的 hook 不应残留；FB07 必须只有新 hook 一个写入源。
    for name in ('coarse_getattr_before', 'coarse_read_before', 'coarse_read_after',
                 'c8_selfcheck', 'c8_read_return', 'c10_vn_rdwr_ret'):
        assert (name + ':\n') not in out, 'retired hook leaked: ' + name
    assert out.count('mov w0,#7\n') == 1, 'FB07 must have exactly one writer'
    assert 'movz x30,#49044' not in out, 'self-built x30 detour must be gone'
    assert out.count('.jump p0_mac_read_resume') == 1
    assert out.count('.jump p0_mac_read_error_target') == 1

    OUT.write_text(out, encoding='utf-8')
    EVIDENCE.write_text(json.dumps(dict(
        schema='Nuwa.P0ObserverSource.v1',
        input=str(SRC.relative_to(R)), input_sha256=sha(src.encode()),
        output=str(OUT.relative_to(R)), output_sha256=sha(out.encode()),
        output_bytes=len(out.encode()),
        kept_sections=['trace_1 初始化', '.text 头部', '10 个 coarse 大阶段',
                       'pmgr_install', 'phase_record', 'coarse_release_before'],
        retired_sections=['8 个自建改道/密集诊断 hook (coarse_getattr_* 等)',
                          'CHECK8 c8_selfcheck / c8_read_return',
                          'CHECK10 c10_vn_rdwr_ret'],
        retired_bytes=len((M_GETATTR + retired_dense).encode()) + len((M_CHECK8 + retired_check8_10).encode()),
        new_hook=dict(name='p0_mac_read_after',
                      patch_address='0xfffffff007466ad0',
                      native_word='a0020035',
                      native_semantics='cbnz w0,0xfffffff007466b24',
                      field_decimal_id=7, field_label='0xFB07',
                      field_value_source='w0 = mac_vnode_check_read 返回码',
                      resume_zero='0xfffffff007466ad4',
                      resume_nonzero='0xfffffff007466b24'),
        field_id_formula='draw: ID = (N + 0xB00) | 0xF000 = 0xFB00 + N; N 为十进制，屏幕后缀为十六进制',
        limitations=['派生源码，未编译；符号地址由构建脚本重算。',
                     '本脚本只写源码与切片证据，不改内核、不构建、不操作设备。'],
    ), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('wrote', OUT.relative_to(R), len(out.encode()), 'bytes')
    print('stages kept', len(stages), '| FB07 writers', out.count('mov w0,#7\n'))
    print('evidence', EVIDENCE.relative_to(R))


if __name__ == '__main__':
    main()
