# NEED-REVIEW

> 需要用户拍板才能落地的改动。**没有 open 项时，这里保持空表。**
> 2026-10-23现行边界：内存/基址等受审字段、`*_verified=true`；设备动作前缺具体过程日志或已确认恢复路径须硬停。生成镜像本身无需硬停；历史审批保留当时规则。

## 判定规则

立项必须写清：编号、背景、**至少两个候选**、各自代价、你的倾向及理由、需要用户批准的最小范围。
只写「是否继续」不算合格条目。

## Open

| 编号 | 主题 | 需要用户做什么 |
| --- | --- | --- |
| — | 截至2026-10-26 PROBE27收尾无新增待批准项；下一次设备动作仍核对具体日志及恢复路径 | — |

## R-013 · PROBE21当轮过程日志与恢复条件（answered A，本包就绪）

AGENTS第3.2/9节要求临时启动前有具体过程日志和恢复路径。PROBE21离线已完成，新的30个root内部点需实际画面才能区分等待阶段，不能以ACK替代。本包未确认录像条件时停在设备动作前，离线检查继续完成。

候选A：用户本包全程录像、菜单电源Enter、拍停屏并可按键恢复；刷新Android/三SHA预检、即时通知后仅一次临时boot，采集后原厂临时boot恢复及三SHA后验。代价是需要本轮在场，收益是能分清初始IOBSD与介质等待。候选B：保持Android，暂不启动，保留PROBE21离线结果并继续真实root介质准备；代价是不能确定内部等待位置。

倾向A；最小确认仅为PROBE21镜像f005f7ed的当轮可观测/可恢复条件及单次临时boot，不含flash/erase/改槽、内存字段、IPSW身份或*_verified。用户已答复“现在可以，PROBE21 录像与恢复就绪”；新鲜preflight确认Android1/A槽/三SHA与v28后验一致。该日志门解除，按A推进。

## R-012 · ADT 的 dram_size / owned_memory_size 取值（approved A，已写入 board.toml）

**执行结果（2026-10-24 18:40）**：用户回复「批准A继续推进」，按批准的最小范围只写入两个受审字段：`[payload] dram_size = "0x240000000"`、`[payload.adt] owned_memory_size = "0x40000000"`。未置任何 `*_verified = true`，未改 bringup-plan/donor/固件/feed/XNU 窗口，`example = true` 保持，本轮无设备动作。

获批后按 `payload.py:149-170` 的传参规则做了离线复核：`scripts/check-nuwa-adt-board.py` 从 board.toml 组装同样的命令行驱动生成器，两种场景（无 sidecar / 带 ramdisk+trustcache+gpuaddon）均产出 21 节点树、31 与 34 项结构检查 0 失败；证据 `reports/adt-nuwa/2026-10-24/board.json`。**这只证明 board 的 ADT 配置能产出合法树，不证明基座 payload 步骤接受该 board（仍被 example=true 拦住），也不证明固件能满足窗口。**

复核中发现并修正一处契约不兼容：原实现强制 `--unique-chip-id` 与 `--chip-id` 成对，而基座是分别从命令行/环境变量与 `[payload.adt]` 独立传入的，board 的 `chip_id` 目前仍是 TODO，强制成对会让 payload 步骤直接失败。已改为允许独立传入、仅告警，并在原因为缺一方时不写该属性。正负例覆盖见 `scripts/test-nuwa-adt.py` 的 `seed-without-chip-id` 用例。

以下保留审批时背景与候选。

背景：2026-10-24 设备仓 ADT 生成器已落地（`scripts/make-nuwa-adt.py`、`scripts/check-nuwa-adt.py`、`scripts/audit-nuwa-adt-inputs.py`），`[payload.adt] tool` 已指向它，板级常量已逐项对回实机 FDT。但 `[payload] dram_size`（`scripts/unixnu/payload.py:149` 直接读取，缺则无法组装 payload）与 `[payload.adt] owned_memory_size` 属于 AGENTS §3.1 的内存/基址受审字段，本轮没有写入，因此 payload 步骤仍不可运行。

本轮实测证据（`reports/adt-nuwa/2026-10-24/inputs.json`，输入为 `out/live-nuwa-dt/android-dt-after-r011/android-live.dtb`）：

- 实机 FDT `/memory` 的 9 个 reg 条目合并后共有 8 段连续区，最大一段为 **base `0x8c0000000`、跨度 `0x240000000`**（精确 9216 MiB，满足 2 MiB 对齐）。
- `/proc/iomem` 的 System RAM 尾部条目 `0x8c0000000-0xaffffefff` 跨度是 `0x23FFFF000`，比 FDT 描述**恰好少 `0x1000`（最后一页）**，不是少 55 MiB；此前把该段近似记作 9216 MiB 是取整表述。
- 两者只在最后一个 4 KiB 页上不同。`dram-size` 是广告给内核的物理 DRAM 大小，不是分配承诺；实际可用性由 UEFI 内存图与 DarwinBoot 分配决定。

候选 A（倾向）：`[payload] dram_size = "0x240000000"`，`[payload.adt] owned_memory_size = "0x40000000"`（1 GiB）。
代价：广告值比 iomem 可见 System RAM 多最后一页。若 DarwinBoot 真把窗口推到该页，需要 UEFI 内存图证明该页可用；但窗口起点与长度由分配器实际返回的连续区决定，不由 `dram-size` 单独决定，因此这条风险主要落在 owned 请求的验证上，而不是板值本身写错。理由：与 D-001 的 9216 MiB 主 bank 结论、D-002 的 512 MiB–1 GiB 首版窗口范围一致，且 FDT 与 iomem 两条独立证据互相印证。

