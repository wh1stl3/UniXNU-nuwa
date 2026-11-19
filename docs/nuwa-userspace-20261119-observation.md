# nuwa 用户态推进观察记录（r16–r35，2026-11-17 – 2026-11-19）

本文是全量记录：每次上机的载荷哈希、设备侧结果、关键发现、当前阻塞、证据路径与下一步顺序。
`out/` 与 `.cache/` 被 `.gitignore` 排除，所以结论与哈希必须写在这里，不能只留在 `out/`。

**状态标签**

- 主机产物、打包与自检：**self-checked**（本仓库历次会话自跑，无独立 `verifier` 复跑）。
- 设备侧读数：**主控转述的用户观测**（实机屏幕/照片/录像），或本仓库内已落盘的上一轮记录文字；
  除 r16 外没有主机读图文档，也没有独立 `verifier`。
- 认证：**NOT REACHED**（CHMH 仍是未认证实验身份，runtime trust cache 为空）。
- 交互目标（到桌面/锁屏可操作 + 断电重启仍回同系统）：**未达成**。

本文不记录 serial、ECID、设备种子、照片或任何 Apple 组件本体；只写哈希、地址、路径与结论。

---

## 0. 一句话结论

r16–r34 把流程从「dyld 找不到共享缓存」推进到「SpringBoard 与 mobileactivationd 以 SIGTRAP 退出」：
根卷 + SystemOS 联合挂载 + Data 卷 + keybag/AppleKeyStore 桩都在设备上走到了 launchd 之后的多进程阶段，
但显示服务仍未接、SMP 仍未启用，SpringBoard 的 SIGTRAP 是当前第一阻塞。r35（异常退出环）已构建**但未上机**，
设备当前运行的是 r34 载荷。

---

## 1. 每次上机台账

`vendor_boot.img` 一律 100,663,296 B（96 MiB 分区整数），写入方式一律是**单次有界
`fastboot -s <nuwa> flash vendor_boot_a`**，只有 `Sending OKAY` + `Writing OKAY` 级确认，
bootloader 无 `fetch`、fastboot 模式无 adb，**没有任何设备侧回读**。`boot_a` 自 2026-11-15 起未再写
（仍是 r4 loader 前 1,495,040 B `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`）。
每次写入的回滚说明与哈希清单在 `out/nuwa-boot-payload-write-20261115-01/ROLLBACK-rNN.md`，
写入记录在同目录 `WRITE-rNN.json`（失败尝试与补救见 `WRITE-rNN-FLASH-REJECTED*.json`）。

