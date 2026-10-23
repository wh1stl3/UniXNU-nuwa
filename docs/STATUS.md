# STATUS

> 当前唯一真相；0012 MMU分支诊断包构建核验完成，等待用户实测安排。

## 当前结论

CI39958974666成功（设备源码ee98dfe）；独立mmu-branches profile已接入0012。新v4包3153920B/SHA2b203afa，FD ea0277e8。实际SEC五条MMU、八条CTOR、四条HANDOFF及基线检查通过；41行内存表/2952字节与R-011完全一致。严格整头/载荷/填充重建通过。

[构建验收及完整哈希](operations/2026-10-23-mmu-branches-build.md)。包：out/trial-boot/mmu-branches-39958974666/boot-mmu-branches-v4.img；证据：reports/mmu-branches/39958974666/。五项离线反向测试通过，ready_to_execute=false。

## 实机状态与下一步

本轮无设备读取/启动/刷写。最新实机仍为旧530f56b4：Debug/Extract成功，最后可见Mmu enter；具体指令/分支和日志路径未定位，未见XNU。最近恢复仍是19:46:21 Android完成1及三分区SHA不变，并非本轮状态。

下一步先通知用户录像，再刷新nuwa身份、Android状态、三分区哈希和恢复门。新preflight需要本轮实际capture-confirmation；条件齐备再临时启动新包，记录120秒以上过程日志。实测结束确认Android完成1和三分区不变。不得拿旧包期待新日志。

## 固定边界

4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、XNU8796.141.3、ipad_identity=true保持；board仍example=true。board/feed/内存基址/验证标记未改，两旧仓只读，原未跟踪文件保留。

稳定SEC/DXE后再推进SHENGMEM/真实initrd、小FAT、当前预链接/ADT、EL1/XNU和根卷；当前包不含这些负载。
