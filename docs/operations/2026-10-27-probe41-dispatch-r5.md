# PROBE41 r5：实际ResourceFork分派目标

本轮用户要求调整PROBE41观测范围并重新生成镜像，仅离线，不部署或访问设备。阶段为S05文件系统实际调用/返回、S12画面证据、S03/S13绑定与交付。S04完整平台资格、原生资源读取/解压和首次EL0仍未完成；本轮不以宿主OS/Data成果代替这些前提。

## 调整范围

保留r4的22个resource helper观察点、后续decode/read/exec及239释放门。在固定原始内核SHA256 `1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6`的原生`VNOP_GETXATTR`包装中新增两个点：

| A03D | A03E含义 | 可作的判断 |
| --- | --- | --- |
| `FFFFFFF00746E1A4` | 原生`blr x8`执行前已解析的实际x8目标 | 达到分派调用前，不能认定handler入口已执行 |
| `FFFFFFF00746E1A8` | 配对分派返回后的原始x0 | 该次handler调用已返回；不是完整文件读取/解压成功 |

仍使用原A03D/E矩形，不增加网格。A03A—C和其它观察保留；后续helper续接正常覆盖最新检查点。观察器不自行解引用vnode操作表或目标指针，直接记录原生已加载的x8；原生BLR重定位保留真正的目标及原生续接LR。未修改分配、锁、缓存、IRQ、认证、返回码或root/Data输入。

作用域继承当前header、TPIDR_EL1、实际callback、decode帧及父调用配对；另核对wrapper原生保存LR等于helper `6DA0`、resource帧/LR/active、VNOP未完成配对位，以及分派自己的wrapper FP/active配对。独立诊断状态16字节，每次header清零；r4的32字节resource状态不挪用。A03D始终是最后记录点，不是采样的停止PC。

## 离线核验

`resource_dispatch_sites.py`提供两点及作用域；`resource_dispatch_checks.py`由强制`test-read-flow.py`调用，检查源码摘要纳入包证据绑定。新增38项包括两个站点各16种作用域/配对条件、真实wrapper参数准备到两个不同fixture目标及0/93返回的四条连续路径、header重置和缺VNOP配对门负对照。比较原生寄存器/标志/SP/PC，核对实际目标和参数、配对状态以及原矩形内像素。handler主体仍为明确fixture，未执行APFS、分配器或硬件IO。

初次专项末尾的负对照选到了更早的callback配对位，未能拒绝该变异，未生成通过报告；修正为实际VNOP配对检查后38项通过。另一次stdin测试入口缺scripts导入路径而失败，补入明确路径后执行。r5内核生成期间WSL输出localhost代理提示，Windows UTF-8读取线程报告解码错误；三个编译/链接/objcopy命令exit0，原commands.json中的stderr=null保留，不能将其解释为空stderr。后续完整回归、独立重建及包回读分别验收，不将首次过程错误抹掉。

## 后续实机范围

后续恢复设备工作时，先按当轮身份、包摘要、拍摄与实体键恢复条件作新鲜预检。本轮没有启动授权动作。拍摄从菜单电源键触发起的连续录像，并在稳定后拍清完整HEX区域；按实际画面变化和恢复条件结束，不设固定180秒。

一次集中回答：helper入口是否执行；UIO创建是否返回；是否到达实际getxattr分派、目标为何、是否返回；清理/错误日志是否续接；成功后能否继续解压、外层读取及exec。若止于分派调用前，只能依据最新检查点和录像约束下游范围，不能直接宣布APFS死锁。完整OS/Data、UFS与显示修复不混入本轮诊断输入。

依据2026-10-27在线核对的[官网启动检查点](https://unixnu.com/porting/bring-up)与[日志采集指南](https://unixnu.com/porting/log-capture)，按当前阶段保存图像及最后检查点。公开指南提供方法，不是nuwa实测证据。

最终产物与验收结果在全部检查完成后追加。旧r4包/资格和PROBE40媒体、报告保持原始字节；旧28—40已消费命令只追溯，不重发。

## 最终交付 · 2026-10-27T18:29:35.355383+08:00

PROBE41已调整为实际ResourceFork分派版r5，未启动、未消费。镜像out/trial-boot/xnu-entry-probe-41-dispatch-r5/boot-xnu-first-entry.img，204484608字节，SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；内核89fdd0a831500ff2f28d2245824c47a0d1ad5e7d1719c42f7ede3b7e9237eaad，ADTfbc8ee7eabb52c2d1c0e4bca2dd581af6b107f0c2672fba33b8f455fa1e5e155。38项串行作业全部通过，2420透明性、1015专项（含新增38项分派检查）、9连续路径/重置、独立内核逐字节复现与镜像回读通过。新增A03D=FFFFFFF00746E1A4/A03E=原生实际x8目标，A03D=FFFFFFF00746E1A8/A03E=配对返回原始x0；调用前不是handler入口，A03D不是停止PC。仍使用原矩形，旧22点及后续主线继续；Restore根、239门、板值/内存/IPSW身份、verified边界不变。旧r4内核/ADT/整包摘要核对不变，旧资格保留且不套给r5。本轮没有设备操作、提交、推送或CI。详情docs/operations/2026-10-27-probe41-dispatch-r5.md，资格reports/kernel-entry-probe/2026-10-27-v49-r5/qualification.json，包报告reports/xnu-first-entry/entry-probe-41-r5.json。

生成命令和工具状态保存在两个独立kernel工作目录的commands.json；完整回归命令、各作业exit0及输出在execution.json与out/probe41-dispatch-r5-regression-console.txt。连续路径、复现、打包日志见同一r5报告目录下vector-console.txt、reproduce-console.txt、package-console.txt及package-validation.json。新增38项检查包含在read-flow.json的1015项内，不重复相加。两次kernel相同不表示含随机nonce的整包要求字节复现。

可只读复核的已执行命令：

```powershell
& C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-41-r5.json
```

待验收仍为实际helper/UIO/getxattr及解压续接、exec/EL0；完整OS/Data provider与原生挂载、UFS、平台和桌面资格单独保留。宿主fixture不证明这些运行结果。后续工具维护项：WSL非UTF8提示的原始stderr采集/解码；本轮未修改代理或安全配置。

2026-10-27T18:43:05.203664+08:00 · 用户恢复实机且当轮确认连续拍摄/实体键恢复已就绪。PROBE41 r5单次临时启动已获fastboot Sending/Booting OKAY，包SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；ACK只证明命令接受，不证明菜单/内核/handler已执行。候选已消费，禁止重发。新鲜预检Android1、nuwa/kalama、A槽，三SHA与PROBE40一致。当前等待用户菜单电源Enter、连续录像/稳定照片和回Android；启动后设备状态尚未取得后验，不沿用启动前Android1冒充恢复。证据reports/xnu-entry-probe-trial/2026-10-27-v49-r5/{preflight,launch,consumed}.json。媒体目录D:/Code/PortingiOS/nuwa/Media-nuwa；恢复后补postcondition与三SHA。未flash/erase/改槽、未提交。
