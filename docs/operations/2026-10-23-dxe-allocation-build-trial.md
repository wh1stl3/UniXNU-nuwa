# R-010 A 分配器快照构建与试验

用户批准A，同时修订硬停边界（D-021）。生成镜像无需暂停；设备动作前必须有具体日志观测及已确认恢复路径。用户已回复“可以，启动前通知我”，可录像屏幕；尚无独立USB日志。R-009按键回fastboot和已校验原boot恢复Android完成1为历史恢复证据，本次启动前重新核对在线身份与状态。

固定固件2ab6827d、UniXNU75bc13dd、Mu cfb93724均保持；只额外应用0008（SHAac8bd476…），两文件原/后LF哈希、raw哈希见config/firmware-dxe-allocation-profile.json。保留CRLF仅针对该补丁的两个精确目标，仍严格git apply --check/apply，不使用ignore-whitespace。CI构建后继续检查后置哈希。MemoryMapLib、nuwa.toml、board及feed哈希不变。

验证：`python -B scripts/check-dxe-allocation-profile.py`：35项静态检查通过；`scripts/ci/inspect-firmware-candidate.py`对39820752081旧真实产物的回归检查通过。新增验收从实际FD嵌入DXE_CORE GUID D6A2CB7F-6A18-4E2F-B43B-9920A733700A的PE/TE查找两个stage及请求/汇总字符串；该GUID来自固定Mu DxeMain.inf。不以profile声明替代实际核心内容。

构建尚未执行；当前没有R-010镜像或实机结果。源码及旧包检查不等于新编译通过。


## 构建与试启动门进展

CI39826580758从设备316c19f启动，工具安装44秒后进入构建，结果待取。新增trial-v4的D-021前置检查：启动必须携带当前package哈希匹配、15分钟内nuwa Android完成1、用户可录像明确答复及实际已成功恢复Android的证据文件/哈希；缺失则在设备命令前拒绝。负向检查见reports/dxe-allocation-audit/gate-check.json。恢复路径仍允许原boot恢复，并修复等待期间fastboot晚出现时未接管的问题；不循环发送原boot。

新增record-nuwa-trial-state.py只读采集设备身份/Android状态/槽位/三个分区摘要；本轮android-online-before-build.json确认nuwa/kalama完成1及三个SHA与R-009恢复值相同。当前尚未试启动。拍摄条件由用户明确答复“可以，启动前通知我”，启动前仍需告知。
