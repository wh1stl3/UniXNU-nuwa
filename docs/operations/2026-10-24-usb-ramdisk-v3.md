# USB数据线负载运输：v3单变量诊断候选

用户本轮明确选择USB数据线路径；无需OTG/U盘。2026-10-24离线准备完成，未操作手机。

准备期间用户补充“现在有OTG线了，你可以自行判断哪个路线更稳健更快”。判断仍先试已就绪USB v3：保持既有物理连接和固件，候选与对照仅两字节差异；OTG方案另需host角色、供电和介质枚举验证，尚未确认U盘本身可用。线已具备作为备选，不安排自动写介质或自动切换第二次启动。

## 首要判断与反证

当前运输失败首因倾向于**v4 ABL选择已安装init_boot，而不是临时boot镜像附带的generic ramdisk**，置信较高，尚未取得分支运行时跟踪。依据：a22e9a44实测chosen长度33870292B与历史Android一致，临时镜像声明67108928B探针却不在扫描结果中；固定安装ABL38a837fa/LinuxLoader b489faff的0x7660–0x769c在context+0x45c非零且版本>=4时选择名为init_boot的镜像。

本轮补充直接版本来源：0x7608–0x762c从头指针+0x28按little endian组成u32，写入context+0x458；另两处32位非栈写入窗口也含+0x28读取。并非仅根据字段数值命名，仍不把局部窗口当作所有间接数据流/实际现场已证明。原始指令与SHA见abl-version-source-final.json。

隔离夹具原样保留0x7660–0x7684的36字节，只把进入init_boot查找和旁路目标替换为返回值。在AArch64用户态QEMU中执行16组版本/条件值，包括unsigned高位边界：v3对建模的两种条件均旁路，v4在条件非零时进入查找。**这是QEMU执行通过的局部分支夹具，不是完整ABL或实机通过**。上下文实际值、后续vendor/generic拼接和v3容器接受仍待实测。

备选排序：版本上下文来自其他已选镜像或被后续路径替换；v3与现有vendor_boot组合被固件拒绝；成功交接后范围/封装校验失败。若chosen仍为旧长度且封装absent，优先继续追版本与镜像选择，不能假称v3已生效；若ABL直接拒绝，应回到解析兼容路径，不改分区。HOB/Heap保护和缓存维护保持，不能用换Heap解释运输变化。

## 已构建的实际输入

使用已有成功CI40014018074/source5abdde1的upstream-merged固件，不修改或重新编译相同FD：

- FD 2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f，3145728B；完整SEC与已实测26ef8efd相同，保护保留。
- shim 8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，112B；复制目标/长度不改。
- FAT bc0b3eae88e0dd8a528b3469d0fa9c3fa21c99097af842cab42c28cfa5068ff2，67108864B；与此前v4运输试验完全相同，仅退出配置，无XNU/Apple ADT。
- ramdisk为既有64B有界NUWA封装+上述FAT，67108928B，SHA64846f6698217ce0daa6ee3bfe91cb7898ce564f6b312f4c3b302edb6e57840f，CRC32 574100a3。
- v3候选SHA **8177783e1364caed71e0db82f4c91db720f9586f8bc0d05ca044e133be4ad898**；v4离线对照SHA91e86ce45b1d880c48f6ddb5a7b8876f2f64b69ef592f3ab692bcca0b821b3f6。两者均70266880B，产物out/trial-boot/usb-ramdisk-40014018074/。

相对于彼此，全部镜像仅offset20的header_size（1580/1584）和offset40的version（3/4）两个字节不同，4096B之后逐字节相同。相对于原厂boot头，只改kernel_size/ramdisk_size及上述两字段，原cmdline/os_version/保留域不改，v4签名原为0；4096页对齐，ramdisk文件偏移3153920。v3/v4不声明新的物理base/offset，不修改board或bringup-plan，也不照搬sheng v0地址。v3只是待验证临时容器，不将它设为设备正式boot配置。

