#!/usr/bin/env python3
"""Generate the isolated r35g exception tap and its boot-progress row."""
import hashlib

UX_SHA = "ec87d1dcfa6cdb5132ce0e219db26d5c11079bbc65a4df543bdc5e7be616b0af"
RENDERER_SHA = "c8948cea7090fa6397dfd372c0eb9f5c56b80189450f940b563eb10e5258275c"


def pin(data, sha):
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"r35g input mismatch: expected {sha}")
    return data


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"r35g anchor changed: {old}")
    return text.replace(old, new, 1)


def generate_ux(data):
    text = pin(data, UX_SHA).decode()
    text = replace_once(text, "#include <sys/ux_exception.h>\n", """#include <sys/ux_exception.h>

#include <arm/thread.h>

extern void boot_progress_exception(int pid, unsigned type, uint64_t code,
    uint64_t subcode, uint64_t pc, int pc_valid);
""")
    return replace_once(text, "\tint ux_signal = ux_exception(exception, code, subcode);\n",
                        """\tint ux_signal = ux_exception(exception, code, subcode);
\tif (exception > 0 && exception < EXC_TYPES_COUNT) {
\t\tconst arm_saved_state_t *saved = get_user_regs(thread);
\t\tboot_progress_exception(proc_pid(p), (unsigned)exception,
\t\t    (uint64_t)code, (uint64_t)subcode,
\t\t    saved ? get_saved_state_pc(saved) : 0, saved != NULL);
\t}
""").encode()


def generate_renderer(data):
    text = pin(data, RENDERER_SHA).decode()
    text = replace_once(text, "struct bp_exit_view { struct bp_exit_ring_entry entries[4]; unsigned count; };",
                        """struct bp_exception_entry {
  uint64_t code, subcode, pc;
  int pid;
  unsigned type;
  int pc_valid;
};
static struct bp_exception_entry exception_ring[4];
static unsigned exception_next;

struct bp_exit_view {
  struct bp_exit_ring_entry entries[4];
  unsigned count;
  struct bp_exception_entry exception;
};""")
    text = replace_once(text, "static unsigned enabled, busy, started, last_draw = ~0U;",
                        """static unsigned enabled, busy, started, last_draw = ~0U;

void boot_progress_exception(int pid, unsigned type, uint64_t code,
    uint64_t subcode, uint64_t pc, int pc_valid);
void boot_progress_exception(int pid, unsigned type, uint64_t code,
    uint64_t subcode, uint64_t pc, int pc_valid) {
  if (!enabled || __atomic_exchange_n(&exit_lock,1,__ATOMIC_ACQUIRE)) return;
  exception_ring[exception_next]=(struct bp_exception_entry){
    .pid=pid, .type=type, .code=code, .subcode=subcode, .pc=pc, .pc_valid=pc_valid
  };
  exception_next=(exception_next+1)%4;
  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);
}""")
    text = replace_once(text, "  view->count=exit_ring_count;\n",
                        "  view->count=exit_ring_count;\n"
                        "  view->exception=exception_ring[(exception_next+3)%4];\n")
    return replace_once(text, "  if(&nuwa_systemos_row3) line(5,nuwa_systemos_row3(),0xff00ffcc);",
                        """  const struct bp_exception_entry *x=&exit_view.exception;
  if (x->type) {
    char pc[17]="-";
    if (x->pc_valid) snprintf(pc,sizeof(pc),"%llx",(unsigned long long)x->pc);
    snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
      x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);
    line(5,b,0xff00ffcc);
  } else if(&nuwa_systemos_row3) line(5,nuwa_systemos_row3(),0xff00ffcc);""").encode()
