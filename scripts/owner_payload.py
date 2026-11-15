"""Pinned, isolated host payload wrapper. No native patching or device dispatch."""
import argparse
import ast
import copy
import os
import shutil
import struct
import subprocess
import sys
import tomllib
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

import owner_bnch as O

# Load order is part of the closure: top-level relative imports see executed dependencies.
PINS = {
    'util': O.UTIL_SHA,
    'config': 'f14d5745f8796b5c356280c1f4ee9550e513fea0a381b10ede84099295f6595d',
    'profiles': '0a11f976adc9bab5afdac6bb6ff66f6c9338d8821901f9b7c3292647f54fc015',
    'feeds': '3ebe1714f73c6d66f7a1775c7ce7fdc64c1d4214d76349c423896ca5f86c2c66',
    'components': 'a0aa6d2a6e21735add0086089f93e242c1f3380feb00ab62d19b125a55dfd3fd',
    'ipsw': 'b7d166e113329a9dbfa352864567a6f61e344efae6fbeb96e9b997fdd7bfb093',
    'patches': '899b00bdd07e4ce0fd28f746c88d0106a903f4d5b13e58e17473834765eb7206',
    'kernel': '468f7c913a0016b9d78c07f6d283287a2daea0d3073b60f933be7c8ef4406ecf',
    'devicetree': O.SOURCE_SHA,
    'payload': '477701f3a19b78f0ef3ebc62fc61b640c2793c9e85a4e4024333abac5041f278',
}
SOC_REVISION = 'a9f45dc60c035084b95463781538380f4c3606c9'
OS_PROFILE = 'ios-16.7.16-20H392'
BASELINE_PROFILE = 'baseline-prepared-fb1e'
DIAGNOSTIC_PROFILE = 'pmap-ret-stop-20261111-r1'
CONTINUATION_PROFILE = 'pmap-ret-continue-20261111-r1'
PROFILES = {
    BASELINE_PROFILE: (O.KERNEL_SHA, 55357440),
    DIAGNOSTIC_PROFILE: ('6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269', 55386112),
    CONTINUATION_PROFILE: ('7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4', 55386112),
}
DIAGNOSTIC_ARGS = ['-v', 'serial=3', 'sheng-platform-stage=5']
# The continuation profile deliberately drops the old stage argument: ArmDTPlatform.cpp:200-209
# resets the platform stage after registerService returns, so the stage-5 hint only masked state.
CONTINUATION_ARGS = ['-v', 'serial=3']
# Verified diagnostic source frozen by the reviewed r1 report. The continuation image is derived
# from it by exactly these two inverse 4-byte writes; the native/renderer recipe is never rerun.
CONTINUATION_SOURCE = ('6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269', 55386112)
CONTINUATION_SITES = (
    # fileoff, VA, diagnostic word (branch/observer hook), restored word
    (0x19acf00, 0xfffffff0046e9f00, 0x14ca9d0e, 0xd65f03c0),  # PMAP initializer RET restored
    (0x98d340, 0xfffffff007991340, 0x17e984a0, 0x14000000),  # observer slot back to self-loop
)
RENDERER_SPAN = (0x3ee5c0, 2607)  # Unchanged reviewed renderer blob inside the entry padding.

EXPECTED_CALL = """(payloads / 'kernel.macho.adt').write_bytes(generate(
    dtb, ctx.board, unique_chip_id=seed, data=bool(data), trust=bool(trust), addon=bool(addon),
    root_policies=bool(policies)))"""


def dump(tree):
    return ast.dump(tree, include_attributes=False)


