# v33 / PROBE25：保留原生 exec 错误并连续推进

## PROBE24实际证据

原图仅本地 out/trial-evidence/entry-probe-24/user-screen.jpg，SHA256 683cc91b265592424d9af2eb83c144027021ce65b31cd031a1bc0e1011acb7e6，3072×4096，10661351字节。使用原始像素注册右侧两列：220中心(2264,506)，列距55、行距27.4像素，各9×9像素中位数；对应固定build中的1320/1368与256起24行距。220黄；221/222暗；223蓝、224绿；225蓝、226绿；227至232暗；233蓝、234绿；235蓝、236绿；237暗、238绿；239暗。主面板219绿需要与同址其他前驱共同解释，不能仅凭后继亮宣称调用成功。

静态指令依据为固定输入1aeebf13、源码xnu-ios16-full提交1b191cb58250d0705d8a51287127505aa4bc0789、kern_exec.c SHA d6c064ee0c954db395d865e3265f6aa319e0908bb7e243e48bfe004298e96af1。0xfffffff00769cfac保存激活返回x0到x24；cfb4/cfb8检查/获取新任务后，cfc4仅当w24=0进入任务切换路径d0c0。本轮尚未观察任务切换/签名，也未触发239释放守卫。部分清理后继有原生跳转前驱，238亮而237暗不代表task_terminate调用已执行。

首要调查方向是首进程exec的激活错误/原生回退；不能从累计格点推出最终停在某一调用，也不能把未知哨兵FFFFFFFFFFFFFFFF解释成原生errno。候选原因包括DEVELOPMENT默认AppleInternal launchd路径不存在后的回退，以及正式/sbin/launchd的加载错误；旧只读报告已确认/sbin/launchd和/usr/lib/dyld存在，因此“所有launchd均缺失”不符合现有主机证据。具体文件查找、Mach-O/签名错误或等待尚须真实errno及尝试计数区分，不先修改认证策略。

原图A02D/E为未知哨兵、A02F=0，与激活后继已亮并存。直接连续执行观察hook的模型能够保持状态并渲染errno2，不能据此声称实机状态相同。下一包消除诊断盲区：真实后继的x0无条件写屏；新尝试不擦去上一笔已完成的错误；A02C记录exec尝试次数。该变化不改变原生返回值、不跳过检查、没有新增成功终点。

PROBE24固定原厂临时boot恢复完成，22:25:22 +08后验Android1/A槽/三SHA与试前相同；v32b/recovery.json和postcondition.json，无待恢复。用户要求暂不调查重启现象，保持。

## 新候选设计和检查

exec_trace_sites.py冻结为v32，v33独立模块exec_trace_v33.py固定其SHA并复用原生调用核对。原生任务切换调用/返回处重新建立active跟踪并捕获真实新任务，释放守卫仍要求实际切换返回、任务匹配和FINAL_WAIT=2；不依赖cloneproc之前的active位一直保留。独立nuwa_exec_detail_launch_context.py固定根生产器，明确测量此策略，不破坏旧包24的策略及复验。A02D仍为实际激活返回、A030实际exec返回；A02C为尝试计数。只在第一次尝试初始化未知显示，后续保留已完成结果；不能混淆不同尝试的累计格点与最后一次返回。

条件边界回归保留8项，新增4项实际hook执行和像素解码检查：跟踪状态为0仍显示真实激活/exec返回；第二次尝试保留已完成结果并递增计数；active初值为0仍在原生任务切换调用处建立跟踪并记录x3任务。共12项通过。它们不执行真实exec函数体，不证明实机首进程运行。最终权威候选为v33c/build.json，内核52dd89529567caa552c690f11de2f20cd701bde60027c2868b46364cef8489db、58433536字节。初始v33/v33b不部署；v33b透明性回归由代理主动中止以补强守卫，非通过也非实机故障，原始失败执行记录保留。完整串行回归、独立重建和实际包回读完成后才安排一次临时boot。

