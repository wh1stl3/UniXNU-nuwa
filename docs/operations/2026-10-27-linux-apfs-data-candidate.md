# S05/S06：公开设备方法复核与Linux APFS Data候选

用户没有Data种子或macOS环境，要求查已推进设备的实现和公开资料。本轮找到并实际复现了Linux APFS构建方法，**不必先有Mac才能准备文件系统候选**。仍未将它当作iOS16运行时已验收的Data输入，不操作设备、不改内核/板值/239门、不提交。

## 公开实现比较

| 来源 | 实际方法/公开进度 | 对nuwa的取用 |
| --- | --- | --- |
| UniXNU-sheng，08cde20edc3254ed6f7df8d0f5384fb887786e8f | SM8550/iPadOS17桌面记录；Data作为独立种子，macOS工具可增长并接持久化 | 沿用root/Data分离和接口审查方法，不把外部种子当已有输入，不套大盘/持久化和板参数 |
| johnpanos/UniXNU-fajita，fb8c389bd9877d4db0ef6e09170b83752dec7259 | Linux mkapfs创建容器，Python写目录catalog，apfsck与独立读回，最后DBRDISK1打包；其README硬件仍到root等待，不能声称桌面已完成 | 本轮采用通用文件格式构建方法，目录元数据取nuwa自己固定20H392输入；实际本机结果见下 |
| IssacL04/UniXNU-Pagani_SM8750 | 维护者记录build39到UI、Data易失；工作流在macOS生成种子 | 证明易失Data可先于持久化，但其OS/SoC和ABI不同；未执行工作流、未导入板配置 |
| dipa-studio/ios-sweet，45263bee51df4a0f55cdf9c649af886399488ddb | 同代iOS16桌面记录；OS/cryptex复制进单个可写HFS+根 | 可作另一种根组织的参照；不是当前APFS窗口+独立Data的直接替换，本轮保持既定接口 |

固定源码/许可及下载字节摘要在`reports/desktop-readiness/2026-10-27-data-linux-r1/dependencies.json`。Fajita脚本BSD-2-Clause-Patent，apfsprogs为GPL-2.0。只将第三方工具/来源放到设备仓外的`D:/Code/PortingiOS/nuwa/Toolchain-nuwa/data-seed-20261027`；从固定归档提取，没有git clone/init、没有创建新仓库或第二写入者。没有运行示例设备命令。

## 已生成的真实文件系统候选

`out/linux-data-candidate-20261027-r1/build-a/data-linux.raw`与`data-linux.dbr`：

| 属性 | 本轮实际结果 |
| --- | --- |
| 格式 | 偏移0的APFS容器，单卷Data，区分大小写、未加密、role=none |
| 逻辑容量 | 1073741824字节（1 GiB）；仅宿主候选参数，没有修改board/bringup-plan内存值 |
| 目录 | 160个，由已固定OS-var来源包的目录UID/GID/mode生成，另有APFS内部根/私有目录 |
| 普通文件 | 0；没有套用外部OS的迁移成功、Setup或watchdog偏好；36个原来源文件的供应/初始化仍需处理 |
| Volume UUID | `3FA04580-6AA3-5949-A64F-B5F03A271995`，新候选卷身份，不是设备身份，也未写入kernel/ADT |
| raw SHA256 | `1a97ed81a7d9cc8866b4b7c3edc8c462797d92a9dce1560a0a2122eaf17b85d9` |
| packed | 106608字节、5个extent；SHA256 `1e00210d8fb17f13736efe8d6ca9f6b72eb424c223fa1bf03168b808bf2f7598` |

role=none来自被复现方法；外部设备记录APFS拒绝未加密的专用Data角色，不能把卷名Data与该角色位混同。该观察仍是外部设备/OS记录，本轮只验收生成属性，没有宣称iOS16原生接受。没有修改内核加密/认证策略。

## 本机核验链

1. 安全归档/来源规格8项测试通过，拒绝越根、绝对路径、源链接、特殊节点和已有输出；数值权限直接来自固定OS目录证据。
2. apfsprogs固定归档提交`1bd1c1c2140d13d1b6d2e03379316572bee70aa3`，SHA256 `f25c2ad7a4ebf5b14cc60bdeb14cf26283152784b0fbffa2c3f5a89b72060c6a`；只编译mkapfs/apfsck、不安装。其版本输出`unknown git commit id`原样保留，因为使用无.git的归档，不能伪造Git版本字符串；实际来源以归档和二进制摘要绑定。
3. Fajita固定脚本SHA256 `977534d326005f34d3883e35d368dd3f1945b3fcee82b171212271f77332c891`。以明确nuwa规格、固定UUID/时间、新目录分别构建a/b；两份raw和packed摘要一致。apfsck -cuw、构建器catalog/omap/checksum读回及packed到raw逐字节对照通过。
4. 现有独立apfs-fuse只读挂载和apfsutil卷检查通过，160个实际目录的UID/GID/mode与规格逐项一致，退出挂载后raw摘要不变。未使用构建器删除读回日志的可选步骤，自己的命令/日志全部保留。
5. 直接编译只读旧快照的SparseDisk.h/Test/sparse.cpp，4000次差分I/O与错误分支通过。新C++适配器用该真实parser/importer导入本轮dbr、用OpenSSL计算完整逻辑磁盘摘要，与raw相同；不是另写Python模型替代驱动核心。

