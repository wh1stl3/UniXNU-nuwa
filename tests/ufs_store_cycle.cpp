// Actual production commands; only HC, DMA, time and lock primitives are fixtures.
#include "RootCommandsBridge.cpp"
#include <array>
#include <algorithm>
static std::array<uint8_t,kDmaBytes> dma;
static std::array<uint8_t,64*4096> disk, stable;
static std::array<uint32_t,64> regs;
static uint64_t ticks;
static unsigned submits, syncs;
static bool poisonOnLock, residual, timeout;
static uint64_t io(unsigned op,uint64_t at,uint64_t value,void *bytes) {
  if(op==6 && poisonOnLock) { gHost.poisoned=true;gHost.ready=false; }
  if(op==0)return regs.at(at/4);
  if(op==4)return ticks;
  if(op==5)ticks+=value;
  if(op==2 || op==3) {
    assert(at>=gHost.phys && at-gHost.phys+value<=dma.size());
    auto p=dma.data()+at-gHost.phys;
    if(op==2)memcpy(p,bytes,value);else memcpy(bytes,p,value);
  }
  if(op!=1)return 0;
  if(at==0x20) { regs.at(at/4)&=~uint32_t(value);return 0; }
  regs.at(at/4)=value;
  if(at!=0x58)return 0;
  ++submits;
  if(timeout)return 0;
  auto cmd=dma.data()+kUcdOffset;auto rsp=cmd+kRspOffset;auto cdb=cmd+16;
  memset(rsp,0,512);rsp[0]=0x21;rsp[2]=cmd[2];rsp[3]=cmd[3];
  uint32_t lba=loadBe32(cdb+2), count=(unsigned(cdb[7])<<8)|cdb[8];
  if(cdb[0]==0x28 || cdb[0]==0x2a) {
    assert(lba<64 && count<=64-lba);
    if(cdb[0]==0x28)memcpy(dma.data()+kDataOffset,disk.data()+lba*4096,count*4096);
    else { memcpy(disk.data()+lba*4096,dma.data()+kDataOffset,count*4096);if(cdb[1]&8)stable=disk; }
  } else { assert(cdb[0]==0x35);stable=disk;++syncs; }
  if(residual)putBe32(rsp+12,512);
  *reinterpret_cast<uint32_t *>(dma.data()+8)=0;regs[0x58/4]=0;
  return 0;
}
static void reset() {
  dma.fill(0);regs.fill(0);ticks=0;submits=syncs=0;poisonOnLock=residual=timeout=false;
  ufs_test_reset(io,0x8cb5e9000);assert(ufs_test_store_open(8,40));
}
int main(int argc,char **) {
  std::array<uint8_t,32*4096> input,output;
  for(size_t i=0;i<input.size();++i)input[i]=uint8_t((i*17)^(i>>8));
  // This negative control must fail on the exact original production header.
  reset();regs[0x58/4]=1;auto before=std::array<uint8_t,kDmaBytes>{};memcpy(before.data(),memory,sizeof(memory));
  assert(ufs_test_write(0,8,1,input.data())!=0);
  if(memcmp(before.data(),memory,sizeof(memory))) { puts("FAIL: busy DMA overwritten before refusal");return 42; }
  if(argc>1)return 0;
  reset();poisonOnLock=true;memcpy(before.data(),memory,sizeof(memory));
  assert(ufs_test_write(0,8,1,input.data())!=0 && !memcmp(before.data(),memory,sizeof(memory)) && !submits);
  reset();regs[0x20/4]=0x20000;memcpy(before.data(),memory,sizeof(memory));
  assert(ufs_test_write(0,8,1,input.data())!=0 && !memcmp(before.data(),memory,sizeof(memory)) && !submits);
  reset();disk.fill(0x39);stable=disk;
  assert(ufs_test_write(0,8,32,input.data())==0 && stable!=disk);
  assert(ufs_test_sync()==0 && syncs==1 && stable==disk);
  disk=stable;output.fill(0);assert(ufs_test_read(0,8,32,output.data())==0 && output==input);
  assert(std::all_of(disk.begin(),disk.begin()+8*4096,[](uint8_t x){return x==0x39;}));
  assert(std::all_of(disk.begin()+48*4096,disk.end(),[](uint8_t x){return x==0x39;}));
  unsigned old=submits;
  assert(ufs_test_write(0,7,1,input.data())!=0 && ufs_test_write(0,47,2,input.data())!=0);
  assert(ufs_test_write(1,8,1,input.data())!=0 && submits==old);
  assert(hostWrite4k(0,47,1,input.data(),true)==0 && disk==stable);
  reset();residual=true;assert(ufs_test_write(0,8,1,input.data())!=0 && ufs_test_poisoned());
  reset();timeout=true;assert(ufs_test_write(0,8,1,input.data())!=0 && ufs_test_poisoned());
  memcpy(before.data(),memory,sizeof(memory));old=submits;
  assert(ufs_test_write(0,8,1,input.data())!=0 && ufs_test_sync()!=0 && submits==old);
  assert(!memcmp(before.data(),memory,sizeof(memory)));
  puts("PASS: real write/sync/read commands, FUA, bounds, busy/fatal ownership, waiting writer, residual, timeout quarantine");
}