候选 B：`dram_size = "0x23FFE0000"`（把 `0x23FFFF000` 向下对齐到 2 MiB），`owned_memory_size = "0x40000000"`。
代价：比 D-001 记录的 9216 MiB 少 128 KiB，需要同步修订 D-001 的表述，否则两份文档互相矛盾；收益是广告范围严格不越过 iomem 的 System RAM 末尾。

候选 C：只填 `dram_size`，`owned_memory_size` 留空（不请求连续窗口）。
代价：DarwinBoot 不会通过 `darwinboot-memory-size` 请求指定窗口，58 MB 级内核加 boot_args 与 kext 的装载余量落回默认分配路径，后续仍需补一次同类审批；收益是本轮改动面最小，可先单独验证 ADT 能否被平台专家接受。

**需要批准的最小范围：选择 A 时，只在 board.toml 写入上述两个值，其余 TODO 与 `example = true` 保持不变；不置任何 `*_verified = true`，不改 bringup-plan、donor、固件、feed 或 XNU 窗口，不进行任何设备动作。** 选择 B 时额外授权修订 D-001 中 9216 MiB 的表述。选择 C 时只写 `dram_size`，并明确 owned 窗口留待下一次审批。

## R-011 · 资源耗尽后的DXE Heap修正范围（approved A，源码/构建/唯一临时对照及恢复完成）

本轮执行结果：CI39835052901与实际SEC 41条表检查通过，唯一临时包8e852150由ABL接受。用户明确确认先看到Return to firmware/Restart/Power off的UniXNU内置菜单，随后出现NoBootOS资源图；与无FAT/XNU负载的当前包一致，不当作XNU执行。09:14:28命令确认nuwa/kalama Android完成1且三分区SHA未变，用户另确认已回Android。未再试候选，未改其他区域；下一主线为系统卷发现链路离线审查，不因生成镜像本身新增审批。

用户在R-011 A具体范围后回复“同意”，批准仅恢复同机原厂Heap一行、保持诊断及其他区域，并在D-021日志/恢复门通过后一次同类v4临时对照和Android完成1收尾。固件新分支codex/nuwa-factory-heap@1ccf760已发布完整相同Git对象；只改MemoryMapLib.c一行，35项输入/实际旧SEC描述符回归检查通过，CI39835052901成功，666项实际产物核验通过，新SEC Heap为209.75MiB且41条表仅获批字段变化；运行仍未验证。下文保留审批时背景与方案。

背景：R-010最新清晰实机照片已取得。断言前快照为27次失败、free=25页/100KiB、largest=8页/32KiB、5段、special=0；各段2+3+6+8+6核对一致。上方可见type7=208页，紧随1153页申请失败；第一请求type/align/guard/caller头部未拍到。当前资源瓶颈已有实机证据，但尚未归因所有协议/SPSS错误或证明扩Heap即可进入BDS。

**本次停下依据是R-010既定最小批准范围明确写了“不改board/bringup-plan、原内存图或任何基址/容量”。** 用户新规取消镜像生成硬停已执行；本项请求的是改变原内存图的新增具体范围，不重复请求一般Git、构建或生成镜像许可。只读候选、逐行diff、区间检查已准备完成，未应用固件源码或生成后续包。

**候选A（倾向）：仅恢复同机原厂DXE Heap一行。** 固定uefi-nuwa@2ab6827d中MemoryMapLib.c:32从`0xBAE00000 / 0x04500000`（69MiB）恢复为同机xbl_config抽取表的`0xBAB00000 / 0x0D1C0000`（209.75MiB，半开端点0xC7CC0000），其他行及AddMem/SYS_MEM/Conv/缓存属性均不改。可审阅diff在patches/firmware-candidates/0009-nuwa-factory-dxe-heap-proposal.patch，完整原/候选SHA及静态审查在reports/dxe-allocation-audit/factory-heap-proposal.json；严格apply --check通过，尚未应用。

代价/风险：需新固件来源固定、输入门和一次同类诊断对照。当前固件其他行无区间重叠；历史同机Android DT的/memory覆盖候选、reserved reg和当时initrd均不重叠，未解析节点0。但历史Android DT不等于本次候选ABL x0 DT，静态无重叠不证明所有权/MMU/HOB/实际dispatch；仍可能有SPSS、协议或驱动问题。增加的是UEFI临时分配Heap，不是XNU ADT窗口，D-002和4KiB保持。

来源与适用性：数值取同机原厂表，当前板原厂xbl_config SHA686bce68…证据沿用loader-integration/audit.json及source-audit；同SM8550 sheng@0eb4514d/fuxi@bb25ad75仅佐证Heap结构，已有固定提交/许可/依赖/适用性记录，不复制其额外bank或当作nuwa实机通过。

**候选B：保持69MiB，先审查可选vendor驱动的依赖和内存开销，再作精确裁剪。** 参照固定sheng的vendor条件门结构，列明每个候选模块、APRIORI/DEPEX/协议消费者与保留范围；不做空实现、不删核心Security/BDS/Variable或显示/恢复所需驱动来掩盖错误。代价是更长依赖/资源追踪，且没有证据保证69MiB能容纳保留链，随意关闭设备驱动可能丢失存储/显示或初始化能力。

倾向A：只改一行、同机原厂有确证，针对已实测资源瓶颈，比无资源归属记录时裁剪多项真实驱动更可审阅；不承诺解决所有后续错误。

**需要批准的最小范围：选择A时，只应用0009这一行的地址/容量恢复，保留R-010诊断、原PIL空AUTO/正确shim和其他内存行，固定独立固件提交后编译/静态核验同类v4包；在D-021日志与恢复门通过后一次临时试启动，结束恢复Android完成1并对比三分区。** 不改board/bringup-plan/feed/ADT、donor或XNU窗口，不flash/erase/改槽，不增FAT/XNU/新DTB，不置_verified=true。选择B仅先进行上述源码依赖/开销方案审查，具体裁剪diff另明确后执行。