def adapt_payload(raw):
    original = ast.parse(raw)
    tree = copy.deepcopy(original)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build']
    O.require(len(functions) == 1, 'Payload build AST drift')
    statements = [n for n in functions[0].body if isinstance(n, ast.If) and
                  dump(n.test) == dump(ast.parse('ctx.schema_version == 2', mode='eval').body)]
    O.require(len(statements) == 1, 'Payload format2 branch drift')
    branch = statements[0]
    expected = ast.parse("from .devicetree import compile_hardware, generate\n"
                         "dtb = compile_hardware(ctx)\n" + EXPECTED_CALL).body
    O.require([dump(n) for n in branch.body] == [dump(n) for n in expected],
              'Payload format2 generate/write_bytes/keywords drift')
    calls = [n for n in ast.walk(functions[0]) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Name) and n.func.id == 'generate']
    O.require(len(calls) == 1, 'Payload generate call count drift')
    calls[0].func.id = '_owner_generate'  # The sole approved delta, not a devicetree replacement.
    normalized = copy.deepcopy(tree)
    changed = [n for n in ast.walk(normalized) if isinstance(n, ast.Call) and
               isinstance(n.func, ast.Name) and n.func.id == '_owner_generate']
    O.require(len(changed) == 1, 'Payload adapter delta count')
    changed[0].func.id = 'generate'
    O.require(dump(normalized) == dump(original), 'Payload AST change outside sole callee')
    return ast.fix_missing_locations(tree)


def validate_blob(name, raw, committed):
    O.require(O.sha(raw) == PINS[name], 'Payload dependency SHA drift: ' + name)
    O.require(raw.replace(b'\r\n', b'\n') == committed.replace(b'\r\n', b'\n'),
              'Payload dependency revision content drift: ' + name)


def sources(base):
    base = Path(base).resolve(strict=True)
    O.require(O.git(base, 'rev-parse', 'HEAD').decode().strip() == O.REVISION, 'Payload base revision drift')
    result = {}
    for name in PINS:
        relative = 'scripts/unixnu/' + name + '.py'
        path = base / relative
        O.require(path.resolve(strict=True) == path, 'Linked payload dependency: ' + name)
        raw = path.read_bytes()  # Same bytes for hash, parse, compile. No loader reread.
        validate_blob(name, raw, O.git(base, 'show', O.REVISION + ':' + relative))
        result[name] = raw
    return base, result


@contextmanager
def private_payload(base, blobs, bridge):
    O.require(list(blobs) == list(PINS), 'Missing/unordered payload dependency closure')
    O.require(all(O.sha(raw) == PINS[name] for name, raw in blobs.items()), 'Private payload snapshot SHA drift')
    trees = {name: ast.parse(raw) for name, raw in blobs.items()}
    trees['payload'] = adapt_payload(blobs['payload'])
    # All relative imports, including delayed function imports, must stay within this explicit closure.
    for tree in trees.values():
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.level:
                O.require(n.level == 1 and ((n.module in PINS) if n.module else
                          all(alias.name in PINS for alias in n.names)), 'Import outside payload closure')
    package_name = '_nuwa_owner_payload_' + uuid.uuid4().hex
    package = types.ModuleType(package_name)
    package.__path__ = []
    package.__package__ = package_name
    modules = {name: types.ModuleType(package_name + '.' + name) for name in PINS}
    names = {package_name: package, **{m.__name__: m for m in modules.values()}}
    O.require(not any(n in sys.modules for n in names), 'Private payload module collision')
    try:
        for n, module in names.items():
            sys.modules[n] = module
        for name, module in modules.items():
            module.__package__ = package_name
            module.__file__ = str(base / 'scripts/unixnu' / (name + '.py'))
            setattr(package, name, module)
            if name == 'payload':
                module._owner_generate = bridge
            exec(compile(trees[name], module.__file__, 'exec'), module.__dict__)
        O.require(modules['payload'].kernel_step is modules['kernel'] and
                  modules['payload'].Error is modules['util'].Error, 'Private dependency origin mismatch')
        yield modules
    finally:
        for n, module in names.items():
            O.require(sys.modules.get(n) is module, 'Private payload registration replaced')
            del sys.modules[n]


def reject_links(path):
    path = Path(path).absolute()
    O.require('..' not in path.parts, 'Parent traversal forbidden')
    for p in (path, *path.parents):
        O.require(not p.is_symlink(), 'Symlink output/input ancestry forbidden')
        if p.exists():
            O.require(not (getattr(p.lstat(), 'st_file_attributes', 0) & 0x400), 'Reparse point forbidden')
    if os.name != 'nt' and len(path.parts) > 3 and path.parts[1] == 'mnt' and len(path.parts[2]) == 1:
        # Linux lstat alone does not establish the absence of every Windows reparse tag.
        powershell = shutil.which('powershell.exe')
        O.require(powershell is not None, 'Windows reparse check unavailable')
        windows_path = path.parts[2].upper() + ':\\' + '\\'.join(path.parts[3:])
        escaped = windows_path.replace("'", "''")
        code = ("$ErrorActionPreference='Stop'; $p='" + escaped + "'; "
                "while($p){if([IO.File]::Exists($p) -or [IO.Directory]::Exists($p)){"
                "if(([IO.File]::GetAttributes($p) -band [IO.FileAttributes]::ReparsePoint) -ne 0)"
                "{exit 9}}; $p=[IO.Path]::GetDirectoryName($p.TrimEnd('\\'))}; exit 0")
        result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command', code],
                                capture_output=True)
        O.require(result.returncode == 0, 'Windows junction/reparse ancestry rejected or check failed')
    return path


