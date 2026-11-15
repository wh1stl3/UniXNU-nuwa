"""Device-owned, opt-in host ADT experiment; no payload/device entry point."""
import ast
import copy
import hashlib
import json
import secrets
import struct
import subprocess
import sys
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = '693f5d9cae8a408dd18b39f3f9fdc4228c934241'
SOURCE_SHA = '06043e034b5ac7ee6fe0a71bb6ee9fefa75e8a53609a7fa6810dfcd0c83e9c75'
UTIL_SHA = '1f6efa81051d67f7225783958f1f8e86a38a7d4e538299ce6aa639b3cb4a759d'
KERNEL_SHA = 'fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd'
DOMAIN = 'nuwa.owner-defined-boot-artifact.bnch.v1'
KEYWORDS = ('unique_chip_id', 'data', 'trust', 'addon', 'root_policies')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    # Preserve parsed table order: it affects the formal serializer's output.
    return json.dumps(obj, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'Duplicate JSON key: ' + key)
        out[key] = value
    return out


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_pairs)


def write_json(path, obj):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n')


def git(base, *args):
    return subprocess.check_output(['git', '-C', str(base), *args])


def verified_sources(base):
    base = Path(base).resolve(strict=True)
    require(git(base, 'rev-parse', 'HEAD').decode().strip() == REVISION, 'Base revision drift')
    blobs = {}
    for filename, pin in [('devicetree.py', SOURCE_SHA), ('util.py', UTIL_SHA)]:
        relative = 'scripts/unixnu/' + filename
        path = base / relative
        require(path.resolve(strict=True) == path, 'Symlinked base source')
        raw = path.read_bytes()  # These exact bytes are hashed, parsed and compiled.
        require(sha(raw) == pin, 'Base source SHA drift: ' + filename)
        committed = git(base, 'show', REVISION + ':' + relative)
        # Windows checkout may use CRLF, while Git's immutable blob uses LF.
        require(raw.replace(b'\r\n', b'\n') == committed.replace(b'\r\n', b'\n'),
                'Base source differs from revision: ' + filename)
        blobs[filename] = raw
    return base, blobs


def manifest_properties(value):
    require(isinstance(value, list), 'Manifest input requires a list')
    require(value == [] or (len(value) == 1 and type(value[0]) is tuple and
            len(value[0]) == 2 and value[0][0] == 'BNCH' and
            type(value[0][1]) is bytes and len(value[0][1]) == 48),
            'Only empty manifest or unique BNCH bytes48 allowed')
    return list(value)


def adapt(raw):
    original = ast.parse(raw)
    changed = copy.deepcopy(original)
    functions = [n for n in changed.body if isinstance(n, ast.FunctionDef) and n.name == 'generate']
    require(len(functions) == 1, 'AST generate count drift')
    assignments = [n for n in functions[0].body if isinstance(n, ast.Assign) and
                   len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and
                   n.targets[0].id == 'children']
    require(len(assignments) == 1, 'AST children assignment drift')
    expected = ast.parse("[node('chosen', chosen, [node('memory-map', mappings), node('manifest-properties')])]",
                         mode='eval').body
    dump = lambda n: ast.dump(n, include_attributes=False)
    require(dump(assignments[0].value) == dump(expected), 'AST chosen structure drift')
    matches = [n for n in ast.walk(functions[0]) if isinstance(n, ast.Call) and
               isinstance(n.func, ast.Name) and n.func.id == 'node' and
               len(n.args) >= 1 and isinstance(n.args[0], ast.Constant) and
               n.args[0].value == 'manifest-properties']
    require(len(matches) == 1 and len(matches[0].args) == 1 and not matches[0].keywords,
            'AST manifest call drift')
    matches[0].args.append(ast.Name(id='_owner_manifest_properties', ctx=ast.Load()))
    normalized = copy.deepcopy(changed)
    for n in ast.walk(normalized):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'node' and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'manifest-properties':
            require(len(n.args) == 2 and isinstance(n.args[1], ast.Name) and
                    n.args[1].id == '_owner_manifest_properties', 'AST adapter delta drift')
            n.args.pop()
    require(dump(normalized) == dump(original), 'AST change outside approved argument')
    return ast.fix_missing_locations(changed)


