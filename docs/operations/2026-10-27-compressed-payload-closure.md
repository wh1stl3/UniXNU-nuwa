# 压缩读取输入核验：38文件、188块

本轮继续离线主线，不上机。没有改原生内核、缓存/IRQ/锁/分配/认证策略、板值或IPSW身份，没有释放239门、设置_verified=true、提交或推送。PROBE40仍是下一合格未消费候选。

## 结果与实际意义

对固定恢复根中上轮已确定的38个launchd/dyld依赖文件，直接读取原始com.apple.decmpfs与com.apple.ResourceFork属性，用独立Python块表解析和宿主zlib展开：38个文件全部为type4，共188个块，展开10960640字节，逐文件SHA全部等于上轮APFS宿主读取结果。上轮另有2508个CodeDirectory代码页摘要匹配证据。

验证包含资源数据区/管理区边界、块数、索引范围与块间重叠、流完整结束、展开长度、完整文件摘要，以及188个首部/跨64KiB/文件末尾读取窗口。窗口是纯数据模型，不是实际XNU vnode/uio/vector执行；没有模拟成功的内核返回来冒充文件系统已通过。

| 输入 | 展开字节 | ResourceFork字节 | 块数 | 第0块绝对资源偏移 | 第0块声明长度 | 第0块zlib流长度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| /sbin/launchd | 541600 | 205547 | 9 | 336 | 23707 | 23311 |
| /usr/lib/dyld | 922912 | 325642 | 15 | 384 | 33021 | 32482 |

两者首4KiB/16KiB窗口均只涉及第0块。此结论用于限定输入侧所需块，不代表实际内核请求参数已经观测到，也不将40字节分配请求直接解释成文件块表大小。

目前没有发现需替换根镜像、修复必需依赖或修补压缩数据的离线输入故障。工程优先级保持在原生调用能否完成与观察器是否干扰上：分配器/调用方结果、实际读取回返、解码结果仍依靠PROBE40已有观察。未因宿主解压成功就认定XNU原生解压、锁或设备内存状态正常。

## 修正的离线判断

最初审计器要求zlib结束时整个ResourceFork块范围必须耗尽，实际launchd首块解出65536字节、eof=true，但留下396字节，因此首次审计失败。固定apfs-fuse/ApfsLib/Util.cpp:430起的DecompressZLib在Z_STREAM_END退出，并不要求avail_in为零；Decmpfs.cpp按块表声明范围调用它。

修改后仍要求完整流结束、没有因输出限额留下未消费流、展开长度准确及最终文件摘要一致；额外记录流长度和剩余范围长度/SHA。188块都有流结束后的剩余范围；本轮不推断这些字节的来源或用途，也不把宿主接受规则升级为已验证的原生AppleFSCompression规则。

新增“流结束后带包装剩余数据”与“截断流必须失败”回归，最终19项通过；损坏校验和、未知标记、越界块、表重叠和错误展开长度仍被拒绝。旧17项测试、第一次失败日志、失败时审计源码、第一次原始属性导出全部保留在r1位置，r2是独立新输出；不是放宽内核错误检查。

## 工具与证据

- scripts/apfs-resource-export/{CMakeLists.txt,main.cpp}：只读导出适配器，限制固定本地普通镜像，输出到新的out目录；不运行镜像代码。不经FUSE xattr接口传输大资源属性，直接调用同一只读APFS库。
- 上游来源D:/Code/PortingiOSLegacy/common/sources/apfs-fuse，GPL-2.0-or-later；只引用链接，未复制整仓、未写Legacy。DeviceLinux.cpp以O_RDONLY打开镜像。实际使用源码清单SHA绑定在audit.json。
- out/apfs-resource-export-build-r1：独立本地串行编译目录。日志有Clock skew detected警告，原日志保留；不是声称无警告构建。输出通过38个实际文件的独立解码摘要对照，未依赖增量构建时间戳来宣布有效。
- scripts/audit-compressed-payloads.py、test-compressed-payloads.py、qualify-compressed-payloads.py：有界解析、负例与资格绑定。
- reports/compressed-payloads/2026-10-27-r2/{audit,tests,qualification}.json：最终证据；audit-console.txt保留运行输出。
- out/compressed-payloads-20261027-r2/attributes：38组原始属性，只在本地保留；导出路径清单及stdout/stderr在同目录。原始媒体未动、未上传任何内容。
- reports/compressed-payloads/2026-10-27-r1/audit-console.txt与out/compressed-payloads-20261027-r1/audit-script-at-failure.py保留首次失败，资格报告绑定其摘要。

固定根镜像SHA256 d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a，导出前后重新核对一致。PROBE40镜像SHA256 bc895d41c3308884a82c653e89c99226a81911d036c01ccb328389fce625bc8b重新核对未变，无新包重编或消费。

## 下一步边界

能确定的文件存在、装载格式、代码页完整性、压缩块表与宿主展开一致性已补齐；不能由此确认原生分配、APFS调用、压缩回调、exec认证/映射、dyld EL0执行。没有找到可据此安全修改内核的确定缺陷，不猜改底层策略。

暂时不上机继续有效。恢复实测安排后仍须新鲜身份/槽位/三SHA及可用拍摄和实体键恢复条件；PROBE40尚未消费。239门、5项恢复根启动服务审阅边界、UFS未验收状态不变。详见上一轮2026-10-27-userland-input-closure.md。

复核需串行运行，新报告/工作目录不能复用已存在的r1/r2。实际命令记录：

```powershell
wsl -d Ubuntu-22.04 -- cmake -S /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/apfs-resource-export -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/apfs-resource-export-build-r1 -DCMAKE_BUILD_TYPE=Release
wsl -d Ubuntu-22.04 -- cmake --build /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/apfs-resource-export-build-r1 --target nuwa-resource-export --parallel 1
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-compressed-payloads.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/compressed-payloads/2026-10-27-r2/tests.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-compressed-payloads.py --work /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/compressed-payloads-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/compressed-payloads/2026-10-27-r2/audit.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/qualify-compressed-payloads.py --directory reports/compressed-payloads/2026-10-27-r2 --work out/compressed-payloads-20261027-r2
```