| # | 时间（+08:00） | 载荷 SHA256（`vendor_boot.img`） | 内核 SHA256 / 字节 | seed / APSB xid | 设备侧结果（证据标签） |
| --- | --- | --- | --- | --- | --- |
| r16 | 2026-11-17T03:50:57 | `9a434132341f42c812c515a6b0e0ea7d8a249c89ab252ea44e17eac74215ac9f` | `078455211767759261106cada09046ff2238a70f70aee6f8e15f614af5a263c0` / 55,681,024 | `6a6db153…40d9` / 12 | **失败**：initproc exec 后 dyld panic `Library not loaded: /usr/lib/libSystem.B.dylib (no such file, no dyld cache)`；`DATA mnt st=0 err=-1 ro=-1 dev=ffffffff seed=0`（Data 链未跑）；`procs=0`；页面 6.3 s 后冻结。**主机整段录像判读**（`out/nuwa-r16-video-frames-20261117/READ-r16-video.md`，1,172 帧） |
| r17 | 2026-11-17T18:05:43 | `579d19b4714364a842d90f48343d21e23dcfece7f783bd147a5d7206fdd8a12a` | `5632a383ecc2aa3330b543468544b445c46dc1258b391738cde1f6b916b84c1f` / 55,681,024 | 同上 / 12 | **失败**：改成 devfs 上 `/private/preboot`、在其内建 `Cryptexes` 并把 cryptex 挂到 `/private/preboot/Cryptexes/OS`（r16 形态留作回退），launchd 仍未取到共享缓存。屏幕读数未落盘，仓库内唯一迹证是 r18 的 fallback 注释与 `INVALID-FIXES.md` A3（主控转述） |
| r17c | 2026-11-17T18:33:20 | `dfbbc3038c455fa188fae2080ebb2502a18facefc71d178514490a20789ec7a1` | `278cbc705aaadc7ceae1bedd518f6bc024c35da2f971b644a5fe2c56d6c470cd` / 55,681,024 | 同上 / 12 | **失败**：r17 + 每次挂载后同步重绘（让页面在 panic 前能读到）。屏幕读数未落盘（主控转述） |
| r18 | 2026-11-17T23:09:45 | `a1996558ce34d27e33068012b22d05ddf9f8c56b995a73be49089d8ae1824bdd` | `8d608d5484e4729a0cd897ed37fa8d4d9f181cba8cf84bc3b09db0829a07566b` / 55,681,024 | 同上 / 12 | **部分成功**：SystemOS cryptex 以 `MNT_RDONLY\|MNT_UNION` 挂到 `/`，`SYSOS st=6 err=0 dev=/dev/disk1s rauth=1 pb=-1 mk=-1 mos=-1 ap=0 uni=1 rv=1`（`rootvnode` 已随 `checkdirs()` 换到 cryptex）；launchd 仍 panic `no such file, no dyld cache`（`out/nuwa-r19-plan-20261118/PLAN.md` 记录的实机截图读数） |
| r19 | 2026-11-18T00:46:49 | `d5f2855ffbc9b79ba2aad3d987dbe97d4dcf82a63f47ac812ae3053edc9aabbb` | `19bd5d5b4a469024ac32492d6aa81748b0695edc5cdfe34b98c4ea7cede4246c` / 55,681,024 | 同上 / 12 | **失败**：四条缓存路径内核探测 `p1..p4/csz` 上线；实机 `p3=2`（`/System/Cryptexes/OS` 前缀不存在），dyld 仍报 no cache（`INVALID-FIXES.md` A3；主控转述）。页面同时暴露字符竖笔丢失问题（`p1` 的 `1`、`uni=1`→`uni=_`） |
| r20 | 2026-11-18T01:07:31 | `6d6282388232b2d64d31f10902eb5a338f7463c2444ba36f7b83c2f53aa12d5f` | `d85a7ba129fd41308d8c4909cadcc8fc0087881a45423f4192f9f1dfa1eff90e` / 55,681,024 | 同上 / 12 | **失败**：打开 `namei()` 追踪 + AMFI/cs 观测（`SYSOS amfi=/cs=`）；与 r19 同结论（`p3=2`、无 dyld cache） |
| r21 | — | **无载荷**（未打包、未上机） | `out/nuwa-r21-20261118/kernel.macho` 未进入 CHMH/FAT | — | 仅渲染器修正（bind 去重、panic 后停画、关键行移入 panic 安全区）+ 自检图案；没有 `scripts/build-ufs-apfs-root-chmh-r21.py`，也没有 `WRITE-r21.json` |
| r22 | 2026-11-18T11:18:13 | `8660cf6baf53a92939abe3638d45521db0cd9c67a4656cb8fa00e3c52353e7d0` | `d267f9cab727b768e8f5f147ee02667ad21c378a274497c2249f643349ceab4f` / 55,685,120 | 同上 / 12 | **失败**：4K 代码签名哈希缓存 + dyld flags 回读 + 缓存 magic 探测；实机 `mg=bad`（缓存实际可被 dyld 加载），且 reboot 路径在 `vnode_rele_ext` 崩溃（`vfs_subr.c:2691`，usecount -1）。`INVALID-FIXES.md` A1 |
| r23 | 2026-11-18T19:37:59 | `1a9f6299f90e5f9cfdd3e728e2679c59d6e381a112f5d3915454696286321e18` | `89db8ee910a23d8732f18393e2065ab9ae2a1bb69b9f7d0fcd2fa96de966fdf2` / 55,685,120 | 同上 / 12 | **失败**：探测改为「一次 `vnode_lookup` + 一次 `vnode_put`」，magic 按 16 字节 `memcmp`；实机 `mg=ok`，vnode 侧不再有释放点（A1）。launchd 仍 panic |
| r24 | 2026-11-18T21:55:23 | `469524541c818af9527864644b9f5a7d19e9be822072ca6e1d60ae9136ee5e8a` | `d8fc613a2e0a5749ab3708b40292a00ac9bd5c070579cc75857f04a113f738a7` / 55,685,120 | 同上 / 12 | **失败**：union 前对旧根加一次 `vnode_ref` + guard；实机 `uc=10/8`（仍少 2，union 内部实际释放 3 次），reboot 时 `vnode_rele_ext` panic 未变。Data 侧读 `hdr=9 gpt=ff/ff`，说明 Data 卷已挂上并写 overlay（A2/A5） |
| r25 | 2026-11-18T22:52:40 | `fcfd25489425a6abe7bc262a9169d81df6b4f68b06a9017ec427f4360afafc6f` | `c4a2bdecde81ad511a153ab262ded1bd44a6078bea796a8b0e5bcab6982e362a` / 55,685,120 | 同上 / 12 | **失败**：把 Data/RamBlock/reboot 观测搬到诊断页（行 3/8/9）；实机 `uc=10/8` 不变，结论同 r24（A2） |
| r26 | 2026-11-18T23:28:48 | `fc2fba6ab650d4ad2a742e4a20ad5146b86feb87535e84d90de5edd18d42d186` | `0ff3494854ee02dbb33e2d07ceb074da2d68fcfc18089c328791f35f4ac1f08a` / 55,685,120 | 同上 / 12 | **失败**：在 `IOPlatformExpertDevice::startIOServiceMatching()` 里显式 new/init/attach/start RamBlock；实机崩在 `OSMetaClass::getClassName()`（pc `0x785ee38`，far 指向 `"NativeRamBlock"` 字面量）。A6 |
| r27 | 2026-11-19T00:10:28 | `aa51fa0f0d0578308df939b94af1eb071f12b44a6d6015b3b9c3244c2c462401` | `a8921ab06add3bf514adfca4eafe74dd879176d76dceb887c74d211cfef6dd85` / 55,685,120 | 同上 / 12 | **失败**：同一创建点挪到 `nuwa_data_mount_prepare()`（`bsd_init`/`bsd_autoconf` 之后）；实机仍是同一 `getClassName` 崩溃 ⇒ 崩因不是时机，是类注册未加 `preModLoad`/`postModLoad` 括号（A6） |
| r28 | 2026-11-19T12:05:57 | `2652369b1c2eb00f5396e8c1f19719709fc224b2c396199ba97a61cc247bacf7` | `e000e7a6ac99b5f72e0ea1b0d73521c07986a0a126ff62b4b2250f46abb43391` / 55,685,120 | 同上 / 12 | **失败**：只补注册括号（r26/r27 创建点保留），删除无效的 r24 root guard；实机在 teardown 的 `apfs vflush → vclean → vnode_update_identity` 期间 `vnode_rele_ext` panic（usecount 变负），且 reboot 请求记录写在 `system_inshutdown` CAS 之后，页面停在 `boot=-1/-` |
| r29 | 2026-11-19T18:04:41 | `e1f247f334e270730078e23368933d24c0c027f60c15c94d261f0624f214ffb6` | `ca33a66413e987a0dc97148f033d94c0d18f9db87df880e0b5c18a2997254de7` / 55,685,120 | 同上 / 12 | **进展**：`set_rootvnode()` 给 kernproc `fd_cdir` 自己的 `vnode_ref`（`XNU_NUWA_ROOT_CDIR_REF`），三次释放各有对应持有，r28 的 teardown panic 消失；reboot 请求改在 `reboot(2)`/`reboot_kernel()`/`host_reboot()` 三处记录并立即重绘。屏幕读数未落盘（主控转述） |
| r30 | 2026-11-19T18:55:28 | `d5d99a03597c3d571784beb4b8893d6f00c27aa7160ab749146a725f7ff5b97e` | `334e43567a4084ab864aa3a363c71f9e87dd339f2b6596c107a54758107a3def` / 55,689,216 | 同上 / 12 | **失败但读数清晰**：keybagd 在 `t=72109 ms` 请求普通重启（`boot=11/keybag/0`），Data 卷可写（`DATA st=4`），keybag 目录 `kb=ooo`；即「keychain 背后没有 AppleKeyStore」。`package/nuwa-aks/SOURCE.md` |
| r31 | 2026-11-19T20:29:26 | `c9ed423d3f6b3ac8ebf1d9fe79ac60d31b684cd56fe4abb8e3559b1e1286ffd9` | `626543a02f1a9d79e404ad588416e4f810ed1d7bb106ed9759c3b460a4227afd` / 55,717,888 | 同上 / 12 | **前进**：链接 UniXNU `AppleKeyStoreState` + `aks=1`；服务起来、keybagd 连接过一次，但仍重启（`scripts/build-ufs-apfs-root-chmh-r32.py` 记录的 r31 设备结果） |
| r32 | 2026-11-19T20:58:21 | `dfecf0f3d9a5497e7a67875e225ae1dae56dbfb92da43653e205c0acb366e9c7` | `8a343b2784ea63862a971645c22fda3916b5dc9802cc0f01ce7c25dc5dd07966` / 55,717,888 | 同上 / 12 | **失败**：AKS 分派环放行 10（不在 panic 安全区），实机 panic 清屏把该行抹掉，选择器读数丢失（r33 记录的 r32 设备结果） |
| r33 | 2026-11-19T21:22:36 | `2d97df5ffe06b81ed9ac16e4be8abaed9897b4bba1ebd8e3388cea5fa9e33f29` | `6234a90ca614f26c13779b1f17adf76b3c503f5d2f485188adae3baa54701535` / 55,717,888 | 同上 / 12 | **失败**：环移到行 6（panic 安全区，20 字符 stage 标签旁）；实机读得 keybagd 两次走 `aks_get_system`（selector 14）后重启，随后读 `/private/var/keybags/systembag.kb` 失败（r34/r35 记录的 r33 设备结果） |
| r34 | 2026-11-19T22:45:14 | `46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e` | `ce24818ea19e1301dc0f4173a448ff3088aabf9bcc413f645f93c1c569a7f6dd` / 55,717,888 | `2c95d15b…8110` / 16 | **当前设备状态**：内核/args 同 r33，只换 seed（含 `keybags/systembag.kb`）与 ADT `/defaults no-effaceable-storage=1`，并加 `disable-watchdogd=1`；实机出现 **SpringBoard 与 mobileactivationd 的 SIGTRAP**（`out/nuwa-r35-20261119/build.py` 记录的 r34 设备结果）。窗口内 adb/fastboot 全程无枚举 |
| r35 | 2026-11-19T23:16:43（构建） | `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed` | `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464` / 55,721,984 | `2c95d15b…8110` / 16 | **已构建，未上机**：把最后四笔异常用户退出（`EX1 <comm6> <sig>:<ns>:<code>`）画进 panic 安全带，并把 pid/status/ns/code/nprocs/AKS 计数打到控制台；没有 `WRITE-r35.json`，设备仍跑 r34 |

