#!/usr/bin/env python3
"""Add SpringBoard breakpoint frame records to the r35g/r35h diagnostic."""
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
    text = once(text, "#include <arm/thread.h>\n", """#include <arm/thread.h>
#include <kern/task.h>
#include <machine/machine_routines.h>
#include <vm/pmap.h>
#include <vm/vm_map.h>

#if defined(HAS_APPLE_PAC)
#include <ptrauth.h>
#endif
""")
    text = once(text, "    uint64_t subcode, uint64_t pc, int pc_valid);",
                """    uint64_t subcode, uint64_t pc, int pc_valid,
    const uint64_t *lr, unsigned lr_count);

static unsigned
nuwa_breakpoint_lr(thread_t thread, const arm_saved_state_t *saved, uint64_t lr[3])
{
	if (saved == NULL || !is_saved_state64(saved) || !ml_get_interrupts_enabled()) {
		return 0;
	}

	user_addr_t fp = get_saved_state_fp(saved);
	vm_map_t map = get_task_map_reference(get_threadtask(thread));
	if (map == VM_MAP_NULL) {
		return 0;
	}

	unsigned count = 0;
	/* copyin() permits kernel-to-kernel copies; exclude that path. */
	if (vm_map_get_pmap(map) != pmap_kernel()) {
		vm_map_t old_map = current_map() != map ? vm_map_switch(map) : VM_MAP_NULL;
		while (count < 3) {
			struct { uint64_t prev, lr; } frame;
			if (fp == 0 || (fp & 15) || copyin(fp, &frame, sizeof(frame)) != 0) {
				break;
			}
#if defined(HAS_APPLE_PAC)
			frame.lr = (uintptr_t)ptrauth_strip((void *)(uintptr_t)frame.lr,
			    ptrauth_key_return_address);
#endif
			if (frame.lr == 0) {
				break;
			}
			lr[count++] = frame.lr;
			/* Keep the readable frame; reject an invalid link to the next one. */
			if (frame.prev <= fp) {
				break;
			}
			fp = frame.prev;
		}
		if (old_map != VM_MAP_NULL) {
			(void)vm_map_switch(old_map);
		}
	}
	vm_map_deallocate(map);
	return count;
}""")
    return once(text, """		boot_progress_exception(proc_pid(p), (unsigned)exception,
		    (uint64_t)code, (uint64_t)subcode,
		    saved ? get_saved_state_pc(saved) : 0, saved != NULL);""",
                """		uint64_t lr[3];
		bool capture_lr = exception == EXC_BREAKPOINT &&
		    !strncmp(p->p_comm, "SpringBoard", sizeof("SpringBoard"));
		unsigned lr_count = capture_lr ? nuwa_breakpoint_lr(thread, saved, lr) : 0;
		boot_progress_exception(proc_pid(p), (unsigned)exception,
		    (uint64_t)code, (uint64_t)subcode,
		    saved ? get_saved_state_pc(saved) : 0, saved != NULL,
		    capture_lr ? lr : NULL, lr_count);""").encode()


def generate_renderer(data):
    text = pinned(data, "27ff1837a5a576db23c2e4d4049f7be6514fdf4344d750bd7b43d7ebb94ebbf6")
    text = once(text, "  uint64_t code, subcode, pc;\n",
                "  uint64_t code, subcode, pc, lr[3];\n"
                "  unsigned lr_count;\n"
                "  int lr_requested;\n")
    old = "    uint64_t subcode, uint64_t pc, int pc_valid)"
    assert text.count(old) == 2
    text = text.replace(old, "    uint64_t subcode, uint64_t pc, int pc_valid,\n"
                            "    const uint64_t *lr, unsigned lr_count)")
    text = once(text, "  exception_ring[exception_next]=(struct bp_exception_entry){",
                "  struct bp_exception_entry *e=&exception_ring[exception_next];\n"
                "  *e=(struct bp_exception_entry){\n"
                "    .lr_requested=(lr!=0), .lr_count=lr_count,")
    text = once(text, "  exception_next=(exception_next+1)%4;",
                "  for (unsigned i=0; i<lr_count; ++i) e->lr[i]=lr[i];\n"
                "  exception_next=(exception_next+1)%4;")
    return once(text, """    snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
      x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);""",
                """    if (x->lr_requested) {
      char lr[17]="UNKNOWN";
      if (x->lr_count) snprintf(lr,sizeof(lr),"%llx",(unsigned long long)x->lr[0]);
      if (snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s lr=%s",
          x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc,lr)>80)
        snprintf(b,sizeof(b),"X1 pid=%d t=%x cs24=%06x/%06x pc=%s lr=%s",
          x->pid,x->type,(unsigned)x->code&0xffffff,(unsigned)x->subcode&0xffffff,pc,lr);
    } else {
      snprintf(b,sizeof(b),"X1 pid=%d t=%x c=%llx s=%llx pc=%s",
        x->pid,x->type,(unsigned long long)x->code,(unsigned long long)x->subcode,pc);
    }""").encode()
