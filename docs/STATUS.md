# STATUS

更新：2026-10-26。完成PROBE28参数契约离线补测与模拟夹具ABI修正；本轮用户已授权必要的最小离线实现。设备操作仍全部暂停，未执行adb/fastboot、预检、临时启动或刷写。

新增9组真实flags8/4096读取对照、4组交付loader存储案例、2个负对照通过。实际EFI把owned window同时写到memSize/0x18与memSizeActual/0x2d8；当前ADT窗口1GiB。原生arm_init定位块写PAGE_SHIFT_CONST=12，实际header指令产生4096/flags8。bootstrap TCR的翻译粒度另行解码，不能与运行时页大小混同。16KiB仅为负对照，未取得可运行资格。

修正test-probe-transition.py遗留的Darwin23模拟偏移0x478为Darwin22的0x2d8；从入口重验normal路径5项通过、到_kernel_bootstrap。新旧完整快照有6处差异，未声称逐字节等价；最终映射和5项验收相同。短读首轮错误EIO预期已纠正并保留失败：vn_rdwr总向内层传局部残余指针，外层NULL不触发内层NULL分支。原默认11组输出逐字节相同，原23份绑定报告及包/内核/ADT SHA保持。详见[参数契约记录](operations/2026-10-26-read-parameter-contract.md)与reports/kernel-entry-probe/2026-10-26-v36-parameter-contract/validation.json。

证据级别仅为静态/Unicorn指令与API模型检查通过；未执行完整EFI分配/arm_init或真实MAC/APFS/decmpfs。最早实机卡点仍为PROBE27的250到达/251未观察；264黄/265绿及A033 FFFFFFF005F48EF8只证明类型4表项。PROBE28尚未实机，首要文件系统读取内部等待、次要MAC，需用266..275分界后再下结论。[后续路径与公开研究](operations/2026-10-26-next-stage-public-research.md)、[激活读取审计](operations/2026-10-26-read-active-transparency-and-waits.md)保留。

有效PROBE28未重建未改包：reports/xnu-first-entry/entry-probe-28.json；包7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f，204484608B；内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07；ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0。原24项、1092比较、独立内核重建及包回读为此前证据，本轮未重复全套。旧a8cb包禁用。FD/shim、板值/内存/TCR/iOS16身份/_verified均未改，loadable/runtime_qualified=false。

R-014仍open；设备当前状态未刷新，历史v35/postcondition（2026-10-26T00:19:12.450574+08:00）不能当当前预检。中午可用时间不自动授权操作，需当轮画面/恢复确认及新鲜身份/Android1/槽/三SHA，再按门禁使用同一PROBE28；239恢复用户态门保留。历史28项未跟踪保留，无push/云CI/原始媒体上传，enuma与旧会话未动。唯一最新交接：[10月26日主线交接](operations/2026-10-26-mainline-handoff.md)。