该快照导入后非零页106496字节（26页），页指针表2097152字节，输入106608字节仍属loader所有直至重启；三项基础驻留模型合计2310256字节，**不含对象/分配器/页表/后续写入增长，不是已验收的设备内存预算**。原封不动的本地packer通过一个接口别名shim供新构建器使用（PLAIN_HASH_LIMIT=旧MAX_LOGICAL=2 GiB）；没有改旧库或扩大其接受范围，Python均带-B以免向Legacy写pyc。

最终报告：`{tests,tools,candidate,readback,provider,qualification}.json`位于`reports/desktop-readiness/2026-10-27-data-linux-r1/`。当前候选仅通过宿主格式、基本目录语义和打包回读；文件保护类、ACL、运行时数据库/迁移、预装应用与iOS16原生挂载仍未验收。

## 新发现的集成缺口

- 当前PROBE41实际内核有64693项可见符号，未找到NativeRamBlock/native_ram_block/native_ufs_store相关名称；身份字符串也单独记录。它没有已验收的Data provider链接/初始化证据。不能因源码或配置列出模块就认为已装入该内核。
- 当前ADT只有一个16字节全零RAMDisk交接占位，包实际带RestoreRamDisk、`-v rd=md0`，没有新增Data候选。该RAMDisk服务于恢复根；不能同时添加PackedRAMDisk并把二者当成独立Data路径，本地参考驱动明确拒绝两者并存。
- 本地旧SparseDisk.h摘要`8b1202eda8ae920c6b505d7b97c44691e4cd2b3c7756b20bbd86ade40b8738fd`只接受最多2 GiB；配置声明d4d22d9819b0162eda49f6402235dddc2279410d的公开文件摘要为`5ab6516488b7daaef88e788fffef17195e7d2f74746da2206c6d9ed3a63c8c74`，支持更大格式并需相应SeedDisk/DirectDisk与存储后端。NativeRamBlock.cpp也不同。两套来源分开标注，不能把旧快照测试转授给配置新pin；大于2 GiB的公开实现需要已打开的持久存储，nuwa未验收，不采用大盘示例。
- 读取旧库Git元数据被`dubious ownership`保护拒绝，已停止该Git操作，不改safe.directory，不手读.git绕过。这里只验证允许读取的文件字节，不宣称旧库HEAD已确认。该Git访问如需恢复，须正规所有权/访问复核；现有文件和修改不重置。此拒绝原始证据在本轮工具输出，文档为转述，不伪造原始控制台文件。

下一依赖现在是**固定正确Data源码 → iOS16 IOBlockStorageDevice/provider ABI → archive/link/init → 完整root与Data各自发布/匹配 → 真实挂载**；不再以缺Mac作为格式候选的阻塞。任何接入仍需实际loader内存所有权/预算和原生错误路径，不能把候选直接塞入PROBE41。ResourceFork读取、exec/EL0、平台和显示/HID前沿不因本轮宿主结果而变化。239门保持。

## 复现命令（仅追溯）

以下目录/输出已存在；脚本/编译/测试全串行。续验应选新路径，不覆盖证据：

```powershell
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-linux-data-inputs.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-data-linux-r1/tests.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/prepare-linux-data-tools.py --work /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/linux-data-tools-20261027-r1 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-data-linux-r1/tools.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/build-linux-data-candidate.py --work /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/linux-data-candidate-20261027-r1 --mount /var/tmp/nuwa-linux-data-20261027-r1 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-data-linux-r1/candidate.json
wsl -d Ubuntu-22.04 -- /usr/bin/clang++ -std=c++17 -O2 -Wall -Wextra -Werror -I /mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeRamBlock /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/data-seed-readback/main.cpp -lcrypto -o /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/linux-data-tools-20261027-r1/data-seed-readback
wsl -d Ubuntu-22.04 -- /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/linux-data-tools-20261027-r1/data-seed-readback /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/linux-data-candidate-20261027-r1/build-a/data-linux.dbr
```

## 公开原始资料

- [Fajita Linux生成器](https://github.com/johnpanos/UniXNU-fajita/blob/fb8c389bd9877d4db0ef6e09170b83752dec7259/scripts/make-data-seed-linux.py)、[Data规格](https://github.com/johnpanos/UniXNU-fajita/blob/fb8c389bd9877d4db0ef6e09170b83752dec7259/data-seed.json)、[用户态缺口记录](https://github.com/johnpanos/UniXNU-fajita/blob/fb8c389bd9877d4db0ef6e09170b83752dec7259/NOTES-userland.md)。规格含不同OS偏好，未直接用作nuwa规格；本轮用自己的160目录元数据。
- [apfsprogs固定源](https://github.com/linux-apfs/apfsprogs/tree/1bd1c1c2140d13d1b6d2e03379316572bee70aa3)、[RamBlock配置pin的公开实现](https://github.com/UniXNU/RamBlock/tree/d4d22d9819b0162eda49f6402235dddc2279410d)、[官网Data流程](https://unixnu.com/guide/userdata)。
- [Sheng](https://github.com/UniXNU/UniXNU-sheng/blob/08cde20edc3254ed6f7df8d0f5384fb887786e8f/README.md)、[Pagani维护者记录](https://github.com/IssacL04/UniXNU-Pagani_SM8750)、[sweet固定根脚本](https://github.com/dipa-studio/ios-sweet/blob/45263bee51df4a0f55cdf9c649af886399488ddb/tools/mkiosroot.sh)。外部设备进度只作方法线索；Pagani为当日在线公开快照，未复用其实现。

GitHub连接器请求本轮传输失败，改用公开HTTPS固定来源；RamBlock的ls-remote网络长时间不返回已中断，没有将网络问题当成pin确认或绕过本地Git保护。
