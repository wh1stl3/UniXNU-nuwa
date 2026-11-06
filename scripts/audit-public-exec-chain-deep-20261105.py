"""深度核查：两公开仓相对 nuwa 在 exec header read → EL0 段的差异 + 接线证据。

离线只读。输出：
  reports/public-exec-chain-deep-20261105/patch-classification.json
  reports/public-exec-chain-deep-20261105/exec-el0-wiring-evidence.json

证据纪律：
- 补丁按「已逐字节读全文」与「仅按名称分类」分开标注 confidence。
- 符号地址从 donor Mach-O 的 LC_SYMTAB 解出，不采信手抄值。
- 分支/立即数一律从 32 位机器码解出。
- 公开仓 SpringBoard 状态是仓库自述，不升格为本机实机证据。
"""
import hashlib
import json
import re
import struct
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/public-exec-chain-deep-20261105'
REF = R / 'references/exec-chain-public-20261105'
REF_ROOT = R / 'references/public-root-chain-20261105'
KERN_EXEC = Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full/bsd/kern/kern_exec.c')

P0_KERNEL = R / 'out/p0-native-restore-20261105-r1/kernel.macho'
CHECK10_KERNEL = R / 'out/ufs-check-10-r1/kernel.macho'
CHECK4_KERNEL = R / 'out/ufs-check-4-r1-clean/kernel.macho'
EARLYSEC = R / 'out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho'

# 已逐字节读全文的补丁（本轮 + 上一轮归档），可下机制级判断。
READ_FULL = {
    '0002': 'references/exec-chain-public-20261105/0002-negroni-UIO_STACKBUF.patch',
    '0015': 'references/exec-chain-public-20261105/0015-sweet-unavailable-trust-cache-runtime.patch',
    '0022': 'references/public-root-chain-20261105/0022-sweet-ramdisk-root-without-iomedia.patch',
    '0025': 'references/exec-chain-public-20261105/0025-sweet-builtin-amfi-no-entitlements.patch',
    '0026': 'references/exec-chain-public-20261105/0026-sweet-builtin-hfs.patch',
    '0028': 'references/public-root-chain-20261105/0028-sweet-ufs-root-device.patch',
    '0029': 'references/exec-chain-public-20261105/0029-sweet-unsealed-root-volume.patch',
    '0031': 'references/exec-chain-public-20261105/0031-sweet-read-write-root.patch',
    '0035': 'references/exec-chain-public-20261105/0035-sweet-amfi-entitlements-platform-binaries.patch',
    '0036': 'references/exec-chain-public-20261105/0036-sweet-amfi-cs-signed.patch',
    '0038': 'references/exec-chain-public-20261105/0038-sweet-applekeystore.patch',
    '0042': 'references/exec-chain-public-20261105/0042-sweet-short-exec-log.patch',
    '0050': 'references/exec-chain-public-20261105/0050-sweet-sandbox-policy.patch',
    '0053': 'references/exec-chain-public-20261105/0053-sweet-crash-scan-springboard.patch',
    '0059': 'references/exec-chain-public-20261105/0059-sweet-iphone-identity.patch',
}

