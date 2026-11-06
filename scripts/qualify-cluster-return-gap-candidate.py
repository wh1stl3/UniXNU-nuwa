"""Seal PROBE52 sources and verify completed offline candidate evidence.

Uses explicit fresh build/package reports. Never accesses a device.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def ref(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))


def main():
    c=argparse.ArgumentParser(description=__doc__)
    c.add_argument('--build',type=Path,required=True)
    c.add_argument('--seal',action='store_true')
    c.add_argument('--package',type=Path)
    c.add_argument('--reproduce',type=Path)
    a=c.parse_args();build=a.build.resolve();folder=build.parent;b=read(build)
    assert folder.is_relative_to(ROOT/'reports') and b['read_flow']['resource_cluster']['cache_progress_revision']==52
    seal=folder/'source-seal.json';archive=folder/'bound-sources'
    if a.seal:
        assert not seal.exists() and not archive.exists()
        prior=read(ROOT/'reports/kernel-entry-probe/2026-10-28-probe48-tiles/source-qualification-v2/source-archive.json')
        paths={ROOT/s['path'] for s in prior['sources'] if not s['path'].startswith('out/')}
        paths|={ROOT/p for p in ('scripts/cluster_gate_diagnostics.py','scripts/test-cluster-gates.py','scripts/qualify-cluster-gate-candidate.py','scripts/kernel_entry_probe_inputs.py','scripts/test-probe-evidence-binding.py','scripts/qualify-cluster-return-gap-candidate.py','out/run-probe52-return-gap.py','out/closeout-probe52-return-gap.py')}
        sources=[]
        paths.add(ROOT/'scripts/verify-image4-entry-candidate.py')
        paths.add(ROOT/'scripts/test-vm-cache-continuity.py')
        for command in read(folder/'execution.json')['commands']+read(folder/'pipeline.json'):
            if 'argv' in command:
                script=(ROOT/command['argv'][2]).resolve()
                assert script.is_relative_to(ROOT) and script.suffix=='.py'
                paths.add(script)
        for p in sorted(paths):
            target=archive/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(p.read_bytes())
            sources.append(dict(**ref(p),archive=target.relative_to(ROOT).as_posix()))
        save(seal,dict(sources=sources,scope='Current source superset from PROBE48 provenance plus PROBE52 additions; sealed before independent rebuild and final package validation',candidate_sha256=b['candidate']['sha256']))
        print(json.dumps(dict(sealed=True,source_count=len(sources))));return
    assert a.package and a.reproduce
    for item in read(seal)['sources']:
        assert sha(ROOT/item['path'])==item['sha256']==sha(ROOT/item['archive']),item['path']
    ks=b['candidate']['sha256'];kernel=ROOT/b['candidate']['path'];assert sha(kernel)==ks
    assert read(seal)['candidate_sha256']==ks
    other=read(a.reproduce);assert other['candidate']['sha256']==ks
    for name in ('kernel-entry-probe.macho','probe.S','probe.bin'):
        assert (kernel.parent/name).read_bytes()==((ROOT/other['candidate']['path']).parent/name).read_bytes(),name
    assembly=(kernel.parent/'probe.S').read_bytes();lines=assembly.splitlines(keepends=True)
    while lines[0].startswith(b'.equ '):lines.pop(0)
    assert hashlib.sha256(b''.join(lines)).hexdigest()==b['source_sha256']==other['source_sha256']
    generated=archive/'generated/probe.S';generated.parent.mkdir();generated.write_bytes(assembly)
    execution=read(folder/'execution.json');assert len(execution['commands'])==38
    counts={}
    for command in execution['commands']:
        assert command['exit_code']==0
        report=read(folder/(command['name']+'.json'));assert report['candidate_sha256']==ks
        checks=report.get('checks',report.get('cases'))
        if checks is not None:
            assert checks and all(x.get('passed') is True for x in checks)
            counts[command['name']]=len(checks)
    for name,count in [('gate-diagnostics',131),('cluster-tiles',165),('vm-continuity',6),('x18-interruption',29),('read-vector-path',9)]:
        report=read(folder/(name+'.json'));assert report['candidate_sha256']==ks
        assert len(report['checks'])==count and all(x['passed'] is True for x in report['checks'])
        counts[name]=count
    assert counts['binding']==69 and counts['read-flow']==3624 and counts['transparency']==3296
    pipeline=read(folder/'pipeline.json');assert len(pipeline)==10 and all(x['exit_code']==0 for x in pipeline)
    package=read(a.package);assert package['kernel_sha256']==ks and sha(ROOT/package['image_path'])==package['image_sha256']
    assert 'PROBE 52' in package['fat_detail']['config']['entry'][0]['title'] and 'PROBE52 return-gap diagnosis' in package['success_requires']
    assert read(folder/'package-validation-console.txt')['image_sha256']==package['image_sha256']
    fifty=read(ROOT/'reports/kernel-entry-probe/2026-10-28-probe50-caller-r4/qualification.json')
    assert sha(ROOT/fifty['image_path'])==fifty['image_sha256']
    for item in fifty['evidence']+[fifty['sources']]:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    previous=read(ROOT/'reports/xnu-first-entry/entry-probe-49.json')
    assert sha(ROOT/previous['image_path'])==previous['image_sha256']
    assert sha(ROOT/previous['kernel_source']['path'])==previous['kernel_sha256']
    previous_q=read(ROOT/'reports/kernel-entry-probe/2026-10-28-probe49-gates-r3/qualification.json')
    for item in previous_q['evidence']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    old=read(ROOT/'reports/xnu-first-entry/entry-probe-48.json')
    assert sha(ROOT/old['image_path'])==old['image_sha256']
    assert sha(ROOT/old['kernel_source']['path'])==old['kernel_sha256']
    for key in ('root_ramdisk','fd_sha256','shim_sha256','original_boot_sha256'):assert old[key]==package[key],key
    oldq=read(ROOT/'reports/kernel-entry-probe/2026-10-28-probe48-tiles/qualification.json')
    for item in oldq['evidence']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    oldbuild=read(ROOT/'reports/kernel-entry-probe/2026-10-28-probe48-tiles/build.json')
    assert {x['site'] for x in b['dense_bootstrap']['edges']}=={x['site'] for x in oldbuild['dense_bootstrap']['edges']}
    assert b['root_mount_diagnostic']['conditional_boundary_only'] and counts['root-stop']==15
    plan=b['read_flow']['resource_cluster']
    import resource_cluster_sites as P
    assert plan==P.plan()
    assert len(P.TILE_OFFSETS)==16 and plan['state_bytes']==32*len(P.SPECS)+9*32+16
    assert len(P.points())==132
    save(folder/'fallback-map.json',dict(points=[dict(site=hex(p['site']),id=p['id'],group=p['group'],phase=p['phase'],base_tile=P.geometry(p),existing_gate_diagnostic=P.G.selected(p)) for p in P.points() if P.tile_selected(p)],scope='Sixteen strict-gated once-per-header tiles; no new native hooks. Cumulative hits do not establish invocation order. Seven additional displays use existing offsets.'))
    rows=[]
    for p in P.points():
        if P.G.selected(p):
            rows.append(dict(site=hex(p['site']),id=p['id'],group=p['group'],phase=p['phase'],base_tile=P.geometry(p),reason_rectangle=P.G.rectangles(p,P.geometry)[0],status_rectangle=P.G.rectangles(p,P.geometry)[1]))
    save(folder/'gate-map.json',dict(points=rows,reasons=P.G.REASONS,status_left_to_right=['thread-arrival','strict-pass','wide-null','wide-nonnull','strict-null','strict-nonnull'],scope=plan['gate_diagnostics']['scope'],ubc_entry_status_left_to_right=['thread-arrival','strict-pass','caller-7438c38','caller-74364a4','caller-743a080','caller-other'],caller_lrs=[hex(x) for x in P.G.CALLER_LRS]))
    from trial_media import prepare
    media=prepare(package)
    evidence=[ref(p) for p in folder.iterdir() if p.is_file() and p.name!='qualification-console.txt']+[ref(a.package.resolve()),ref(a.reproduce.resolve()),ref(generated)]
    save(folder/'qualification.json',dict(time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='offline-diagnostic-qualified',candidate_sha256=ks,image_path=package['image_path'],image_sha256=package['image_sha256'],image_bytes=package['image_bytes'],adt_sha256=package['read_file_sha256'],sources=ref(seal),evidence=evidence,check_counts=counts,independent_kernel_byte_identical=True,probe48_evidence_and_images_preserved=True,probe49_evidence_and_images_preserved=True,probe50_evidence_and_image_preserved=True,same_native_hook_sites_as48=True,release_239_retained=True,media_directory=media,device_accessed=False,device_test_passed=False,deployed=False,consumed=False,limitations=['Synthetic CPU/framebuffer evidence, no physical scanout guarantee','Wide control has no target-call attribution','Sticky bits are per header, not order or invocation counts; no atomic reentrancy guarantee','Dark markers are absence of visible evidence, not proof of no execution','No real VM locks, wakeups, IRQ, IO, SMP, EL0 or desktop qualification']))
    print(json.dumps(dict(qualified=True,image_sha256=package['image_sha256'],counts=counts)))


if __name__=='__main__':main()
