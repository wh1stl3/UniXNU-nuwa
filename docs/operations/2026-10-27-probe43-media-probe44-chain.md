# PROBE43实测与PROBE44连续读取链

阶段：S03/S05/S12/S13。用户确认43照片前画面稳定、等待超过十秒，已回Android；新鲜postcondition确认nuwa/kalama、Android完成1、A槽及三分区SHA与43预检一致。43已消费，不重发；本轮准备44，不自动启动。

## 实测、代码和最大疑点

原始媒体现存`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE43/original/`。498个源帧及用户给定的五阶段截图保存在同轮`derived/review-01/`；源PTS、原件和派生SHA分别保存。FFmpeg记录非单调DTS（241 >= 241）和附加数据流元数据警告；帧数与ffprobe一致，不用帧号/60替代源PTS。已核对原照片、五阶段截图及视频末帧，没有声称逐帧转录全部HEX。

照片末态可辨A03D=`FFFFFFF00519CC10`。43实际代码在该位置记录原生调用前x0，随后原生`bl FFFFFFF00519CC48`。观察器要求read线程、活动handler状态、caller frame和LR匹配，因此证据已超越42的wrapper分派：handler内部已到属性处理调用前。不能据此宣称519CC48入口已执行，或内部锁、IO已经卡死。原生x0看似对象指针，其有效性不能由照片单独证明。

固定43内核SHA为`e5df5bef0779347edc5d94becd1611f8c3ffe7d5595795f345872dc02fe74a8b`；`reports/kernel-entry-probe/2026-10-27-probe43-analysis/native-attribute.json`保存实际候选上未修改部分的有界控制流、调用和导入stub解析。CFG保守地允许panic调用后的顺序边，不把因此抵达的相邻函数当成一个原生函数；44选点使用实际前言/尾声边界，并不从全部可达指令自动生成钩子。

**最大疑点已收窄为属性处理及其ResourceFork取数链未完成可观察返回。** 519CC48先分类属性，再分支处理ResourceFork vnode查找（519D350）、文件读取（519C2A4）或属性元数据/直接拷贝。读取函数存在实际`_cluster_read`调用519C49C，也有锁、对象释放及节流调用。前一轮519CBD4条件辅助函数已不宜继续作为当前停留位置的首要解释：执行已经到达它之后的519CC10，说明它要么被跳过，要么完成了返回。

支持：稳定十秒以上的末态与实际匹配记录吻合，尚无519CC14配对续接。反证/不确定性：没有属性函数入口、内部调用及返回现场；观察遗漏、诊断绘制干扰仍可解释末态。不能仅凭该结果给某一把锁或UFS归因。当前根仍是`rd=md0` RAMDisk，`_cluster_read`是VFS缓存/读取接口，不等于访问UFS。

已有[压缩输入闭环](2026-10-27-compressed-payload-closure.md)记录38个固定恢复根文件、188块的宿主展开及摘要一致；本轮根输入未变，引用该历史证据，不冒称重新执行。它削弱“压缩字节本身已坏”的猜测，但不能验收设备上的APFS缓存、锁、内存分配或IO。原生UIO初始化的既有夹具同样不能替代真实分配器/handler执行。

本轮公开资料搜索工具返回HTTP403，停止对应访问，没有换通道绕过；未完成新的在线资料核验。沿用已固定本地源码/原始实现并保留该缺口。

## 44的连续范围与证伪标准

新增68个唯一位置，分属3个函数，覆盖入口/返回和31个有意义调用的前后续接：

- 属性处理519CC48：分类、ResourceFork lookup/read、读锁、元数据获取、直接uiomove、外部数据读取及清理。
- ResourceFork vnode查找519D350：内部查找/对象准备、vnode创建、读锁、属性查询和释放。
- 文件读取519C2A4：两级读锁、读取准备、`_cluster_read`、条件写锁、回调及节流；主函数RET是519C848，不把后面的其它前言/返回混入。

新增96字节状态；每个子调用验证活动read线程、父调用配对位、父帧及saved LR，返回还验证自己的调用位。仍仅写A03D/E两行，不增加网格；没有新halt、不替换原生锁/错误/IO、不修改239限制。顺利返回后继续已有解压、exec等原生路径，不能把添加观测点说成已修复原生卡点。

预期区分：若停在lookup内部，继续针对vnode/属性对象生命周期；若到cluster_read调用前而没有续接，排查缓存/读取等待；若元数据或uiomove分支未返回，转向该分支；若519D2AC及519CC14、wrapper返回均可见，则推翻“属性处理未完成”，继续用后续解压/exec记录定位。调用前始终不是callee入口或停止PC。未拍到短暂字段也不是未执行。

818项新增离线检查已通过，涵盖原生指令差分、无视频、错误线程/帧/LR、父调用未配对、自身返回未配对、头重置和删除线程门负对照。不是全函数APFS执行或实机调度证明。44内核已生成，完整串行回归、独立重编和整包回读完成前不能部署。

## 媒体目录维护

按用户要求已将PROBE29至43的原件与派生材料归入每轮目录；1397文件移动前后SHA逐一一致。根目录`media-path-migration-2026-10-27.json`保存旧路径→新路径、字节数和摘要，旧manifest和原始证据保持原文。未来实机前先创建轮目录；下一轮`Media-nuwa/PROBE44/original/`及`derived/`已创建，AGENTS第9节和媒体README已落规则。

目录准备已接入`record-nuwa-trial-state.py`的XNU包预检：先验证包，再由`trial_media.py`解析菜单PROBE编号和可选R修订号，在任何设备查询前创建目录，并将路径写入新预检记录。现有文件不移动、不覆盖；歧义编号、文件冲突及路径重定向拒绝。6项纯本地目录检查在内核串行作业结束后通过，涵盖创建、保留原件、修订轮、错误标题及文件冲突；不是设备预检通过。

后续一条包含README更新、空目录清理和转录保存的组合命令被自动审批拒绝（仅返回blocked by policy，无具体原因）。该命令未执行，空的旧derived目录保留；不再尝试清理。必要的纯文本维护已通过不包含删除操作的编辑完成。

## 21:48 +08 离线整包完成

- 镜像`D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img`，204484608字节，SHA256 `b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030`。
- 内核SHA256 `49b913fc15e1517c51acc57af919c76d32187a1258a3a9fbb7f4890ebe2c74f1`；ADT SHA256 `260e212658598fa21732d7d14f7e75fcf5974e5f8918ca70df12148991d861c7`。
- 38项串行作业通过：2768透明性、2025调用流程（含818新增）、67绑定；另29项x18扰动和9项向量准备连续路径通过。独立内核重编逐字节一致，实际整包回读通过，菜单为PROBE44。
- 43旧内核/镜像及迁移后的43原件和五阶段截图摘要一致；Restore根、固件FD、shim和原boot输入保持。已有WSL/GBK stderr读取异常保留，不能声称日志无异常。
- 资格`reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json`；包报告`reports/xnu-first-entry/entry-probe-44.json`；相对43的内核观测代码差异`changes-from-probe43.diff`。媒体工作流另见trial_media.py和record-nuwa-trial-state.py，源码摘要亦纳入资格记录。

44未启动/未消费；本轮无flash/erase/改槽、无提交/推送。239保留，正常OS/Data接入、原生读取/解压/exec闭环和EL0仍分别待验收。上文“完整回归未完成前”的门槛现已完成离线部分，不能据此升级为实机通过。
