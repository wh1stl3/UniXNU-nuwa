# 独立uefi-nuwa源码仓接入

## 仓库组织

目标三仓：wh1stl3/UniXNU（基座）、wh1stl3/UniXNU-nuwa（设备）、wh1stl3/uefi-nuwa（固件）。

2026-10-22创建公开独立固件仓。账号已有wh1stl3/uefi-enuma，parent为UniXNU/uefi-sheng，source为Project-Silicium/Mu-Silicium；fork API返回已有enuma而非新仓，脚本在任何该仓配置/分支修改前因名称断言退出。没有重命名或改动enuma。

改用独立Git仓保留原Mu-Silicium提交历史：临时GitHub Actions环境只进行bare fetch/push，不检出源码、不构建固件。本机只读源树不修改、不复制；不使用--force或--mirror。GitHub Source Imports API已退役，未调用该失效接口；参考[GitHub公告](https://github.blog/changelog/2023-10-11-deprecation-source-imports-rest-api/)。

固定上游main=42fe563791e51bf5500c2e470ed294ca0c94b97c，nuwa分支codex/nuwa-bringup从已验证基线6c6755012728c9f7de748228758bad94d1e9a660开始，导入任务先验证祖先关系。新仓Actions已关闭，避免继承的固件工作流自行运行。

## 导入任务与后续接线

.github/workflows/import-uefi-nuwa-source.yml仅手动调度，产物仅source-import.json；通过临时UEFI_IMPORT_TOKEN仓库secret访问新仓，凭据只经stdin送入GitHub加密secret，不进入命令参数、文件或证据包。任务结束后删除该secret。已有Git/gh/secret授权覆盖此步骤。

导入完成后运行scripts/provision-uefi-nuwa.py：校验来源与patch哈希，在RAM生成已有BootShim/SEC/DSC/FDF改动，发布新固件分支单提交；将裁剪后的只读initrd发布器纳入nuwaPkg并保留来源/许可与模块GUID。完整树比较确认内存/配置图和子模块不变，原main保留。

下一步建立设备仓的独立固件profile，引用该固定提交并避免重复应用已入仓patch；历史patch/原构建profile继续保留。firmware与device源码迁移不等于新FD已构建，更不等于实机阶段通过。board/内存/镜像/_verified边界保持。

## 完成结果

源导入CI[39796387414](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39796387414)成功，临时UEFI_IMPORT_TOKEN已删除。固件源码[0a3a51af229eabe76bcc9dcb90d3ce985223b125](https://github.com/wh1stl3/uefi-nuwa/commit/0a3a51af229eabe76bcc9dcb90d3ce985223b125)已发布，默认分支codex/nuwa-bringup；2256个非目录树条目逐项匹配，保护的内存/配置图、nuwa.toml、.gitmodules和全部子模块SHA与原基线相同，main保留42fe563。

新增config/firmware-dedicated-profile.json；构建入口--profile dedicated读取独立仓固定提交，四个模块的路径和发布器输出名已接入。原firmware/sheng补丁已经落在新仓，不再重复apply，只保留设备侧Darwin22 ABI patch。构建前后继续检查来源哈希；原manifest及patch文件保留，--profile legacy可用于历史回归。尚未调度新固件CI，没有新EFI/FD或boot.img。

执行scripts/prepare-dedicated-firmware-profile.py --firmware-checkout D:/Code/uefi-nuwa通过31项输入检查；Mu_Basecore未初始化时，仅从同固定Gitlink的只读缓存校验其BaseFdtLib.inf，报告明确区分来源。四模块、两外部包、一条剩余patch及未变board/feed哈希检查通过。发布器以PiDxe.h及INF消耗GUID的AutoGen等价声明作AArch64语法检查通过；第一次简化前置头缺PI类型的失败也保留，不能把测试前置头问题误判为完整固件构建失败。

## 本地检出

用户要求补齐独立本地目录后建立D:/Code/uefi-nuwa，并更新设备AGENTS目录边界；旧资料库仍只读。普通HTTPS clone卡在0字节临时pack，固定提交归档下载也超时；只结束匹配本次目标URL/目录的clone进程树。

scripts/bootstrap-local-uefi-nuwa.py利用原只读Git对象缓存和API元数据重建精确提交/树，加上RAM中已验证的12个变更blob；Git repack后移除alternate，本地仓库不再依赖旧缓存。工作区2256项与远端0a3a51a相同、干净，完整git fsck通过；dangling的旧基线commit不是完整性错误。初次alternate文件因Windows CRLF被Git当成路径尾字符，已以LF写入修正；未修改旧缓存。

本地是depth-one检出，远端保留完整导入历史；子模块未初始化，没有伪装为完整可构建环境。reports/uefi-nuwa/local-checkout.json记录HEAD、分支、Git完整性和独立对象存储结果；profile-check.json记录实际本地文件校验。所有结果仍为源码/静态证据，不是固件或实机通过。
