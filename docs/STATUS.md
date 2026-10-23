# STATUS

> 当前唯一真相；0012 MMU分支包实测完成并恢复Android。

## 最新实机结论

新包2b203afa（CI39958974666，源码ee98dfe）已临时启动，命令成功。用户文本与原图确认Debug/Extract成功返回，最后可见Mmu enter；未见新增MMU after-guid-query或后续日志。尚无DXE/SHENGMEM/XNU证据。

只能界定GUID HOB查询及随后日志路径，不能确认具体故障指令，也不能认定cache已执行。120秒USB观察不替代固件日志，当前留存单张照片而非连续录像。

用户按键回fastboot后，原厂boot临时加载成功；21:22:57确认nuwa Android完成1，postcondition再次确认A槽和三分区SHA与试前相同。本轮恢复完成。

[实测及时间戳解释](operations/2026-10-23-mmu-branches-trial.md)；[构建验收](operations/2026-10-23-mmu-branches-build.md)。完整证据reports/mmu-branches-trial/2026-10-23-evening/。

## 下一步

离线核对GetHobList/GetNextGuidHob遍历及紧随其后的日志输出路径，基于实际链接实现设计可区分诊断。没有故障PC/运行HOB链证据，不跳过cache或伪造HOB。下一包实测仍须通知用户并刷新录像/恢复门。

屏幕06:50:55为固定SOURCE_DATE_EPOCH（固件ddd794f提交的UTC时间），不是本轮编译时刻；本次发送哈希2b203afa与旧530f56b4不同。

## 固定边界

39输入/41行内存表及BootShim/PIL保持；新包不含FAT/ADT/XNU/ramdisk。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、XNU8796.141.3、ipad_identity=true、board example=true保持。board/feed/内存基址/验证标记未改，两旧仓只读。
