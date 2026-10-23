# R-011 后系统卷发现与 initrd 契约审查

## 已确认进展

用户明确回复“先看到上述菜单再报错”，对应 Return to firmware / Restart / Power off 三项。结合固定 UniXNU 75bc13dd34dc4e403826793739e316a264ce00dd 的 Config.c:35-56、1517-1548，以及固件 1ccf760 的 BootManager.c:210 和 NoBootOS.bmp，可将本轮记为用户实机观察到 UniXNU 菜单后返回 BDS 无 OS 页面。原始文字与来源关系见 `reports/factory-heap/39835052901/user-observation.json`，未收到本轮照片/录像，不补造日志。

R-011 包无 FAT、XNU、ramdisk，不能加载未提供的系统。09:14:28 已恢复 nuwa/kalama Android，boot_completed=1，三个启动分区 SHA 与试前相同；本次审查只读取 Android，没有切换模式或追加试启动。

## 当前发现链路

固定 UniXNU 的 `package/UniXNUPkg/UniXNUPkg.dec:42` 指定 `\EFI\UniXNU\unixnu.toml`。Config.c 的 UniXNUConfigLoad 先查自身 DeviceHandle，再查 SimpleFileSystem 卷；无配置时使用三项内置动作并扫描 `\EFI\BOOT\BOOTAA64.EFI`。仅进入菜单并不证明系统卷、DarwinBoot、Apple ADT 或 XNU 可用。

固件 `Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c:132-188` 从 `/chosen` 读取 linux,initrd-start/end，要求正长度且能被512整除，然后将整个范围发布为只读 BlockIo。该实现不会剥除 vendor/cpio 前缀，也不会从拼接范围内定位 FAT；整扇区检查通过也不等于 FAT 挂载通过。其日志仍使用继承的 SHENGMEM 前缀。

同 SoC 复用已有 sheng 来源的 initrd BlockIo 机制有参考价值，但该实现自身的整段/整扇区契约需要在 nuwa 上验证；不能因同 SoC 将 Android 的组合 initrd 当作已验证的 FAT 载体。本次不引入其他板地址或更改内存表。

## 只读采集证据

命令与输出摘要在 `reports/system-volume-audit/inputs.json`；脚本为 `scripts/audit-system-volume-inputs.py`。先筛选 ro.product.device=nuwa，再核对 DT 的 nuwa/kalama 和 boot_completed=1；仅读取启动分区头、vendor ramdisk 前缀及108字节 fragment table。未保存新镜像，设备序列号未入报告。

| 当前 Android 输入 | 实际读取结果 |
| --- | --- |
| boot_a | v4，kernel 40417792B，ramdisk 0B |
| init_boot_a | v4，kernel 0B，ramdisk 2969050B |
| vendor_boot_a | v4，page4096，header2128，vendor ramdisk30899943B，DTB3885003B |
| fragment table | 108B，1条，offset0/size30899943/type1，名称为空 |
| bootconfig | 头字段声明113B；未解析其内容 |
| 恢复后 Android `/chosen` initrd | [0xb5fb2000, 0xb7fff1d4)，33870292B，模512余468 |

DT 摘要 `android-dt-after-r011.json` 的原始 DT SHA256 为 e7217b1575c7a7c2ca4bd758ab7fc20f580533cae4ea85631608997fede51e1d；原 DTB 仅放忽略的 out 中。这里只记录实际 Android 地址，不把它们写成候选启动地址或 board 配置。vendor header 的地址字段也明确标为声明值、非运行地址。

vendor 与 generic ramdisk 声明长度之和为33868993B，与实际 Android chosen 长度差1299B。没有安装 ABL 的完整拼接跟踪，不能据此自行分配差额、断言固定偏移或将尾部向上取整后作为可读内存。前缀十六进制见 JSON，未以解压验证替代缺失的数据。

字段格式依据固定 [AOSP bootimg.h](https://android.googlesource.com/platform/system/tools/mkbootimg/+/808d42e197506319ee65eb078d3defd9602e2ac2/include/bootimg/bootimg.h)，Apache-2.0，源文件 SHA256 276f565d67d2e78375b2099a66945ddd7f17a16e248c9f321bcbe58b6e476da3。[AOSP vendor boot 文档](https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions)给出 v4 fragment 与 generic ramdisk/bootconfig 组合契约；它不能替代安装版 ABL 的 fastboot boot 实际行为证据。

## 结论与下一步

静态审查确认：当前包未提供系统卷；当前驱动对整段 initrd 的要求使“往 v4 ramdisk 追加 FAT”不能直接成为已验证方案。恢复后 Android initrd 确实不满足当前整扇区前置条件，但 **R-011 候选包实际 x0/chosen 未捕获**，不能宣称本轮驱动一定走了该失败分支。

下一步优先从已有录像提取 SHENGMEM 行（no initrd / not a whole number of sectors / initrd block device），并继续固定安装 ABL 的 v4 拼接路径。再选择有明确边界、可静态验收的系统卷运输方式；真实 Darwin22 预链接负载和目标 Apple ADT 单独验收。没有实际范围前不猜偏移、不填 Apple ADT、不改 board/feed/bringup-plan 或 *_verified。

本审查未新增镜像或设备启动。任何后续临时启动仍需事前通知可拍摄日志、核对恢复输入和设备身份；缺日志或恢复路径时按 AGENTS§3 写 NEED-REVIEW 并停。
