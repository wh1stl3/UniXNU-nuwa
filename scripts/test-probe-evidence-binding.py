"""Adversarial checks for mandatory v21 packaging evidence, without editing reports."""
import argparse, copy, hashlib, json, sys
from pathlib import Path
from unittest.mock import patch
from kernel_entry_probe_inputs import ROOT, metadata, validate

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());meta=metadata(a.build);sha=b['candidate']['sha256'];checks=[]
    validate(meta,sha);checks.append(dict(name='complete v21 evidence accepted',passed=True))
    for name in ('transparency','wfe','read-sites','loader','mapping') + (('transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb') if b.get('probe_revision',0)>=22 else ()):
        altered=copy.deepcopy(meta);del altered[name]
        try:validate(altered,sha)
        except (ValueError,KeyError):checks.append(dict(name='missing '+name+' rejected',passed=True))
        else:raise AssertionError(name)
    original=Path.read_bytes
    for name in ('transparency','wfe') + (('transition-normal',) if b.get('probe_revision',0)>=22 else ()):
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
    altered=copy.deepcopy(meta);altered['software']['sha256']='0'*64
    try:validate(altered,sha)
    except ValueError:checks.append(dict(name='software digest mutation rejected',passed=True))
    else:raise AssertionError('digest')
    a.output.write_text(json.dumps(dict(candidate_sha256=sha,checks=checks),indent=2)+'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
