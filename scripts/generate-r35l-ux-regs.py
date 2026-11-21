#!/usr/bin/env python3
"""Limit the r35h exception ring to the targeted SpringBoard register snapshot."""
import runpy
from pathlib import Path

_base = runpy.run_path(str(Path(__file__).with_name("generate-r35j-ux-lr.py")))
once = _base["once"]
pinned = _base["pinned"]
OLD_ARGS = "    uint64_t subcode, uint64_t pc, int pc_valid)"
NEW_ARGS = "    uint64_t subcode, uint64_t pc, const uint64_t regs[7])"


def generate_ux(data):
    text = pinned(data, "b081ec0104c522aec658029b5bf5cf7a4d4d7a3e31c00fcc8cca83feb4f4b7f6")
    text = once(text, OLD_ARGS + ";", NEW_ARGS + ";")
    return once(text, """	if (exception > 0 && exception < EXC_TYPES_COUNT) {
		const arm_saved_state_t *saved = get_user_regs(thread);
		boot_progress_exception(proc_pid(p), (unsigned)exception,
		    (uint64_t)code, (uint64_t)subcode,
		    saved ? get_saved_state_pc(saved) : 0, saved != NULL);
	}""", """	if (exception == EXC_BREAKPOINT &&
	    !strncmp(p->p_comm, "SpringBoard", sizeof("SpringBoard"))) {
		const arm_saved_state_t *saved = get_user_regs(thread);
		if (saved && is_saved_state64(saved)) {
			uint64_t pc = get_saved_state_pc(saved);
			if ((pc & 0xfff) == 0xca8) {
				const uint64_t *x = const_saved_state64(saved)->x;
				const uint64_t regs[7] = { x[0], x[1], x[2], x[19], x[20], x[21], x[22] };
				boot_progress_exception(proc_pid(p), (unsigned)exception,
				    (uint64_t)code, (uint64_t)subcode, pc, regs);
			}
		}
	}""").encode()


def generate_renderer(data):
    text = pinned(data, "27ff1837a5a576db23c2e4d4049f7be6514fdf4344d750bd7b43d7ebb94ebbf6")
    text = once(text, "  unsigned type;\n  int pc_valid;\n", "  unsigned type;\n  uint64_t regs[7];\n")
    text = once(text, OLD_ARGS + ";", NEW_ARGS + ";")
    text = once(text, OLD_ARGS + " {", NEW_ARGS + " {")
    text = once(text, "    .pid=pid, .type=type, .code=code, .subcode=subcode, .pc=pc, .pc_valid=pc_valid",
                """    .pid=pid, .type=type, .code=code, .subcode=subcode, .pc=pc,
    .regs={regs[0],regs[1],regs[2],regs[3],regs[4],regs[5],regs[6]}""")
    text = once(text, """    char pc[17]="-";
    if (x->pc_valid) snprintf(pc,sizeof(pc),"%llx",(unsigned long long)x->pc);
    snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
      x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);
    line(6,b,0xff00ffcc);""", """    snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%llx",
      x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,
      (unsigned long long)x->pc);
    line(6,b,0xff00ffcc);
    snprintf(b,sizeof(b),"X2 x0=%016llx x19=%016llx x20=%016llx",
      (unsigned long long)x->regs[0],(unsigned long long)x->regs[3],
      (unsigned long long)x->regs[4]);
    line(7,b,0xff00ffcc);
    // Register indices precede the four complete hex values, in order.
    snprintf(b,sizeof(b),"X3 1/2/21/22=%016llx/%016llx/%016llx/%016llx",
      (unsigned long long)x->regs[1],(unsigned long long)x->regs[2],
      (unsigned long long)x->regs[5],(unsigned long long)x->regs[6]);
    line(8,b,0xff00ffcc);""")
    return once(text, "    line(7, b, 0xff00ffff);", "    if (!x->type) line(7, b, 0xff00ffff);").encode()
