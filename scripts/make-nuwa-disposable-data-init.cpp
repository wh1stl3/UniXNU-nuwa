// SPDX-License-Identifier: BSD-2-Clause
// Host output only. Never opens a target. Prepare and commit are distinct
// artifacts; a boot image has no code path to apply either.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include "../package/nuwa-data-write/DisposableData.h"

int main(int argc, char **argv) {
  using namespace NuwaData;
  using namespace NuwaData::Disposable;
  if (argc != 2 || (strcmp(argv[1], "prepare") && strcmp(argv[1], "commit"))) {
    fprintf(stderr, "usage: %s prepare|commit (binary output to stdout)\n", argv[0]);
    return 2;
  }
  static Overlay::Workspace w{};
  if (!strcmp(argv[1], "commit")) {
    if (!Overlay::initialSuperblock(w.block, Seed, w)) return 1;
    return fwrite(w.block, 1, Block, stdout) == Block && !fflush(stdout) ? 0 : 1;
  }
  for (uint64_t i = 0; i < Overlay::Data0; ++i)
    if (fwrite(w.block, 1, Block, stdout) != Block) return 1;
  return fflush(stdout) ? 1 : 0;
}
