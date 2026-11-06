"""Bind core launch service requirements to audited dependency and Data evidence.

Does not enable jobs, choose feature values, create directories or modify images.
"""
import argparse, hashlib, itertools, json
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def variants(arguments):
    flags=set()
    for a in arguments:
        v=a['value']
        if not isinstance(v,dict) or set(v)!={'#IfFeatureFlagEnabled','#Then','#Else'}:
            raise ValueError('Unsupported conditional argument')
        if not all(isinstance(v[k],str) for k in v):
            raise ValueError('Non-string conditional branch')
        flags.add(v['#IfFeatureFlagEnabled'])
    if len(flags)>8:raise ValueError('Feature combination budget')
    names=sorted(flags); result=[]
    for values in itertools.product((False,True),repeat=len(names)):
        assignment=dict(zip(names,values))
        result.append(dict(assumed_features=assignment,replacements=[dict(index=a['index'],value=a['value']['#Then' if assignment[a['value']['#IfFeatureFlagEnabled']] else '#Else']) for a in arguments],runtime_selected=False))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists();refs=[]
    def read(path):
        raw=path.read_bytes();refs.append(dict(path=path.relative_to(R).as_posix(),sha256=hashlib.sha256(raw).hexdigest()));return json.loads(raw)
    audit=read(a.audit.resolve())
    assert audit['error'] is None and audit['mount_cleanup_complete'] and not audit['device_accessed']
    contract=read(R/audit['launch_contract']['path']);assert refs[-1]['sha256']==audit['launch_contract']['sha256']
    source=read(R/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json')
    seed=read(R/'reports/desktop-readiness/2026-10-27-data-linux-r1/candidate.json')
    assert source['error'] is None and seed['error'] is None
    spec=read(R/seed['spec']['path']);assert refs[-1]['sha256']==seed['spec']['sha256']
    dirs={'/private/var/'+v[0]:dict(uid=v[1],gid=v[2],mode=v[3]) for v in spec['directories']}
    dirs['/private/var']=dict(uid=0,gid=0,mode='0755')
    source_files=[v for v in source['data_source']['entries'] if v.get('type')=='file']
    seeded_files={f[0] for f in spec['files']} if spec['files'] else set()
    missing=[dict(path=v['path'],sha256=v['sha256'],bytes=v['bytes'],uid=v['uid'],gid=v['gid'],mode=v['mode'],required_for_boot='not_established') for v in source_files if v['path'].removeprefix('private/var/') not in seeded_files]
    graph={}
    for e in audit['dependency_closure']['edges']:graph.setdefault(e['source'],set()).add(e['target'])
    jobs=[]
    for j in audit['launch_contract']['jobs']:
        seen=set();todo=[j['program']]
        while todo:
            node=todo.pop()
            if node in seen:continue
            seen.add(node);todo.extend(graph.get(node,()))
        user=j['user_lookup']['record'];home=user['home'] if user else None
        # Canonical home is taken from the existing namespace audit, not guessed.
        candidates=[]
        def walk(value):
            if isinstance(value,dict):
                if value.get('path')==home and 'canonical' in value:candidates.append(value)
                for item in value.values():walk(item)
            elif isinstance(value,list):
                for item in value:walk(item)
        if home:walk(contract['data_contract'])
        canonical=next((v['canonical'] for v in candidates),None)
        contextual=j['non_string_arguments']
        jobs.append(dict(label=j['label'],program=j['program'],reachable_images=len(seen),declared=j['declared'],identity=j['user_lookup'],group=j['group_lookup'],home=home,canonical_home=canonical,seed_home_metadata=dirs.get(canonical),mach_services=j['mach_services'],conditional_argument_variants=variants(contextual) if contextual else [],enabled=False))
    result=dict(parents=refs,services=jobs,unselected_or_absent_labels=audit['launch_contract']['selected_labels_not_found'],dependency_summary={k:len(audit['dependency_closure'][k]) for k in ('nodes','edges','required_missing','unresolved_contextual')},source_files_absent_from_directory_seed=missing,seed_directory_count=len(dirs),feature_default_files=source['feature_flags']['default_files'],deployable=False,device_accessed=False,limitations=['Path closure is not symbol binding, signatures, IPC or runtime execution','Data source omissions are not all boot requirements','Directory evidence does not establish ACLs, protection classes or runtime writable state','Conditional variants enumerate assumptions, never select runtime defaults'])
    result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(services=len(jobs),source_files_missing=len(missing),conditional_jobs=[j['label'] for j in jobs if j['conditional_argument_variants']],unresolved_homes=[j['label'] for j in jobs if j['home'] and not j['seed_home_metadata']]),ensure_ascii=False))

if __name__=='__main__':main()
