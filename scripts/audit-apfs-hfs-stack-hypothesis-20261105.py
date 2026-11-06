"""对比 APFS / HFS+ 与两种存储栈接入层，评估「卡点就在这两处实现」的证据强度。

离线只读。输出 reports/apfs-vs-hfs-stack-20261105/evidence.json。
纪律：逐门实机证据与静态事实分列；不把阴性证据写成「未发生」；不虚构确定根因。
"""
import hashlib
import json
import re
import struct
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/apfs-vs-hfs-stack-20261105'
REF = R / 'references/exec-chain-public-20261105'
REF_ROOT = R / 'references/public-root-chain-20261105'
UPSTREAM = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeUfs/NativeUfs.cpp')

SOURCES = {
    'check5_disassembly': R / 'reports/ufs-check-5-r1/trial/read-path-disassembly.txt',
    'check5_result': R / 'docs/operations/2026-11-03-check5-result-and-main-validation.md',
    'mac_trust_verdict': R / 'reports/mac-trust-chain-verdict-20261105/README.md',
    'donor_bindings': R / 'reports/donor-compat/current-kernel-bindings.json',
    'p0_kernel': R / 'out/p0-native-restore-20261105-r1/kernel.macho',
    'p0_qualification': R / 'reports/p0-native-restore-20261105-r1/qualification.json',
    'sweet_0028': REF_ROOT / '0028-sweet-ufs-root-device.patch',
    'sweet_0022': REF_ROOT / '0022-sweet-ramdisk-root-without-iomedia.patch',
    'sweet_0026': REF / '0026-sweet-builtin-hfs.patch',
    'sweet_0031': REF / '0031-sweet-read-write-root.patch',
    'sweet_readme': REF_ROOT / 'ios-sweet-README.md',
    'native_ufs_cpp': UPSTREAM,
    'read_boundary_sites': R / 'scripts/read_boundary_sites.py',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def anchor(path, needle):
    for i, line in enumerate(Path(path).read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        if needle in line:
            return dict(line=i, text=line.strip()[:220])
    return None


def macho_symbols(raw, keywords):
    offs, sym = 32, None
    for _ in range(struct.unpack_from('<I', raw, 16)[0]):
        cmd, sz = struct.unpack_from('<II', raw, offs)
        if cmd == 0x2:
            sym = struct.unpack_from('<IIII', raw, offs + 8)
        offs += sz
    if not sym:
        return {}
    so, ns, sto, sts = sym
    out = {}
    for i in range(ns):
        sx, nt, nse, desc, val = struct.unpack_from('<IBBHQ', raw, so + i * 16)
        if not sx:
            continue
        end = raw.find(b'\0', sto + sx)
        name = raw[sto + sx:end].decode('utf-8', 'replace')
        for kw in keywords:
            if kw.lower() in name.lower():
                out.setdefault(kw, []).append(dict(symbol=name, address=hex(val)))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    kernel = (R / SOURCES['p0_kernel']).read_bytes()
    syms = macho_symbols(kernel, ['decmpfs_', 'cluster_read', 'upl_', 'apfs'])
    bindings = json.loads((R / SOURCES['donor_bindings']).read_text(encoding='utf-8'))

    result = dict(
        schema='Nuwa.ApfsHfsStackHypothesis.v1', date='2026-11-05',
        purpose='回答 APFS 与 HFS+、两种存储栈的差异，并评估「卡点就在这两处实现」的证据强度',
        question3_verdict=dict(
            answer='有可能，且是当前最值得验证的假设之一，但现有证据不足以定为根因。',
            precise_form='更可能是「nuwa 的 APFS 后端接线 / VNOP_READ 完成链」问题，'
                         '而不是「Apple 原生 APFS 文件系统实现本身有 bug」。',
            confidence='中等偏低：CHECK10 阴性把区间收窄到 _vn_rdwr 内部，'
                       '但该区间还有 len<0 早退与自建改道链两种未排除解释。',
            status='未实机证伪，也未实机证实'),
        gate_by_gate=[
            dict(gate='vfs_mountroot / 根挂载', evidence='KMAIN-4、CHECK5 FB09=0 / FB0A=0',
                 state='已实机通过', note='APFS mount、卷识别、IOMedia 发布、基础块读已工作过；'
                                          '挂载本身需要读 APFS 超级块与 B-tree'),
            dict(gate='FSIOC_KERNEL_ROOTAUTH', evidence='FB04=50 (EAUTH) / FB05=1 owner 放行',
                 state='已实机通过'),
            dict(gate='/sbin/launchd namei', evidence='CHECK3/5 FB13=0', state='已实机通过'),
            dict(gate='mac_vnode_check_exec', evidence='CHECK5 FB12=A0000005', state='已实机通过'),
            dict(gate='_vn_rdwr 入口 / MAC-read 分派', evidence='CHECK5 A5 到达 vn_rdwr 调用前；'
                                                          'CHECK10 FB15/16/17 368 帧全空',
                 state='未区分：CHECK5 明写「不把 A5 当成 VNOP_READ、APFS 或 UFS 已进入」'),
            dict(gate='mac_vnode_check_read (0x7466ACC)', evidence='CHECK10 epilogue 空白',
                 state='未区分；但 MAC 返回错误码会跳 0x7466B24 汇合点并正常返回，'
                       'FB15 应出现，故纯 errno 拒绝不是首要解释'),
            dict(gate='VNOP_READ (0x7466B20) / APFS 后端', evidence='CHECK10 未到达 0x74669C8 epilogue',
                 state='未区分；CHECK5 明写「APFS/decmpfs 锁、缓存/UPL、解压及后端 I/O '
                       '目前仍无法从本轮画面区分」'),
            dict(gate='process_signature / FINAL_WAIT / EL0 / ERET',
                 evidence='FB0D / FB0E 各轮 FFFFFFFF', state='从未实机验收'),
        ],
        structural_argument=dict(
            site='0xfffffff007466b20 bl _VNOP_READ (0x7466c628)，汇合点 0xfffffff007466b24 mov x20,x0',
            fact='0x7466ad0 cbnz w0,0x7466b24：MAC-read 返回错误码会直接跳到 VNOP_READ 之后的'
                 '共同汇合点，vn_rdwr_64 仍走 epilogue 返回',
            consequence='CHECK10 epilogue 空白不能由「MAC 策略返回 errno」解释；'
                        '更支持 VNOP_READ 内部未返回，或 _vn_rdwr 入口 tbnz w3,#31 的 len<0 '
                        '早退（mov w0,#22; ret）绕过 epilogue',
            caveat='CHECK5 记录参数 rw=0, offset=0, segflg=2, ioflg=8，len<0 可能性低，'
                   '但无设备级反证'),
        filesystem_difference=[
            dict(dim='卷模型', apfs='卷组 OS/SystemOS/Data/Preboot/cryptex、快照、sealed volume、共享 Data 卷',
                 hfs='单一 case-sensitive journaled HFS+ 卷；mkiosroot.sh 把 OS + 两个 cryptex 拍平合成',
                 evidence='ios-sweet-README.md:18/89'),
            dict(dim='根认证', apfs='FSIOC_KERNEL_ROOTAUTH 封印卷认证，依赖 Image4/AMFI/CoreTrust',
                 hfs='无封印；0029 把 autherr 从 panic 改为 printf',
                 evidence='0029-sweet-unsealed-root-volume.patch'),
            dict(dim='读链中间层', apfs='vnode → decmpfs 透明压缩（AppleFSCompressionTypeZlib）→ '
                                       'cluster/UPL/缓存 → APFS vnop → 块设备',
                 hfs='vnode → HFS vnop → d_strategy 同步块读；无 decmpfs / UPL / 卷重定向层',
                 evidence='donor LC_SYMTAB 含 _decmpfs_* / _cluster_read* / _upl_*；'
                          '0002 补丁改 decmpfs.c:515；0026 内置 HFS'),
            dict(dim='压缩/加密/快照', apfs='支持透明压缩、文件加密、快照重定向',
                 hfs='普通 HFS+ 文件，不做透明解压', evidence='内核符号 + HFS 实现'),
            dict(dim='依赖形态', apfs='Apple 闭源 com.apple.filesystems.apfs kext（donor prelinked）'
                                     '+ IOStorageFamily + CoreTrust/Image4',
                 hfs='源码内编译 bsd/sweet_hfs/，无闭源 kext 依赖', evidence='0026 / donor roots'),
            dict(dim='根镜像', apfs='原始 iPadOS OS/SystemOS DMG（GPT+APFS）字节不变',
                 hfs='由 IPSW 的 OS.dmg/SystemOS.dmg/AppOS.dmg 重新合成新 HFS+ 镜像',
                 evidence='build-userdata-root-image.py:3-9 / ios-sweet-README.md:81-83'),
        ],
        storage_stack_difference=[
            dict(dim='注册方式', bsd='bdevsw_add(-1,&bdevsw) + devfs_make_node("ufsroot0")；'
                                    'IOFindBSDRoot 直接返回 dev_t',
                 iokit='IOBlockStorageDevice 派生类 ::start() → IOBlockStorageDriver 发布 IOMedia → '
                       'GPT/分区方案 → 文件系统',
                 evidence='0028:548-557 / NativeUfs.cpp:1103,1445'),
            dict(dim='读调用与完成', bsd='physio(strategy,...,uio) → d_strategy(buf_t) → '
                                       'buf_biodone(bp) 同栈同步完成',
                 iokit='VNOP_READ → IOStorageRequest → doAsyncReadWrite(..., IOStorageCompletion*) '
                       '→ completion->action 回调；中间有锁/队列/DMA/SMMU/电源',
                 evidence='0028:350/465/474 / NativeUfs.cpp:1347/1410'),
            dict(dim='依赖', bsd='不经过 IOService 匹配、IOMedia、IOStorageFamily',
                 iokit='需要 IOStorageFamily 与 IOMedia 类',
                 evidence='0022 去掉 assert(iomediaClass)，注释「SWEET has no IOStorageFamily」'),
            dict(dim='失败模式', bsd='读错误由 buf_seterror 同栈返回；不易「挂住」',
                 iokit='完成事件丢失、锁未释放、DMA 未完成或 IOMedia 未发布，'
                       '调用者可能无限等待（与「epilogue 从未到达」形态吻合）',
                 evidence='工程推断，非实机结论'),
        ],
        hypothesis_ranking=[
            dict(rank=1, hypothesis='0x7466B20 _VNOP_READ 内部（APFS decmpfs / UPL / cluster / '
                                    'IOKit 异步完成事件 / 自写 NativeUfs 回调）未返回',
                 support=['CHECK10 368 帧 FB15/16/17 全空，epilogue 从未到达',
                          'MAC errno 会走 0x7466B24 汇合点并正常返回，故不解释空白',
                          'CHECK5 明写 APFS/decmpfs 锁、缓存/UPL、解压及后端 I/O 无法区分',
                          'donor 内核确有 _decmpfs_* / _cluster_read* / _upl_* 符号',
                          'ios-sweet 绕过整条 APFS/IOKit 栈后跑到 SpringBoard（仓库自述）'],
                 against=['sheng 用同样的 APFS + IOKit 栈也跑到 SpringBoard（仓库自述）',
                          'nuwa 实机 vfs_mountroot=0，说明 APFS mount 与基础块读通路已工作',
                          'donor APFS 是 Apple 原厂 prelinked 二进制，nuwa 补丁未改其字节']),
            dict(rank=2, hypothesis='_vn_rdwr 入口 len<0 早退绕过 epilogue（与文件系统/存储栈无关）',
                 support=['CHECK10 阴性文档已列为两种可能之一'],
                 against=['CHECK5 参数 rw=0, offset=0, segflg=2, ioflg=8 显示 len 正常',
                          '但无设备级反证']),
            dict(rank=3, hypothesis='nuwa 自建改道链 0x769BF90/94 造成调用/返回 ABI 异常',
                 support=['nuwa 独有，公开仓完全没有', 'P0 正是为检验它而恢复'],
                 against=['CHECK5 7 例机器码模型未发现参数或返回值污染（ABI 卫生静态通过）']),
            dict(rank=4, hypothesis='Apple 原生 APFS 文件系统实现本身有 bug',
                 support=['donor 绑定审计有 1 条未解析跨模块引用（见 binding_finding）'],
                 against=['sheng 用同栈跑到 SpringBoard',
                          'donor APFS 与 earlysec 原生基线在关键调用点逐字节相同',
                          '根挂载已实机成功'],
                 note='这是最弱的一档，几乎可以排除「APFS 全局损坏」'),
        ],
        binding_finding=dict(
            file='reports/donor-compat/current-kernel-bindings.json',
            failure_count=bindings['failure_count'], device_verified=bindings['device_verified'],
            detail=bindings['failures'][0] if bindings['failures'] else None,
            interpretation='静态跨模块引用审计发现 apfs 模块 0x6eac110 调用 '
                           '_vfs_getvfs_with_vfsops 有 0 个候选地址；属绑定审计缺口，'
                           '不是运行时故障证据，且根挂载已实机成功，故不列为阻断项'),
        donor_symbols={k: v[:5] for k, v in syms.items()},
        minimal_discriminating_observation=dict(
            limitation='P0 的 FB07（0x7466AD0，w0 = MAC-read 返回码）只能区分 '
                       'MAC 放行 / 拒绝 / 未到达分派点，不能区分「VNOP_READ 已进入后卡住」。',
            design='在 0x7466B10..0x7466B20（仅 UIO_READ 路径经过）画入口标记，'
                   '在 0x7466B24 汇合点画 w0 返回值 + 到达标记，做入口/返回配对。',
            warning='CHECK5 文档明确：MAC 失败可直接跳到 VNOP_READ 之后的共同汇合点，'
                    '不能只在返回地址打点就宣称 VNOP_READ 执行过；必须配对。',
            reusable='scripts/read_boundary_sites.py 已有 CALLS 的 pc / pc+4 成对设计与 '
                     'site==pc+4 时 str x0 记录返回值，可直接复用，不必新写。',
            discipline='按 AGENTS §6：新观测不得同时引入新挂点与首次使用的字段行号；'
                       '复用已验证可见的空白行位；每个字段列出全部写入源；'
                       '改控制流/加观测需用户单独批准。'),
        fb07_tristate=[
            dict(value='00000000', verdict='MAC-read 放行，进入 0x7466AD4 之后的 VNOP_READ 路径；'
                                           '仍需入口/返回配对才能判定是否卡在后端'),
            dict(value='非零', verdict='MAC 拒绝，走 0x7466B24 汇合点并应正常返回；'
                                       '若 epilogue 仍空白则与结构性推理矛盾，需重查'),
            dict(value='行空白', verdict='未到达 0x7466AD0 分派点（含 len<0 早退），'
                                         '与 APFS/存储栈无关'),
        ],
        inputs={k: dict(path=str(v), sha256=sha(v)) for k, v in SOURCES.items()},
        anchors=dict(
            vnop_read_call=anchor(SOURCES['check5_disassembly'], '7466b20 c2160094'),
            join_point=anchor(SOURCES['check5_disassembly'], '7466b24 f40300aa'),
            mac_read_call=anchor(SOURCES['check5_disassembly'], '7466acc a4c01294'),
            check5_caveat=anchor(SOURCES['check5_result'], 'APFS/decmpfs'),
            sweet_hfs=anchor(SOURCES['sweet_readme'], 'journaled HFS+ volume')),
        limitations=[
            'CHECK10 空白须同时满足通道有效、行位可见、挂点覆盖所有返回路径；'
            'len<0 早退路径绕过 epilogue，故结论只能写「未到达正常 epilogue」。',
            'sheng / ios-sweet 的 SpringBoard 状态是仓库自述，不是本机实机验证。',
            'VNOP_READ 内部失败模式为工程推断，无实机 trace 或运行时证据。',
            '本轮未改内核、未构建、未上机、未提交 git。',
        ])
    (OUT / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print('verdict:', result['question3_verdict']['answer'])
    print('gates', len(result['gate_by_gate']), '| hypotheses', len(result['hypothesis_ranking']))
    print('donor symbol groups', {k: len(v) for k, v in syms.items()})
    print('written', (OUT / 'evidence.json').relative_to(R))


if __name__ == '__main__':
    main()
