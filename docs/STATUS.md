# STATUS

更新：2026-10-25。**按用户要求减少阶段停止，PROBE23已取消挂载后停止，连续执行原生安全根/BSD收尾/首进程准备，唯一终点在首次init exec前。21项串行验证和镜像回读完成；用户已确认本包录像/恢复仍就绪，新鲜preflight确认Android1/A槽/三SHA与上轮后验一致，准备单次临时boot。** 尚无PROBE23实机结果。

## 最近实机与设备

PROBE22照片fc1c4ade8efa484b2e0362067e1d68b997f76477a297a6d41f77c79b1ecbe58b仅本地：真实mdevadd196/197、mdevlookup204/205、setRootMedia206/207、IOFindBSDRoot164/165、vfs_mountroot166/167均亮；A0350/212绿、213暗，原生根挂载返回0，在旧预定终点停止，未进入恢复用户态。实载APFS已知，运行时FS名称/root vnode和整盘哈希未直接读回，不扩大结论。

PROBE22恢复后21:30:22观察Android1，21:30:50 +08后验确认Android1/A槽/三SHA与试前相同，无待恢复任务。用户此前要求暂不调查重启现象，仍保持。当前PROBE23的新鲜preflight再次确认Android完成1/A槽/相同三SHA，不重复启动22。

## PROBE23有效输入与设计

权威包reports/xnu-first-entry/entry-probe-23.json。镜像out/trial-boot/xnu-entry-probe-23-bsd/boot-xnu-first-entry.img，204,484,608B，SHA7e24257b5dede7e8a0d6089c6c0e458b8e54d0f5a904fe91371acb74e41c44a0。内核2e1f5d4a1e586a8f3dfb432053d8fe4c1c019d4beb405017f5aefeac9eea3ffc；ADT531c915c18213897113ec1011a682155ee04ea5123fa2903517a6cd246a556a3；真实102MiB APFS仍为d180c38d，-v rd=md0，192MiB运输。

挂载返回后只记录A035及212绿/213红，然后重放原生后继指令。安全根、imageboot/devfs、BSD收尾、PID1创建与init参数准备按原生控制流继续；不逐阶段停止或换包，不跳过原生错误。唯一终点在0xfffffff00769d5f4 BL ___mac_execve之前，避免运行恢复镜像里的restored_external；不证明可执行文件存在、Mach-O/AMFI加载或用户态通过。

新增214=bsdinit_task、215=load_init_program、216=load_init_program_at_path入口；217=首次exec调用前，218品红=主动终点，A02B=217。旧root观察标记保持。v30冻结生产器不改，v31独立策略/生产器SHA纳入真实测量，旧包22复验通过。

21项串行任务通过：872透明差分、25Image4、6pthread、3唯一终点、7根输入、34绑定及入口/MMU/向量/显示回归。原挂载hook已重新加入透明性检查；只有首次exec前终点单独豁免。独立内核逐字节一致，实际FAT回读kernel/ADT/APFS/菜单并重新测量通过。源码/指令依据、SHA和命令见[v31记录](operations/2026-10-25-v31-continuous-bsd.md)。

## 实测边界和续接

用户原文“PROBE23 录像与恢复仍就绪，继续”保留于v31/preflight。即时通知后仅一次临时boot，取最终画面后固定原厂boot恢复，确认Android1/A槽/三SHA与本轮preflight相同。人工等待继续离线工作，恢复未确认不启动第二候选。

当前基线7057d1d之后的新里程碑以git log为准；无PROBE23实机结果，安全根/首进程/用户态、IRQ计时器和驱动完整性仍未验证。原FD/shim/board内存表、1GiB窗口、TCR、iOS16/8796身份和*_verified不改，loadable/runtime_qualified保持false；无flash/erase/改槽、push/新CI或原始媒体上传。
