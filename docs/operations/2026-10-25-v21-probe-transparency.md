# v21：恢复探针语义，再继续内核推进

2026-10-25。承接用户“按照建议继续推进”。本轮在原有v20未提交工作区上修复，不回滚既有改动；未改板值/固件/TCR/内存声明/donor/认证/_verified。本轮随后已单次临时启动并完成恢复闭环（见末节）。沿用此前不commit/push约束，交付保留在工作区。

## 结果与边界

在独立新目录重建得到相同SHA（reports/kernel-entry-probe/2026-10-25-v21-reproduce/build.json）。

候选内核SHA256 `0c1594215b534434221ddd16f10a8da6e4162bcc2d614d321f297425373723c4`，58,363,904 B，45补丁；包entry-probe-14的镜像SHA256 `42b42624460d5f0b974e4315bc50d615dce6111514184815724d2040adbd509f`，70,266,880 B。`reports/xnu-first-entry/entry-probe-14.json`绑定最终回读的FAT/内核/ADT与7份证据文件摘要；静态包报告保留构建时的device_executed=false；真实设备结果独立保存在trial报告。

核心缺陷是原ADRP编码移动到新PC后读错地址，而非另一个同名全局。旧v19/v20局部执行：真实解析器在-v上返回未找到，选择events/sec=1000000；19.2MHz得到ticks=19、eventi=4，init的错误ADRP却使比较读取0x5f006570并进入同一panic。恢复原址原首指令即可返回。当前v21显式ADRP重定位后读4并返回；实机是否还有别的问题须本包对照，未宣称唯一根因。

其它修复：
- CBZ显式区分taken/fallthrough，再用可达的B跳回原目标；直接重编码CBZ会超出±1MiB范围，因此不能只改其目标符号。
- MMU后C钩子保存x9-x28及NZCV，绘图结束恢复后再执行原指令，保留SP与原native栈写入。
- 每个阶段独立flag；字符串字面量按__TEXT完整16字节范围检查，不要求页/8字节对齐；panic先记录原始指针/整数变参，后选择性读取字符串。
- 字段标签与读数置于800行以前；显示快照至少要求800行、736像素stride，pre-MMU小tile单独要求最小stride。
- init入口读32位eventi并记录目标全局地址，配置入口的FFFFFFFF明确标为初值而非被panic拒绝值。

## 离线证据

目录 `reports/kernel-entry-probe/2026-10-25-v21d/`：

| 文件 | 结果与覆盖 |
|---|---|
| software.json | 42项，真实入口连续穿过MMU/负对照/占槽/无framebuffer |
| transparency.json | 88场景，22个已安装C钩子×首次/重复/无视频/计数饱和，比较全部GPR/SP/NZCV/PC/native栈写；CBZ两条路径；所有framebuffer写位于200..799行 |
| wfe.json | 5项：真实配置/解析/init，在-v、wfe=0、19200、2000000分别得到4/24/9/4并返回；旧v20作为负对照仍在全局为4时panic |
| read-sites.json | 18项，植入值的地址/宽度/字模/字段ID；这是渲染测试，非运行时值证明 |
| post-arm-init.json | 8项，真实连续候选带正确ADT偏移，进入arm_vm_init；停于_bzero+0x1c，FAR=0x8d01d8000，超出夹具RAM覆盖 |
| post-arm-init-handler.json | 2项，异常处理器合成执行/读数，不等于发生过实机异常 |
| mapping.json | 6个地址软件页表walk，包括新增探针页与framebuffer |
| loader.json | ParseKernel实际C函数体ASan/UBSan，原始/候选接受、三个畸形拒绝，共5例 |
| binding.json | 10项：完整包接受；缺少任一新增证据、删差分/WFE场景后重封摘要、篡改software摘要、降低revision绕过均拒绝 |

