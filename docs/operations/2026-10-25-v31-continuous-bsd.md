# v31 / PROBE23：连续执行BSD，只在首次init exec前停止

## 用户要求与已有实测

用户明确要求少用“挂载成功后主动停止”这样的阶段终点，一次推进尽可能多。PROBE22原图fc1c4ade已确认真实md0路径与原生vfs_mountroot返回0，21:30:50 +08恢复Android1/A槽/三SHA一致；无需重复证明这个单点。

PROBE23取消挂载后停止，挂载返回码/成功错误格继续记录，然后重放原生后继指令。安全根、imageboot、devfs、BSD收尾、PID1创建、首进程任务及init参数准备按原生控制流继续，不跳过错误检查，不将服务返回值改为成功。唯一终点移到首次用户态exec调用前，避免运行恢复镜像内的restored_external。不是为每个观察点安排一次试验。

## 固定执行边界

只读XNU提交1b191cb58250d0705d8a51287127505aa4bc0789（APSL-2.0）：bsd_init.c:1024调用bsd_utaskbootstrap；bsdinit_task完成异常/凭据准备、vm_init_before_launchd后调用load_init_program。kern_exec.c:6752的load_init_program_at_path复制程序路径/参数到真实用户地址并设置安全令牌，再调用execve。固定原生编译将其落在0xfffffff00769d5f4的BL `___mac_execve`；目标0xfffffff00769ce3c由符号与原始指令核验，不能机械按源码中函数名匹配。

kern_exec.c源文件SHAd6c064ee0c954db395d865e3265f6aa319e0908bb7e243e48bfe004298e96af1。保留原生DEVELOPMENT的init路径顺序和错误回退语义；首次exec前停止只证明参数准备/该调用点到达，不证明目标程序已存在、Mach-O/AMFI检查或用户态执行成功。

边界在该BL之前，所有原生首进程参数准备仍执行，第一次exec本身不执行。不在挂载返回、BSD入口或PID1创建处提前停止；也不放行恢复镜像用户态。如果前面真实检查失败，保留原生panic/错误/等待，不用终点设计掩盖失败。

旧标记0–211保持，212绿/213红仍记录真实vfs_mountroot返回，但不停止。新增214=bsdinit_task入口、215=load_init_program入口、216=load_init_program_at_path入口、217=首次___mac_execve调用前，218品红=唯一主动终点，A02B=217显示该检查点。A035保留挂载实际返回；后续阶段未亮时不得当作已完成。原native root/用户态bootstrap点继续可见。

## 输入与实现

内核SHA2e1f5d4a1e586a8f3dfb432053d8fe4c1c019d4beb405017f5aefeac9eea3ffc，58,425,344B；根仍为真实102MiB APFS d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a，参数-v rd=md0，192MiB FAT运输。新ADT531c915c18213897113ec1011a682155ee04ea5123fa2903517a6cd246a556a3。原FD/shim、1GiB窗口、board/TCR、iOS16/8796身份和所有*_verified保持。

冻结PROBE22的nuwa_root_launch_context.py字节及策略，不使旧包验证失效。nuwa_bsd_launch_context.py在独立命名空间执行该固定生产器（SHA36bcd82377a57ad97ca7ebe0ecc73b2cd5f21cb66cbb65633ce114a8165063ec），只为新包替换唯一终点策略，扩展生产器自身SHA和策略都进入真实清单；旧模块全局值不改。新旧包的根测量和参数仍强制验证，不扩大可信启动/防重放声明。

原挂载后hook重新加入完整透明性比较；只有首次exec前终点单独豁免，并用三例执行确认原始入参保留、无视频仍停止，`___mac_execve`目标没有执行。七项根输入错误对照及强制证据绑定继续保留。完整串行回归、独立重建和实际大镜像四文件回读完成后才进行新启动，未完成不能写通过。

## 设备门与后续

当前设备最近后验为21:30:50 +08 Android1/A槽/三SHA一致。用户当前持续要求推进更多进度且已可拍摄具体画面；实际启动前刷新preflight、即时通知，只临时boot一次。取图后绑定新包恢复固定原厂boot并补本轮三SHA后验。恢复未确认不执行第二候选，人工等待不阻断离线工作。不flash/erase/改槽、不push/新CI/上传原始媒体。尚无PROBE23实机结果，也未启动iOS用户态。

离线完成：21项串行任务通过，872透明差分/25Image4/6pthread/3唯一终点/7根输入/34绑定及入口/MMU/向量/显示回归。原挂载后hook重新加入透明比较，独立内核逐字节一致；实际FAT四文件回读/测量通过，旧包22复验通过。包reports/xnu-first-entry/entry-probe-23.json；镜像204,484,608B，SHA7e24257b5dede7e8a0d6089c6c0e458b8e54d0f5a904fe91371acb74e41c44a0，FAT SHA6e8f367f5206bd8a1900b294c83da8f928d76441de93ce0e5a7400a0eba32407。

本包用户已确认“PROBE23 录像与恢复仍就绪，继续”，新鲜preflight确认Android1/A槽/三SHA与v30后验一致，准备单次临时boot，尚无实机结果。后续恢复命令为trial-v4-firmware.py recover绑定包23、输出v31/recovery.json，后验以v31/preflight为基线。

2026-10-25 21:47:10 +08：即时通知后仅一次临时boot镜像7e24257b，199692KB传输/Booting ACK。代码91175af，等待菜单电源Enter后最终画面；本轮恢复后验尚未取得，不启动第二候选。ACK不提升为安全根/BSD/PID1成功；启动证据v31/launch.json。
