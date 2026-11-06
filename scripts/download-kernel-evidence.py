"""Read selected existing Actions ZIP members with bounded, retryable HTTP ranges.

Signed URLs and authentication remain in memory. CRC checks cover downloaded
members; this does not verify the digest of the complete artifact ZIP.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GH = 'C:/Program Files/GitHub CLI/gh.exe'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def artifact_url(repo, artifact_id):
    token = subprocess.check_output([GH, 'auth', 'token'], text=True).strip()
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})
    try:
        urllib.request.build_opener(NoRedirect).open(request, timeout=60)
    except urllib.error.HTTPError as response:
        if response.code == 302:
            return response.headers['Location']
        raise RuntimeError(f'Artifact API HTTP {response.code}') from None
    raise RuntimeError('Expected signed artifact redirect')


class RangeFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.chunk_size = 1024 * 1024
        self.cache = {}
        self.requests = 0

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if self.position < 0:
            raise ValueError('Negative ZIP position')
        return self.position

    def tell(self):
        return self.position

    def read(self, count=-1):
        end = self.size if count < 0 else min(self.size, self.position + count)
        parts = []
        while self.position < end:
            index = self.position // self.chunk_size
            if index not in self.cache:
                start = index * self.chunk_size
                stop = min(start + self.chunk_size, self.size) - 1
                for attempt in range(5):
                    try:
                        request = urllib.request.Request(self.url, headers={
                            'Range': f'bytes={start}-{stop}', 'Accept-Encoding': 'identity'})
                        with urllib.request.urlopen(request, timeout=45) as response:
                            expected = f'bytes {start}-{stop}/{self.size}'
                            if response.status != 206 or response.headers.get('Content-Range') != expected:
                                raise ValueError('Server did not honor exact bounded range')
                            data = response.read(stop - start + 2)
                        if len(data) != stop - start + 1:
                            raise ValueError('Incomplete artifact range')
                        self.cache[index] = data
                        self.requests += 1
                        break
                    except Exception as error:
                        if attempt == 4:
                            raise RuntimeError(f'Range {start}-{stop} failed: {type(error).__name__}') from None
                        time.sleep(1 + attempt)
            data = self.cache[index]
            offset = self.position % self.chunk_size
            take = min(end - self.position, len(data) - offset)
            parts.append(data[offset:offset + take])
            self.position += take
        return b''.join(parts)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('run_id', type=int)
    cli.add_argument('--repo', default='wh1stl3/UniXNU-nuwa')
    args = cli.parse_args()
    listing = json.loads(subprocess.check_output([
        GH, 'api', f'repos/{args.repo}/actions/runs/{args.run_id}/artifacts'], text=True))
    items = [item for item in listing['artifacts'] if item['name'] == f'nuwa-8796-merged-{args.run_id}']
    if len(items) != 1 or items[0]['expired']:
        raise ValueError('Expected one live merged-kernel artifact')
    item = items[0]
    target = ROOT / f'out/kernel-ci/{args.run_id}'
    report = ROOT / f'reports/kernel-ci/{args.run_id}/selective-download.json'
    target.mkdir(parents=True, exist_ok=True)
    records = []
    stream = RangeFile(artifact_url(args.repo, item['id']), item['size_in_bytes'])
    with zipfile.ZipFile(stream) as archive:
        inventory = archive.infolist()
        (target / 'zip-inventory.json').write_text(json.dumps([
            {'path': m.filename, 'bytes': m.file_size, 'compressed_bytes': m.compress_size}
            for m in inventory], indent=2) + '\n', encoding='utf-8')
        for member in inventory:
            name = member.filename
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe artifact member')
            selected = ('/reports/' in name and path.suffix in ('.json', '.log')) or name in (
                'nuwa-host/kernel-console.log', 'nuwa-host/toolchain.log')
            selected |= name.endswith('.unstripped') or (name.endswith('.a') and 'driver-archives' in name)
            if not selected or member.is_dir():
                continue
            if member.file_size > 128_000_000:
                raise ValueError(f'Selected member exceeds audit bound: {name} ({member.file_size})')
            destination = target.joinpath(*path.parts)
            if not destination.resolve().is_relative_to(target.resolve()):
                raise ValueError('Artifact member escapes output directory')
            if destination.exists() and destination.stat().st_size == member.file_size:
                import zlib
                payload = destination.read_bytes()
                if zlib.crc32(payload) != member.CRC:
                    payload = archive.read(member)
            else:
                payload = archive.read(member)  # zipfile verifies CRC on full read
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            records.append({'path': name, 'bytes': len(payload), 'crc32': f'{member.CRC:08x}',
                            'sha256': hashlib.sha256(payload).hexdigest()})
            print(json.dumps(records[-1]), flush=True)
    result = {'run_id': args.run_id, 'repo': args.repo, 'artifact_id': item['id'],
              'artifact_name': item['name'], 'artifact_bytes': stream.size,
              'whole_zip_digest_checked': False, 'selected_members_crc_checked': True,
              'range_requests': stream.requests, 'members': records,
              'inventory': [{'path': m.filename, 'bytes': m.file_size} for m in inventory]}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
