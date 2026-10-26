# PROBE28 实机画面、边界判读与恢复闭环

2026-10-26（上海时间）。有效包7a04626e仅临时启动一次，未重发、未换包、未启动下一候选。用户明确拍摄/按键恢复条件，12:07:53新预检确认nuwa/kalama、Android1/_a/三SHA；12:08:55发送PROBE28，fastboot接受仅作传输证据。用户随后提供本轮照片并报告已回fastboot；本轮先核对实际连接状态，确认nuwa仍在fastboot而非用户已自行恢复，再按既有原boot流程恢复。

## 原图判读

照片Library ID libfile_8da6cb270ad481918654ead1a4bb94f7，710443B、1536×2048，SHA256 8b25519f7eb803bf101cb96ba6d2f83befe5b575a071aa2b5ccd4b4eb9bb70df。已实际视觉检查原尺寸像素，不使用Library文字摘要代替读图。原图与Library身份/版本扩展属性仅保存在本地out/trial-evidence/entry-probe-28/user-screen-library-complete.tar（SHA ad688e9ec6fe39b0e84b9402809000c3c8616aa1d4949c882aa9f1b718793cba），未commit、未push、未由本会话重新上传媒体。Windows扩展属性兼容问题通过原样Library助手在本机WSL解决；原图与元数据归档完成。无有效Windows直接图片路径时不伪造路径，失效临时路径不作为持久证据。

原图明确显示XNU ENTRY PROBE 28。A034=0000000000000110，即272；A035=FFFFFFFFFFFFFFFF，为调用未返回哨兵，不是原生errno。A033在此照片中未可靠逐字转录，不据模糊像素修改先前用户更正的EF8历史读数。

| 边界 | 调用标记 | 返回标记 | 本图读数 |
| --- | --- | --- | --- |
| vn_rdwr → vn_rdwr_64 | 266青 | 267未亮 | 已观察调用，未观察返回 |
| mac_vnode_check_read | 268青 | 269绿 | 本轮作用域内已观察成对调用/返回 |
| VNOP_READ | 270青 | 271未亮 | 调用已观察，返回未观察 |
| VNOP_READ内原生BLR x8 | 272青 | 273未亮 | 到达分派调用点，返回未观察 |
| vn_read_swapfile | 274未亮 | 275未亮 | 未观察该分支 |

映射依据scripts/read_boundary_sites.py的CALLS和observe，以及probe_bootstrap_sites.py的266..275坐标（x832+(id-266)*48、y784）。本包每次header250清理这行，且限定原生caller/线程/帧，返回需有对应调用；MAC拒绝和VNOP返回的公共汇合点不会凭地址制造271。

## 结论与边界

首要调查区域从“MAC或文件系统”收窄到**真实文件系统分派调用点至其返回之间**。本次画面不支持仍停在mac_vnode_check_read内部；269是返回标记，绿色本身不编码errno0。按保留的原生MAC错误分支，随后到达270/272支持本次MAC返回未阻止继续读取，但原始MAC返回码没有在当前A035中保留，不能把绿灯称为全部策略认证通过。

272在重放原生BLR x8之前记录，故只能证明到达调用点，尚未直接证明目标函数体入口执行。聊天中一度称“已进入真实回调”过满，已明确更正，本记录采用上述严格边界。后续仍须区分分派重放/目标指针/入口异常与目标进入后的APFS/decmpfs/UBC/UPL/认证/fetch/底层I/O等待。

工程排序：优先核对实际v_op目标、回调入口和APFS/decmpfs等待路径；MAC函数内等待降为不符合本次成对标记的解释。图中未取得目标地址、锁owner、wait_event、线程栈或IRQ状态，不能指定死锁、某把锁或丢中断为唯一原因。单张照片也不能证明永久停滞或精确等待时长。A033类型4表项不能当作此v_op目标，不能当解压执行成功。

本次证明XNU执行推进到受限header读分派调用点；未证明完整文件头读取、解压回调完成、Mach-O/dyld或用户态启动成功。_verified、loadable/runtime_qualified不变。

## 恢复后验

只对显式选中的nuwa执行既有recover：核对product、隔离重进bootloader，临时加载固定原boot ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31，未flash/erase/改槽。recovery.json确认Android boot_completed=1。12:24:07上海时间（2026-10-26T04:24:07.962085+00:00）postcondition.json再次确认nuwa/kalama、Android1/_a，三SHA与本轮preflight逐项相同：

- boot_a：ef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31
- vendor_boot_a：5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23
- init_boot_a：19e95d952ded5172e8a17bd1af907a8d6b08b29734881c370961b09bbaf78f96

没有向enuma发送查询或设备操作；枚举中出现其他设备不作为本项目证据。此前被用户接管拒绝的父侧操作未执行，本轮基于明确交回指令核对状态后才恢复，没有重复已成功恢复操作。R-014本轮已满足并闭环，当前无需人按键。PROBE28已consumed，不能再启动。

## 最小下一步

先离线核对固定候选中v_op读取与BLR的实际指令、目标符号/模块边界，利用已保存但未展示的dispatch target规划入口/返回观测，再选择最早未返回的APFS/decmpfs内部边界。需要区别目标入口未执行与进入后等待，保留原有权限、认证、错误和恢复用户态239门。当前只给下一阶段方案，未构建或启动新候选；任何后续实测仍需对应候选资格与当轮观测/恢复预检。

完整证据：reports/xnu-entry-probe-trial/2026-10-26-v36/的preflight、launch、consumed、screen、recovery、postcondition与evidence-binding.json。仅提交脱敏文字与哈希。
