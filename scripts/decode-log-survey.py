"""Validate transcribed survey pages; requires every row and canonical CRC32."""
import argparse,json,re,struct,zlib
from pathlib import Path

def decode(text):
    maps={};current=None;pending=None
    for line in text.splitlines():
        m=re.fullmatch(r'NUWA SURVEY1 MAP=([01]) PAGE=([0-9A-F]{4}) COUNT=([0-9A-F]{4})',line)
        if m:
            if pending is not None:raise ValueError('Missing descriptor continuation')
            ident,page,count=(int(v,16) for v in m.groups())
            if not 0<count<=3276 or page>=(count+5)//6:raise ValueError('Invalid page bounds')
            current=maps.setdefault(ident,dict(count=count,rows={},pages=set()))
            if current['count']!=count:raise ValueError('Mixed map snapshots')
            current['pages'].add(page);continue
        if current is None:continue
        m=re.fullmatch(r'bytes=([0-9A-F]{8}) stride=([0-9A-F]{4}) ver=([0-9A-F]{4})',line)
        if m:
            val=tuple(int(v,16) for v in m.groups())
            if 'metadata' in current and current['metadata']!=val:raise ValueError('Mixed map metadata')
            current['metadata']=val;continue
        m=re.fullmatch(r'CANONICAL CRC32=([0-9A-F]{8})',line)
        if m:
            value=int(m[1],16)
            if 'crc32' in current and current['crc32']!=value:raise ValueError('Mixed CRC')
            current['crc32']=value;continue
        m=re.fullmatch(r'([0-9A-F]{4}) ([0-9A-F]{8}) ([0-9A-F]{16}) ([0-9A-F]{16})',line)
        if m:
            if pending is not None:raise ValueError('Missing descriptor continuation')
            pending=tuple(int(v,16) for v in m.groups());continue
        m=re.fullmatch(r' V=([0-9A-F]{16}) A=([0-9A-F]{16})',line)
        if m:
            if pending is None:raise ValueError('Orphan continuation')
            index,kind,physical,pages=pending;pending=None
            virtual,attribute=(int(v,16) for v in m.groups());row=(kind,physical,virtual,pages,attribute)
            if index in current['rows'] and current['rows'][index]!=row:raise ValueError('Conflicting repeated row')
            current['rows'][index]=row
    if pending is not None or set(maps)!={0,1}:raise ValueError('Need complete before and held maps')
    result=[]
    for ident,m in sorted(maps.items()):
        n=m['count']
        if set(m['rows'])!=set(range(n)) or m['pages']!=set(range((n+5)//6)):raise ValueError('Missing rows/pages')
        size,stride,version=m.get('metadata',(0,0,0))
        if stride<40 or stride>256 or stride%8 or size!=stride*n or version!=1:raise ValueError('Invalid descriptor metadata')
        rows=[m['rows'][i] for i in range(n)]
        crc=zlib.crc32(b''.join(struct.pack('<IQQQQ',*r) for r in rows))
        if crc!=m.get('crc32'):raise ValueError('Canonical CRC mismatch')
        ranges=[]
        for kind,pa,va,pages,attr in rows:
            end=pa+pages*4096
            if pa%4096 or not pages or end>=2**64:raise ValueError('Invalid physical extent')
            if any(pa<b and a<end for a,b in ranges):raise ValueError('Overlapping descriptors')
            ranges.append((pa,end))
        result.append(dict(id=ident,descriptor_count=n,stride=stride,canonical_crc32=f'{crc:08x}',
          descriptors=[dict(type=r[0],physical=hex(r[1]),virtual=hex(r[2]),pages=r[3],attributes=hex(r[4])) for r in rows]))
    return dict(scope='Validated standard descriptor transcription; raw stride padding not exported; no reset retention proof',maps=result)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('transcript',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Fresh output required')
    result=decode(a.transcript.read_text(encoding='utf-8-sig'))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS complete map rows and canonical CRC32')
if __name__=='__main__':main()
