#!/usr/bin/env python3
"""Exercise the production sampler, PIX formatter and banner row budget."""
from pathlib import Path
import runpy
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
diag = runpy.run_path(str(ROOT / "scripts/generate_r35_display_diag.py"))
fixture = r"""
#include "NuwaPixelSig.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
""" + (diag["BANNER_SELECTION"] + diag["PIX_ROWS"]).decode() + r"""
static struct nuwa_pix_state state;
static unsigned char pixels[20*96];

static void show(const char *label, uint32_t crc, unsigned nz, unsigned uc,
                 unsigned so, unsigned chg, unsigned unk) {
  char rows[64][120]={{"PROC one"},{"PROC two"}};
  struct nuwa_pix p;
  assert(nuwa_pix_read(&state,&p));
  assert(p.crc==crc && p.nz==nz && p.uc==uc && p.so==so && p.chg==chg && p.unk==unk);
  assert(p.bk==1 && p.ticks==so);
  unsigned n=2+bp_pix_rows(rows+2,&p,78);
  unsigned kept=bp_banner_select(rows,n,n-1);
  assert(kept==n-1 && !strncmp(rows[2],"PIX ",4));
  printf("%s\n",label);
  for(unsigned i=2;i<kept;++i) {
    assert(strlen(rows[i])<=78 && bp_banner_priority(rows[i],2)==bp_banner_priority("PROC x",2));
    printf("%zu %s\n",strlen(rows[i]),rows[i]);
  }
  assert(bp_banner_select(rows,n,3)==3 && !strncmp(rows[2],"PIX ",4));
}

static void bgra(unsigned w, unsigned h, unsigned st, uint64_t ticks) {
  nuwa_pix_surface(&state,pixels,sizeof(pixels),w,h,st,0x42475241,0,ticks);
}

int main(void) {
  nuwa_pix_blank(&state);
  show("blank only",0,0,0,0,0,0);
  memset(pixels,0x55,sizeof(pixels)); // outside window and row padding must not contribute
  for(unsigned y=2;y<18;++y)
    for(unsigned x=2;x<18;++x) {
      unsigned char *p=pixels+y*96+x*4;
      p[0]=p[1]=p[2]=0; p[3]=0xff;
    }
  bgra(20,20,96,1);
  show("black",CRC_BLACK,0,1,1,0,0);
  pixels[0]=0xde; pixels[2*96+2*4+3]=0x01; // outside RGB center sample
  bgra(20,20,96,2);
  show("identical center signature",CRC_BLACK,0,1,2,0,0);
  for(unsigned y=2;y<18;++y)
    for(unsigned x=2;x<18;++x) {
      unsigned char *p=pixels+y*96+x*4;
      p[2]=0x12; p[1]=0x34; p[0]=0x56;
    }
  bgra(20,20,96,3);
  show("solid, signature changed",CRC_SOLID,256,1,3,1,0);
  for(unsigned y=2;y<18;++y)
    for(unsigned x=2;x<18;++x) {
      unsigned char *p=pixels+y*96+x*4;
      p[2]=(y-2)*16+x-2; p[0]=p[1]=0;
    }
  bgra(20,20,96,4);
  show("gradient, capped unique colors",CRC_GRAD,255,64,4,2,0);
  memset(pixels,0,sizeof(pixels)); pixels[0]=0x99;
  bgra(3,2,16,5);
  show("small/different geometry",CRC_SMALL,1,2,5,2,0);
  /* Nonlinear FourCC: no access even though the address is unusable. */
  nuwa_pix_surface(&state,(const uint8_t *)1,32,3,2,16,0x26424741,1,6);
  show("unsupported format",0,0,0,6,2,1);
  pixels[0]=0x77;
  bgra(3,2,16,7);
  show("unsupported breaks comparison",CRC_OTHER,1,2,7,2,1);
  memset(pixels,0,sizeof(pixels));
  pixels[1]=0x80; pixels[3]=0x3c; pixels[5]=0x38; // -0, 1, 0.5
  nuwa_pix_surface(&state,pixels,sizeof(pixels),1,1,8,0x52476841,0,8);
  show("half RGB",CRC_HALF,1,1,8,2,1);
  nuwa_pix_surface(&state,NULL,8,1,1,8,0x52476841,0,9);
  show("no sample in elevated context",0,0,0,9,2,1);
  char rows[2][120];
  struct nuwa_pix maximum={.bk=UINT32_MAX,.so=UINT32_MAX,.unk=UINT32_MAX,.chg=UINT32_MAX,
    .w=16384,.h=16384,.st=UINT64_MAX,.fmt=UINT32_MAX,.crc=UINT32_MAX,.nz=256,.uc=64,.valid=1};
  assert(bp_pix_rows(rows,&maximum,78)==2 && strstr(rows[1]," nz=256") && !strstr(rows[1]," uc="));
  for(unsigned i=0;i<2;++i) {
    assert(strlen(rows[i])<=78);
    printf("%zu %s\n",strlen(rows[i]),rows[i]);
  }
}
"""

expected = {
    "BLACK": bytes(768),
    "SOLID": bytes.fromhex("123456") * 256,
    "GRAD": b"".join(bytes((i, 0, 0)) for i in range(256)),
    "SMALL": bytes.fromhex("000099") + bytes(15),
    "OTHER": bytes.fromhex("000077") + bytes(15),
    "HALF": bytes.fromhex("0000003c0038"),
}
with tempfile.TemporaryDirectory() as tmp:
    c, exe = Path(tmp) / "fixture.c", Path(tmp) / "fixture"
    c.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", ROOT / "package",
                    *(f"-DCRC_{k}=0x{zlib.crc32(v):08x}U" for k, v in expected.items()),
                    str(c), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
