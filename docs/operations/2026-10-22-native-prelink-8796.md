# NativePrelink 两项对8796的独立检查

2026-10-22；基座 `75bc13dd34dc4e403826793739e316a264ce00dd`，XNU `1b191cb58250d0705d8a51287127505aa4bc0789`（8796.141.3）。

命令（仓库根，PowerShell）：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -I -B scripts/check-native-prelink-8796.py
```

脚本只调用只读Git命令，日志与JSON写本仓 `reports/native-prelink-8796/`。源树检查前后status返回0且为空，基座tracked status为空，精确命令、补丁SHA-256、时间及结果见 [results.json](../../reports/native-prelink-8796/results.json)。

| 补丁 | 独立检查结果 | 原始日志 |
| --- | --- | --- |
| xnu-10063.141.1-security-init.patch | 静态检查通过；第二hunk落在8289（offset -162） | [security-init](../../reports/native-prelink-8796/xnu-10063.141.1-security-init.patch.log) |
| xnu-10063.141.1-sparse-index.patch | 静态检查通过；五个hunk均offset -1 | [sparse-index](../../reports/native-prelink-8796/xnu-10063.141.1-sparse-index.patch.log) |

名字含10063并不意味着8796文本不能匹配；此次未改补丁。两项不计入原49项，原统计保持38通过/11失败。合起来仅可表述为51项独立检查中40通过/11失败，不是整套补丁应用通过。

## 语义审查边界

security-init把调用插到 `libkern/c++/OSKext.cpp` 的OSRuntimeInitializeCPP及startfunc成功之后：8796原树对应8284-8286行；`security/mac_base.c:151,377` 存在mac_late定义与置位。补丁仍要求AppleSecurityExtension、prelinked身份、MAC阶段和只读可执行范围检查，不能用未知地址填board。donor实际initializer、符号绑定、执行时序未验证。

sparse-index修改 `osfmk/kern/kalloc.c:1028-1034` 的prelink扫描；8796确实有原contiguous遍历。新增索引格式与NativePrelink产物的配合、所有load-command边界和实际allocator运行均未验证。仅凭apply不能宣布Darwin22接口兼容。

同一次脚本用Python标准库tomllib解析获批 `board.toml` 成功，解析数据和哈希存入results.json。**这是TOML语法静态检查通过；不是完整board配置验收**。该文件仍为example=true，未知字段缺失。

完整依赖顺序、累积应用、编译/链接、QEMU、实机均未验证。feed未改变，无Git写操作、镜像生成或设备操作。下一步处理49项中的版本上下文差异；先保留来源哈希与适配理由，不把缺失的8796 API硬改成17.x实现。