补充事实：

- r17c 与 r19 之后的若干轮只改了同一 CHMH 谱系的输入；每轮 CHMH 都按新内核重新绑定，`record.json` 里
  `authentication: "NOT REACHED"`、`device_release: false` 未变。
- 写入被拒与补救（`Requested download size ...` / `partition size: 0`，本机 ABL 间歇性）出现于
  r23（1 次）、r27（1 次）、r28（2 次）、r33（1 次，用单次 `reboot bootloader` 补救成功）；
  这些尝试都在 download 阶段被拒，**传输 0 字节**，补救后同一轮成功。
- r17 / r17c / r19 / r20 / r22 / r24–r34 的屏幕读数**没有主机读图文档入库**（照片与录像按硬约束不入 Git），
  本文引用的都是仓库内已落盘的上一轮文字（`INVALID-FIXES.md`、`SOURCE.md`、下一轮 `build.py`/打包脚本的说明），
  来源一律标「主控转述」。

---

## 2. 关键发现

### 2.1 env 变量救不了 dyld：initproc 是平台二进制，dyld 只走固定路径

- r16 给 initproc 传了 `DYLD_SHARED_CACHE_DIR`，但 initproc 是平台二进制，dyld **忽略** 该变量、
  走自己的固定列表；r16 又把 cryptex 直接挂在 `/private/preboot` 上，遮住了真实目录，
  `/private/preboot/Cryptexes` 不存在 ⇒ 根上的 `/System/Cryptexes/OS` 符号链接悬空 ⇒ dyld 回退
  `/usr/lib/libSystem.B.dylib`（该文件在本镜像不存在）⇒ panic。