TPIDR_EL1 shim是有意行为改变，透明性测试不把它当作不变项。连续阶段测试以前钉死_cpu_number+0x10，修复临时寄存器保护后前线已变化：现在用实际观测点验收arm_vm_init，在white点验收shim/VBAR。没有跳过系统寄存器指令或伪造执行位置。停止时已发生非法访存的事实保留在报告，不把8项通过写成整核通过。

模型仍使用synthetic boot_args/topOfKernelData与稀疏RAM；未映射的bzero目标不能拿来修改实机内存参数。后续先按真实加载器布局扩展夹具，再继续分析；不因模型覆盖缺口修改内核。

## 屏幕判读

左侧tile宽96高32，原逻辑阶段y<800时保持y，>=800时映射到第二列x96，y=256+(logical_y-256)%512；与右侧数据分开。早期入口/页表/pre-MMU/cyan/white仍在x0,y256/288/320/352/384。

右侧x256处起：4位字段ID+16位值，共480像素宽、20行高；逻辑记录映射y=224+28*((logical_y-1088)/32)，counter独立y756，全部结束于y775之前。值从x352起。

| ID | 实际y | 含义 |
|---|---:|---|
| A022 | 224 | panic函数名首8字节（若指针合法） |
| A024/A025/A026 | 280/308/336 | ESR/ELR/FAR |
| A027 | 364 | panic函数名后8字节 |
| A028/A029 | 392/420 | panic格式串首16字节 |
| A02A/A02B | 448/476 | DTInitialized / DTRootNode |
| A02C | 504 | soc_base函数入口时的全局值，不代表返回值 |
| A02D/A02E | 532/560 | PE_state原始+0x90 / bootArgs(+0xa0) |
| A02F | 588 | configure入口timebase |
| A030 | 616 | configure入口eventi，可能仍FFFFFFFF |
| A031 | 644 | panic第一个原始变参 |
| A032 | 672 | init入口实际32位eventi，默认预期4 |
| A033 | 700 | 预期读取的eventi全局地址 |
| A034 | 728 | panic第二个原始变参（若是本panic，应为bit_index） |

pmap重建可能使诊断设备映射失效，后续无标记不能单独判停点。自动重入也可能让记录跨次启动残留，读数按录像时间顺序判定。

## 复现

Windows Python固定路径 `C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`，下列命令在D:/Code/PortingiOS/nuwa/UniXNU-nuwa串行执行。新建build须用新的out和reports目录；以下测试重跑会更新对应证据，已打包后应保留现有目录，复制到新目录重新绑定。

```powershell
python -B scripts/build-kernel-entry-probe.py --work out/kernel-entry-probe-NEW --output reports/kernel-entry-probe/NEW/build.json
python -B scripts/test-kernel-entry-probe.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/software.json
python -B scripts/test-probe-transparency.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/transparency.json
python -B scripts/test-probe-wfe.py --build reports/kernel-entry-probe/NEW/build.json --negative-build reports/kernel-entry-probe/2026-10-25-v20/build.json --output reports/kernel-entry-probe/NEW/wfe.json
python -B scripts/test-probe-read-sites.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/read-sites.json
python -B scripts/test-post-arm-init-markers.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/post-arm-init.json --adt out/trial-boot/xnu-entry-probe-14/kernel.macho.adt
python -B scripts/test-post-arm-init-markers.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/post-arm-init-handler.json --handler
python -B scripts/audit-entry-probe-post-mmu-mapping.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/mapping.json
python -B scripts/audit-entry-probe-loader.py --build reports/kernel-entry-probe/NEW/build.json --work out/kernel-entry-probe-NEW-loader --output reports/kernel-entry-probe/NEW/loader.json
python -B scripts/test-probe-evidence-binding.py --build reports/kernel-entry-probe/NEW/build.json --output reports/kernel-entry-probe/NEW/binding.json
```

负对照需要历史v20候选（SHA 1f517836...，路径见报告）；基线预链接输入与历史候选均为out外部构建依赖，二进制不入Git。

