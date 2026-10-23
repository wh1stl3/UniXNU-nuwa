# MMU 分支诊断包验收

时间：2026-10-23T21:18:05.100423+08:00。用户要求的0012独立profile、CI构建和诊断包核验已完成；本轮无设备操作。

## 固定输入与构建

- 设备提交：ee98dfe6c0263d17741c45327383791c26bd51c8。
- 固件提交：ddd794fc07e9bc64057222a9bffa4d79c8553af8；Mu：cfb93724a06ff86ff5ba971413368a7809ee42a5。
- CI：https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39958974666，构建与实际固件检查均success。
- profile：config/firmware-mmu-branches-profile.json。0012排在0011后，39项输入保持，只替换ArmMmuLibCore.c唯一post-patch pin为704ba022。
- scripts/check-mmu-branches.py通过39输入/补丁哈希和日志删除后逐字节还原父源码检查。

## 实际产物

| 产物 | 大小 | SHA256 |
| --- | --- | --- |
| v4诊断包 | 3153920 | 2b203afa8372e99ebd9049b276c41984fa16db4d92a92a6cea0f3b4904c403dd |
| FD | 3145728 | ea0277e8087b036c062866388a67fd75a9cf24f61cb0de0bc2132bc7f2243227 |
| BootShim | 112 | 8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462 |

原包路径：`out/trial-boot/mmu-branches-39958974666/boot-mmu-branches-v4.img`。完整下载在out/firmware-ci/39958974666/nuwa-firmware-39958974666。
静态检查核对666项inventory，实际SEC内5条MMU、8条CTOR、4条HANDOFF全部存在；原SEC/DXE日志、四模块、PCD/DEPEX、PIL及空AUTO通过。
R-011全部41行内存描述符/2952字节完全一致，表SHA7694de6cf91ac305c82b3a2a82ad717a3155f88d59a185093a2a74a1a42bbdda。
原厂v4头只改kernel_size，整头+shim+FD+零填充重新构造一致；没有FAT、ADT、XNU、ramdisk或附加DTB。

## 验证与实机前门

更新后的严格验证通过新包及旧constructor包回归。tests/test_mmu_branches.py五项离线测试通过：旧FD改profile不能冒充新日志；不能省略基线检查；录像确认不能为空；填充篡改即使同步改hash仍被拒绝；缺preflight或录像确认在任何设备子进程前拒绝。测试只在内存中mock，不改历史证据或镜像。

打包scope为MMU-BRANCHES-OFFLINE，ready_to_execute=false。新preflight需要`--capture-confirmation`传入用户本轮实际确认，空白拒绝；launch接受本轮非空原文而不要求用户逐字复述旧确认。工具修改不改变本轮CI固件输入。
实机前先通知用户准备录像，再刷新真实nuwa身份、Android状态、三分区哈希和恢复路径；本轮未运行adb/fastboot。

判读顺序：after-guid-query表示查询返回；HOB分支前后界定函数指针读取；before/after-cache界定缓存维护调用。缺after-cache仍不能单独判定dc、DSB或日志故障。共享库日志影响其他消费者及时序；编译/静态通过不是实机通过。

证据：reports/mmu-branches/39958974666/的ci-run.json、ci-artifacts.json、artifact-inspection.json、memory-table.json、package.json、validation.json。原始workflow日志保留out/firmware-ci/39958974666/workflow.log。