## R-010 · DXE分配器资源快照诊断（approved A，本次构建/试启动/恢复完成）

执行结果：CI39829943950/c9d538f成功，666项实际产物检查通过；包9197fed2唯一一次临时启动，最新清晰照片确认候选DXE诊断执行，最终27次失败、25页空闲/最大8页/5段，DxeMain.c(586) Not Found断言；BDS/XNU未到。用户按键回fastboot后原boot恢复，02:30:04 nuwa Android完成1且三分区SHA与试前相同，H-005完成。原内存图未改，下一范围见R-011。

执行补充：39827372451真实编译暴露DxeMain缺私有锁声明，锁封装移回Page.c，仍仅两文件、不改锁语义/内存图；私有锁修订bb8bf3ec；后续仅纠正包装注释得到当前patch SHA 4a859ab6108270229fd305d091deaa6cd2d76c37e62dbce823b7e848c73750e1，原hash下文保留为历史。

用户回复“批准”，按倾向A执行两文件核心诊断、CI构建和静态检查；试启动前仍须满足本次新增的具体日志与恢复门。用户同时明确生成镜像无需硬停，历史第3类触发已被本次规则替代；不改内存图、不自动切换B，不把批准当作尚未取得的实机结果。

背景：R-009实际到DXE后连续AllocatePoolPages失败，核心架构协议缺失并断言。当前源码SYS_MEM/Conv仅69MiB，与同机原厂209.75MiB Heap不同；同SM8550的sheng/fuxi也使用后者但驱动范围/额外映射不同，不能凭容量差直接判断根因。失败API还受连续范围、类型bin、地址、alignment/guard与可提升资源影响。本轮没有操作设备或生成镜像，静态审查见[完整报告](operations/2026-10-23-dxe-allocation-source-audit.md)。

触发AGENTS.md§3第3类：“新建或重写任何诊断 / 固件镜像”。R-009已完成，其配置替换范围不自动覆盖新的Mu核心诊断。Git/GitHub持续授权不重复申请；这里仅请求下一具体诊断范围。

**候选A（倾向）：保持现有内存图和驱动链，构建分配器快照诊断并进行一次受限临时启动/恢复。** 源码草案0008-nuwa-dxe-allocation-trace.patch已完成，固定Mu_Basecore@cfb93724，只改Page.c与DxeMain.c：首次pool页搜索失败打印请求参数、类型bin、原始总空闲页/最大空闲块、各类型占用；最终架构协议检查失败前再打印快照，保留原断言与返回。Helper不分配内存、不调用GetMemoryMap、不改变map，前8条自由区间打印但汇总所有区间。严格git apply --check -p2通过，未实际apply/编译。patch SHAac8bd4763feddda9a7e5e6b0d179c3416531283137b75329965d5737bb6e32d9，完整原/候选hash见preview.json。

代价/限制：须新的核心/四EFI/FD/shim构建与严格产物检查；Mu原blob/补丁保留CRLF，现有CI正规化应仅对这两个目标作精确例外并检查raw/LF hash，不能直接沿用旧处理。日志仍走已有FrameBufferSerialPortLib，锁内打印和cache flush改变时序，非独立USB/持久通道；需要照片/录像。最大块仅raw值，尚未按alignment/guard裁剪，不保证能分配；不会直接得出所有成功分配的来源。源码静态通过不等于编译或实机通过。

**候选B：不加核心诊断，先基于同机原厂表审查恢复209.75MiB Heap。** 固件Heap从当前BAE00000/04500000变到原表BAB00000/0D1C0000有同机取证来源，但必须额外核对保留区、MMU/HOB、ABL交接与RamManager，不机械复制sheng/fuxi的额外bank。代价是改变可分配范围且未证明能解决碎片/guard/泄漏；需要单独可审阅的具体内存图diff和审批后才构建。本轮未改这些数值，也不把选择B视为立即批准未知内存图。

倾向A：先获取失败时实际资源量，减少无证据调heap的试验；同SoC仓已评估，作为来源之一而非nuwa运行证明。现无实际空闲量/最大块，相关值保留TODO。

**需要批准的最小范围：A对应这份两文件源码诊断、精确CI接线/独立新固件构建与产物审查、保持正确相对头及R-009空AUTO配置的同类v4临时包，一次试启动后恢复Android并确认boot_completed=1。** 不改board/bringup-plan、原内存图或任何基址/容量，不flash/erase/改槽，不加FAT/XNU负载，不置_verified=true。若需实体按键恢复按PENDING-HUMAN执行，继续独立证据工作；超出此范围另审查。当前尚未生成R-010镜像，A已批准，按新日志/恢复门推进。

## R-009 · 取消二级固件自动ABL链载（approved A，已完成本轮验证与恢复）

用户回复“批准”，承接上一条明确请求R-009 A，已批准候选A的源码、构建/产物、临时试启动及Android=1收尾范围；暂停解除。

执行结果：源码2ab6827d，首轮39819452729仅APT超时未编译；修正换源覆盖后39820752081成功，665项输入/产物检查、新RAW空AUTO与原PILDxe SHA通过。3153920B包b60f96c0完成唯一一次实机试启动，照片以候选专属GUID确认已到DXE；后续AllocatePoolPages失败、多个架构协议缺失、DxeMain.c(581)断言，BDS/XNU未到达。用户按键回fastboot后按D-016临时加载已验证Android备份，01:25:30实际nuwa boot_completed=1，三分区hash与试前一致。按用户“做完这笔实机验证就停下 写好文档”收尾，未切换B或继续修复。完整证据reports/pil-no-auto/39820752081/及对应operations。下方保留审批时方案，不作为新的待执行授权请求。

