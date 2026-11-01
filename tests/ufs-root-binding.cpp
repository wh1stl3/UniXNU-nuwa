#include <cassert>
#include <cstdio>
#include <vector>
#include "NuwaRootBinding.h"

struct MountOps {
  struct Vnode {} root,dev;
  struct Mount {} mp;
  bool holdOk=true,mountOk=true,readOnly=true,deviceOk=true,authOk=true;
  unsigned rootHeld=0,deviceHeld=0,rootPuts=0,devicePuts=0,queries=0;
  uint32_t actual=0x0e000003;
  bool hold(Vnode *p) { assert(p==&root);if(holdOk)++rootHeld;return holdOk; }
  Mount *mount(Vnode *p) { assert(p==&root&&rootHeld==1);return mountOk?&mp:nullptr; }
  bool readonly(Mount *p) { assert(p==&mp);return readOnly; }
  Vnode *device(Mount *p) { assert(p==&mp&&rootHeld==1);if(deviceOk)++deviceHeld;return deviceOk?&dev:nullptr; }
  uint32_t deviceId(Vnode *p) { assert(p==&dev&&deviceHeld==1);return actual; }
  bool authorized(uint32_t id) { assert(id==actual&&rootHeld==1&&deviceHeld==1);++queries;return authOk; }
  void put(Vnode *p) {
    if(p==&root){assert(rootHeld==1);--rootHeld;++rootPuts;}
    else {assert(p==&dev&&deviceHeld==1);--deviceHeld;++devicePuts;}
  }
};

struct MediaOps {
  struct Node { bool isMedia=false,uuidOk=true;int auth=-1;Node *parent=nullptr; } mediaNode,block;
  struct Iterator {} iterator;
  bool matchOk=true,iteratorValid=true;
  unsigned cursor=0,releases=0,authCalls=0;
  std::vector<Node *> entries;
  MediaOps() {mediaNode.isMedia=true;mediaNode.parent=&block;block.auth=1;entries={&mediaNode};}
  Iterator *match(uint32_t id) {assert(id==0x0e000003);return matchOk?&iterator:nullptr;}
  Node *next(Iterator *p) {assert(p==&iterator&&!releases);return cursor<entries.size()?entries[cursor++]:nullptr;}
  Node *media(Node *p) {return p->isMedia?p:nullptr;}
  const char *uuid(Node *p,const char *expected) {assert(expected&&expected[0]=='R');return p->uuidOk?expected:nullptr;}
  int authenticate(Node *p,const char *id) {assert(id&&!releases);++authCalls;return p->auth;}
  Node *provider(Node *p) {return p->parent;}
  bool valid(Iterator *p) {assert(p==&iterator&&!releases);return iteratorValid;}
  void release(Iterator *p) {assert(p==&iterator&&!releases);++releases;}
};

int main() {
  for(unsigned c=0;c<9;++c) {
    MountOps o;auto root=&o.root;uint32_t selected=o.actual;unsigned expected=1;
    if(c==1){root=nullptr;expected=2;}
    if(c==2){selected=UINT32_MAX;expected=2;}
    if(c==3){o.holdOk=false;expected=3;}
    if(c==4){o.mountOk=false;expected=4;}
    if(c==5){o.readOnly=false;expected=5;}
    if(c==6){o.deviceOk=false;expected=6;}
    if(c==7){selected++;expected=7;}
    if(c==8){o.authOk=false;expected=8;}
    assert(nuwaCheckMountedRoot(o,root,selected)==expected);
    assert(!o.rootHeld&&!o.deviceHeld);
    assert(o.rootPuts==(c==0||c>=4));
    assert(o.devicePuts==(c==0||c>=7));
    assert(o.queries==(c==0||c==8));
  }
  for(unsigned c=0;c<10;++c) {
    MediaOps o;std::vector<MediaOps::Node> chain(65);bool expected=c==0||c==8;
    if(c==1)o.matchOk=false;
    if(c==2)o.entries.clear();
    if(c==3)o.mediaNode.uuidOk=false;
    if(c==4)o.block.auth=0;
    if(c==5)o.entries.push_back(&o.mediaNode);
    if(c==6)o.iteratorValid=false;
    if(c==7){o.block.auth=-1;o.block.parent=&o.block;}
    if(c>=8){
      chain[0].isMedia=true;
      for(unsigned i=0;i<64;++i)chain[i].parent=&chain[i+1];
      chain[c==8?63:64].auth=1;o.entries={&chain[0]};
    }
    assert(nuwaCheckRootMedia(o,0x0e000003,"Root")==expected);
    assert(o.releases==(c!=1));
    assert(o.authCalls<=64);
  }
  std::puts("PASS 9 mount identity/iocount cases and 10 unique-media/provider cases");
}