# 作用域分类：L0 = 卡点之前且 nuwa 已实机通过；L1 = root 后端替换（mount 期配置，
# 效果落在 VNOP_READ）；L2 = MAC-read 门；L3 = header read 之后、EL0 之前；L4 = EL0 之后。
LAYER = {
    '0002': ('BUILD_FIX', '编译期 uio 栈缓冲声明替换；含 vfs_vnops.c:964 vn_rdwr_64，但不改控制流/语义'),
    '0021': ('L1', 'mockfs ramdisk root，绕过真实块设备'),
    '0022': ('L1', '无 IOMedia 时去掉 setRootMedia assert'),
    '0024': ('L1', 'mockfs 虚拟 ramdisk I/O'),
    '0026': ('L1', '内置 HFS+，根走 HFS+ 不走 APFS'),
    '0028': ('L1', '自写 UFS root device，512B 逻辑扇区 + 同步 strategy/physio'),
    '0030': ('L1', 'UFS 写支持'),
    '0031': ('L1', 'rootrw=1 挂载标志（不改 mountroot 控制流）'),
    '0034': ('L1', 'UFS DMA above 4G'),
    '0052': ('L1', 'HFS rename swap'),
    '0069': ('L1', 'UFS faster'),
    '0090': ('L1', 'UFS sense / START UNIT'),
    '0092': ('L1', 'UFS WLUN active'),
    '0015': ('L3', 'trust cache 优雅缺失，不 panic/不悬挂'),
    '0025': ('L3', '内置 AMFI 接口，诚实报告无 entitlements'),
    '0029': ('L0', 'FSIOC_KERNEL_ROOTAUTH 失败不 panic；nuwa 实机已过（FB04=50 / FB05=1）'),
    '0035': ('L3', 'AMFI mpo_vnode_check_signature 注册 + platform binary'),
    '0036': ('L3', 'signature hook 置 CS_SIGNED'),
    '0042': ('L3', 'exec 日志（条件编译边界见 conditional_compile）'),
    '0057': ('L3', 'no ext resolver'),
    '0038': ('L4', '内置 AppleKeyStore stand-in'),
    '0050': ('L4', 'permissive Sandbox MAC 策略'),
    '0053': ('L4', 'SpringBoard crash scan'),
    '0059': ('L4', 'iPhone 身份'),
}

# 核心结论：零个补丁改这些位置的「控制流或 I/O 语义」。
# 0002 例外：它改了 vfs_vnops.c:964 vn_rdwr_64 的源码行，但只是编译期声明替换。
NO_COVERAGE = [
    'mac_vnode_check_read / mpo_vnode_check_read',
    'vn_rdwr / vn_rdwr_64 的控制流与 I/O 语义',
    'load_machfile / exec_activate_image 主体',
    'VNOP_READ 分派（XNU 侧）',
    'INITIAL_WAIT / FINAL_WAIT / proc_exec_switch_task / ERET',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def segments(raw):
    offs, out = 32, []
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, offs)
        if cmd == 0x19:
            name = raw[offs + 8:offs + 24].split(b'\0')[0].decode()
            va, vs, fo, fs = struct.unpack_from('<QQQQ', raw, offs + 24)
            out.append((name, va, vs, fo, fs))
        offs += sz
    return out


def at(raw, va, n=16):
    for name, v, vs, fo, fs in segments(raw):
        if v <= va and va + n <= v + fs:
            o = fo + va - v
            return name, o, raw[o:o + n].hex()
    return None, None, None


def symbols(raw):
    offs = 32
    sym = None
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, offs)
        if cmd == 0x2:
            sym = struct.unpack_from('<IIII', raw, offs + 8)
        offs += sz
    if not sym:
        return {}
    symoff, nsyms, stroff, strsize = sym
    out = {}
    for i in range(nsyms):
        strx, ntype, nsect, desc, val = struct.unpack_from('<IBBHQ', raw, symoff + i * 16)
        if not strx or not val:
            continue
        end = raw.find(b'\0', stroff + strx)
        out.setdefault(raw[stroff + strx:end].decode('utf-8', 'replace'), val)
    return out


def branch(word, pc):
    imm = word & 0x3ffffff
    imm = imm - (1 << 26) if imm & (1 << 25) else imm
    return pc + 4 * imm


