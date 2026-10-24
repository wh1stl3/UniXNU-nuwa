# STATUS

> USB v3 的64MiB独立ramdisk封装、只读块发布及FAT挂载已实机通过。8177783e单次试验完成；Android于北京时间2026-10-24 15:41:49恢复完成1，三个启动分区SHA与试前不变，无需再按键/录像。

当前已解决配置卷之外的USB内存运输阶段：原图显示envelope result=1、bytes=0x4000000、块设备Success，FAT挂载早于NuwaEmbeddedVolumeDxe。内嵌fallback菜单不是判据。offset0x1d77f27减64B正好等于已记录vendor ramdisk30899943B，明显支持vendor+临时generic拼接；v4 init_boot替代为此前缺卷首因的判断增强。同固件v4匹配对照未实测，重复性未验。[本轮实测](operations/2026-10-24-usb-v3-trial.md)。

本轮证据reports/usb-ramdisk-trial/2026-10-24-v3-01/：两原图、screen-observation.json、preflight/baseline-check/launch/recovery/postcondition。120.0秒USB观察不是视频；用户交付照片和文字，未交付完整连续视频文件。实际postcondition.at=2026-10-24T07:41:49.163107+00:00，唯一nuwa/kalama、Android完成1、槽_a、三分区SHA一致。只一次候选，之后临时加载原厂v4恢复；无flash/erase/改槽位/OTG写入。

USB候选SHA8177783e1364caed71e0db82f4c91db720f9586f8bc0d05ca044e133be4ad898/70266880B，严格报告reports/usb-ramdisk/40014018074/package-v3.json。v4离线匹配对照91e86ce4，仅offset20/40两字节不同；4096之后相同，不安排自动试验。复用固定FD/112B shim及64MiB探针，原cmdline、Heap/HOB保护/缓存维护、内存表不改。7新测试、10历史门控、16项原始ABL选择门字节AArch64用户QEMU夹具通过；不是完整ABL执行。[准备记录](operations/2026-10-24-usb-ramdisk-v3.md)。

上游全部已审查更新合并：wh1stl3/UniXNU@e553e467ebfe7642e9f483d3977a57066c6d1aef，真实双亲merge上游1a01c2af，树为上游+3个nuwa工作流，21模块固定；独立检出D:/Code/UniXNU-integration，两旧资料库只读。接入5abdde1/前置修复6070627。默认firmware upstream-merged、kernel merged及预链接工具新源。[集成记录](operations/2026-10-24-upstream-integration.md)。

固件CI40014018074/source5abdde1 success：FD SHA2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3145728B，697静态检查。SEC7192fd3f与已实测26ef8efd逐字节相同，Heap/HOB保护、DSB/IVAC/DSB/ISB保留；本轮该FD已实测到独立卷/FAT/菜单。固件源码pin6176a822+11补丁，不用文档HEAD替代。之前26ef8efd的after-mmu/ReadyToBoot实测原图仍保留，本轮不伪造新的早期HOB日志。

内核CI40015845083/source6070627 success：bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，64补丁、Darwin22.6.0/iOS16.0、零未定义及ArmCpu/ArmDTPlatform五导出/归档独立核对。原40014023191失败已留档。新解析24、packed逻辑1TiB/13拒绝、SMMU夹具、grant9、常量池4通过，GPU VM仅AArch64用户QEMU软件夹具通过。21模块纳入不等于所有可选root/hash-cache/GPU分支已激活或硬件通过。

分析预链接eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定读回及30 donor/native代码范围保持、24解析通过，loadable=false。AMFI原始入口逆slide定位真实注册，局部conf80B偏移对应；12项补丁后源码时序检查与23项回调写入到实际335槽对应。文件DATA_CONST只读标志不足以判早期写保护故障，但完整构造/start/once-guard和回调/C++ABI未资格；initializer仍为空。[AMFI记录](operations/2026-10-24-amfi-phase-and-slots.md)。

下一步离线准备真实大文件的只读读取/SHA探针，沿已通过的USB v3运输，不重复同一菜单试验；不执行分析内核。完整OS负载仍缺初始化/ABI、真实nuwa ADT和实际分配窗口。9GiB为快照，64MiB封装CRC/FAT成功不等于真实58MiB文件SHA或XNU/iOS成功。board/bringup身份/内存/_verified未改，ST FTS路线保持。

用户已具备OTG线并授权选择路线，当前无需OTG，保留备选。没有未完成恢复或人工待办；下次新候选另过录像/恢复门并即时通知，不复用本轮许可。[交接](operations/2026-10-23-mainline-handoff.md)。
