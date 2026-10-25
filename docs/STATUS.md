# STATUS

更新：2026-10-25。**PROBE23实机已见bsd_init调用/返回110/111、BSD首进程准备214–216、首次init exec前217及终点218；A02B=217。21:50:51 +08后验Android1/A槽/三SHA一致，恢复关闭。** 尚未执行___mac_execve、可执行文件/AMFI加载或用户态代码。用户明确“之后都要连续推进”，已写AGENTS：诊断点默认只记录继续，成功里程碑不再作为停止理由，只有真实故障/明确硬停或尚未授权设备写入边界才停。

本轮照片624b4cda9d93521f5d818cd6004944e947e9ab820085c11e4346a265edbebdb6仅本地out/trial-evidence/entry-probe-23/user-screen.jpg：110/111、168/169 IOSecureBSDRoot调用/返回、174/175 devfs挂载、176/177 bsd_utaskbootstrap均亮；9、214/215/216黄，217蓝、218品红。A02A0/B=0xD9/C1，A0350/212绿，213暗。可确认原生BSD初始化返回、首进程路径到第一次exec前；不把安全根调用返回当成密码学/Apple可信根验证通过，也不把exec前终点写成可执行加载成功。

固定原厂boot恢复流程确认21:50:19 Android完成1，21:50:51后验A槽/三SHA与v31/preflight完全一致，用户也确认已回Android。无待恢复任务，不重复启动23；证据v31/{screen,recovery,postcondition}.json。代码91175af、启动d644d7a，当前实测提交号以git log为准。

## 最近实机与设备

PROBE22照片fc1c4ade8efa484b2e0362067e1d68b997f76477a297a6d41f77c79b1ecbe58b仅本地：真实mdevadd196/197、mdevlookup204/205、setRootMedia206/207、IOFindBSDRoot164/165、vfs_mountroot166/167均亮；A0350/212绿、213暗，原生根挂载返回0，在旧预定终点停止，未进入恢复用户态。实载APFS已知，运行时FS名称/root vnode和整盘哈希未直接读回，不扩大结论。

PROBE22恢复后21:30:22观察Android1，21:30:50 +08后验确认Android1/A槽/三SHA与试前相同，无待恢复任务。用户此前要求暂不调查重启现象，仍保持。当前PROBE23的新鲜preflight再次确认Android完成1/A槽/相同三SHA，不重复启动22。

## PROBE23有效输入与设计

权威包reports/xnu-first-entry/entry-probe-23.json。镜像out/trial-boot/xnu-entry-probe-23-bsd/boot-xnu-first-entry.img，204,484,608B，SHA7e24257b5dede7e8a0d6089c6c0e458b8e54d0f5a904fe91371acb74e41c44a0。内核2e1f5d4a1e586a8f3dfb432053d8fe4c1c019d4beb405017f5aefeac9eea3ffc；ADT531c915c18213897113ec1011a682155ee04ea5123fa2903517a6cd246a556a3；真实102MiB APFS仍为d180c38d，-v rd=md0，192MiB运输。

挂载返回后只记录A035及212绿/213红，然后重放原生后继指令。安全根、imageboot/devfs、BSD收尾、PID1创建与init参数准备按原生控制流继续；不逐阶段停止或换包，不跳过原生错误。唯一终点在0xfffffff00769d5f4 BL ___mac_execve之前，避免运行恢复镜像里的restored_external；不证明可执行文件存在、Mach-O/AMFI加载或用户态通过。

新增214=bsdinit_task、215=load_init_program、216=load_init_program_at_path入口；217=首次exec调用前，218品红=主动终点，A02B=217。旧root观察标记保持。v30冻结生产器不改，v31独立策略/生产器SHA纳入真实测量，旧包22复验通过。

21项串行任务通过：872透明差分、25Image4、6pthread、3唯一终点、7根输入、34绑定及入口/MMU/向量/显示回归。原挂载hook已重新加入透明性检查；只有首次exec前终点单独豁免。独立内核逐字节一致，实际FAT回读kernel/ADT/APFS/菜单并重新测量通过。源码/指令依据、SHA和命令见[v31记录](operations/2026-10-25-v31-continuous-bsd.md)。

## 实测边界和续接

下一项连续进入真实exec/Mach-O/AMFI/dyld加载路径，先核对新任务激活与用户态释放点，不机械地在每个成功阶段另设终点。固定kern_exec.c:5017注明激活在不可回退点后失败时仍可能返回0，因此不能只看exec返回0宣称加载成功；需记录真实激活/签名结果及任务交接。恢复镜像用户态不是正常完整iOS环境，不能让持续推进隐含授权其还原/写盘程序。除此类实际边界，已有授权、日志与恢复条件有效时直接继续，不重复询问。

用户原文“PROBE23 录像与恢复仍就绪，继续”保留于v31/preflight。即时通知后仅一次临时boot，取最终画面后固定原厂boot恢复，确认Android1/A槽/三SHA与本轮preflight相同。人工等待继续离线工作，恢复未确认不启动第二候选。

当前基线7057d1d之后的新里程碑以git log为准；无PROBE23实机结果，安全根/首进程/用户态、IRQ计时器和驱动完整性仍未验证。原FD/shim/board内存表、1GiB窗口、TCR、iOS16/8796身份和*_verified不改，loadable/runtime_qualified保持false；无flash/erase/改槽、push/新CI或原始媒体上传。
