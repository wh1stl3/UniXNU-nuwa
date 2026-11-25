#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Host fixture: actual retained open predicates, reason mapping and PU1 row."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_r35_display_diag import data_persist_row


def function(source, name):
    lines = source.splitlines()
    start, = (i for i, line in enumerate(lines) if line.startswith(name))
    lines = lines[start:]
    end = lines.index("}")
    return "\n".join(lines[:end + 1])


def main(base):
    provider = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    ufs = (provider / "NativeUfs.cpp").read_text()
    commands = (provider / "RootCommands.h").read_text()
    renderer = ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c"
    row = data_persist_row(renderer.read_bytes()).decode()
    overlay = base / "drivers/RamBlock/PersistOverlay.h"
    geometry = tomllib.loads((ROOT / "board.toml").read_text())["userdata"]
    store_geometry = ufs[ufs.index("struct StoreGeometry {"):ufs.index("// The diagnostic log")]
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        source = temp / "fixture.cpp"
        source.write_text(f"""
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "{ROOT / 'package/nuwa-ramblock/PersistOpenReason.h'}"
#include "{overlay}"
struct {{ bool ready; }} gHost;
static uint32_t requested_mode;
static unsigned storeMode() {{ return requested_mode; }}
static uint64_t reserveBlocks() {{ return 262144; }}
{store_geometry}
{function(commands, 'static bool hostStoreOpen (')}
{function(ufs, 'extern "C" int native_ufs_store_open (')}
volatile uint32_t native_data_persist_state = 4, native_data_persist_header = 9,
  native_data_persist_gpt = 0, native_data_persist_gpt_after = 0xff;
volatile uint64_t native_data_persist_first_lba = 0, native_data_persist_present = 0,
  native_data_persist_loaded = 0, native_data_persist_writes = 0,
  native_data_persist_syncs = 0, native_data_persist_errors = 0;
const char *volatile nuwa_data_persist_open_why = nullptr;
static char boot_progress_ext[8][48];
{function(row, 'static void ext_data_rows(')}

static const uint64_t first = {geometry['first_lba']}, last = {geometry['last_lba']};
static const uint64_t image_bytes = 8446279680ULL, seed_bytes = 8589934592ULL;
static uint64_t blocks, lba;
static void expect(const char *expected, uint64_t requested, int result=0) {{
  const char *why = nullptr;
  lba = 0;
  int ok = native_ufs_store_open(requested, &lba, &why);
  assert(ok == result);
  nuwa_data_persist_open_why = nuwa_persist_open_reason(ok, why);
  assert(!strcmp(nuwa_data_persist_open_why, expected));
  native_data_persist_first_lba = lba;
  ext_data_rows();
  char output[60];
  snprintf(output, sizeof output, "PU1 %.47s", boot_progress_ext[2]);
  assert(strlen(output) == 51);
  char token[24];
  snprintf(token, sizeof token, "why=%s ", expected);
  assert(strstr(output, token));
  puts(output);
}}

int main() {{
  ext_data_rows();
  assert(strstr(boot_progress_ext[2], "why=- "));
  const uint64_t pages = seed_bytes / persist::kBlock;
  blocks = persist::windowBlocks(pages);
  assert(pages == 2097152 && persist::bitmapBlocks(pages) == 64 && blocks == 2097217);
  assert(persist::bitmapBlocks(32768) == 1 && persist::bitmapBlocks(32769) == 2);
  assert(last - first + 1 == 58739643 && image_bytes / 4096 == 2062080);
  gStoreGeometry = {{true, first, last, image_bytes, 0, 0, 0, 0}};
  expect("off", blocks);
  requested_mode = 2;
  expect("nolayout", blocks);
  gHost.ready = true;
  expect("size", 0);
  expect("size", last - first + 2 - reserveBlocks());
  gStoreRegionBlocks = blocks;
  expect("open", blocks);
  gStoreRegionBlocks = 0;
  const uint64_t floor = first - 1 + reserveBlocks() + blocks + image_bytes / 4096 + 1024;
  gStoreGeometry.last = floor - 1;
  expect("overlap", blocks);
  gStoreGeometry.last = floor;
  expect("window", blocks);
  gStoreGeometry.last = last;
  expect("window", blocks);
  assert(lba == 0 && gStoreRegionBlocks == 0);
  requested_mode = 1;
  expect("ok", blocks, 1);
  assert(lba == 59491258 && lba + blocks == 61588475);
  assert(lba - first - image_bytes / 4096 == 54318202);
  native_data_persist_first_lba = UINT64_MAX;
  native_data_persist_gpt = 0xff;
  ext_data_rows();
  assert(strstr(boot_progress_ext[2], "l=ffffffffffffffff"));
  assert(!strcmp(nuwa_persist_open_reason(0, "unexpected"), "unknown"));
}}
""")
        binary = temp / "fixture"
        subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17",
                        str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
