"""Source-only R-009 proposal; do not modify or build firmware."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
BASE = '910ee079fbaef736c49c14fd24501b132e98bb90'


def main():
    report = json.loads((ROOT/'reports/relative-offset/screen-origin.json').read_text())
    config, = report['candidate_pil_configs']
    original = config['text']
    if hashlib.sha256(original.encode()).hexdigest() != config['sha256']:
        raise ValueError('Decoded config differs from exact RAW section')
    old = '[AUTO]\nABL\n'
    new = '[AUTO]\n# No automatic ABL chainload in the UniXNU second-stage firmware.\n'
    if original.count(old) != 1:
        raise ValueError('Unexpected AUTO section')
    revised = original.replace(old, new)
    relative = 'Platforms/Xiaomi/nuwaPkg/RawFiles/uefipil.cfg'
    source = 'Platforms/Xiaomi/nuwaPkg/Include/RAW.inc'
    raw = subprocess.check_output(['git','-C',str(FIRMWARE),'show',BASE+':'+source]).decode().replace('\r\n','\n')
    needle = 'SECTION RAW = Binaries/nuwa/RawFiles/uefipil.cfg'
    replacement = 'SECTION RAW = nuwaPkg/RawFiles/uefipil.cfg'
    if raw.count(needle) != 1:
        raise ValueError('Unexpected RAW include')
    patched = raw.replace(needle,replacement)
    patch = ''.join(difflib.unified_diff(raw.splitlines(True),patched.splitlines(True),
                                       fromfile='a/'+source,tofile='b/'+source))
    patch += ''.join(difflib.unified_diff([],revised.splitlines(True),
                                        fromfile='/dev/null',tofile='b/'+relative))
    destination=ROOT/'patches/firmware-candidates/0007-nuwa-disable-auto-abl.patch'
    destination.write_text(patch,encoding='utf-8',newline='\n')
    subprocess.run(['git','-C',str(FIRMWARE),'apply','--check',str(destination)],check=True)
    # Show all inherited config differences; never invent or rewrite board values.
    delta=''.join(difflib.unified_diff(original.splitlines(True),revised.splitlines(True),
                                      fromfile='embedded-original',tofile='proposed-local-config'))
    result=dict(result='Source-only apply check passed; no image or firmware checkout changed',
        approval='R-009 pending',base_commit=BASE,original_config_bytes=config['bytes'],
        original_config_sha256=config['sha256'],
        proposed_config_sha256=hashlib.sha256(revised.encode()).hexdigest(),
        patch=destination.relative_to(ROOT).as_posix(),patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        changed_config_lines=delta,changed_source_paths=[source,relative],
        retained=['PILDxe','PILProxyDxe','All RETAIL and image definitions, GUIDs and memory numbers'],
        unverified=['Empty AUTO section parser/runtime behavior','DXE dependencies after PIL','BDS/UniXNU dispatch'],
        image_generated=False,firmware_source_changed=False)
    (ROOT/'reports/relative-offset/no-auto-abl-preview.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
