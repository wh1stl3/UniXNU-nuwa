# 桌面主线：离线输入与领先设备参考

用户明确“离线”仅指不使用实机，公开资料仍须在线参考。本轮按此执行，无设备访问、启动、刷写、提交或推送；PROBE41未消费，镜像SHA仍为`8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a`。既有239门和受审字段保持。

## 本轮已经完成的工作

新增4个本仓脚本：audit-desktop-root.py、test-desktop-root.py、audit-desktop-system.py、qualify-desktop-inputs.py。只读清点恢复根和桌面输入，单独解析iOS的`/System/Library/xpc/launchd.plist`，不把LaunchDaemons目录枚举当全部启动配置。6项测试覆盖缺失桌面、仅存在文件、shared-cache歧义、启动声明、主配置及链接越根。

重新只读检查恢复RAMDisk：缺少SpringBoard/backboardd、没有shared cache、没有iOS主launch配置，仅5份目录服务。结果在`reports/desktop-readiness/2026-10-27-r2`。r1是增加主配置解析前的初步结果，保留，不套给新脚本。

资料库已有同一d22ap/20H392的完整输入，未重新下载。OS、SystemOS、AppOS三份文件均流式计算SHA256/SHA384，匹配固定BuildManifest的组件摘要；只读检查前后摘要一致，挂载均已退出。新证据`reports/desktop-readiness/2026-10-27-system-r1/audit.json`，不改写10月20日旧报告。

| 输入 | 当前核对结果 |
| --- | --- |
| OS `087-86698-044.dmg`，4730814044字节 | 20H392；SpringBoard/backboardd及launchd/dyld存在；主launch配置532项 |
| SystemOS `087-86593-047.dmg`，2743074816字节 | 20H392；44个dyld缓存文件，记录大小、magic及UUID头字段 |
| AppOS `087-86715-047.dmg`，10485760字节 | 组件摘要与固定manifest相符，已单独清点 |

SpringBoard、backboardd、runningboardd的主配置程序均存在；前两者声明为mobile用户，含RunAtLoad、KeepAlive与Mach服务。这是原配置清点，不是批准启用所有532项服务。SpringBoard SHA256 `ea835980610a95591fb349bca077840fab7bdd663efaa11ef054d91bc2125475`，backboardd SHA256 `7aa6f8bf5ea2c3634fb8c8916a4e9c3c84508de78eccf57ca65c1ae4f676267c`。主程序解析和代码页摘要不代替CMS/AMFI或实际运行。

绑定资格及非部署输入计划：`reports/desktop-readiness/2026-10-27-qualification-r1/{qualification,desktop-input-plan}.json`。44个缓存仅完成头/大小清点，尚未完成subcache UUID引用闭包和库路径索引；不能把缺少独立framework文件直接判成缺库，也不能宣称依赖已经闭合。

## 优先参考的领先设备

| 来源与固定提交 | 维护者公开进度 | 本项目取用的方法与限制 |
| --- | --- | --- |
| [sheng](https://github.com/UniXNU/UniXNU-sheng/blob/08cde20edc3254ed6f7df8d0f5384fb887786e8f/porting.toml)，08cde20edc32 | SM8550，iPadOS17，桌面呈现和GPU设备记录 | 优先学同SoC组件分层与ABI先审计后绑定；不搬板值/固定地址/布局 |
| [ishtar详细日志](https://github.com/markakash/UniXNU-ishtar/blob/9ee8ee510ebb38e12a6f61a8c0ddba7d006057c7/PORTING.md)，9ee8ee510ebb | SM8550，小米13 Ultra；iOS18锁屏、按键和USB日志；触摸仍有未决项 | 近亲机型故障归因参考；README阶段表滞后，按详细日志判读；不是nuwa实测 |
| [ios-sweet](https://github.com/dipa-studio/ios-sweet/blob/45263bee51df4a0f55cdf9c649af886399488ddb/tools/mkiosroot.sh)，45263bee51df | 不同SoC，同代iOS16，桌面/输入记录 | 优先参考完整OS/cryptex组织与缓存路径；不执行上游根构建脚本或带入其板级、策略修改 |

已实际阅读sheng的`build-gop-legacy-display.py`：它依赖已核验的原生ABI报告，生成声明并绑定原始实现，硬编码布局仅适合相应输入。ishtar的2009补丁处理锁屏后显示关闭，不能当作nuwa读取卡点修复。方法评估及文件SHA、许可、版本和限制已记录`reports/desktop-readiness/2026-10-27-reference-r1/manifest.json`；没有导入上游实现。ishtar未找到根LICENSE，且其README注明基础源许可不明，不作为当前可直接复用代码。

公开通用依据：[Apple launchd启动说明](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)说明常驻与按需服务；iOS具体配置以本轮实际主配置为准。[UniXNU驱动目录](https://unixnu.com/drivers/repositories)及[GopFramebuffer固定README](https://github.com/UniXNU/GopFramebuffer/blob/33e941a878dcf01b98dbd9160d798bd56e7551ea/README.md)用于区分显示接口、扫描输出与刷新通知。没有将其它设备的声明作为nuwa通过证据。

## 当前判断与下一项实际工作

当前原生卡点仍以PROBE40/41的ResourceFork读取边界为准。更远的确定缺口是：现用恢复根不是桌面根，即使首次launchd进入用户态，也不会因此自行获得完整桌面。完整原材料现已重新核验，缺的是组合、依赖和运行接口资格。

下一项离线代码工作依序为：建立OS/cryptex的只读虚拟命名空间和冲突/链接解析；解析shared-cache主/子文件引用及路径索引，核对桌面依赖；拟定独立可写Data布局与启动服务范围；对iOS16原生IOSurface/MobileFramebuffer/HID建立接口契约并检查可复用实现。完整根不直接替换PROBE41，不提前扩大内存/身份/板值，也不凭静态清点解除239或认证检查。实机EL0、设备呈现和输入最终仍需运行证据。

## 已执行命令记录

以下输出已存在，只作追溯；再次执行须使用新的报告/挂载目录，不能覆盖现有证据。从`D:/Code/PortingiOS/nuwa/UniXNU-nuwa`运行：

```powershell
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-desktop-root.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-r2/tests.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-desktop-root.py --mount /var/tmp/nuwa-desktop-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-r2/audit.json --lock /mnt/d/Code/PortingiOSLegacy/config/donor-ios16.lock.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-desktop-system.py --work /var/tmp/nuwa-desktop-system-20261027-r1 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-system-r1/audit.json
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -X utf8 -B scripts/qualify-desktop-inputs.py --work reports/desktop-readiness/2026-10-27-qualification-r1
```

本轮差异`out/desktop-progress-r1.diff`包括4个新增脚本及STATUS/最新交接更新；新操作说明和参考清单另列于本文件及reference-r1/manifest.json。无本轮内核补丁或启动包修改。
