"""Check real storage dependencies and all three vtables in an analysis prelink."""
import argparse, hashlib, json, runpy, struct
from pathlib import Path
from native_prelink_inputs import ROOT, inputs, tools, components

def digest(raw): return hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',type=Path,required=True)
    ap.add_argument('--emission',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); output=args.output.resolve()
    if not output.is_relative_to(ROOT/'reports') or output.exists(): raise ValueError('Fresh report required')
    profile,native,donor,selection=inputs(args.profile)
    emission=json.loads(args.emission.read_bytes()); raw=(ROOT/emission['candidate']['path']).read_bytes()
    if digest(raw)!=emission['candidate']['sha256'] or digest(native)!=emission['native_sha256']: raise ValueError('Image drift')
    contract=json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())
    abi_raw=(ROOT/contract['abi_report']['path']).read_bytes()
    if digest(abi_raw)!=contract['abi_report']['sha256']: raise ValueError('ABI evidence drift')
    abi=json.loads(abi_raw); helper=runpy.run_path(str(ROOT/'scripts/ci/build-ramblock-kernel.py'))
    symbols,_=helper['symbols'](native); bindings=[]; checks=[]
    with tools(True,args.profile) as (parser,_):
        candidate=parser.macho(raw); _,_,modules=components(parser,donor,selection)
        storage=modules['com.apple.iokit.IOStorageFamily']
        def q(address):
            at=parser.backed_offset(candidate['segments'],address,8,len(raw))
            return struct.unpack_from('<Q',raw,at)[0]
        for name,value in contract['bindings'].items():
            address=int(value,16)
            owners=[s['name'] for s in storage['segments'] if s['va']+profile['slide']<=address and address+8<=s['va']+profile['slide']+s['filesize']]
            if len(owners)!=1 or symbols[name]['value']!=address: raise ValueError('Storage binding mismatch: '+name)
            q(address); bindings.append(dict(symbol=name,address=value,donor_segment=owners[0]))
        inherited={item['slot']:int(item['target'],16) for item in abi['original_methods']}
        artifact=(ROOT/profile['native_path']).parents[4]
        ufs=helper['vtable'](artifact/'build/ramblock-archive/NativeUfs.o','NativeUfsBlock')
        tables=[('IOBlockStorageDevice',contract['reference_vtable'],inherited),
                ('NativeRamBlock',contract['production_vtable'],{}),('NativeUfsBlock',ufs,{})]
        for classname,methods,original in tables:
            if len(methods)!=190: raise ValueError('Unexpected slot count')
            base=symbols['__ZTV'+str(len(classname))+classname]['value']+16
            for slot,name in enumerate(methods):
                expected=original[slot] if slot in original else symbols[name]['value']
                if q(base+slot*8)!=expected: raise ValueError(f'{classname} slot {slot}: {name}')
            checks.append(dict(classname=classname,slots=len(methods),passed=True))
        for name in contract['allowed_weak']:
            if symbols[name]['kind']&14!=14: raise ValueError('UFS provider not section-backed')
            q(symbols[name]['value'])
    report=dict(passed=True,scope='File-backed donor storage bindings and exact final vtable targets; no execution proof',
        profile_sha256=digest(args.profile.read_bytes()),candidate=emission['candidate'],native_sha256=digest(native),
        donor_sha256=digest(donor),bindings=bindings,vtables=checks,real_ufs_definitions=contract['allowed_weak'],
        runtime_qualified=False,loadable=False,device_accessed=False)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(passed=True,bindings=len(bindings),vtables=checks,loadable=False)))

if __name__=='__main__': main()
