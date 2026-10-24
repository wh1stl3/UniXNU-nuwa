"""Bind the entry-probe package to exact kernel patches and offline evidence."""
import hashlib, importlib.util, json, struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(data):return hashlib.sha256(data).hexdigest()
def report_path(relative):
    path=(ROOT/relative).resolve()
    if not path.is_relative_to(ROOT/'reports'):raise ValueError('Probe evidence must stay under reports')
    return path

def metadata(build):
    build=build.resolve();software=build.with_name('software.json')
    if not build.is_relative_to(ROOT/'reports'):raise ValueError('Probe build report path')
    return {name:dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path.read_bytes())) for name,path in (('build',build),('software',software))}

def validate(meta,kernel_sha):
    bound={}
    for name in ('build','software'):
        item=meta[name];raw=report_path(item['path']).read_bytes()
        if sha(raw)!=item['sha256']:raise ValueError('Probe report digest differs: '+name)
        bound[name]=json.loads(raw)
    build=bound['build'];software=bound['software'];candidate=(ROOT/build['candidate']['path']).resolve()
    if not candidate.is_relative_to(ROOT/'out'):raise ValueError('Probe candidate path')
    raw=candidate.read_bytes()
    if sha(raw)!=kernel_sha or kernel_sha!=build['candidate']['sha256'] or kernel_sha!=software['candidate_sha256']:raise ValueError('Probe candidate/evidence digest differs')
    if len(software['checks'])<16 or any(x['passed'] is not True for x in software['checks']):raise ValueError('Probe software checks incomplete')
    if software['instrumented'].get('stop')!='before-sctlr' or software['instrumented']['bad_memory']:raise ValueError('Probe did not reach pre-MMU stop')
    if build['loadable'] is not False or build['runtime_qualified'] is not False:raise ValueError('Diagnostic qualification flags changed')
    spec=importlib.util.spec_from_file_location('entry_builder',ROOT/'scripts/build-kernel-entry-probe.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    original=builder.INPUT.read_bytes()
    if sha(original)!=builder.EXPECTED or build['input_sha256']!=builder.EXPECTED:raise ValueError('Probe baseline changed')
    expected=bytearray(original)
    hooks={p['reason'] for p in build['patches'] if p['reason'].startswith('probe_')}
    if not {'probe_entry','probe_tables','probe_mmu'}<=hooks:raise ValueError('Required entry/tables/MMU hooks missing')
    # Two header edits, one branch per hooked site, the BCM NOP and sixteen early vectors.
    if len(build['patches'])!=2+len(hooks)+1+16:raise ValueError('Patch set shape differs from the recorded hook set')
    # The checks that carry a hook's evidence must actually be present: deleting
    # them and re-sealing the reports must not produce an acceptable package.
    names={c['name'] for c in software['checks']}
    required={'Entry blue band','Tables yellow band','Pre-MMU magenta band'}
    if 'probe_mmu_on' in hooks:required|={'Post-SCTLR hook executes to its replay point','Cyan post-MMU band'}
    if 'probe_arm_init' in hooks:required|={'arm_init hook executes to its replay point','White arm_init band'}
    if not required<=names:raise ValueError('Probe software checks missing: '+', '.join(sorted(required-names)))
    covered=set()
    for patch in build['patches']:
        off=patch['file_offset'];before=bytes.fromhex(patch['before']);after=bytes.fromhex(patch['after']);new=set(range(off,off+len(after)))
        if len(before)!=len(after) or new & covered or off<0 or off+len(after)>len(original) or original[off:off+len(before)]!=before:raise ValueError('Probe patch bounds, overlap or preimage differs')
        covered|=new;expected[off:off+len(after)]=after
    probe=build['probe'];offset=probe['file_offset']
    if offset!=builder.align(len(original)) or len(raw)!=offset+4096 or probe['segment_bytes']!=4096:raise ValueError('Probe page extent differs')
    payload=raw[offset:]
    if sha(payload)!=probe['sha256'] or raw[:len(original)]!=expected or any(raw[len(original):offset]):raise ValueError('Kernel has bytes outside recorded diagnostic changes')
    m=builder.macho(raw)
    if m['entry']!=builder.macho(original)['entry']:raise ValueError('Kernel original entry changed')
    segment=next(s for s in m['segments'] if s['name']=='__NUWA_PROBE')
    if segment['va']!=int(probe['va'],16) or segment['fileoff']!=offset or segment['size']!=4096:raise ValueError('Probe segment changed')
    bcm=next(p for p in build['patches'] if 'Suppress BCM' in p['reason'])
    if bcm['before']!='010000b9' or bcm['after']!='1f2003d5':raise ValueError('BCM correction differs')
    return dict(kernel_sha256=kernel_sha,patches=len(build['patches']),software_checks=len(software['checks']))
