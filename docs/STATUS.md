# STATUS

> 当前唯一真相；历史只追加WORKLOG。更新：2026-10-22 11:28（Asia/Shanghai）。

## 当前结论

公开基座fork及设备仓已创建。[首轮CI](https://github.com/wh1stl3/UniXNU/actions/runs/39715232540)失败于clang17拒绝8796过期启用开关；保留变量清零的修复已提交推送dbbf029，[第二轮39716728005](https://github.com/wh1stl3/UniXNU/actions/runs/39716728005)正在编译。首轮已证明Xcode16.4/SDK18.5/IIG/MIG可用、48项实际应用及ARM64 firehose真实构建；修复后48+1项精确顺序和bash静态检查通过。**内核构建尚未通过**。见[CI说明](operations/2026-10-22-source-kernel-ci.md)。

## 当前边界

- 用户后续明确允许全部Git命令，并选择公开设备仓。此前Git只读禁令已解除；本地Git写入仍须遵守宿主沙箱权限。按[提交队列](COMMIT-QUEUE.md)分里程碑提交，不改写历史。
- 两个旧仓及其上游来源树仍只读。设备仓独立，用-D接入正式基座；云端临时源构建树在RUNNER_TEMP、设备仓外。本地不复制上游源码树。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392，8796.141.3；ipad_identity=true。D-002窗口上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true。四类硬停不变；无_verified=true、固件/诊断镜像或设备动作。

## 已有证据与限制

- [源构建输入检查](../reports/official-ci-plan/source-input-check.json)：同一Apple 8796提交1b191cb，48项原选择hash匹配，追加1项clang17兼容补丁；[49项顺序检查](../reports/kernel-ci/39715232540/compatibility-check.json)通过、清零仍保留。没有在本机执行make。
- 源CI使用基座75bc真实配方，仅关闭可选设备archive/boot-progress；不压掉链接错误、不创建stub，不运行IPSW/预链接/固件/payload/bootimg。即使源内核成功，也不代表完整nuwa内核或实机通过。
- [官方CI审查](operations/2026-10-22-official-ci-route.md)：固定e95b的macos.yml真实存在；领先本地75个提交、491项完整路径/blob变化。没有整体升级；旧48项结论不平移到e95b。官方kernel仍无条件预链接，默认10063/iOS17。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：设备archive ABI、13项回调及watchdog scratch覆盖风险仍未解决；完整driver/donor接口门未过。
- [WSL预检](../reports/wsl-firststage/preflight.json)仍缺目标clang内建、IIG与sysroot输入；9项工具自身测试通过，MIG/宿主语法样例通过，预检exit2，不是内核构建成功。D-008转向macOS Actions，R-003 A保留历史。

## 下一步

1. 跟踪第二轮39716728005（device_ref=dbbf029），按真实首个失败继续修复。首轮原始证据已保存reports/kernel-ci/39715232540/；第二轮状态见对应run.json。
2. 按第一处真实失败修复8796源构建兼容性；成功后检查Mach-O、对象/符号及版本证据，仍不宣称预链接/QEMU/实机通过。
3. 完成Darwin22设备archive、boot-progress/watchdog、nuwa defconfig及donor kernelcache解析，接回正式-D设备构建入口；feed切换独立处理。
4. 板值/内存/地址、镜像或设备动作命中硬停时先写NEED-REVIEW再停。只差人按实体键的项记PENDING-HUMAN后继续。

## 其余缺口

donor hash/slide/initializer/roots、driver符号闭包、SMMU/DMA和用户态ABI/PAC未验证；uefi-nuwa/ADT/实机板值未落实，b槽不作可靠兜底。本轮无实体按键待办。