旧fastboot证据max-download-size=805306368B，大于候选70266880B；这是2026-10-22历史查询，不当作当前新查询。内存放置由ABL决定，固件仍只接受既有Kernel保留范围中的真实chosen；没有据此扩大映射或宣称具体装载地址。

## 验收与门控

scripts/usb_ramdisk_package.py复核固定recipe/CI输入、完整固件检查、FD/shim/FAT及原恢复boot哈希；按原头重建每一字节，再独立读回头/长度/边界/内容/零padding。package-v3.json是唯一新增可试scope USB-RAMDISK-V3-OFFLINE；package-v4.json仅离线对照，不纳入启动scope。

新增7项测试通过：规范容器对照、9类字节损坏和截断/追加拒绝、旧版/带签名输入拒绝、空录像拒绝、v4对照不能启动、v3缺新鲜preflight不能启动、缺录像确认在ADB枚举前拒绝。受影响的历史门控10项回归通过，legacy-gates.json保存实际输出。另有16项真实分支字节QEMU夹具通过，abl-gate-fixture.json保存命令/代码SHA与范围。

**运输实测成功条件是NUWA-VOLUME envelope result=1，并发布0x4000000B只读块设备Success。** 必须采集chosen范围、封装结果和发布日志；只看到菜单不算成功，因为相同FD还内嵌4MiB配置fallback。即使64MiB封装CRC成功，也仅证明该运输探针，不代表约58MiB分析内核已经文件读取/SHA验收，更不代表XNU/iOS执行。

当前等待本包新鲜录像条件确认；启动前通知，唯一nuwa/kalama及Android完成1/三分区基线刷新后仅一次fastboot boot；原厂v4恢复镜像ef558db2保持。试验结束恢复Android完成1与三分区SHA不变，无flash/erase/改槽位。本轮离线准备没有设备模式变化。完整OS资格（初始化/ABI、ADT、分配窗口）仍独立保留loadable=false。

## 复现与来源

- 新包已存在时：bundled Python -B scripts/usb_ramdisk_package.py --validate reports/usb-ramdisk/40014018074/package-v3.json。build无参数，但要求新输出目录，不覆盖历史。
- 分支夹具：check-usb-abl-gate.py --work out/<新目录> --output reports/<新文件>.json；原始门字节由audit-abl-handoff.py只读解码固定ABL。
- tests：bundled Python -B -m unittest discover -s tests -p test_usb_ramdisk_package.py -v；历史test_*gate.py。
- [AOSP固定bootimg.h，Apache-2.0](https://android.googlesource.com/platform/system/tools/mkbootimg/+/808d42e197506319ee65eb078d3defd9602e2ac2/include/bootimg/bootimg.h)：v3/v4结构及4096对齐；[generic boot官方说明](https://source.android.com/docs/core/architecture/partitions/generic-boot)：Android13 init_boot分离。规范不替代nuwa安装ABL行为证据。
- [UniXNU固定上游负载说明](https://github.com/UniXNU/UniXNU/blob/1a01c2afa197d975d04da892325c56b6b14aaecb/docs/zh/concepts/payload.md)及[sheng固定打包器](https://github.com/UniXNU/UniXNU-sheng/blob/a599a1a8a92093b5077543e071b72130769eb325/scripts/package-sheng-xnu-boot.py)：USB内存ramdisk是已有路线，OTG非依赖；不抄其v0/板值，未复制源码树。

2026-10-24实测更新：8177783e单次试验取得独立封装result=1/64MiB块Success及内嵌驱动之前的FAT挂载原图，运输探针阶段实机通过；offset-64精确等于原vendor ramdisk长度，支持拼接解释。Android已于北京时间15:41:49完成恢复/三分区SHA一致，无第二轮。详见[本轮实测记录](2026-10-24-usb-v3-trial.md)。