保持真实APFS、-v rd=md0、FD/shim、板内存/TCR、iOS16/8796身份和*_verified不变；不启动未审阅恢复用户态、不flash/erase/改槽，不push/新CI或上传原始媒体。后续继续原生exec及所有成功阶段，真实故障/明确硬停边界才停止相关动作。

## 离线完成与设备门

PROBE25连续exec错误保留版离线完成，21项串行回归通过：956透明性、25Image4、6pthread、12条件边界与像素解码、7根输入、34证据绑定及入口/MMU/向量/显示回归。独立重建逐字节一致，新包实际FAT回读和旧包24复验通过。用户“PROBE25 录像与恢复就绪”；22:50:05 +08预检Android1/A槽/三SHA与v32b后验一致，尚未启动25。

权威包reports/xnu-first-entry/entry-probe-25.json，镜像out/trial-boot/xnu-entry-probe-25-exec/boot-xnu-first-entry.img，204484608字节，SHA256 8e24773c3811f267b36272abf04a030d0fd2adfa5f5a15340d1cb8fbe8b5b655。内核52dd89529567caa552c690f11de2f20cd701bde60027c2868b46364cef8489db、ADT f9e3e90956fda7a5713022295e09d50bad88383112726df9e2eeb31ecefe4461；真实102MiB APFS d180c38d、-v rd=md0和192MiB运输不变。最终build为v33c/build.json，初始v33/v33b不部署。

PROBE24完整右侧格点确认220黄、223蓝/224绿、225蓝/226绿；227至232暗；233/235蓝、234/236/238绿、239暗，219绿。清理后继可能有其他前驱，累计格点不提供顺序或次数；未证明task switch、签名或恢复用户态释放守卫已触发。A02D/E未知、A02F0与激活后继同时出现，原生最终errno未确认。首要调查方向为原生激活错误/回退，不能直接认定所有launchd缺失，旧只读证据已见正式launchd和dyld。原图683cc91b仅本地out；v32b/screen-registered.json为本轮补录，不能以未知哨兵当errno。

PROBE25无条件记录原生激活/exec/签名后继的x0，A02C为exec尝试数；仅首次初始化未知显示，后续保留上一笔完成结果。任务切换调用和返回处重新建立跟踪并记录实际新任务，匹配已切换任务的FINAL_WAIT=2才守住尚未审阅恢复用户态释放；原生错误、认证及回退均保留，不新增阶段终点。固定源、指令、测试局限见[本轮操作记录](operations/2026-10-25-v33-exec-errors.md)。

最近设备已知状态：PROBE24后22:25:22 +08 Android1/A槽/三SHA恢复闭环，本轮22:50:05预检再次相同，无待恢复。最近内核实测仍24，不声称25已运行或用户态已通过。下一步仅一次25临时boot；菜单电源Enter后保存完整画面，含右侧两列和A02C/D/E/F/A030。取图后固定原厂临时boot恢复Android1，再与本轮preflight比A槽/三SHA；恢复未确认不启动第二候选，人工等待继续离线分析。

代码父b0704b5，新里程碑以git log为准；无push/新CI，保持FD/shim/板内存/TCR/iOS16/8796身份和*_verified不变，loadable/runtime_qualified仍false。无flash/erase/改槽和原始媒体上传。用户要求暂不调查重启现象，保持。硬停规则未因平台弹窗或连续推进而放宽。

命令入口：build-kernel-entry-probe.py --image4-launch --pthread --root-trace --exec-trace --exec-detail；verify-image4-entry-candidate.py绑定v33c/build与launch-guard实际ADT/nonce/manifest，21项串行命令及原始输出见v33c/execution.json。独立重建v33c/reproduce.json，实际FAT读回及旧24复验用build_xnu_boot_package.py --validate。nonce仅本地，不提交原始值。
