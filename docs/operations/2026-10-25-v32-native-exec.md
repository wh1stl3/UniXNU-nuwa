# v32 / PROBE24：连续执行真实exec、激活和签名

## 当前目标与依据

用户要求“之后都要连续推进”“触发硬停再停”。本候选移除PROBE23的首次exec前终点，不新增成功阶段终点。挂载、BSD、PID1、exec入口、镜像激活、任务切换、签名、错误回退继续原生执行，观察点只记实际结果。

最近实机仍PROBE23：bsd_init110/111调用/返回，214–216首进程准备、217蓝/218品红，A02B217，未执行___mac_execve；21:50:51 +08 Android1/A槽/三SHA后验一致，无待恢复任务。用户此前要求暂不调查重启现象，保持该要求。

## 实际设备内容更改边界

只读主机挂载固定APFS d180c38d检查到System/Library/LaunchDaemons/com.apple.restored_external.plist，SHAac190dd86eb7c5dec961559d355eec55fcb55b6826113de5327f8974884c0bf9：ProgramArguments=/usr/local/bin/restored_external，RunAtLoad=true。记录reports/kernel-entry-probe/2026-10-25-v32b/restore-policy.json，挂载已卸载。它证明该程序会由恢复用户态启动，不证明本轮已经还原/擦除设备，也不以一般iOS推进授权放行恢复/写盘服务。

固定XNU1b191cb58250d0705d8a51287127505aa4bc0789的kern_exec.c（SHAd6c064ee0c954db395d865e3265f6aa319e0908bb7e243e48bfe004298e96af1，APSL-2.0）说明：exec会创建新任务/线程，exec_activate_image可能在不可回退失败后仍返回0；随后proc_exec_switch_task切换、process_signature检查，最后清除新任务的FINAL_WAIT以放行新线程。不能在___mac_execve返回后才阻拦，因为新线程已可能被释放。

唯一边界因此在___mac_execve内部0xfffffff00769d230调用task_clear_return_wait之前，且只在：本次init exec已进入、原生任务切换已返回、x0匹配调用proc_exec_switch_task时x3传入的新任务、w1=2（TCRW_CLEAR_FINAL_WAIT）时守住。INITIAL_WAIT=1、未提交失败任务、其他任务/非本次exec都继续；旧exec前点和错误返回点不停止。osfmk/kern/task.h定义两个实际标志，native CALL目标由原始指令核对。源脚本exec_trace_sites.py及其SHA绑定进build报告。

该边界不是成功里程碑；它阻止进入尚未授权的恢复用户态。若真实故障在前面发生，保留原生错误/panic，不假返回，不跳过AMFI，不额外设置阶段终点。达到该边界后须按AGENTS对正常系统root/恢复用户态执行范围做实质审查，不能自动放行写盘服务。

## 观察与输入

最终候选权威build为reports/kernel-entry-probe/2026-10-25-v32b/build.json；初始v32离线候选保留，不部署。最终内核e8032e02eafb478837d61525c6b2c3ac8d257f65c6a8d50be40622604c6c6328，58,433,536B；ADT3196efdee76507d8df099fc2d2a15697bd92f4ba0add02a907d428b4ebdb9db5。根APFS、192MiB运输、FD/shim、1GiB窗口、板值/TCR、iOS16/8796身份不变。

旧0–217标记不变，218蓝表示exec前观察后继续，219绿为真实___mac_execve返回。右侧新面板x1320/1368，两列、y256起24像素行距，仅行跨度>=5760时绘制，最大像素仍在1440x800安全区。220=___mac_execve入口；221/222 MAC入口，223/224 cloneproc，225/226激活，227/228任务切换，229/230IPC，231/232签名，233/234初始等待清除，235/236最终等待调用/后继，237/238旧任务终止。239品红/A02B239表示真实恢复任务释放边界被守住，不代表exec成功。

exec阶段字段复用：A02D=实际激活返回，A02E=实际签名返回，A02F=观察到任务切换，A030=实际exec返回，A032=MAC入口返回；A035仍为挂载返回。每次原生exec尝试将未完成值重置FFFFFFFFFFFFFFFF，任务切换值重置0，避免沿用旧WFE或前次尝试数据。若出现panic，按panic布局优先解释其覆盖数据，不将同名旧字段机械解释为errno。仅零激活返回不足以声明成功。

冻结旧生产器与策略，新nuwa_exec_launch_context.py在独立命名空间使用固定根测量实现，明确绑定真实根、参数及条件边界，不破坏22/23旧包复验。8项独立模型检查覆盖普通/未提交/不匹配/INITIAL_WAIT放行、匹配提交任务守住、有无视频、exec前继续和错误返回继续；不执行或伪造真实exec函数体。所有普通hook纳入透明比较，不再无条件豁免exec点。

## 验证与设备门

完整串行验证v32b/execution.json的21项任务全部通过：956透明性、25Image4、6pthread、8条件边界、7根输入、34绑定及既有回归。v32b/reproduce.json独立重建逐字节相同；包24实际FAT回读和旧包23复验通过。包24镜像SHA256 eed726b2406e4809196aefd03ee91a166bd0fbbde3eb749cc0dc25d83fcd935e，204484608字节。无本包实机结果，不把模型或主机APFS检查当作签名/用户态执行证据。loadable/runtime_qualified和*_verified保持false，无flash/erase/改槽、push/新CI/原始媒体上传。

用户已授权连续推进；实际启动前核对具体日志/恢复条件并刷新preflight对比v31/postcondition，即时通知后仅一次临时boot。需保存完整屏幕包括最右侧两列、阶段标签/错误字段。取图后固定原厂boot恢复，Android1/A槽/三SHA后验通过前不启动第二候选，人工恢复等待不阻断离线工作。

22:19:42 +08新鲜preflight确认Android1/A槽/三SHA与v31后验一致；用户“录像与恢复仍就绪，继续 PROBE24”。权威包reports/xnu-first-entry/entry-probe-24.json。复验命令：build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-24.json；对包23同样复验。正式只读策略审计audit-restore-userland-policy.py在WSL使用/var/tmp/unixnu-nuwa-restore-policy-v32，报告v32b/restore-policy.json且确认已卸载。
