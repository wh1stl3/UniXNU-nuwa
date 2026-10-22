"""Read-only nuwa DT / pinned firmware mapping audit. No image generation."""
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
FW = Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware')
DT = Path('D:/Code/PortingiOSWithUniXNU/device/observed/nuwa-live.dtb')


def properties(data):
    magic, total, off, strings, reserve, version, last, cpu, string_size, size = struct.unpack_from('>10I', data)
    if magic != 0xd00dfeed or not (40 <= total <= len(data)) or off + size > total or strings + string_size > total:
        raise ValueError('Invalid FDT header/bounds')
    names = data[strings:strings + string_size]
    end, stack, nodes = off + size, [], {}
    while off + 4 <= end:
        token = struct.unpack_from('>I', data, off)[0]; off += 4
        if token == 1:
            stop = data.index(b'\0', off, end)
            stack.append(data[off:stop].decode()); off = (stop + 4) & ~3
            nodes['/' + '/'.join(stack[1:])] = {}
        elif token == 2:
            if not stack: raise ValueError('FDT stack underflow')
            stack.pop()
        elif token == 3:
            length, name_at = struct.unpack_from('>II', data, off); off += 8
            if not stack or off + length > end or name_at >= len(names): raise ValueError('Invalid property')
            name = names[name_at:names.index(b'\0', name_at)].decode()
            nodes['/' + '/'.join(stack[1:])][name] = data[off:off + length]
            off = (off + length + 3) & ~3
        elif token == 4: pass
        elif token == 9:
            if stack: raise ValueError('Unclosed FDT nodes')
            return nodes
        else: raise ValueError('Unknown FDT token')
    raise ValueError('Missing FDT terminator')


def main():
    raw = DT.read_bytes(); nodes = properties(raw)
    model = nodes['/'].get('model', b'').rstrip(b'\0').decode()
    compatible = nodes['/'].get('compatible', b'').rstrip(b'\0').decode().split('\0')
    if 'nuwa' not in model.lower() or not any('kalama' in c for c in compatible):
        raise ValueError('Reference DT is not nuwa/kalama')
    path = FW / 'Platforms/Xiaomi/nuwaPkg/Library/MemoryMapLib/MemoryMapLib.c'
    pattern = r'\{"([^"]+)",\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+)\}'
    regions = [dict(name=n, start=int(a,16), end=int(a,16)+int(s,16), hob=h, resource=r, memory_type=t, attributes=v)
               for n,a,s,h,r,c,t,v in re.findall(pattern,path.read_text())]
    if len(regions) != 41: raise ValueError('Pinned map shape changed')
    chosen = nodes.get('/chosen', {})
    initrd = {}
    for name in ('linux,initrd-start','linux,initrd-end'):
        value = chosen.get(name)
        if value is not None and len(value) not in (4,8): raise ValueError('Invalid initrd property')
        initrd[name] = int.from_bytes(value, 'big') if value else None
    start,end = initrd.values()
    overlaps=[]
    if start is not None and end is not None and end>start:
        overlaps=[r for r in regions if r['start']<end and r['end']>start]
    current = ROOT / 'out/trial-boot/nuwa-android-live.dtb'
    current_observation = None
    if current.is_file():
        live = current.read_bytes(); current_nodes = properties(live)
        if 'nuwa' not in current_nodes['/']['model'].decode().lower():
            raise ValueError('Current DT is not nuwa')
        current_chosen = current_nodes.get('/chosen', {})
        current_observation = dict(sha256=hashlib.sha256(live).hexdigest(),
            initrd={k:hex(int.from_bytes(current_chosen[k], 'big')) for k in initrd if k in current_chosen},
            scope='Original Android temporary boot only; not candidate firmware placement')
    sources=[path, FW/'Silicon/Silicium/SiliciumPkg/Library/MemoryInitPeiLib/MemoryInitPei.c',
             FW/'Silicon/Silicium/SiliciumPkg/Drivers/RamManagerDxe/RamManager.c',
             FW/'Silicon/Qualcomm/QcomPkg/Library/RamManagerLib/RamManager.c',
             FW/'Mu_Basecore/ArmPkg/Library/ArmPsciResetSystemLib/ArmPsciResetSystemLib.c']
    result=dict(scope='Archived Android DT and static firmware source only; not candidate ABL layout or runtime UEFI map',
                dt=dict(path=str(DT),sha256=hashlib.sha256(raw).hexdigest(),model=model,compatible=compatible),
                source_hashes=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources],
                initrd=initrd,initrd_overlapping_static_regions=overlaps,static_regions=regions,
                actual_candidate_dt_address=None,actual_candidate_initrd_address=None,
                current_android_observation=current_observation,
                archived_initrd_wholly_in_reserved_static_region=any(r['start']<=start and end<=r['end'] and r['memory_type']=='Reserv' for r in overlaps),
                archived_initrd_sector_aligned=(end-start)%512==0 if start is not None and end is not None else None,
                safe_to_boot=False,blockers=['Candidate ABL DT/initrd addresses unknown',
                'Publisher does not reserve initrd; RamManager can promote unregistered gaps to conventional memory',
                'SEC access to original DT needs mapping/lifetime evidence in candidate firmware'])
    out=ROOT/'reports/trial-boot-preflight/mapping.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(model=model,initrd=initrd,overlaps=overlaps,safe_to_boot=False),indent=2))


if __name__ == '__main__':
    main()