背景：R-008 A已完成头部单变量构建与两次临时试启动（第二次用户另明确要求录像）。新旧容器只差两个字节，修正后fastboot不再持续枚举，用户看见大量日志。照片清晰记录Pil_abl分区读取/ELF加载失败及uefipil.cfg自动处理panic；这不是XNU panic。同一帧没有NUWA-ENTRY，候选/原厂UEFI均含相关驱动，精确画面时序/来源仍待连续录像。**实际候选FD独立确认带[AUTO] ABL，源码配置问题无需猜测。** 取证与同SM8550对照见[本轮报告](operations/2026-10-23-relative-offset-trial-and-pil-stop.md)及reports/relative-offset/。

触发AGENTS.md§3第3类“新建或重写任何诊断 / 固件镜像”。R-008 A明确只复用旧FD，新PIL配置必须重建FD，超出其范围。Git/GitHub和可恢复临时试启动持续授权不重复请求。

**候选A（倾向）：保留PILDxe/PILProxyDxe，只取消uefipil.cfg的AUTO ABL项。** 源码预览0007-nuwa-disable-auto-abl.patch SHA f3d6d9c76a7e6ec2531a7bdbc2aa185a86ad74808c55f73eb6b63f05f462faaf已准备，对910ee079的git apply --check通过。只将RAW.inc的该配置输入切到nuwaPkg本地文件；本地文件来自实际同一FD的6868B原始配置SHA51facfcb…，只把[AUTO]下ABL行改注释，其他RETAIL、镜像定义、GUID、内存值逐字保留，未猜板值。先静态核实PILDxe空AUTO解析行为，再应用/固定来源，沿现有CI构建和独立产物检查，使用R-008修正shim打包同类v4临时包，临时对照后恢复Android=1。

代价：需要一次新FD/四EFI构建及容器检查；原配置RAW内容从FD提取、来源hash已固定，需核实空列表处理，不能把无崩溃预先当结果。UFS/BlockIo或其他Qsee/FeatureEnabler错误可能仍阻塞，BDS/UniXNU/XNU仍未验证；保留PIL不等于协议初始化通过。若解析不支持空AUTO，先报告并修正方案，不自动换B或改二进制跳过panic。

**候选B：参照sheng给PIL链建立独立条件门，本轮关闭PILProxy/PIL/SPSS三项。** UniXNU/uefi-sheng@0eb4514d在APRIORI与DXE中将三项包在SHENG_VENDOR_HW条件内，默认0；fuxi@bb25ad75最小链无PIL且尚未记录真机运行。可以在nuwa中同时控制APRIORI/DXE而保留其余真实驱动，不照搬全部vendor=0。代价是需审计其协议消费者/DEPEX和SPSS初始化影响，改动范围和潜在硬件影响大于A；不能只删APRIORI而让DXE仍分派，也不能声称同SoC已实机验证。

倾向A：精准对应候选FD确有的自动Android ABL路径，保留已复用的真实硬件驱动。B是有同SoC结构依据的替代路线，不能无证据整体关闭驱动。两者均不修复/重刷ABL分区，不以取消一条路径证明存储可用。

**需要批准的最小范围：选择A或B对应源码改动、独立新固件编译与静态检查、保持R-008相对偏移修正的v4新临时包，并按既有可恢复授权试启动、最后确认nuwa Android boot_completed=1。** 不含XNU/新FAT负载、不改board/bringup-plan或原厂内存表/基址、不flash/erase/改槽、不设置_verified=true。当前Android=1，尚未应用0007或生成R-009镜像；连续录像待办不阻塞静态工作，暂停原因仅为新镜像具体范围。

## R-008 · 修正BootShim的相对text_offset并做单变量试验（approved A，已完成）

用户在R-008具体方案提交后回复“授权通过 继续主线”，按倾向A执行；新shim/复用FD打包及一次临时对照/恢复范围获批，不扩展其他硬停项。

结果：固件源码910ee079已发布独立分支，WSL只编译112B shim；新包8b420abe与R-007包仅offset4106/4107不同，FD9ea347a4完全复用。两次临时启动（第二次用户明确“你直接启动就好 我随时录像”追加授权）均OKAY、15次fastboot均false；用户提供Qualcomm PIL/ABL错误照片，不能据此称XNU panic或确认候选SEC阶段。两次恢复检查分别00:41:49/00:43:49实际nuwa Android=1，记录均无临时原boot下发，回返机制未确定；三个Android分区hash与试前一致。完整证据reports/relative-offset/及本轮operations。下方保留审批时背景与候选；新FD另列R-009。

背景：本机abl_a/b SHA38a837fa与只读备份相同，安装UEFI QcomBds的变量发布代码和ABL消费代码已静态核对。现有shim头把绝对FD_BASE=A7100000写入相对text_offset；若普通平台分支成功读取原厂Kernel变量，装载地址会算成14F100000，越过B8000000末端，在CopyMem之前返回EFI_BUFFER_TOO_SMALL。**这是一条有条件的静态诊断，运行变量/实际错误码仍未验证**。ACK在BootLinux之前发出，不能排除早退。logfs/minidump只读取证未得到可归属R-007的实际错误。详见[完整证据](operations/2026-10-23-abl-handoff-and-relative-offset.md)。

触发：AGENTS.md§3第3类“新建或重写任何诊断 / 固件镜像”。R-007 A只涵盖已完成的SEC阶段诊断，新BootShim头修正/新容器超出该具体范围。已有Git/GitHub及可恢复临时实机授权持续有效，不请求重复授权这些通用动作。

