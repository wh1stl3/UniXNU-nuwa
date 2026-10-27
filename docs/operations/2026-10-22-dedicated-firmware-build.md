# 独立固件仓真实构建与阶段诊断候选

## 已完成的R-004 A构建

CI39805110487，设备提交0b9dbd6，独立固件源码0a3a51a，UniXNU包75bc13；Darwin22 ABI patch8532237e。原内存表/nuwa.toml及board/feed哈希保护保留。安装工具4分23秒，实际构建5分37秒，整轮success，2026-10-22 23:38:25（Asia/Shanghai）完成。前一轮39802617878因Azure镜像依赖下载阻塞取消，次生No files上传错误单独保留；本轮使用官方Ubuntu镜像和有限超时，未删除依赖或编译检查。

下载artifact12438077239（13366074B），独立检查全部665项inventory文件长度/SHA，解析嵌套FV/FFS、PE/TE、模块GUID/DEPEX/PCD/协议/SEC入口HOB、BootShim机器码复制量，均静态检查通过。四模块：UniXNU、UniXNUDxe、DarwinBoot、NuwaBootMemoryDxe。新发布器保留既有GUID，不引入额外DRAM/GCD区域。

- FD3145728B，SHA256 **7f6f16c8c58c4695c1d883e1597e52379042175e4b668ad5e99e4e6a648707de**。
- BootShim112B，SHA256 **9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9**，image_size3145840、payload offset112、copy_count3145728。
- DarwinBoot完整编译链接已包含608B/0x2e0结构修复与边界复制，真实构建成功不再停留语法样例；源哈希门在构建前后均执行。运行ABI仍未验证。

命令：

```powershell
gh run download 39805110487 --repo wh1stl3/UniXNU-nuwa --dir out/firmware-ci/39805110487
python -X utf8 -B scripts/ci/inspect-firmware-candidate.py out/firmware-ci/39805110487/nuwa-firmware-39805110487 --publisher-name NuwaBootMemoryDxe --output reports/firmware-ci/39805110487/artifact-inspection.json
```

runner原始result仍写artifact inspection pending，原文保留；独立artifact-inspection.json记录后续完成，不篡改runner记录。大日志与二进制仅out/；reports/保留输入、命令、inventory、工具链与检查结果。GH整包ZIP digest44c83aed…仅为服务端元数据，下载工具未留下原ZIP，本轮不宣称本地完整ZIP摘要核验。

没有生成新的Android boot容器、预链接负载，也没有把此FD送上设备。新FD不含XNU，旧v4包仍是旧FD，不可拿旧包验收新固件。普通基座-D入口仍受example/必填项限制。

## 下一诊断的具体源码候选（未应用）

新增patches/firmware-candidates/0005-nuwa-sec-stage-trace.patch，SHAae5d5e16254da93dac42665bfedeef77cf1ed737df0332fe84f1b2dfce57303f。仅修改SEC.c：在PlatformInitialize前后、MemoryPeim前/返回、PlatformPeim前/返回、FV解压前/返回、DXE Core调用前/返回增加WARN标记和已有x0值；移除本文件的45MiB全屏清零以保留较早标记。原SMMU/内存/HOB/解压/DXE调用及错误返回保持，不改BootShim、MMIO/地址、board、内存图、FDT、DTB、XNU或donor数据。

scripts/check-sec-trace-preview.py验证固定SEC原始LF哈希fd28b903…、严格RAM应用、单文件范围、原阶段调用各一次、六个标记各一次及无新增地址/头文件；另git -C D:/Code/PortingiOS/nuwa/uefi-nuwa apply --check通过。只读源码仓保持干净。新源码尚未完整编译；报告sec-trace-preview.json明确这一点。

候选仍走原帧缓冲DebugLib：不具备USB/UART/跨重启日志，不能观测ABL/BootShim/最早汇编，若未显示仍不能证明SEC未执行，打印/cache flush可能改变时序。输出前未调用SerialPortInitialize的依据是当前实现只返回EFI_SUCCESS、不建立硬件；这不是已验证的运行前置条件。执行需要单独诊断镜像范围R-007批准，尚未接到活动CI profile。

另一候选为先实现USB设备端日志与有证据的早期RAM日志保留/回收；覆盖与成本见既有log-export-options报告，DXE USB无法单独定位更早挂死。当前Android ramoops与固件FD重叠，不能填一个现成地址冒充安全持久缓冲区。
