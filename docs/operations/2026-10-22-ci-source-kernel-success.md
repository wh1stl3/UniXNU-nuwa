# 8796源内核构建成功取证

2026-10-22，第十轮CI39738601892首次完成完整源内核配方，生成真实Mach-O文件。结论仅为云端编译/链接成功及下载后静态检查通过；尚未预链接、QEMU或实机验证。

## 固定输入与实际结果

- 运行：https://github.com/wh1stl3/UniXNU/actions/runs/39738601892 。完整编译/链接步骤07:10:17–07:19:45 UTC，作业07:20:15 UTC完成，conclusion=success；原始状态见reports/kernel-ci/39738601892/run.json。
- device_ref=526651af94610f40c3223eae9550deaa3c44ae57；基座75bc13dd34dc4e403826793739e316a264ce00dd、Apple XNU1b191cb58250d0705d8a51287127505aa4bc0789（8796.141.3），48项选择加10项CI兼容补丁，逐项哈希见build.json。
- 实际主机macOS15.7.9/x86_64、Xcode16.4、Apple clang17.0.0、iphoneos18.5 SDK，见toolchain.log。WSL本机仍未具备同等输入，本结果不构成本机编译可行的证据。
- build.json记录kernel_built=true、prelinked=false、device_verified=false。没有忽略make退出码、undefined-symbol或导出检查；第九轮唯一display引用修复已由本轮完整链接覆盖。

取证命令：

```powershell
gh run view 39738601892 --repo wh1stl3/UniXNU --json status,conclusion,jobs,headSha,url,createdAt,updatedAt
gh run download 39738601892 --repo wh1stl3/UniXNU --dir out/kernel-ci/39738601892
python -X utf8 -B scripts/ci/summarize-build-evidence.py 39738601892
python -X utf8 -B scripts/ci/inspect-source-kernel.py out/kernel-ci/39738601892/nuwa-8796-source-39738601892/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped --output reports/kernel-ci/39738601892/kernel-inspection.json
```

上述检查只读取已存在内核，不生成或修改内核/固件镜像。使用固定基座NativePrelink解析器，parser SHA-256为5bd80b8c63deec29b747c28253e02308a56d5f8cdb37c9d315e7c8af7012d017。

## 下载产物

相对路径为out/kernel-ci/39738601892/nuwa-8796-source-39738601892/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped。

- 20,136,488字节，SHA-256 bdaad81373d00df8334cb5a453b32f06a5e607c3e7d8cde812e4f5f927e19ced，与runner的kernel_sha256和linked_kernel_sha256一致；见acceptance.json。
- 普通小端ARM64/subtype0/MH_EXECUTE；实际_version字符串为Darwin Kernel Version 22.6.0，LC_SOURCE_VERSION五字段为8796/141/3/0/0；LC_DYSYMTAB未解析符号数0，导出名称21732。
- LC_BUILD_VERSION platform=2、minimum_os=16.0.0、sdk_metadata=16.0.0。这是链接命令写入的metadata，不是实际SDK版本；实际SDK为18.5。
- _kalloc_sparse_prelink_index_version与_native_prelink_security_init_version均存在唯一导出、可映射到文件，读取的32位值均为1；详见kernel-inspection.json。
- 全部build目录870个.o、目标841个.o，不含.cpo。51个IIG生成实现无kernelContent残留，原IORPC头不变；数量和文本检查不等于RPC运行时ABI验证。

原始控制台81,760,874字节、852090行，SHA-256 5058243f0c200dbd32dd39d0c3e5d41fd2211c1bb51e8909ab60646168c36f14；大日志和二进制仅保留忽略的out。build-analysis.json保存哈希/计数，completion-evidence.txt保留带原始行号的链接及Mach-O输出。云端artifact保留7天，原始过期时间见artifacts.json。

## 仍未验收的边界

该目标是BCM2837源构建配置，关闭KPC/KPERF、boot-progress和可选设备archive，尚未建立完整nuwa配置。两项NativePrelink标记只满足基础格式入口，未执行donor解析/重绑定/预链接，不代表driver、用户态或供体ABI通过。段起点4KiB对齐也不是运行时页大小的独立证明。

今晚无需启动这份源内核做实机验证：driver/static archive、13项boot-progress回调、watchdog/scratch、ADT/uefi及donor闭包仍缺。下一步先处理软件侧接口。后续若需新建镜像或fastboot boot，必须按硬停在NEED-REVIEW列出至少两条路径和代价后等待批准；本次没有此类操作。

acceptance.json复核board/feed原始哈希不变、三来源树tracked状态空。未把任何_verified置true，未知板值继续TODO。
