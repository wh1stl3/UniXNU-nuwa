"""Emit the two unchanged, pinned 20H392 trust modules as a loader bundle.

No new hashes or policy exceptions; no ADT, kernel, image or device changes.
The pinned DarwinBoot format parser is compiled from source through stdin.
"""
import argparse
import hashlib
import importlib.util
import json
import plistlib
import struct
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path('D:/Code/PortingiOSLegacy/common/cache/donor-ios16')
BASE=Path('D:/Code/PortingiOSLegacy/common/sources/UniXNU')
PIN='75bc13dd34dc4e403826793739e316a264ce00dd'
SOURCE='drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c'
spec=importlib.util.spec_from_file_location('research',ROOT/'scripts/research-ios16-payload-chain.py')
research=importlib.util.module_from_spec(spec);spec.loader.exec_module(research)


def sha(data):return hashlib.sha256(data).hexdigest()
def linux(path):
    value=path.resolve().as_posix()
    assert value.startswith('D:/')
    return '/mnt/d/'+value[3:]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();work=a.work.resolve();output=a.output.resolve()
    assert work.is_relative_to(ROOT/'out') and not work.exists()
    assert output.is_relative_to(ROOT/'reports') and not output.exists()
    manifest_bytes=(DONOR/'BuildManifest.plist').read_bytes()
    manifest=plistlib.loads(manifest_bytes)
    assert manifest['ProductBuildVersion']=='20H392' and manifest['ProductVersion']=='16.7.16'
    identities=[i for i in manifest['BuildIdentities'] if i['Info']['DeviceClass']=='d22ap' and i['Info']['RestoreBehavior']=='Erase']
    assert len(identities)==1
    prior_path=ROOT/'reports/ios16-payload-research/donor-inventory.json'
    prior=json.loads(prior_path.read_bytes())
    modules=[];inputs=[]
    for name in ('StaticTrustCache','Cryptex1,SystemTrustCache'):
        record=identities[0]['Manifest'][name]
        path=DONOR/'components'/Path(record['Info']['Path']).name
        raw=path.read_bytes()
        old=next(i for i in prior['components'] if i['component']==name)
        assert sha(raw)==old['current_sha256']
        assert hashlib.sha384(raw).digest()==record['Digest']
        module=research.trust_payload(raw)
        assert sha(module)==old['module_sha256']
        version,count=struct.unpack_from('<I16xI',module)
        assert version==2 and len(module)==24+count*24
        modules.append(module)
        inputs.append(dict(component=name,path=str(path),sha256=sha(raw),module_sha256=sha(module),entries=count))
    bundle=struct.pack('<3I',2,12,12+len(modules[0]))+b''.join(modules)
    assert sha(bundle)==prior['trust_bundle_in_memory']['sha256']
    work.mkdir(parents=True)
    target=work/'original-static-system.bundle';target.write_bytes(bundle)
    raw_source=subprocess.check_output(['git','--no-optional-locks','-c',f'safe.directory={BASE}',
                                       '-C',str(BASE),'show',f'{PIN}:{SOURCE}'])
    source=raw_source.decode()
    start=source.index('STATIC\nBOOLEAN\nValidTrustCaches')
    end=source.index('\nSTATIC\n',start+1)
    function=source[start:end]
    host='''#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define STATIC static
#define CONST const
#define TRUE 1
#define FALSE 0
#define CompareMem memcmp
typedef uint8_t UINT8;typedef uint32_t UINT32;typedef size_t UINTN;typedef int BOOLEAN;
static UINT32 U32(const void *p){UINT32 v;memcpy(&v,p,4);return v;}
'''+function+'''
int main(int argc,char **argv){if(argc!=2)return 3;FILE *f=fopen(argv[1],"rb");if(!f)return 4;
fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<0||n>1048576)return 5;
unsigned char *p=malloc(n?n:1);if(!p)return 6;if(fread(p,1,n,f)!=(size_t)n)return 7;
fclose(f);int ok=ValidTrustCaches(p,n);free(p);return ok?0:2;}
'''
    exe=work/'validate-trust'
    subprocess.run(['wsl','--','/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror',
                    '-x','c','-','-o',linux(exe)],input=host.encode(),check=True)
    fixtures=[('original',bundle,True),('truncated',bundle[:-1],False),
              ('zero-count',bytes(4)+bundle[4:],False)]
    bad=bytearray(bundle);struct.pack_into('<I',bad,4,13);fixtures.append(('misaligned-offset',bytes(bad),False))
    bad=bytearray(bundle);bad[12+24+20]=0;fixtures.append(('invalid-hash-type',bytes(bad),False))
    bad=bytearray(bundle);bad[12+48:12+68]=bad[12+24:12+44];fixtures.append(('duplicate-cdhash',bytes(bad),False))
    checks=[]
    for name,data,want in fixtures:
        f=work/(name+'.fixture');f.write_bytes(data)
        result=subprocess.run(['wsl','--',linux(exe),linux(f)],capture_output=True)
        assert result.returncode==(0 if want else 2),(name,result.returncode,result.stderr)
        checks.append(dict(name=name,accepted=want))
    assert target.read_bytes()==bundle
    report=dict(image_build='20H392',inputs=inputs,manifest_sha256=sha(manifest_bytes),
                bundle=dict(path=target.relative_to(ROOT).as_posix(),bytes=len(bundle),sha256=sha(bundle)),
                parser=dict(commit=PIN,path=SOURCE,source_sha256=sha(raw_source),checks=checks),
                sources={n:sha((ROOT/'scripts'/n).read_bytes()) for n in
                         ('build-ios16-original-trust-bundle.py','research-ios16-payload-chain.py')},
                original_module_bytes_preserved=True,device_accessed=False,boot_integrated=False,
                runtime_trust_acceptance=False,apple_signature_verification=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(bytes=len(bundle),entries=[i['entries'] for i in inputs],parser_checks=len(checks))))


if __name__=='__main__':main()