def patch_headers(path):
    return [l for l in Path(path).read_text(encoding='utf-8').splitlines()
            if l.startswith('diff --git ')]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tree = json.loads((REF / 'repo-tree-manifest.json').read_text(encoding='utf-8'))
    names = {'negroni': tree['negroni']['xnu_patches'],
             'ios_sweet': tree['ios_sweet']['xnu_patches'],
             'guacamole': []}
    rows = []
    for repo, patches in names.items():
        for p in patches:
            num = p.split('-', 1)[0]
            layer, note = LAYER.get(num, ('OUT_OF_SCOPE', '按名称分类，未逐字节审计'))
            full = READ_FULL.get(num)
            rows.append(dict(repo=repo, patch=p, layer=layer, note=note,
                             read_full=bool(full),
                             source=(str(full) if full else None),
                             sha256=sha(R / full) if full else None,
                             confidence='full-diff' if full else 'name-only'))
    counts = {}
    for r in rows:
        counts[r['layer']] = counts.get(r['layer'], 0) + 1

    # 逐字节读全文补丁的 diff 头，作为「改了哪些文件」的可复核证据。
    diffs = {}
    for num, rel in READ_FULL.items():
        p = R / rel
        diffs[num] = dict(path=rel, sha256=sha(p), diff_headers=patch_headers(p))

    board = (REF / 'guacamole-board.toml').read_text(encoding='utf-8')
    args = re.search(r'kernel_args\s*=\s*\[(.*?)\]', board, re.S)
    kernel_args = re.findall(r'"([^"]+)"', args.group(1)) if args else []
    nuwa_board = (R / 'board.toml').read_text(encoding='utf-8')

    classification = dict(
        schema='Nuwa.PublicExecChainDeep.v1', date='2026-11-05',
        purpose='两公开仓相对 nuwa 在 exec header read → EL0 段的差异分层',
        repos=dict(
            negroni=dict(branch=tree['negroni']['branch'], xnu_patch_count=len(names['negroni'])),
            ios_sweet=dict(branch=tree['ios_sweet']['branch'], xnu_patch_count=len(names['ios_sweet'])),
            guacamole=dict(branch=tree['guacamole']['branch'], xnu_patch_count=0,
                           note='仓库树 21 项，0 个 xnu patch；内核由 ios-sweet 的 kernel-8796.yml 构建并 --kernel 传入')),
        layer_definitions=dict(
            L0='卡点之前且 nuwa 已实机通过（rootauth / 根挂载门）',
            L1='文件系统 / 存储栈接入层替换：mount 期配置，效果决定 VNOP_READ 落到哪个实现',
            L2='卡点区间内的 mac_vnode_check_read 门（两仓补丁零覆盖）',
            L3='header read 之后、EL0 之前（process_signature / launch constraints / FINAL_WAIT）',
            L4='EL0 / launchd 之后（trust cache 查询、Sandbox、KeyStore）',
            BUILD_FIX='编译期兼容修复，不改运行时控制流或 I/O 语义',
            OUT_OF_SCOPE='与 exec→EL0 无直接关系（显示/触摸/GPU/USB/追踪等）'),
        layer_counts=counts,
        no_patch_covers=NO_COVERAGE,
        no_patch_covers_qualifier=(
            '零个补丁改 vn_rdwr 的控制流或 I/O 语义。0002 是唯一改到 '
            'vfs_vnops.c:964 vn_rdwr_64 源码行的补丁，但仅把 '
            'uio_stackbuf_t uio_buf[UIO_SIZEOF(1)] 换成宏 UIO_STACKBUF(uio_buf, 1)'
            '（新 clang 拒绝 over-aligned 数组），属编译期声明替换。'),
        ufs_driver_comparison=dict(
            question='「换成同步自写块设备」是否指公开仓没有使用自行实现的 UFS 驱动？',
            answer='不是。两侧都使用自写的 UFS 驱动读真实 UFS 硬件，且都是 polled、'
                   '单请求槽、同栈完成；差异在文件系统与存储栈接入层，不在有没有自写驱动。',
            public_side=dict(
                file='bsd/dev/sweet_ufs.c（0028 新增，536 行）',
                evidence='UFSHCI 2.1 寄存器 REG_UTRLBA/UTRLDBR/UTRLRSR；polled SCSI (0x28 READ(10))；'
                         'GPT 分区名 ufsroot=；512B 逻辑扇区 over 4 KiB 块；'
                         'REG_IE=0 关中断；ufs_read_blocks 一次一个命令',
                stack='BSD 裸块设备：bdevsw_add + devfs_make_node("ufsroot0") + '
                      'd_strategy=sweet_ufs_strategy + physio()；buf_biodone(bp) 同栈完成；'
                      '不经过 IOStorageFamily / IOMedia',
                filesystem='内置 HFS+（0026）或 mockfs 虚拟 ramdisk（0021/0024）'),
            nuwa_side=dict(
                file='UniXNU/drivers/NativeUfs/NativeUfs.cpp',
                sha256='3fbd24df8e9517b30d369fe64f4133aa6fb05bd90577d220dab8c58c0f5232f4',
                evidence=':217 "Interrupts stay masked and completion is polled"；'
                         ':798 "One shared host (a single UTP request slot, polled)"；'
                         ':1347 doAsyncReadWrite override；:1410 completion->action(...) 同栈回调',
                stack='IOKit 标准存储栈：NativeUfsBlock : IOBlockStorageDevice → IOMedia → 文件系统',
                filesystem='Apple 原生 APFS（donor prelinked 的 com.apple.filesystems.apfs）'),
            real_difference=[
                '文件系统层：HFS+/mockfs 的 VNOP_READ vs Apple 原生 APFS 的 VNOP_READ（decmpfs 锁、'
                '缓存/UPL、压缩/解压、卷认证路径）',
                '存储栈接入层：BSD 裸 bdevsw 绕过 IOKit vs IOBlockStorageDevice + IOMedia 标准栈',
                '不是「同步 vs 异步」：两侧都是轮询单槽同栈完成',
                '不是「有没有自写 UFS 驱动」：两侧都自写',
            ],
            corrected_wording=(
                '原表述「把 VNOP_READ 后端整体换成了同步自写块设备」把文件系统层与块设备层'
                '压缩成一句，且易被读成「nuwa 有自写 UFS 驱动而公开仓没有」。'
                '准确表述：两仓把根做成 BSD 裸块设备 + 内置 HFS+/mockfs，'
                '使 VNOP_READ 落到不依赖 IOKit 存储栈与 APFS 的实现；'
                'nuwa 走 IOKit 存储栈 + Apple 原生 APFS。')),
        amfi_replacement_scope=dict(
            registered_ops=['mpo_vnode_check_signature (0035/0036)',
                            'mpo_policy_syscall / "Sandbox" (0050)'],
            not_registered=['mpo_vnode_check_read', 'mpo_vnode_check_exec',
                            'mpo_vnode_check_write'],
            consequence='permissive 替身不覆盖 _vn_rdwr 内的 mac_vnode_check_read；'
                        '它不能解释公开仓如何越过当前卡点。'),
        boot_args=dict(
            guacamole_kernel_args=kernel_args,
            nuwa_board_has_kernel_args='kernel_args' in nuwa_board and 'kernel_args = [' in nuwa_board,
            nuwa_board_note='board.toml:20 明写 kernel_args 为 TODO；未实际传入任何兼容开关',
            located_anchor=dict(arg='unentitled_ios_sim_launch',
                                file='bsd/kern/kern_exec.c', lines=[196, 7398, 7401, 7415],
                                conditional='位于 #if XNU_TARGET_OS_OSX (7389–7428)',
                                resolution='条件编译已核实：makedefs/MakeInc.def:69-70 只在 '
                                           'PLATFORM=MacOSX 定义 -DXNU_TARGET_OS_OSX；'
                                           ':86-88 嵌入式平台定义 -DXNU_TARGET_OS_IOS。'
                                           '故 iOS16 内核里该分支与 0042 的 printf 默认不编译，'
                                           '该 boot-arg 对 iOS 内核无效。'),
            arg_resolution=dict(
                launchd_unsecure_cache='launchd 接受其作业缓存、无需 AMFI；用户态 launchd 侧（L4，EL0 之后）。'
                                       '来源：ios-sweet README「不那么明显的启动参数」表',
                wdt='wdt=-1 与 wdt_test=no_user_checkin 禁用硬件看门狗；不作用于 _vn_rdwr',
                rd_ufsroot0='rd=ufsroot0 / ufsrw=1 / rootrw=1 在 userdata 分区挂载可写根（L1）',
                ignition_level='公开仓 README 未解释，本地 xnu-8796 源码无锚点，作用域仍未定'),
            unlocated_anchors=['ignition_level'],
            unlocated_note='ignition_level 作用域仍未定；其余参数已按公开仓 README 与源码锚点定位。'),
        patches=rows,
        full_diff_headers=diffs,
        evidence_boundary=[
            'SpringBoard / userland reached 来自仓库 README 自述，不是本机实机验证。',
            '81 / 116 个补丁按名称分类；仅 %d 个逐字节读全文，其余未逐字节审计。' % len(READ_FULL),
            '0002 已逐字节审计：纯编译期 uio 栈缓冲声明替换（两仓 SHA 相同 '
            '19f7571eb90608ef66f1d8cf9dee5333d4fbbccbfeee9ea244b90cb4a4240727），不改运行时语义。',
            '0042 的条件编译边界已核实（MakeInc.def），iOS 构建默认不编译该分支；'
            '公开仓是否额外定义 -DXNU_TARGET_OS_OSX 未核实，但无证据表明它定义了。',
            '走查顺序已与 donor 反汇编逐调用点配对（见 exec-el0-wiring-evidence.json 的 '
            'donor_bl_callsites / corrected_walkthrough）。',
            'ignition_level 作用域仍未定。',
        ],
        followup_downloads=[
            dict(url='https://raw.githubusercontent.com/pawlickerr/UniXNU-negroni/dev/patches/xnu/0002-new-clang-backport-UIO_STACKBUF.patch',
                 path='references/exec-chain-public-20261105/0002-negroni-UIO_STACKBUF.patch',
                 sha256=sha(REF / '0002-negroni-UIO_STACKBUF.patch')),
            dict(url='https://raw.githubusercontent.com/dipa-studio/ios-sweet/main/xnu/patches/0002-new-clang-backport-UIO_STACKBUF.patch',
                 path='references/exec-chain-public-20261105/0002-sweet-UIO_STACKBUF.patch',
                 sha256=sha(REF / '0002-sweet-UIO_STACKBUF.patch')),
        ],
        inputs=dict(
            repo_tree_sha256=sha(REF / 'repo-tree-manifest.json'),
            patches_index_sha256=sha(REF / 'patches-index.json'),
            guacamole_board_sha256=sha(REF / 'guacamole-board.toml'),
            guacamole_workflow_sha256=sha(REF / 'guacamole-kernel-8796.yml'),
            nuwa_board_sha256=sha(R / 'board.toml'),
            kern_exec_c_sha256=sha(KERN_EXEC)),
    )
    (OUT / 'patch-classification.json').write_text(
        json.dumps(classification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # ---- 接线证据 ----
    images = {'p0': P0_KERNEL, 'check10': CHECK10_KERNEL,
              'check4_clean': CHECK4_KERNEL, 'earlysec': EARLYSEC}
    raws = {k: v.read_bytes() for k, v in images.items()}
    syms = symbols(raws['p0'])
    wanted = ['_proc_exec_switch_task', '_task_clear_return_wait', '_exec_activate_image',
              '___mac_execve', '_load_init_program_at_path', '_process_signature',
              '_vn_rdwr', '_vn_rdwr_64', '_mac_vnode_check_read', '_mac_vnode_check_exec',
              '_exec_mach_imgact', '_thread_deallocate']
    resolved = {n: hex(syms[n]) for n in wanted if n in syms}

    sites = {
        '0xfffffff00769bf90': 'P0 恢复的原生 bl _vn_rdwr',
        '0xfffffff00769bf94': 'P0 恢复的原生 cbnz w0',
        '0xfffffff00769bfe0': 'bl _exec_mach_imgact',
        '0xfffffff00769d10c': 'bl _process_signature',
        '0xfffffff00769d110': 'signature 返回后首指令（P0 已恢复原生 mov x24,x0）',
        '0xfffffff00769d1f4': 'FINAL_WAIT 前 bl _task_clear_return_wait',
        '0xfffffff00769d22c': 'mov w1,#2 (TCRW_CLEAR_FINAL_WAIT)',
        '0xfffffff00769d230': 'P0 保留 coarse_release_before 功能件；原生是 bl _task_clear_return_wait',
        '0xfffffff00769c238': '_proc_exec_switch_task 入口',
        '0xfffffff0073c3864': '公共返回入口（P0 是 el0 大阶段观测 hook）',
        '0xfffffff0073c3994': 'ERET',
        '0xfffffff0084db290': '旧 239 自环门（carrier 退役区）',
        '0xfffffff0084d9be4': 'probe61 遗留 cbz w0 桥接',
    }
    site_rows = []
    for va_s, note in sites.items():
        va = int(va_s, 16)
        words = {}
        for k, raw in raws.items():
            seg, off, h = at(raw, va, 16)
            words[k] = dict(segment=seg, file_offset=off, hex=h)
        seg, off, h = at(raws['p0'], va, 4)
        decoded = None
        if h:
            w = int.from_bytes(bytes.fromhex(h), 'little')
            top = (w >> 24) & 0xff
            if w == 0xd69f03e0:
                decoded = dict(kind='eret')
            elif w == 0x14000000:
                decoded = dict(kind='self-loop b .', target=va_s)
            elif w & 0x7c000000 == 0x14000000:
                decoded = dict(kind='bl' if w & 0x80000000 else 'b',
                               target=hex(branch(w, va)))
            elif top in (0x34, 0x35, 0xb4, 0xb5):
                imm = (w >> 5) & 0x7ffff
                if imm & (1 << 18):
                    imm -= (1 << 19)
                decoded = dict(kind='cbnz' if top in (0x35, 0xb5) else 'cbz',
                               target=hex(va + 4 * imm))
        site_rows.append(dict(address=va_s, note=note, words=words, p0_decoded=decoded))

    wiring = dict(
        schema='Nuwa.ExecEl0WiringEvidence.v1', date='2026-11-05',
        purpose='补齐 reports/native-restore-20261105/exec-el0-wiring.md 的四项验收缺口',
        macho_symbols=resolved,
        symbol_source='donor P0 kernel.macho LC_SYMTAB (268678 nlist_64 项)',
        gaps_resolved=[
            dict(gap='proc_exec_switch_task 地址未找到',
                 result='已找到 _proc_exec_switch_task = 0xfffffff00769c238',
                 evidence='LC_SYMTAB；入口字 fc6fbaa9 在 P0/CHECK10/CHECK4clean/earlysec 逐字节相同'),
            dict(gap='0x3c3994 处 ERET 机器码未找到',
                 result='0x3c3994 = e0039fd6，little-endian 即 0xd69f03e0 = ERET',
                 evidence='四个镜像该地址 16 字节逐字节相同；后续 df3f03d5 / 1f2003d5 为填充'),
            dict(gap='0x84db290 自环是否物理擦除未确证',
                 result='未物理擦除：00000014 = b . 自环仍在 __NUWA_PROBE file_offset 58671760',
                 evidence='CHECK4clean / CHECK10 / P0 三份内核该地址逐字节相同；earlysec 无 __NUWA_PROBE 段',
                 clarification='CHECK4 撤除的是调用点（改调真实 _task_clear_return_wait），'
                              '不是擦除退役区字节；按 CHECK4 纪律不可达字节保留'),
            dict(gap='kern_exec.c 本地副本未抓取',
                 result='已找到只读资料库副本（上一轮更正）',
                 evidence=str(KERN_EXEC), sha256=sha(KERN_EXEC)),
        ],
        corrected_walkthrough=[
            dict(step=1, desc='exec_activate_image (0x769bb5c) 参数块 w6=8 (IO_NODELOCKED)',
                 source='kern_exec.c:2210-2213'),
            dict(step=2, desc='0x769bf90 bl _vn_rdwr (0x7466988)；x30 由硬件写 0x769bf94',
                 source='P0 恢复后的原生指令'),
            dict(step=3, desc='0x769bf94 cbnz w0,0x769c144；成功落 0x769bf98 的 resid 检查',
                 source='机器码 800d0035 解出'),
            dict(step=4, desc='0x769bfe0 bl _exec_mach_imgact (0x76984c4)，在 exec_activate_image 内',
                 source='donor BL 扫描，全内核唯一调用点'),
            dict(step=5, desc='回到 ___mac_execve 后段：0x769d0d8 bl proc_exec_switch_task (0x769c238)',
                 source='donor BL 扫描 + kern_exec.c:5033；**先于 process_signature**'),
            dict(step=6, desc='0x769d10c bl process_signature (0x769c734)；0x769d110 mov x24,x0',
                 source='8afdff97 解出；0x769d110 是 11 个恢复点之一，P0 已恢复原生'),
            dict(step=7, desc='0x769d1f0 mov w1,#1 + 0x769d1f4 bl task_clear_return_wait '
                              '= INITIAL_WAIT',
                 source='task.h:579 TCRW_CLEAR_INITIAL_WAIT=0x1；kern_exec.c:5181'),
            dict(step=8, desc='0x769d22c mov w1,#2 + 0x769d230 原生 bl task_clear_return_wait '
                              '= FINAL_WAIT；P0 在此保留 coarse_release_before 功能件，'
                              '释放前发布 ip_new_thread 并重放该 BL',
                 source='task.h:580 TCRW_CLEAR_FINAL_WAIT=0x2；kern_exec.c:5202 / '
                        'build-p0-native-restore-20261105.py 三分类清单'),
            dict(step=9, desc='0x769d238 bl _thread_deallocate (0x72b192c)',
                 source='donor 反汇编'),
            dict(step=10, desc='0x3c3864 公共返回入口（P0 为 el0 大阶段 hook b；原生 mov x19,x3）',
                 source='10 个 coarse milestone 之一'),
            dict(step=11, desc='0x3c3994 ERET = e0039fd6',
                 source='本轮机器码解码'),
        ],
        walkthrough_correction=dict(
            previous_order='上一轮把 process_signature 放在 proc_exec_switch_task 之前，'
                           '并把 0x769d1f4 归入 FINAL_WAIT 段',
            corrected='donor 反汇编与 kern_exec.c 两条路径（:4086→:4458、:5033→:5050）'
                      '都显示 proc_exec_switch_task 先于 process_signature；'
                      '0x769d1f4 的 w1=1 是 INITIAL_WAIT，FINAL_WAIT 是 0x769d230 的 w1=2',
            evidence='全内核 BL 调用点扫描 + 0x769d0c0..0x769d240 逐字解码'),
        donor_bl_callsites={
            '_proc_exec_switch_task': ['0xfffffff00769a934', '0xfffffff00769d0d8'],
            '_process_signature': ['0xfffffff00769afd8', '0xfffffff00769d10c'],
            '_task_clear_return_wait': ['0xfffffff00769acb4', '0xfffffff00769b240',
                                       '0xfffffff00769d1f4', '0xfffffff0076a7d64'],
            '_exec_mach_imgact': ['0xfffffff00769bfe0'],
        },
        wait_flags=dict(initial='0x1 (task.h:579)', final='0x2 (task.h:580)',
                        note='0x769d230 在 P0 里是 b coarse_release_before，不再是 BL，'
                             '故不出现在 BL 扫描结果中'),
        real_device_status=dict(
            FB0D='各轮 FFFFFFFF（原生 exec 结果从未实机验收）',
            FB0E='各轮 FFFFFFFF（限定新线程 EL0 交接从未实机验收）',
            conclusion='走查第 4–11 步全部为静态接线，无实机命中证据'),
        sites=site_rows,
        inputs={k: sha(v) for k, v in images.items()},
        limitations=[
            '符号地址来自静态 Mach-O 符号表，未做运行时断点或 trace 确认。',
            '调用顺序已与 donor 反汇编逐调用点配对（corrected_walkthrough / donor_bl_callsites），'
            '但函数边界（哪个 BL 属于哪个函数）仅按地址区间推定，未逐个符号化。',
            'ignition_level 作用域仍未定；公开仓是否额外定义 -DXNU_TARGET_OS_OSX 未核实。',
            'P0 尚未上机；本文件全部是静态证据，不构成实机阶段跨越。',
        ])
    (OUT / 'exec-el0-wiring-evidence.json').write_text(
        json.dumps(wiring, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('patch rows', len(rows), 'layer counts', counts)
    print('full-diff patches', len(READ_FULL), '| guacamole kernel_args', len(kernel_args))
    print('symbols resolved', len(resolved), 'of', len(wanted))
    print('gaps resolved', len(wiring['gaps_resolved']))
    for s in site_rows:
        if s['p0_decoded']:
            print(' ', s['address'], s['p0_decoded'])
    print('written', OUT.relative_to(R))


if __name__ == '__main__':
    main()
