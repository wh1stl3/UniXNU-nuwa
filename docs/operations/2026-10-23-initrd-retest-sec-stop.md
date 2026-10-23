# R-011 原包定向复测：最后可见SEC平台HOB成功

用户“人已就位 可以开始实机验证了”授权后，重新只读确认nuwa/kalama、Android完成1、A槽和三分区SHA；原Android恢复输入完整SHA及候选8e852150匹配。启动前明确通知20秒后开始并请全程录像，沿用用户既有可拍摄日志承诺；本次仅同一包一次临时启动，无flash/erase/改槽。

本次证据位于 `reports/initrd-retest/2026-10-23-noon/`。fastboot Sending3080KB/Booting均OKAY只作命令接受证据，不据此声明SEC/DXE通过。

## 实机照片与阶段归属

用户先报告“停在了nuwa entry platform-hobs status success”，随后提供原始照片。照片6699911B，SHA25647637c0e2b45f9f21e3c67464437231cab66d8060c3bc3106d8377aa10914211，保存在sec-last-screen.jpg，未裁剪/增强/改写。

可读文字包括：C-before-platform、C-after-platform、memory status=Success、before-platform-hobs，以及末行`[NUWA-ENTRY] platform-hobs status=Success`；多处x0可读为0xB5DB1000。banner为Oct 22 2026 /18:47:10，已与**本次固定实际FD解包的SEC TE字符串**对应，避免仅凭照片日期误认其他固件。该指针只是本次运行观测，不写入板配置。

未取得before-fv-decompress、DXE、SHENGMEM或菜单的本轮证据。上午用户明确观察的UniXNU菜单仍保留为独立那次到达证据；不能将本次照片倒写为上午未运行，也不能用上午菜单补足本次运行缺失。相同包的阶段到达尚不稳定，原因未定位。

固定源码1ccf760的Sec.c:123-144中，PlatformPeim返回后打印该行；到下一条before-fv-decompress之间依次有BuildGuidDataHob和ProcessLibraryConstructorList。因此只能把后续检查优先缩小到入口参数HOB创建、构造函数及日志可见性，**不能由最后一行独断为解压失败、initrd出错或某个函数必然卡死**。需要实际SEC指令与库依赖审查后再加细诊断。

## 恢复与后置条件

已通知保留画面后按电源+音量下回fastboot，用户回复“已回 fastboot”。恢复等待脚本识别nuwa、复位bootloader后只临时加载原boot ef558db2，Sending196608KB 4.488s、Booting0.117s OKAY。12:18:42（Asia/Shanghai）命令确认nuwa/kalama Android boot_completed=1，随后postcondition记录三个分区SHA与本次preflight完全相同。

没有第二次候选启动。H-007录像配合完成，但SHENGMEM目标行因阶段未到达而仍未取得。用户后续要求继续离线分析；下一项为实际SEC/link-map反汇编、PrePiHobLib及真实构造函数依赖审查，不操作设备。
