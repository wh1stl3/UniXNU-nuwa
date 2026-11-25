#pragma once
#include "../package/nuwa-data-write/Overlay.h"
#include <initializer_list>

namespace NuwaData {
struct FixtureGpt {
  GptIdentity id{61850624, 6, 61850618, 3110976, 61850618, {1}, {2}, {3}};
  uint8_t p[Block]{}, b[Block]{}, pe[Block]{}, be[Block]{};
  FixtureGpt() {
    auto *e = pe + 31 * 128;
    memcpy(e, id.type, 16);
    memcpy(e + 16, id.partition, 16);
    putLE(e + 32, id.userdataFirst, 8);
    putLE(e + 40, id.userdataLast, 8);
    for (unsigned i = 0; i < 8; ++i) e[56 + i * 2] = "userdata"[i];
    memcpy(be, pe, Block);
    for (auto *h : {&p, &b}) {
      const bool backup = h == &b;
      memcpy(*h, "EFI PART", 8);
      putLE(*h + 8, 0x10000, 4);
      putLE(*h + 12, 92, 4);
      putLE(*h + 24, backup ? id.capacity - 1 : 1, 8);
      putLE(*h + 32, backup ? 1 : id.capacity - 1, 8);
      putLE(*h + 40, id.firstUsable, 8);
      putLE(*h + 48, id.lastUsable, 8);
      memcpy(*h + 56, id.disk, 16);
      putLE(*h + 72, backup ? id.capacity - 2 : 2, 8);
      putLE(*h + 80, 32, 4);
      putLE(*h + 84, 128, 4);
    }
    repair();
  }
  void repair() {
    putLE(p + 88, crc(pe, Block), 4);
    putLE(b + 88, crc(be, Block), 4);
    putLE(p + 16, crc(p, 92, 16), 4);
    putLE(b + 16, crc(b, 92, 16), 4);
  }
  bool accept(unsigned lun = 0, unsigned block = Block) const {
    return gpt(lun, block, id, {1, 2, p, pe}, {id.capacity - 1, id.capacity - 2, b, be});
  }
  const uint8_t *at(uint64_t lba) const {
    if (lba == 1) return p;
    if (lba == 2) return pe;
    if (lba == id.capacity - 1) return b;
    return lba == id.capacity - 2 ? be : nullptr;
  }
};
}
