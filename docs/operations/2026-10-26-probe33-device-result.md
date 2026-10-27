# PROBE33 实测与恢复闭环

PROBE33 / revision41 单次临时启动于2026-10-26 22:18:53 +08:00，已consumed、禁止重发。用户提供PROBE33.jpg并报告已回Android；本轮只读后验于22:21:17确认nuwa/kalama、sys.boot_completed=1、A槽及三分区摘要与预检一致，未额外恢复boot。

原图5252708 B，SHA256 `112f3c21959fcbd5c7c9e11d4afed2a0f0845339f8b2def4c5b5d4ff12a1e66f`。原件及派生图只在本地Media-nuwa；清单为derived/PROBE33/review-01/manifest.json，文字及输入绑定为reports/xnu-entry-probe-trial/2026-10-26-v41/{screen,media-binding}.json。视觉读数不是用户逐字符确认；原件未改写。

## 实测事实

276/277绿色；278—287为调用青色、接续绿色；288/289未观察点亮；290—293成对，294青色、295未观察点亮。后续未观察到完整读取返回、init/exec成功或用户态。

固定代码映射：uio_resid、uio_offset、vnode_mount、vfs_fsprivate、vnode_fsnode及两处APFS内部直接调用均已有接续标记；可选288/289未经过不等于失败。294位于0xfffffff0051a59b8原生BL之前，对应_decmpfs_read_compressed经导入stub调用。只能证明到达调用前观察点，不能证明被调函数入口、锁等待或死锁。

A02B=D9，A033=FFFFFFF005F48EF8，A034=110，A035全F，A036/A037=FFFFFFF0051A5858；A038=0、A039全F是revision41延后HEX刷新的正常初始显示，不代表没有正文进展。完整字段见screen.json。PROBE32的0x1000仍是uio_resid剩余请求量，不是已读取长度。

## 工程判断与下一步

相对于PROBE32，本轮可见进度越过了uio_offset等多个原生调用，继续沿当前RAMDisk/APFS读取主线调查压缩读取。优先区分压缩读取是否实际进入、首个锁是否返回、缓存/压缩头/获取函数/解压路径是否返回。其依据是294而非旧注册表猜测；尚无证据指定某把锁永久死锁。观测代码负载、布局及显示可见性仍是替代解释，单轮进展不证明唯一根因修复。

PROBE34离线固定指令审计记录reports/kernel-entry-probe/2026-10-26-v42-preparation/decmpfs-native.json：入口0xfffffff007480028；首个_current_act调用0xfffffff007480078，首个_IORWLockRead调用0xfffffff007480090。锁、错误、认证及239释放门保持，静态可确定的绑定/ABI/保存与恢复先在代码中核对，实机只集中补运行时事实。

黑格与已有标记初始化区域相符；照片未完成逐像素透视校准，不声称显示硬件故障或全部黑色代表未执行。UFS未通过XNU实机验收；当前根为RAMDisk/md0，没有证据把本次压缩读取边界归因到UFS。
