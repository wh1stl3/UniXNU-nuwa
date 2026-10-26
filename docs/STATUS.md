# STATUS

更新：2026-10-26。PROBE28已单次实测、读图及Android恢复闭环，候选consumed，禁止重发；未启动下一候选。

原图A034=0x110/272、A035=FFFFFFFFFFFFFFFF；266/268/270/272青，269绿，267/271/273及274/275未亮。已观察MAC成对返回，读取推进到VNOP_READ内原生BLR x8调用点，未观察分派返回。272在BLR之前记录，不能单独证明目标函数体入口执行；优先调查分派/目标入口及APFS/decmpfs读路径，不能指定某把锁或IRQ为根因。未证明完整header、解压、Mach-O/dyld或用户态成功。[实测判读及边界](operations/2026-10-26-probe28-device-result.md)。

12:24:07上海时间，postcondition确认nuwa/kalama、Android boot_completed=1、_a，boot/vendor_boot/init_boot三SHA与本轮新preflight完全相同。原boot临时恢复完成，未flash/erase/改槽、未操作enuma。R-014本轮观测/恢复已满足并闭环，当前无人工恢复待办。证据reports/xnu-entry-probe-trial/2026-10-26-v36/的screen、recovery、postcondition、evidence-binding.json。

原图710443B、SHA8b25519f7eb803bf101cb96ba6d2f83befe5b575a071aa2b5ccd4b4eb9bb70df及Library身份元数据仅保留本地out归档，未上传/commit原始媒体。A033本图不作不可靠转录，先前EF8用户更正历史保留。

有效包7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f、内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07和ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0未改，旧a8cb包禁用。此前c302451离线参数契约及原23份绑定报告保持。[参数契约](operations/2026-10-26-read-parameter-contract.md)。板值/内存/TCR/身份/_verified与239、权限/认证门不变。

下一步仅离线固定v_op目标与入口观测，再选最早未返回的内部边界；不重启28、不自动启动新候选。不把MAC返回绿灯当错误码0或策略全部执行的直接证明。历史28项未跟踪保留，无push；唯一最新交接：[10月26日主线交接](operations/2026-10-26-mainline-handoff.md)。
