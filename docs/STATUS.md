# STATUS

更新：2026-10-25。**PROBE19实机已越过MAC/Image4并进入bsd_init；当前panic为pthread内核函数表未注册。root发现/挂载和iOS用户态尚未进入。20:03:58已确认Android1/A槽/三SHA一致，恢复待办关闭。**

**20:42:51 PROBE20已单次临时boot ACK，等待用户菜单电源Enter后的画面；ACK不计为pthread/BSD进度。** 本轮新鲜preflight与v27后验三SHA一致，用户本包录像/恢复条件已确认；当前Android恢复后验尚未取得，不启动第二候选。launch证据reports/xnu-entry-probe-trial/2026-10-25-v28/launch.json，代码f0f4ea6。照片到达后判读178–181与原BSD/root点，再执行固定原厂临时boot恢复及本轮三SHA后验。

## 当前设备与有效包

19:56:34北京时间preflight确认nuwa/kalama、Android完成1、A槽、boot_a/vendor_boot_a/init_boot_a三SHA与v25后验一致。用户确认本包录像及恢复就绪后，19:57单次临时boot ACK；照片5bad2ca9179cc42353ea70c1a5cb0dc69a3ef5bb197560ce8527976565154f6f本地保存。ACK不作为内核阶段证据。

照片A02A=0、A02B=6、A02C=1，MAC后继89与BSD入口6亮、root入口7/8未亮；panic前16字节为pthread kernel e，与原生pthread_shims.c:318函数表NULL检查匹配。无新IRQ/计时器/驱动资格结论。第一次恢复监测超时，随后用户回到Android，20:03:58后验确认Android完成1/A槽/三分区SHA与试前相同；失败recovery.json及成功recovery-retry.json都保留。当前无人工恢复待办，不重复启动19。

权威包reports/xnu-first-entry/entry-probe-19.json；镜像f1febc069f45bcf22d88c91f571e4c5fa8d84e1a7e4368c7375adf525cb787a6（70,266,880B）；内核f3c33194973fc6469b3bc3e4aa5f72595083ef4560c5979a860415ebec918984；ADTace998436500149856a0f41838aa8a4e3dd8dedbb6cfb716922a5baad544ec4d。

## 本轮输入与验证

集成AMNM/CHMH兼容入口；nonce由主机OS CSPRNG新生成，BNCH为其SHA-384，manifest实际绑定固定FD/shim/新内核/基础ADT，boot-manifest-hash为规范清单的SHA-384。属于非Apple诊断启动测量：未建立Apple IM4M/TSS链，nonce按候选包存续，不提供硬件防重放；不当作nuwa硬件nonce实测。禁止混配值为32位LE1；未放宽认证或MAC错误。

740差分、入口/MMU/向量/上下文/同ADT切换及console回归通过；25项完整原生Image4初始化及错误对照、29项证据绑定通过。内核独立重建一致，新包实际镜像回读及输入重新测量通过。参考DarwinBoot/VerifiedRoot/sweet/topaz/nuwa RNG均固定提交与源文件SHA；其他机型固定字符串摘要未采用。

v26切片把x19强制设成pmap runtime，不能证明真实初始化只补字段仍失败；完整原生prologue实际加载Darwin IOKit runtime。完整入口反例确认：原ADT为AMNM panic、仅补合法AMNM后为BNCH panic；实际新输入使原初始化RET。dtless缺AMNM/CHMH仍对后续查询成立，兼容代码对此单独验证。D-048纠正D-047完整路线排序，D-049记录本轮BSD实机结果。

## 下一项与边界

固定donor有iOS16.7的com.apple.kec.pthread，原30组件selection遗漏它。新增11项离线审计只加入pthread后31组件绑定闭合，指令原字节保留；真实kmod入口通过原生pthread_kext_register注册实际函数表，原生wrapper分派到donor初始化入口，重复注册仍拒绝。分析产物52227410位于out/pthread-prelink-v28-analysis，不是试包20，未执行初始化函数体/真实OSKext生命周期，不可直接部署。

PROBE20/revision28已加入31组件并在BSD前调用原生OSKextLoadKextWithIdentifier；内核d34a5de9，独立启动输入ADT635d4f4d。19项串行任务全部通过：740差分、25完整Image4、6pthread、31绑定及入口/MMU/向量/显示回归；独立内核重建一致，实际FAT回读和输入重新测量通过。新镜像365216ae/70,266,880B，权威包reports/xnu-first-entry/entry-probe-20.json。尚未实测，等待PROBE20当轮录像/恢复条件；最近设备证据仍20:03:58 Android1/A槽/三SHA一致。不能把模型API边界当成完整生命周期。保留原生pthread_init和NULL表panic；锁/hash/thread-call/sysctl实际初始化仍需确认。命令与SHA见[v28记录](operations/2026-10-25-v28-pthread-to-root.md)。前轮因果见[v27记录](operations/2026-10-25-v27-image4-to-bsd.md)及[当前交接](operations/2026-10-25-mainline-handoff.md)。

实测reports/xnu-entry-probe-trial/2026-10-25-v27/；离线reports/kernel-entry-probe/2026-10-25-v27/。板值、TCR、内存/身份、只读资料库、loadable=false/runtime_qualified=false保持。无flash/erase/改槽，无push、新CI或原始媒体上传。
