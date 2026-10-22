# R-011 A 同机原厂DXE Heap恢复对照

用户回复“同意”，承接已提交R-011 A的明确范围：仅恢复MemoryMapLib.c的DXE Heap地址/容量一行，保留R-010诊断、其他内存行/属性、PIL空AUTO和正确shim；独立构建及产物验收，满足D-021后一次临时v4对照并恢复Android完成1。无flash/erase/改槽或新XNU/FAT/DTB，board/feed/ADT窗口不变。

## 来源落地

wh1stl3/uefi-nuwa新分支codex/nuwa-factory-heap@1ccf760d667b9eec6dd3491c90cc04ebb7c58340，父2ab6827d。源码仅MemoryMapLib.c变化一行，严格apply检查和原/后LF哈希核对，原051c431a…、后b6cfda2e…。已发布完整相同Git blob/tree/commit对象；旧no-auto-abl和bringup分支未改，证据source-local/source-publish.json。只读旧资料库未写入。

数值取同机xbl_config抽取原表：BAB00000/0D1C0000=209.75MiB，末端C7CC0000；原69MiB的BAE00000/04500000恢复至原值。静态无重叠和同机Android DT覆盖/保留区检查沿用factory-heap-proposal.json；历史Android DT不证明本次候选x0或运行所有权，仍需实际对照。

## CI接线与实际产物门

factory-heap profile由R-010直接派生，只变固件提交及MemoryMapLib输入哈希；诊断补丁4a859ab6、其余34项输入和loader补丁保持。check-factory-heap-profile.py核对35项固定输入、完整派生差异和board/feed哈希，通过；CI仍在补丁前初始化固定Mu嵌套gitlink并严格保留两个CRLF目标。

新增实际SEC描述符读取：固定MemoryMapLib.h的CHAR8 Name[32]后为64位Address/Length，直接从解压后SEC TE找唯一DXE Heap记录，不以源码声明替代实际FD。对39829943950旧FD回归检查通过，读出BAE00000/72351744B=69MiB；新包必须实际读出BAB00000/219938816B=209.75MiB，同时保留DXE核心分配诊断/四EFI/SEC/HOB/DEPEX/PIL与shim检查。新FW尚未编译或试启动。