def check_imports(tree, util=False):
    allowed = {'hashlib', 'os', 'shutil', 'subprocess', 'sys', 'pathlib'} if util else {
        'dataclasses', 'pathlib', 'os', 're', 'struct', 'uuid', 'zlib'}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            require(all(a.name in allowed for a in n.names), 'Unexpected dependency import')
        elif isinstance(n, ast.ImportFrom):
            if not util and n.level == 1 and n.module == 'util':
                require([a.name for a in n.names] == ['Error', 'run', 'tool'], 'util import drift')
            elif not util and n.level == 1 and n.module == 'profiles':
                # Only compile_hardware contains this import. It is deliberately not available.
                require([a.name for a in n.names] == ['resolve_path'], 'profiles import drift')
            else:
                require(n.level == 0 and n.module in allowed, 'Unexpected relative dependency')


@contextmanager
def generator(base, properties, modified=True):
    properties = manifest_properties(properties)
    base, blobs = verified_sources(base)
    tree = ast.parse(blobs['devicetree.py'])
    util_tree = ast.parse(blobs['util.py'])
    check_imports(tree)
    check_imports(util_tree, util=True)
    if modified:
        tree = adapt(blobs['devicetree.py'])
    # UUID is namespace isolation only, not a nonce/epoch. No official module name touched.
    package = '_nuwa_owner_adt_' + uuid.uuid4().hex
    names = [package, package + '.util', package + '.devicetree']
    require(all(n not in sys.modules for n in names), 'Private namespace collision')
    modules = [types.ModuleType(n) for n in names]
    modules[0].__path__ = []  # No filesystem fallback for further relative dependencies.
    try:
        for n, module in zip(names, modules):
            sys.modules[n] = module
        for filename, module, code in [('util.py', modules[1], util_tree),
                                       ('devicetree.py', modules[2], tree)]:
            module.__file__ = str(base / 'scripts/unixnu' / filename)
            module.__package__ = package
            if filename == 'devicetree.py':
                module._owner_manifest_properties = properties
            exec(compile(code, module.__file__, 'exec'), module.__dict__)
        require(modules[2].Error is modules[1].Error, 'Relative util origin mismatch')
        yield modules[2]
    finally:
        for n, module in zip(names, modules):
            require(sys.modules.get(n) is module, 'Private namespace was replaced')
            del sys.modules[n]


def validate_config(config, kwargs):
    require(type(config) is dict and type(kwargs) is dict and set(kwargs) == set(KEYWORDS),
            'All five explicit generate keywords required')
    require(kwargs['unique_chip_id'] is None or type(kwargs['unique_chip_id']) is str,
            'Identity requires string or null')
    require(all(type(kwargs[k]) is bool for k in KEYWORDS[1:]), 'Generate flags must be bool')
    platform = config.get('adt', {})
    require(type(platform) is dict, 'ADT configuration table required')
    kinds = ('string', 'strings', 'u32', 'u64', 'bytes')

    def table(value, chosen=False, root=False):
        require(type(value) is dict, 'Typed node table required')
        keys = set()
        automatic = {'name'}
        if root:
            automatic |= {'#address-cells', '#size-cells'}
        if chosen:
            automatic |= {'random-seed', 'dram-base', 'dram-size', 'nvram-bank-size',
                          'nvram-bank-count', 'nvram-current-bank', 'nvram-proxy-data',
                          'unique-chip-id', 'chip-id', 'darwinboot-memory-size',
                          'root-matching', 'ephemeral-storage', 'text-fixups'}
        for kind, props in value.items():
            require(kind in kinds and type(props) is dict, 'Unexpected typed table or chosen child')
            for key in props:
                require(type(key) is str and key not in keys and key not in automatic,
                        'Duplicate/automatic typed property: ' + str(key))
                keys.add(key)

    def configured_node(value):
        require(type(value) is dict, 'Configured node table required')
        table({k: v for k, v in value.items() if k in kinds})
        for key, val in value.items():
            if key not in kinds:
                configured_node(val)

    table(platform.get('chosen', {}), chosen=True)
    table(platform.get('root', {}), root=True)
    for key in ('defaults', 'options', 'product', 'buttons'):
        if key in platform:
            configured_node(platform[key])


