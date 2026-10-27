"""Replay XNU's find_entry() over an ADT byte-for-byte.

pexpert/gen/device_tree.c implements SecureDTFindEntry with a single global
cursor (startingP) and a recursive helper:

    find_entry(propName, propValue, entryH):
        nodeP = startingP
        if nodeP->nProperties == 0: return kError      # end of the node list
        startingP = nodeP + 1
        for k in 0..nodeP->nProperties-1:
            propP = startingP
            startingP += sizeof(propP) + ((propP->length + 3) & -4)
            if strcmp(propP->name, propName) == 0 and
               (propValue == NULL or strcmp(propP + 1, propValue) == 0):
                *entryH = nodeP; return kSuccess
        for k in 0..nodeP->nChildren-1:
            if find_entry(...) == kSuccess: return kSuccess
        return kError

The recursion does not restore the cursor, so a child that returns kError
leaves the cursor past that child's whole subtree, which is exactly where the
next sibling starts. That only holds if the flattened tree stores a node as
"header, properties, then the whole subtree of each child in order".

This module reproduces that algorithm exactly - the global cursor, the
nProperties == 0 terminator, the property advance rule and the recursive
child loop - and reports what it finds. It differs from a structural walk: it
fails on any tree whose byte layout does not match what XNU expects.
"""

import struct
import sys

PROP_NAME_LENGTH = 32
PROP_HEADER = PROP_NAME_LENGTH + 4      # name[32] + uint32 length


class Cursor:
    """The global startingP of find_entry()."""

    def __init__(self, blob):
        self.blob = blob
        self.pos = 0

    def u32(self, off):
        return struct.unpack_from('<I', self.blob, off)[0]

    def prop_advance(self, length):
        self.pos += PROP_HEADER + ((length + 3) & ~3)


def find_entry(cursor, prop_name, prop_value):
    """Return the node offset of the match, or None. Mirrors find_entry()."""
    blob = cursor.blob
    if cursor.pos + 8 > len(blob):
        return None
    node = cursor.pos
    n_props = cursor.u32(node)
    n_children = cursor.u32(node + 4)
    if n_props == 0:
        return None                      # end of the node list
    cursor.pos = node + 8
    for _ in range(n_props):
        if cursor.pos + PROP_HEADER > len(blob):
            return None
        length = cursor.u32(cursor.pos + PROP_NAME_LENGTH)
        name = blob[cursor.pos:cursor.pos + PROP_NAME_LENGTH].split(b'\0', 1)[0]
        value_off = cursor.pos + PROP_HEADER
        cursor.prop_advance(length)
        if name == prop_name:
            if prop_value is None:
                return node
            value = blob[value_off:value_off + length].split(b'\0', 1)[0]
            if value == prop_value:
                return node
    for _ in range(n_children):
        hit = find_entry(cursor, prop_name, prop_value)
        if hit is not None:
            return hit
    return None


def lookup(path, blob):
    """SecureDTLookupEntry(NULL, path): walk children by their name property."""
    parts = [p for p in path.split('/') if p]
    node = 0
    for part in parts:
        node = find_child(node, part, blob)
        if node is None:
            return None
    return node


def children_of(node, blob):
    """Child node offsets, using XNU's skipProperties/skipTree rule."""
    cursor = Cursor(blob)
    cursor.pos = node
    n_props = cursor.u32(node)
    n_children = cursor.u32(node + 4)
    cursor.pos = node + 8
    for _ in range(n_props):
        length = cursor.u32(cursor.pos + PROP_NAME_LENGTH)
        cursor.prop_advance(length)
    out = []
    pos = cursor.pos
    for _ in range(n_children):
        out.append(pos)
        pos = skip_tree(pos, blob)
    return out


