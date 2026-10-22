# STATUS

> 当前唯一真相；更新：2026-10-23T02:51:01+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**用户已批准R-011 A。独立固件仓仅恢复同机原厂DXE Heap一行至209.75MiB，codex/nuwa-factory-heap@1ccf760已发布；原R-010诊断、PIL空AUTO、正确BootShim和其他内存区域保持。35项固定输入静态检查通过，已接入factory-heap独立CI配置，尚未编译或试启动新范围。**

上轮R-010实机DXE分配失败27次，最终空闲25页/100KiB、最大8页/32KiB、5段，DxeMain.c(586) Not Found断言；BDS/XNU未到。最近Android恢复完成1及三个分区SHA未变为02:30:04/05记录；本轮尚未切换设备状态。

[本轮报告](operations/2026-10-23-factory-heap-build-trial.md)，reports/factory-heap/；[上轮完整证据](operations/2026-10-23-dxe-allocation-build-trial.md)。

## 本轮源码与检查

| 项目 | 状态 |
| --- | --- |
| 固件源 | wh1stl3/uefi-nuwa@1ccf760d667b9eec6dd3491c90cc04ebb7c58340，父2ab6827d；新分支发布，旧分支保留 |
| 唯一源码差异 | MemoryMapLib.c:32的DXE Heap，BAE00000/04500000 → BAB00000/0D1C0000；209.75MiB，末端C7CC0000；其他行/属性不变 |
| 来源 | 同机xbl_config抽取表SHA2adc494b…；不是复制其他板地址；原/后LF哈希051c431a…/b6cfda2e… |
| CI配置 | firmware-factory-heap-profile.json，35项原始输入；沿用0008分配诊断patch4a859ab6、Darwin22 loader补丁、固定UniXNU75bc13dd和Mu cfb93724 |
| 实际产物门 | 从真实SEC TE按固定Name[32]/Address/Length布局读取Heap描述符，新值必须精确匹配；旧R-010 FD回归读出69MiB，通过 |
| 当前验证级别 | 源码/配置/旧产物回归静态检查通过；新FD、描述符、临时包及运行均未验证 |

候选原静态审查：其他源表行无区间重叠，历史同机Android DT覆盖候选，reserved reg/当时initrd均不重叠，未解析节点0。这不证明实际候选ABL x0 DT或范围运行所有权；实际MMU/HOB/分配/协议分派仍需实机对照。

## 下一步

1. 提交本轮设备CI接线并触发factory-heap构建；按实际首错推进。
2. 成功后下载逐项核验、确认实际SEC Heap=209.75MiB、DXE诊断/四EFI/SEC/PIL与正确shim保持，再打包同类v4。
3. 重新读取nuwa身份、Android完成1/三分区SHA，核对日志及恢复门；启动前通知用户录像，一次临时试启动后恢复Android完成1并对比摘要。
4. 结合实际快照看分配失败和核心协议是否改善；不预先认定扩Heap能解决全部SPSS/协议错误，不增XNU/FAT/新DTB或改其他内存范围。

## 已知实机与恢复基线

R-010 CI39829943950/c9d538f成功（6m51s），666项实际产物静态检查通过。FD d9c3eaa0、核心c0135047、v4包9197fed2。唯一一次临时启动最新清晰照片确认NUWA-MEM末阶段执行：27次失败、free=25 largest=8 ranges=5 special=0，2+3+6+8+6=25。上方type7=208页后1153页失败，但第一请求type/guard/align/caller头部不在画内，仍TODO。

用户按键回fastboot后等待脚本实际接管，复位bootloader并只临时加载原Android boot ef558db2；02:30:04实际nuwa/kalama Android完成1、02:30:05三个分区SHA与试前相同。当前原有rooted/custom Android，非完整原厂恢复，A槽标志未改。H-005完成；H-001独立按键演练/H-003历史可选连续录像不阻塞本轮静态工作。

## 内核和固定边界

基座wh1stl3/UniXNU@76dd641保留nuwa补丁；8796内核CI39793231214成功，源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。Darwin22/4KiB段起始、五平台导出、零undefined、三archive哈希和65348项donor指针零失败；完整NativePrelink/运行ABI、ADT/provider/定时器/watchdog/13回调仍未验证，ARCH_TIMER/BOOT_PROGRESS仍0。历史payload输入仍CI15 a9e08c69，本轮固件包不含XNU。

608B CommandLine/0x2e0 boot_args已真实编译DarwinBoot EFI，运行未验证；Android DT不能当Apple ADT，ramoops与FD保留区重叠未占日志区。本机WSL仅shim编译证据，非完整XNU本机构建通过。

board/feed/bringup-plan/ADT及_verified不变，board仍example=true、普通基座-D入口尚未完整打通。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true保持；D-002先512MiB–1GiB过阶段5、硬上限8GiB，不与UEFI Heap混用。两个旧仓只读；Git/GitHub/workflow持续授权；镜像生成无需硬停，设备动作前缺具体日志或已确认恢复路径必须停，其他硬停仍按AGENTS§3。

同SoC来源作为困难问题解决来源之一主动评估：本次沿用sheng0eb4514d/fuxibb25ad75固定提交/许可/依赖/适用性记录，数值取同机证据，不复制额外bank或宣称同板已验证。
