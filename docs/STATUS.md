# STATUS

更新：2026-10-25。**PROBE20实机已越过pthread初始化并进入IOFindBSDRoot，尚未进入vfs_mountroot。当前主线是root发现/存储输入。20:45:31北京时间确认已恢复Android完成1、A槽、三分区SHA与试前一致，无待恢复任务。**

## 实机与恢复

用户确认本包录像及恢复就绪；新鲜preflight确认nuwa/kalama、Android1/A槽/三SHA与v27后验一致。20:42:51单次临时boot ACK，用户菜单电源Enter后拍照。原图SHA369835170e359ef66697a02510152bc7b48328095beb1207900f65a69259d0f6，仅本地out/trial-evidence/entry-probe-20/user-screen.jpg。

ID180品红、181黄：BSD入口时真实pthread表已经注册，备用显式OSKext请求未执行。160/161 IOKitBSDInit与162/163 net_init_run调用/后继亮，164调用和7号IOFindBSDRoot入口亮，165后继与8号挂载入口未亮。原生pthread_init调用0xfffffff007672f94在已达路径之前，确认本次初始化返回；不由表非空单独推导成功。旧NULL表panic未复现，无新panic/fault记录。A02A=0/B=6/C=1；B仍为6是root入口未更新DISPLAY_CHECK。171在白logo上采样未知，不视为点亮。

用户已回fastboot，固定原厂boot临时加载成功；20:45:24观察Android完成1，20:45:31后验确认A槽及boot_a/vendor_boot_a/init_boot_a三SHA与本轮preflight相同。无flash/erase/改槽，无第二候选。

## 有效包与验证

权威包reports/xnu-first-entry/entry-probe-20.json；镜像out/trial-boot/xnu-entry-probe-20-pthread/boot-xnu-first-entry.img，SHA365216aebab5ec2e925a65f65576a26a6f1173ca4aa631e0c0ff0faf46422198，70,266,880B。内核d34a5de954a806f66fa346a74e5312a2513ec24d4377759d850ec6d6dd3eeb1d，ADT635d4f4dd8fc4abc7c2d15b427cf69b6a037086a39df21fb22b33b6fddb1ed09。

代码f0f4ea6，启动记录cde790a；当前实测记录提交号以git log为准，无push/新CI。固定iOS16.7 donor加入漏选pthread后31组件闭合；正常prelink启动已在BSD前注册。helper保留原生pthread_init/NULL断言，已注册时不重复请求。19项串行任务全部通过：740差分、25Image4、6pthread、31绑定及入口/MMU/向量/显示/同ADT回归。独立内核重建一致，实际FAT回读与输入重测通过。备用显式请求仍只有模型证据，本轮实机走已注册路径。

nonce来自主机OS CSPRNG，BNCH为原像SHA-384；非Apple诊断manifest绑定FD/shim/内核/基础ADT，不是Apple IM4M/TSS、硬件nonce或防重放证明。loadable=false/runtime_qualified=false，未设置任何*_verified。旧包19及其报告不改。

## 当前判断与下一步

7项root输入审计确认：出货菜单只有-v，实际ADT没有root-matching/boot-uuid或RAMDisk，原生IOFindBSDRoot默认等待Content=Apple_HFS的IOMedia。**首要原因是当前包缺少可选择的真实root提供路径。** 照片只能定位在IOFindBSDRoot内部，尚不能区分初始IOBSD资源等待、IOMedia等待和计时器/唤醒停滞；IRQ/计时器真实递送仍未验证。

下一步固定真实root介质/镜像、格式、DarwinBoot侧车或nuwa存储提供者来源与依赖，核对注册/匹配/根选择；不填假UUID、不把运输FAT当XNU root、不跳过等待。具体root内部停点需有限标记和独立候选；触及受审内存字段按AGENTS边界处理。无需重复启动20。root挂载/用户态未验证。

实测reports/xnu-entry-probe-trial/2026-10-25-v28/{screen,recovery,postcondition}.json；静态reports/kernel-entry-probe/2026-10-25-v28/root-inputs.json。[v28记录](operations/2026-10-25-v28-pthread-to-root.md)、[当前交接](operations/2026-10-25-mainline-handoff.md)。媒体仅本地，只读资料库、iOS16/8796身份、板值/TCR/内存窗口保持。