def skip_tree(node, blob):
    """skipTree(): past this node's properties and all of its children's trees."""
    cursor = Cursor(blob)
    cursor.pos = node
    n_props = cursor.u32(node)
    n_children = cursor.u32(node + 4)
    cursor.pos = node + 8
    for _ in range(n_props):
        length = cursor.u32(cursor.pos + PROP_NAME_LENGTH)
        cursor.prop_advance(length)
    for _ in range(n_children):
        cursor.pos = skip_tree(cursor.pos, blob)
    return cursor.pos


def find_child(node, name, blob):
    for child in children_of(node, blob):
        cursor = Cursor(blob)
        cursor.pos = child
        n_props = cursor.u32(child)
        cursor.pos = child + 8
        value = None
        for _ in range(n_props):
            length = cursor.u32(cursor.pos + PROP_NAME_LENGTH)
            pname = blob[cursor.pos:cursor.pos + PROP_NAME_LENGTH].split(b'\0', 1)[0]
            off = cursor.pos + PROP_HEADER
            if pname == b'name':
                value = blob[off:off + length].split(b'\0', 1)[0]
            cursor.prop_advance(length)
        if value is None:
            return None
        if value == name.encode():
            return child
    return None


def get_property(node, name, blob):
    cursor = Cursor(blob)
    cursor.pos = node
    n_props = cursor.u32(node)
    cursor.pos = node + 8
    for _ in range(n_props):
        length = cursor.u32(cursor.pos + PROP_NAME_LENGTH)
        pname = blob[cursor.pos:cursor.pos + PROP_NAME_LENGTH].split(b'\0', 1)[0]
        off = cursor.pos + PROP_HEADER
        cursor.prop_advance(length)
        if pname == name:
            return blob[off:off + length]
    return None


def report(path):
    blob = open(path, 'rb').read()
    print('=== %s (%d bytes) ===' % (path, len(blob)))
    n_props, n_children = struct.unpack_from('<II', blob, 0)
    print('root: nProperties=%d nChildren=%d' % (n_props, n_children))

    cursor = Cursor(blob)
    hit = find_entry(cursor, b'name', b'arm-io')
    print('\nSecureDTFindEntry("name","arm-io") -> %s'
          % ('FOUND @0x%x' % hit if hit is not None else 'NOT FOUND'))
    if hit is not None:
        ranges = get_property(hit, b'ranges', blob)
        if ranges is None:
            print('  ranges: MISSING')
        else:
            words = struct.unpack_from('<%dQ' % (len(ranges) // 8), ranges, 0)
            print('  ranges len=%d words=%s' % (len(ranges), ['0x%x' % w for w in words]))
            if len(words) >= 2:
                print('  gPESoCBasePhys = *(ranges+1) = 0x%x  -> %s'
                      % (words[1], 'nonzero' if words[1] else 'ZERO (early return!)'))

    cpus = lookup('/cpus', blob)
    print('\nSecureDTLookupEntry(NULL,"/cpus") -> %s'
          % ('FOUND @0x%x' % cpus if cpus is not None else 'NOT FOUND'))
    if cpus is not None:
        for index, child in enumerate(children_of(cpus, blob)):
            state = get_property(child, b'state', blob)
            tb = get_property(child, b'timebase-frequency', blob)
            if state is None:
                continue
            text = state.split(b'\0', 1)[0]
            match = text == b'running'
            print('  cpu%d state=%r len=%d running=%s timebase=%s'
                  % (index, text, len(state), match,
                     struct.unpack('<I', tb)[0] if tb and len(tb) == 4 else tb))

    # The first node with nProperties == 0 terminates XNU's walk. Report where
    # the walk actually stops, because a tree without the terminator makes the
    # cursor run past the end of the blob.
    cursor = Cursor(blob)
    pos = 0
    depth_ok = True
    while pos + 8 <= len(blob):
        n_props = struct.unpack_from('<I', blob, pos)[0]
        if n_props == 0:
            break
        pos = skip_tree(pos, blob)
    print('\nwalk terminator: %s'
          % ('nProperties==0 at 0x%x' % pos if pos + 8 <= len(blob)
             else 'NONE - the cursor runs past the end of the blob at 0x%x' % pos))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        report(arg)
        print()
