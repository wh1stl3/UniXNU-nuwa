#!/usr/bin/env python3
"""Compile and exercise the exact generated banner value formatter."""
import importlib.util
import pathlib
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("renderer", root / "scripts/generate_r35_display_diag.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
generated = renderer.generate((root / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes(), mg_reset=True).decode()
start = generated.index("static void bp_short_value(")
end = generated.index("\n}\n", start) + 3
helper = generated[start:end]
assert 'UFS L r=%s rd=%s T r=%s rd=%s' in generated
assert 'SCHED n=%s m=%s x=%s >50=%s' in generated
assert 'SVC %02x K=%ux%u H=%u' in generated
assert ' TF=%u/%u' in generated
assert 'cs_text_fixup_parsed __attribute__((weak_import))' in generated
test = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
HELPER
int main(void) {
  const uint64_t values[] = {0, 1, 99, 999, 9999, 10000, 999999, 1000000,
                              999999999, UINT64_MAX};
  const char *units[] = {"", "ms", "us"};
  for (unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++)
    for (unsigned j=0;j<3;j++) {
      char out[7];
      bp_short_value(out, values[i], units[j]);
      assert(strlen(out)<=6);
      if (units[j][0]) assert(strstr(out, units[j]));
      printf("%llu %s => %s\n",(unsigned long long)values[i],units[j],out);
    }
  char boundary[7];
  bp_short_value(boundary,999999,"ms"); assert(!strcmp(boundary,"999kms"));
  bp_short_value(boundary,999999999,""); assert(!strcmp(boundary,"999M"));
  bp_short_value(boundary,UINT64_MAX,"us"); assert(!strcmp(boundary,"18Eus"));
  char row[120];
  snprintf(row,sizeof(row),"UFS L r=%s rd=%s T r=%s rd=%s","999999","9999ms","999999","9999ms");
  printf("%zu %s\n",strlen(row),row); assert(strlen(row)==45);
  snprintf(row,sizeof(row),"SCHED n=%s m=%s x=%s >50=%s","999999","9999us","9999us","999999");
  printf("%zu %s\n",strlen(row),row); assert(strlen(row)==43);
  snprintf(row,sizeof(row),"SVC %02x K=%ux%u H=%u", 0xffffffffu, 255u, 16777215u, 7u);
  printf("%zu %s\n",strlen(row),row); assert(strlen(row)==31);
  snprintf(row,sizeof(row),"SVC %02x K=%ux%u H=%u TF=%u/%u", 0xffffffffu, 255u, 16777215u, 7u,
           UINT32_MAX, UINT32_MAX);
  printf("%zu %s\n",strlen(row),row); assert(strlen(row)<=80);
  snprintf(row,sizeof(row),"SVC 00 K=0x0 H=0 TF=0/0");
  printf("%zu %s\n",strlen(row),row); assert(strlen(row)<=80);
}
""".replace("HELPER", helper)
with tempfile.TemporaryDirectory() as tmp:
    source = pathlib.Path(tmp) / "test.c"
    source.write_text(test)
    executable = pathlib.Path(tmp) / "test"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
