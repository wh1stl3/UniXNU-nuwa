# nuwa HID stage 刷写观察（2026-11-23）

- 写前审查：主控转述 reviewer 审 `3cd1476`，**PASS WITH CONDITIONS**；方案 A 审查，未经深审。
- 判读边界：仅 `H=5` 且之后仍无帧才支持“该身份不足”；`H=2/7` 不能定位失败；缺行不等于 0；`H` 可能滞后。
- 文档待修正：阶段文档的 `H=2` 应描述为“未取得 IOHIDResource（含 serviceMatching 返回空）”，不只是超时。
- 目标 outer SHA-256：`01e6e1c71346c05fb7cc9885d1179346b72e296ef3bbd993952017b6edd6479d`；回滚 outer SHA-256：`7d9f09cb26eded61e2fdfc9b90ae137a45c7fa9baba4c3687de1a57246dbea49`。
- 设备判定：fastboot 恰有一台 nuwa，当前槽 `a`，`vendor_boot_a` 大小 `0x6000000`；另有一台 enuma，仅只读查询型号。
- 指定 Python 从 outer 提取后核对：args 含所需参数且无禁用参数，`/chosen/display-scale` 为 4 字节 `03000000`，encoded seed SHA-256 为 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`；self-checked。
- 2026-11-23 12:16 +08:00：`vendor_boot_a` 发送及写入均 OKAY，flash 退出码 0；随后 reboot OKAY、退出码 0。未做镜像回读或启动画面判读；运行与交互尚未验证。
- 本地命令与输出记录：`out/nuwa-hid-stage-flash-20261123/execution.log`；此前枚举及校验命令未逐项采集时间戳。
