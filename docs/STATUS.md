# STATUS

> 当前唯一真相；历史只追加WORKLOG。更新：2026-10-22 11:03（Asia/Shanghai）。

## 当前结论

GitHub账号wh1stl3已登录，公开的[基座fork](https://github.com/wh1stl3/UniXNU)与[nuwa设备仓](https://github.com/wh1stl3/UniXNU-nuwa)已创建。固定75bc基座的8796源内核CI入口已准备，48项输入hash及适配后的bash语法静态检查通过，待提交/上传并手动触发。**当前没有内核构建通过证据**。见[首轮CI说明](operations/2026-10-22-source-kernel-ci.md)。

## 当前边界

- 用户后续明确允许全部Git命令，并选择公开设备仓。此前Git只读禁令已解除；本地Git写入仍须遵守宿主沙箱权限。按[提交队列](COMMIT-QUEUE.md)分里程碑提交，不改写历史。
- 两个旧仓及其上游来源树仍只读。设备仓独立，用-D接入正式基座；云端临时源构建树在RUNNER_TEMP、设备仓外。本地不复制上游源码树。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392，8796.141.3；ipad_identity=true。D-002窗口上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true。四类硬停不变；无_verified=true、固件/诊断镜像或设备动作。

## 已有证据与限制

- [源构建输入检查](../reports/official-ci-plan/source-input-check.json)：同一Apple 8796提交1b191cb，48项选择hash匹配；3处产物名、内核/链接和firehose的iOS16部署目标在内存适配，bash -n通过。没有在本机执行make。
- 源CI使用基座75bc真实配方，仅关闭可选设备archive/boot-progress；不压掉链接错误、不创建stub，不运行IPSW/预链接/固件/payload/bootimg。即使源内核成功，也不代表完整nuwa内核或实机通过。
- [官方CI审查](operations/2026-10-22-official-ci-route.md)：固定e95b的macos.yml真实存在；领先本地75个提交、491项完整路径/blob变化。没有整体升级；旧48项结论不平移到e95b。官方kernel仍无条件预链接，默认10063/iOS17。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：设备archive ABI、13项回调及watchdog scratch覆盖风险仍未解决；完整driver/donor接口门未过。
- [WSL预检](../reports/wsl-firststage/preflight.json)仍缺目标clang内建、IIG与sysroot输入；9项工具自身测试通过，MIG/宿主语法样例通过，预检exit2，不是内核构建成功。D-008转向macOS Actions，R-003 A保留历史。

## 下一步

1. 检查待发布文件，按队列提交并上传设备仓；将专用源构建workflow安装到基座fork，使用精确device_ref手动触发，收集实际编译/链接结果。
2. 按第一处真实失败修复8796源构建兼容性；成功后检查Mach-O、对象/符号及版本证据，仍不宣称预链接/QEMU/实机通过。
3. 完成Darwin22设备archive、boot-progress/watchdog、nuwa defconfig及donor kernelcache解析，接回正式-D设备构建入口；feed切换独立处理。
4. 板值/内存/地址、镜像或设备动作命中硬停时先写NEED-REVIEW再停。只差人按实体键的项记PENDING-HUMAN后继续。

## 其余缺口

donor hash/slide/initializer/roots、driver符号闭包、SMMU/DMA和用户态ABI/PAC未验证；uefi-nuwa/ADT/实机板值未落实，b槽不作可靠兜底。本轮无实体按键待办。
