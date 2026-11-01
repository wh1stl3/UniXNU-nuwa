// Execute the extracted production doAsyncReadWrite method and RootWindowRead.
// IOKit/transport/crypto are modeled; real crypto is tested by the root builder.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
using IOReturn=uint32_t; using UInt64=uint64_t;
constexpr IOReturn kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnIOError=2,
 kIOReturnNotPrivileged=3,kIOReturnNotWritable=4,kIOReturnNotReady=5;
constexpr unsigned kIODirectionIn=1,kDataMax=131072,VR_OK=0;
struct IOLock { bool held=false; };
void IOLockLock(IOLock *p) { assert(!p->held);p->held=true; }
void IOLockUnlock(IOLock *p) { assert(p->held);p->held=false; }
struct IOMemoryDescriptor {
 std::vector<uint8_t> data; unsigned direction=1; uint64_t shortCopy=UINT64_MAX;
 explicit IOMemoryDescriptor(size_t n):data(n,0xa5){}
 uint64_t getLength() {return data.size();} unsigned getDirection(){return direction;}
 uint64_t writeBytes(uint64_t at,const void *p,uint64_t n) {
  n=n<shortCopy?n:shortCopy;assert(at+n<=data.size());memcpy(data.data()+at,p,n);return n;
 }
};
struct IOStorageAttributes {};
struct IOStorageCompletion {void *target,*parameter;void (*action)(void*,void*,IOReturn,uint64_t);};
struct vr_view {}; static int vr_xnu_crypto;
static unsigned reads,failRead,failVerify=UINT32_MAX,progressCalls,timerCalls;
static uint64_t timerTicks(){return ++timerCalls;}
static void boot_progress_poll(){++progressCalls;}
static std::vector<uint8_t> disk(64*4096,0x37);
IOReturn hostRead4k(unsigned lu,uint64_t lba,uint32_t n,void *p) {
 assert(lu==0 && lba*4096+n*4096<=disk.size());
 if(++reads==failRead)return kIOReturnIOError;
 memcpy(p,disk.data()+lba*4096,n*4096);return 0;
}
int vr_verify_block(const vr_view*,uint64_t i,const void *p,size_t n,const int*) {
 return i==failVerify || memcmp(p,disk.data()+i*4096,n) ? 5:0;
}
struct {const char *stage;uint32_t verify,result;} gRootDiagnostic;
volatile uint64_t native_ufs_read_ticks,native_ufs_verify_ticks,native_ufs_verified_blocks,
 native_ufs_block_reads,native_ufs_block_failures;
volatile uint32_t native_ufs_integrity_failures;
static void rootDiagnosticFailure(const char*){throw std::runtime_error("diagnostic panic before completion");}
#include "RootWindowRead.h"
struct NativeUfsBlock {
 uint64_t bytes=disk.size(),absolute=0;bool online=true;
 IOLock *windowLock=new IOLock;uint8_t *bounce=new uint8_t[kDataMax];vr_view verified;
 ~NativeUfsBlock(){assert(!windowLock->held);delete windowLock;delete[] bounce;}
 IOReturn doAsyncReadWrite(IOMemoryDescriptor*,UInt64,UInt64,IOStorageAttributes*,IOStorageCompletion*);
};
#include "production-method.inc"
struct Context {
 NativeUfsBlock *device;IOMemoryDescriptor *buffer;IOStorageCompletion *completion;
 unsigned calls=0;IOReturn status=99;uint64_t done=UINT64_MAX;bool release=false,reenter=false;
};
static void complete(void *target,void*,IOReturn status,uint64_t done) {
 auto &c=*static_cast<Context*>(target);assert(!c.device->windowLock->held);
 ++c.calls;c.status=status;c.done=done;
 if(c.reenter){
  c.reenter=false;IOMemoryDescriptor nested(512);Context nc{c.device,&nested,nullptr};
  IOStorageCompletion co{&nc,nullptr,complete};nc.completion=&co;
  assert(c.device->doAsyncReadWrite(&nested,0,1,nullptr,&co)==0 && nc.calls==1 && nc.done==512);
 }
 if(c.release){delete c.device;delete c.buffer;delete c.completion;}
}
int main(int argc,char**) {
 if(argc>1){
  NativeUfsBlock d;IOMemoryDescriptor b(4096);Context c{&d,&b,nullptr};IOStorageCompletion co{&c,nullptr,complete};
  failRead=1;try{d.doAsyncReadWrite(&b,0,8,nullptr,&co);}catch(const std::runtime_error&){assert(c.calls==0);return 42;}
  return 1;
 }
 for(unsigned scenario=0;scenario<9;++scenario){
  reads=failRead=progressCalls=timerCalls=0;failVerify=UINT32_MAX;
  NativeUfsBlock *d=new NativeUfsBlock;auto *b=new IOMemoryDescriptor(257*512);
  Context c{d,b,nullptr};auto *co=new IOStorageCompletion{&c,nullptr,complete};c.completion=co;
  if(scenario==1)failRead=1;
  if(scenario==2)failRead=2;
  if(scenario==3)failVerify=0;
  if(scenario==4)failVerify=32;
  if(scenario==5)b->shortCopy=17;
  if(scenario==6)c.release=true;
  if(scenario==7)c.reenter=true;
  if(scenario==8){d->absolute=4096;d->bytes-=4096;}
  assert(d->doAsyncReadWrite(b,0,257,nullptr,co)==0 && c.calls==1);
  const IOReturn status[]={0,2,2,3,3,2,0,0,0};
  const uint64_t done[]={257*512,0,131072,0,131072,17,257*512,257*512,257*512};
  assert(c.status==status[scenario] && c.done==done[scenario]);
  assert(!timerCalls && !progressCalls);
  if(!c.release){if(c.done<b->data.size())assert(b->data[c.done]==0xa5);delete d;delete b;delete co;}
 }
 for(unsigned scenario=0;scenario<5;++scenario){
  NativeUfsBlock d;IOMemoryDescriptor b(4096);Context c{&d,&b,nullptr};IOStorageCompletion co{&c,nullptr,complete};
  if(scenario==1)b.direction=2;if(scenario==2)d.online=false;if(scenario==3)co.action=nullptr;
  auto ret=d.doAsyncReadWrite(&b,scenario==4?UINT64_MAX:0,scenario==0?0:8,nullptr,&co);
  assert(ret!=0 && c.calls==0);
 }
 puts("PASS: 9 completed requests, 5 synchronous rejections; error propagation, partial reads, unlocked reentry and callback destruction");
}
