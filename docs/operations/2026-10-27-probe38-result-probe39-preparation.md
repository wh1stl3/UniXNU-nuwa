# PROBE38实机结果与PROBE39准备

PROBE38照片PROBE38.jpg已核对并保留原件，SHA256 f95a0ff2e9aa7e1be77d2660a20d36b3a964c065e71a4b30531a0346ce307fcd。裁剪与清单在Media-nuwa/derived/PROBE38/review-01，screen.json和media-binding.json在reports/xnu-entry-probe-trial/2026-10-27-v46。当前仅有照片，拍摄等待时长/稳定状态已询问，尚未确认。

新增左侧511/512分配器入口、513/514 kalloc调用/续接、517/518原子计数调用/续接、519/520统计调用/续接和521 RET位置可辨。499—510分配后/向量检查点未见点亮，decode入口未见点亮。分配器条带在同一header内累计两处调用，不能单凭521归属第二次分配，更不能判定整个分配器死锁。A033/A035/A039部分被Logo遮挡，本轮不以历史值代填为新OCR。

09:03:46 +08只读后验确认Android完成1、nuwa/kalama、A槽、boot_a/vendor_boot_a/init_boot_a SHA与启动前一致。用户已回Android，未额外恢复boot。38已消费，不重发。

固定指令事实：第二次调用前x24=((w21+1)<<4)|8，已知当前fetch设置w5=1；回调+0x1b4检查x0，零直接跳+0x208的错误打印路径，非零才经过+0x1b8/+0x1c0。首次分配可选，条带没有区分两次调用。首要待证伪解释为第二次分配返回零进入此前未覆盖的printf错误分支；支持为分配器RET点已出现而后续非零检查点未见，反对/限制为RET可能属于第一次分配、白色续接被Logo遮挡、照片没有时间序列。仍保留第二次调用未完成或其他观察盲点解释。不把假设作为改分配器或绕过错误检查的依据。

PROBE39 / revision47保留全部分配、向量、decode、外层读取及exec观察，新增第二次请求/返回的独立作用域记录与printf调用/续接、错误分支、回调退出值设置位置。A03A请求字节、A03B分配器RET x0、A03C调用者续接x0、A03D最后检查点PC、A03E回调原生SP+0x58元数据类型。A03B/C以全F标记尚未观察；必须结合A03D，不将全F解读为真实返回。

新增scripts/read_result_sites.py、scripts/test-read-result.py。不修改分配策略、锁、错误、认证、IRQ、缓存或239释放门；无用户态/UFS资格声明。测试中的零/非零分配返回由夹具提供，只执行真实原生epilogue/RET/CBZ及其后指令，不冒称实际kalloc或printf执行通过。

首候选布局检查失败：新增条带y248与原下一行重叠。已撤下未部署，保留out/kernel-entry-probe-47-result及原build/失败日志；将新增条带放y244的空隙，重编译为out/kernel-entry-probe-47-result-r2，内核SHA256 8e98e5bd67c8ccda1f216ec195c47c316ea08cabe673f3ba0022e6ba7e72c72d。第二次专项运行遇测试读取混合整数/字符串va字段的TypeError，修正夹具类型处理，候选未改变，原日志保留。当前专项及完整资格尚待完成，未打包部署。

2026-10-27T09:21:58.5667315+08:00：新增专项105项通过，包括9个实际hook位置×11种作用域/状态条件、header清理、布局、排除第一次分配、原生零/非零返回分支和缺失printf配对负对照。第一次重跑的夹具另遇va=null条目，已按非地址补丁跳过，候选未改变；原日志保留。完整36项串行作业已启动。ADT SHA256 e43df7d6472fe97b6c279687b53971c87b7f5e0e1a763d3f609077cb92763c72。

只读源码参照：Legacy/common/sources/xnu-ios16-full/config/MasterVersion为22.6.0；iokit/Kernel/IOLib.cpp SHA256 244409aa9cd6abfeed886d8e494973c8cb0c57f252328a7d372a25e337a75315，osfmk/kern/printf.c SHA256 af83777d18a7054285e143d6cfe49db87b31010dfa6a346983d9de935767d2b5。参照中分配器保留NULL返回，printf仍执行格式化、控制台和os_log路径；仅作机制解释，实际地址/ABI以固定prelink指令为准，未把不同来源源码当作完整二进制匹配或实测结论。


固定指令进一步约束：IOMallocData设置w2=0x1000，IOMalloc_internal保存到w22；bit15未置位，原生+0x58/+0x5c在底层结果为0时跳过统计路径。照片517原子计数调用点及其续接可见，因此至少一次匹配作用域的分配走过非零结果路径。仍不能归属第一/第二次，也不能外推整个堆稳定或UFS通过。这是照片与固定指令结合的推断，非独立返回值读数。


PROBE39结果判读（条件表，尚非实测）：

| 读数组合 | 可支持的结论 | 下一步证据方向 |
| --- | --- | --- |
| A03A有请求，A03B/C仍全F | 新请求已记录，尚无相应返回记录 | 结合既有allocator条带，不能把旧条带归属新调用 |
| A03B为0、A03C为0，A03D到+0x208或+0x224 | 第二次返回NULL，进入真实错误路径 | 先查分配失败来源；若printf无续接，再查该日志路径 |
| A03B/C相同且非零 | 分配器返回并被调用者收到 | 依据499..510、522..581继续看向量/decode，不再停在分配猜测 |
| A03B已有值、A03C仍全F | 返回点观察到了值，调用者续接尚未观察 | 结合A03D与异常/原生返回目标，不能直接命名死锁 |
| 完整读取及exec外层出现后续点 | 相应原生路径有新实测依据 | 仍按239释放门与用户态真实执行证据判定 |

全F是当前记录哨兵，不作通用错误码；A03D记录的是观察点PC，不是采样到的当前CPU PC。条带和HEX不能替代完整时序。原始照片不覆写，原报告不重算摘要伪装成原验证。

用户补充确认：‘画面已稳定拍的’。具体等待秒数未提供；独立追加reports/xnu-entry-probe-trial/2026-10-27-v46/capture-confirmation.json，绑定首次screen/media-binding摘要，不改写首次记录或原图。上文‘稳定状态尚未确认’现已被本条补充取代。


完整回归35项功能作业通过（透明性2324、read-body476、read-decmp617、read-fetch509、read-deep752、read-result105等）。末项binding因新增函数内import importlib.util遮蔽已有模块级importlib，在校验前抛UnboundLocalError；删除重复局部导入，未改变任何内核字节或检查条件。保留execution.json失败原记录，单独重跑binding，全部通过后写execution-qualified.json引用原失败和修正后绑定结果。


## 最终资格及部署（2026-10-27T09:47:43.3076351+08:00）

以上准备中、尚无资格是历史阶段。现36项作业全部通过，独立内核逐字节一致，最终包FAT读回通过。qualification.json绑定原失败尝试；execution-qualified.json关联原execution.json失败及绑定续接。最终镜像SHA256 83b7eaa213922be09da3236b0ec0a16ecdec928a86668b6c688855884112672c，204484608字节；源码diff out/probe39-source.diff。09:45:39新鲜预检nuwa/kalama/Android1/A槽/三SHA一致，09:46单次临时发送ACK0并写consumed，尚待媒体及恢复后验。ACK不是内核执行证明；保留239释放门，无flash/erase/改槽、受审参数或_verified修改。

