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
    if json.loads(build.read_text()).get('probe_revision',0)>=25:
        paths += [(n,build.with_name(n+'.json')) for n in ('renderer-bounds','context-display','vectors')]
    if json.loads(build.read_text()).get('probe_revision',0)>=27:
        paths += [(n,build.with_name(n+'.json')) for n in ('image4-launch','launch-context')]
    if json.loads(build.read_text()).get('probe_revision',0)>=28:
        paths += [('pthread-startup',build.with_name('pthread-startup.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=30:
        paths += [(n,build.with_name(n+'.json')) for n in ('root-stop','root-launch','root-inputs')]
    if json.loads(build.read_text()).get('probe_revision',0)>=35:
        paths += [('fscompression-startup',build.with_name('fscompression-startup.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=36:
        paths += [('read-boundaries',build.with_name('read-boundaries.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=37:
        paths += [('read-dispatch',build.with_name('read-dispatch.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=39:
        paths += [('read-init',build.with_name('read-init.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=38:
        paths += [('read-body',build.with_name('read-body.json')),('read-body-reset',build.with_name('read-body-reset.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=40:
        paths += [('single-pass-hex',build.with_name('single-pass-hex.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=49:
        paths += [('read-flow',build.with_name('read-flow.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=48:
        paths += [('delta-hex',build.with_name('delta-hex.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=47:
        paths += [('read-result',build.with_name('read-result.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=46:
        paths += [('read-deep',build.with_name('read-deep.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=45:
        paths += [('read-fetch',build.with_name('read-fetch.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=44:
        paths += [('compact-decmp',build.with_name('compact-decmp.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=43:
        paths += [('shared-hex',build.with_name('shared-hex.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=42:
        paths += [('read-decmp',build.with_name('read-decmp.json'))]
    if json.loads(build.read_text()).get('probe_revision',0)>=41:
        paths += [('read-grid',build.with_name('read-grid.json'))]
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
    if build.get('probe_revision',0)>=30:
        policy=build.get('root_mount_diagnostic',{})
        endpoint=('0xfffffff00769d230','probe_dense_769d230') if build['probe_revision']>=32 else ('0xfffffff00769d5f4','probe_dense_769d5f4') if build['probe_revision']>=31 else ('0xfffffff0076730e8','probe_dense_76730e8')
        if (policy.get('site'),policy.get('hook'))!=endpoint or policy.get('intentional_transparency_exemption') is not (build['probe_revision']<32):raise ValueError('Diagnostic boundary missing')
        if build['probe_revision']>=32:
            if not policy.get('conditional_boundary_only') or build.get('exec_trace',{}).get('source_sha256')!=sha((ROOT/('scripts/exec_path_sites.py' if build['probe_revision']>=34 else 'scripts/exec_trace_v33.py' if build['probe_revision']>=33 else 'scripts/exec_trace_sites.py')).read_bytes()):raise ValueError('Continuous exec policy/source differs')
        for name in ('root-stop','root-launch','root-inputs'):
            item=meta[name];payload=report_path(item['path']).read_bytes()
            if sha(payload)!=item['sha256']:raise ValueError('Root evidence digest differs')
            e=json.loads(payload)
            if e.get('candidate_sha256')!=kernel_sha:raise ValueError('Root evidence candidate differs')
            if name=='root-stop':
                checks=e.get('checks',[])
                required={'inactive-pass','uncommitted-pass','foreign-task-pass','wrong-flag-pass','committed-hold','committed-no-video','first-exec-continues','error-return-continues'} if build['probe_revision']>=32 else {'first','nonzero-argument','no-video'} if build['probe_revision']>=31 else {'success','error','no-video'}
                if build['probe_revision']>=33:required|={'inactive-activation-result','inactive-exec-result','repeat-retains-result','inactive-switch-rearms'}
                if build['probe_revision']>=34:required|={'path-first-error','path-zero-return','path-keeps-first-error'}
                if len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks):raise ValueError('Boundary evidence incomplete')
            elif name=='root-launch':
                if build['probe_revision']>=33:
                    from nuwa_exec_detail_launch_context import API
                    validate_report=API.validate_report
                elif build['probe_revision']>=32:
                    from nuwa_exec_launch_context import API
                    validate_report=API.validate_report
                elif build['probe_revision']>=31:
                    from nuwa_bsd_launch_context import API
                    validate_report=API.validate_report
                else:
                    from nuwa_root_launch_context import validate_report
                validate_report(e)
            else:
                required={'actual-root','corrupt-root','missing-root-measurement','userspace-allowed','wrong-arguments','wrong-producer','nonzero-placeholder'}
                checks=e.get('checks',[])
                if len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks):raise ValueError('Root input negative controls incomplete')
    hooks={p['reason'] for p in build['patches'] if p['reason'].startswith('probe_')}
    if not {'probe_entry','probe_tables','probe_mmu'}<=hooks:raise ValueError('Required entry/tables/MMU hooks missing')
    # Two header edits, one branch per hooked site, the BCM NOP and sixteen early vectors.
    compat=build.get('image4_compatibility',{}).get('hooks',[])
    if compat and build.get('probe_revision') not in (27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49):raise ValueError('Image4 compatibility requires a supported diagnostic revision')
    overlay=[]
    if build.get('probe_revision',0)>=28:
        from pthread_prelink_overlay import load,ranges,SHA256
        replacement=load(original);overlay=ranges(original,replacement)
        actual=[p for p in build['patches'] if p['reason'].startswith('pthread_prelink_range_')]
        wanted=[(off,data.hex(),'pthread_prelink_range_'+str(i)) for i,(off,data) in enumerate(overlay)]
        if [(p['file_offset'],p['after'],p['reason']) for p in actual]!=wanted:raise ValueError('Pinned pthread overlay differs')
        startup=build.get('pthread_startup',{})
        source=sha((ROOT/'patches/xnu-8796-candidates/pthread-oskext-start.S').read_bytes())
        if startup.get('prelink_sha256')!=SHA256 or startup.get('source_sha256')!=source or startup.get('overlay_patch_count')!=len(overlay):raise ValueError('pthread source binding differs')
        if 'pthread-startup' not in meta:raise ValueError('Missing pthread startup evidence')
        item=meta['pthread-startup'];payload=report_path(item['path']).read_bytes();evidence=json.loads(payload)
        required={mode+': '+video for mode in ('registered','load-success','load-failure') for video in ('video','no-video')}
        checks=evidence.get('checks',[])
        if (sha(payload)!=item['sha256'] or evidence.get('candidate_sha256')!=kernel_sha or evidence.get('prelink_sha256')!=SHA256 or evidence.get('source_sha256')!=source or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks)):raise ValueError('pthread startup evidence incomplete')
    if build.get('probe_revision',0)>=35:
        startup=build.get('fscompression_startup',{});source=sha((ROOT/'patches/xnu-8796-candidates/fscompression-oskext-start.S').read_bytes())
        if startup.get('source_sha256')!=source or startup.get('bundle')!='com.apple.AppleFSCompression.AppleFSCompressionTypeZlib' or startup.get('compression_type')!=4 or startup.get('registration_address')!=hex(builder.macho(original)['symbols']['_decompressors']+32) or startup.get('loader_va')!=hex(builder.macho(original)['symbols']['_OSKextLoadKextWithIdentifier']):raise ValueError('FS compression lifecycle binding differs')
        if 'fscompression-startup' not in meta:raise ValueError('Missing FS compression startup evidence')
        item=meta['fscompression-startup'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={mode+': '+video for mode in ('registered','load-success','load-failure','load-empty') for video in ('video','no-video')};checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks) or e.get('os_kext_lifecycle_executed') is not False or e.get('decompressor_body_executed') is not False:raise ValueError('FS compression startup evidence incomplete')
    if build.get('probe_revision',0)>=36:
        source=sha((ROOT/'scripts/read_boundary_sites.py').read_bytes());plan=build.get('read_boundaries',{})
        if plan.get('source_sha256')!=source or plan.get('first')!='0xfffffff00769bf90' or plan.get('markers')!=list(range(266,276)) or plan.get('native_flow_preserved') is not True:raise ValueError('Read boundary policy/source differs')
        if 'read-boundaries' not in meta:raise ValueError('Missing read boundary evidence')
        item=meta['read-boundaries'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'success','mac-denied','read-error','mac-pending','dispatch-pending','swap','noauth','foreign-thread','foreign-frame','repeat','no-video'};checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks) or e.get('device_accessed') is not False or e.get('real_filesystem_body_executed') is not False or e.get('real_mac_policy_executed') is not False:raise ValueError('Read boundary evidence incomplete')
    if build.get('probe_revision',0)>=49:
        from read_flow_sites import plan as flow_plan
        if build['probe_revision']!=49 or build.get('read_flow')!=flow_plan():raise ValueError('Read flow plan differs')
        item=meta['read-flow'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        from resource_dispatch_checks import source_sha256 as dispatch_checks_sha256
        if e.get('dispatch_checks_sha256')!=dispatch_checks_sha256():raise ValueError('Dispatch test dependency differs')
        from resource_handler_checks import source_sha256 as handler_checks_sha256
        if e.get('handler_checks_sha256')!=handler_checks_sha256():raise ValueError('Handler test dependency differs')
        from resource_chain_checks import source_sha256 as chain_checks_sha256
        if e.get('chain_checks_sha256')!=chain_checks_sha256():raise ValueError('Resource chain test dependency differs')
        spec=importlib.util.spec_from_file_location('flow_evidence_contract',ROOT/'scripts/test-read-flow.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);required=mod.required_names()
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=flow_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-flow.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Read flow evidence incomplete')
    if build.get('probe_revision',0)>=48:
        from probe_delta_hex import plan as delta_plan
        if build['probe_revision'] not in (48,49) or build.get('delta_hex')!=delta_plan():raise ValueError('Delta HEX plan differs')
        item=meta['delta-hex'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        spec=importlib.util.spec_from_file_location('delta_evidence_contract',ROOT/'scripts/test-delta-hex.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);required=mod.required_names()
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=delta_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-delta-hex.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Delta HEX evidence incomplete')
    if build.get('probe_revision',0)>=47:
        from read_result_sites import plan as result_plan
        if build['probe_revision'] not in (47,48,49) or build.get('read_result')!=result_plan():raise ValueError('Result trace plan differs')
        item=meta['read-result'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        spec=importlib.util.spec_from_file_location('result_evidence_contract',ROOT/'scripts/test-read-result.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);required=mod.required_names()
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=result_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-result.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Result trace evidence incomplete')
    if build.get('probe_revision',0)>=46:
        from read_deep_sites import plan as deep_plan, points as deep_points
        if build['probe_revision'] not in (46,47,48,49) or build.get('read_deep')!=deep_plan():raise ValueError('Deep trace plan differs')
        item=meta['read-deep'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        modes=('normal','foreign-thread','foreign-frame','wrong-lr','outer-unpaired','unpaired','no-video','inactive','wrong-target')
        required={hex(p['site'])+':'+mode for p in deep_points() for mode in modes}|{'header-reset','layout','missing-pair-negative','missing-parent-pair','native-allocation-prefix'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=deep_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-deep.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Deep trace evidence incomplete')
    if build.get('probe_revision',0)>=45:
        from read_fetch_sites import plan as fetch_plan, points as fetch_points
        if build['probe_revision'] not in (45,46,47,48,49) or build.get('read_fetch')!=fetch_plan():raise ValueError('Fetch trace plan differs')
        item=meta['read-fetch'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        modes=('normal','foreign-thread','foreign-frame','wrong-lr','outer-unpaired','unpaired','no-video','inactive','wrong-target')
        required={hex(p['site'])+':'+mode for p in fetch_points() for mode in modes}|{'header-reset','layout','missing-pair-negative','wrong-callback-target','native-fetch-prefix'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=fetch_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-fetch.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Fetch trace evidence incomplete')
    if build.get('probe_revision',0)>=44:
        from probe_compact_decmp import plan as compact_plan
        if build['probe_revision'] not in (44,45,46,47,48,49) or build.get('compact_decmp')!=compact_plan():raise ValueError('Compact display plan differs')
        item=meta['compact-decmp'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'pixels-'+str(i) for i in range(373,441)}|{'header-reset','old-height-negative','no-video','repeat-no-write'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=compact_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-compact-decmp.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Compact display evidence incomplete')
    if build.get('probe_revision',0)>=43:
        from probe_shared_hex import plan as shared_plan
        if build['probe_revision'] not in (43,44,45,46,47,48,49) or build.get('shared_hex')!=shared_plan():raise ValueError('Shared HEX plan differs')
        item=meta['shared-hex'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'field-pixels','unchanged-result-no-write','changed-result-redraw','no-video','header-reset','omitted-reset-negative','code-size-reduction','dispatch-native-equivalence'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=shared_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-shared-hex.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('hardware_timing_measured') is not False:raise ValueError('Shared HEX evidence incomplete')
    if build.get('probe_revision',0)>=42:
        from read_decmp_sites import plan as decmp_plan
        from read_decmp_sites import points as decmp_points
        if build['probe_revision'] not in (42,43,44,45,46,47,48,49) or build.get('read_decmp')!=decmp_plan():raise ValueError('Compressed read plan differs')
        item=meta['read-decmp'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        modes=('normal','foreign-thread','foreign-frame','wrong-lr','outer-unpaired','unpaired','no-video','inactive','wrong-target')
        required={hex(p['site'])+':'+mode for p in decmp_points() for mode in modes}|{'header-reset','missing-pair-negative','native-prefix','layout-no-overlap','old-layout-negative'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=decmp_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-decmp.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('complete_decompression_executed') is not False:raise ValueError('Compressed read evidence incomplete')
    if build.get('probe_revision',0)>=41:
        from read_grid_sites import plan as grid_plan
        if build['probe_revision'] not in (41,42,43,44,45,46,47,48,49) or build.get('read_grid')!=grid_plan():raise ValueError('Read grid plan differs')
        item=meta['read-grid'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'prefix-zero','prefix-offset','prefix-no-video','prefix-foreign-thread','prefix-write-reduction','ret-flush','ret-inactive','header-reset','missing-buffer-store-negative'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=grid_plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-grid.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('complete_filesystem_body_executed') is not False or e.get('native_helpers_executed')!=['uio_resid','uio_offset'] or e.get('stop_before')!='vnode_mount':raise ValueError('Read grid evidence incomplete')
    if build.get('probe_revision',0)>=40:
        from probe_single_pass_hex import plan
        if build['probe_revision'] not in (40,41,42,43,44,45,46,47,48,49) or build.get('single_pass_hex')!=plan():raise ValueError('Single-pass HEX plan differs')
        if build.get('screen',{}).get('max_written_row')!=1039:raise ValueError('Single-pass HEX screen extent differs')
        item=meta['single-pass-hex'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'pixels-'+f'{v:016x}' for v in (0,0xffffffffffffffff,0x0123456789abcdef,0xfedcba9876543210,0x8000000000000001)}|{'no-video','missing-spacing-store-negative'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=plan()['source_sha256'] or e.get('test_sha256')!=sha((ROOT/'scripts/test-single-pass-hex.py').read_bytes()) or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('hardware_timing_measured') is not False:raise ValueError('Single-pass HEX evidence incomplete')
    if build.get('probe_revision',0)>=39:
        from read_init_sites import CHECKPOINTS,MIN_HEIGHT
        source=sha((ROOT/'scripts/read_init_sites.py').read_bytes());plan=build.get('read_init',{})
        if build['probe_revision'] not in (39,40,41,42,43,44,45,46,47,48,49) or plan!=dict(source_sha256=source,checkpoints=CHECKPOINTS,minimum_height=MIN_HEIGHT,final_stage=250,native_policy_changed=False):raise ValueError('Read initialization plan differs')
        item=meta['read-init'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'checkpoints-video','checkpoints-no-video','height-799','height-800','height-1039','height-1040','height-3200','old-height-800-negative','omitted-checkpoint-negative'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or e.get('test_sha256')!=sha((ROOT/'scripts/test-read-init.py').read_bytes()) or e.get('checkpoints')!=CHECKPOINTS or e.get('minimum_height')!=MIN_HEIGHT or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False:raise ValueError('Read initialization evidence incomplete')
    if build.get('probe_revision',0)>=38:
        from read_body_sites import points
        source=sha((ROOT/'scripts/read_body_sites.py').read_bytes());plan=build.get('read_body',{})
        if build['probe_revision'] not in (38,39,40,41,42,43,44,45,46,47,48,49) or plan.get('source_sha256')!=source or plan.get('points')!=points() or plan.get('native_policy_changed') is not False:raise ValueError('Read body plan differs')
        item=meta['read-body'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={(hex(p['site']),mode) for p in points() for mode in ('normal','foreign-thread','foreign-frame','unpaired','no-video')}
        required|={(hex(site),mode) for site in (0xfffffff0051a585c,0xfffffff0051a5888,0xfffffff0051a5978) for mode in ('inactive','wrong-lr')}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or e.get('points')!=points() or len(checks)!=len(required) or {(c['site'],c['mode']) for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('complete_filesystem_body_executed') is not False:raise ValueError('Read body evidence incomplete')
        item=meta['read-body-reset'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or e.get('tile_count')!=len(points()) or e.get('stale_fields_tiles_bits_cleared') is not True or e.get('omitted_reset_negative_rejected') is not True or e.get('device_accessed') is not False:raise ValueError('Read body reset evidence incomplete')
    if build.get('probe_revision',0)>=37:
        source=sha((ROOT/'scripts/read_dispatch_sites.py').read_bytes());plan=build.get('read_dispatch',{})
        if build['probe_revision'] not in (37,38,39,40,41,42,43,44,45,46,47,48,49) or plan.get('source_sha256')!=source or plan.get('entry')!='0xfffffff0051a5858' or plan.get('entry_marker')!=276 or plan.get('target_tag')!='A036' or plan.get('entry_tag')!='A037' or plan.get('runtime_target_known') is not False:raise ValueError('Dispatch observation policy/source differs')
        item=meta['read-dispatch'];payload=report_path(item['path']).read_bytes();e=json.loads(payload)
        required={'matched candidate','assigned index1','assigned index73','error return preserved','candidate body pending','different target','unmapped target','foreign thread','foreign frame','no video','null context'}
        checks=e.get('checks',[])
        if sha(payload)!=item['sha256'] or e.get('candidate_sha256')!=kernel_sha or e.get('source_sha256')!=source or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c.get('passed') is not True for c in checks) or e.get('device_accessed') is not False or e.get('real_filesystem_body_executed') is not False or e.get('header_stale_fields_and_entry_tile_cleared') is not True or e.get('wrong_target_register_negative_rejected') is not True:raise ValueError('Dispatch observation evidence incomplete')
        wanted={'scripts/test-read-dispatch-integrated.py','scripts/test-read-dispatch-observer.py','scripts/read_dispatch_sites.py','scripts/read_boundary_sites.py'}
        sources=e.get('sources',[])
        if len(sources)!=len(wanted) or {s['path'] for s in sources}!=wanted or any(sha((ROOT/s['path']).read_bytes())!=s['sha256'] for s in sources):raise ValueError('Dispatch model source binding differs')
    if len(build['patches'])!=2+len(hooks)+1+16+len(compat)+len(overlay):raise ValueError('Patch set shape differs from the recorded hook set')
    if build.get('probe_revision',0)>=27:
        required_sites={(0xfffffff0046ea000,'image4_amnm_provider'),(0xfffffff0046ea3b4,'image4_chmh_provider')}
        if {(int(h['va'],16),h['symbol']) for h in compat}!=required_sites:raise ValueError('Image4 provider hooks incomplete')
        for va,symbol in required_sites:
            patches=[p for p in build['patches'] if p['reason']==symbol]
            if len(patches)!=1:raise ValueError('Image4 hook missing/duplicate')
            p=patches[0];target=int(build['probe']['symbols'][symbol],16)
            if (p['va']!=hex(va) or p['before']!='08ae00d0'
                    or bytes.fromhex(p['after'])!=builder.branch(va,target)):
                raise ValueError('Image4 provider patch differs')
        evidence={}
        for name in ('image4-launch','launch-context'):
            if name not in meta:raise ValueError('Missing Image4 launch evidence: '+name)
            item=meta[name];payload=report_path(item['path']).read_bytes()
            if sha(payload)!=item['sha256']:raise ValueError('Image4 launch evidence digest differs')
            evidence[name]=json.loads(payload)
        launch=evidence['image4-launch'];context=evidence['launch-context']
        required={'Actual nonce preimage and all four launch components match',
                  'Real prologue original shipped-baseline','Real prologue original legal-amnm-only',
                  'Complete native Image4 initializer RET with measured inputs: unpatched',
                  'Complete native Image4 initializer RET with measured inputs: candidate',
                  'Unpatched subsequent dtless AMNM and CHMH queries reproduce ENOENT',
                  'Integrated AMNM preserves prevention-one as allow=false',
                  'Integrated CHMH returns all 48 actual manifest digest bytes',
                  'Eight unrelated dtless queries retain native results','Wrong nonce preimage refused'}
        required|={'Context rejects '+n for n in ('missing-amnm','empty-amnm','relaxed-amnm','missing-bnch','short-bnch','long-bnch','manifest-digest-corrupt','manifest-bytes-corrupt','board-value-corrupt')}
        required|={'Native initialization error retained: '+n for n in ('missing-bnch','oversized-bnch','missing-chmh')}
        required|={'Integrated CHMH preserves '+n+' error/output' for n in ('missing','oversized','wrong-type')}
        checks=launch.get('checks',[])
        if (launch.get('candidate_sha256')!=kernel_sha or len(checks)!=len(required)
                or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks)):
            raise ValueError('Image4 launch checks incomplete')
        if (context.get('adt_sha256')!=launch.get('adt_sha256')
                or context.get('components',{}).get('kernel',{}).get('sha256')!=kernel_sha
                or context.get('nonce_preimage_checked') is not True
                or context.get('trust',{}).get('apple_im4m') is not False):
            raise ValueError('Image4 launch input binding differs')
    if any(h.startswith('probe_dense_') for h in hooks):
        if build.get('probe_revision',0)<24:raise ValueError('Dense hooks require revision 24')
        from probe_bootstrap_sites import generate
        _,_,dense_sites,edges=generate(original,builder.macho(original),builder.backed,revision=build.get('probe_revision',24))
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
                exempt={'probe_dense_769d5f4'} if build.get('probe_revision',0)==31 else {'probe_dense_76730e8'} if build.get('probe_revision',0)==30 else set()
                required_cases={h+': '+mode for h in hooks-{'probe_entry','probe_tables','probe_mmu','probe_mmu_on','probe_ttbr1','probe_ttbr0','probe_console_policy'}-exempt
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
    if build.get('probe_revision',0)>=25:
        required_extra={
            'renderer-bounds':{site+suffix for site in ('probe_soc_base','probe_wfe_timeout','probe_panic_trap') for suffix in (' confines every framebuffer write to exact rectangles',' rejects old PROBE17 row drift')},
            'context-display':{'Machine context restore preserves GPR SIMD SP system registers: '+mode for mode in ('fresh','repeat','no-video','FPCR-change','first-stack-layout')} | {'Calibration band writes exact white and cyan pixels','Immediate display readback reports zero mismatches','Readback detects one changed pixel without repainting','Readback detects one changed row without repainting','Missing framebuffer keeps native control flow without display writes'}}
        required_extra['vectors']={'All sixteen actual vector entries branch to the reporter','Old PROBE17 vector entries trap before the reporter','Real cold path captures the pinned native VBAR before override','First-thread entry restores native VBAR before services and IRQ enable','Unexpected saved VBAR is rejected without unsafe handoff'}
        for name,required in required_extra.items():
            if name not in meta:raise ValueError('Missing v25 evidence: '+name)
            item=meta[name];payload=report_path(item['path']).read_bytes()
            if sha(payload)!=item['sha256']:raise ValueError('v25 digest differs: '+name)
            evidence=json.loads(payload);checks=evidence.get('checks',[])
            if evidence.get('candidate_sha256')!=kernel_sha or len(checks)!=len(required) or {c['name'] for c in checks}!=required or any(c['passed'] is not True for c in checks):raise ValueError('v25 evidence incomplete: '+name)
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
