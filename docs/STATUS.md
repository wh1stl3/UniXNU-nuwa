# STATUS

更新：2026-10-25。PROBE24照片683cc91b已保留本地，A02D/E仍未知哨兵、A02F=0，未证明激活/签名/任务切换或用户态成功；完整格点及exec返回码尚待逐项注册核对。用户已回fastboot，固定原厂临时boot恢复完成；后验2026-10-25T14:25:22.341342+00:00确认Android1/A槽/三SHA与试前一致，无待恢复，不重复启动24。代码7269f20、启动1b4fe71；本轮证据v32b/screen、recovery、postcondition.json。下一项分析真实exec停点，不按成功阶段停止，不放行未审阅恢复服务。

PROBE24取消旧exec前终点；挂载、BSD、exec、Mach-O激活、签名与错误回退均继续原生流程。唯一条件边界在原生已切换的新任务清除FINAL_WAIT前，阻止释放尚未审阅的恢复用户态。只读检查确认恢复根中restored_external的RunAtLoad=true；这不是自动擦除证明。真实故障则保留错误/panic。观察点不假返回、不跳过认证，不为成功阶段主动停止。

权威包reports/xnu-first-entry/entry-probe-24.json；镜像out/trial-boot/xnu-entry-probe-24-exec/boot-xnu-first-entry.img，204484608字节，SHA256 eed726b2406e4809196aefd03ee91a166bd0fbbde3eb749cc0dc25d83fcd935e。内核e8032e02eafb478837d61525c6b2c3ac8d257f65c6a8d50be40622604c6c6328，ADT3196efdee76507d8df099fc2d2a15697bd92f4ba0add02a907d428b4ebdb9db5；真实102MiB APFS d180c38d、192MiB FAT、-v rd=md0保持。最终build为reports/kernel-entry-probe/2026-10-25-v32b/build.json，初始v32候选不部署。

21项串行验证通过：956透明性差分、25 Image4、6 pthread、8条件边界、7根输入、34绑定及入口/MMU/向量/显示回归。独立重建逐字节一致，包24实际FAT回读及旧包23复验通过。主机只读恢复配置检查和卸载通过；未执行实际用户态。完整依据见[本轮记录](operations/2026-10-25-v32-native-exec.md)。

实机PROBE23照片624b4cda中110/111 BSD调用/返回、168/169安全根调用/返回、174/175 devfs、176/177 bootstrap均亮，214至216黄、217蓝/218品红，A02B217；不把安全根返回当密码学验证，不宣称Mach-O/AMFI或用户态通过。证据reports/xnu-entry-probe-trial/2026-10-25-v31/{screen,recovery,postcondition}.json。PROBE22曾实测原生挂载返回0。用户要求暂不调查重启现象，保持。

下一步：核对PROBE24完整格点、exec返回和原生指令，定位当前首进程执行阻碍并继续离线修复。239品红/A02B239仅为条件边界定义，本轮未宣称到达。距离系统启动画面仍需首个用户态成功执行、完整系统根/启动服务和显示接管三块工作；不能换算为固定试包数。

本轮预检reports/xnu-entry-probe-trial/2026-10-25-v32b/preflight.json，22:19:42 +08，用户原文“录像与恢复仍就绪，继续 PROBE24”。代码父a785eed，新里程碑以git log为准，无push/新CI。FD/shim/板内存/TCR/iOS16身份与所有*_verified不改，loadable/runtime_qualified仍false；无flash/erase/改槽、原始媒体上传。本轮照片已收到，恢复与三SHA后验已闭环。启动证据reports/xnu-entry-probe-trial/2026-10-25-v32b/launch.json。
