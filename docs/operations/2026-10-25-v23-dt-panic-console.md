# v23：无pram时跳过旧panic导入，实机进入kernel_bootstrap

2026-10-25。延续用户“解决当前卡点、继续主线”。保持iOS16/8796、固件/板值/内存声明、认证与_verified不变，原始音视频不上传。

## 问题与修复范围

旧v22连续模型在PE_create_console+0x48读0x3c0fc000失败；出货二进制在console初始化前内联了BCM固定旧panic区导入。上游UniXNU16e592ab的native-dt-panic-region.patch可选DT路径，缺pram时自然返回，不跳过console。

已按固定上游补丁适配8796源码候选`patches/xnu-8796-candidates/native-dt-panic-region.patch`。严格patch --fuzz=0应用、实际check_for_panic_log函数体AArch64 freestanding编译（Wall/Wextra/Werror）及11个host UBSan DT边界用例通过，含无pram、缺chosen、错误属性宽度/零地址/溢出/区域过小/长度越界/映射失败/有效区。真实header结构来自只读8796 debug.h，sizeof=161。**不是整核源码构建或DriverKit重建通过。**

当前出货二进制的panic_text_len被优化为1字节状态，其他路径使用固定0x3f5f容量，不能把它当成通用动态缓冲长度赋值。因此诊断实现仅覆盖缺pram情况：在PE_create_console原生栈帧建立后，执行真实SecureDTLookupEntry；无节点则不触及旧panic全局/映射，返回原生initialize_screen路径。若pram存在，显式status=2/红色/A035=2并停住，不猜地址、不走BCM旧区。native console tail所需w20=1明确回放；当前panic代码未修改。

PE_initialize_console包装在出货PE_create_console中已内联并尾跳_initialize_screen，不能只在包装函数上打点；新marker钩在实际_initialize_screen入口。

## 候选与验收

entry-probe-16：镜像`6f0907b2ce684a70dd143664172bf083012bae5b31d3d4a195459d0c3f6400fa`；内核`167bd013da33a6a1e439b0dba5a4ec161ce5a90c781e14f446da6b520ec40753`；ADT`b674491617e625632ef509f12174b0d6d23ea580ba579c490f750db59d32a0df`。报告reports/xnu-first-entry/entry-probe-16.json。

证据reports/kernel-entry-probe/2026-10-25-v23c/：42入口/MMU、92普通钩子差分、18渲染、5WFE、8阶段、2异常、5ParseKernel、17绑定门；4切换场景12断言、6条console策略检查（实际包ADT/极简缺节点/有节点拒绝/保留screen入口/旧v22负对照）与11个源码函数体边界用例。

四个切换场景及console策略测试用最终镜像同一ADT重跑，摘要重新绑定，镜像字节未变；最终镜像回读通过。新候选连续模型从真实入口穿过MMU/pmap/console，到kernel_bootstrap原入口；旧v22负对照同ADT仍读0x3c0fc000失败。测试不代写正常路径页表、不跳PC、不把非法区映射成假RAM。

ParseKernel首轮在原始内核上出现间歇宿主ASan失败，同一可执行文件重跑正常，原因仍未验证。审计脚本改为即使失败也保存全部原始case；宿主夹具使用-fno-pie/-no-pie固定地址布局，保留ASan/UBSan，五例通过。这不修改EFI代码或候选内核，也不证明已找到历史rc139根因。

## 实机观察

用户针对PROBE16明确录像/按键恢复就绪。刷新preflight后单次临时boot，用户菜单电源键Enter触发，无180秒固定等待。用户文字“橙色出现”及照片均确认左列y512橙色0xffff8040（pmap绿色下方）出现，对应_kernel_bootstrap原入口0xfffffff00729e804。

右列x96/y256青黄色为缺pram策略命中，x96/y288棕色为实际screen初始化入口。该位置覆盖旧WFE阶段tile，必须按PROBE16布局解释，右侧A032仍是独立eventi读数。无A035=2和异常/panic记录可见，不推导绝对无后续异常。**最高实机事实为kernel_bootstrap入口；未证明完成、调度器、驱动、root或iOS。**

照片保留out/trial-evidence/entry-probe-16/screen-original.jpg，哈希和读数记录于reports/xnu-entry-probe-trial/2026-10-25-v23/screen.json，本轮尚未收到连续视频，不虚构时序证明。恢复闭环结果见该目录recovery/postcondition和STATUS更新。

## 下一步

1. 收敛kernel_bootstrap之后的阶段观察，先核对vm_mem_bootstrap、启动内存页释放/初始化的进展与模型预算。20,000,000指令续跑在_vm_page_release_startup+0x254达到预算、无错误，仅属模型进展，不能称死循环或实机停点。
2. 保留source DT panic补丁作正式源码构建候选，接入真实配置与8796重建前不得宣称支持通用DT日志缓冲。二进制无pram策略仅诊断桥接。
3. QR日志仍为独立UEFI工程，不替代当前内核观测。后续新包再过录像、preflight与恢复门，本轮不追加第二候选启动。

## 复现

```powershell
python -B scripts/audit-dt-panic-source.py --work out/NEW-source-check --output out/NEW-source-check.json
python -B scripts/test-probe-console-policy.py --build reports/kernel-entry-probe/2026-10-25-v23c/build.json --adt out/trial-boot/xnu-entry-probe-16/kernel.macho.adt --negative-build reports/kernel-entry-probe/2026-10-25-v22c/build.json --output out/NEW-console-policy.json
python -B scripts/test-probe-transition.py --build reports/kernel-entry-probe/2026-10-25-v23c/build.json --adt out/trial-boot/xnu-entry-probe-16/kernel.macho.adt --case normal --output out/NEW-transition.json
python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-16.json
```

构建/原始视频在本地，命令需对应out输入；不要覆写实机绑定报告。源码来源固定上游16e592ab、只读8796 pe_init.c与debug.h，精确源/补丁/函数SHA见source-policy.json。

恢复闭环补充：2026-10-25 16:44:29北京时间，Android完成1/A槽，boot_a/vendor_boot_a/init_boot_a三SHA与本轮preflight一致，无flash/erase/改槽；恢复等待已关闭。原图只在本地out；screen/trial报告仅存哈希与读数。本轮源补丁函数体编译不等于整核源码重建，后续必须保留此边界。
