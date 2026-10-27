"""Adversarial checks for mandatory v21 packaging evidence, without editing reports."""
import argparse, copy, hashlib, json, sys
from pathlib import Path
from unittest.mock import patch
from kernel_entry_probe_inputs import ROOT, metadata, validate

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());meta=metadata(a.build);sha=b['candidate']['sha256'];checks=[]
    validate(meta,sha);checks.append(dict(name='complete v21 evidence accepted',passed=True))
    if b.get('probe_revision',0)>=49:
        altered=copy.deepcopy(meta);del altered['read-flow']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-flow rejected',passed=True))
        else:raise AssertionError('missing read-flow')
        native_read=Path.read_bytes;path=(ROOT/meta['read-flow']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-flow']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-flow case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-flow case')
    if b.get('probe_revision',0)>=48:
        altered=copy.deepcopy(meta);del altered['delta-hex']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing delta-hex rejected',passed=True))
        else:raise AssertionError('missing delta-hex')
        native_read=Path.read_bytes;path=(ROOT/meta['delta-hex']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['delta-hex']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted delta-hex case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing delta-hex case')
    if b.get('probe_revision',0)>=47:
        altered=copy.deepcopy(meta);del altered['read-result']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-result rejected',passed=True))
        else:raise AssertionError('missing read-result')
        native_read=Path.read_bytes;path=(ROOT/meta['read-result']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-result']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-result case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-result case')
    if b.get('probe_revision',0)>=46:
        altered=copy.deepcopy(meta);del altered['read-deep']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-deep rejected',passed=True))
        else:raise AssertionError('missing read-deep')
        native_read=Path.read_bytes;path=(ROOT/meta['read-deep']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-deep']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-deep case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-deep case')
    if b.get('probe_revision',0)>=45:
        altered=copy.deepcopy(meta);del altered['read-fetch']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-fetch rejected',passed=True))
        else:raise AssertionError('missing read-fetch')
        native_read=Path.read_bytes;path=(ROOT/meta['read-fetch']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-fetch']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-fetch case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-fetch case')
    if b.get('probe_revision',0)>=44:
        altered=copy.deepcopy(meta);del altered['compact-decmp']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing compact-decmp rejected',passed=True))
        else:raise AssertionError('missing compact-decmp')
        native_read=Path.read_bytes;path=(ROOT/meta['compact-decmp']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['compact-decmp']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted compact-decmp case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing compact-decmp case')
    if b.get('probe_revision',0)>=43:
        altered=copy.deepcopy(meta);del altered['shared-hex']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing shared-hex rejected',passed=True))
        else:raise AssertionError('missing shared-hex')
        native_read=Path.read_bytes;path=(ROOT/meta['shared-hex']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['shared-hex']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted shared-hex case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing shared-hex case')
    if b.get('probe_revision',0)>=42:
        altered=copy.deepcopy(meta);del altered['read-decmp']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-decmp rejected',passed=True))
        else:raise AssertionError('missing read-decmp')
        native_read=Path.read_bytes;path=(ROOT/meta['read-decmp']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-decmp']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-decmp case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-decmp case')
    if b.get('probe_revision',0)>=41:
        altered=copy.deepcopy(meta);del altered['read-grid']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-grid rejected',passed=True))
        else:raise AssertionError('missing read-grid')
        native_read=Path.read_bytes;path=(ROOT/meta['read-grid']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-grid']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-grid case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-grid case')
    if b.get('probe_revision',0)>=40:
        native_read=Path.read_bytes;path=(ROOT/meta['build']['path']).resolve();obj=json.loads(native_read(path));obj['screen']['max_written_row']=1040;payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['build']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='wrong screen extent rejected after resealing digest',passed=True))
            else:raise AssertionError('wrong screen extent')
        altered=copy.deepcopy(meta);del altered['single-pass-hex']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing single-pass HEX rejected',passed=True))
        else:raise AssertionError('missing single-pass HEX')
        native_read=Path.read_bytes;path=(ROOT/meta['single-pass-hex']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['single-pass-hex']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted single-pass HEX case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing single-pass HEX case')
    if b.get('probe_revision',0)>=39:
        altered=copy.deepcopy(meta);del altered['read-init']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-init rejected',passed=True))
        else:raise AssertionError('missing read-init')
        native_read=Path.read_bytes;path=(ROOT/meta['read-init']['path']).resolve();obj=json.loads(native_read(path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-init']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted read-init case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing read-init case')
    if b.get('probe_revision',0)>=38:
        altered=copy.deepcopy(meta);del altered['read-body-reset']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-body-reset rejected',passed=True))
        else:raise AssertionError('missing read-body-reset')
        altered=copy.deepcopy(meta);del altered['read-body']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-body rejected',passed=True))
        else:raise AssertionError('missing read-body')
        native_read=Path.read_bytes;body_path=(ROOT/meta['read-body']['path']).resolve()
        obj=json.loads(native_read(body_path));obj['checks'].pop();payload=json.dumps(obj).encode()
        altered=copy.deepcopy(meta);altered['read-body']['sha256']=hashlib.sha256(payload).hexdigest()
        with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==body_path else native_read(p)):
            try:validate(altered,sha)
            except ValueError:checks.append(dict(name='deleted body case rejected after resealing digest',passed=True))
            else:raise AssertionError('missing body case')
    if b.get('probe_revision',0)>=37:
        altered=copy.deepcopy(meta);del altered['read-dispatch']
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing read-dispatch rejected',passed=True))
        else:raise AssertionError('missing read-dispatch')
        original_dispatch=Path.read_bytes;dispatch_path=(ROOT/meta['read-dispatch']['path']).resolve()
        for mode in ('deleted-case','missing-negative'):
            obj=json.loads(original_dispatch(dispatch_path))
            if mode=='deleted-case':obj['checks'].pop()
            else:obj['wrong_target_register_negative_rejected']=False
            payload=json.dumps(obj).encode();altered=copy.deepcopy(meta)
            altered['read-dispatch']['sha256']=hashlib.sha256(payload).hexdigest()
            with patch.object(Path,'read_bytes',lambda p:payload if p.resolve()==dispatch_path else original_dispatch(p)):
                try:validate(altered,sha)
                except ValueError:checks.append(dict(name='read-dispatch '+mode+' rejected after resealing digest',passed=True))
                else:raise AssertionError(mode)
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
    a.output.write_text(json.dumps(dict(candidate_sha256=sha,checks=checks),indent=2)+'\n',newline='\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
