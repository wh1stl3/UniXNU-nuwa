"""Bind and carry unchanged donor trust modules through the real loader path."""
import hashlib,json,subprocess
from pathlib import Path
import nuwa_launch_context as context
ROOT=Path(__file__).resolve().parents[1]
TRUST=ROOT/'out/ios16-original-trust-20261102-r1/original-static-system.bundle'
EXPECTED='eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3'

def sha(data):return hashlib.sha256(data).hexdigest()
def linux(path):return '/mnt/d/'+path.resolve().as_posix()[3:]
def trust_bytes():
    raw=TRUST.read_bytes();assert len(raw)==67764 and sha(raw)==EXPECTED;return raw

def bind_context(work,adt,kernel,fd,shim):
    raw=trust_bytes();tree=context.parse(adt);chosen=context.find(tree,'/chosen')
    values=context.properties(chosen);manifest=json.loads(values[context.CONTEXT_KEY])
    assert 'trust_cache' not in manifest['components']
    manifest['components']['trust_cache']={'bytes':len(raw),'sha256':sha(raw)}
    encoded=context.canonical(manifest)
    chosen['properties']=[(k,f,encoded if k==context.CONTEXT_KEY else hashlib.sha384(encoded).digest() if k==context.HASH_KEY else v) for k,f,v in chosen['properties']]
    adt=context.encode(tree)
    receipt=context.validate(adt,kernel,fd,shim,nonce=(work/'launch/nonce.bin').read_bytes(),manifest_bytes=encoded)
    (work/'launch/launch-manifest.json').write_bytes(encoded)
    (work/'launch/kernel.macho.adt').write_bytes(adt)
    return adt,receipt

def install_sidecar(work,fatpath,kernel,adt):
    raw=trust_bytes();tree=context.parse(adt)
    manifest=json.loads(context.properties(context.find(tree,'/chosen'))[context.CONTEXT_KEY])
    assert manifest['components']['trust_cache']=={'bytes':len(raw),'sha256':sha(raw)}
    assert context.properties(context.find(tree,'/chosen/memory-map'))['TrustCache']==bytes(16)
    source=work/'kernel.macho.trustcache';source.write_bytes(raw)
    target='::/EFI/UniXNU/Payloads/kernel.macho.trustcache';readback=work/'readback-kernel.macho.trustcache'
    subprocess.run(['wsl','--','env','MTOOLS_SKIP_CHECK=1','mcopy','-i',linux(fatpath),linux(source),target],check=True,capture_output=True)
    subprocess.run(['wsl','--','env','MTOOLS_SKIP_CHECK=1','mcopy','-i',linux(fatpath),target,linux(readback)],check=True,capture_output=True)
    assert readback.read_bytes()==raw
    return dict(path=target,bytes=len(raw),sha256=sha(raw),fat_readback=True,launch_measurement_bound=True,
                original_modules_unchanged=True,apple_signature_verification=False,runtime_acceptance=False)