- r19/r20 的内核探测给出同向证据：`p3=2`（`/System/Cryptexes/OS/...` 前缀 `ENOENT`）。
- r22 起改为**不给任何环境**（`*envp = USER_ADDR_NULL`），r28 起在镜像层面断言字符串
  `DYLD_SHARED_CACHE_DIR` 不存在。dyld4 的 CacheFinder 对无法打开的 override 目录直接放弃、不回退，
  所以「换一个 env 值」不是可选项。

来源：`package/nuwa-systemos/nuwa_systemos.c` 头注释（r17 段）、`out/nuwa-r28-20261119/INVALID-FIXES.md` A3。

### 2.2 SystemOS 必须 union 挂到 `/`，才有 dyld 唯一可用的固定缓存位置

20H392 的 OS 卷没有 `/System/Library/Caches/com.apple.dyld`，共享缓存（约 2.7 GB，
`dyld_shared_cache_arm64` + `.01..18`）只在 SystemOS cryptex 卷内。dyld 唯一可满足的固定位置就是根上的
`/System/Library/Caches/com.apple.dyld`，因此 r18 用 `MNT_RDONLY|MNT_UNION` 把 cryptex 挂到 `/`：
实机 `SYSOS st=6 err=0 dev=/dev/disk1s rauth=1 uni=1 rv=1` 证明挂载成功、`rootvnode` 随 `checkdirs()`
换到 cryptex。挂载只解决「文件在不在」，不解决「能不能映射」（见 2.8/2.9）。
r17 的 devfs + `/private/preboot/Cryptexes/OS` 形态作为记录在案的 fallback 保留。

