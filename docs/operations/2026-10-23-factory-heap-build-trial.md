# R-011 A 同机原厂DXE Heap恢复对照

用户回复“同意”，承接已提交R-011 A的明确范围：仅恢复MemoryMapLib.c的DXE Heap地址/容量一行，保留R-010诊断、其他内存行/属性、PIL空AUTO和正确shim；独立构建及产物验收，满足D-021后一次临时v4对照并恢复Android完成1。无flash/erase/改槽或新XNU/FAT/DTB，board/feed/ADT窗口不变。

## 来源落地

wh1stl3/uefi-nuwa新分支codex/nuwa-factory-heap@1ccf760d667b9eec6dd3491c90cc04ebb7c58340，父2ab6827d。源码仅MemoryMapLib.c变化一行，严格apply检查和原/后LF哈希核对，原051c431a…、后b6cfda2e…。已发布完整相同Git blob/tree/commit对象；旧no-auto-abl和bringup分支未改，证据source-local/source-publish.json。只读旧资料库未写入。

数值取同机xbl_config抽取原表：BAB00000/0D1C0000=209.75MiB，末端C7CC0000；原69MiB的BAE00000/04500000恢复至原值。静态无重叠和同机Android DT覆盖/保留区检查沿用factory-heap-proposal.json；历史Android DT不证明本次候选x0或运行所有权，仍需实际对照。

## CI接线与实际产物门

factory-heap profile由R-010直接派生，只变固件提交及MemoryMapLib输入哈希；诊断补丁4a859ab6、其余34项输入和loader补丁保持。check-factory-heap-profile.py核对35项固定输入、完整派生差异和board/feed哈希，通过；CI仍在补丁前初始化固定Mu嵌套gitlink并严格保留两个CRLF目标。

新增实际SEC描述符读取：固定MemoryMapLib.h的CHAR8 Name[32]后为64位Address/Length，直接从解压后SEC TE找唯一DXE Heap记录，不以源码声明替代实际FD。对39829943950旧FD回归检查通过，读出BAE00000/72351744B=69MiB；新包必须实际读出BAB00000/219938816B=209.75MiB，同时保留DXE核心分配诊断/四EFI/SEC/HOB/DEPEX/PIL与shim检查。新FW尚未编译或试启动。


## CI39835052901实际产物与试前检查

2199fa5固定固件1ccf760，本轮构建6m51s成功，666项inventory文件/大小/SHA与输入检查通过。实际FD3MiB SHAaca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6；实际DXE核心8fccb5c9包含原诊断标记，四EFI/SEC/HOB/DEPEX及原PIL空AUTO/相对shim全部静态检查通过。

actualSEC Heap唯一记录BAB00000/219938816B=209.75MiB；新旧实际SEC按固定72B结构核对41条，除Heap Address/Length16字节外表内其他字节完全一致，memory-table-comparison.json有新旧完整表SHA。该结果只证明实际二进制表，不证明运行所有权或dispatch。

v4临时包3153920B SHA8e85215011248b3e9462cace9a92133d4d58f33957ea2534fcb487a401e283c0，无XNU/FAT/新DTB/ramdisk，原header仅kernel_size变化。2026-10-23T01:07:31.572290+00:00重新读取唯一nuwa/kalama Android完成1、A槽和三个分区摘要，原Android恢复输入完整SHA再次校验，D-021前置记录preflight.json已就绪；当前尚未启动候选，须先通知用户录像。
