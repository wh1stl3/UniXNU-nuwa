#!/usr/bin/env python3
"""Model r35h from the generated C; this does not execute kernel C."""
import re
import sys
from pathlib import Path


def check(label, ok, detail):
    print(f"{label:28} {'PASS' if ok else 'FAIL'} {detail}")
    if not ok:
        raise AssertionError(label)


def capture(pattern, text):
    found = re.search(pattern, text, re.S)
    if not found:
        raise ValueError("missing C anchor: " + pattern)
    return found


def main():
    path = Path(sys.argv[1])
    c = path.read_text()
    display = (path.parent / "BootProgressDisplay.h").read_text()
    draw = c[c.index("static void draw(unsigned now)"):c.index("// Published by arm_init")]
    wrappers = c[c.index("static void line(unsigned row"):c.index("// nuwa r12 (N7)")]
    guard = r"static void %s\(unsigned row[^{}]*\{\s*if \(!row\) return;"
    check("row 0 wrapper guards", all(re.search(guard % name, wrappers) for name in ("line", "bar")),
          "line/bar return before capture and framebuffer writes")
    stride = int(capture(r"row\*([0-9]+)\*d->scale", display)[1])
    cell = int(capture(r"width\s*/\s*\(\s*([0-9]+)\s*\*\s*d->scale", display)[1])
    cap = int(capture(r"if \(strlen\(b\)>(\d+)\) snprintf", draw)[1])
    exbase = int(capture(r"line\(i\+(\d+),b,0xffffffff\)", draw)[1])
    exfmt = capture(r'"(EX%u p%u [^"]+pc=%016llx)"', draw)[1]
    xfmt = capture(r'"(X1 pid=%d [^"]+)"', draw)[1]
    xrow = int(capture(r'X1 pid=%d.*?line\((\d+),b,0xff00ffcc\)', draw)[1])
    stgrow = int(capture(r'snprintf\(stage, sizeof\(stage\), "stg.*?line\((\d+), b, 0xff00ffff\)', draw)[1])
    statrow = int(capture(r'"\[nuwa-r35\] t=%us m=%llu np=%d".*?line\((\d+),b,0xffffffff\)', draw)[1])
    check("rows", (statrow,exbase,xrow,stgrow)==(1,2,6,7), f"counter={statrow} EX={exbase}..{exbase+3} X1={xrow} stg={stgrow}")
    check("counter mandatory fields", all(x in draw for x in ("[nuwa-r35] t=%us", "m=%llu", "np=%d")), "tag t= m= np=")
    check("format strings", exfmt=="EX%u p%u %-6.6s sig=%u code=0x%08x n=%u pc=%016llx" and
          xfmt=="X1 pid=%d t=%x c=%llx s=%llx pc=%s", f"EX={exfmt}; X1={xfmt}")
    hook = c[c.index("void boot_progress_exit(int pid,"):c.index("// The log's [spawn] section")]
    key = capture(r"if\(exit_ring\[i\]\.pid==\(unsigned\)pid && !strcmp\(exit_ring\[i\]\.comm,comm\) && exit_ring\[i\]\.sig==signal &&\s*exit_ring\[i\]\.ns==ns && exit_ring\[i\]\.code==code\)", hook)
    check("merge key source", bool(key), "pid, comm, sig, ns, code (full 64-bit)")
    ring = []
    def add(pid, comm, sig, ns, code):
        k = (pid,comm,sig,ns,code)
        for entry in ring:
            if entry[0] == k:
                entry[1] += 1
                return
        ring.insert(0,[k,1])
        del ring[4:]
    add(99999,"abcdef",127,0xffffffff,1)
    add(99999,"abcdef",127,0xffffffff,1)
    check("same PID merges", len(ring)==1 and ring[0][1]==2, str(ring))
    add(99998,"abcdef",127,0xffffffff,1)
    check("different PID separate", len(ring)==2 and ring[0][0][0]==99998, str(ring))
    add(99999,"abcdef",127,0xffffffff,0x100000001)
    check("high code bits separate", len(ring)==3 and ring[0][0][-1]!=ring[-1][0][-1], str(ring))
    ex = "EX%d p%d %-6.6s sig=%d code=0x%08x n=%d pc=%016x" % (1,99999,"abcdef",127,0xffffffff,0xffffffff,0xffffffffffffffff)
    x1 = "X1 pid=%d t=%x c=%x s=%x pc=%x" % (99999,13,0xffffffffffffffff,0xffffffffffffffff,0xffffffffffffffff)
    counter = "[nuwa-r35] t=%us m=%u np=%d" % (0xffffffff,0xffffffffffffffff,99999)
    stage = "%-24s %s n=%u" % ("stg " + "x"*20,"AKS" + " ffff:ff"*4,9999)
    rows = {1:counter,2:ex,3:ex.replace("EX1","EX2",1),4:ex.replace("EX1","EX3",1),
            5:ex.replace("EX1","EX4",1),6:x1,7:stage if len(stage)<=cap else stage[:24]}
    check("capacity", cap==80 and cell==6 and stride==14, f"limit={cap} cell={cell} row_height={stride}")
    for scale in (1,2,3):
        for row,text in rows.items():
            columns = 1440//(cell*scale)
            check(f"scale={scale} row={row}", row>=1 and len(text)<=min(cap,columns) and "\n" not in text,
                  f"y={row*stride*scale} cols={len(text)}/{columns} width={len(text)*cell*scale}px")
    check("EX/X1 presence variants", "if (i<exit_view.count)" in draw and "if (x->type)" in draw and
          'else line(i+2,"",0xffffffff)' in draw, "no EX / four EX / X1 absent / X1 present")
    print("Python source model only; no compiled execution or physical visibility claim.")


if __name__ == "__main__":
    main()