来源：`out/nuwa-r19-plan-20261118/PLAN.md` §「上一轮事实」；`scripts/build-ufs-apfs-root-chmh-r18.py` 头注释。

### 2.3 root cdir 引用记账：r24 的「多持一次」是错的，r29 的「各自持有」才对

- union 挂载时 `checkdirs()` 会把 `rootvnode` 移走，teardown 有三处释放（kernproc cdir、initproc cdir、
  rootvnode）。r24/r25 在挂载前给旧根加一次 `vnode_ref` 试图抵消，实机 `uc=10/8`：相对挂载前仍少 2，
  说明 union 内部实际释放了 3 次，**多持 1 次无效**，还在成功路径上故意泄漏一个引用。r28 整段删除，
  `vnode_ref`/`vnode_rele`/`vnode_usecount` 在对象里各 0 次。
- r29 改在 `set_rootvnode()` 里给 kernproc 的 `fd_cdir` 自己的 `vnode_ref`（`XNU_NUWA_ROOT_CDIR_REF`），
  cdir 移动时释放该持有；三处释放各自对上持有，r28 的 `apfs vflush → vclean →
  vnode_update_identity`（`vnode_rele_ext`，usecount -1）panic 消失。

来源：`out/nuwa-r28-20261119/INVALID-FIXES.md` A2；`scripts/build-ufs-apfs-root-chmh-r29.py` 头注释；
`patches/xnu/8796-nuwa-root-cdir-ref.patch`。

### 2.4 RamBlock：崩因是类注册缺括号，不是创建时机

r26 在 `IOPlatformExpertDevice::startIOServiceMatching()` 内创建、r27 挪到
`nuwa_data_mount_prepare()`（`bsd_autoconf` 之后、registry 已连通、媒体有 2 s 等待窗口），
**两次都崩在 `OSMetaClass::getClassName()`**（pc `0x785ee38`，far 指向 `"NativeRamBlock"` 字面量）。
原因是静态构造器裸跑：`OSMetaClass` 构造只把类名当裸字符串存下，`postModLoad()` 才把它转成已注册的
`OSSymbol`。r28 用 `OSMetaClass::preModLoad("__kernel__")` / `postModLoad()` 把注册包起来，
创建点保留 r27 位置，并让 `start()` 用静态 claim 拒绝第二个实例（页面 `reject` 字段：
`1..9` = `start()` 拒绝码、`a..d` = 创建路径、`e` = 第二实例被拒、`f` = 创建入口未链接）。
r31 的 AppleKeyStoreState 用同一括号形状（`nuwa_aks_wrap.cpp`）。

来源：`out/nuwa-r28-20261119/INVALID-FIXES.md` A6；`package/nuwa-ramblock/NativeRamBlock.cpp:540`；
`package/nuwa-aks/nuwa_aks_wrap.cpp:7-16`。

