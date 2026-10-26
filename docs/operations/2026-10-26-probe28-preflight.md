# PROBE28 当轮预检与目标隔离

## 当前实测准备（2026-10-26）

用户最新明确“nuwa可以开展实测了”，解除此前设备操作暂停，范围仅既定PROBE28单次临时启动及安全恢复；没有授权无关刷写/改槽/换包。有效包7a04626e校验通过，现有仓库试验记录未发现已启动该包。

本轮新鲜只读状态：2026-10-26T04:01:35.029989+00:00，nuwa/kalama、Android完成1、_a，boot_a/vendor_boot_a/init_boot_a三SHA均与v35后验一致。证据reports/xnu-entry-probe-trial/2026-10-26-v36/state-before-confirmation.json。尚未临时启动，未消费候选；当前状态不能写为PROBE28实测通过。

USB清单存在其他设备，本轮仅按明确选中的nuwa serial执行身份/Android/槽位/三SHA读取，没有向其他设备发送查询或状态命令。给record-nuwa-trial-state.py和trial-v4-firmware.py添加--serial目标筛选，外来设备混接/所选设备缺失的3项隔离测试通过；记录中不持久化序列号。后续preflight/launch/recover均必须传本轮选定nuwa目标，不使用自动遍历其他设备的默认路径。

R-014仍缺本轮菜单Enter后的拍摄/读取与按键恢复确认；已发出只针对这两个必要条件的问题，等待答复。不是再次询问一般实测授权。条件明确后才生成带真实确认原文的新preflight；若超时先刷新Android/三SHA。候选未启动时不执行无必要恢复或回刷。下一步仍为同一PROBE28的266..275/A034/A035观测，原日志/恢复/239/verified/权限门保留。
