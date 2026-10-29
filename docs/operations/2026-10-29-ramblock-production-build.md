# RamBlock 生产编译入口接入

2026-10-29，S01/S03/S05/S13；按[官方驱动构建方法](https://unixnu.com/porting/drivers)复核真实编译记录和archive输入。此次实现的是生产环境编译入口，不是已经通过生产编译或最终内核链接。

## 实现

`scripts/ci/build-ramblock-archive.py` 在 macOS Actions 的本次 RUNNER_TEMP XNU 构建中执行，验证 IOPlatformExpert 实际编译记录及对应已生成对象，保留私有定义、ABI、编译器及SDK参数。固定RamBlock提交且要求源码干净。IOStorageFamily公开参考通过固定commit和tar SHA获取到临时构建目录；不当成donor完全一致的证明。

依次编译真实 NativeRamBlock、NativeRamBlockLateInit、IOBlockStorageDevice参考对象，保存头/源依赖摘要、原始诊断、对象和DWARF。使用同一编译器生成驱动汇编，导出显式构造器；LLVM仅用于section处理和archive工具，版本输出留证。对转换前后运行section和重定位严格比较，拒绝注册入口含自动构造器。产出 build/ramblock-archive/libNativeRamBlock.late.a，不加入固定原类地址alias，不自动链接或启用启动补丁。

真实生产记录带 -fno-c++-static-destructors，因此允许基准只有mod_init而没有mod_term；仍要求实际mod_init存在。共享转换验证器默认旧严格规则保持，新生产调用只传入实际存在的待移除section集合。

`.github/workflows/kernel-merged-source.yml` 增加默认false的 `ramblock_archive_check` 输入。启用时，在现有XNU编译/平台链接成功后安装LLVM工具并执行本步骤，最终收集报告和新对象/archive。没有借用旧ref启动CI；本地更改尚未提交/推送。

## 修复既有预检阻塞

`build-8796-source.py` 原来只要设备候选目录有同名文件，就优先采用它，导致未选入审阅清单的新版native-dt-panic-region.patch遮住历史原版。现在按审阅记录chosen的来源选择设备候选或上游文件，再执行原有SHA校验；merged明确override继续优先。未删除/修改新候选，也未接受变更摘要。

64份实际选择的补丁与历史成功CI逐项摘要一致，完整 --profile merged --check 已通过：out/ramblock-ci-precheck-20261029.txt。这一修复恢复选定配方的可检查性，不表示新候选已选用。

## 本机验证

- scripts/ci/test-ramblock-ci-inputs.py 四项通过：未选同名候选不遮蔽、已选设备候选保持必需、真实64补丁序列一致、真实编译记录的私有/ABI参数保留。
- 实际Mach-O无析构段场景检查通过：7个运行section和624条重定位一致。out/ramblock-ci-transform-20261029/check.json。这里只是对象转换验证。
- Python语法、WSL PyYAML解析工作流、git diff --check通过。Windows缺PyYAML的首次检查未成功，随后在已有WSL PyYAML环境检查；首轮路径断言使用POSIX字面值在Windows失败，已改为平台Path字符串并重跑通过。

## 未关闭的门槛

需要发布精确审阅commit后运行新CI步骤，确认Apple私有编译、警告和新对象ABI。旧公开配置得到的0x90/0x160及dispatch结果不能自动覆盖新私有对象；DWARF与参考对象已纳入待生成证据。

之后仍需把启动候选、功能宏、late archive及原storage绑定接入真正kernel make，按新布局完成prelink并验证实际call/GOT/构造器列表和6个UFS weak接口。此步骤未实现完毕、未通过，不以archive脚本或LLD用户态bundle失败替代最终链接验收。当前仍无新boot、设备操作、提交、推送或运行资格变更。

## CI 40851582287 失败修复

用户随后授权运行CI，提交a7a2a39已推送独立分支。该run的XNU源码编译、真实内核链接及平台archive链接步骤成功；RamBlock的command 0失败。取回artifact后确认唯一fatal error为 IOStorageDeviceCharacteristics.h:27 找不到 TargetConditionals.h；8条现有头风格警告不是终止原因。完整原始stderr位于 out/ci-ramblock-40851582287-proxy/nuwa-8796-source/reports/ramblock-archive/command-0.stderr。

修复在保留-nostdinc及全部私有参数的前提下，从本次DEVELOPER_DIR下xcrun解析的真实iPhoneOS SDK单独链接TargetConditionals.h到临时include目录，验证文件存在及SDK归属，并记录路径/内容SHA；不生成平台常量或添加整个用户态SDK include树。依据：[Clang include选项说明](https://clang.llvm.org/docs/ClangCommandLineReference.html)。另将失败stdout/stderr直接输出到Actions日志，仍完整保留artifact原件。四项既有回归和Python语法检查通过；修复是否解除实际生产编译失败由新CI结果确认。
