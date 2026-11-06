"""Compare user-visible Qualcomm driver names against candidate/installed FV.

No device changes, firmware generation or binary extraction files.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('fv', ROOT/'scripts/ci/inspect-firmware-candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    needles = ('uefipil.cfg', 'Calling target panic', 'Failed to read from partition', 'Pil_abl')
    class Reader(module.Firmware):
        def __init__(self):
            super().__init__()
            self.hits = []
            self.pil_configs = []

        def sections(self, data, owner, depth):
            if owner['guid'] == '21e9bdd9-6c3f-4f10-84a5-bbec322741f1':
                at = 0
                while at+4 <= len(data):
                    size, kind, header = int.from_bytes(data[at:at+3], 'little'), data[at+3], 4
                    if size == 0xffffff:
                        size, header = struct.unpack_from('<I', data, at+4)[0], 8
                    if not header <= size <= len(data)-at:
                        raise ValueError('PIL config section bounds')
                    if kind == 0x19:
                        raw = data[at+header:at+size]
                        text = raw.rstrip(b'\0').decode('ascii')
                        self.pil_configs.append(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),text=text))
                    at = (at+size+3)&~3
            for text in needles:
                if text.encode() in data or text.encode('utf-16-le') in data:
                    self.hits.append(dict(guid=owner['guid'], text=text))
            super().sections(data, owner, depth)
    fd = (ROOT/'out/firmware-ci/39809636575/nuwa-firmware-39809636575/build/FV/SILICIUM_UEFI.fd').read_bytes()
    if hashlib.sha256(fd).hexdigest() != '9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf':
        raise ValueError('Candidate FD changed')
    reader = Reader()
    reader.volume(fd, 'R-007 FD reused in R-008')
    current = json.loads((ROOT/'reports/abl-handoff/live-uefi-variables.json').read_text())
    seen = ('PILDxe', 'PILProxyDxe', 'DisplayDxe', 'FeatureEnablerDxe')
    # Match immutable FFS GUIDs, independent of stripped UI names.
    installed = [m for m in current['pe_images'] if m['name'] in seen]
    matches = [dict(name=m['name'], installed_guid=m['guid'], installed_pe_sha256=m['sha256'],
                    candidate_contains_same_guid=any(f['guid']==m['guid'] for f in reader.files))
               for m in installed]
    if len(matches) != 4:
        raise ValueError('Expected four screen driver identities')
    source = Path('C:/Users/ADMINI~1/AppData/Local/Temp/codex-clipboard-b0290a1c-e316-40e6-8dc2-40aa80d5fba9.jpg')
    photo = ROOT/'reports/relative-offset/user-screen.jpg'
    if not photo.exists():
        shutil.copyfile(source, photo)
    report = dict(scope='Static driver/FV comparison and manual transcription of user photo',
        candidate_fd_sha256=hashlib.sha256(fd).hexdigest(),
        installed_uefi_sha256=current['sha256'], candidate_ffs_count=len(reader.files),
        drivers=matches, candidate_selected_string_hits=reader.hits,
        candidate_pil_configs=reader.pil_configs,
        photo_path=photo.relative_to(ROOT).as_posix(), photo_sha256=hashlib.sha256(photo.read_bytes()).hexdigest(),
        readable_tail=['Pil_abl Failed to read from partition', 'Pil_abl Failed to load ELF file',
                       'Auto processing of uefipil.cfg failed. Calling target panic'],
        conclusion='Photo contains Qualcomm PIL/ABL-loading errors, not an XNU panic. '
                   'Attribution to candidate SEC/DXE is not established; compare FFS identity.',
        limitations=['No timestamp or NUWA-ENTRY marker visible in this frame',
                     'Video chronology needed to separate initial stock boot, candidate execution and later reboot',
                     'No exact candidate runtime PC/SEC stage inferred from this frame'])
    (ROOT/'reports/relative-offset/screen-origin.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