### 2.5 Data seed 与 keybag：卷能挂、能写，缺的是 keybag 内容

- seed 一直是 macOS 15 VM 用官方脚本产出的 8 GiB packed APFS 镜像（容器 4096 B 块、8 个 region、
  APSB 卷 UUID `B0E0F71F-A265-4038-8F5C-6D3632859DEF` 从 packed extents 解析后写进内核
  `XNU_NUWA_DATA_VOLUME_UUID`）。r16–r33 用 `data-8g-fixed.dbr`
  （1,609,888 B `6a6db153603b9a4a424711f0fa21c06a3d2b5ffb96a5001864be62d051ed40d9`，
  identity `689fd890…08bd`，`apsb_xid=12`）。
- r34 换成 `data-8g-keybag.dbr`（1,896,608 B
  `2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110`，identity
  `e17c9691f69caa05b8d2c04dfce32bb53068446bd305f0652bed889c2fc69ec8`，`apsb_xid=16`），
  新增 `/private/var/keybags/` 目录与 234 B `systembag.kb`（`KeyBagKeys` = `SWEET`），
  并给 ADT `/defaults` 加 `no-effaceable-storage = 1`。该 seed 源在仓外
  `D:/vmshare/data-8g-keybag.dbr`，仓内只有哈希与打包脚本里的 pin。
- 读数的推进链：r24/r25 `hdr=9 gpt=ff/ff`（Data 已挂且已写 overlay）→ r30 `DATA st=4`、`kb=ooo`、
  keybagd `boot=11/keybag/0` @ `t=72109 ms` → r33 keybagd 两次 `aks_get_system(14)` 后重启 →
  r34 补 keybag 内容。Data 卷「能挂能写」不再是阻塞，阻塞移到 keybag/AKS 与用户态退出。

来源：`out/nuwa-data-seed-macos-20261116-r2/REPORT-seed.md`；
`scripts/build-ufs-apfs-root-chmh-r34.py:230-238`；`package/nuwa-aks/SOURCE.md:12-17`。

### 2.6 AKS 桩：软件 key wrapping，不是硬件数据保护

r31 起链接 UniXNU `AppleKeyStoreState`（upstream `UniXNU/AppleKeyStoreState@8c70daf8`，
BSD-2-Clause-Patent，byte-identical `NativeKeyStoreEvents.cpp`），实现板侧 6 个函数：
`aks=1` 时 enabled、lock state 恒 0、selector/last-result 计数、open 计数、device id 取 ADT
`/chosen/unique-chip-id` 8 字节（缺失时拒绝 wrap，而不是用常量）。它按 AppleKeyStore 的 selector ABI
做**软件** key wrapping；keybag、passcode、reference-key 操作仍 unsupported，**没有**硬件数据保护。
r32 在行 10 加「最近四笔 selector/rc」环，被 panic 清屏抹掉；r33 移到行 6（panic 安全带）。

来源：`package/nuwa-aks/SOURCE.md`；`package/nuwa-aks/nuwa_aks.c`、`nuwa_aks_wrap.cpp`；
`scripts/build-ufs-apfs-root-chmh-r32.py`、`r33.py` 头注释。

### 2.7 watchdogd 策略：r34 起可关，恢复只靠去掉 boot-arg

从 `Allenwdk/UniXNU-uke@55909f42` 的 `package/BootWatchdogPolicy.c`（MIT）移植：
Data 卷校验通过后，按 `disable-watchdogd=1` 写
`/private/var/db/com.apple.xpc.launchd/disabled.plist`（XML、`com.apple.watchdogd` =
`com.apple.watchdog` = true、0644 root:root、`O_NOFOLLOW`），并建 `disabled.migrated`（`O_EXCL`）
让 launchd 走现代 override loader；`disable-jobs=<list>` 追加标签。未移植 uke 的 Gunyah
wdt petting/autoreset 与 `sheng_boot_setup_reset()`。效果：无 IOWatchdog 的板上 watchdogd 不再
`brk #1`；每次启动按当前 boot-arg 重写，去掉参数即恢复。

来源：`package/nuwa-watchdog/SOURCE.md`；`package/nuwa-watchdog/nuwa_watchdog_policy.c`。

