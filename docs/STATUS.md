# STATUS

更新：2026-10-26。用户已允许既定nuwa PROBE28实测，解除此前一般设备暂停。本轮已完成新鲜只读预检，尚未临时启动或消费候选；仅待菜单Enter后的具体画面拍摄及必要时按键恢复的当轮确认，针对性问题已发送。R-014保持open，不是权限拒绝。

2026-10-26T04:01:35.029989+00:00确认nuwa/kalama、Android完成1、_a，三分区SHA与v35恢复后验相同。有效包7a04626e和原恢复boot ef558db2哈希校验通过，现有试验记录未发现PROBE28已启动。本轮没有改变设备状态，没有新的实测画面或恢复后验；不能把只读预检当内核通过。

混接其他设备时工具原默认会遍历身份，本轮增加--serial仅选nuwa；实际读取均明确指定nuwa，未向其他设备发查询/操作。混接及所选设备缺失的3项隔离测试通过。记录见[当轮预检](operations/2026-10-26-probe28-preflight.md)与reports/xnu-entry-probe-trial/2026-10-26-v36/。后续preflight/launch/recover必须指定本轮nuwa目标；过期时刷新预检。

c302451离线参数契约成果保留：9组flags8/4096对照、4组实际EFI存储、2负对照；模拟夹具memSizeActual改为Darwin22/0x2d8后启动模型5项通过，默认11组逐字节保持，原23份绑定报告保持。[参数契约及限制](operations/2026-10-26-read-parameter-contract.md)。这是静态/Unicorn检查，不是真实MAC/APFS/decmpfs执行。

PROBE28镜像未改：reports/xnu-first-entry/entry-probe-28.json；包7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f，204484608B；内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07；ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0。旧a8cb包禁用，PROBE27不重启。最早实机卡点仍是250到达/251未观察，A033 FFFFFFF005F48EF8只证明类型4表项。

下一步：当轮观测/恢复条件满足后取带真实确认原文的新preflight，按原门禁单次临时boot同一PROBE28，菜单电源Enter后观察266..275/A034/A035；然后恢复Android1/同槽/三SHA后验。权限/认证、239、内存/TCR/身份/_verified门保持，不自动换包或扩大刷写。历史28项未跟踪保留，无push/媒体上传；唯一最新交接：[10月26日主线交接](operations/2026-10-26-mainline-handoff.md)。
