# 合并版8796内核独立产物核验

## 实际结果

CI39793231214固定device_ref=3a210b1，成功后两次完整146197478B ZIP下载EOF；历史失败保留artifact-download.json。使用scripts/download-kernel-evidence.py，以1MiB HTTP Range、206/Content-Range严格检查和单块重试，从同一artifact12432438112读取ZIP目录与18个成员（实际数量见selective-download.json），不下载重复链接库/dSYM。各成员全量CRC校验；没有完整ZIP的SHA验证，不将GitHub摘要声称为本地整包通过。凭据与签名URL只在内存。

实际内核20187912B，SHA256 77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8，与runner平台重链接报告相同。固定NativePrelink解析器只读检查：ARM64 subtype0 MH_EXECUTE，Darwin22.6.0，8796.141.3，minimumOS16.0，所有段起始4KiB对齐、两个prelink版本标记为1，21835导出、0未定义符号。五项ArmCpu/ArmDTPlatform导出逐项存在；三个实际archive格式/长度/哈希与runner报告相同。ArmVirtPlatform仅编译审查，未链接进此内核。

实际donor指针表扫描：41095个kernel、24253个component，共65348项，failure_count=0。此检查不生成/重绑定/预链接镜像；只证明所选组件的指针符号映射，不能代替完整C++/运行ABI、PC-relative重定位或设备驱动初始化。

## 可复核命令

```powershell
python -X utf8 -B scripts/download-kernel-evidence.py 39793231214
python -X utf8 -B scripts/ci/summarize-build-evidence.py 39793231214 --artifact out/kernel-ci/39793231214 --repo wh1stl3/UniXNU-nuwa
python -X utf8 -B scripts/ci/inspect-source-kernel.py out/kernel-ci/39793231214/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped --output reports/kernel-ci/39793231214/kernel-inspection.json --platform-link-report out/kernel-ci/39793231214/nuwa-8796-source/reports/platform-link/audit.json --artifact-root out/kernel-ci/39793231214
```

第三个只读donor命令的输入路径见reports/kernel-ci/39793231214/donor-bindings.json以及2026-10-22-donor-vfs-bridge.md，使用同一iPhone donor与既有分析组件集。

百万行源编译日志的限定错误扫描无命中，841项XNU目标对象；这不是对全部警告的审阅。证据在reports/kernel-ci/39793231214/，大日志与二进制仅out/。

## 下一环

同轮已按R-004 A调度独立固件CI39802617878，固定设备提交a93b8ca、firmware0a3a51a。仅四EFI/FD/BootShim，不生成Android boot容器、不改地址/board/feed。CI15仍是历史固定负载，本轮不自动换kernel candidate。新内核尚无本轮DWARF、完整预链接或任何设备执行证据。
