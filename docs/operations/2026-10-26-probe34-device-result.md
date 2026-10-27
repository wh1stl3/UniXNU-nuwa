# PROBE34 实测与恢复

2026-10-26 23:03:57 +08:00单次临时启动，已consumed，禁止重发。合格包reports/xnu-first-entry/entry-probe-34.json，SHA256 586a12a37076a73d36a478a5f1202de436b734b1edf2f699856a7b753e77506f。31项串行离线检查、1744透明性、476原读取位置、617新增位置、53绑定、独立内核逐字节重建及最终包回读通过，证据v42-r2/qualification.json；这些不是实机结果。

用户原话：等待约10秒以上，画面已不再变化。媒体为Media-nuwa/PROBE34.jpg，原件与派生仅本地保存；screen.json和media-binding.json在reports/xnu-entry-probe-trial/2026-10-26-v42。视觉转录不是用户逐字符确认。

本轮266/268/270/272青色、269绿色，未见273、276、294或373点亮。A034=110，A035全F，A036=A037=A038=0，A039全F。没有复现PROBE33的入口及压缩读取前294；不能据此把34解释为压缩读取体内死锁或用户态进展。也不能将272或最后一次可见字段当CPU精确停点。

静态比较：33与34的probe_dense_746c688均为0xfffffff008498218，replay均为0xfffffff0084987dc；分派观察代码并未因新增内部点而改变起止地址。诊断状态从0xfffffff0084b20d8移到0xfffffff0084bc0d8。新内部观察尚无执行证据，初始清屏和观察布局/负载仍不同；这些事实不足以指定唯一根因。下一步先检查观测路径的重复HEX代码/写入负载，保留原生锁、错误、IRQ和239门，不按缺失格点猜改原生函数。

首个后验查询因身份或Android完成门未通过而失败，随后短暂ADB目标不可见；失败记录postcondition-first-failure.json保留。用户自行恢复后，仅只读重查，23:10:52 +08:00 postcondition.json确认nuwa/kalama、Android1、A槽、三分区摘要与预检一致。未额外恢复boot。
