# S05/S06：OS原始磁盘解码与System卷身份

本轮依AGENTS及阶段规则继续离线准备root输入。不用设备、不提交/推送、不改现有内核/镜像/板值/239门。原DMG及历史报告保留；独立输出不代表目标存储、原生挂载或用户态通过。

## 新交付

`out/desktop-raw-os-20261027-r2/os.raw.img`，5635081728字节，SHA256：

`6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906`

该摘要是本轮实际解码文件的摘要，不能与原DMG摘要`80f426d5b8fca8552f95be427434f1911dbb4c2c6d28aad94f2426ddd0c92483`混用。新增`raw-window-contract.json`绑定OS原始摘要、既定SystemOS窗口及System卷身份；目标容量仍未知、不可部署。没有生成SHNGROOT镜像、Data文件系统、payload或boot包，不能把5.64 GB原始输入加入当前RestoreRamDisk链路冒充可启动完整根。

最终证据`reports/desktop-readiness/2026-10-27-raw-os-r1/{tests-r2,decode-r2,qualification}.json`。三个新脚本/模块：`udif_raw_decode.py`、`test-udif-raw-decode.py`、`prepare-desktop-raw-os.py`。

## 实际核验

- 新建独立宿主LZFSE构建目录，15项上游往返测试通过；本地14项检查涵盖六类UDIF块、大小/截断/后缀/资源界限、覆盖缺口、已有输出拒绝和Windows/POSIX证据路径。
- 解出全部3638个块，每块记录原存储字节摘要和解码摘要；逐块回读、全文件长度/摘要对照通过。raw、zero/ignore采用有界流式处理，压缩块输入/输出上限64 MiB。LZFSE输出缓冲为期望长度+1，以拒绝截断到缓冲区大小的假成功。
- LZFSE buffer API只报告输出长度，不单独证明输入消费长度；本轮绑定完整存储块和源DMG摘要，不宣称额外的输入消费或认证证明。zlib/bzip2夹具另检查EOF/后缀。实际OS块类型仍为3266 LZFSE、369 raw、3 ignore。
- 原DMG解码前后SHA256/SHA384和长度一致。raw只读挂载后，launchd、dyld、SpringBoard、backboardd及主launch配置五个文件与既有固定库存摘要一致；挂载退出。只是宿主文件系统视图，不是运行了这些程序。
- `apfsutil`以文件参数读取raw，确认Volume 0、Role=System、Name=`SydneyUpdate20H392.D22D221OS`、UUID=`DADD93F8-DBBF-4B17-A1DF-0F11E64172F7`。GPT分区唯一GUID为`2B716AD1-2C9C-4564-1A91-F3D1A449C1CA`，不能拿它替代System卷UUID。没有写入ADT或board.toml。

## 工具与来源

PATH未发现LZFSE命令，WSL无lzfse Python模块；后续发现Legacy工具目录有旧CLI，本轮没有复用它。新共享库/CLI由只读Apple LZFSE源码构建，固定提交`e634ca58b4821d9f3d560cdc6df5dec02ffc93fd`，BSD-3-Clause。源码位于`D:/Code/PortingiOSLegacy/common/sources/apfs-fuse/3rdparty/lzfse`，源文件清单/摘要在`lzfse-source-before.json`，构建后再次核对；构建文件仅落`out/host-lzfse-20261027-r1`，未安装系统包或向Legacy写入。

配置、构建和CTest原输出分别为configure-console.txt、build-console.txt、ctest-console.txt。构建保留了Clock skew警告，没有改时钟或源文件时间戳。构建目录原先不存在、目标编译完成；15项上游测试、14项本地检查及实际完整OS解码/回读提供运行证据，不隐去警告。

APFS读取器SHA256 `4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922`。卷信息工具`D:/Code/PortingiOSLegacy/common/tools/apfs-fuse-linux/bin/apfsutil` SHA256 `1ad246148909835c180cd06bfa47c58c2f199a1ffe40e6103bcca3163aa8eddb`；其本地来源apfs-fuse提交`66b86bd525e8cb90f9012543be89b1f092b75cf3`，ApfsUtil/ApfsUtil.cpp已审阅为读取文件并打印卷信息，GPL-2.0-or-later。记录工具/来源摘要，不把当前源码提交自动当作既有二进制的可复现构建证明。

格式依据：[UniXNU root/Data指南](https://unixnu.com/guide/userdata)及固定提交`0fc0fc1f9ddd0fbd4787738afef38667df5e0a95`的[UDIF实现](https://github.com/UniXNU/UniXNU/blob/0fc0fc1f9ddd0fbd4787738afef38667df5e0a95/scripts/unixnu/udif.py)，2026-10-27在线核对。解码器使用本机Apple API，未复制/执行上游根构建脚本。

同时复核领先设备[ios-sweet固定mkiosroot.sh](https://github.com/dipa-studio/ios-sweet/blob/45263bee51df4a0f55cdf9c649af886399488ddb/tools/mkiosroot.sh)：其策略是把OS/cryptex读出后复制到一个HFS+根，不能当作nuwa当前APFS窗口+独立Data种子的既成实现。本轮未采用该布局、参数或设备命令，也未取得可直接验收为nuwa/iOS16的Data种子。

## 命令与失败保留

脚本/编译/测试串行。以下输出已存在，仅追溯，续验换新路径：

```powershell
wsl -d Ubuntu-22.04 -- cmake -S /mnt/d/Code/PortingiOSLegacy/common/sources/apfs-fuse/3rdparty/lzfse -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/host-lzfse-20261027-r1 -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DLZFSE_DISABLE_TESTS=OFF
wsl -d Ubuntu-22.04 -- cmake --build /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/host-lzfse-20261027-r1 --parallel 1
wsl -d Ubuntu-22.04 -- ctest --test-dir /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/host-lzfse-20261027-r1 --output-on-failure --parallel 1
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-udif-raw-decode.py --library /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/host-lzfse-20261027-r1/liblzfse.so --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-raw-os-r1/tests-r2.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/prepare-desktop-raw-os.py --library /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/host-lzfse-20261027-r1/liblzfse.so --work /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/desktop-raw-os-20261027-r2 --mount /var/tmp/nuwa-desktop-raw-os-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-raw-os-r1/decode-r2.json
```

初版12项本地测试通过后，首次prepare在生成文件前因父报告使用Windows分隔符而报Parent binding differs；原decode-console.txt保留，没有生成raw。新增仅相对路径分隔符规范化和越根负对照，摘要要求未放宽，14项检查及r2准备通过，未覆盖首次日志。当前raw的91.6秒记录是宿主准备耗时，不是内核计时。

## 剩余依赖与当前主线边界

原始OS窗口摘要和来源System卷UUID现在有独立证据。仍需合格iOS16 Data文件系统种子（保护/ACL/卷身份/初始化）、完整OS/SystemOS/AppOS发布与挂载契约、目标容量/日志保留、nuwa UFS/RamBlock与OS ABI资格。现有198项tar只能提供初始材料，不能作为Data ramdisk。服务条件保留原配置，后续核对原生解释/运行时状态，不要求宿主猜选分支或改动原始plist。

PROBE40/41的ResourceFork原生读取边界、平台timer/IPI/DMA、exec认证/EL0和显示/HID仍未由这些宿主结果验收。本轮没有切换根或扩大RAMDisk/内存，PROBE41包与239门保持；最后Android状态仍是既有12:00:43+08证据，不是新查询。
