"""Frozen continuation outer vendor_boot packing/readback; never a device entry.

The reviewed diagnostic outer script is reused read-only for its official
vendor_boot invocation, stock/GPT validation and exact outer comparison. This
wrapper has its own continuation input whitelist and never accepts the old
diagnostic package.
"""
import argparse
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import owner_bnch as O
import owner_payload as P

spec = importlib.util.spec_from_file_location(
    'owner_reviewed_outer', Path(__file__).with_name('build-owner-vendor-boot.py'))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)

FAT_SHA = '9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c'
ADT_SHA = '885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4'
RECORD_SHA = 'a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57'
KERNEL_SHA = '7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4'
STOCK_SHA = V.STOCK_SHA
R4_SHA = V.R4_SHA
CANDIDATE = 'out/owner-pmap-ret-continuation-verifier-final-20261111'
CURRENT_BACKUP = 'out/pmap-ret-run-pmap-ret-20261111-r4/vendor_boot_b.stock.img'
CURRENT_BACKUP_SHA = '493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad'
FORBIDDEN_ARG_TOKENS = ('stage', 'smp', 'reset', 'panic', 'entry_probe', 'native-ufs-root')


def check_record(record):
    O.require(record.get('profile') == P.CONTINUATION_PROFILE, 'Wrong selected profile')
    O.require(record.get('continuation_only') is True and
              record.get('execution_mode') == 'continue-original' and
              record.get('pmap_ret_restored') is True and record.get('observer_unhooked') is True and
              record.get('renderer_retained') is True, 'Continuation record flags mismatch')
    O.require(record.get('readback_complete') is True and record.get('device_release') is False,
              'Continuation record is not a complete host artifact')


def check_continuation(cont):
    O.require(cont.get('target_sha256') == KERNEL_SHA and
              cont.get('source_diagnostic_sha256') == P.CONTINUATION_SOURCE[0] and
              cont.get('source_diagnostic_bytes') == P.CONTINUATION_SOURCE[1] and
              cont.get('diff_byte_count') == 8 and cont.get('other_bytes_identical') is True and
              cont.get('pmap_ret_restored') is True and cont.get('observer_unhooked') is True and
              cont.get('renderer_retained') is True, 'Continuation evidence mismatch')
    expected = [{'fileoff': hex(o), 'va': hex(v), 'diagnostic_word': hex(b), 'restored_word': hex(r), 'bytes': 4}
                for o, v, b, r in P.CONTINUATION_SITES]
    O.require(cont.get('inverse_patches') == expected, 'Continuation inverse patch mismatch')
    O.require(cont.get('renderer_span') == {'fileoff': hex(P.RENDERER_SPAN[0]), 'bytes': P.RENDERER_SPAN[1]},
              'Continuation renderer span mismatch')


def check_args(board, record):
    arguments = board['payload']['kernel_args']
    O.require(arguments == P.CONTINUATION_ARGS, 'Continuation arguments changed')
    O.require(record.get('effective_kernel_args') == ' '.join(P.CONTINUATION_ARGS),
              'Continuation effective arguments mismatch')
    O.require(not any(token in value.lower() for value in arguments for token in FORBIDDEN_ARG_TOKENS),
              'Forbidden stage/reset/smp argument in continuation profile')


def check_fat(raw, record):
    O.require(len(raw) == 67108864 and O.sha(raw) == record.get('payload_sha256') == FAT_SHA,
              'Selected verifier FAT pin mismatch')


def check_kernel(raw, record):
    O.require(len(raw) == 55386112 and O.sha(raw) == record.get('prepared_kernel_sha256') == KERNEL_SHA,
              'Continuation kernel pin mismatch')


