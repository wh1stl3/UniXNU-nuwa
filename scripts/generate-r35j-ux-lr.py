#!/usr/bin/env python3
"""Add saved x29/x30 to the SpringBoard breakpoint diagnostic."""
import hashlib


def pinned(data, sha):
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError("r35j source pin mismatch")
    return data.decode()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"r35j anchor changed: {old}")
    return text.replace(old, new, 1)


def generate_ux(data):
    text = pinned(data, "b081ec0104c522aec658029b5bf5cf7a4d4d7a3e31c00fcc8cca83feb4f4b7f6")
    text = once(text, "    uint64_t subcode, uint64_t pc, int pc_valid);",
                "    uint64_t subcode, uint64_t pc, int pc_valid,\n"
                "    uint64_t x29, uint64_t x30, int regs_requested, int regs_valid);")
    return once(text, """		boot_progress_exception(proc_pid(p), (unsigned)exception,
		    (uint64_t)code, (uint64_t)subcode,
		    saved ? get_saved_state_pc(saved) : 0, saved != NULL);""",
                """		int requested = exception == EXC_BREAKPOINT &&
		    !strncmp(p->p_comm, "SpringBoard", sizeof("SpringBoard"));
		int valid = requested && saved && is_saved_state64(saved);
		boot_progress_exception(proc_pid(p), (unsigned)exception,
		    (uint64_t)code, (uint64_t)subcode,
		    saved ? get_saved_state_pc(saved) : 0, saved != NULL,
		    valid ? get_saved_state_fp(saved) : 0,
		    valid ? get_saved_state_lr(saved) : 0, requested, valid);""").encode()


def generate_renderer(data):
    text = pinned(data, "27ff1837a5a576db23c2e4d4049f7be6514fdf4344d750bd7b43d7ebb94ebbf6")
    text = once(text, "  uint64_t code, subcode, pc;\n",
                "  uint64_t code, subcode, pc, x29, x30;\n"
                "  int regs_requested, regs_valid;\n")
    old = "    uint64_t subcode, uint64_t pc, int pc_valid)"
    assert text.count(old) == 2
    text = text.replace(old, "    uint64_t subcode, uint64_t pc, int pc_valid,\n"
                            "    uint64_t x29, uint64_t x30, int regs_requested, int regs_valid)")
    text = once(text, "    .pid=pid, .type=type, .code=code, .subcode=subcode, .pc=pc, .pc_valid=pc_valid",
                "    .x29=x29, .x30=x30, .regs_requested=regs_requested, .regs_valid=regs_valid,\n"
                "    .pid=pid, .type=type, .code=code, .subcode=subcode, .pc=pc, .pc_valid=pc_valid")
    return once(text, """    snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
      x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);""",
                """    if (x->regs_requested) {
      char x30[17]="UNKNOWN";
      if (x->regs_valid) snprintf(x30,sizeof(x30),"%llx",(unsigned long long)x->x30);
      if (snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s x30=%s",
          x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc,x30)>80)
        snprintf(b,sizeof(b),"X1 pid=%d t=%x cs16=%04x/%04x pc=%s x30=%s",
          x->pid,x->type,(unsigned)x->code&0xffff,(unsigned)x->subcode&0xffff,pc,x30);
    } else {
      snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
        x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);
    }""").encode()
