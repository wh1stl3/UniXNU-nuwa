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
    paths=[('build',build),('software',software)]
    if json.loads(build.read_text()).get('probe_revision',0)>=21:
        paths += [(n,build.with_name(n+'.json')) for n in ('transparency','wfe','read-sites','loader','mapping')]
    if json.loads(build.read_text()).get('probe_revision',0)>=22:
        paths += [(n,build.with_name(n+'.json')) for n in ('transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb')]
    if json.loads(build.read_text()).get('probe_revision',0)>=23:
        paths += [('console-policy',build.with_name('console-policy.json'))]
    return {name:dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path.read_bytes())) for name,path in paths}

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
    if any(h.startswith('probe_dense_') for h in hooks):
        if build.get('probe_revision',0)<24:raise ValueError('Dense hooks require revision 24')
        from probe_bootstrap_sites import generate
        _,_,dense_sites,edges=generate(original,builder.macho(original),builder.backed)
        if build.get('dense_bootstrap',{}).get('edges')!=edges:raise ValueError('Dense edge catalogue differs from native calls')
        actual={(int(p['va'],16),p['reason']) for p in build['patches'] if p['reason'].startswith('probe_dense_')}
        if actual!=set(dense_sites):raise ValueError('Dense hook set incomplete')
    # The checks that carry a hook's evidence must actually be present: deleting
    # them and re-sealing the reports must not produce an acceptable package.
    names={c['name'] for c in software['checks']}
    required={'Entry blue band','Tables yellow band','Pre-MMU magenta band'}
    if 'probe_mmu_on' in hooks:required|={'Post-SCTLR hook executes to its replay point','Cyan post-MMU band'}
    if 'probe_arm_init' in hooks:required|={'arm_init hook executes to its replay point','White arm_init band'}
    if not required<=names:raise ValueError('Probe software checks missing: '+', '.join(sorted(required-names)))
    if 'probe_wfe_init' in hooks and build.get('probe_revision',0)<21:
        raise ValueError('Unsafe pre-v21 WFE hook revision (ADRP relocation)')
    if build.get('probe_revision',0)>=21:
        # These tests are mandatory for this revision, not optional attachments.
        for name in ('transparency','wfe','read-sites','loader','mapping'):
            if name not in meta: raise ValueError('Missing v21 evidence: '+name)
            raw_report=report_path(meta[name]['path']).read_bytes()
            if sha(raw_report)!=meta[name]['sha256']: raise ValueError('Probe report digest differs: '+name)
            evidence=json.loads(raw_report)
            if evidence.get('candidate_sha256')!=kernel_sha: raise ValueError('Probe evidence candidate differs: '+name)
            if name=='mapping':
                walks=[w for snap in evidence['snapshots'] for w in snap.get('walks',[])]
                if len(walks)!=6 or not all(w.get('mapped') is True for w in walks): raise ValueError('Probe mapping evidence incomplete')
                continue
            checks=evidence['cases'] if name=='loader' else evidence['checks']
            if not checks or any(c['passed'] is not True for c in checks): raise ValueError('Failed v21 evidence: '+name)
            actual_names={c['name'] for c in checks}
            if len(actual_names)!=len(checks): raise ValueError('Duplicate v21 check names: '+name)
            if name=='transparency':
                required_cases={h+': '+mode for h in hooks-{'probe_entry','probe_tables','probe_mmu','probe_mmu_on','probe_ttbr1','probe_ttbr0','probe_console_policy'}
                                for mode in ('first','repeat','no-video','count-saturated')}
                if actual_names!=required_cases: raise ValueError('Probe transparency cases incomplete')
            if name=='wfe' and actual_names!={'configure-init '+c for c in ('-v','-v wfe_events_sec=0','-v wfe_events_sec=19200','-v wfe_events_sec=2000000')}|{'v20 negative control reaches panic despite eventi=4'}:
                raise ValueError('Probe WFE cases incomplete')
            if name=='read-sites' and 'Every sampled data row has its own correct four-nibble field ID' not in actual_names:
                raise ValueError('Probe field ID evidence missing')
            if name=='loader' and actual_names!={'original','candidate','overlapping-probe','command-overrun','probe-file-overrun'}:
                raise ValueError('Probe loader cases incomplete')
    if {'probe_ttbr1','probe_ttbr0','probe_console_policy'} & hooks:
        if build.get('probe_revision',0)<22: raise ValueError('TTBR hooks require revision 22 evidence')
        for case in ('normal','occupied-probe','bad-topology','occupied-fb'):
            name='transition-'+case
            if name not in meta: raise ValueError('Missing transition evidence: '+case)
            report_raw=report_path(meta[name]['path']).read_bytes()
            if sha(report_raw)!=meta[name]['sha256']:raise ValueError('Transition digest differs')
            evidence=json.loads(report_raw)
            if evidence.get('candidate_sha256')!=kernel_sha or evidence.get('case')!=case:
                raise ValueError('Transition identity differs')
            if not evidence.get('checks') or any(c.get('passed') is not True for c in evidence['checks']):
                raise ValueError('Transition checks incomplete')
            required_transition={'TTBR1 call preserves GPR/SP/NZCV and native LR'}
            if case in ('normal','occupied-fb'):required_transition.add('TTBR0 call preserves GPR/SP/NZCV and native LR')
            if case=='normal':required_transition|={'Native cold path passes pmap probe after TTBR reconstruction','Code RO executable and data RW NX map exact probe physical pages',('Native cold path passes console and reaches kernel_bootstrap' if build.get('probe_revision',0)>=23 else 'Next stop preserved as console platform read, not probe fetch')}
            elif case=='occupied-fb':required_transition.add('Occupied framebuffer slot preserved and renderer disabled')
            else:required_transition.add('Rejects occupied or malformed tables without partial page-table edits')
            if {c['name'] for c in evidence['checks']}!=required_transition:
                raise ValueError('Transition cases incomplete')
    if 'probe_console_policy' in hooks:
        if build.get('probe_revision',0)<23 or 'console-policy' not in meta:raise ValueError('Console policy evidence missing')
        item=meta['console-policy'];payload=report_path(item['path']).read_bytes()
        if sha(payload)!=item['sha256']:raise ValueError('Console policy digest differs')
        evidence=json.loads(payload)
        if evidence.get('candidate_sha256')!=kernel_sha or any(c['passed'] is not True for c in evidence.get('checks',[])):
            raise ValueError('Console policy evidence differs')
        required_console={'shipped-missing-pram uses native DT lookup without BCM access','minimal-missing-pram uses native DT lookup without BCM access','present-pram uses native DT lookup without BCM access','Missing-pram path retains native screen initialization entry','Present-pram policy stops explicitly before console and old log access','Old candidate still reads unmapped BCM panic region'}
        if {c['name'] for c in evidence['checks']}!=required_console:raise ValueError('Console policy checks incomplete')
    covered=set()
    for patch in build['patches']:
        off=patch['file_offset'];before=bytes.fromhex(patch['before']);after=bytes.fromhex(patch['after']);new=set(range(off,off+len(after)))
        if len(before)!=len(after) or new & covered or off<0 or off+len(after)>len(original) or original[off:off+len(before)]!=before:raise ValueError('Probe patch bounds, overlap or preimage differs')
        covered|=new;expected[off:off+len(after)]=after
    probe=build['probe'];offset=probe['file_offset']
    if offset!=builder.align(len(original)) or probe['segment_bytes']%4096 or probe['segment_bytes']<8192:raise ValueError('Probe segment extent differs')
    if len(raw)!=offset+probe['segment_bytes']:raise ValueError('Candidate length differs from the probe segment')
    if any(raw[offset+probe['code_bytes']:offset+probe['segment_bytes']]):raise ValueError('Bytes after the probe code must be zero (padding and the per-CPU page)')
    payload=raw[offset:]
    if sha(payload)!=probe['sha256'] or raw[:len(original)]!=expected or any(raw[len(original):offset]):raise ValueError('Kernel has bytes outside recorded diagnostic changes')
    m=builder.macho(raw)
    if m['entry']!=builder.macho(original)['entry']:raise ValueError('Kernel original entry changed')
    segment=next(s for s in m['segments'] if s['name']=='__NUWA_PROBE')
    if segment['va']!=int(probe['va'],16) or segment['fileoff']!=offset or segment['size']!=probe['segment_bytes']:raise ValueError('Probe segment changed')
    bcm=next(p for p in build['patches'] if 'Suppress BCM' in p['reason'])
    if bcm['before']!='010000b9' or bcm['after']!='1f2003d5':raise ValueError('BCM correction differs')
    return dict(kernel_sha256=kernel_sha,patches=len(build['patches']),software_checks=len(software['checks']))