### 2.8 SpringBoard SIGTRAP 是当前第一阻塞

r34 实机上 SpringBoard 与 mobileactivationd 都以 **SIGTRAP** 退出（`out/nuwa-r35-20261119/build.py`
头注释记录）。SIGTRAP 在这里是用户态主动陷入调试器（`__builtin_trap`/`brk`）的形态，不是内核 panic，
所以之前的 panic 安全带里读不到它所在的进程与原因。r35 因此新增「异常退出环」：
`boot_progress_exit()` 保留最后四笔 status 或 os_reason namespace 非零的退出，行 0 读
`EXk <comm6> <sig>:<ns>:<code>`，控制台打完整记录（pid/status/ns/code/nprocs 与当时的 AKS
调用/open 计数）。**r35 未上机**，所以 SIGTRAP 的 sig/ns/code 目前只有「是 SIGTRAP」这一层事实。

来源：`out/nuwa-r35-20261119/build.py` 头注释；`scripts/build-ufs-apfs-root-chmh-r35.py`。

### 2.9 显示链路与 SMP 仍缺（不是本轮改动能解决的）

- 显示：只有 `vinfo` 直绘的诊断页，没有 `GopFramebuffer` 与 launchd 的显示服务。r21 只修了
  渲染器（bind 去重、panic 后停画、关键行移入 row 0–8 安全带）并加了自检图案；
  r21 之前用户确认「面板上本身就不对」（`p1` 的 `1` 上半截缺失、`uni=1`→`uni=_`、
  `amfi`→`am..i`），代码侧已证明像素写入与 stride 正确，丢失在 framebuffer store 之后
  （DPU/DSI/面板或 fb 映射属性），未定案。
- SMP：页面 `armcpu_smp_*` 全程 `req=0 run=0 cond=0 boot=0`（r16 读数），即从未请求启动从核；
  到 r35 未改。

来源：`out/nuwa-r21-20261118/PLAN.md` §0；`out/nuwa-r16-video-frames-20261117/READ-r16-video.md` §3.8。

---

## 3. 当前阻塞（按解除顺序）

1. **SpringBoard / mobileactivationd SIGTRAP**：需要 r35 的异常退出环读数（sig/ns/code + nprocs +
   当时 AKS 计数），才能判断是缺 keystore、缺激活、缺显示服务还是别的原因。**需要一次上机授权。**
2. **显示服务未接**：`GopFramebuffer` 路径与 launchd 显示服务都不存在；即使 SpringBoard 起来也看不到界面。
3. **SMP 未启用**：`armcpu_smp_requested` 从未置位，用户态只有单核调度。
4. **认证 NOT REACHED**：CHMH 是未认证实验身份，ADT `TrustCache` 仍 `{0,0}`，
   root auth / trust cache 早初始化 / initproc exec 策略三条绕过仍 opt-in 生效。
5. **断电重启回同系统未验证**：本轮全部是 `vendor_boot_a` 载荷 + `fastboot reboot` 的运行态；
   没有任何一次断电重启后回到同系统的观测。

---

## 4. 证据路径（`out/` 被 `.gitignore` 排除，仅本机）

- 写入台账与回滚：`out/nuwa-boot-payload-write-20261115-01/`
  （`WRITE-r16..r34.json`、`WRITE-r23/r27/r28/r33-FLASH-REJECTED*.json`、
  `boot-observe-r16..r34-*.log`、`ROLLBACK-r16..r34.md`、`boot_a.stock.img`、`vendor_boot_a.stock.img`）。
- 每次打包：`out/nuwa-ufs-apfs-root-chmh-2026111{6,7,8,9}-rNN/`（`record.json` 有
  kernel/args/trust/config/seed 的 SHA、CHMH、payload 与 ADT 哈希；`-audit-r1/` 复现同一 outer）。
- 内核构建：`out/nuwa-r16..r35-2026111N/`（`kernel.macho`、`build.py`、`verify_rNN.sh`、
  每文件 `compile-*.log`、`root-config.json`、`provenance.json`）。
- r16 全量判读（唯一有主机读图的一轮）：`out/nuwa-r16-video-frames-20261117/READ-r16-video.md` +
  `dense/`（67 张定点裁图）。
