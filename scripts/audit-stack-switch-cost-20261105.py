"""更换文件系统 / 存储栈接入层的成本评估（2026-11-05，离线只读）。

回答「更换文件系统和存储栈接入层的成本怎么样」。
从固定输入重算：nuwa 二进制形态、公开仓 L1 层补丁规模、认证根实测状态、
sheng 同栈反证、已实机通过的 5 门、授权边界；输出 evidence.json。

不操作设备、不改内核、不构建、不写分区、不提交。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/stack-switch-cost-20261105'
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    'apfs_hfs': R / 'reports/apfs-vs-hfs-stack-20261105/README.md',
    'sheng': R / 'reports/sheng-storage-stack-20261105/README.md',
    'deep': R / 'reports/public-exec-chain-deep-20261105/README.md',
    'patch_classification': R / 'reports/public-exec-chain-deep-20261105/patch-classification.json',
    'p0_readme': R / 'reports/p0-native-restore-20261105-r1/README.md',
    'r2_readme': R / 'reports/p0-vnop-pair-20261105-r2/README.md',
    'r2_qualification': R / 'reports/p0-vnop-pair-20261105-r2/qualification.json',
    'readback': R / 'reports/ufs-root-readback-20261105/readback.json',
    'root_route': R / 'docs/operations/2026-11-01-ufs-root-recovery-route.md',
    'decisions': R / 'docs/DECISIONS.md',
    'agents': R / 'AGENTS.md',
    'board': R / 'board.toml',
    'build_r2': R / 'scripts/build-p0-vnop-pair-20261105.py',
    'build_c4': R / 'scripts/build-ufs-check4-r1.py',
    'hfs_patch': R / 'references/exec-chain-public-20261105/0026-sweet-builtin-hfs.patch',
    'ufs_patch': R / 'references/public-root-chain-20261105/0028-sweet-ufs-root-device.patch',
    'no_iomedia': R / 'references/public-root-chain-20261105/0022-sweet-ramdisk-root-without-iomedia.patch',
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def text(key: str) -> str:
    return FILES[key].read_text(encoding='utf-8', errors='replace')


def inputs() -> dict:
    return {
        k: dict(path=str(p.relative_to(R)).replace('\\', '/'),
                sha256=sha(p), bytes=p.stat().st_size)
        for k, p in FILES.items()
    }


def shape() -> dict:
    agents = text('agents')
    sheng = text('sheng')
    assert 'kernelcache 提取 + donor prelinked 二进制 patch' in agents, \
        '二进制形态纪律原文缺失'
    assert 'kernelcache 提取 + donor prelinked 二进制 patch' in sheng, \
        'nuwa 形态列缺失'
    assert 'XNU 源码自编译' in sheng, '公开仓形态列缺失'

    # 本仓没有 XNU 源码树：只编译 cave 汇编
    build = text('build_c4')
    assert 'def compile_observer' in build and 'SOURCE.read_text()' in build
    has_master = any((R / p).exists() for p in
                     ('config/MASTER', 'bsd/conf/files', 'bsd/conf/Makefile.template'))
    assert not has_master, '本仓出现 XNU 源码构建配置，形态判断需复核'

    return dict(
        nuwa='kernelcache 提取 + donor prelinked 二进制 patch',
        public_repos='XNU 源码自编译 + 81 / 116 个补丁',
        sheng='donor prelinked (XnuPrelink) + XNU 源码补丁',
        nuwa_build_chain='只编译 cave 汇编并 patch 到 donor 内核；'
                         '本仓无 config/MASTER、bsd/conf/files、Makefile.template，'
                         '不具备内核源码构建链',
        donor_fs='Apple 闭源 com.apple.filesystems.apfs（在 prelink 里，无源码）',
        donor_storage='IOStorageFamily / IOMedia / IOBlockStorageDevice（prelink）',
        consequence='公开仓换栈补丁全部是源码级（改 config/MASTER、bsd/conf/files、'
                    '新增 .c 文件），在二进制形态上无法直接套用；'
                    'nuwa 要换栈必须先切换到源码构建形态',
    )


def prior_ci() -> dict:
    d = text('decisions')
    hit = ('第十轮39738601892已完成完整源配方与链接' in d and
           '未解析符号0' in d)
    boundary = ('WSL本机、完整driver/RPC ABI、donor预链接与nuwa可启动性仍未验证' in d)
    assert hit and boundary, ('源 CI 记录或边界原文缺失', hit, boundary)
    return dict(
        exists=True,
        run='39738601892（2026-10-22，D-008/D-010/D-011 补充）',
        achieved='云端 macOS 工具链真实源配方与完整链接；'
                 '普通 ARM64 / LC_SOURCE_VERSION 8796.141.3 / Darwin 22.6.0；'
                 '未解析符号 0；两项 NativePrelink 标记 1',
        not_achieved=['WSL 本机', '完整 driver / RPC ABI', 'donor 预链接',
                      'nuwa 可启动性', '正式 nuwa 配置'],
        explicit_boundary='不切 feed、不改 board、不生成固件/诊断镜像、'
                          '不改变任何 _verified；正式 nuwa 配置尚未建立',
        meaning='这不是「从零开始」，但也不等于「已有可启动的换栈基座」。'
                '它是一条独立的源内核构建证据，未与 donor prelinked kext、'
                '认证根、板级 ADT 或实机启动链打通。',
    )


def patch_scale() -> dict:
    hfs = text('hfs_patch')
    ufs = text('ufs_patch')
    cls = json.loads(text('patch_classification'))
    layers = cls['layer_counts']
    assert layers['L1'] == 22, ('L1 层数量变化', layers['L1'])

    hfs_sources = len(re.findall(r'^\+bsd/sweet_hfs/', hfs, re.M))
    hfs_files = len(re.findall(r'^diff --git ', hfs, re.M))
    ufs_lines = ufs.count('\n')
    ufs_files = len(re.findall(r'^diff --git ', ufs, re.M))
    assert hfs_sources >= 40, ('HFS 源文件计数异常', hfs_sources)

    return dict(
        L1_patch_count=layers['L1'],
        L1_definition=cls['layer_definitions']['L1'],
        hfs_patch_files=hfs_files,
        hfs_source_files_introduced=hfs_sources,
        hfs_note='0026 引入完整 Apple OSS HFS+ 源码树（40+ 个 .c），'
                 '并改 config/MASTER、MASTER.arm64.sweet、bsd/conf/files、'
                 'Makefile.template、bsd_init.c、mockfs_vfsops.c 等构建配置',
        ufs_patch_lines=ufs_lines,
        ufs_patch_files=ufs_files,
        ufs_note='0028 新增 bsd/dev/sweet_ufs.c（536 行）+ 改 IOKitBSDInit.cpp 的 '
                 'IOFindBSDRoot / bdevsw_add / devfs_make_node / physio / buf_biodone',
        no_iomedia_patch='0022 去掉 assert(iomediaClass)，注释明写 '
                         '「SWEET has no IOStorageFamily」',
        scale_verdict='公开仓 22 个 L1 补丁 = 新增一整套文件系统源码 + '
                      '新增一整套 BSD 裸块设备后端 + 改挂载配置。'
                      '这是子系统级替换，不是候选级 patch。',
    )


def cost_layers() -> list[dict]:
    return [
        dict(
            layer='1 · 文件系统层（APFS → HFS+/mockfs）',
            magnitude='极高',
            why='donor 的 apfs 是闭源 prelinked kext，无源码可改；'
                '必须引入并编译一套完整 HFS+ 实现（公开仓 0026 引入 40+ 源文件），'
                '再让 VFS 在 mount 期选它而不是 apfs',
            reusable=['公开仓 0026 的源码清单与构建配置改法（作为参考，不能照搬 ABI）'],
            must_write=['整套 HFS+ 源码与 8796.141.3 内核 ABI 适配',
                        'VFS 挂载点选择 / vfsops 注册',
                        'decmpfs / firmlinks / union 等依赖层的去留决策'],
            irreversible='切换后 FSIOC_KERNEL_ROOTAUTH 封印卷认证链前提消失；'
                         'Apple 原生认证模型被改',
        ),
        dict(
            layer='2 · 存储栈接入层（IOKit → BSD 裸 bdevsw）',
            magnitude='极高',
            why='现有 NativeUfs 继承 IOBlockStorageDevice、发布 IOMedia、'
                '经 IOStorageFamily 异步完成；换裸栈要新增 bdevsw_add / '
                'devfs_make_node / d_strategy / physio / buf_biodone 一整套，'
                '并改 IOFindBSDRoot 直接返回 dev_t',
            reusable=['自写 UFS 驱动的底层 UFSHCI / polled SCSI 逻辑'
                      '（两侧同为 polled、单槽、同栈完成）',
                      '7 个已链接的 NativeUfs 对象（部分可复用）'],
            must_write=['BSD 裸块设备后端与 strategy 例程',
                        '根设备发现 / devfs 节点 / 512B 逻辑扇区适配',
                        '与现有 IOKit 栈共存或整体替换的切换逻辑'],
            irreversible='6 个功能件里的 BSD root selector / mapped end / '
                         'validate_increment / install_increment / map_permissions '
                         '全部要重做；已实机通过的 root_wait / root_return / '
                         'mount_return 观测链失效',
        ),
        dict(
            layer='3 · 认证根与分区',
            magnitude='高（含授权硬门槛）',
            why='当前根是字节不变的原始 iPadOS OS/SystemOS DMG（GPT+APFS），'
                '8,445,681,664 B 写入 userdata 前缀，15:05 刚实测四项 SHA 全一致；'
                'HFS+ 路线要求由 IPSW 重新合成单一 HFS+ 卷',
            reusable=['已实测的分区几何与读回方法（dd bs=4096 | sha256sum）'],
            must_write=['重新合成根镜像的完整脚本与验证',
                        '全量重写 userdata 前缀'],
            irreversible='**分区写入**，AGENTS §4 明写「放弃旧数据也不等于授权'
                         '格式化、分区写入或改槽」，需用户单独明确批准；'
                         '且会作废刚取得的认证根完好证据',
        ),
        dict(
            layer='4 · 构建链 / ABI / 观测',
            magnitude='高',
            why='现有 11 个真原生恢复点、10 个大阶段、6 个功能件、'
                'FB03/FB06/FB07 全部绑定到 donor 二进制的绝对地址；'
                '换源码内核后所有地址漂移',
            reusable=['P0/r2 的构建脚本框架、资格化与回归框架（需重绑地址）',
                      '云端源 CI 的完整链接配方（run 39738601892）'],
            must_write=['donor prelinked 闭源 kext 与新源内核的合并/重定位',
                        '全部挂点、cave、字段语义表、ADT/nonce 绑定重做',
                        '78 项回归与独立重建资格重建'],
            irreversible='离线合格、未消费的 r2 及 P0 对照序列全部作废；'
                         '已实机通过的 5 门需重新验收',
        ),
        dict(
            layer='5 · 验证与归因',
            magnitude='高',
            why='换栈一次改掉文件系统、存储栈、根镜像、认证模型四组变量；'
                '若启动推进，无法归因是哪一组起作用；若不推进，也无法区分'
                '是换栈无效还是新栈自身的问题',
            reusable=['单次上机的判读纪律与四态矩阵（需重写）'],
            must_write=['多轮上机与逐门重新验收', '新栈自身的观测点'],
            irreversible='破坏单一变量对照；当前「VNOP_READ 后端是否卡住」'
                         '这一未决问题会与新变量混杂，根因更难定位',
        ),
    ]


def counter_evidence() -> dict:
    s = text('sheng')
    a = text('apfs_hfs')
    assert 'sheng 同样要过 APFS 的 VNOP_READ' in s
    assert '几乎可以排除' in a
    return dict(
        sheng_same_stack='官方固定版 sheng 用同样的 Apple 原生 APFS + '
                         'IOBlockStorageDevice→IOMedia→IOStorageFamily，'
                         '仓库自述跑到 SpringBoard',
        nuwa_mount_passed='nuwa 实机 FB09=0 / FB0A=0：APFS 挂载、卷识别、'
                          'IOMedia 发布、基础块读都工作过',
        donor_unmodified='donor APFS 是 Apple 原厂 prelinked 二进制，'
                         'nuwa 的补丁没改它的字节；关键 MAC/读调用点与 earlysec 逐字节相同',
        verdict='「这个栈本身走不通」缺少证据；换栈是在未证实根因的前提下，'
                '先拆掉一整片已实机通过的工作面',
        caveat='sheng 跑到 SpringBoard 是仓库自述，不是本机实机验证；'
               'nuwa 的 VNOP_READ 完成链仍未被实机区分',
    )


def three_cases() -> list[dict]:
    return [
        dict(
            condition='r2 上机：FB03 有 / FB06 空 / FB07=0（VNOP_READ 已进入未返回）',
            cost_benefit='换栈这时才第一次成为可讨论的候选，但仍不是首选',
            recommended='先在现有栈内做下一层配对观测：APFS vnop 入口、'
                        'IOStorageCompletion 回调、gHost.lock 生命周期、'
                        'decmpfs / cluster·UPL 边界',
            why='成本从「换四个子系统」降到「加几个挂点」，且保留单一变量；'
                '只有确认具体哪一层不返回，才能判断换栈是否对症'),
        dict(
            condition='r2 上机：FB03 / FB06 都有（read 已返回）',
            cost_benefit='换栈成本 100% 浪费',
            recommended='卡点下移到 process_signature → FINAL_WAIT → '
                        'proc_exec_switch_task → ERET 接线',
            why='存储读链已通，与文件系统/存储栈无关'),
        dict(
            condition='r2 上机：FB07 非零，或双空白',
            cost_benefit='换栈成本 100% 浪费',
            recommended='FB07 非零 → 按原生 AMFI errno 定位（两仓 L2 零覆盖，无补丁可抄）；'
                        '双空白 → 按 AGENTS §6 安排三路阳性对照',
            why='分别属 MAC 策略门与观测覆盖问题，换文件系统不触及'),
    ]


def authorization() -> dict:
    a = text('agents')
    q = json.loads(text('r2_qualification'))
    r = json.loads(text('readback'))
    return dict(
        partition_write_required=True,
        partition_write_rule='放弃旧数据也不等于授权格式化、分区写入或改槽' in a,
        security_model_change_required=True,
        security_model_rule='AGENTS §6 / 交接文档要求用户单独明确批准安全模型路线选择',
        current_gate=q['device_gate']['status'],
        candidate_consumed=q['device_gate']['candidate_consumed'],
        root_readback_all_match=r['comparison']['all_match'],
        note='换栈同时触发分区写入与安全模型两道独立授权门，'
             '且当前 r2 仍停在实机确认门、未消费',
    )


def main() -> None:
    ev = dict(
        schema='nuwa/stack-switch-cost/1',
        question='更换文件系统和存储栈接入层的成本怎么样',
        answer=('成本极高，且不是「打几个补丁」而是**换内核形态**：'
                'nuwa 是 donor prelinked 二进制 patch，公开仓的 22 个 L1 补丁全是源码级，'
                '无法直接套用。五层成本里文件系统层与存储栈接入层都是子系统级重写，'
                '认证根要全量重写 userdata（分区写入单独授权），'
                '所有 donor 绝对地址绑定的观测与回归作废，且一次改掉四组变量破坏归因。'
                '项目有一条云端源内核完整链接证据可作起点，但 donor 预链接、driver ABI、'
                'nuwa 可启动性均未验证。当前不该做。'),
        cost_verdict=dict(
            overall='极高（路线级切换，不是候选级改动）',
            cheaper_alternative='在现有栈内做下一层配对观测，成本量级低一到两个数量级',
            not_started_from_zero='云端源 CI run 39738601892 已证明源配方与完整链接可行',
            still_missing='donor prelinked 闭源 kext 合并、driver/RPC ABI、'
                          '正式 nuwa 配置、可启动性'),
        shape=shape(),
        prior_source_ci=prior_ci(),
        patch_scale=patch_scale(),
        cost_layers=cost_layers(),
        counter_evidence=counter_evidence(),
        three_cases=three_cases(),
        authorization=authorization(),
        explicitly_not_now=[
            '引入 permissive 替身（不覆盖 mac_vnode_check_read）',
            '换 HFS+ / BSD 裸 bdevsw（只对 ios-sweet 系成立）',
            '重建认证根或重写 userdata（分区写入，需单独批准）',
            '改 board.toml 内存/基址或 kernel_args',
            '在 r2 消费前再加挂点或再建候选'],
        boundaries=[
            '本轮为离线成本评估：未操作设备、未改内核、未构建、'
            '未写分区、未改槽、未提交 git。',
            '认证根 15:05 刚实测完好；r2 仍停在实机确认门、未消费。',
            'sheng / ios-sweet 到 SpringBoard 均为仓库自述，非本机实机验证。',
            '唯一主线动作仍是消费 r2 取 FB03/FB06 配对读数，'
            '再按三情况决定是否需要动存储栈。'],
        inputs=inputs(),
    )
    (OUT / 'evidence.json').write_text(
        json.dumps(ev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('inputs:', len(ev['inputs']))
    print('cost layers:', len(ev['cost_layers']))
    print('L1 patches:', ev['patch_scale']['L1_patch_count'],
          '| HFS sources:', ev['patch_scale']['hfs_source_files_introduced'])
    print('prior CI exists:', ev['prior_source_ci']['exists'])
    print('three cases:', len(ev['three_cases']))
    print('written:', OUT / 'evidence.json')


if __name__ == '__main__':
    main()