def validate_inputs(candidate, stock_path, loader, layout_path):
    candidate = Path(candidate).resolve(strict=True)
    O.require(candidate == (O.ROOT / CANDIDATE).resolve(),
              'Only the independent continuation verifier candidate may be packed')
    source = O.read_json(candidate / 'payload-record.json')
    check_record(source)
    fat_path = Path(source['payload_path']).resolve(strict=True)
    O.require(fat_path.is_relative_to(candidate), 'FAT outside selected candidate')
    fat = fat_path.read_bytes()
    check_fat(fat, source)
    kernel = (candidate / 'inputs/kernel.macho').read_bytes()
    check_kernel(kernel, source)
    artifact = P.qualify_prepared(kernel, KERNEL_SHA, P.CONTINUATION_PROFILE)
    check_continuation(source['continuation'])
    adt = (candidate / 'adt-generation/final.adt').read_bytes()
    record_path = candidate / 'adt-generation/record.json'
    O.require(O.sha(adt) == source['adt_sha256'] == ADT_SHA and
              O.sha(record_path.read_bytes()) == source['owner_record_sha256'] == RECORD_SHA,
              'Selected continuation ADT/record pin mismatch')
    board = O.read_json(candidate / 'runtime-board.json')
    kwargs = O.read_json(candidate / 'adt-generation/keywords.json')
    check_args(board, source)
    O.load_record(record_path, O.binding((candidate / 'adt-generation/input.dtb').read_bytes(),
                                         board, kwargs, artifact))
    layout = O.read_json(layout_path)
    O.require(Path(layout['candidate']).resolve() == candidate and
              layout['kernel_sha256'] == KERNEL_SHA and layout['adt_sha256'] == ADT_SHA and
              layout['r4_image_sha256'] == R4_SHA and layout['relative_ranges_disjoint'] is True and
              layout.get('runtime_ret_executed') == 'not observed' and layout['device_release'] is False,
              'Independent continuation layout binding mismatch')
    loader_raw = Path(loader).read_bytes()
    O.require(len(loader_raw) == 1495040 and O.sha(loader_raw) == R4_SHA, 'Fixed independent r4 boot pin mismatch')
    stock_path = Path(stock_path).resolve(strict=True)
    O.require(stock_path == (O.ROOT / '.cache/stock/vendor_boot_b.img').resolve(), 'Wrong nuwa stock path')
    stock = stock_path.read_bytes()
    O.require(O.sha(stock) == STOCK_SHA == O.read_json(O.ROOT / '.cache/stock/vendor_boot.json')['stock_sha256']
              and O.sha((O.ROOT / '.cache/stock/vendor_boot_a.img').read_bytes()) == STOCK_SHA,
              'Nuwa historical stock A/B source hash mismatch')
    partitions = V.gpt_capacity((O.ROOT.parent / '.cache/device-evidence/20261107-recovery/gpt-sde.bin').read_bytes())
    O.require(len(stock) == partitions['vendor_boot_b']['bytes'], 'Stock/GPT capacity mismatch')
    V.parse(stock)
    return SimpleNamespace(candidate=candidate, source=source, fat_path=fat_path, fat=fat, kernel=kernel,
                           artifact=artifact, adt=adt, record_path=record_path, board=board, kwargs=kwargs,
                           layout=layout, stock=stock, stock_path=stock_path, loader_raw=loader_raw,
                           partitions=partitions)


def current_backup_comparison(stock):
    path = (O.ROOT / CURRENT_BACKUP).resolve()
    if not path.is_file():
        return {'path': str(path), 'present': False}
    raw = path.read_bytes()
    O.require(O.sha(raw) == CURRENT_BACKUP_SHA, 'Current vendor_boot backup evidence hash mismatch')
    before, after = V.parse(stock), V.parse(raw)
    return {'path': str(path), 'present': True, 'sha256': CURRENT_BACKUP_SHA, 'same_object_as_template': False,
            'ramdisk_bytes': [len(before['ramdisk']), len(after['ramdisk'])],
            'dtb_bytes': [len(before['dtb']), len(after['dtb'])], 'dtb_equal': before['dtb'] == after['dtb'],
            'bootconfig_equal': before['bootconfig'] == after['bootconfig'],
            'vbmeta_equal': before['vbmeta'] == after['vbmeta'],
            'footer_equal': before['footer'] == after['footer'],
            'note': 'Historical template accepted for the diagnostic outer is reused unchanged for packing; '
                    'it is not the current device backup and was not silently substituted.'}


