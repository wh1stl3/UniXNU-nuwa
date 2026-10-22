# R-010 A 分配器快照构建与试验

用户批准A，同时修订硬停边界（D-021）。生成镜像无需暂停；设备动作前必须有具体日志观测及已确认恢复路径。用户已回复“可以，启动前通知我”，可录像屏幕；尚无独立USB日志。R-009按键回fastboot和已校验原boot恢复Android完成1为历史恢复证据，本次启动前重新核对在线身份与状态。

固定固件2ab6827d、UniXNU75bc13dd、Mu cfb93724均保持；只额外应用0008（SHAac8bd476…），两文件原/后LF哈希、raw哈希见config/firmware-dxe-allocation-profile.json。保留CRLF仅针对该补丁的两个精确目标，仍严格git apply --check/apply，不使用ignore-whitespace。CI构建后继续检查后置哈希。MemoryMapLib、nuwa.toml、board及feed哈希不变。

验证：`python -B scripts/check-dxe-allocation-profile.py`：35项静态检查通过；`scripts/ci/inspect-firmware-candidate.py`对39820752081旧真实产物的回归检查通过。新增验收从实际FD嵌入DXE_CORE GUID D6A2CB7F-6A18-4E2F-B43B-9920A733700A的PE/TE查找两个stage及请求/汇总字符串；该GUID来自固定Mu DxeMain.inf。不以profile声明替代实际核心内容。

构建尚未执行；当前没有R-010镜像或实机结果。源码及旧包检查不等于新编译通过。


## 构建与试启动门进展

CI39826580758从设备316c19f启动，工具安装44秒后进入构建，结果待取。新增trial-v4的D-021前置检查：启动必须携带当前package哈希匹配、15分钟内nuwa Android完成1、用户可录像明确答复及实际已成功恢复Android的证据文件/哈希；缺失则在设备命令前拒绝。负向检查见reports/dxe-allocation-audit/gate-check.json。恢复路径仍允许原boot恢复，并修复等待期间fastboot晚出现时未接管的问题；不循环发送原boot。

新增record-nuwa-trial-state.py只读采集设备身份/Android状态/槽位/三个分区摘要；本轮android-online-before-build.json确认nuwa/kalama完成1及三个SHA与R-009恢复值相同。当前尚未试启动。拍摄条件由用户明确答复“可以，启动前通知我”，启动前仍需告知。


## 首轮39826580758失败与最小修复

实际首错`MdePkg.dec(33): error 000E`，`Library/MipiSysTLib/mipisyst/library/include`不存在；25条命令已到build入口，尚未编译核心。下载证据包18项大小/哈希逐一匹配。补丁严格应用和后置输入hash均已通过，CRLF例外生效；不归因于C编译错误。

submodules-final.txt显示Mu嵌套gitlink均为未初始化（前导减号），setup只有Mu行缺“## Done.”的常规格式；已修改Mu工作树使Stuart setup未补齐其嵌套依赖是当前解释，精确内部判定未单独跟踪。按DeviceBuild.py GetRequiredSubmodules对Mu声明recursive=True的契约，在应用诊断前主动`git submodule update --init --recursive --depth 1`，仅在CI临时Mu目录执行，使用原gitlink，不更新版本或改只读缓存。运行待重试。


## 重试39827372451真实编译错误与修订

5m10s失败，build.log:1714/1721首报DxeMain.c:575/577未声明CoreAcquireMemoryLock/CoreReleaseMemoryLock；前轮嵌套依赖问题已消失，实际核心C编译开始。下载所有inventory项逐一验证，准确错误行/原build.log摘要见compile-errors.json，原完整build.log仍在本机out证据包。

这两个函数在固定Mu Mem/Imem.h:106/115声明、Page.c:90/102实现，DxeMain.h未导出；草案静态apply不检查C声明可见性，不能当编译证明。修复不手写既有原型、不禁用-Werror、不改锁：Page.c新增CoreNuwaDumpAllocationStateWithLock包装，在其原有可见上下文取锁/快照/放锁；DxeMain只声明并调用包装。首次分配失败仍使用原已持锁的内部快照。保持两文件和日志语义，patch更新为bb8bf3ece733c4410e33477da65e414841a7b890f4f3c54d94c651af47ca3af2，原修订证据保留preview-at-build.json。35项输入及严格apply检查再次通过，修订版实际编译未验证。


## 第三轮39828647170工具安装超时

本轮只运行到Install build tools，360秒超时124，编译步骤跳过，out未创建，因此无artifact；服务端失败日志已保存failed-actions.log。实际ubuntu.sources的URIs为mirror+file:/etc/apt/apt-mirrors.txt，两条均如此；apt update和install继续使用Azure，最后下载cpp-13-aarch64-linux-gnu 10.8MB处超时。原sed只处理sources内直接Azure URL，无法触及间接mirrorlist。

修复仅把本次明确观测的mirror+file URI换为https://archive.ubuntu.com/ubuntu，Signed-By、Suites、Components原样保留；预检遇残留Azure或任何未处理mirror+file即失败，不放宽签名或延长超时。工作流安装脚本经WSL bash -n通过。尚未证明新runner下载完成。

顺手纠正DxeMain包装声明的旧注释为“wrapper acquires and releases the core memory lock”，无C语义变化；当前0008 SHA4a859ab6108270229fd305d091deaa6cd2d76c37e62dbce823b7e848c73750e1，35项原/后输入及严格apply再次通过。包报告增加实际设备提交/诊断patch SHA，启动门核对当前精确profile补丁。


## 第四轮39829943950构建与实际产物通过

设备c9d538f，固定源和0008 SHA4a859ab6，CI6m51s成功；安装问题未重现。下载666项清单/文件哈希及输入检查通过。实际FD3MiB SHAd9c3eaa0d5eefd9e237dfd74f7d98402d93764d47cf4126a3c9bba9e4f5b860f；实际DXE核心167936B SHAc013504794e83635c1b9f7b197d3f1c5ff64f96568b37cd2b7ae952f658f4014，五个诊断标记均在真实PE/TE中，四EFI/SEC/DEPEX/HOB及原PIL/空AUTO验收通过；shim SHA8a3b5476、relative offset0保持。

v4包3153920B SHA9197fed24748e1fa2b79da879e3c58c2018e3db943526d65641f86cb2226c0d6，只改原v4 header kernel_size，内容为已验shim+FD，无XNU/FAT/新DTB/ramdisk。包报告包含实际设备提交、源提交及patch哈希；来源未复制入本仓，产物留out未提交。

当前到静态产物核验为止，尚未临时启动。下一步重新读Android/分区摘要并按D-021检查日志与恢复门，启动前通知用户录像。


## 唯一一次临时启动与恢复等待

试前重新读取nuwa/kalama Android完成1、A槽和三个分区SHA，原Android恢复输入完整哈希再次匹配；D-021当前包哈希/新鲜状态/用户录像确认/历史具体恢复证据门通过。提前15秒通知录像后，02:27执行唯一一次包9197fed2的fastboot boot，Sending3080KB 0.075s/Booting0.117s均OKAY，15次采样nuwa fastboot均false；只记录命令接受，不认定阶段运行或XNU。

具体屏幕/分配数字仍等用户回传。当前已启动原Android恢复等待，用户录完后只需按电源+音量下；H-005已记录，主机如检测到nuwa fastboot会复位bootloader后临时加载原boot并检查Android完成1。当前未确认恢复完成，不掩盖为已恢复；不再启动候选包。
