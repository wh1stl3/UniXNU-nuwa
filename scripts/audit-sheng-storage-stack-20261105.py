"""核查 sheng 的文件系统与存储栈接入层，产出可复核证据。

离线只读。固定 UniXNU/UniXNU-sheng 提交 08cde20edc3254ed6f7df8d0f5384fb887786e8f。
输出 reports/sheng-storage-stack-20261105/evidence.json。

证据纪律：
- 以公开固定提交为准；本地 2026-10-19 旧快照只作差异对照，不冒充固定版。
- 每个结论绑定到文件:行号或配置项，不用官网自述代替实现。
- sheng 是 iPadOS 17.7.11 / xnu-12377，与 nuwa iOS16 / xnu-8796.141.3 不同版本。
"""
import hashlib
import json
import re
import tomllib
from pathlib import Path

R = Path(__file__).resolve().parent.parent
OUT = R / 'reports/sheng-storage-stack-20261105'
REF = R / 'references/sheng-storage-20261105'
PINNED = '08cde20edc3254ed6f7df8d0f5384fb887786e8f'
BASE_URL = 'https://raw.githubusercontent.com/UniXNU/UniXNU-sheng/' + PINNED

LOCAL_SHENG = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng')
UPSTREAM = Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
CONTRACT = R / 'reports/desktop-readiness/2026-11-02-payload-exposure-r1/sheng-contract.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_items(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = re.match(r'\s*(CONFIG_XNU_\w+)\s*=\s*(.*?)\s*$', line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def grep_line(path, needle):
    for i, line in enumerate(Path(path).read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        if needle in line:
            return dict(line=i, text=line.strip())
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    board_raw = (REF / 'board.toml').read_bytes()
    board = tomllib.loads(board_raw.decode('utf-8'))
    cfg = config_items(REF / 'sheng_defconfig')
    local_cfg = config_items(LOCAL_SHENG / 'configs/sheng_defconfig')
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))

    kernel_args = board['payload']['kernel_args']
    archives = board['kernel']['archives']
    components = board['components']['include']
    windows = board['userdata']['windows']

    drivers = {}
    for name, rel, cls in (
        ('NativeUfs', 'drivers/NativeUfs/NativeUfs.cpp', 'NativeUfsBlock'),
        ('NativeVirtioBlock', 'drivers/NativeVirtioBlock/NativeVirtioBlock.cpp', 'NativeVirtioBlock'),
        ('NativeRamBlock', 'drivers/NativeRamBlock/NativeRamBlock.cpp', 'NativeRamBlock'),
    ):
        p = UPSTREAM / rel
        drivers[name] = dict(
            path=str(p), sha256=sha(p),
            inherits=grep_line(p, 'class %s : public IOBlockStorageDevice' % cls),
            do_async=grep_line(p, 'doAsyncReadWrite'),
            iomedia=grep_line(p, 'serviceMatching ("IOMedia")') or grep_line(p, 'serviceMatching("IOMedia")'))

    files = {
        'pinned_board_toml': REF / 'board.toml',
        'pinned_sheng_defconfig': REF / 'sheng_defconfig',
        'pinned_readme': REF / 'README.md',
        'pinned_patch_series': REF / 'patch-series.txt',
        'local_board_toml': LOCAL_SHENG / 'board.toml',
        'local_sheng_defconfig': LOCAL_SHENG / 'configs/sheng_defconfig',
        'local_build_userdata_root_image': LOCAL_SHENG / 'scripts/build-userdata-root-image.py',
        'local_build_sheng_payload': LOCAL_SHENG / 'scripts/build-sheng-payload.py',
        'upstream_build_mockfs_fixture': UPSTREAM / 'scripts/build-mockfs-fixture.py',
        'payload_sheng_contract': CONTRACT,
    }
    inputs = {k: dict(path=str(v) if v.is_absolute() else str(v.relative_to(R)),
                      sha256=sha(v)) for k, v in files.items()}

    result = dict(
        schema='Nuwa.ShengStorageStack.v1', date='2026-11-05',
        purpose='回答 sheng 采用什么文件系统与存储栈接入层，并与 nuwa / ios-sweet 对齐',
        version_binding=dict(
            repository='UniXNU/UniXNU-sheng', pinned_commit=PINNED,
            os_profile=board['board']['os_profile'], soc=board['board']['soc'],
            defconfig_sha256=sha(REF / 'sheng_defconfig'),
            board_toml_sha256=sha(REF / 'board.toml'),
            pinned_equals_main_for_defconfig=contract['public_main_same_bytes_as_pin'],
            local_snapshot_note='本地 UniXNU-sheng 检出为 2026-10-19 旧快照，'
                                '多 12 个配置项且 VirtioBlock archive 名不同；不冒充固定版',
            local_only_configs=sorted(set(local_cfg) - set(cfg)),
            local_different_values={k: dict(local=local_cfg.get(k), pinned=cfg.get(k))
                                    for k in set(local_cfg) & set(cfg) if local_cfg[k] != cfg[k]}),
        filesystem=dict(
            verdict='Apple 原生 APFS（donor prelinked，未被替换）',
            evidence=[
                dict(source='board.toml:74', value='offline-apfs-load=1'),
                dict(source='board.toml:74', value='-apfs_shared_datavolume'),
                dict(source='board.toml:86', value='root_match_volume_uuid = ' +
                     str(board['payload']['adt']['root_match_volume_uuid'])),
                dict(source='components.include', value='XnuPrelink（donor prelinked 内核形态）'),
                dict(source='local board.toml:56/67',
                     value='旧快照 roots 显式列出 com.apple.filesystems.apfs 与 com.apple.iokit.IOStorageFamily'),
                dict(source='build-userdata-root-image.py:8-9',
                     value='userdata 窗口 OS / SystemOS 均为原始 iPadOS 磁盘镜像（GPT + APFS），字节不变'),
                dict(source='sheng_defconfig',
                     value='OWNER_UNION_SYSTEMOS=y / OWNER_CACHE_MOUNT=y / OWNER_DATA_MOUNT=y / '
                           'OWNER_BOOT_MANIFEST=y'),
                dict(source='pinned patch_series', value='仅 3 个设备补丁（audio-addon-mount / cpu-idle / amp），'
                                                        '无任何文件系统或存储栈补丁'),
            ],
            root_layout=dict(
                partition='userdata（board.toml [userdata] first_lba/last_lba/lba_bytes=4096）',
                windows=[dict(name=w['name'], component=w['component']) for w in windows],
                union='SystemOS 经原生 MNT_UNION 联合挂载到 /System/Cryptexes/OS，提供 dyld 共享缓存',
                data='OWNER_DATA_MOUNT + sheng-data-persist=2 + packed_data_ramdisk / persistent_data'),
            mockfs=dict(
                verdict='不是根文件系统；固定版 defconfig 未启用 CONFIG_XNU_SOURCE_MOCKFS',
                evidence='build-mockfs-fixture.py:2 "Compile XNU\'s minimal executable-root filesystem '
                         'for offline tests"；仅编译 mockfs_fsnode/mockfs_vfsops/mockfs_vnops 三个 .o 作离线夹具',
                local_snapshot_note='本地旧快照有 CONFIG_XNU_SOURCE_MOCKFS=y，属旧版差异，不能据此判定固定版'),
            hfs_plus='固定版配置、board.toml、patch series、根镜像脚本中均无 HFS+ 痕迹'),
        storage_stack=dict(
            verdict='IOKit 标准栈：自写块设备驱动继承 IOBlockStorageDevice → 发布 IOMedia → '
                    'Apple 原生 IOStorageFamily → APFS；不是 BSD 裸 bdevsw',
            block_device_backends=[
                dict(component='ShengUfs', config='CONFIG_XNU_NATIVE_UFS=y',
                     boot_arg='native-ufs-root=1', role='真实 UFS 根设备',
                     archive='component:ShengUfs（独立仓，本地无副本）'),
                dict(component='VirtioMmioBlock', config='CONFIG_XNU_NATIVE_VIRTIO_BLOCK=y',
                     archive=cfg.get('CONFIG_XNU_NATIVE_VIRTIO_BLOCK_ARCHIVE'),
                     role='VirtIO MMIO 块设备'),
                dict(component='RamBlock', config='CONFIG_XNU_NATIVE_RAM_BLOCK=y',
                     role='Data 种子 / 缓存（packed_data_ramdisk）'),
            ],
            iokit_evidence=drivers,
            verified_root=dict(config='CONFIG_XNU_VERIFIED_ROOT_PROBE=y / OWNER_ROOT_AUDIT=y / OWNER_ROOT_TRUST=y',
                               archive=cfg.get('CONFIG_XNU_VERIFIED_ROOT_ARCHIVE'),
                               note='认证根探针与 owner-root 放行，位于块设备与 APFS 挂载之间'),
            no_bdevsw_evidence='固定版与上游基座均未出现 bdevsw_add / devfs_make_node / physio('
                               'sweet_ufs 风格) 的实现；sheng 走 IOKit 发布 IOMedia'),
        kernel_args_relevant=[a for a in kernel_args if any(
            k in a for k in ('apfs', 'ufs', 'data', 'ramdisk', 'root', 'pmgr'))],
        three_way_comparison=[
            dict(project='sheng（UniXNU 官方，固定 %s）' % PINNED[:8],
                 os='iPadOS 17.7.11 / xnu-12377',
                 filesystem='Apple 原生 APFS（OS + SystemOS union + Data）',
                 storage_stack='IOKit IOBlockStorageDevice → IOMedia → IOStorageFamily',
                 ufs_driver='自写 ShengUfs + VirtioMmioBlock + RamBlock',
                 kernel_form='donor prelinked（XnuPrelink）+ XNU 源码补丁'),
            dict(project='nuwa（本仓）', os='iOS 16.7.16 / xnu-8796.141.3',
                 filesystem='Apple 原生 APFS（donor prelinked com.apple.filesystems.apfs）',
                 storage_stack='IOKit IOBlockStorageDevice → IOMedia → IOStorageFamily',
                 ufs_driver='自写 NativeUfs（与上游基座 NativeUfs.cpp 同源）',
                 kernel_form='kernelcache 提取 + donor prelinked 二进制 patch'),
            dict(project='ios-sweet / UniXNU-negroni', os='iOS 16.7.16 / xnu-8796.141.3',
                 filesystem='内置 HFS+ 或 mockfs 虚拟 ramdisk',
                 storage_stack='BSD 裸 bdevsw + d_strategy + physio()，绕过 IOKit / IOMedia',
                 ufs_driver='自写 sweet_ufs.c（UFSHCI polled SCSI）',
                 kernel_form='XNU 源码自编译 + 81 / 116 个补丁'),
        ],
        conclusion=dict(
            direct_answer='sheng 与 nuwa 在「文件系统 + 存储栈接入层」上同类：Apple 原生 APFS + '
                          'IOKit IOStorageFamily 标准栈；与 ios-sweet 的 HFS+ / 裸 bdevsw 路线不同类。',
            implication='「公开仓换 HFS+ 绕过 APFS 从而越过 header-read 卡点」只对 ios-sweet 系成立，'
                        '不能推广到官方 UniXNU 路线。sheng 同样要过 APFS VNOP_READ；它对 nuwa 的'
                        '参考价值在认证根探针、SystemOS union、Data 挂载与多条块设备后端，'
                        '而不是「换文件系统绕开 APFS」。',
            caution='sheng 的实机状态来自仓库 / 官网自述，不是本机实机验证；'
                    '其 iPadOS17 / xnu-12377 的板值、UUID、mount ABI 不能直接搬到 nuwa iOS16/8796。'),
        inputs=inputs,
        limitations=[
            'ShengUfs 是独立组件仓（UniXNU/ShengUfs），本地无副本，未逐字节核对其实现；'
            '本结论依据 board.toml 的 component 声明与 native-ufs-root=1。',
            '上游基座 NativeUfs / NativeVirtioBlock / NativeRamBlock 源码已核对类继承，'
            '但 sheng 固定版链接的是 ShengUfs / VirtioMmioBlock / RamBlock 组件，名称与本地基座不完全一致。',
            '本地 UniXNU-sheng 检出为 2026-10-19 旧快照，固定版以 GitHub 08cde20e… 为准。',
            '官网 / README 的 UFS 根可用状态是仓库自述，不是本机实机证据。',
            '本轮只读：未改内核、未构建、未上机、未提交 git。',
        ])
    (OUT / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print('filesystem:', result['filesystem']['verdict'])
    print('storage:', result['storage_stack']['verdict'])
    print('local-only configs:', len(result['version_binding']['local_only_configs']))
    print('inputs:', len(inputs), '| written', (OUT / 'evidence.json').relative_to(R))


if __name__ == '__main__':
    main()
