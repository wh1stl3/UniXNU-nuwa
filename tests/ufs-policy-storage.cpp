// Real installation-image policy reads and original C signature verification.
#include <cassert>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <vector>
#include "verified_root.h"
extern "C" int vr_host_open(const uint8_t*,size_t,const uint8_t*,uint64_t,vr_view*);
using IOReturn=uint32_t;
constexpr IOReturn kIOReturnSuccess=0,kIOReturnBadArgument=1,kIOReturnIOError=2,kIOReturnNotPrivileged=3;
#include "NuwaUfsPolicyRead.h"
#include "policy-fixture.h"
static std::vector<uint8_t> file(const char *p) {
 std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};
}
struct Reader {
 std::ifstream f;unsigned calls=0,fail=0;
 explicit Reader(const char *p):f(p,std::ios::binary){assert(f);}
 IOReturn read(uint64_t lba,uint32_t blocks,void *out){
  assert(lba>=first && lba+blocks<=last+1 && blocks && blocks<=32);
  if(++calls==fail)return kIOReturnIOError;
  f.seekg((lba-first)*4096);f.read(static_cast<char*>(out),blocks*4096);
  return f.gcount()==blocks*4096?kIOReturnSuccess:kIOReturnIOError;
 }
};
int main(int argc,char **argv){
 assert(argc==2);auto key=file(keyPath);
 for(unsigned i=0;i<2;++i){
  auto envelope=file(policyPath[i]);auto bytes=envelope.size();uint64_t rounded=(bytes+4095)&~uint64_t(4095);
  std::vector<uint8_t> destination(rounded,0xa5);Reader r(argv[1]);vr_view view{};
  assert(nuwaReadRootPolicy(r,first,last,imageBytes,imageBytes,dataEnd,offsets[i],bytes,envelope.data(),destination.data(),rounded)==0);
  assert(!memcmp(destination.data(),envelope.data(),bytes));assert(vr_host_open(destination.data(),bytes,key.data(),1,&view)==VR_OK);
  assert(r.calls==(rounded+131071)/131072);
  destination[544]^=1;assert(vr_host_open(destination.data(),bytes,key.data(),1,&view)==VR_HASH_TABLE);
  Reader fail(argv[1]);fail.fail=2;
  assert(nuwaReadRootPolicy(fail,first,last,imageBytes,imageBytes,dataEnd,offsets[i],bytes,envelope.data(),destination.data(),rounded)==kIOReturnIOError && fail.calls==2);
  auto wrong=envelope;wrong[10]^=1;Reader bad(argv[1]);
  assert(nuwaReadRootPolicy(bad,first,last,imageBytes,imageBytes,dataEnd,offsets[i],bytes,wrong.data(),destination.data(),rounded)==kIOReturnNotPrivileged);
  for(unsigned scenario=0;scenario<10;++scenario){
   Reader no(argv[1]);uint64_t begin=first,end=last,actual=imageBytes,offset=offsets[i],length=bytes,capacity=rounded,rootEnd=dataEnd;
   uint8_t *dest=destination.data();const uint8_t *head=envelope.data();
   switch(scenario){case 0:actual-=4096;break;case 1:offset=0;break;case 2:offset++;break;case 3:length=UINT64_MAX;break;case 4:capacity--;break;case 5:end=first;break;case 6:begin=last+1;break;case 7:dest=nullptr;break;case 8:head=nullptr;break;case 9:rootEnd=imageBytes+4096;break;}
   assert(nuwaReadRootPolicy(no,begin,end,actual,imageBytes,rootEnd,offset,length,head,dest,capacity)==kIOReturnBadArgument && no.calls==0);
  }
 }
 std::cout<<"PASS: both complete disk policies authenticate; changed hash tables fail; 20 invalid ranges perform no reads; read failures and signed-header mismatch fail closed\n";
}