**候选A（倾向）：只修正相对偏移、复用同一FD，生成并临时试启动一个对照包。** 源码草案0006-bootshim-relative-text-offset.patch已完成，SHA7409eecd0c6956becab01f7efb426cde2437de807ec5ebbf15f8a286058adf05。只把头字段`.quad FD_BASE`改`.quad 0`，FD_BASE拷贝/入口目标A7100000、image_size和指令保持；source-only preview及git apply --check通过，尚未实际apply或编译。固定基线5e4a8c8，复用R-007 FD SHA9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf，避免重新构建FD引入其他变化。

代价/验收：需重编112B shim、更新旧头值检查门和打包输入清单，对比确认除头text_offset八字节范围外shim逐字节相同，FD SHA相同，复用原v4头且只按既有规则更新kernel_size，不增加DTB/ramdisk/FAT/XNU；记录真实新SHA，不预填。再按D-016重新进入bootloader、筛选nuwa、临时启动及观察/采样，恢复前再复位bootloader，加载已验证Android备份并确认boot_completed=1。风险：没有运行变量/PC证据，该修正可能仍黑屏；显示/SEC/更后阶段问题仍可能存在。不得因新的ACK声称进入SEC或XNU。

**候选B：暂不生成新镜像，继续解码现有minidump并寻找独立运行观测。** 本轮96MiB minidump含五个Raw_Dmp!头，但明文筛选无相应加载错误；下一步需解析各段/会话与可能压缩内容，或核实BootLinux错误的其他可读出口。代价是时间与产出未验证，旧记录可能根本不包含R-007；boot-only易失变量也不能靠Android efivarstore追溯。优点是避免新试验，若取得实际拒绝码能减少条件假设。不会直接占用Android ramoops或发明USB/RAM地址。

倾向A：二进制控制流与同机表已有明确对应，补丁只纠正一个协议字段；复用同一FD可把新变量限定到头部，实验成本小于重新开发日志通道。B保留为黑屏持续后的取证路径，不把A成功预先写入结论。

**需要批准的最小范围：A这一份源码补丁、相应shim编译/静态核验、复用已锁定R-007 FD的受限v4新容器，以及按既有可恢复临时启动授权进行一次对照并恢复Android=1。** 不改任何board/bringup-plan内存或基址，不修改FD目标/原厂内存表，不flash/erase/改槽、不含XNU负载、不置_verified=true。当前手机仍在Android=1，本轮未生成新镜像。

## R-007 · 新SEC阶段诊断镜像（approved A，构建/试启动/恢复已完成）

背景：独立固件CI39805110487的四EFI/FD/BootShim及665项下载产物静态检查通过，但旧v4实机仅黑屏，未定位BootShim/SEC/DXE。新FD含Darwin22加载器修复，但不含XNU；不能期待该ABI修复本身解决未到加载器的黑屏。既有R-004 A只覆盖固定接线构建与审查，新SEC诊断改动和新boot容器超出这次已完成范围。触发AGENTS.md§3第3类：“新建或重写任何诊断 / 固件镜像”。

**候选A（倾向）：生成有限SEC阶段标记诊断版，沿已有可恢复授权临时试启动。** 源码补丁0005-nuwa-sec-stage-trace.patch已准备，固定原SEC LF SHAfd28b903，补丁SHAae5d5e16，patched SHA6af8dd4d；RAM应用与git apply --check通过。只在既有帧缓冲出口增加六个阶段WARN与阶段返回状态/已有x0值，并移除SEC全屏清零以保留文字；原SMMU、内存、HOB、解压和DXE调用不跳过，不增MMIO/内存地址。完整范围见operations/2026-10-22-dedicated-firmware-build.md和sec-trace-preview.json。

代价/限制：需另一次四EFI/FD/BootShim构建、独立静态检查及新v4临时boot容器；仍依赖面板显示，不能导出USB文本或定位ABL/BootShim/最早汇编，未显示时结论仍有限。打印与flush可能改变时序，不能把实验版当生产修复。后续试启动需用户查看屏幕，按D-016隔离bootloader状态，结束恢复Android=1；不刷分区、不改槽位。

**候选B：先完成独立USB日志驱动与早期RAM记录/回收，再生成诊断镜像。** 优点是DXE可向电脑回传文本，具备证据的RAM通道才能补早期日志；代价是USB描述符/事件/PHY角色、RAM所有权/cache/跨重启回读需实际开发与验证。当前没有安全缓冲区/持久回读证明，Android ramoops与固件FD重叠，不能直接选用；只做DXE USB仍不能覆盖更早入口。未实现、未估计完成时间。

倾向A：已有可审查的单文件补丁与匹配的当前splash保留区证据，先以有限范围缩小SEC的平台初始化/内存/解压阶段；不承诺一定可见，若仍黑屏再转独立通道/ABL交接排查。

**需要用户批准的最小范围：A这一份补丁对应的诊断四EFI/FD/BootShim生成及静态审查，并仅复用原厂已接受的v4头重新打包raw shim+FD临时容器（只更新kernel_size，无新增DTB/FAT/XNU）；临时设备操作沿既有可恢复fastboot授权，执行前重新核对nuwa和原厂恢复源，结束恢复Android=1。** 不包含v1大ramdisk对照、FAT/内核预链接、任何board/内存/地址/slot/flash/erase或_verified=true。新容器的完整SHA待获批构建后记录，当前不编造。

