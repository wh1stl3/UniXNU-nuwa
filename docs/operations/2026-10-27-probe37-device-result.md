# PROBE37：固定type4回调入口已观察

原件 `D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE37.jpg`、`PROBE37.mp4` 本地保留，未修改/上传。照片、4.906411秒录像及派生裁图/2fps接触表绑定在 `Media-nuwa/derived/PROBE37/review-01/manifest.json` 和 `reports/xnu-entry-probe-trial/2026-10-27-v45/media-binding.json`。录像长度不是用户等待时间；本次未另行询问稳定时长，抽样后段画面相近。

可见441品红fetch入口，442/443锁调用/续接，444/445注册函数查询/续接，446间接调用前；467品红固定type4回调入口。这比36仅到416外层调用前进一步，现已具备固定回调入口执行的屏幕证据，不能继续沿用“回调尚未进入”的旧状态。该入口观察约束实际x8、线程、外层配对与嵌套帧/LR链。

470、478琥珀标记可见，分别对应回调内helper调用及第二处IOMallocData调用前。479白线与原Logo相交，不单凭其外观认定分配返回或分配器卡住；447 fetch间接调用续接、295 APFS返回及完整header/exec/用户态未观察到。手工核对HEX与36一致，详见screen.json。

当前应同时辨别分配内部、返回后的原生写入/向量准备及decode helper。不能把网格外观当主线终点，也不能声称观察器对时间与可见性毫无影响。下一候选合并上述路径，不猜改锁、分配结果、错误、缓存或IRQ。

代码可确定：fetch在进入回调前置w5=1；回调保存为w21，因此第二处分配请求为((1+1)<<4)|8=40字节。这里指IOMallocData入口请求，IOMalloc_internal可能根据运行时追踪标志增加开销，不声称底层实际分配尺寸恒为40。IOMallocData尾跳IOMalloc_internal，须保留原生LR来关联回调，不能假定它自己建栈或有RET。

2026-10-27 01:08:58 +08只读后验确认Android完成1、nuwa/kalama、A槽、三分区摘要与37预检一致。无额外恢复boot。postcondition.json闭合历史consumed中的恢复待办，不改写当时快照。PROBE37已消费禁止重发。UFS和真实用户态仍未验收。
