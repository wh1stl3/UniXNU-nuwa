// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>
// These adapters carry real vnode iocounts and an owning matching iterator.
// A matching media reference stays inside that iterator's lifetime.
template<class Ops, class Vnode>
static unsigned nuwaCheckMountedRoot(Ops &ops, Vnode root, uint32_t selected)
{
  if (!root || selected == UINT32_MAX) return 2;
  if (!ops.hold(root)) return 3;
  unsigned result = 4;
  auto mount = ops.mount(root);
  if (mount) {
    result = 5;
    if (ops.readonly(mount)) {
      result = 6;
      auto device = ops.device(mount); // Returns one owned iocount, or null.
      if (device) {
        uint32_t actual = ops.deviceId(device);
        result = actual != selected ? 7 : ops.authorized(actual) ? 1 : 8;
        ops.put(device);
      }
    }
  }
  ops.put(root);
  return result;
}

template<class Ops>
static bool nuwaCheckRootMedia(Ops &ops, uint32_t device, const char *expected)
{
  auto iterator = ops.match(device);
  if (!iterator) return false;
  unsigned matches = 0;
  bool authenticated = false;
  while (auto object = ops.next(iterator)) {
    auto media = ops.media(object);
    if (!media) continue;
    if (++matches != 1) { authenticated = false; break; }
    const char *uuid = ops.uuid(media, expected);
    if (!uuid) continue;
    auto provider = media;
    for (unsigned depth = 0; provider && depth < 64; ++depth) {
      int result = ops.authenticate(provider, uuid);
      if (result >= 0) { authenticated = result == 1; break; }
      provider = ops.provider(provider);
    }
  }
  bool valid = ops.valid(iterator);
  ops.release(iterator);
  return valid && authenticated && matches == 1;
}
