# v24：一次性加密 kernel_bootstrap 可见路径

用户要求继续主线，在可见路径内一次性做密。沿用 PROBE16 已实机确认的 kernel_bootstrap 入口，新增四个真实函数内部的调用边与后继指令观察，不跳过 VM 初始化、不修改内核参数。

## 布点与读图

固定 INPUT SHA 为 1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6。扫描固定二进制的 `_kernel_bootstrap`、`_vm_mem_bootstrap`、`_vm_page_bootstrap`、`_pmap_startup` 函数范围，选择 79 个原生 BL 调用，每个调用前和后继指令各一个编号，共 158 个点。相邻调用共享补丁位置，合计新增 150 个补丁位置，最终 199 条记录补丁。printf/kprintf、早期 debug 字符串、参数解析和直接 panic/Assert 等调用不单独编号；冷路径函数调用仍可见。不是所有内核调用的全覆盖。

右侧网格起点 x832/y256，10 列、格距 48×32，每块 32×24，最大 y759；原左侧阶段块与 x256 的 A 字段保留。ID 从 0 起，位置为 x=832+(ID%10)*48、y=256+(ID//10)*32。偶数为蓝色调用边，奇数为绿色后继指令。完整对应表在 build.json 的 dense_bootstrap.edges 中，并绑定进镜像报告 probe_screen。

蓝色只说明执行到调用前探针；绿色说明执行到原调用后继指令，不单独证明对应调用返回。模型实际出现了 ID117 亮而 ID116 未亮、ID157 亮而 ID156 未亮：原代码的其他分支共享后继位置，不能误报 fillPage 或 cold.1 已运行。目录用 continuation 而非 returned。编号按函数分组，不是时间顺序；每点只画一次，不表示次数或每次调用都成功。后续内核绘图可能覆盖网格，未亮不能单独作为停点证明，也不能由这些点推导子系统正确、调度器运行或 iOS 启动。

## 指令与映射

探针保存渲染器使用的 x9–x28 和 NZCV，渲染不改 x0–x8/x29/x30。BL 通过恢复原生 x30=调用点+4 后 B 到原函数，函数收到原始返回地址；没有把返回地址改成探针内部地址。ADR/ADRP 按原地址独立重算，条件分支保留原条件与两个后继，普通指令重放。禁止直接复制 PC 相对指令编码。

新增 flag 使用 128–285，与旧标记分开。代码增大后继续由 v22 跨 TTBR 映射逻辑逐页映射，代码 RO/X、数据 RW/NX；不修改 TCR、板值、owned window、donor 或资格标志。

逐指令单元夹具为合成寄存器的寻址范围补充 0x100000–0x10ffff RAM，原生指令和探针共用同一夹具；这不是冷启动模型的内存修复。连续冷启动仍只使用既有 1 GiB owned window、真实装载布局和页表，不代写正常路径页表，不跳 PC。

## 已完成的离线验证

- 两次新目录构建均为内核 6110c6fba2579eca0e3dfe84bd87a03869685645e98d6fbb75faa2b2a368e09b，58,404,864 B；donor/prelink 段逐字节不变，未记录原字节改动为零。
- 692 项逐点差分通过：173 个普通补丁位置，各首次、重复、无视频、饱和 flag 四场景。比较 x0–x30/SP/NZCV/下一 PC、原生内存写入、调用者栈；逐个校验编号点的实际像素及所有屏幕写入范围。
- 42 入口/MMU、18 读数、5 WFE、6 静态地址 walk、5 ParseKernel、8 稀疏阶段、2 异常检查通过。
- 最终镜像同一 ADT 的四个页表切换场景共 12 断言，6 个 console 策略检查与 v22 旧 BCM 读失败负对照通过。
- 20 项绑定检查通过，新增删除编号、篡改坐标、降为 revision23 后重新封摘要均被拒绝。资格标志仍为 false。

包为 PROBE17，镜像 e3b8e0224a0f4f0421927780e2257fda0d892a6cecf1d153c94f3868bbd71aea，70,266,880 B；ADT 572c4dbb22009ceae9fc27f1c61e3e5f4208f7db377b2a52cca32a18315127b5。构建/测试报告在 reports/kernel-entry-probe/2026-10-25-v24/；包报告 reports/xnu-first-entry/entry-probe-17.json。

## 连续 VM 路径与下一步

连续模型的进一步运行单列 bootstrap-forward.json。6000万指令进入 vm_page_release_startup 133,696 次，停止在 _pmap_startup+0x360，error=null/bad_memory为空。采样 x0 从 0xfffffff07aeef000 单调推进，每16,384次增长0xc0000，即每个 vm_page 对象48字节。这是正常推进的直接模型证据，支持此前20M预算不足，不能将其称为已证明的死循环。未证明实机也处于该循环。

必须按报告实际 stop/error/release_count 解读，不把预算耗尽认定为完成。源码 `osfmk/vm/vm_resident.c:1538–1585` 显示逐页初始化及释放循环，1574/1582 调用 vm_page_release_startup；应优先核对页对象参数推进，而非仅看最后 PC。

延长至1.2亿指令，页释放累计240,085次，出现 pmap_startup 后继点97、vm_page_bootstrap后继点63及zone_bootstrap调用点64。预算结束位置为 `_ccsha256_ltc_compress+0x184`，error=null/bad_memory为空；zone_bootstrap后继点65未出现。模型已越过页初始化/释放阶段并执行后续路径，不证明zone完成、真实计时/中断可用或实机同样推进。原始结果见 bootstrap-forward-120m.json。报告目录里早期重建仍使用 returned 字段名，最终 build.json/build-final.json 已统一改成 continuation；三份重建内核字节相同，没有为文字修订改指令。

最终镜像回读核验通过，build/软件/切换/console 摘要已绑定最终目录；20项绑定反例复验通过。脚本执行命令和夹具边界汇总在 execution.json，原始 stdout/stderr 留 out/probe-v24-analysis。所有检查均为离线模型或静态检查，无设备动作。

离线里程碑提交75daa59。随后用户明确PROBE17录像/按键恢复就绪；17:11:45北京时间刷新Android完成1/A槽/三SHA并与PROBE16试后记录逐项一致。即时通知后17:12:30完成单次临时boot ACK，等待用户菜单电源Enter后的画面。最高实机阶段仍为PROBE16 kernel_bootstrap入口，本包阶段、恢复与三SHA后验待补。无固定180秒，不以ACK计内核时长。原始音视频和截图仅本地，无push。

复现命令按 scripts 的 --help 及本目录报告所列参数执行，所有脚本串行。典型续跑：

```powershell
python -B scripts/test-probe-transition.py --build reports/kernel-entry-probe/2026-10-25-v24/build.json --adt out/trial-boot/xnu-entry-probe-17/kernel.macho.adt --explore-bootstrap --instruction-budget 60000000 --output out/NEW-bootstrap-forward.json
python -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-17.json
```
