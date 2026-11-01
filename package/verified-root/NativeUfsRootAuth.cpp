// SPDX-License-Identifier: BSD-2-Clause-Patent
// iOS16 adaptation of UniXNU's owner-root BSD/IOMedia/provider binding.
// Called only after the original APFS root authentication has returned an error.
#include <IOKit/IOService.h>
#include <IOKit/IOBSD.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wzero-as-null-pointer-constant"
#pragma clang diagnostic ignored "-Wshadow-field"
#include <IOKit/storage/IOMedia.h>
#pragma clang diagnostic pop
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSIterator.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSString.h>
#include <libkern/libkern.h>
#include <sys/mount.h>
#include <sys/vnode.h>
#include <sys/types.h>
#include "VerifiedBlockPolicy.h"
#include "NuwaRootBinding.h"

extern "C" int native_ufs_block_authenticates(IOService *, const char *, uint8_t *);
extern "C" unsigned nuwa_ufs_root_authorize(vnode_t, dev_t);

namespace {
struct RootMediaOps {
  OSIterator *match(uint32_t device) {
    OSDictionary *matching = IOService::serviceMatching("IOMedia");
    OSDictionary *properties = OSDictionary::withCapacity(2);
    OSNumber *mjr = OSNumber::withNumber(static_cast<unsigned>(major(device)),32);
    OSNumber *mnr = OSNumber::withNumber(static_cast<unsigned>(minor(device)),32);
    bool ready = matching && properties && mjr && mnr &&
        properties->setObject(kIOBSDMajorKey,mjr) && properties->setObject(kIOBSDMinorKey,mnr) &&
        matching->setObject("IOPropertyMatch",properties);
    OSIterator *iterator = ready ? IOService::getMatchingServices(matching) : nullptr;
    if (mnr) mnr->release();
    if (mjr) mjr->release();
    if (properties) properties->release();
    if (matching) matching->release();
    return iterator;
  }
  OSObject *next(OSIterator *it) { return it->getNextObject(); }
  IOService *media(OSObject *object) { return OSDynamicCast(IOMedia,object); }
  const char *uuid(IOService *media, const char *expected) {
    OSString *value = OSDynamicCast(OSString,media->getProperty("UUID"));
    return value && value->getLength()==36 && !strcmp(value->getCStringNoCopy(),expected)
        ? value->getCStringNoCopy() : nullptr;
  }
  int authenticate(IOService *service,const char *uuid) {
    return native_ufs_block_authenticates(service,uuid,nullptr);
  }
  IOService *provider(IOService *service) { return service->getProvider(); }
  bool valid(OSIterator *it) { return it->isValid(); }
  void release(OSIterator *it) { it->release(); }
};

struct RootMountOps {
  const char *expected;
  bool hold(vnode_t vp) { return vnode_getwithref(vp)==0; }
  mount_t mount(vnode_t vp) { return vnode_mount(vp); }
  bool readonly(mount_t mp) { return (vfs_flags(mp)&MNT_RDONLY)!=0; }
  vnode_t device(mount_t mp) { return vfs_devvp(mp); }
  uint32_t deviceId(vnode_t vp) { return static_cast<uint32_t>(vnode_specrdev(vp)); }
  void put(vnode_t vp) { vnode_put(vp); }
  bool authorized(uint32_t device) {
    RootMediaOps media;
    return nuwaCheckRootMedia(media,device,expected);
  }
};
}

extern "C" unsigned nuwa_ufs_root_authorize(vnode_t root,dev_t selected)
{
  // Local package qualification binds policy slot zero to chosen/root-matching.
  // These are compiled immutable headers, not a UUID supplied by the disk.
  if (verified_root_policy_count!=2 || !verified_root_policies[0].manifest ||
      verified_root_policies[0].manifestBytes<544) return 9;
  const uint8_t *uuid = verified_root_policies[0].manifest+40;
  const char hex[]="0123456789ABCDEF";
  char expected[37]; unsigned at=0;
  for (unsigned i=0;i<16;++i) {
    if (i==4 || i==6 || i==8 || i==10) expected[at++]='-';
    expected[at++]=hex[uuid[i]>>4]; expected[at++]=hex[uuid[i]&15];
  }
  expected[at]=0;
  RootMountOps ops={expected};
  return nuwaCheckMountedRoot(ops,root,static_cast<uint32_t>(selected));
}
