#include <cassert>
#include <cstring>
#include <cstdio>
#include <vector>
#include "NuwaVolumeSelection.h"

struct Ops {
  struct Node { unsigned refs=0; int auth=-1; Node *parent=nullptr; } mediaNode,driver;
  struct Iterator {} iterator;
  bool matchOk=true,validOk=true,typeOk=true,uuidOk=true,descriptionOk=true;
  unsigned cursor=0,releases=0,authCalls=0;
  std::vector<Node*> entries;
  Ops() { mediaNode.parent=&driver;driver.auth=1;entries={&mediaNode}; }
  Iterator *match(const char *id) { assert(!strcmp(id,"SystemOS")); return matchOk?&iterator:nullptr; }
  Node *next(Iterator *it) { assert(it==&iterator&&!releases);return cursor<entries.size()?entries[cursor++]:nullptr; }
  Node *media(Node *n) { return typeOk?n:nullptr; }
  bool uuid(Node *,const char *) { return uuidOk; }
  bool describe(Node *,NuwaVolumeSelection &s) { return descriptionOk && nuwaVolumeIdentity(14,3,"disk7s1",7,s); }
  Node *retain(Node *n) { ++n->refs;return n; }
  Node *copyParent(Node *n) { assert(n->refs); return n->parent?retain(n->parent):nullptr; }
  void releaseService(Node *n) { assert(n->refs);--n->refs; }
  int authenticate(Node *n,const char *) { assert(n->refs&&!releases);++authCalls;return n->auth; }
  bool valid(Iterator *) { assert(!releases);return validOk; }
  void releaseIterator(Iterator *) { assert(!releases);++releases; }
};

int main() {
  for(unsigned c=0;c<12;++c) {
    Ops o; std::vector<Ops::Node> chain(65);bool expected=c==0||c==10;
    if(c==1)o.matchOk=false;
    if(c==2)o.entries.clear();
    if(c==3)o.typeOk=false;
    if(c==4)o.uuidOk=false;
    if(c==5)o.descriptionOk=false;
    if(c==6)o.driver.auth=0;
    if(c==7)o.entries.push_back(&o.mediaNode);
    if(c==8)o.validOk=false;
    if(c==9){o.driver.auth=-1;o.driver.parent=&o.driver;}
    if(c>=10){
      for(unsigned i=0;i<64;++i)chain[i].parent=&chain[i+1];
      chain[c==10?63:64].auth=1;o.entries={&chain[0]};
    }
    NuwaVolumeSelection out={};out.device=123;std::strcpy(out.path,"stale");
    assert(nuwaSelectVolume(o,"SystemOS",out)==expected);
    assert(out.device==(expected?0x0e000003:UINT32_MAX));
    assert(!std::strcmp(out.path,expected?"/dev/disk7s1":""));
    assert(o.releases==(c!=1)&&o.authCalls<=64);
    assert(!o.mediaNode.refs&&!o.driver.refs);
    for(auto &n:chain)assert(!n.refs);
  }
  struct Case {uint64_t major,minor;const char *name;size_t length;bool ok;};
  const Case cases[]={{14,3,"disk7s1",7,true},{256,3,"disk7s1",7,false},
    {14,0x1000000,"disk7s1",7,false},{255,0xffffff,"disk",4,false},
    {0,0,"disk0",5,true},{14,3,nullptr,0,false},{14,3,"",0,false},
    {14,3,"../disk",7,false},{14,3,"disk/x",6,false},{14,3,"disk\0x",6,false}};
  for(auto &c:cases){NuwaVolumeSelection out;assert(nuwaVolumeIdentity(c.major,c.minor,c.name,c.length,out)==c.ok);if(!c.ok)assert(out.device==UINT32_MAX&&!out.path[0]);}
  char name[60];std::memset(name,'a',sizeof(name));NuwaVolumeSelection out;
  assert(nuwaVolumeIdentity(1,2,name,58,out)&&out.path[63]==0);
  assert(!nuwaVolumeIdentity(1,2,name,59,out)&&out.device==UINT32_MAX&&!out.path[0]);
  std::puts("PASS 12 selector/lifetime and 12 BSD identity cases");
}
