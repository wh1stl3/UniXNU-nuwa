# 进入用户态前的固定输入与启动服务核验

本轮仅离线操作，遵守用户“暂时不上机”。未访问设备、未改内核/恢复镜像/PROBE40包、未释放239门、未改受审内存或IPSW身份、未置任何_verified=true、未提交或推送。

## 已确定的输入条件

固定RAMDisk SHA256 `d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a`，使用固定apfs-fuse `4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922`只读挂载到独立/var/tmp目录。审计后已卸载，前后RAMDisk摘要一致。旧报告保留，不重新封装成历史验收。

新增scripts/audit-userland-closure.py递归处理launchd/dyld依赖，新增test-userland-closure.py验证11项正常/损坏输入边界；qualify-userland-closure.py绑定源码、测试、固定XNU头文件和现有包，形成reports/userland-closure/2026-10-27-r1/{audit,tests,qualification}.json。

- 38个实际Mach-O文件，355条依赖声明，全部CPU_TYPE_ARM64/subtype ALL；解析到的VM段无重叠，文件范围和入口均在界内，段地址、容量、文件偏移符合16KiB对齐。
- 38个文件的CodeDirectory共2508个代码页摘要匹配宿主解压出的实际字节。未验证CMS信任链、特殊槽/entitlements或内核AMFI接受；不能把摘要匹配说成认证通过。
- 所有声明为必需的依赖都有独立文件。唯一不存在的`/usr/local/lib/libobjc-env.dylib`来自libobjc.A.dylib的LC_LOAD_WEAK_DYLIB，固定loader.h明确允许此类库缺失，不能把它当当前必需库缺失的阻塞。尚未执行动态符号绑定或初始化器；弱声明也不证明应用所有使用路径都容忍缺失。
- launchd仍为541600字节、SHA12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c，dyld为922912字节、SHA5806834564fe6462ae981d0915d612b1eb2f6f168822b5d278bee56254933757，与历史记录一致。此次用新路径重新读出验证，未改写旧证据。

代码页完整性为“固定压缩内容可被宿主工具还原为自洽代码”的证据，不替代XNU原生APFS/type4解压路径。当前实机文件头读取未见完整返回，仍是先于用户入口的实际卡点。

## 首次用户态的正确目标

launchd通过LC_LOAD_DYLINKER请求`/usr/lib/dyld`；launchd的LC_MAIN偏移为0x169b4。dyld为MH_DYLINKER，LC_UNIXTHREAD/ARM_THREAD_STATE64指定未滑移PC 0x151b0，均落在文件支撑的可执行段内。

固定xnu-ios16-full/bsd/kern/mach_loader.c:2669明确LC_MAIN入口由dyld使用；同文件3124在load_dylinker成功后用myresult->entry_point替换最终用户入口，3119附近同步替换线程状态。因此应区分“dyld首次用户指令”和“launchd自身入口”：前者是本输入组合的首个用户态执行目标。实际PC还需加实际装载滑移，目前没有实测该滑移或用户态PC，不能将0x151b0当设备绝对地址。源文件与ARM64结构/代码签名/Mach-O头文件SHA已绑定到qualification.json。

## 启动服务完整清单

本次枚举/System/Library/LaunchDaemons和/Library/LaunchDaemons，共5份plist；对应程序均存在。表中是配置声明，不是服务已运行。

| 服务 | 配置触发条件 | 尚需审阅的范围 |
| --- | --- | --- |
| restored_external | RunAtLoad=true；输出到/dev/console | 恢复流程、设备内容更改路径和实际调用条件 |
| PurpleReverseProxy.ramdisk | 3个socket配置，包含IPv4v6/回环声明 | socket激活、依赖及外围设备要求 |
| diskimagesiod | 2个MachServices；指定_diskimagesiod用户 | 磁盘镜像服务和身份/设备依赖 |
| diskimagesiod.ram | 1个MachServices，--ram参数 | RAM模式的具体副作用和依赖 |
| syslogd | Disabled=true且KeepAlive=true | 实际禁用覆盖状态、日志设施依赖 |

仅移除restored_external的RunAtLoad不能等同于完成整个启动环境审阅；socket或Mach服务仍有按需触发入口。这里不声称这些服务会自动破坏设备，也不虚构已审过它们的二进制行为。239门继续保持。

未来释放方案可在完整依赖审阅后选择：保留原恢复根并审清全部自动/按需服务，或单独制作受限启动根并明确服务选择与输入身份。前者保持当前输入但需更多服务副作用证据，后者需要新根输入的独立验证和相应审阅。本轮不实现两种方案、不请求一般授权、不修改已合格PROBE40。

## 尚不能离线宣布解决的部分

1. 当前原生读取/第二次分配/解压链的真实完成结果；PROBE40已保留这些观察点，等待用户恢复实测。
2. 原生exec的映射、签名认证、动态链接及初始化器实际执行。上述文件格式与摘要检查不替代它们。
3. 239受控释放条件及restore服务内容审阅；未作运行许可变更。
4. 首线程确实进入EL0并执行dyld，再到launchd；没有运行时证据。

UFS仍未验收，当前根是RAMDisk/md0，进入最早用户指令不能证明完整iOS服务或驱动就绪。

PROBE40镜像204484608字节，SHA256 `bc895d41c3308884a82c653e89c99226a81911d036c01ccb328389fce625bc8b`，内核SHA256 `4237d18ca1c4d1ac95d464c8828330ef8f833a53a6dd0942fd5c26c1a24099b5`，本轮再次核对未变，无需重编或重跑已合格的37项内核核验。新增工具和文档差异另存out/userland-closure-r1.diff。

## 可复核命令

工作目录为D:/Code/PortingiOS/nuwa/UniXNU-nuwa。审计/测试/资格命令必须串行，后续重跑选新的报告目录和不存在的/var/tmp挂载点，避免覆盖本轮证据。

```powershell
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-userland-closure.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/userland-closure/2026-10-27-r1/audit.json --mount /var/tmp/nuwa-userland-closure-20261027-r1
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-userland-closure.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/userland-closure/2026-10-27-r1/tests.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/qualify-userland-closure.py --directory reports/userland-closure/2026-10-27-r1
```

这些为已经执行的命令记录，原路径已存在，不能直接重跑覆盖。11项测试包括命令越界、入口越界、段文件越界、未消费命令字节、损坏代码页、摘要表越界、镜像内绝对/相对链接、越根与链接循环。审计不运行镜像中的任何程序。
