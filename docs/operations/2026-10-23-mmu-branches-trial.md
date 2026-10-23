# MMU分支诊断包实测

2026-10-23T21:23:58.332786+08:00。用户明确“可以开始”，在启动前通知录像后临时启动新包2b203afa。未flash、erase或改槽。

## 执行与屏幕

实际发送out/trial-boot/mmu-branches-39958974666/boot-mmu-branches-v4.img，SHA2b203afa8372e99ebd9049b276c41984fa16db4d92a92a6cea0f3b4904c403dd；fastboot返回0。
USB观察120.0秒，共59条；这不是固件阶段日志。用户文本及原图确认Debug/Extract leave Success，最后可见[NUWA-CTOR] Mmu enter，没有[NUWA-MMU]。原图SHA e1bc997f75acf15d06f86354a2cd740662e15377ef905357b50d09847b316187。
当前仅有单张照片及用户报告，未取得连续录像，不声称全过程画面不变。

0012第一条after-guid-query在GetFirstGuidHob调用之后。缺此日志只能界定查询或紧随其后的输出路径；尚不能证明HOB遍历死循环，也不能证明进入cache分支。后续优先审查GetHobList/GetNextGuidHob/GET_NEXT_HOB及日志实现，不能直接绕过cache或伪造HOB。

## 六点多时间戳的解释

屏幕Build at 06:50:55不是本轮CI执行时间。scripts/ci/build-firmware-candidate.py:156固定SOURCE_DATE_EPOCH为固件ddd794f提交时间1792738255，即2026-10-23T06:50:55Z（北京时间14:50:55）；Sec.c:38显示__TIME__/__DATE__。新旧诊断补丁均基于此提交，所以时间相同。
launch.json记录本次新包路径与SHA，实际FD ea0277e8已核验五条MMU字符串。发送新包与运行到新日志是两个不同结论。详见timestamp-and-package-check.json。

## 恢复

用户确认“已进入 fastboot”；恢复脚本复位bootloader并临时加载原厂boot ef558db2，命令成功。2026-10-23T13:22:57.370420+00:00确认真实nuwa Android完成1；postcondition再次确认nuwa/kalama、A槽及boot_a/vendor_boot_a/init_boot_a三分区SHA与试前一致。
本轮恢复已完成，没有遗留设备恢复动作。未进行第二个候选试验。

证据：reports/mmu-branches-trial/2026-10-23-evening/的preflight、launch、actual-screen、screen-observation、recovery、postcondition、timestamp-and-package-check、trial-summary。
