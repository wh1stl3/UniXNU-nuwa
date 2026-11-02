// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>
#include <stddef.h>

struct NuwaVolumeSelection {
  uint32_t device;
  char path[64];
};

// BSD name is a single component, never a caller-controlled pathname.
static bool nuwaVolumeIdentity(uint64_t major, uint64_t minor,
                               const char *name, size_t length,
                               NuwaVolumeSelection &out)
{
  out = {}; out.device = UINT32_MAX;
  if (major > 255 || minor > 0xffffff || !name || !length || length > 58)
    return false;
  uint32_t device = (static_cast<uint32_t>(major)<<24) | static_cast<uint32_t>(minor);
  if (device == UINT32_MAX) return false;
  for (size_t i=0; i<length; ++i) {
    char c=name[i];
    if (!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9')))
      return false;
  }
  const char prefix[]="/dev/";
  for (unsigned i=0;i<5;++i) out.path[i]=prefix[i];
  for (size_t i=0;i<length;++i) out.path[5+i]=name[i];
  out.path[5+length]=0; out.device=device;
  return true;
}

// Initial boot only. Caller must revalidate mounted dev_t/UUID/provider after
// mount; these copied scalars are not a persistent authorization capability.
// Ops owns each retained provider and the iterator independently.
template<class Ops>
static bool nuwaSelectVolume(Ops &ops, const char *expected, NuwaVolumeSelection &out)
{
  out={}; out.device=UINT32_MAX;
  auto iterator=ops.match(expected);
  if (!iterator) return false;
  unsigned matches=0;
  bool authenticated=false;
  NuwaVolumeSelection candidate={}; candidate.device=UINT32_MAX;
  while (auto object=ops.next(iterator)) {
    // Fail closed on an unexpected object or duplicate UUID result.
    if (++matches!=1) { authenticated=false; break; }
    auto media=ops.media(object);
    if (!media || !ops.uuid(media,expected) || !ops.describe(media,candidate)) break;
    auto service=ops.retain(media);
    for (unsigned depth=0; service && depth<64; ++depth) {
      int result=ops.authenticate(service,expected);
      if (result>=0) {
        authenticated=result==1;
        ops.releaseService(service); service=nullptr; break;
      }
      auto parent=ops.copyParent(service);
      ops.releaseService(service); service=parent;
    }
    if (service) ops.releaseService(service);
  }
  bool valid=ops.valid(iterator);
  ops.releaseIterator(iterator);
  if (!valid || !authenticated || matches!=1) return false;
  out=candidate;
  return true;
}
