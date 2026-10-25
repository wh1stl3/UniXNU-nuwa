# STATUS

更新：2026-10-25 22:59 +08。PROBE25实机A02C=2（两次exec尝试），A02D=2且A030=2（最后原生激活和exec返回ENOENT），A02E未知/A02F0，未到任务切换、签名或239恢复任务释放守卫。原图e7ffb6cc仅本地。22:55:01 +08后验确认Android1/A槽/三SHA与试前一致，恢复关闭。主机只读复核正式/sbin/launchd与/usr/lib/dyld均为普通755文件，launchd声明的加载器正是/usr/lib/dyld且存在；开发/调试AppleInternal路径不存在。不能把ENOENT直接归为正式文件缺失或据此放宽认证；下一步定位原生namei、镜像激活及dyld查找的首个错误。

最近包25镜像8e24773c3811f267b36272abf04a030d0fd2adfa5f5a15340d1cb8fbe8b5b655，204484608B；内核52dd89529567caa552c690f11de2f20cd701bde60027c2868b46364cef8489db，ADT f9e3e90956fda7a5713022295e09d50bad88383112726df9e2eeb31ecefe4461。代码d65c2b4、启动bc7f0cf。21项串行回归、独立逐字节重建、实际FAT回读及旧包24复验通过，不等于用户态运行。证据v33c/{screen,recovery,postcondition}.json；主机路径/权限/LC_LOAD_DYLINKER检查为v34/exec-files.json，已卸载，无设备写入。

此前实机已到原生根挂载返回0、BSD初始化返回和首进程准备；25已执行真实exec但返回ENOENT。未知最终错误来源不能用虚构路径、强制成功、绕过认证或复制同机型身份解决。继续原生流程，不为成功阶段停止；只在真实故障、明确硬停或未授权设备内容更改边界停止相关动作，恢复用户态释放守卫保留。

用户新规则已写AGENTS §3：fastboot getvar多次unknown command / Variable Not found本身不硬停，保留失败日志，重进一次fastboot后重试；不把缺失变量当确认值。目标设备/具体日志/恢复及内存身份等既有边界不变。当前无待恢复，最近设备证据22:55:01 Android1；不重复启动25。人工等待继续离线工作。

当前推进原生路径错误定位；下一包尚未完成，不提前启动。FD/shim、真实APFS d180c38d、192MiB运输、-v rd=md0、板内存/TCR、iOS16/8796身份和*_verified不变，loadable/runtime_qualified=false。无flash/erase/改槽、push/新CI或原始媒体上传。详见operations/2026-10-25-v33-exec-errors.md；本轮milestone提交以git log为准。
