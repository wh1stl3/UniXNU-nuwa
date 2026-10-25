"""Adversarial checks for mandatory v21 packaging evidence, without editing reports."""
import argparse, copy, hashlib, json, sys
from pathlib import Path
from unittest.mock import patch
from kernel_entry_probe_inputs import ROOT, metadata, validate

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());meta=metadata(a.build);sha=b['candidate']['sha256'];checks=[]
    validate(meta,sha);checks.append(dict(name='complete v21 evidence accepted',passed=True))
    if b.get('probe_revision',0)>=36:
        altered=copy.deepcopy(meta);del altered['read-boundaries']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-boundaries rejected',passed=True))
        else:raise AssertionError('missing read-boundaries')
        original_read=Path.read_bytes;path=(ROOT/meta['read-boundaries']['path']).resolve();obj=json.loads(original_read(path));obj['checks'].pop()
        payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered['read-boundaries']['sha256']=hashlib.sha256(payload).hexdigest()
        def read_boundary(p):return payload if p.resolve()==path else original_read(p)
        with patch.object(Path,'read_bytes',read_boundary):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read boundary case rejected after resealing digest',passed=True))
            else:raise AssertionError('deleted read boundary case')
    if b.get('probe_revision',0)>=30:
        for name in ('root-stop','root-launch','root-inputs'):
            altered=copy.deepcopy(meta);del altered[name]
            try:validate(altered,sha)
            except (ValueError,KeyError):checks.append(dict(name='missing '+name+' rejected',passed=True))
            else:raise AssertionError(name)
    if b.get('probe_revision',0)>=35:
        altered=copy.deepcopy(meta);del altered['fscompression-startup']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing FS compression startup rejected',passed=True))
        else:raise AssertionError('FS compression startup')
        original_fs=Path.read_bytes;fs_path=(ROOT/meta['fscompression-startup']['path']).resolve();obj=json.loads(original_fs(fs_path));obj['checks'].pop();payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered['fscompression-startup']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==fs_path else original_fs(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted FS compression case rejected after resealing digest',passed=True))
            else:raise AssertionError('FS compression cases')
    if b.get('probe_revision',0)>=28:
        altered=copy.deepcopy(meta);del altered['pthread-startup']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing pthread-startup rejected',passed=True))
        else:raise AssertionError('pthread-startup')
        original_pthread=Path.read_bytes;pthread_path=(ROOT/meta['pthread-startup']['path']).resolve()
        obj=json.loads(original_pthread(pthread_path));obj['checks'].pop()
        pthread_payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered['pthread-startup']['sha256']=hashlib.sha256(pthread_payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:pthread_payload if p.resolve()==pthread_path else original_pthread(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted pthread-startup case rejected after resealing digest',passed=True))
            else:raise AssertionError('pthread-startup cases')
    for name in ('transparency','wfe','read-sites','loader','mapping') + (('transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb') if b.get('probe_revision',0)>=22 else ()) + (('console-policy',) if b.get('probe_revision',0)>=23 else ()) + (('renderer-bounds','context-display','vectors') if b.get('probe_revision',0)>=25 else ()) + (('image4-launch','launch-context') if b.get('probe_revision',0)>=27 else ()):
        altered=copy.deepcopy(meta);del altered[name]
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing '+name+' rejected',passed=True))
        else:raise AssertionError(name)
    original=Path.read_bytes
    for name in ('transparency','wfe') + (('transition-normal',) if b.get('probe_revision',0)>=22 else ()) + (('console-policy',) if b.get('probe_revision',0)>=23 else ()) + (('renderer-bounds','context-display','vectors') if b.get('probe_revision',0)>=25 else ()) + (('image4-launch',) if b.get('probe_revision',0)>=27 else ()):
        path=(ROOT/meta[name]['path']).resolve();obj=json.loads(original(path));obj['checks'].pop()
        payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered[name]['sha256']=hashlib.sha256(payload).hexdigest()
        def read(p):return payload if p.resolve()==path else original(p)
        with patch.object(Path,'read_bytes',read):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted '+name+' case rejected after resealing digest',passed=True))
            else:raise AssertionError(name)
    path=a.build.resolve();obj=copy.deepcopy(b);obj['probe_revision']=20
    payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered['build']['sha256']=hashlib.sha256(payload).hexdigest()
    def read_build(p):return payload if p.resolve()==path else original(p)
    with patch.object(Path,'read_bytes',read_build):
        try:validate(altered,sha)
        except ValueError:checks.append(dict(name='revision downgrade rejected after resealing digest',passed=True))
        else:raise AssertionError('downgrade')
    if b.get('probe_revision',0)>=24:
        for mode in ('missing-edge','changed-coordinate','revision-23'):
            obj=copy.deepcopy(b)
            if mode=='missing-edge':obj['dense_bootstrap']['edges'].pop()
            elif mode=='changed-coordinate':obj['dense_bootstrap']['edges'][0]['x']+=4
            else:obj['probe_revision']=23
            payload=json.dumps(obj).encode();altered=copy.deepcopy(meta);altered['build']['sha256']=hashlib.sha256(payload).hexdigest()
            with patch.object(Path,'read_bytes',read_build):
                try:validate(altered,sha)
                except ValueError:checks.append(dict(name='dense '+mode+' rejected after resealing digest',passed=True))
                else:raise AssertionError(mode)
    altered=copy.deepcopy(meta);altered['software']['sha256']='0'*64
    try:validate(altered,sha)
    except ValueError:checks.append(dict(name='software digest mutation rejected',passed=True))
    else:raise AssertionError('digest')
    a.output.write_text(json.dumps(dict(candidate_sha256=sha,checks=checks),indent=2)+'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
