# MMU 分支诊断构建

用户要求接入0012独立profile/CI，构建核验诊断包，实机测试前再通知。

## 配置和静态检查

独立profile为`config/firmware-mmu-branches-profile.json`，固定固件ddd794f与Mu cfb93724。
0012排在0011后，39项原始输入保持；只替换ArmMmuLibCore.c唯一post-patch pin为704ba022。
`scripts/check-mmu-branches.py`逐项核对39项来源和补丁哈希，五条日志删除后逐字节还原父源码。
不跳过cache同步、不伪造HOB、不改内存表/board/feed/验证标记；共享库其他消费者亦受日志影响。

CI新增mmu-branches选项和真实产物检查步骤，检查5条MMU、8条CTOR、4条HANDOFF及既有SEC/DXE/PIL/模块/PCD/DEPEX/BootShim。
打包和严格scope新增MMU-BRANCHES-OFFLINE；独立preflight要求新鲜用户录像确认。
旧constructor包530f56b4通过更新后的严格验证回归。新产物尚待CI，静态通过不代表编译或实机通过。

## 后续验收

CI成功后下载全部产物，检查inventory及实际SEC，比较R-011全部41行/2952字节内存表，再重建v4容器。
完成后保持ready_to_execute=false；不执行adb/fastboot，等待用户实测安排。