## 本轮实机命令记录（已经完成，不重放既有报告路径）

本轮已收到“可以，现在准备录像，也能按键恢复”的回复并执行一次；以下命令为历史记录。用户随后明确：无需固定180秒，实际以菜单电源键Enter触发，后续使用XNU scope默认0秒运输观察。

```powershell
python -B scripts/record-nuwa-trial-state.py --output reports/xnu-entry-probe-trial/2026-10-25-v21/preflight.json --package reports/xnu-first-entry/entry-probe-14.json --capture-confirmation "填写本次用户实际录像就绪回复"
python -B scripts/trial-v4-firmware.py launch --package reports/xnu-first-entry/entry-probe-14.json --preflight reports/xnu-entry-probe-trial/2026-10-25-v21/preflight.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v21/launch.json --observation-seconds 180
```

launch前即时通知，确认唯一设备、Android完成1、三分区基线与可恢复路径；严禁拿模板文字冒充确认。脚本不会替代用户录像。必要时按电源+音量下回fastboot，使用脚本recover阶段临时加载hash固定stock boot，恢复Android后用record-nuwa-trial-state.py --before复核三SHA。未知设备状态不启动。全部禁止flash/erase/改槽。


## 本轮实测与后续定位

2026-10-25 15:07:42北京时间，恢复Android完成1、A槽，三分区SHA与试前完全一致；无flash/erase/改槽。trial目录reports/xnu-entry-probe-trial/2026-10-25-v21/。用户照片原SHA24670ad5...，视频SHA b21ad90c...、时长4.036708秒；FFmpeg系统路径D:/ffmpeg/bin/ffmpeg.exe。视频拍到菜单→绿条→阶段色块与数据的转换，底部49秒菜单是残留背景，无返回固件证据。

人工视觉复核：A02F=000000000124F800；A030=00000000FFFFFFFF；A032=0000000000000004；A033=FFFFFFF00716E5F8。前者是配置前初值，后者是配置后的init读数。后续misc/cpu初始化及arm_vm_init内部+54/+a4/+108/+130色块出现，未见pmap/panic/异常记录；无记录不排除映射丢失后的异常。

进一步按加载器公式与真实包ADT构造完整1GiB owned RAM模型，没有更改候选/参数：argsPA8c4890000、treePA8c4891000、treeKVAFFFFFFF008491000、topOfKernelData8c4898000。真实冷路径可达pmap_bootstrap入口。arm_vm_init的0xfffffff0073beb60/_set_mmu_ttb_alternate先把TTBR1换成8c4899000，probe KVA已无映射；0xfffffff0073beb74/_set_mmu_ttb再把TTBR0换成8c4898000，framebuffer也无映射。这两步均早于pmap调用0xfffffff0073bef40。继续执行pmap入口的branch后，在probe_pmap=0xfffffff00848a1a8取指发生UC_ERR_EXCEPTION。

首要工程判断变为“诊断通道跨重建页表失效”，不是“还没到pmap”。模型有直接证据，实机实际ELR仍未获取。下一轮须同时保证探针代码RX、scratch/flags记录RW以及framebuffer Device映射；禁止只给renderer加守卫却保留未映射的探针入口。候选方案：在新根表受控保留诊断映射（最小诊断补丁，需权限/占槽/内存分配审计）；或把探针迁入真实受映射的原生文本/数据区（更规范，但需核对可用空间或源码构建）。先离线选型，不再用旧显示盲点判停点。

用户取消XNU固定180秒等待的指令已落实到trial-v4-firmware.py；其它固件scope保留原默认与范围。3项测试无设备命令，原有preflight/恢复门不变。本轮没有第二次候选启动。

归档补充：用户已于后续授权本轮本地提交，v21/v22代码与证据合并保存在597baed；当前最高实机阶段以v22记录为准。本文此前不commit/未启动等描述为当时状态，不代表当前状态；不push和原始音视频本地保留约束仍有效。
