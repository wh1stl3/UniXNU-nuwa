# STATUS

更新：2026-10-25。PROBE26于2026-10-25T23:11:09.500196+08:00仅一次临时boot ACK，代码5263bbb，镜像9906e2b7；等待用户菜单电源Enter后完整画面，尚无新阶段实测或Android恢复后验，不重复启动26或第二候选。已有连续推进授权及当前具体画面/恢复条件沿用，新鲜预检Android1/A槽/三SHA一致。重点A02E首个非零调用ID、A032原始返回和右侧240至263格点，按函数解释errno/Mach状态，不能把ACK作为内核证据。取图后trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-26.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v34/recovery.json；再record-nuwa-trial-state.py对比本轮preflight补postcondition。人工恢复等待继续离线工作；fastboot缺失变量保留日志重进一次，不单独硬停。启动证据v34/launch.json。

PROBE26原生exec/dyld路径错误定位版离线完成，21项串行回归全部通过：1052透明性、25Image4、6pthread、15边界/结果读回、7根输入、34绑定及入口/MMU/向量/显示回归；独立重建逐字节相同，实际FAT文件回读和旧包25复验通过。新鲜预检2026-10-25T23:09:47.274939+08:00确认Android1/A槽/三分区SHA与v33c后验一致。沿用用户本轮录像恢复确认、最新具体照片/fastboot确认及随后继续指令，条件未报告失效，按AGENTS连续推进不重复问是否继续；已取得单次ACK，尚无本轮内核画面。

权威包reports/xnu-first-entry/entry-probe-26.json，镜像out/trial-boot/xnu-entry-probe-26-paths/boot-xnu-first-entry.img，204484608字节，SHA256 9906e2b702e8123d729ad83b4d1c07bad2ec26daedc9f11f1424c4c8c025b895。内核d7f125b5d06fd4cc4b526dd04132adce276a3c6198efca2d8009e457b46c726c、58449920B，ADT4e45522907b9b08ae4172ad84103326383c03f3a0e625cd22d7afcbfb07ea34f；真实APFS d180c38d、192MiB运输和-v rd=md0保持。代码父74a5193，新milestone提交以git log为准，无push/新CI。

最近内核实测PROBE25：A02C2次尝试，实际激活A02D2和exec A0302均为ENOENT，尚无任务切换/签名/用户态。原图e7ffb6cc仅本地，22:55:01 +08 Android1/A槽/三SHA恢复闭环，本轮恢复后验待完成。主机只读确认正式launchd/dyld普通755且LC_LOAD_DYLINKER路径正确，开发/调试AppleInternal路径缺失；不能用此替代运行时路径证明。

新增240至263共12组实际BL/后继观察，覆盖exec_save_path、两处初始/后续namei、vnode_getattr/MAC/授权/读取、Mach-O激活/load_machfile及dyld的namei/授权/读取。A02E记录本次尝试首个非零调用ID、A032记录其原始返回，外层传播不覆盖首项；须按callee区分errno、Mach加载状态和内部控制返回。A02C尝试数、A02D/A030聚合返回保持；累计格点不是时序。原生调用/错误/认证不变，无新增成功终点，恢复用户态释放守卫保持。

下一步：不重复启动，菜单电源Enter后拍完整画面，含最右侧两列全部新增行与A02C/D/E/F/A030/A032。首个错误阶段必须结合函数和源码解释，不据未知值改认证。取图后固定原厂临时boot恢复Android1，再与v34/preflight比A槽/三SHA；恢复未确认不启动第二候选，人工恢复等待继续离线分析。

fastboot getvar反复unknown command / Variable Not found不单独硬停，保留日志，重进一次fastboot重试；必要目标/日志/恢复条件仍须确认。FD/shim、板内存/TCR、iOS16/8796身份、所有*_verified保持，loadable/runtime_qualified=false，无flash/erase/改槽或原始媒体上传。用户要求暂不调查重启现象，保持。

完整依据和命令见[本轮记录](operations/2026-10-25-v34-exec-paths.md)。