用户明确批准：“批准 R-007 A，继续构建 SEC 阶段诊断固件、检查产物并准备临时启动包，按既有授权试启动，结束后恢复 Android 并确认 boot_completed=1。”暂停解除；源码5e4a8c8/CI39809636575真实构建与产物检查通过，v4诊断包fbb7940a已临时试启动。Sending/Booting OKAY、用户“fastboot之后黑屏”、15次采样fastboot持续可见，SEC/DXE未验证。按D-016重新进入bootloader后临时加载已验证Android备份boot，00:09确认nuwa Android boot_completed=1；boot/vendor_boot/init_boot三个分区SHA与试前相同。实际结果见reports/sec-trace/39809636575/trial-summary.json及对应operations。Git操作已有持续授权，不重复申请。

## R-004 · 加载器候选编译与产物审计（approved A，已完成）

用户明确批准：“批准 R-004 的 A，继续编译 EFI/FD 和 BootShim 并检查产物”。本轮按A完成：CI39764322744成功，四EFI/FD/BootShim下载静态检查通过，见operations/2026-10-22-firmware-candidate-build.md；以下保留原候选与边界。暂停解除，不再请求同范围批准。

触发来源：本仓 AGENTS.md §3 第3类“新建或重写任何诊断 / 固件镜像”。Git/gh/workflow授权已明确，不重复请求；这里仅请求新的EFI/FD/BootShim产物生成范围。审批时尚未编译或生成这些产物；当前完成状态见上文。

背景：CI15自己的8796内核已链接ArmCpu/ArmDTPlatform。三份源码候选补丁完成了BootShim头修正、四模块DSC/FDF/包路径/库接线，并将sheng的initrd发布模块裁剪为只读BlockIo，去掉AddMemory/GCD扩展。75项静态检查及两来源树git apply --check通过；内核、来源、补丁、board/feed哈希固定。详细变更和来源见 [接线报告](operations/2026-10-22-loader-source-integration.md) 与 config/loader-candidate.json。

原厂表已独立提取，DXE Heap209.75MiB，隔壁的6GiB高地址Conv和AddDynamicMem转AddMem不能直接继承。尚无nuwa最终UEFI map和initrd保留/映射证据；四模块真实编译、FV容量/分派也尚未验证。本项不询问已作废容量选择。

**候选 A（倾向）：先只构建加载器固件候选并静态审计产物。**

最小范围：允许在独立GitHub Actions临时源树中，使用清单固定的mu-nuwa-firmware、UniXNU和uefi-sheng输入及三份补丁，生成四模块的EFI文件、nuwa FD和BootShim编译/头校验所需二进制；下载后核对模块GUID/DEPEX/协议依赖、FV大小、FD大小及shim头/拷贝长度，保存日志、输入版本和哈希。沿用固定固件来源的Resources/Configs/nuwa.toml及内存表，不改board/feed、内存/地址、设备槽位或_verified。只生成构建验收用产物，不打Android boot.img、不生成预链接/负载镜像、不执行fastboot或将固件送上手机。实际kernel payload仍固定CI15，完整预链接待另外完成。

代价：需要一次固件CI，可能暴露Mu/EDK版本、库依赖或3MiB FD空间问题；产物不能因此称可启动。若需要改地址/容量或扩展镜像范围，继续单独提出具体审批，不自动扩大。收益：先把可编译性与布局问题从内存策略、XNU运行配置和设备问题中分开取证。

**候选 B：推迟所有固件产物，继续源码/ABI与内存语义审查。**

在当前三补丁基础上继续检查Darwin22运行provider/时钟/回调、NativePrelink编码、原厂动态内存语义和initrd生命周期，期间不生成EFI/FD/BootShim/boot镜像。代价：实际EDK依赖、FV容量和模块格式错误仍要到后续构建才能发现，不能靠静态审查验收；最终运行map仍可能需要单独获批的实机验证。

倾向 A：源码候选已具体且可审阅，先获取真实编译证据能缩小后续调试范围；不会把旧内核/旧FD混进来，也不会继承隔壁的容量批准。**需要用户批准的最小范围就是A所列固件构建与静态产物审计；设备执行、board内存/地址变更及完整boot.img均不在其中。**

## R-005 · 恢复核对后准备固件入口包（已授权范围内实施，完成准备）

授权来源为用户“可以随意推送镜像，只要能恢复回fastboot”及“先核对恢复路径和DT/initrd映射，再准备试启动包”，无需为同范围生成/临时原厂恢复重复询问。本项记录具体实现选择，不声称用户逐字选择过下面字母。

候选A（本轮采用）：先临时加载哈希锁定的原厂nuwa boot恢复Android，再复用已被ABL接受的v4原厂头，仅改kernel_size，装入本仓验收的raw shim+FD；DT/原始ramdisk走现有vendor_boot，无新增FAT/XNU。代价：候选实际ABL放置、SEC DT访问和DXE仍需实测，原厂临时恢复不修复持久A槽标志。收益：已知头与恢复源可核对，避免编造legacy基址。

候选B：沿固定Mu的v1/gzip/附加DT/5B ramdisk配方生成。代价：上游DT含旧initrd属性，参考日志有Load Error且缺目标身份；mkbootimg默认base与参考仓不同。需额外核验，不能直接称比A可用。

A的输入、实现和报告见operations/2026-10-22-trial-boot-preflight.md。当前仅原厂boot临时恢复实机通过，新的3153920B固件包只静态检查通过；没有执行新包、flash或改槽位。board/内存字段和_verified审批仍独立，H-001未验证。不新增open审批项。

## R-006 · 已准备v4固件入口包临时启动（approved，已执行并恢复）

用户明确批准“临时启动咱们已准备的v4固件入口包，检查ABL、SEC和DXE/BDS的实际结果”。最小范围为SHA12864ac6…的既有3153920B包单次临时启动、只读观测及原厂ef558db2…恢复；不生成镜像、不flash/erase或改槽位。

