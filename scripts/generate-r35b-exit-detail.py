#!/usr/bin/env python3
"""Generate the detailed exit recorder from the pinned compact r35b renderer."""
import hashlib

SHA = "a4163ecd10ecfd6bb429f2ce9c919f9a67a6dab85c936beeabb8f7fba2fe89be"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("renderer anchor changed: " + old[:100])
    return text.replace(old, new, 1)


def generate(data):
    if hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError("compact renderer pin mismatch")
    text = data.decode()
    text = replace_once(text,
        "  char comm[7];\n  unsigned pid, sig, ns, code, nprocs, aks_calls, aks_opens;",
        "  char comm[33];\n  unsigned pid, sig, ns, nprocs, aks_calls, aks_opens, count, pc_valid;\n  uint64_t code, pc;")
    text = replace_once(text, "static unsigned exit_ring_count;",
                        """static unsigned exit_ring_count;
struct bp_exit_view { struct bp_exit_ring_entry entries[4]; unsigned count; };
static int bp_exit_view_take(struct bp_exit_view *view) {
  if(__atomic_exchange_n(&exit_lock,1,__ATOMIC_ACQUIRE)) return 0;
  memcpy(view->entries,exit_ring,sizeof(exit_ring));
  view->count=exit_ring_count;
  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);
  return 1;
}""")
    text = replace_once(text, "  const struct bp_core *visible=started ? &render_snapshot : &state;",
                        "  struct bp_exit_view exit_view;\n  if(!bp_exit_view_take(&exit_view)) return;\n  const struct bp_core *visible=started ? &render_snapshot : &state;")
    start = text.index("  if(exit_ring_count) {\n", text.index("// r35: the bar row"))
    end = text.index("  // r21: labels shortened", start)
    text = text[:start] + '''  if (!exit_view.count) {
    if(build_tag[0]) snprintf(b,sizeof(b)," [%s] %s",build_tag,title); else snprintf(b,sizeof(b)," %s",title);
    bar(0,b,0xffffffff,visible->reason && !visible->continuous ? BP_BAR_STOP : BP_BAR_LIVE);
  }
''' + text[end:]
    # Draw last: rows 0,2,3,4 replace the title/UFS/PID1 rows, never counters row 1.
    text = replace_once(text, "  nuwa_rows();\n", '''  nuwa_rows();
  if (exit_view.count) {
    for (unsigned i=0; i<exit_view.count && i<4; ++i) {
      const struct bp_exit_ring_entry *e=&exit_view.entries[i];
      if(e->pc_valid)
        snprintf(b,sizeof(b),"EX%u %-6.6s sig=%u ns=%08x code=0x%08x n=%u pc=%016llx",
          i+1,e->comm[0]?e->comm:"?",e->sig,e->ns,(unsigned)e->code,e->count,(unsigned long long)e->pc);
      else
        snprintf(b,sizeof(b),"EX%u %-6.6s sig=%u ns=%08x code=0x%08x n=%u pc=----------------",
          i+1,e->comm[0]?e->comm:"?",e->sig,e->ns,(unsigned)e->code,e->count);
      if (!i) bar(0,b,0xffffffff,visible->reason && !visible->continuous ? BP_BAR_STOP : BP_BAR_LIVE);
      else line(i+1,b,0xffffffff);
    }
  }
''')
    old = '''    for(unsigned i=3;i>0;--i) exit_ring[i]=exit_ring[i-1];
    memset(&exit_ring[0],0,sizeof(exit_ring[0]));
    if(name) { for(unsigned i=0;i<6 && name[i];++i) exit_ring[0].comm[i]=name[i]; }'''
    new = '''    const char *comm=name?name:"";
    unsigned found=exit_ring_count;
    for(unsigned i=0;i<exit_ring_count;++i)
      if(!strcmp(exit_ring[i].comm,comm) && exit_ring[i].sig==signal &&
         exit_ring[i].ns==ns && exit_ring[i].code==code) { found=i; break; }
    unsigned slot;
    if(found<exit_ring_count) {
      slot=found;
      if(exit_ring[found].count!=~0u) ++exit_ring[found].count;
    } else {
      slot=0;
      for(unsigned i=3;i>0;--i) exit_ring[i]=exit_ring[i-1];
      memset(&exit_ring[0],0,sizeof(exit_ring[0]));
      strlcpy(exit_ring[0].comm,comm,sizeof(exit_ring[0].comm));
      exit_ring[0].count=1;
      if(exit_ring_count<4)exit_ring_count++;
    }'''
    # A found slot is updated in place, preserving the first observation and order.
    text = replace_once(text, old, new)
    begin = text.index("    exit_ring[0].pid=pid;", text.index("void boot_progress_exit(int pid,"))
    end = text.index("    for(unsigned i=0;i<4;++i) {", begin)
    text = text[:begin] + '''    if(slot==0 && exit_ring[0].count==1) {
      exit_ring[0].pid=pid;
      exit_ring[0].sig=signal;
      exit_ring[0].ns=ns;
      exit_ring[0].code=code;
      if(pid==proc_selfpid()) {
        const arm_saved_state_t *saved=get_user_regs(current_thread());
        if(saved) { exit_ring[0].pc=get_saved_state_pc(saved); exit_ring[0].pc_valid=1; }
      }
      exit_ring[0].nprocs=(unsigned)nprocs;
      exit_ring[0].aks_calls=(&nuwa_aks_calls)?(unsigned)nuwa_aks_calls:0u;
      exit_ring[0].aks_opens=(&nuwa_aks_opens)?(unsigned)nuwa_aks_opens:0u;
    }
''' + text[end:]
    text = replace_once(text, "memcpy(nuwa_exit_ring_comm[i],exit_ring[i].comm,7);",
                        "memcpy(nuwa_exit_ring_comm[i],exit_ring[i].comm,6); nuwa_exit_ring_comm[i][6]=0;")
    text = replace_once(text,
                        "(unsigned)nprocs, exit_ring[0].aks_calls, exit_ring[0].aks_opens);",
                        "(unsigned)nprocs, exit_ring[slot].aks_calls, exit_ring[slot].aks_opens);")
    return text.encode()