def reserve(path):
    return O.reserve(reject_links(path))


def verify_soc(path):
    path = reject_links(path).resolve(strict=True)
    O.require(path == (O.ROOT.parent / 'UniXNU-sm8550-common').resolve(), 'Unexpected local SoC path')
    O.require(O.git(path, 'rev-parse', 'HEAD').decode().strip() == SOC_REVISION, 'Local SoC revision drift')
    tracked = O.git(path, 'ls-tree', '-r', '--name-only', SOC_REVISION, '--', 'soc.toml', 'dts').decode().splitlines()
    O.require('soc.toml' in tracked and any(n.startswith('dts/') for n in tracked), 'SoC input set missing')
    for relative in tracked:
        source = path / relative
        O.require(source.resolve(strict=True) == source, 'Linked SoC input')
        O.require(source.read_bytes().replace(b'\r\n', b'\n') ==
                  O.git(path, 'show', SOC_REVISION + ':' + relative).replace(b'\r\n', b'\n'),
                  'Local SoC working input drift: ' + relative)
    return path


def identity(path):
    obj = O.read_json(path)
    O.require(set(obj) == {'unique_chip_id'} and type(obj['unique_chip_id']) is str and
              0 < int(obj['unique_chip_id'], 16) < 1 << 64, 'Explicit nonzero u64 identity JSON required')
    return obj['unique_chip_id']


def namespace(out, soc, seed, inputs):
    # Every directly accessed Namespace field in Context/load_build_options/_cli_locals/build is explicit.
    return argparse.Namespace(config=str(out / 'build-input.toml'), target='DEBUG',
        out=str(out / 'build'), device=str(O.ROOT), os=OS_PROFILE, command='status', jobs=1,
        local_module=['soc:sm8550=' + str(soc)], local=None,
        local_drivers=None, local_kits=None, local_patches=None, local_scripts=None, local_package=None,
        kernel=None, kernel_arg=[], trust_cache=inputs.get('trust'), owner_trust_cache=None,
        data_ramdisk=inputs.get('data'), gpu_addon=inputs.get('addon'), skip_setup=False,
        unique_chip_id=seed, uefi=None)


def check_context(ctx, out, soc):
    O.require(ctx.device == O.ROOT and ctx.schema_version == 2 and ctx.name == 'nuwa' and not ctx.example,
              'Effective device/schema/name/example mismatch')
    O.require(ctx.board['board']['os_profile'] == OS_PROFILE and ctx.config_name == 'nuwa_defconfig',
              'Effective OS/config mismatch')
    O.require(ctx.profile_roots == {'arch': ctx.root / 'profiles/arch/arm64', 'soc': soc,
                  'os': ctx.root / 'profiles/os' / OS_PROFILE, 'device': O.ROOT}, 'Profile roots mismatch')
    O.require(ctx.work == out / 'build/nuwa' / OS_PROFILE / 'nuwa' and ctx.logs.is_relative_to(out) and
              ctx.tree.is_relative_to(out) and not ctx.tree.exists() and not ctx.config_path.exists() and
              not ctx.state_path.exists() and ctx.config == {}, 'Fresh Context work/state/config mismatch')
    O.require(ctx.args.command == 'status' and not ctx.args.skip_setup and ctx.args.jobs == 1 and
              ctx.args.unique_chip_id and ctx.args.build_config == str(out / 'build-input.toml'),
              'Controlled Context arguments mismatch')


