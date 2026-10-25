# STATUS

更新：2026-10-25 22:20 +08。PROBE24连续exec候选离线完成，用户本轮录像/恢复就绪，新鲜预检Android完成1/A槽/三分区SHA与PROBE23后验相同。尚未启动24；最近实机为PROBE23，原生bsd_init已返回、PID1准备到首次init exec前，21:50:51 +08恢复闭环。

PROBE24取消旧exec前终点；挂载、BSD、exec、Mach-O激活、签名与错误回退均继续原生流程。唯一条件边界在原生已切换的新任务清除FINAL_WAIT前，阻止释放尚未审阅的恢复用户态。只读检查确认恢复根中restored_external的RunAtLoad=true；这不是自动擦除证明。真实故障则保留错误/panic。观察点不假返回、不跳过认证，不为成功阶段主动停止。

权威包reports/xnu-first-entry/entry-probe-24.json；镜像out/trial-boot/xnu-entry-probe-24-exec/boot-xnu-first-entry.img，204484608字节，SHA256 eed726b2406e4809196aefd03ee91a166bd0fbbde3eb749cc0dc25d83fcd935e。内核e8032e02eafb478837d61525c6b2c3ac8d257f65c6a8d50be40622604c6c6328，ADT3196efdee76507d8df099fc2d2a15697bd92f4ba0add02a907d428b4ebdb9db5；真实102MiB APFS d180c38d、192MiB FAT、-v rd=md0保持。最终build为reports/kernel-entry-probe/2026-10-25-v32b/build.json，初始v32候选不部署。

21项串行验证通过：956透明性差分、25 Image4、6 pthread、8条件边界、7根输入、34绑定及入口/MMU/向量/显示回归。独立重建逐字节一致，包24实际FAT回读及旧包23复验通过。主机只读恢复配置检查和卸载通过；未执行实际用户态。完整依据见[本轮记录](operations/2026-10-25-v32-native-exec.md)。

实机PROBE23照片624b4cda中110/111 BSD调用/返回、168/169安全根调用/返回、174/175 devfs、176/177 bootstrap均亮，214至216黄、217蓝/218品红，A02B217；不把安全根返回当密码学验证，不宣称Mach-O/AMFI或用户态通过。证据reports/xnu-entry-probe-trial/2026-10-25-v31/{screen,recovery,postcondition}.json。PROBE22曾实测原生挂载返回0。用户要求暂不调查重启现象，保持。

下一步：仅一次24临时boot，菜单电源Enter后保存完整画面，尤其最右侧220至239及字段。239品红/A02B239为恢复任务释放条件边界；激活零返回不独立证明exec成功。取图后绑定包24恢复固定原厂boot，补Android1/A槽/三SHA后验；恢复未确认不启动第二候选，人工恢复等待继续离线分析。

本轮预检reports/xnu-entry-probe-trial/2026-10-25-v32b/preflight.json，22:19:42 +08，用户原文“录像与恢复仍就绪，继续 PROBE24”。代码父a785eed，新里程碑以git log为准，无push/新CI。FD/shim/板内存/TCR/iOS16身份与所有*_verified不改，loadable/runtime_qualified仍false；无flash/erase/改槽、原始媒体上传。当前无恢复待办。
