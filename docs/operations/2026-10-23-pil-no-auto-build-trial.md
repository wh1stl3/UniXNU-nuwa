# R-009 A：保留PIL并取消自动ABL链

用户在具体R-009 A请求后回复“批准”。范围涵盖源码、独立EFI/FD/shim编译和产物检查、受限v4临时对照及Android完成1收尾；不扩展board/内存、flash/erase/槽位或_verified。

## 构建前静态门

`scripts/audit-pil-auto.py`从R-007实际FD在RAM解包PILDxe，PE SHA89e030af07847bdc596f0c213bdce0ac430be66e572db55b434d7ec66ad9afcb，恰与先前安装UEFI的该驱动一致。保存原指令字节/地址与字符串交叉引用至reports/pil-no-auto/parser-disassembly.json，不输出PE/固件文件。下述地址均为PE首选地址，不是实机PC：

- 初始化列表函数0x41b4按AUTO选择0x4398回调；枚举完成后AUTO走0x4364的x19=0并在0x437c返回成功。不存在“列表必须至少一项”的AUTO后置检查；特殊检查是另一个16进制长度0x16的节名，不能套到AUTO。
- 通用配置解析初始化0x11378将注释字符设置为`#`；0x11764按节名枚举回调，枚举耗尽在0x117dc返回0。完整迭代/行处理路径保留0x11400–0x11844。
- 自动项计数首选地址0x18718在PE数据/零填充映像初始为0；AUTO回调只有实际条目才会累加（0x4414–0x4424）。入口0x1600的CBZ在计数0时跳0x1650安装协议，绕过加载循环及0x163c panic消息/调用。

结论为**静态检查通过**，前提是配置RAW可读取、解析成功且普通初始化内存状态正常；未模拟执行，更未把它写成实机验收。此门足以继续获批构建，最终行为以新FD试启动取证为准。

复现命令：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-pil-auto.py --range 0x1588:0x1708 --range 0x41b4:0x446c --range 0x11298:0x113d8 --range 0x11400:0x11844
```

## 已固定源码与CI接线

独立固件分支`codex/nuwa-no-auto-abl@2ab6827d77dfe15010534b52e1abb76a26464a7d`，父910ee079，仅两条路径：RAW.inc改该输入路径，新增nuwa本地uefipil.cfg。候选配置SHA dbc9ee6e4c7728b32245453322f348c32d6a5eef0107f8c07662918bc3c23fdd；对原配置只改AUTO ABL行为，不改GUID/RETAIL/镜像定义/内存数值。保留原配置既有行尾空白，未借机格式化。固件提交信息符合既有格式，逐blob/tree/commit等同发布报告source-publish.json；稳定/SEC/相对偏移旧分支未改。

新增firmware-pil-no-auto-profile.json，继承SEC profile并固定该新提交、R-008已批准的相对头0以及两个新源码输入。`check-pil-no-auto-profile.py`核对33项本机来源hash、完整profile差异与board固定值，通过；两个旧资料库只读，未初始化/改写其中任何源码。

固件workflow增加独立pil-no-auto选项。CI构建校验头时区分relative text_offset和FD destination，不再把新头0误判为必须等于FD_BASE；旧profile默认行为保留。下载检查器新增严格新FD门：实际PILDxe PE SHA不变、原GUID仍存在、实际RAW SHA为dbc9ee6e且AUTO条目为空、正确头0、SEC标记与四个真实EFI继续核对。旧R-007产物回归检查通过；没有为了通过而删除旧profile保护。

当前编译/下载产物与实机结果待后续记录，不能用profile或源码静态检查替代。

## 后续验收顺序

固定本设备提交启动CI → 取实际终态/日志/产物 → 严格检查新RAW/PILDxe/SEC/四EFI/FD/shim → v4原头受限打包（仅kernel_size，raw shim+FD，无新DTB/ramdisk/FAT/XNU）→ 重新识别nuwa并核对Android/恢复源 → D-016隔离bootloader临时试启动 → 记录画面/采样并恢复Android=1，核对三个Android分区hash。任何失败以实际首错推进，不自动切换R-009 B。
