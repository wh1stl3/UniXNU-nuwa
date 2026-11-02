// SPDX-License-Identifier: BSD-2-Clause-Patent
// Candidate iOS16 initial-boot adapter; not selected by the KMAIN16 build.
#include <IOKit/IOService.h>
#include <IOKit/IOBSD.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSIterator.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSString.h>
#include <libkern/c++/OSSymbol.h>
#include <libkern/libkern.h>
#include "VerifiedBlockPolicy.h"
#include "NuwaVolumeSelection.h"

extern "C" int native_ufs_block_authenticates(IOService *, const char *, uint8_t *);

namespace {
struct VolumeOps {
  OSIterator *match(const char *expected) {
    OSDictionary *matching=IOService::serviceMatching("IOMedia");
    OSDictionary *properties=OSDictionary::withCapacity(1);
    OSString *id=OSString::withCString(expected);
    bool ready=matching && properties && id && properties->setObject("UUID",id) &&
      matching->setObject("IOPropertyMatch",properties);
    OSIterator *it=ready?IOService::getMatchingServices(matching):nullptr;
    if(id) id->release();
    if(properties) properties->release();
    if(matching) matching->release();
    return it;
  }
  OSObject *next(OSIterator *it) { return it->getNextObject(); }
  IOService *media(OSObject *object) {
    if(!object) return nullptr;
    const OSSymbol *type=OSSymbol::withCStringNoCopy("IOMedia");
    if(!type) return nullptr;
    auto checked=OSMetaClass::checkMetaCastWithName(type,object);
    type->release(); return static_cast<IOService *>(checked);
  }
  bool uuid(IOService *service,const char *expected) {
    OSObject *property=service->copyProperty("UUID");
    OSString *value=OSDynamicCast(OSString,property);
    bool ok=value && value->getLength()==36 && !strcmp(value->getCStringNoCopy(),expected);
    if(property) property->release();
    return ok;
  }
  bool describe(IOService *service,NuwaVolumeSelection &out) {
    OSObject *a=service->copyProperty(kIOBSDMajorKey);
    OSObject *b=service->copyProperty(kIOBSDMinorKey);
    OSObject *c=service->copyProperty(kIOBSDNameKey);
    OSNumber *major=OSDynamicCast(OSNumber,a), *minor=OSDynamicCast(OSNumber,b);
    OSString *name=OSDynamicCast(OSString,c);
    bool ok=major && minor && name && nuwaVolumeIdentity(major->unsigned64BitValue(),
      minor->unsigned64BitValue(),name->getCStringNoCopy(),name->getLength(),out);
    if(c) c->release();
    if(b) b->release();
    if(a) a->release();
    return ok;
  }
  IOService *retain(IOService *service) { service->retain();return service; }
  IOService *copyParent(IOService *service) {
    IORegistryEntry *entry=service->copyParentEntry(gIOServicePlane);
    IOService *parent=OSDynamicCast(IOService,entry);
    if(entry && !parent) entry->release();
    return parent;
  }
  void releaseService(IOService *service) { service->release(); }
  int authenticate(IOService *service,const char *expected) {
    return native_ufs_block_authenticates(service,expected,nullptr);
  }
  bool valid(OSIterator *it) { return it->isValid(); }
  void releaseIterator(OSIterator *it) { it->release(); }
};
}

// Policy slot 1 is SystemOS in the qualified nuwa two-window package. It is a
// compiled trusted manifest, never a UUID/public key accepted from disk alone.
extern "C" int nuwa_ufs_select_systemos(NuwaVolumeSelection *out)
{
  if(!out) return 0;
  *out={};out->device=UINT32_MAX;
  if(verified_root_policy_count!=2 || !verified_root_policies[1].manifest ||
     verified_root_policies[1].manifestBytes<544) return 0;
  const uint8_t *uuid=verified_root_policies[1].manifest+40;
  const char hex[]="0123456789ABCDEF";
  char expected[37];unsigned at=0;
  for(unsigned i=0;i<16;++i) {
    if(i==4||i==6||i==8||i==10) expected[at++]='-';
    expected[at++]=hex[uuid[i]>>4];expected[at++]=hex[uuid[i]&15];
  }
  expected[at]=0;
  VolumeOps ops;
  return nuwaSelectVolume(ops,expected,*out)?1:0;
}
