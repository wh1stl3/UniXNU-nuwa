"""Root-window geometry preview and declared launch-service contracts.

No filesystem image is assembled, seed synthesized, job enabled or program run.
UDIF format reference: UniXNU 0fc0fc1f9ddd0fbd4787738afef38667df5e0a95,
scripts/unixnu/udif.py. This reader validates metadata, not decoded payloads.
"""
import hashlib, plistlib, posixpath, struct


def plist_value(value):
    if isinstance(value, bytes):
        return dict(plist_type='data', bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
    if isinstance(value, plistlib.UID):
        return dict(plist_type='UID', value=value.data)
    if hasattr(value, 'isoformat'):
        return dict(plist_type='date', value=value.isoformat())
    if isinstance(value, dict):
        return {k:plist_value(v) for k,v in value.items()}
    if isinstance(value, list):
        return [plist_value(v) for v in value]
    return value


def need(ok, message):
    if not ok:
        raise ValueError(message)


def geometry(path):
    size = path.stat().st_size
    need(size >= 512, 'Image too short')
    with path.open('rb') as image:
        image.seek(size-512); trailer = image.read(512)
        if trailer[:4] != b'koly':
            need(size % 512 == 0, 'Raw disk sector alignment')
            return dict(format='raw_disk_without_koly', stored_bytes=size, raw_bytes=size,
                        decoded=False, geometry_only=True, footer_sha256=hashlib.sha256(trailer).hexdigest())
        version, headersize = struct.unpack_from('>II', trailer, 4)
        need(version == 4 and headersize == 512, 'Unsupported UDIF trailer')
        fork, fork_size = struct.unpack_from('>QQ', trailer, 24)
        at, length = struct.unpack_from('>QQ', trailer, 216)
        sectors = struct.unpack_from('>Q', trailer, 492)[0]
        need(0 < sectors <= (1 << 48) and 0 < length <= 32*1024*1024, 'UDIF metadata size')
        need(at+length <= size-512 and fork+fork_size <= size-512, 'UDIF file extent')
        image.seek(at); metadata = image.read(length); need(len(metadata) == length, 'UDIF plist truncated')
    obj = plistlib.loads(metadata); tables = obj.get('resource-fork', {}).get('blkx', [])
    need(0 < len(tables) <= 1024, 'UDIF blkx table count'); chunks = []
    for table in tables:
        raw = table['Data']; need(len(raw) >= 204 and raw[:4] == b'mish', 'UDIF mish header')
        first, = struct.unpack_from('>Q', raw, 8); base, = struct.unpack_from('>Q', raw, 24)
        count, = struct.unpack_from('>I', raw, 200)
        need(count <= 1000000 and 204+count*40 <= len(raw), 'UDIF chunk table extent')
        for i in range(count):
            kind, reserved, sector, n, offset, stored = struct.unpack_from('>IIQQQQ', raw, 204+i*40)
            if kind in (0x7ffffffe, 0xffffffff):
                continue
            need(kind in (0, 1, 2, 0x80000005, 0x80000006, 0x80000007) and n > 0, 'Unsupported UDIF chunk')
            need((first+sector+n) <= sectors, 'UDIF logical extent')
            if kind not in (0, 2):
                need(stored > 0 and base+offset+stored <= fork_size, 'UDIF stored extent')
            if kind == 1:
                need(stored == n*512, 'UDIF raw chunk length')
            chunks.append(dict(start=(first+sector)*512, bytes=n*512, kind=hex(kind), stored_bytes=stored))
    position = 0; kinds = {}
    for chunk in sorted(chunks, key=lambda v: v['start']):
        need(chunk['start'] == position, 'UDIF logical gap or overlap')
        position += chunk['bytes']; kinds[chunk['kind']] = kinds.get(chunk['kind'], 0)+1
    need(position == sectors*512, 'UDIF disk coverage differs')
    return dict(format='UDIF', stored_bytes=size, raw_bytes=sectors*512, chunks=len(chunks), chunk_kinds=kinds,
                footer_sha256=hashlib.sha256(trailer).hexdigest(), plist_sha256=hashlib.sha256(metadata).hexdigest(),
                decoded=False, geometry_only=True)


def windows(components, capacity=None):
    need(0 < len(components) <= 31, 'Manifest window count')
    position = 1 << 20; result = []; names = set()
    for item in components:
        name = item['name']; size = item['raw_bytes']
        need(isinstance(name, str) and name.isascii() and 0 < len(name) < 32 and '/' not in name and name not in names, 'Manifest window name')
        need(isinstance(size, int) and 0 < size <= 1 << 60 and size % 512 == 0, 'Window sector geometry')
        names.add(name); result.append(dict(name=name, offset=position, raw_bytes=size, block_size=512, read_only=True,
                                           decoded_sha256=None, source_component=item['component']))
        position = (position+size+(1 << 20)-1)//(1 << 20)*(1 << 20)
    if capacity is not None:
        need(isinstance(capacity, int) and capacity >= position, 'Target capacity insufficient')
    return dict(manifest='SHNGROOT v1', image_bytes=position, windows=result, target_capacity_bytes=capacity,
                capacity_fit=None if capacity is None else True, manifest_ready=False, deployable=False,
                unresolved=['Decoded raw-byte SHA256 for UDIF windows','nuwa storage provider and root UUID matching','Target geometry and Data/log reservations'])


def jobs(obj, trail=()):
    need(len(trail) <= 12, 'Launch config depth')
    if not isinstance(obj, dict):
        return []
    if any(k in obj for k in ('Label','Program','ProgramArguments','BundleProgram')):
        return [(trail, obj)]
    return [entry for key, value in obj.items() if isinstance(value, dict) for entry in jobs(value, trail+(str(key),))]


def identities(text, group=False):
    records = {}; rejected = 0
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        fields = line.split(':')
        try:
            need(len(fields) >= (4 if group else 7), 'Identity fields')
            name = fields[0]; uid = int(fields[2]); gid = uid if group else int(fields[3])
            need(name and -(1 << 31) <= uid < (1 << 32) and -(1 << 31) <= gid < (1 << 32) and name not in records, 'Identity values')
            uid &= 0xffffffff; gid &= 0xffffffff
            records[name] = dict(name=name, gid=gid) if group else dict(name=name, uid=uid, gid=gid, home=fields[5], shell=fields[6])
        except (ValueError, IndexError):
            rejected += 1
    return dict(records=records, rejected_lines=rejected)


def contract(obj):
    records = []; providers = {}; path_refs = []; conditions = []
    for trail, job in jobs(obj):
        args = job.get('ProgramArguments', []); program = job.get('Program') or (args[0] if isinstance(args, list) and args else None)
        need(isinstance(args, list), 'ProgramArguments container type')
        need(program is None or isinstance(program, str), 'Program type')
        label = job.get('Label'); identifier = '/'.join(trail)
        mach = job.get('MachServices', {}); need(isinstance(mach, dict), 'MachServices must be dictionary')
        event = job.get('LaunchEvents', {}); need(isinstance(event, dict), 'LaunchEvents must be dictionary')
        selected = {k:job[k] for k in ('RunAtLoad','KeepAlive','Disabled','UserName','GroupName','LimitLoadToSessionType','ProcessType','LaunchOnlyOnce','EnableTransactions','POSIXSpawnType') if k in job}
        records.append(dict(id=identifier, label=label, program=program, declared=selected,
                            non_string_arguments=[dict(index=i,type=type(v).__name__,value=plist_value(v)) for i,v in enumerate(args) if not isinstance(v,str)],
                            argument_expansion_resolved=all(isinstance(v,str) for v in args),
                            environment_keys=sorted(job.get('EnvironmentVariables', {})),
                            mach_services=list(mach), launch_event_streams=list(event),
                            normalized_job_sha256=hashlib.sha256(plistlib.dumps(job, fmt=plistlib.FMT_BINARY, sort_keys=True)).hexdigest(),
                            enabled_for_deployment=False))
        for name, flags in mach.items():
            providers.setdefault(name, []).append(dict(job=identifier, label=label, declaration=flags))
        def add(path, role):
            if isinstance(path, str):
                path_refs.append(dict(job=identifier, label=label, path=path, absolute=path.startswith('/'), role=role))
        for key in ('WorkingDirectory','RootDirectory','StandardOutPath','StandardErrorPath'):
            if key in job:
                add(job[key], key)
        for key in ('WatchPaths','QueueDirectories'):
            need(isinstance(job.get(key, []), list), 'Path array type')
            for path in job.get(key, []):
                add(path, key)
        keep = job.get('KeepAlive')
        if isinstance(keep, dict):
            for path in keep.get('PathState', {}):
                add(path, 'KeepAlive.PathState')
            for other, state in keep.get('OtherJobEnabled', {}).items():
                conditions.append(dict(job=identifier, other_label=other, state=state, kind='KeepAlive.OtherJobEnabled', startup_dependency=False))
        def socket_paths(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'SockPathName':
                        add(item, 'Socket.SockPathName')
                    else:
                        socket_paths(item)
            elif isinstance(value, list):
                for item in value:
                    socket_paths(item)
        socket_paths(job.get('Sockets', {}))
    return dict(jobs=records, providers=providers, duplicate_service_declarations={k:v for k,v in providers.items() if len(v)>1},
                path_references=path_refs, explicit_job_conditions=conditions,
                inference='MachServices lists providers, not consumers or a startup topological order')
