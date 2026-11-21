#!/usr/bin/env python3
"""Apply the r35h layout to the pinned r35g renderer."""
import hashlib


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("r35h anchor mismatch: " + old[:100])
    return text.replace(old, new, 1)


def generate(data):
    if hashlib.sha256(data).hexdigest() != "fd55972223684d9d507b046d2c348803586ac0ffe8f89ab6d60b06c94193d084":
        raise ValueError("r35h renderer pin mismatch")
    text = data.decode()
    text = once(text,
        'if(!strcmp(exit_ring[i].comm,comm) && exit_ring[i].sig==signal &&',
        'if(exit_ring[i].pid==(unsigned)pid && !strcmp(exit_ring[i].comm,comm) && exit_ring[i].sig==signal &&')
    # Leave row zero unused on every normal and handoff drawing path.
    text = once(text, '  capture(row,text);\n  // Reserve the last diagnostic row',
                '  if (!row) return;\n  capture(row,text);\n  // Reserve the last diagnostic row')
    text = once(text, 'static void bar(unsigned row, const char *text, uint32_t color, uint32_t background) {\n',
                'static void bar(unsigned row, const char *text, uint32_t color, uint32_t background) {\n  if (!row) return;\n')
    start = text.index('  // r21: every title variant')
    end = text.index('  // r21: shortened labels', start)
    text = text[:start] + '''  snprintf(b,sizeof(b),"[nuwa-r35] t=%us m=%llu np=%d i=%us q=%llu l=%u r=%d f=%u",
    now,thread_count,nprocs,now-visible->activity_at,irq_count,visible->dropped,
    native_owner_root_accepted,vm_page_free_count);
  if (strlen(b)>80) snprintf(b,sizeof(b),"[nuwa-r35] t=%us m=%llu np=%d",now,thread_count,nprocs);
  line(1,b,0xffffffff);
''' + text[end:]
    start = text.index('  const struct bp_exception_entry *x=&exit_view.exception;')
    end = text.index('  // nuwa r12 (N4)', start)
    exception = text[start:end].replace('line(5,', 'line(6,')
    text = text[:start] + text[end:]
    start = text.index('  // r33: row 6 is inside the panic-safe band')
    end = text.index('  if(!__atomic_exchange_n(&exit_lock', start)
    stage = text[start:end].replace('line(6, b,', 'line(7, b,')
    stage = once(stage, '    line(7, b, 0xff00ffff);',
                 '    if (strlen(b)>80) snprintf(b,sizeof(b),"%s",stage);\n'
                 '    line(7, b, 0xff00ffff);')
    text = text[:start] + text[end:]
    start = text.index('  if (exit_view.count) {', text.index('  nuwa_rows();'))
    end = text.index('#if NUWA_GLYPH_SELFTEST', start)
    text = text[:start] + '''  for (unsigned i=0; i<4; ++i) {
    if (i<exit_view.count) {
      const struct bp_exit_ring_entry *e=&exit_view.entries[i];
      if(e->pc_valid)
        snprintf(b,sizeof(b),"EX%u p%u %-6.6s sig=%u code=0x%08x n=%u pc=%016llx",
          i+1,e->pid,e->comm[0]?e->comm:"?",e->sig,(unsigned)e->code,e->count,(unsigned long long)e->pc);
      else
        snprintf(b,sizeof(b),"EX%u p%u %-6.6s sig=%u code=0x%08x n=%u pc=----------------",
          i+1,e->pid,e->comm[0]?e->comm:"?",e->sig,(unsigned)e->code,e->count);
      line(i+2,b,0xffffffff);
    } else line(i+2,"",0xffffffff);
  }
''' + exception + stage + text[end:]
    return text.encode()