def build(base, candidate, stock, loader, layout, output):
    base = V.check_base(base)
    ctx = validate_inputs(candidate, stock, loader, layout)
    out = P.reserve(output)
    try:
        (out / 'build-input.toml').write_text('[build]\n')
        destination = out / 'vendor_boot.img'
        O.require(not destination.exists() and not (out / 'vendor_boot.json').exists(), 'Outer output already exists')
        soc = P.verify_soc(O.ROOT.parent / 'UniXNU-sm8550-common')
        command = [sys.executable, '-B', str(base / 'unixnu'), 'vendor_boot', '--stock', str(ctx.stock_path),
                   '--ramdisk', str(ctx.fat_path), '-o', str(destination), '-D', str(O.ROOT),
                   '--out', str(out / 'context'), '--config', str(out / 'build-input.toml'),
                   '--local-module', 'soc:sm8550=' + str(soc), '-j', '1']
        result = subprocess.run(command, cwd=base, capture_output=True, text=True)
        O.write_json(out / 'official-command.json', {'command': command, 'cwd': str(base),
                                                    'exit': result.returncode, 'stdout': result.stdout,
                                                    'stderr': result.stderr})
        O.require(result.returncode == 0, 'Official vendor_boot failed (see official-command.json)')
        image = destination.read_bytes()
        differences = V.compare(ctx.stock, image, ctx.fat, ctx.partitions['vendor_boot_b']['bytes'])
        extracted_fat = out / 'actual-vendor-ramdisk.img'
        extracted_fat.write_bytes(V.parse(image)['ramdisk'])
        extraction = out / 'extracted'
        extraction.mkdir()
        P.capture(['mcopy', '-s', '-i', extracted_fat, '::/EFI', extraction], out / 'extract-command.json')
        expected = {'Payloads/kernel.macho': ctx.kernel, 'Payloads/kernel.macho.adt': ctx.adt,
                    'Payloads/kernel.macho.trustcache': (ctx.candidate / 'inputs/kernel.macho.trustcache').read_bytes(),
                    'unixnu.toml': (ctx.candidate / 'extracted/EFI/UniXNU/unixnu.toml').read_bytes()}
        hashes = P.verify_extracted(extraction, expected, ctx.adt, ctx.record_path,
                                    SimpleNamespace(board=ctx.board), ' '.join(P.CONTINUATION_ARGS), ctx.artifact)
        O.require(hashes == ctx.source['fat_hashes'] and set(hashes) == set(expected),
                  'Outer FAT content binding mismatch')
        config = tomllib.loads(expected['unixnu.toml'].decode())
        O.require(len(config['entry']) == 4 and sum(e['type'] == 'xnu' for e in config['entry']) == 1 and
                  sum(e['type'] == 'action' for e in config['entry']) == 3 and
                  config['boot']['default'] == 'xnu', 'Expected one XNU + three actions/default=xnu')
        O.require(config['entry'][0]['args'] == ' '.join(P.CONTINUATION_ARGS), 'Unexpected FAT XNU arguments')
        negatives = []
        for name, offset in [('header', 16), ('ramdisk', 4096)]:
            changed = bytearray(image)
            changed[offset] ^= 1
            try:
                V.compare(ctx.stock, bytes(changed), ctx.fat, len(ctx.stock))
            except ValueError:
                negatives.append(name)
            else:
                raise ValueError('Outer tamper accepted: ' + name)
        V.check_base(base)
        O.require(ctx.stock_path.read_bytes() == ctx.stock and ctx.fat_path.read_bytes() == ctx.fat and
                  Path(loader).read_bytes() == ctx.loader_raw, 'Frozen source input changed during packing')
        manifest = {'status': 'self-checked', 'official_exit': result.returncode, 'readback_complete': True,
            'base_revision': O.REVISION, 'selected_candidate': str(ctx.candidate),
            'profile': P.CONTINUATION_PROFILE, 'execution_mode': 'continue-original',
            'stock_sha256': STOCK_SHA, 'partition_evidence': ctx.partitions,
            'stock_template_is_current_device_backup': False,
            'current_backup_comparison': current_backup_comparison(ctx.stock),
            'vendor_boot_sha256': O.sha(image), 'vendor_boot_bytes': len(image),
            'vendor_ramdisk_sha256': O.sha(extracted_fat.read_bytes()), 'r4_boot_sha256': R4_SHA,
            'kernel_sha256': KERNEL_SHA, 'kernel_bytes': 55386112, 'adt_sha256': ADT_SHA,
            'owner_record_sha256': RECORD_SHA, 'payload_record_sha256': O.sha((ctx.candidate / 'payload-record.json').read_bytes()),
            'selected_layout_sha256': O.sha(Path(layout).read_bytes()),
            'input_binding': {'fat_sha256': FAT_SHA, 'adt_sha256': ADT_SHA, 'owner_record_sha256': RECORD_SHA,
                              'kernel_sha256': KERNEL_SHA, 'kernel_bytes': 55386112,
                              'effective_kernel_args': ' '.join(P.CONTINUATION_ARGS),
                              'source_diagnostic_sha256': P.CONTINUATION_SOURCE[0],
                              'inverse_diff_bytes': 8},
            'outer_comparison': differences, 'fat_hashes': hashes, 'tamper_negatives_rejected': negatives,
            'entry_counts': {'xnu': 1, 'action': 3}, 'default_entry': 'xnu',
            'args_exact': ' '.join(P.CONTINUATION_ARGS), 'forbidden_arg_tokens': list(FORBIDDEN_ARG_TOKENS),
            'runtime_volume_selection_proven': False,
            'scope': 'Config prefers startup volume else first valid volume; FAT internals do not establish '
                     'runtime selection or uniqueness',
            'auth_verified': False, 'range_static_review': 'Independent continuation layout bound by hash; '
                     'this packer does not re-measure or claim runtime mapping',
            'remaining_resource_conditions': ['GOP', 'EFI memory map'],
            'device_release': False, 'authentication': 'NOT REACHED',
            'payload_generated': False, 'new_bnch_drawn': False, 'native_rebuilt': False,
            'executor': {'profile': None, 'old_r4_boot_claim_reused': False, 'device_authorized': False,
                         'note': 'scripts/run-pmap-ret-once.py is unchanged; the old r4 boot claim is consumed '
                                 'and not reusable; this host candidate has no device entry'}}
        O.write_json(out / 'outer-record.json', manifest)
        return manifest
    except Exception as error:
        O.write_json(out / 'failure.json', {'status': 'failed', 'failure_type': type(error).__name__,
                                           'device_release': False})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'candidate', 'stock', 'loader', 'layout', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = build(a.base, a.candidate, a.stock, a.loader, a.layout, a.output)
    print('self-checked continuation outer vendor_boot:', result['vendor_boot_sha256'],
          '; no device authorization/release')


if __name__ == '__main__':
    main()