def capture(command, log):
    result = subprocess.run([str(x) for x in command], capture_output=True,
                            env=dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC'))
    O.write_json(log, {'command': [str(x) for x in command], 'cwd': str(Path.cwd()),
                      'exit': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
                      'stderr': result.stderr.decode(errors='replace')})
    O.require(result.returncode == 0, 'FAT tool failed: ' + str(command[0]))


def verify_extracted(extraction, expected, bridge_bytes, seed_record, ctx, line, artifact_binding=None):
    directory = extraction / 'EFI/UniXNU'
    files = {str(p.relative_to(directory)): p for p in directory.rglob('*') if p.is_file()}
    O.require(set(files) == set(expected), 'FAT member set mismatch')
    for name, source in expected.items():
        O.require(files[name].read_bytes() == source, 'FAT member content mismatch: ' + name)
    adt = files['Payloads/kernel.macho.adt'].read_bytes()
    O.require(adt == bridge_bytes, 'FAT ADT differs from this bridge invocation')
    token = None
    if seed_record:
        record, token = O.load_record(seed_record)
        O.require(record['status'] == 'generated' and record['final_adt_sha256'] == O.sha(adt),
                  'FAT ADT/owner record mismatch')
        if artifact_binding is not None:
            O.require(record.get('schema_version') == 2 and record['input_binding'].get('artifact') == artifact_binding,
                      'FAT record profile/kernel binding mismatch')
    O.inspect_adt(adt, token)
    config = tomllib.loads(files['unixnu.toml'].read_text())
    spec = ctx.board['payload']
    O.require(set(config) == {'version', 'boot', 'kits', 'entry'} and
              config['version'] == 1 and config['boot'] == {'timeout': spec.get('timeout', 3), 'default': 'xnu'}
              and config['kits'] == {'autoload': False} and 'driver' not in config, 'FAT config header mismatch')
    entries = config['entry']
    xnu = entries[0]
    required = {'id': 'xnu', 'title': spec.get('title', 'UniXNU'), 'type': 'xnu',
                'path': 'Payloads/kernel.macho', 'args': line}
    if 'Payloads/scratch-data.img' in expected:
        required['initrd'] = 'Payloads/scratch-data.img'
    O.require(xnu == required, 'FAT XNU references/args mismatch')
    actions = [{'id': 'reset', 'title': 'Restart', 'type': 'action', 'action': 'reset'},
               {'id': 'shutdown', 'title': 'Power off', 'type': 'action', 'action': 'shutdown'}]
    if spec.get('tools'):
        actions.append({'id': 'tools', 'title': 'Tools', 'type': 'action', 'action': 'tools'})
    O.require(entries[1:] == actions, 'Unexpected FAT menu/reference entries')
    return {name: O.sha(path.read_bytes()) for name, path in files.items()}


def qualify_prepared(raw, supplied_sha, profile=BASELINE_PROFILE):
    O.require(profile in PROFILES, 'Unknown frozen payload profile')
    expected_sha, size = PROFILES[profile]
    O.require(supplied_sha == expected_sha, 'Kernel pin does not match explicitly selected frozen profile')
    O.require(len(raw) == size and O.sha(raw) == expected_sha, 'Frozen profile kernel hash/size mismatch')
    return {'profile': profile, 'kernel_sha256': expected_sha, 'kernel_bytes': size}


def check_profile_arguments(profile, spec_args, extra):
    # Strict profile branches only; the generic path keeps its historical board-argument behavior.
    if profile == DIAGNOSTIC_PROFILE:
        O.require(spec_args == DIAGNOSTIC_ARGS and not extra,
                  'Frozen diagnostic requires exactly reviewed kernel arguments')
    elif profile == CONTINUATION_PROFILE:
        O.require(spec_args == CONTINUATION_ARGS and not extra,
                  'Continuation requires exactly the reviewed serial-only kernel arguments')


def continuation_analysis(kernel, reference):
    source_sha, source_bytes = CONTINUATION_SOURCE
    O.require(len(reference) == source_bytes and O.sha(reference) == source_sha,
              'Continuation source diagnostic kernel hash/size mismatch')
    O.require(len(kernel) == source_bytes, 'Continuation kernel size mismatch')
    for offset, _, branch, restored in CONTINUATION_SITES:
        O.require(struct.unpack_from('<I', reference, offset)[0] == branch,
                  'Continuation source word drift at ' + hex(offset))
        O.require(struct.unpack_from('<I', kernel, offset)[0] == restored,
                  'Continuation restored word drift at ' + hex(offset))
    pieces, start = [], 0
    for offset, *_ in sorted(CONTINUATION_SITES):
        pieces.append((start, offset))
        start = offset + 4
    pieces.append((start, source_bytes))
    O.require(all(kernel[a:b] == reference[a:b] for a, b in pieces),
              'Continuation differs outside the two reviewed words')
    span_start, span_bytes = RENDERER_SPAN
    O.require(kernel[span_start:span_start + span_bytes] == reference[span_start:span_start + span_bytes],
              'Continuation renderer bytes changed')
    O.require(kernel != reference, 'Continuation kernel is identical to its diagnostic source')
    changed = sum(sum(a != b for a, b in zip(kernel[o:o + 4], reference[o:o + 4]))
                  for o, *_ in CONTINUATION_SITES)
    return {'execution_mode': 'continue-original',
            'source_diagnostic_sha256': source_sha, 'source_diagnostic_bytes': source_bytes,
            'target_sha256': O.sha(kernel), 'target_bytes': len(kernel),
            'inverse_patches': [{'fileoff': hex(o), 'va': hex(v), 'diagnostic_word': hex(b),
                                 'restored_word': hex(r), 'bytes': 4}
                                for o, v, b, r in CONTINUATION_SITES],
            'diff_byte_count': changed, 'other_bytes_identical': True,
            'renderer_span': {'fileoff': hex(span_start), 'bytes': span_bytes},
            'pmap_ret_restored': True, 'observer_unhooked': True, 'renderer_retained': True}


def qualify_continuation(raw, supplied_sha, reference):
    artifact = qualify_prepared(raw, supplied_sha, CONTINUATION_PROFILE)
    facts = continuation_analysis(raw, Path(reference).read_bytes())
    facts['source_diagnostic_path'] = str(Path(reference).resolve())
    return artifact, facts


def diagnostic_adt(raw):
    tree = O.parse(raw)
    chosen = O.find(tree, '/chosen')
    manifest = O.find(tree, '/chosen/manifest-properties')
    O.require('boot-manifest-hash' not in dict(chosen[1]), 'Diagnostic chosen boot-manifest-hash forbidden')
    O.require('love' not in dict(manifest[1]), 'Diagnostic manifest love forbidden')
    memory_map = O.find(tree, '/chosen/memory-map')
    return {'chosen_boot_manifest_hash_present': False, 'manifest_love_present': False,
            'memory_map_DeviceTree_present': 'DeviceTree' in dict(memory_map[1])}


def build_candidate(base, soc, kernel, kernel_sha256, identity_file, output, *, enabled=False,
                    reuse=None, trust=None, data=None, addon=None, profile=BASELINE_PROFILE,
                    continuation_reference=None):
    O.require(enabled or reuse is None, 'Payload record supplied while disabled')
    prepared = Path(kernel).read_bytes()
    diagnostic = profile == DIAGNOSTIC_PROFILE
    continuation = profile == CONTINUATION_PROFILE
    O.require(not diagnostic or enabled, 'Diagnostic profile requires explicit owner BNCH enable')
    O.require(not continuation or enabled, 'Continuation profile requires explicit owner BNCH enable')
    O.require(continuation == (continuation_reference is not None),
              'Continuation reference is required only for the continuation profile')
    if continuation:
        artifact, continuation_facts = qualify_continuation(prepared, kernel_sha256, continuation_reference)
    else:
        artifact, continuation_facts = qualify_prepared(prepared, kernel_sha256, profile), None
    base, blobs = sources(base)
    soc = verify_soc(soc)
    seed = identity(identity_file)  # Explicit JSON only; never reads local TOML or seed environment.
    for tool in ('dtc', 'mformat', 'mcopy'):
        O.require(shutil.which(tool), 'Required host tool unavailable: ' + tool)
    out = reserve(output)
    calls, bridge_bytes, ctx = [], None, None
    try:
        inputs_dir = out / 'inputs'
        inputs_dir.mkdir()
        prepared_path = inputs_dir / 'kernel.macho'
        prepared_path.write_bytes(prepared)
        input_paths = {}
        expected = {'Payloads/kernel.macho': prepared}
        for key, path, target in [('trust', trust, 'kernel.macho.trustcache'),
                                  ('data', data, 'scratch-data.img'), ('addon', addon, 'kernel.macho.gpuaddon')]:
            if path is not None:
                content = Path(path).read_bytes()
                snapshot = inputs_dir / target
                snapshot.write_bytes(content)
                input_paths[key] = str(snapshot)
                expected['Payloads/' + target] = content
        (out / 'build-input.toml').write_text('[build]\n', encoding='utf-8')

        def bridge(dtb, board, *, unique_chip_id, data, trust, addon, root_policies):
            nonlocal bridge_bytes
            O.require(not calls and board is ctx.board, 'Bridge must run once on actual Context board')
            O.require(Path(dtb).resolve().is_relative_to(out) and Path(dtb).is_file(), 'Bridge DTB outside new work')
            kwargs = dict(unique_chip_id=unique_chip_id, data=data, trust=trust, addon=addon, root_policies=root_policies)
            O.require(unique_chip_id == seed and (data, trust, addon, root_policies) ==
                      ('data' in input_paths, 'trust' in input_paths, 'addon' in input_paths, bool(policy)),
                      'Bridge identity/keyword mismatch')
            calls.append({'dtb_sha256': O.sha(Path(dtb).read_bytes()),
                          'board_sha256': O.sha(O.canonical(board)), 'keywords_sha256': O.sha(O.canonical(kwargs))})
            # The reviewed generator has its own independent private devicetree namespace.
            O.generate_candidate(base, dtb, board, kwargs, out / 'adt-generation', enabled, reuse,
                                 artifact_binding=artifact)
            bridge_bytes = (out / 'adt-generation/final.adt').read_bytes()
            return bridge_bytes

        with private_payload(base, blobs, bridge) as modules:
            args = namespace(out, soc, seed, input_paths)
            ctx = modules['config'].Context(args)
            O.require(ctx.root == base, 'Private Context root mismatch')
            check_context(ctx, out, soc)
            ctx.refuse_example()
            original_board_sha = O.sha(O.canonical(ctx.board))
            profile_files = {str(p): O.sha(p.read_bytes()) for p in ctx.profile_files}
            fallback = ctx.device / 'configs' / ctx.config_name
            ctx.board = copy.deepcopy(ctx.board)
            spec = ctx.board['payload']
            overrides = {k: {'before': spec.get(k), 'after': value} for k, value in
                         [('panic_screen', False), ('entry_probe_reset_delay', 0)]}
            spec.update(panic_screen=False, entry_probe_reset_delay=0)
            if continuation:
                # Runtime-board-only argument change for this profile; the official board is untouched.
                O.require(spec.get('kernel_args') == DIAGNOSTIC_ARGS,
                          'Continuation expects the frozen board kernel arguments before override')
                overrides['kernel_args'] = {'before': spec.get('kernel_args'), 'after': CONTINUATION_ARGS}
                spec['kernel_args'] = CONTINUATION_ARGS
            O.require(spec.get('loader', 'firmware') == 'firmware' and not spec.get('install') and
                      not args.skip_setup, 'Unsupported loader/install/skip_setup path')
            ctx.logs.mkdir(parents=True)
            O.write_json(out / 'runtime-board.json', ctx.board)
            O.write_json(out / 'overrides.json', overrides)
            O.require(all(not p.exists() for p in modules['payload'].paths(ctx)) and
                      not (ctx.work / 'payload/stage').exists(), 'Payload stage/image/report already exists')
            policy = spec.get('root_policies')
            if policy:
                policy = modules['util'].expand(policy.format(tree=ctx.tree, out=ctx.work))
                expected['Payloads/kernel.macho.vroot'] = policy.read_bytes()
            line = modules['payload'].check_args(spec.get('kernel_args', []))
            check_profile_arguments(profile, spec.get('kernel_args'), args.kernel_arg)
            O.require(not any(arg.startswith('native-ufs-root=') for arg in spec.get('kernel_args', [])),
                      'Native-root/PMGR path not in this wrapper brief')
            image = modules['payload'].build(ctx, kernel=prepared_path)
            O.require(len(calls) == 1 and bridge_bytes is not None, 'Bridge did not execute exactly once')
            O.require(not ctx.tree.exists() and not ctx.config_path.exists() and not ctx.state_path.exists(),
                      'Unexpected setup/tree/state write')
            expected['Payloads/kernel.macho.adt'] = bridge_bytes
            # Formal generator creates the menu. Read it from its actual stage-independent FAT below,
            # then validate every field/reference, not by copying an old TOML into the candidate.
            extraction = out / 'extracted'
            extraction.mkdir()
            capture(['mcopy', '-s', '-i', image, '::/EFI', extraction], out / 'extract-command.json')
            expected['unixnu.toml'] = (extraction / 'EFI/UniXNU/unixnu.toml').read_bytes()
            owner_record = out / 'adt-generation/record.json' if enabled else None
            hashes = verify_extracted(extraction, expected, bridge_bytes, owner_record, ctx, line, artifact if enabled else None)
            adt_facts = diagnostic_adt(bridge_bytes) if (diagnostic or continuation) else None
            formal_report = O.read_json(ctx.work / 'payload/payload.json')
            O.require(formal_report['kernel_sha256'] == kernel_sha256 == formal_report['payload_kernel_sha256']
                      and formal_report['adt_sha256'] == O.sha(bridge_bytes) and
                      formal_report['payload_sha256'] == O.sha(image.read_bytes()) and
                      formal_report['kernel_args'] == line and not formal_report['panic_screen'] and
                      not formal_report['skip_setup'], 'Formal payload report binding mismatch')
            for field, filename in [('trust_cache_sha256', 'kernel.macho.trustcache'),
                                     ('gpu_addon_sha256', 'kernel.macho.gpuaddon'),
                                     ('data_ramdisk_sha256', 'scratch-data.img')]:
                content = expected.get('Payloads/' + filename)
                O.require(formal_report[field] == (O.sha(content) if content is not None else None),
                          'Formal optional-input binding mismatch: ' + field)
            report = {'status': 'self-checked', 'readback_complete': True, 'device_release': False,
                      'profile': profile, 'diagnostic_only': diagnostic, 'artifact_binding': artifact,
                      'new_kernel_initializer_validated': False, 'diagnostic_adt_facts': adt_facts,
                      'prepared_kernel_sha256': kernel_sha256, 'payload_sha256': O.sha(image.read_bytes()),
                      'payload_path': str(image), 'payload_bytes': image.stat().st_size,
                      'adt_sha256': O.sha(bridge_bytes), 'owner_record_sha256':
                      O.sha(owner_record.read_bytes()) if owner_record else None,
                      'owner_legacy_kernel_pin': O.KERNEL_SHA, 'future_probe_hash_approved': False,
                      'input_hashes': {k: O.sha(v) for k, v in expected.items()}, 'fat_hashes': hashes,
                      'bridge_calls': calls, 'enabled': enabled, 'base_revision': O.REVISION,
                      'dependencies': dict(PINS), 'soc_revision': SOC_REVISION,
                      'overrides': overrides, 'work': str(ctx.work), 'config_name': ctx.config_name,
                      'context': {'device': str(ctx.device), 'schema_version': ctx.schema_version,
                                  'name': ctx.name, 'os_profile': OS_PROFILE,
                                  'profile_roots': {k: str(v) for k, v in ctx.profile_roots.items()},
                                  'original_board_sha256': original_board_sha,
                                  'runtime_board_sha256': O.sha(O.canonical(ctx.board)),
                                  'profile_file_hashes': profile_files,
                                  'defconfig_fallback_sha256': O.sha(fallback.read_bytes()),
                                  'config_path': str(ctx.config_path), 'tree_assembled': False},
                      'config_fallback_preserved': not ctx.config_path.exists(),
                      'namespace_fields': sorted(vars(args)), 'authentication': 'NOT REACHED'}
            if continuation:
                report.update(continuation_only=True, execution_mode='continue-original',
                              pmap_ret_restored=True, observer_unhooked=True, renderer_retained=True,
                              effective_kernel_args=line, continuation=continuation_facts)
                O.write_json(out / 'continuation.json', continuation_facts)
        O.write_json(out / 'payload-record.json', report)  # Success only after actual FAT readback + cleanup.
        return report
    except Exception as error:
        O.write_json(out / 'failure.json', {'status': 'failed', 'failure_type': type(error).__name__,
                                          'bridge_calls': len(calls), 'device_release': False})
        raise
