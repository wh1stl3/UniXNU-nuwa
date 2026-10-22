# Darwin22加载器结构与命令行修正

## 改动与生效范围

patches/loader-candidates/0005-darwin22-boot-args.patch针对固定DarwinBoot子模块d099354d0eab34df5088ca1ba89c9c88bc3260bb制作，也通过原75bc基线的git apply --check。只改BootArgs.h与DarwinBoot.c：

- 明确为nuwa的Darwin22/XNU8796专用构建，CommandLine由1024B改为608B，局部缓冲区使用同一常量。
- 尾字段断言改为BootFlags=0x2d0、MemorySizeActual=0x2d8、结构大小0x2e0。
- CopyMem以目标字段sizeof限定，保留现有ASCII/长度检查；607个非零ASCII字符加终止符可接受，608个非零字符拒绝，不静默截断。

长度与偏移来自CI15内核实际DWARF，见reports/official-site-audit/ci15-boot-args-dwarf.json；没有推测板级地址或改变内存窗口。该patch不供Darwin23负载使用，未来支持多版本应建立明确的独立构建/协议选择，不能默认为兼容。

已将patch及哈希加入config/loader-candidate.json，config/firmware-ci-inputs.json补充原始BootArgs.h哈希。构建脚本在应用后与编译后都检查两个修改文件的精确新哈希；未取消其他输入保护。当前固件基线仍为75bc，尚未触发构建，所以已存在的FD/v4包仍是旧版，不能称已修复的实机产物。

## 验证命令与结果

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/check-darwin22-loader.py
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-loader-candidates.py --report-dir reports/darwin22-loader/integration
```

证据reports/darwin22-loader/checks.json与integration/audit.json：

1. 最新子模块：精确上下文在RAM应用patch，不保存上游源码副本；旧只读源树：git apply --check退出0，无实际应用。
2. WSL clang14的AArch64 freestanding语法检查使用真实EDK II Base.h/AArch64 ProcessorBind.h；对三个实际DWARF结构逐项断言所有13个成员偏移、总大小及数组长度，通过。
3. 从两个版本实际DarwinBoot.c提取转换和复制语句，分别编译宿主可执行文件，启用ASan/UBSan，每版10个用例连续运行4次通过。覆盖空/1/606/607/608/609/1023长度、首尾非ASCII和NULL；验证拒绝时不写目标、成功时终止与零填充、尾字段和外部哨兵不被覆盖。宿主程序位于忽略的out，仅验证这些语句，未完整编译DarwinBoot模块，不是目标架构执行。
4. 源码接线审计通过89项检查。新审计显式区分firmware/sheng/unixnu三个虚拟树，检查新patch只改两个加载器文件及其应用后哈希。原厂表提取、既有PCD/FD赋值保护仍通过。

结论等级：静态检查通过；额外宿主用例结果不得写成QEMU或实机通过。完整模块编译、DXE安装、负载加载与运行ABI均未验证。没有生成EFI/FD/boot.img，没有设备访问或_verified修改。

## 宿主ASan异常记录

扩展测试时，PIE宿主程序一次退出139且没有诊断，完整首轮失败保留在first-attempt.json；同一PIE程序随后开启ASan日志连续4次通过，见asan-investigation.json。精确根因未验证，不能据此归因加载器或手机。读取WSL的mmap_rnd_bits被拒绝，未修改系统设置。

宿主测试改用-fno-pie/-no-pie固定布局，保留ASan/UBSan全部检查；两个版本各4次通过。此改动仅作用于宿主测试程序，不进入加载器patch或固件构建参数。后续若再出现139，继续保留失败，不用重跑覆盖失败事实。

## 下一步

先迁移合并版输入：核对模块固定提交、原48项选择的来源哈希变化和构建脚本上下文；完整DarwinBoot编译另取证。已有旧FD的黑屏仍需入口/日志证据；该包不含XNU，本patch不解释那次黑屏。若下一动作进入新的固件/诊断镜像生成，依据AGENTS与已有批准范围处理，不自动触发镜像工作流。
