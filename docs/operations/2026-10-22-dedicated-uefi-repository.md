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