- 无效修复清单：`out/nuwa-r28-20261119/INVALID-FIXES.md`（r22/r24/r25 的实机读数在这里）。
- 计划与需求：`out/nuwa-r19-plan-20261118/PLAN.md`（r18 实机读数、probe 语义）、
  `out/nuwa-r21-20261118/PLAN.md`（显示链路分析）。
- RAMBlock / keybag 说明：`out/nuwa-ramblock-*` 无独立目录，fork 说明在
  `package/nuwa-ramblock/SOURCE.md`；keybag seed 源在仓外 `D:/vmshare/data-8g-keybag.dbr`。

---

## 5. 下一步顺序

1. **一次有界上机 r35**（须当轮授权）：读 `EX1..EX4` 与 `nuwa: exit ...` 控制台行，确定 SpringBoard
   SIGTRAP 的 sig/ns/code 与退出时的 nprocs、AKS 调用/open 计数。这是唯一能把 2.8 从「是 SIGTRAP」
   推进到「为什么」的读数。
2. 按读数分支：缺激活 → 走 activation 面；缺显示服务 → 接 `GopFramebuffer`；
   缺 keybag/AKS 语义 → 回到 selector 层而非改 seed。
3. **接显示**：`GopFramebuffer` + launchd 显示服务，之后才谈「可交互」；渲染器层面的竖笔丢失
   （2.9）用 r21 自检图案的一张特写照片定案，不改面板/DSI 寄存器。
4. **启用 SMP**：先把 `armcpu_smp_requested` 置位路径与 PSCI CPU_ON 读通，页面 `SMP` 行从全 0 变化。
5. **交互目标验收**：到桌面/锁屏可操作 → 断电重启一次仍回同系统 → 才算达成；期间三处绕过保持
   opt-in，逐条按记录的解除条件删除（真实 trust cache / 认证链），不把 panic 消失当成功。
6. 新内核必须重新绑定 CHMH，不能复用 r34/r35 的 ADT/outer。

---

## 6. 记录缺口（明确写出来，不装作完整）

1. r17、r17c、r19、r20、r22–r34 的**屏幕读数没有主机读图文档**：照片/录像按硬约束不入 Git，
   本轮只保留仓库内已有的文字迹证。需要逐轮精确读数时，只能重看当时素材，不能从本文反推。
2. r17c 的载荷哈希在 `WRITE-r17c.json` 与上表一致（`dfbbc303…c7a1`，全文已在表中）；
   `ROLLBACK-r34.md` 的备用清单只保留前缀，以该 JSON 为准。
3. r34 的 seed（`data-8g-keybag.dbr`）**不在仓内**，只在 `D:/vmshare`；仓内可复现的是哈希与
   打包脚本的 pin，重新打包需要该文件存在。
4. 本段没有独立 `verifier` 复跑任何构建或打包；所有主机侧能力仍是 self-checked。

---

## 7. 审查留痕

- root cdir 引用方案（2.3）与 IOKit 发布方式（2.4 / 2.6 的 `preModLoad`/`postModLoad` 括号 +
  `bsd_autoconf` 后创建）经 **Sonnet deep_reviewer** 审查，结论 **CHANGES REQUIRED**，
  随后按建议实现（主控转述；无独立 `verifier` 复跑）。
- 本轮记录没有新的设备写入动作，也没有对上机载荷做不可逆操作；写入台账见 §4。

---

## 8. 复跑（主机，不连设备）

```sh
cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa
PY=/home/wh1stl3/.local/bin/python3.11

# 每次打包复现同一 outer（必须新建目录；--audit 指向已记录目录）
$PY -B scripts/build-ufs-apfs-root-chmh-r35.py --output out/verify-r35-<run>/
$PY -B scripts/build-ufs-apfs-root-chmh-r35.py --output out/verify-r35-audit-<run>/ \
    --audit out/nuwa-ufs-apfs-root-chmh-20261119-r35

# 回归与 profile 门
$PY -B scripts/test-ufs-apfs-root-profile.py
$PY -B scripts/test-ufs-apfs-root-chmh.py
$PY -B scripts/run-pmap-ret-once.py --self-check
```

注意：打包脚本只吃已记录的内核文件与顺序固定的输入，能复现 outer 哈希，但**不能**通过换输出目录
复现记录里的内核哈希（内核构建产物本身才是 pin）。
