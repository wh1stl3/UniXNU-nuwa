"""Strict unified-diff simulation in memory, never a replacement for git/build QA."""
import re


class PatchError(ValueError):
    pass


def parse(text):
    lines = text.splitlines(keepends=True)
    files = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith('--- '):
            i += 1
            continue
        old_path = lines[i][4:].strip()
        if i + 1 >= len(lines) or not lines[i + 1].startswith('+++ '):
            raise PatchError('Missing +++ header')
        new_path = lines[i + 1][4:].strip()
        i += 2
        hunks = []
        while i < len(lines) and lines[i].startswith('@@ '):
            header = lines[i]
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
            if not match:
                raise PatchError(f'Bad header {header}')
            start, old_count, _, new_count = match.groups()
            old_count, new_count = int(old_count or 1), int(new_count or 1)
            i += 1
            old, new = [], []
            while len(old) < old_count or len(new) < new_count:
                if i >= len(lines):
                    raise PatchError('Truncated hunk')
                line = lines[i]
                if line.startswith(' '):
                    old.append(line[1:]); new.append(line[1:])
                elif line.startswith('-'):
                    old.append(line[1:])
                elif line.startswith('+'):
                    new.append(line[1:])
                else:
                    raise PatchError(f'Invalid hunk body {line!r}')
                i += 1
                if i < len(lines) and lines[i].startswith('\\ No newline'):
                    if line[0] in ' -':
                        old[-1] = old[-1].rstrip('\n')
                    if line[0] in ' +':
                        new[-1] = new[-1].rstrip('\n')
                    i += 1
            if len(old) != old_count or len(new) != new_count:
                raise PatchError('Hunk counts differ')
            hunks.append((int(start), old, new))
        path = new_path[2:] if new_path.startswith('b/') else new_path
        if path.startswith('/') or '..' in path.split('/'):
            raise PatchError('Unsafe path or deletion unsupported')
        files.append((path, old_path == '/dev/null', hunks))
    if not files:
        raise PatchError('No files in patch')
    return files


class Tree:
    def __init__(self, source):
        self.source = source
        self.files = {}

    def read(self, path):
        if path in self.files:
            return self.files[path]
        return (self.source / path).read_text(encoding='utf-8')

    def apply(self, patch):
        pending, evidence = {}, []
        for path, create, hunks in parse(patch):
            if create:
                if path in self.files or (self.source / path).exists():
                    raise PatchError(f'{path}: new file already exists')
                lines = []
            else:
                try:
                    lines = self.read(path).splitlines(keepends=True)
                except FileNotFoundError as error:
                    raise PatchError(f'{path}: absent') from error
            offset, floor = 0, 0
            for number, (start, old, new) in enumerate(hunks, 1):
                if not old:
                    if not create or lines:
                        raise PatchError(f'{path}: zero-context insertion unsupported')
                    position = 0
                else:
                    matches = [j for j in range(floor, len(lines) - len(old) + 1) if lines[j:j + len(old)] == old]
                    if not matches:
                        raise PatchError(f'{path}: hunk {number} at {start} has no exact match: {"".join(old)[:220]!r}')
                    expected = start - 1 + offset
                    if expected in matches:
                        position = expected
                    elif len(matches) == 1:
                        position = matches[0]
                    else:
                        raise PatchError(f'{path}: ambiguous hunk {number}: {matches}')
                lines[position:position + len(old)] = new
                evidence.append({'path': path, 'hunk': number, 'line': position + 1})
                offset = position - (start - 1) + len(new) - len(old)
                floor = position + len(new)
            pending[path] = ''.join(lines)
        self.files.update(pending)
        return evidence
