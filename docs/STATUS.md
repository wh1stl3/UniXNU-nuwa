# STATUS

更新：2026-10-25 22:51:47 +08。PROBE25于2026-10-25 22:51:47 +08仅一次临时boot ACK，代码d65c2b4，镜像8e24773c。等待用户菜单电源Enter后完整最终画面，ACK不证明内核或exec进展；本轮Android恢复后验尚未取得，不重复启动25、不启动第二候选。用户本包录像/恢复就绪，22:50:05预检Android1/A槽/三SHA一致。取图后trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-25.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v33c/recovery.json；再用record-nuwa-trial-state.py对比本轮preflight补postcondition。人工恢复等待继续离线工作；真实故障、明确硬停或未授权设备内容更改边界仍停止相关动作。启动证据v33c/launch.json。

PROBE25连续exec错误保留版离线完成，21项串行回归通过：956透明性、25Image4、6pthread、12条件边界与像素解码、7根输入、34证据绑定及入口/MMU/向量/显示回归。独立重建逐字节一致，新包实际FAT回读和旧包24复验通过。用户“PROBE25 录像与恢复就绪”；22:50:05 +08预检Android1/A槽/三SHA与v32b后验一致，已取得单次启动ACK，尚无新内核画面。

权威包reports/xnu-first-entry/entry-probe-25.json，镜像out/trial-boot/xnu-entry-probe-25-exec/boot-xnu-first-entry.img，204484608字节，SHA256 8e24773c3811f267b36272abf04a030d0fd2adfa5f5a15340d1cb8fbe8b5b655。内核52dd89529567caa552c690f11de2f20cd701bde60027c2868b46364cef8489db、ADT f9e3e90956fda7a5713022295e09d50bad88383112726df9e2eeb31ecefe4461；真实102MiB APFS d180c38d、-v rd=md0和192MiB运输不变。最终build为v33c/build.json，初始v33/v33b不部署。

PROBE24完整右侧格点确认220黄、223蓝/224绿、225蓝/226绿；227至232暗；233/235蓝、234/236/238绿、239暗，219绿。清理后继可能有其他前驱，累计格点不提供顺序或次数；未证明task switch、签名或恢复用户态释放守卫已触发。A02D/E未知、A02F0与激活后继同时出现，原生最终errno未确认。首要调查方向为原生激活错误/回退，不能直接认定所有launchd缺失，旧只读证据已见正式launchd和dyld。原图683cc91b仅本地out；v32b/screen-registered.json为本轮补录，不能以未知哨兵当errno。

PROBE25无条件记录原生激活/exec/签名后继的x0，A02C为exec尝试数；仅首次初始化未知显示，后续保留上一笔完成结果。任务切换调用和返回处重新建立跟踪并记录实际新任务，匹配已切换任务的FINAL_WAIT=2才守住尚未审阅恢复用户态释放；原生错误、认证及回退均保留，不新增阶段终点。固定源、指令、测试局限见[本轮操作记录](operations/2026-10-25-v33-exec-errors.md)。

最近设备已知状态：PROBE24后22:25:22 +08 Android1/A槽/三SHA恢复闭环，本轮22:50:05预检再次相同，本轮恢复待完成。最近内核实测仍24，不声称25已运行或用户态已通过。不重复临时boot；菜单电源Enter后保存完整画面，含右侧两列和A02C/D/E/F/A030。取图后固定原厂临时boot恢复Android1，再与本轮preflight比A槽/三SHA；恢复未确认不启动第二候选，人工等待继续离线分析。

代码父b0704b5，新里程碑以git log为准；无push/新CI，保持FD/shim/板内存/TCR/iOS16/8796身份和*_verified不变，loadable/runtime_qualified仍false。无flash/erase/改槽和原始媒体上传。用户要求暂不调查重启现象，保持。硬停规则未因平台弹窗或连续推进而放宽。
