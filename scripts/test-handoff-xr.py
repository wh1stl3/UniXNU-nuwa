#!/usr/bin/env python3
"""Exercise the actual generated XR formatter on host."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_r35_display_diag import generate

root = Path(__file__).resolve().parents[1]
src = generate((root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(),
               mg_reset=True).decode()
body = src.split("  // exit_lock already protects both rings; XR describes only exit_ring.\n", 1)[1].split(
    "  __atomic_store_n(&exit_lock,0,__ATOMIC_RELEASE);", 1)[0]
assert "exit_records" not in body
program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct bp_exit_ring_entry { char comm[33]; unsigned pid,sig,pc_valid; uint64_t pc; };
static struct bp_exit_ring_entry exit_ring[4];
static unsigned exit_ring_count;
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
 exit_ring[0]=(struct bp_exit_ring_entry){"123456789abcdef",4294967295u,127,1,0x123456789abcdefULL};
 exit_ring[1]=exit_ring[0];
 render(rows,&n); assert(n==1);
 printf("%zu %s\n",strlen(rows[0]),rows[0]);
 assert(strlen(rows[0])<=80);
 assert(strlen(rows[0])==41);
 assert(strstr(rows[0],"89abcdef sig=127"));
 assert(strstr(rows[0]," |")==NULL);
 exit_ring[0].pc_valid=0; render(rows,&n);
 assert(strstr(rows[0]," - sig=127"));
 exit_ring_count=0; render(rows,&n); assert(n==0);
}
'''
two = body.replace('char xr[80]="XR";', 'char xr[120]="XR";').replace(
    'i<1;', 'i<2;').replace('part[48]', 'part[80]')
two_program = program.replace(body, two).replace(
    'assert(strlen(rows[0])<=80);', 'assert(strlen(rows[0])==82);').replace(
    'assert(strlen(rows[0])==41);', '').replace(
    'assert(strstr(rows[0]," |")==NULL);', '')
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / "test.c"
    exe = Path(tmp) / "test"
    c.write_text(program)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
    c.write_text(two_program)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