def parse(raw):
    """Ordered strict ADT parse: reject duplicates before any dictionary conversion."""
    require(0 < len(raw) <= 16 * 1024 * 1024, 'Invalid ADT size')

    def read(at, depth):
        require(depth <= 64 and at + 8 <= len(raw), 'ADT depth/header')
        count, children = struct.unpack_from('<II', raw, at)
        require(count <= 4096 and children <= 4096, 'ADT count limit')
        at += 8
        props, keys = [], set()
        for _ in range(count):
            require(at + 36 <= len(raw), 'Truncated ADT property')
            keyraw, length = struct.unpack_from('<32sI', raw, at)
            key = keyraw.split(b'\0')[0].decode('ascii')
            require(key and key not in keys and length < 0x80000000, 'ADT duplicate/flagged property')
            at += 36
            end = at + ((length + 3) & ~3)
            require(end <= len(raw) and not any(raw[at + length:end]), 'ADT property bounds/padding')
            props.append((key, raw[at:at + length]))
            keys.add(key)
            at = end
        names = [v for k, v in props if k == 'name']
        require(len(names) == 1 and names[0].endswith(b'\0') and b'\0' not in names[0][:-1],
                'ADT node name')
        name = names[0][:-1].decode('ascii')
        nodes, seen = [], set()
        for _ in range(children):
            child, at = read(at, depth + 1)
            require(child[0] not in seen, 'ADT duplicate child')
            seen.add(child[0])
            nodes.append(child)
        return (name, props, nodes), at

    tree, end = read(0, 0)
    require(end == len(raw) and tree[0] == 'device-tree', 'ADT trailing bytes/root')
    return tree


def find(tree, path):
    for part in path.strip('/').split('/'):
        matches = [c for c in tree[2] if c[0] == part]
        require(len(matches) == 1, 'Missing/duplicate ADT path: ' + path)
        tree = matches[0]
    return tree


def inspect_adt(raw, token=None):
    tree = parse(raw)
    chosen = find(tree, '/chosen')
    props = dict(chosen[1])
    require(props.get('mix-n-match-prevention-status') == bytes(4), 'AMNM must be u32=0')
    require(len(props.get('random-seed', b'')) == 256, 'random-seed must be 256 bytes')
    manifest = find(tree, '/chosen/manifest-properties')
    expected = [('name', b'manifest-properties\0')]
    if token is not None:
        manifest_properties([('BNCH', token)])
        expected.append(('BNCH', token))
    require(manifest[1] == expected and not manifest[2], 'Unexpected manifest properties/token')

    def walk(node):
        require(all(k != 'CHMH' for k, _ in node[1]), 'CHMH forbidden')
        require(node is manifest or all(k != 'BNCH' for k, _ in node[1]), 'BNCH outside manifest node')
        for child in node[2]:
            walk(child)
    walk(tree)
    return tree


def semantic_equal(left, right, allow_bnch=False):
    def normalize(raw):
        tree = parse(raw)
        chosen = find(tree, '/chosen')
        chosen[1][:] = [(k, bytes(256) if k == 'random-seed' else v) for k, v in chosen[1]]
        if allow_bnch:
            manifest = find(tree, '/chosen/manifest-properties')
            manifest[1][:] = [(k, v) for k, v in manifest[1] if k != 'BNCH']
        return tree
    require(normalize(left) == normalize(right), 'Unexpected ordered ADT semantic difference')


def reserve(path):
    path = Path(path).absolute()
    root = (ROOT / 'out').resolve()
    require(path.resolve().is_relative_to(root) and path.resolve() != root,
            'Fresh output must be below device out/')
    # Reject symlinked paths even if they resolve back inside out/.
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Output symlink forbidden')
    require(not path.exists(), 'Output already exists')
    relative = str(path.relative_to(ROOT))
    require(subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', '--', relative]).returncode == 0,
            'Output must be Git ignored')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()  # Exclusive reservation, no exist_ok.
    return path


def binding(dtb, config, kwargs, artifact_binding=None):
    result = {'base_revision': REVISION, 'generator_sha256': SOURCE_SHA, 'util_sha256': UTIL_SHA,
            'kernel_sha256': KERNEL_SHA, 'dtb_sha256': sha(dtb),
            'config_sha256': sha(canonical(config)), 'keywords_sha256': sha(canonical(kwargs))}
    if artifact_binding is not None:
        require(type(artifact_binding) is dict and set(artifact_binding) == {'profile', 'kernel_sha256', 'kernel_bytes'}
                and type(artifact_binding['profile']) is str and artifact_binding['profile']
                and type(artifact_binding['kernel_sha256']) is str
                and len(artifact_binding['kernel_sha256']) == 64
                and all(c in '0123456789abcdef' for c in artifact_binding['kernel_sha256'])
                and type(artifact_binding['kernel_bytes']) is int and artifact_binding['kernel_bytes'] > 0,
                'Invalid artifact evidence binding')
        # Schema2 separates historical initializer evidence from the actual consuming artifact.
        # The caller's fixed profile gate, not this evidence field, qualifies the kernel.
        result['generator_validation_baseline_kernel_sha256'] = result.pop('kernel_sha256')
        result['artifact'] = copy.deepcopy(artifact_binding)
    return result


