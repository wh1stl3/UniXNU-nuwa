# 官方中文文档页面索引

抓取完成时间（UTC）：2026-10-22T13:07:48.750029+00:00。72页全部HTTP200；144个发布路由中有72个中文路由，中文遗漏0。英文只核对结构配对，没有重复审阅全部英文正文。

原始HTML与正文位于out/official-site-audit；SHA256、标题、页内ID、全部链接见structure.json。下表链接均指官方原页。

## 首页与构建（2页）

- [UniXNU](https://unixnu.com/zh/)：
- [构建](https://unixnu.com/zh/building)：快速开始；macOS runner；命令；常用选项；步骤；本地模块；输出；可复现性；下一步

## porting（5页）

- [移植总览](https://unixnu.com/zh/porting/)：移植清单；通用部分；设备相关部分；设备页面；下一步
- [bring-up 顺序](https://unixnu.com/zh/porting/bring-up)：阶段 1：UEFI；阶段 2：UniXNU；阶段 3：负载；阶段 4：DarwinBoot；阶段 5：内核入口；阶段 6：存储与根卷；阶段 7：用户态；先在 QEMU 验证；失败隔离；下一步
- [设备仓库](https://unixnu.com/zh/porting/device-repository)：布局；board.toml；defconfig；feeds.toml；专有文件；本地开发；package 与 kit；下一步
- [设备树](https://unixnu.com/zh/porting/device-tree)：Apple 设备树编码；必需节点；ADT 工具契约；UEFI 设备树；启动镜像设备树；参考生成器；下一步
- [UEFI 固件](https://unixnu.com/zh/porting/uefi-firmware)：必需服务；Mu-Silicium 布局；设备配置；DSC 与 FDF；预检；厂商输入；子模块与补丁；构建；独立构建；启动镜像集成；验证；添加 UEFI 驱动；下一步

## guide（8页）

- [启动镜像](https://unixnu.com/zh/guide/boot)：前提；启动；启动管理器；Darwin 启动；首次启动；日志；恢复；macOS；下一步
- [构建内核](https://unixnu.com/zh/guide/build-kernel)：源码与构建树；defconfig 开关；构建顺序；新增内核开关；使用已有内核；下一步
- [调试与日志](https://unixnu.com/zh/guide/debugging)：日志来源；串口；屏幕诊断页；脉冲条；panic 屏幕；用户态故障证据；UI 栈追踪；拍照；QEMU 抓取；调试参数；证据包；下一步
- [MobileGestalt 身份](https://unixnu.com/zh/guide/mobilegestalt)：属性；全面屏手势；iPadOS 与 iOS；应用；缓存；下一步
- [总览](https://unixnu.com/zh/guide/overview)：分层模型；组件；仓库；构建产物；下一步
- [构建环境](https://unixnu.com/zh/guide/requirements)：主机；外部输入；设备；下一步
- [Skip Setup](https://unixnu.com/zh/guide/skip-setup)：命令；工具修改的内容；构建版本；设备树；任务；输出；验证；下一步
- [userdata 镜像](https://unixnu.com/zh/guide/userdata)：构建；分区；布局；刷写；根卷选择；Data 卷；下一步

## concepts（5页）

- [启动链](https://unixnu.com/zh/concepts/boot-chain)：1. bootloader 到 BootShim；2. UEFI 到 UniXNU；3. UniXNU 到 DarwinBoot；4. DarwinBoot 到 XNU；5. XNU 到用户态；失败行为；下一步
- [启动负载](https://unixnu.com/zh/concepts/payload)：卷布局；配置；ADT sidecar；内核参数；trust cache；Data ramdisk；确定性；下一步
- [内核预链接](https://unixnu.com/zh/concepts/prelink)：输入；预链接步骤；合并段；指针重绑定；早期安全初始化；kernelcache 固定；稀疏与容量；报告；下一步
- [完整性与启动策略](https://unixnu.com/zh/concepts/security)：输入；trust cache；4 KiB 下的代码签名；AMFI 策略；GPU client 授权；verified root；存储完整性；报告；下一步
- [userdata 布局](https://unixnu.com/zh/concepts/userdata)：manifest；窗口；容量；根卷匹配；Data 卷；报告；下一步

## drivers（7页）

- [设备树匹配](https://unixnu.com/zh/drivers/device-tree-matching)：personality 键；Provider 类；匹配示例；设备树节点；读取属性；overlay 与补丁；probe 顺序；下一步
- [kext 包](https://unixnu.com/zh/drivers/kexts)：包布局；Info.plist；注册到 UniXNU；UniXNU 校验；加载器协议；构建 kext；签名与信任；顺序与依赖；下一步
- [Adreno 740 驱动](https://unixnu.com/zh/drivers/native-adreno)：运行时链路；发布到 render server；组件；最新提交，从新到旧；状态；着色器编译；构建；相关
- [Novatek NT36532E 触控驱动](https://unixnu.com/zh/drivers/native-novatek-touch)：两层结构；触控处理；控制器协议；板级常量；探针阶段；硬件路径；HID 发布；适配这个示例；下一步
- [驱动分层](https://unixnu.com/zh/drivers/overview)：选择层次；匹配；设备树；驱动目录；下一步
- [UEFI 驱动](https://unixnu.com/zh/drivers/uefi-drivers)：模块布局；构建；从 UniXNU 加载；固件卷路径；加入固件卷；Driver model；协议；示例模块；日志；下一步
- [XNU 驱动](https://unixnu.com/zh/drivers/xnu-drivers)：源码布局；驱动类；按内核 ABI 编译；静态库；链接进内核；加入 personality；Provider 属性；内存；中断；设备树资源；运行时行为；测试；参考驱动；完整示例；下一步

## xnu（4页）

- [启动参数](https://unixnu.com/zh/xnu/boot-arguments)：格式；常用参数；平台参数；新增参数；调试；下一步
- [4 KiB 页表](https://unixnu.com/zh/xnu/four-k-page-tables)：granule 常量；启动页表；运行时页大小；用户地址空间；代码签名；分配器对齐；4 GiB 以上的物理地址；非 Apple 平台保护；SMMU 与 4 KiB 表；验证；新代码规则；下一步
- [补丁参考](https://unixnu.com/zh/xnu/patch-reference)：构建与工具链；平台与 CPU；4 KiB 页；安全与 owner root；图形与显示；诊断；行为修复；Mockfs；预链接补丁；新增补丁；下一步
- [源码与补丁](https://unixnu.com/zh/xnu/source-and-patches)：源码；补丁应用；补丁目录；新增补丁；构建开关；defconfig 映射；源码树；更新源码；下一步

## reference（7页）

- [启动配置](https://unixnu.com/zh/reference/boot-configuration)：unixnu.toml；Kit.toml；菜单行为；下一步
- [命令行](https://unixnu.com/zh/reference/cli)：命令；选项；环境变量；退出行为；下一步
- [设备配置](https://unixnu.com/zh/reference/configuration)：board.toml；defconfig；feeds.toml；local.toml；unixnu.lock；模块解析；下一步
- [术语表](https://unixnu.com/zh/reference/glossary)：下一步
- [输出布局](https://unixnu.com/zh/reference/output-layout)：目录；state.json；feeds；ipsw；tree；logs；boot.json；payload.json；userdata-root.json；清理；下一步
- [QEMU 测试](https://unixnu.com/zh/reference/qemu)：前提；准备 ESP；运行；冒烟测试；XNU 入口 fixture；HVF；停点；下一步
- [故障排查](https://unixnu.com/zh/reference/troubleshooting)：构建；IPSW；启动；日志；检查报告；模块来源；下一步

## devices（32页）

- [支持的设备](https://unixnu.com/zh/devices/)：社区移植；设备页面记录什么；新增设备；sheng
- [Redmi Note 14 Pro+ 5G（amethyst）](https://unixnu.com/zh/devices/amethyst)：状态；维护
- [一加 5（cheeseburger）](https://unixnu.com/zh/devices/cheeseburger)：状态；维护
- [小米 15（dada）](https://unixnu.com/zh/devices/dada)：状态；维护
- [Redmi 9A（dandelion）](https://unixnu.com/zh/devices/dandelion)：状态；维护
- [DroidVM 客户机（Gunyah 上的 crosvm）](https://unixnu.com/zh/devices/droidvm)：状态；维护
- [一加平板 2 Pro（erhai）](https://unixnu.com/zh/devices/erhai)：状态；构建；维护
- [一加 6T（fajita）](https://unixnu.com/zh/devices/fajita)：状态；构建；维护
- [小米 13（fuxi）](https://unixnu.com/zh/devices/fuxi)：UniXNU-fuxi；hanzi123-bilp 仓库；维护
- [一加 Ace 5（giulia）](https://unixnu.com/zh/devices/giulia)：状态；tycykp 仓库；维护
- [三星 Galaxy Tab A7 10.4（gta4l）](https://unixnu.com/zh/devices/gta4l)：状态；维护
- [OnePlus 7 Pro（guacamole）](https://unixnu.com/zh/devices/guacamole)：状态；构建；维护
- [Redmi K40 Pro（haydn）](https://unixnu.com/zh/devices/haydn)：状态；haydn4 仓库；维护
- [一加 Ace 5 Pro（hummer）](https://unixnu.com/zh/devices/hummer)：状态；维护
- [小米平板 5（nabu）](https://unixnu.com/zh/devices/nabu)：状态；维护
- [小米 13 Pro（nuwa）](https://unixnu.com/zh/devices/nuwa)：状态；维护
- [努比亚红魔 8 Pro / 8 Pro+（nx729j）](https://unixnu.com/zh/devices/nx729j)：状态；维护
- [一加 13T（oneplus13t）](https://unixnu.com/zh/devices/oneplus13t)：状态；维护
- [OPPO Find X7 Ultra（PHY120）](https://unixnu.com/zh/devices/phy120)：状态；构建；维护
- [小米平板 8 Pro（piano）](https://unixnu.com/zh/devices/piano)：状态；构建；维护
- [Redmi K30 5G（picasso）](https://unixnu.com/zh/devices/picasso)：状态；维护
- [小米平板 6（pipa）](https://unixnu.com/zh/devices/pipa)：状态；维护
- [Galaxy Z Fold3（q2q）](https://unixnu.com/zh/devices/q2q)：状态；维护
- [QEMU virt](https://unixnu.com/zh/devices/qemu)：状态；维护
- [Redmi K20 Pro / Mi 9T Pro（raphael）](https://unixnu.com/zh/devices/raphael)：状态；维护
- [小米 6（sagit）](https://unixnu.com/zh/devices/sagit)：状态；维护
- [小米平板 6S Pro（sheng）](https://unixnu.com/zh/devices/sheng)：板级；IPSW；userdata；内核；defconfig；GPU；固件；负载；构建；启动；macOS；设备支持；观察状态；设备细节；下一步
- [无人值守测试流程](https://unixnu.com/zh/devices/sheng-unattended-test)：日志读取器；运行；默认关闭；离线检查
- [Redmi Note 10 Pro（sweet）](https://unixnu.com/zh/devices/sweet)：状态；构建；维护
- [小米平板 7 / POCO Pad X1（uke）](https://unixnu.com/zh/devices/uke)：状态；构建；维护
- [Redmi K70（vermeer）](https://unixnu.com/zh/devices/vermeer)：状态；维护
- [Microsoft Surface Duo 2（zeta）](https://unixnu.com/zh/devices/zeta)：状态；维护

## contributing（2页）

- [文档站](https://unixnu.com/zh/contributing/documentation)：环境；本地开发；结构；新增页面；语言版本；写作规则；链接检查；下一步
- [仓库布局](https://unixnu.com/zh/contributing/repository)：模块类型；解析顺序；构建树；脚本；新增模块；提交范围；下一步
