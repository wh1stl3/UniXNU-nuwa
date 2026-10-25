# v25：首线程后路径、HEX越框修复及异常向量交接

当前结果：PROBE18实机运行首线程，PE_init_iokit返回，到mac_policy_initmach的Image4策略panic(2)；横纹消失，已恢复Android及三SHA。完整实测与审计见下文后半段；续接入口为[当前交接](2026-10-25-mainline-handoff.md)。

以下至实测段之前为18:11离线验收快照：目标为继续PROBE17实机已到达的load_context调用前边界，一次覆盖首线程、IOKit、BSD/root关键路径，并处理用户确认的实机横纹。当时最高实机阶段尚未更新；模型检查不得写成实机进展。该快照中的“未实测/无设备动作”仅描述验收时刻。

## 横纹定位

用户确认菜单未按Enter时没有横纹，按键后与早期色带/HEX出现，之后网格出现；肉眼也能看到，不能继续归因于拍摄伪影。7.916767秒原始有声视频SHA为2832fce3644cc13f6c14bb9d1640b1e3b72da2eca87f85c4568744f8099d000d，20,849,036 B，保留用户本地路径，未上传。FFmpeg仅提取本地静音PNG，4fps共32帧，未加入Git或CI；不以250ms采样推断更细的先后关系。

明确代码错误在HEX_RENDER：240次STP，每次写8字节，共1920字节；换行却只减1280，导致每行多偏移640字节，即160像素，逐行漂出480×20文字框并覆盖Logo等背景。修复为减1920，不改变stride、分辨率、板值或映射属性。

新精确矩形测试执行真正渲染指令，检查每次framebuffer写入。旧PROBE17在soc_base/wfe/panic三个场景分别出现33,600/13,440/26,880次框外写事件；新候选均为0。旧测试只检查整屏总范围和若干字形，没有约束每个矩形，因此漏掉行漂移。确认的是代码缺陷和负对照复现；修复后实机横纹完全消失尚未验证。详见display-diagnosis.json、renderer-bounds.json。

## 异常向量缺陷与原生交接

继续核对发现临时向量每槽原来是124字节零填充，再B到probe_exception。CPU从槽位首指令进入时会先执行零指令，不能可靠到达报告器。此前仅直接调用probe_exception的测试没有覆盖实际槽位入口。

修复为每128字节槽位第一条B到报告器，再填充124字节。新测试逐一执行16个真实入口，全部到达报告器；旧PROBE17全部先触发异常，作为负对照。此为确定的探针缺陷，不推导PROBE17实机当时必然遭遇过某个异常。

原生固定输入的ExceptionVectorsBase为0xfffffff0073c2000，首指令为原生分支。start.s的common_start在MMU开启前设置该KVA；探针MAP_FB接管前保存VBAR。在kernel_bootstrap_thread入口核对保存值等于固定原生符号后，恢复VBAR并ISB；正常IRQ/FIQ/同步异常交回XNU，避免临时报告器拦截正常线程服务中断。值不匹配则A02C=2明确停止，不猜测向量地址。成功为A02C=1。线程入口前仍使用修复后的诊断向量；原生panic族探针保留。

vectors.json覆盖真实槽位、原生冷启动VBAR捕获、首线程入口交回原生VBAR和异常保存值拒绝，共5项；不代表实机IRQ控制器或中断递送已经可用。不能把无异常字样当作绝对无故障。

## 新观察布局

178编号，162个新增补丁位置，总211记录补丁。旧PROBE17的密集目录保留为revision24解释；revision25替换为新路径，不能沿用旧编号。