def load_record(path, expected=None):
    path = Path(path).resolve(strict=True)
    require(path.is_relative_to((ROOT / 'out').resolve()), 'Record outside device out/')
    record = read_json(path)
    version = record.get('schema_version', 1)
    require(type(version) is int and version in (1, 2) and
            type(record.get('input_binding')) is dict and
            (('artifact' in record.get('input_binding', {})) == (version == 2)),
            'Unsupported/inconsistent owner record schema')
    if version == 2:
        binding(b'', {}, {}, record['input_binding']['artifact'])  # Validate evidence types, no token draw.
        require(record['input_binding'].get('generator_validation_baseline_kernel_sha256') == KERNEL_SHA
                and 'kernel_sha256' not in record['input_binding'], 'Ambiguous schema2 kernel baseline')
    require(record.get('domain') == DOMAIN and record.get('status') in ('reserved', 'generated'),
            'Record incomplete/failed/wrong domain')
    if expected is not None:
        require(record['input_binding'] == expected, 'Record actual input binding mismatch')
    require(type(record.get('token_hex')) is str and len(record['token_hex']) == 96,
            'Record token encoding/length')
    token = bytes.fromhex(record['token_hex'])
    manifest_properties([('BNCH', token)])
    return record, token


def generate_candidate(base, dtb_path, config, kwargs, output, enabled=False, reuse=None, *, artifact_binding=None):
    require(enabled or reuse is None, 'Experiment record supplied while disabled')
    validate_config(config, kwargs)
    # Snapshot caller-owned objects and bytes; bind content rather than source filenames.
    config, kwargs = copy.deepcopy(config), copy.deepcopy(kwargs)
    dtb = Path(dtb_path).read_bytes()
    inputs = binding(dtb, config, kwargs, artifact_binding)
    with generator(base, []) as module:
        pass  # Reject source/revision/AST drift before reserving or drawing a token.
    previous = load_record(reuse, inputs) if reuse else None
    out = reserve(output)
    record = None
    try:
        if enabled:
            # Reserve record before the sole token draw. A failure never redraws or overwrites.
            record_path = out / 'record.json'
            with record_path.open('x', encoding='utf-8') as stream:
                record = {'domain': DOMAIN, 'status': 'reserved', 'input_binding': inputs,
                          'reused_from': str(Path(reuse).resolve()) if reuse else None}
                if artifact_binding is not None:
                    record['schema_version'] = 2
                json.dump(record, stream)
            token = previous[1] if previous else secrets.token_bytes(48)
            record['token_hex'] = token.hex()
            # This is the already reserved record, not a fresh-record fallback.
            record_path.write_bytes(canonical(record) + b'\n')
        else:
            token = None
        snapshot = out / 'input.dtb'
        with snapshot.open('xb') as stream:
            stream.write(dtb)
        write_json(out / 'config.json', config)
        write_json(out / 'keywords.json', kwargs)
        # Same DTB snapshot, parsed config, identity and all five keywords. No RNG substitution.
        with generator(base, [], modified=False) as formal:
            baseline = formal.generate(snapshot, copy.deepcopy(config), **kwargs)
        with generator(base, []) as disabled:
            control = disabled.generate(snapshot, copy.deepcopy(config), **kwargs)
        inspect_adt(baseline)
        inspect_adt(control)
        semantic_equal(baseline, control)
        if enabled:
            with generator(base, [('BNCH', token)]) as adapted:
                final = adapted.generate(snapshot, copy.deepcopy(config), **kwargs)
            inspect_adt(final, token)
            semantic_equal(control, final, allow_bnch=True)
        else:
            final = control
        # No final output is published until all policy and ordered comparisons pass.
        for name, raw in [('formal.adt', baseline), ('disabled.adt', control), ('final.adt', final)]:
            with (out / name).open('xb') as stream:
                stream.write(raw)
        if record is not None:
            record.update(status='generated', final_adt_sha256=sha(final))
            record_path.write_bytes(canonical(record) + b'\n')
        report = {'status': 'self-checked', 'enabled': enabled, 'input_binding': inputs,
                  'final_adt_sha256': sha(final), 'formal_vs_disabled': 'ordered equal except random-seed256',
                  'enabled_vs_disabled': 'ordered equal except BNCH and random-seed256' if enabled else None,
                  'payload_integration': False, 'authentication': 'NOT REACHED'}
        write_json(out / 'generation.json', report)
        return report
    except Exception as error:
        if record is not None:
            record.update(status='failed', failure_type=type(error).__name__)
            (out / 'record.json').write_bytes(canonical(record) + b'\n')
        write_json(out / 'failure.json', {'status': 'failed', 'failure_type': type(error).__name__})
        raise