候选A（获批执行）：对已核对nuwa执行fastboot boot现有包，记录屏幕/USB/命令，结束回Android。代价是现有日志通道有限，黑屏可能无法定位早期阶段，需原厂恢复。

候选B：先停留只读源码/入口与日志通道审查，再准备后续有观测手段的实验。代价是推迟现有包的命令接受结果，后续新增诊断范围另具体落实。

本轮A结果：Sending/Booting OKAY、黑屏、约29s内15次采样fastboot始终可见；SEC/DXE/BDS未验证。直接原厂恢复先Load Error，reboot bootloader后同一原厂boot成功，最终nuwa Android boot_completed=1。见operations/2026-10-22-v4-firmware-trial.md和reports/v4-firmware-trial/。未以ACK替代阶段通过，未置_verified。

## 后续授权记录（2026-10-22）

用户追加：“这个设备日常不需要用 可以随意推送镜像 只要能恢复回fastboot就行”。后续镜像推送/试启动在可恢复fastboot条件下已有授权，无需重复请求相同范围许可；优先临时加载并依据具体镜像、分区和恢复证据决定是否写入，不把此授权当作任意底层分区擦写可恢复的证明。H-001实体键恢复演练仍未验证；只差按键的项保留PENDING-HUMAN并继续软件工作。该授权不替代board/bringup-plan内存/基址审批或_verified实证。本轮仅完成R-004产物检查，未推送或启动镜像。


用户在官方CI接入核验后指定GitHub账号`wh1stl3`，确认目标仓库尚未创建，并明确“Git的所有命令都允许”。此前仅允许status/diff/log/show的Git命令限制已解除，不再为云端checkout/clone/apply范围重复请求批准。两个旧仓及上游来源树仍只读；四类硬停、feed不变、未知板值TODO及证据纪律继续有效。Actions主机方向见DECISIONS D-008，R-003 A保留为历史审批记录。

用户随后进一步明确：“有关Github的命令以后都无需问我要授权 都允许”。这是持续授权，不再重复向用户请求GitHub操作许可；不解除四类硬停或只读资料库边界。

## 审批记录：R-003

### R-003 · WSL工具链与Darwin22构建路线（approved A，第一阶段进行中）

用户本轮选择A，批准保留WSL的工具链预检/适配第一阶段；并确认没有额外Linux clang、IIG或sysroot输入。继续本仓内工作，原暂停解除；来源树、Git、feed、board和镜像边界保持。预检与非执行式适配计划已落地，9项自身测试通过，现有MIG后端代码生成及宿主头文件语法样例通过；完整工具输入仍未落实，详见[本轮报告](operations/2026-10-22-wsl-firststage-adapter.md)。以下保留审批时背景与候选。

触发来源：用户本轮第2项明确要求“要么拿出可在本机跑通内核构建的证据，要么列为不可行并写进docs/NEED-REVIEW.md……后停”。这次停下不是新增板值审批，也不是认为WSL先天不能构建XNU。

**现状结论：当前本机输入、现有基座入口和不执行Git写操作的约束下，直接完成8796内核构建不可行；没有完整内核构建通过证据。** 主线暂停于工具链门，未启动默认clone/apply入口。

背景与证据：

- [审查报告](operations/2026-10-22-darwin22-interfaces-and-wsl.md)及 `reports/darwin22-audit/interfaces.json`：8796产出.unstripped，多个基座消费者使用.unstripped.noctf；archive/编译记录生产者仍绑定Darwin23/ios17或来自sheng；13项回调只在参考树找到实现。NativePrelink kmod局部布局静态一致，但目标符号/完整ABI未验证。
- `reports/darwin22-audit/wsl-toolchain.log`：WSL可运行；默认clang14对三项XNU内建的__has_builtin探测均为0；xcrun/xcodebuild/IIG等不在PATH；有限范围没有找到已验证SDK。已有Linux MIG/cctools prefix与Python3.12可复用，没有被误判为缺失。
- watchdog参考实现有非union环境路径的scratch重叠风险；不能用导入sheng archive绕开接口适配。
- board仍example=true，feed未改。两个旧仓及上游源树保持只读，没有生成镜像或操作设备。

**候选 A：保留WSL要求，先建立经验证的Linux交叉构建输入与无Git写入适配器（倾向）。**

第一阶段交付应为：含所需XNU内建的Linux ELF编译器与版本/哈希/特征证据；MIG/IIG与宿主工具的Linux生产链；明确目标/宿主sysroot；设备仓中的8796产物/编译记录/archive调度适配设计。只用常规clang14或仅包一层xcrun脚本不算通过。随后才讨论完整源内核编译，必须单独提供真实compile/link日志、产物格式/符号检查，不能用生成数据库替代。

代价：需工具链移植或宿主提供已构建工具、对应头文件/sysroot；IIG、XNU内建与编译记录生成均是实际工作，时间和成功率未验证。还需宿主明确提供独立可写补丁应用视图，或另行批准构建视图方案，不能修改只读来源、在本仓复制整份上游源码或调用Git写命令。优点：保持当前所有构建在WSL的边界，避免引入第二个构建主机。现有Linux MIG/cctools可复查后复用，但不继承旧P16/SWEET内核结论。

**候选 B：批准仅内核与archive编译改用macOS/Xcode主机，WSL保留编排和证据审计。**

以同一8796输入和设备仓补丁选择集在用户提供的macOS主机/受控执行环境构建；回传编译记录、archive符号报告和内核哈希。本地只做读取、验证与后续集成。使用基座已有Xcode调用方式可减少宿主工具移植，但仍须修正8796产物名/版本依赖、重建driver/回调、处理watchdog风险，并核验编译器内建与SDK，不能把“有Mac”当作8796已通过。