- 黄色：函数入口；紫红：机器上下文检查点；蓝：调用前；绿：原后继位置，仍可能由共享分支直接到达。
- 右侧10列，x832起，列距48、行距24，块32×16。ID位置为x=832+(ID%10)*48，y=256+(ID//10)*24。
- ID0 load_context；1 machine_load_context；2 thread_continue；3 call_continuation；4 kernel_bootstrap_thread；5 PE_init_iokit；6 bsd_init；7 IOFindBSDRoot；8 vfs_mountroot；9 bsd_utaskbootstrap；10恢复SP后加载D8之前；11恢复上下文RET之前。
- 后续点覆盖load_context内部、thread_continue、kernel_bootstrap_thread主要调用、BSD关键初始化/存储/root调用及utaskbootstrap。BL/BLR保留原生LR，ADR/ADRP/条件分支重定位；不跳过原生函数。
- y224、x832..1215为384×16白/青校验带。进入load_context时绘制，后续检查只读回、不重画。A02A为不符合预期的像素数，A02B为最后检查阶段ID；这两项在进入新阶段后覆盖旧DT字段含义。A02C为向量交接状态，取代旧SoC字段含义。其余字段继续按绑定screen目录解释。

CPU读回0只说明经当前Device映射读到的像素一致，不证明物理扫描输出正确。校验带不承担面板驱动初始化职责。

## 上下文恢复核验

固定二进制load_context和machine_load_context内没有TTBR写入；不为该处凭空补新的页表切换。临时framebuffer映射在此边界的可见性仍须随实机观测核对。

独立配对执行原生machine_load_context与候选，比较全部GPR、SIMD、SP、NZCV、FPCR、TPIDR寄存器、CPU当前线程字段及新栈可见内容。覆盖首次、重复、无视频、FPCR变化和真实首线程SP等于保存帧地址的布局；后者对应pcb.c machine_stack_attach将savestate->sp设为kstackptr的契约。渲染临时栈位于其下方，不覆盖尚未加载的保存帧。另有校验带填充、0错像素、1像素破坏、整行破坏且不重绘、无视频保持原生控制流，共10项。均属合成夹具，不是完整调度器或硬件显示验证。

740项逐点差分也覆盖GPR、SIMD、SP、NZCV、TPIDR和原生内存效果。arm_init的TPIDR shim、首线程入口恢复原生VBAR是明确的预期行为变化，分别独立核验。

## 产物与执行边界

当前最终内核d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e，58,413,056 B；新目录重复构建一致，donor/prelink逐字节保留。新镜像c89cfa52c165562693ab0868dddeeb1225995bb5f30e3899df58a888197e8dde，70,266,880 B；ADT9846c7dadd23bf544190c45ba3db437fb83265cb180ad6c54cd3a3fedee20d93。包reports/xnu-first-entry/entry-probe-18.json，工作产物out/trial-boot/xnu-entry-probe-18-vectors/。

最终d6f101e4及同镜像ADT的连续模型已越过load_context、machine_load_context、thread_continue、call_continuation和kernel_bootstrap_thread，并进入PE_init_iokit。VBAR已恢复0xfffffff0073c2000，其原生向量页确实映射到0x8c37c2000；新的线程TPIDR已安装。之后停于bzero+0x1c，普通STP x1,x1,[x0]写0xfffffff8550a4000，长度0x5000，调用者为OSKext::updateLoadedKextSummaries+0x1e8。源码OSKext.cpp:16162附近为kmem_alloc/保护处理后清零摘要缓冲。Unicorn返回UC_ERR_EXCEPTION，bad_memory为空，ESR/ELR/FAR均0；未进入BSD。分配映射/权限与模型异常递送尚未区分，不将其判为实机故障，也不补假RAM或跳过bzero。

最终740差分、42入口/MMU、18读数、5WFE、6静态walk、5ParseKernel、8稀疏阶段、2处理器、6精确矩形（含旧包反例）、10上下文/显示及5真实向量检查均通过；同ADT四切换场景12断言、6console策略及26绑定检查通过，最终镜像回读通过。新增证据文件被删除或删掉用例后重新封摘要也会拒绝。

本地最终校验驱动曾沿用PROBE17报告文件名，摘要校验拒绝后已按Git HEAD字节恢复历史报告，仅重封PROBE18；没有设备动作或历史包修改进入提交。实际错误、修复及Git字节一致性在execution.json和out原始日志中。中间候选和未完成模型留本地，不能冒充最终候选结果。

loadable=false/runtime_qualified=false；TCR、板值、owned window、donor、认证和_verified未改。脚本串行，无新设备动作。最近设备核验仍是PROBE17恢复后2026-10-25 17:18:00北京时间Android1/A槽/三SHA一致，不当作当前实时查询。

实机试验仍需本包录像及按键恢复就绪，刷新preflight、即时通知后单次临时boot；菜单电源Enter触发，不固定等待180秒。先读校验带/新编号/A02A–A02C，再恢复Android完成1及三SHA闭环。原始音视频/静态截图仅本地，不push。

## PROBE18实机结果与新卡点

代码/离线证据提交9a5961f。本包用户录像/恢复确认后，18:13:09北京时间刷新Android1/A槽/三SHA，与PROBE17后验一致；18:13:39单次临时boot ACK。用户在菜单按电源Enter后确认画面稳定、横纹消失；原图1751df6ec68fe8a4edab0f46798f45e4002acff48cfd726c38dc754dba22e99c，视频bd941aa044c8f672238b61ff713f91718f737a93d137958c5038bdc057ca40de，7.334656秒/19,458,223 B，含音频，均仅本地。照片取样/目视共81格亮，完整读数与RGB见trial目录screen.json。

A02A=0、A02B=4，表明首线程入口检查时校验带无不符像素；照片中白/青条完整，Logo横纹消失。这是本轮实机观察，不是长期显示资格。A02C=1，表明该入口已核对并交回原生向量。0–5入口、10/11上下文检查点及其后调用链可见，首线程确实执行到了kernel_bootstrap_thread；PE_init_iokit的74/75可见，之后80/81中断使能调用、84–87commpage初始化路径可见。88为mac_policy_initmach调用，89未出现，6 BSD入口未出现。不得仅据使能调用返回宣称真实IRQ递送/控制器已验证。

本轮明确panic：A028=6661696C65642074、A029=6F20676574206D69，拼接`failed to get mi`；与保留donor唯一字符串`failed to get mix-n-match policy: %d`匹配，A031=2。模块为com.apple.security.AppleImage4 5.0.0，原donor文本与现prelink的slide为-0x1000000，格式串VA0xfffffff003e20262。最终实机停点是MAC/Image4策略初始化，已经越过模型先前的OSKext摘要bzero停点，不能继续将那个模型异常称为实机阻塞。

按键恢复后18:19:42北京时间Android完成1/A槽，boot_a/vendor_boot_a/init_boot_a三SHA与试前完全一致，无flash/erase/改槽、无第二候选。证据reports/xnu-entry-probe-trial/2026-10-25-v25/{preflight,launch,screen,trial,recovery,postcondition}.json。

## Image4契约审计

静态调用与GOT核对定位`/chosen/mix-n-match-prevention-status`：AppleImage4读取器0xfffffff0046e9fe0的enum12分支，经0xfffffff0046eae28和原生SecureDTGetProperty读取。缺属性返回2，值为0会转换为allow=true，非零为allow=false；读取缓冲容量为4字节，空属性也被当作0，所以“补一个空属性”会改变策略，不能作为修复。

新增audit-image4-boot-policy.py在保留二进制上执行实际读取器与原生SecureDT函数：最终发出的ADT缺属性，返回2；32位1返回成功且禁止mix-n-match；32位0/空属性允许；8字节超出4字节缓冲返回84。5例通过，无原生函数替身、未改当前ADT/内核/运行时策略或设备。隔离模型只执行SecureDT后备路线，IOKit runtime-provider路线尚未动态复现；首要缺项判断由实际属性缺失、同码反例及静态两路线属性名共同支持。见image4-policy-audit.json。

runtime.h的IMG4_IDENTIFIER_AMNM/CHMH说明该策略会影响nonce与前级manifest hash约束。下一步先完整列明Image4启动环境及实际manifest/hash来源，选择明示的软件平台策略，保持来源可追溯；不将补字段视为建立了Apple可信启动链。ios-sweet/topaz的合成boot-manifest-hash只作为其他非Apple移植的兼容性参考，不能当作nuwa真实前级签名manifest证据。当前没有选择运行时值、未绕过认证，板值/TCR/资格保持。
