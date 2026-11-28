#!/usr/bin/env python3
"""Exercise generated XR/XP formatters and banner priority on the host."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_r35_display_diag import generate
from generate_nuwa_postevent import generate as postevent

root = Path(__file__).resolve().parents[1]
src = postevent(generate((root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(),
                         mg_reset=True, pixsig=True), v1_nodur=True, sb_threads=True)[0].decode()
assert "line(4u+i,rows[i]" in src and "bp_rg_row(b,sizeof(b)); line(9,b" in src
assert "px_text(0,0,rows[0]" in src and "px_text(0,(48u+i)*cell" in src
selection = src[src.index("static unsigned bp_banner_priority("):
                src.index("static unsigned bp_pix_rows(")]
body = src.split("  // exit_lock already protects both rings; XR describes only exit_ring.\n", 1)[1].split(
    "  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);", 1)[0]
assert "exit_records" not in body
program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct bp_exit_ring_entry {
  char comm[33]; unsigned pid,sig,pc_valid; uint64_t pc,image_base; unsigned image_base_valid;
};
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_ring_count;
''' + selection + r'''
static size_t strlcat(char *d,const char *s,size_t n) {
  size_t l=strlen(d), m=strlen(s);
  if(l<n) strncat(d,s,n-l-1);
  return l+m;
}
static void render(char rows[][120], unsigned *count) {
  unsigned n=0;
''' + body + r'''
  *count=n;
}
int main(void) {
 char rows[4][120]; unsigned n;
 exit_ring_count=2;
 exit_ring[0]=(struct bp_exit_ring_entry){
   .comm="123456789abcdef", .pid=4294967295u, .sig=127, .pc_valid=1,
   .pc=0x0123456789abcdefULL, .image_base=0xfedcba9876543210ULL, .image_base_valid=1};
 exit_ring[1]=exit_ring[0];
 render(rows,&n); assert(n==2);
 printf("%zu %s\n",strlen(rows[0]),rows[0]);
 assert(strlen(rows[0])<=80);
 assert(strlen(rows[0])==41);
 assert(strstr(rows[0],"89abcdef sig=127"));
 assert(strstr(rows[0]," |")==NULL);
 assert(!strcmp(rows[1],"XP p4294967295 pc=0123456789abcdef b=fedcba9876543210"));
 printf("%zu %s\n",strlen(rows[1]),rows[1]);
 assert(strlen(rows[1])<80 && strlen(rows[1])<120);
 exit_ring[0].pc_valid=0; exit_ring[0].image_base_valid=0; render(rows,&n);
 assert(strstr(rows[0]," - sig=127"));
 assert(!strcmp(rows[1],"XP p4294967295 pc=- b=-"));
 exit_ring[0].pc_valid=1; exit_ring[0].pc=0;
 exit_ring[0].image_base_valid=1; exit_ring[0].image_base=0; render(rows,&n);
 assert(!strcmp(rows[1],"XP p4294967295 pc=0000000000000000 b=0000000000000000"));
 exit_ring_count=0; render(rows,&n); assert(n==0);
 char priority[4][120]={"XP p1","RG en=1","SBTH n=1","PROC n=1"};
 assert(bp_banner_select(priority,4,3)==3);
 for(unsigned i=0;i<3;i++) assert(strncmp(priority[i],"XP ",3));
 }
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "test.c"
    exe = Path(tmp) / "test"
    c.write_text(program)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
