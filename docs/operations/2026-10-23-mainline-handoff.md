# 主线交接（2026-10-24更新）

先读AGENTS、STATUS和DECISIONS。设备仓本轮基线5b782d9；固件codex/nuwa-sec-handoff-trace@00a37d9。两旧资料库只读，不设置_verified或未知板值。

## 当前实机事实

最后试验87b14624/3153920B，CI39988591973/source b4f9075，FD70b266b3。两原图确认4MiB FV发布Success及唯一NUWA VOLUME PROBE配置菜单。包无XNU/ADT；timeout60/action exit解释回固件/无OS。原chosen封装依旧absent。证据reports/embedded-probe-trial/2026-10-24/。

本轮recovery.json及postcondition.json记录Android完成1、nuwa/kalama、slot_a、三分区SHA与preflight一致；实际查询时间取postcondition.at。人工恢复已闭环。没有flash/erase/改槽。

## 本轮离线进展

当前77742999＋donor2ec297ba生成分析候选5a128fb2/58335232B。65348项绑定逐项读回一致，30段组件及native执行字节不变；DarwinBoot主机ParseKernel接受15非零段/74174464B跨度；20解析正反例与4项常量池反向测试通过。Libm精确1224B指纹补丁仅在内存应用固定工具，不改只读源码。

早期安全initializer为空、完整ABI未验收，loadable=false，不能直接加入设备菜单。完整二进制和大报告在out/native-prelink-current/analysis；精简报告reports/native-prelink-current/emission.json及loader-parser.json。细节operations/2026-10-24-current-native-prelink.md。

## 直接续接

- 复现常量区证据：`python -B scripts/qualify-libm-literal-pool.py --output reports/native-prelink-current/<fresh>.json`。
- 复现分析候选：`python -B scripts/emit-current-prelink-analysis.py --work out/native-prelink-current/<fresh> --output reports/native-prelink-current/<fresh>.json`。
- 继续独立UEFI运行内存/CPU入口审查，形成具体连续窗口和目标Apple ADT方案；不使用总DRAM/其他板地址作为分配证据。
- 新包构建/完整产物校验可直接进行；启动前须新鲜用户录像、唯一nuwa身份、包复验及具体恢复门，通知后执行。仅一般“继续”不替代录像可用性。
- 源内核、分析用prelink、真实ADT、阶段入口、根存储/iOS运行分别验收。CPU Vectors、TZ/SPSS/Rsc独立问题仍未修复，不因配置发现成功自动关闭。

## 启动输入诊断续接

新增独立boot-input-audit，固件6176a82；46输入9补丁12后哈希已验，完整CI待触发。命令：`gh workflow run firmware-candidate.yml --repo wh1stl3/UniXNU-nuwa --ref main -f profile=boot-input-audit`。打包 `scripts/embedded_probe_package.py RUN --profile boot-input-audit`；新包仍需新的录像确认。无本轮设备动作，最近postcondition仍为embedded-probe-trial/2026-10-24。
