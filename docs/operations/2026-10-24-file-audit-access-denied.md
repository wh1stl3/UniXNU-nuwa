# 文件探针实测：外部EFI返回Access Denied

本轮唯一候选18ebd838，证据reports/file-read-audit-trial/2026-10-24-01/。用户本轮确认录像后，实际preflight确认nuwa/kalama/Android完成1/A槽和三分区旧基线；即时通知后单次临时启动，ACK=0，USB观察120.0秒。用户随后提供完整菜单原图，screen-observation.json记录SHA和固定构建审计。

## 已确定的结果

原图显示新标题NUWA FILE SHA PROBE、Read 58 MB条目，以及明确的`returned: Access Denied`。因此该条目已经被尝试启动并返回，并非仍等用户选中。此前让用户寻找Enter的判断不准确：该照片出现后应停止重复菜单操作，转入失败定位。没有本轮app enter/actual SHA/PASS画面，不能称文件SHA实机通过，也不能断言文件已经被读到。

新配置已能被读取，不支持把该报错归为旧的ramdisk运输缺卷。上一轮独立64MiB封装/FAT实测证据继续有效。本轮没有实测XNU/ADT/OS执行。

## 首因排序和公开机制

**外部未签名EFI被固件镜像认证拒绝是当前首因，置信高；具体拒绝API未直接记录。** 支持证据不是仅凭错误名：

1. 固件实际CI40014018074/build-settings为ENABLE_SECUREBOOT=1；实际BUILD_REPORT中SecurityStubDxe链接DxeImageVerificationLib及其constructor，非仅存在于源码中。
2. 实际固定/可移动介质PcdImageVerificationPolicy均为0x04。固定Mu源码将0x04定义为DENY_EXECUTE_ON_SECURITY_VIOLATION，未认证路径可返回EFI_ACCESS_DENIED。外部RAM卷也可能归为unknown来源，其默认同为拒绝策略。
3. 本次实际6144B EFI PE的certificate table offset/size均为0，无Authenticode签名。完整QEMU使用普通QEMU_EFI，其加载/验签环境并未等同于nuwa；上一轮验证遗漏了这个环境差异，QEMU的PASS不能推出nuwa认证允许。

备选：应用已进入但某个底层文件服务返回Access Denied；其他Security2/StartImage策略拒绝。反对/限制：本轮只有菜单汇总状态，没有LoadImage/StartImage的原始返回点、runtime SecureBoot变量，也没有完整连续视频文件；固定库在SecureBoot缺失/禁用时可跳过验证，所以不能仅由编译开关声称运行时变量必为1。首因是明确工程判断，不冒充完整调用栈实测。

公开原始实现[EDK2固定版本DxeImageVerificationLib.c](https://github.com/tianocore/edk2/blob/edk2-stable202208/SecurityPkg/Library/DxeImageVerificationLib/DxeImageVerificationLib.c)解释未认证拒绝机制；真正用于本次判断的是实际Mu cfb93724固定源码和实际构建报告，SHA/行号在screen-observation.json，不把公开同类版本当作nuwa运行时证明。

## 后续具体方向

不重复启动同一无签名外部应用，不要求键盘，不把关闭Secure Boot或放宽验证policy当作默认修复。先离线准备保持认证策略的诊断入口：候选A将相同只读检查核心作为独立诊断profile的固件内模块，由既有固件启动链调度，继续只读外来FAT；候选B补齐外部EFI在既有信任链中的签名资格并精确记录LoadImage/StartImage状态。A更便于保持策略并取得早期日志，但需要新固件构建和重新验证SEC/Heap/HOB不变；B需要已有可信签名来源，不能假造、输出或擅改信任变量。当前倾向A，尚未实现/构建，不宣称新包已就绪。

最小证伪：新诊断入口能进入并通过文件SHA，而外部同文件加载仍被拒绝，则支持认证分层；若内置检查亦失败，按真实阶段状态重排。加入明确enter/read/hash状态并保留画面，不再让菜单汇总返回码承担所有定位信息。Heap/HOB坏链保护/缓存维护/板内存/身份/_verified不改。

## 恢复和当前边界

已通知用户保存画面后回fastboot；recover实际临时加载固定原厂v4 boot，Android恢复完成。postcondition.at=2026-10-24T08:14:06.606976+00:00（北京时间16:14:06），nuwa/kalama、完成1、槽_a及boot_a/vendor_boot_a/init_boot_a三SHA与试前一致。恢复待办关闭，无需再按键，无第二候选、无flash/erase/改槽位。旧build/runtime=false元数据不修改，实际本轮失败单独留档。
