# PROBE38 / revision46：分配、向量准备和decode连续覆盖

新增83个观察点：12个回调分配后/向量构造原生指令位置，IOMallocData尾调用入口，IOMalloc_internal入口/4处原生调用及续接/RET，固定decode helper入口/29处非printf调用及续接/RET。全部旧读取、fetch/type4和exec观察保留，成功阶段不停；原生锁/错误/认证/缓存/IRQ及239释放门保持。

新文件scripts/read_deep_sites.py、scripts/test-read-deep.py。ID499..510为回调检查点，511为IOMallocData入口，512..521为IOMalloc_internal，522..581为decode helper。前23个放x208的左间隙；decode放旧中心短线下方16像素，32×2，全部仍在原1040行范围内。没有内存/板值/IPSW身份或*_verified改动。

作用域继承当前header、线程、实际回调目标和外层帧/配对，额外核对精确子调用LR、父调用在途位、子函数保存的父帧及独立配对。IOMallocData尾跳不制造额外帧；allocator/decode内部按实际prologue帧链检查。原始指令清单在reports/kernel-entry-probe/2026-10-27-v46-preparation/{allocation-decode-native,malloc-native}.json；无名helper仅按固定地址命名，不捏造已执行的算法。

内核out/kernel-entry-probe-46-deep/kernel-entry-probe.macho，SHA256 f2711bf88941cb9e1c048e55e6c51b26b77b138c9d4dd6582ece11416f390324，58621952字节。ADT out/exec-mainline-v46/launch/kernel.macho.adt，SHA256 61219246e192aa0f814a9f232a77d380a568ef6f6391f30a6fb7ce620a52a30d。

首次快速夹具使用STACK+0x12000作为子帧，超过模型已映射测试栈，尚未运行观察器就写入失败。原smoke-console.txt保留；仅将夹具子帧移到既有测试栈内STACK+0xa800，无生产内核或硬件内存改动。54个作用域快速用例、重置和真实IOMallocData→IOMalloc_internal→kalloc_ext前缀对照通过，见smoke-r2-console.txt。前缀模型显式选择追踪关闭路径，不是实机分配/全部分支通过。

完整35项串行检查正在运行，新增专项要求752项（83×9作用域模式及5项综合检查），另保留全部旧回归。同覆盖HEX内联对照沿用37修正的方法，不再把不同观察点数量的整包尺寸混比。尚无最终包资格，不可启动。

改动前源码原字节out/before-probe38-source；37媒体/Android恢复已闭环。无提交/推送，媒体本地，不操作其他机型或第二写入者。

## 全回归边界模型修正

首次全回归的透明性检查在header重置写入(y816,x736)时拒绝：旧边界模型只涵盖旧中心矩形的前16行，本轮第三排短线正好位于下一行。固定生成代码及声明布局一致，不是未声明的生产写入；候选未部署。原execution.json、regression-console.txt保留。

修正只添加read_deep_sites.plan对应的精确32×2矩形，并检查新增矩形、旧revision45拒绝这些位置、间隙/跨矩形写入仍拒绝。未把整屏范围放宽。候选二进制不变，重新执行透明性及后续尚未执行项；续接记录execution-continuation.json，全部通过后另写execution-qualified.json并绑定原失败记录，不改写失败为成功。

后续新布局的快速检查应同时调用共享边界模型核对初始化写入，避免完整回归后段才发现测试布局清单遗漏；不能用关闭边界检查代替更新精确布局。

## 最终资格及单次部署（2026-10-27T02:18:06.0262028+08:00）

以上‘正在运行/不可启动’是核验中历史状态，已由35项作业全通过、独立内核逐字节复现和包内读回取代。资格见v46/qualification.json，原失败保留。包SHA256 385b7e5c22bb5532e2a2d1638f7fc2c48d1f9a89d9efe8e7c2c7584242108cfe。新鲜预检确认Android1/nuwa/kalama/A槽/三SHA一致后已临时发送一次，ACK0，consumed.json已记录。等待实机媒体和恢复后验；不把离线模型或ACK写成实际内核阶段通过。源码diff：out/probe38-source.diff。持续授权依据见STATUS，无新增本轮确认。