代价：显式改变“构建全在WSL”的边界，需要额外主机/执行环境及传输、版本固定、成本与可复现性管理；主机是否可用、费用和交付时间均未验证。当前没有启动任何远端任务或外发源码/凭据，也没有新建CI workflow。

倾向 A：符合用户既定WSL主线，并能把缺失输入与接口门槛逐项验证；若用户优先减少宿主工具移植工作，B是需要明确批准的替代路径，不自动切换。两条路径均保留iOS16/iPhone donor与4KiB，均不使用iOS17 donor绕过问题。

**需要批准的最小范围：选择 A 或 B 的方向与第一阶段范围。** 选择A仅批准本仓内无Git写入的工具链预检/适配工作及输入清单落实；工具安装、外部目录写入、来源树复制/覆盖视图等需明确范围后才做。选择B需明确批准macOS内核构建例外，再确认可用执行环境，不能直接启动外部任务。

本项不请求解除Git只读限制，不授权feed切换、board内存/地址修改、移除example保护、镜像生成、设备动作或_verified=true。原暂停已由用户选择A解除；工具链输入未落实时不能宣称构建可执行。

## 审批记录

### R-002 · 首版设备描述（approved，已落地）

用户本轮回复 A，批准候选 A 的精确范围。已创建根目录 board.toml，内容与下方获批代码块逐字一致（忽略末尾换行）。没有填写内存/地址、额外IPSW字段或prelink值；example=true 与 ipad_identity=true 保持。以下背景与候选保留为审批记录，不再是 open 待办。

审批前背景：49项检查已复现38通过/11失败，D-006继续适配8796。当时本仓没有 board.toml；基座 `scripts/unixnu/config.py:73-79` 在读取模块前就要求该文件和板名。用户本轮第六条明确把 **IPSW身份** 列为硬停字段，因此即使 donor 已定，也先提交具体写入范围再停，获批前没有创建 board.toml。

候选 A（倾向）：创建下列不可构建的最小占位文件，只写已定产品身份；未知项用注释 TODO，保留缺失而不填假的数值。代价：可以为后续 status/模块解析准备入口，但不能构建、生成ADT或镜像，完整性仍不合格；`example = true` 也会拒绝 build/bootimg（`config.py:101-103`）。

```toml
[board]
name = "nuwa"
soc = "SM8550"
description = "Xiaomi 13 Pro / iOS 16 bring-up"
example = true
# TODO: kit，尚无经审查的nuwa平台kit，不能照抄sheng实现。

[ipsw]
product = "iPhone10,3"
version = "16.7.16"
build = "20H392"
device_class = "d22ap"
# TODO: url/chip_id/board_id/sha256；缺donor BuildManifest及组件哈希核对。

[payload.adt]
ipad_identity = true
# TODO: tool/chip_id/cpu_regs/psci_method等，待nuwa ADT来源核对。
# TODO: owned_memory_size，缺UEFI可用连续区证据；D-002先512MiB–1GiB，上限8GiB。
# TODO: [payload] dram_size，物理DRAM描述尚需核对，不能当作窗口大小。
# TODO: [userdata] LBA与lba_bytes，缺本轮GPT证据核对。
# TODO: [kernel] defconfig/archives，缺8796配置及Darwin22接口审查。
# TODO: [kernel.prelink] 全部数值，缺donor kernelcache分析；不借sheng/fuxi值。
# TODO: [firmware] 配置/路径，uefi-nuwa尚未建立。
# TODO: [bootimg.image] 地址/offset/pagesize/header_version，缺nuwa装载证据。
```

这些都是官方现有键；TODO注释不作为TOML字段，不引入新schema键。身份依据 D-004，安全属性依据官方摘录与 D-004；schema依据官方摘录§2及上述本地基座入口。未声明完整板级配置静态检查通过。

候选 B：暂不创建 board，先完成8796补丁覆盖、NativePrelink/接口审查和donor manifest核对，再一次性审阅更完整配置。代价：模块状态只能继续静态阅读，完整 board 仍要等待UEFI内存/bootimg证据；优点是减少占位文件的后续修改。

倾向 A：已定身份有明确来源，`example=true`限制构建，能以最小配置为设备仓接入做准备；不提前选择任何内存/基址值。

**请求批准的最小范围：仅创建上述 A 的 board.toml 内容。** 不包含内存/地址数值、bootimg字段赋值、其他IPSW字段、prelink值、镜像生成、Git写操作、设备动作或任何 `_verified=true`。若批准仅对此范围落地，后续触及其他硬停项仍单独审阅。原暂停要求已由用户选择 A 解除；批准只覆盖上述最小文件内容。

## Closed

| 编号 | 主题 | 结论 |
| --- | --- | --- |
| R-001 | 内存窗口怎么声明（nuwa DRAM 不连续 11.22 GiB） | **answered by D-001 → 修正为 D-002**：单窗口为硬约束，排除「14 段全给」；原 A 提案区间不连续，不成立；首选主 bank `0x8c0000000` / 9216 MiB，退路 A′ 768 MiB。详见 `DECISIONS.md` D-001 |
| R-002 | 首版 board.toml 最小占位 | **approved，已落地**：用户选择 A；精确内容见上方及根目录 board.toml，未授权其余硬停项。 |
| R-003 | WSL工具链路线 | **approved A，范围已明确**：用户保持WSL主线；本仓预检/适配计划已落地，工具输入仍未落实；未批准安装或其他目录/源树写入。 |
| R-012 | ADT 的 `dram_size` / `owned_memory_size` 取值 | **approved A，已写入**：`dram_size = 0x240000000`（实机 FDT `/memory` 最大连续段，与 D-001 吻合）、`owned_memory_size = 0x40000000`（D-002 首版窗口上界）。board 仍 `example = true`，窗口可用性未验证。 |
