# 上游主分支合并与CI15实际boot_args类型

## 授权与范围

用户要求合并UniXNU主分支并保留本仓补丁；随后明确允许继续实机操作，撤销20:26暂停。本里程碑只进行GitHub合并与离线调试类型读取，未执行设备命令、未生成镜像、未改变board/feed或_verified。

## 合并结果

- 上游固定输入：UniXNU/UniXNU@5fdbd5d08518bc2d5c196264c56a377dd80cf5ca。
- fork合并前：wh1stl3/UniXNU@02daabcbcf1387fc67c15efeaef8085614dd97f2。
- 共同祖先：e95b37d97875bd8b30c976fcdef44d35d9c27bf3；fork独有5提交，上游独有26提交。
- 合并提交：[76dd64142decca55f6594b860565e848de71d271](https://github.com/wh1stl3/UniXNU/commit/76dd64142decca55f6594b860565e848de71d271)，两个父提交依次为上述fork旧头与上游输入，未改写历史。
- 完整递归树未截断，589个非目录条目逐项等于上游树加原3份nuwa工作流；并非只依赖GitHub compare的有限文件列表。
- 原3份nuwa工作流blob未变化，设备仓28份patch文件SHA256均未变化。fork合并前后feeds.toml blob相同，设备仓feed也未修改。
- 21个子模块固定提交已记录于reports/upstream-merge/verification.json，不将目录迁移当作驱动删除。

执行脚本：scripts/merge-unixnu-upstream.py。命令：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/merge-unixnu-upstream.py
```

该脚本有固定旧头门，已执行后再次调用会因旧头不符退出；不要为重跑放宽门。GitHub merges端点完成一次非强制合并，报告包含树核对和全部设备patch哈希。

## 构建基线与仓库主分支的区别

fork主分支已经合并最新代码；成功内核/固件的历史构建输入仍为75bc13d，config/firmware-ci-inputs.json、loader-candidate.json和源内核脚本没有被无证据改写。原nuwa工作流按设计仍检出该固定提交。此次没有运行新CI，因此不能把旧CI成功写成合并版本构建成功。

下一次升级构建输入需要分别适配子模块获取、48项补丁的旧哈希门、脚本哈希及精确替换上下文；不能只换一个SHA。设备patch原样保留不代表对新输入全部可应用，仍待逐项检查。无需重新询问Git/工作流授权；若进入新的固件/诊断镜像生成范围，按AGENTS第3节与已有具体批准范围判断。

## CI15实际类型证据

脚本scripts/audit-ci15-boot-args-dwarf.py解析Mach-O LC_SEGMENT_64/LC_UUID，将调试节交给pyelftools 0.33（安装在忽略的out/python-tools）。依赖安装及执行：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -m pip install --target out/python-tools pyelftools==0.33
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-ci15-boot-args-dwarf.py
```

输出reports/official-site-audit/ci15-boot-args-dwarf.json：

- 内核SHA256 a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a。
- dSYM SHA256 69261970eef72dfed142a1656589fd275fcf5bd4748c74e0920abdc2e47be7f6。
- 两者LC_UUID字节相同：b8e91919bff83edfb00271bfdd3348f4。
- osfmk/arm/arm_init.c、osfmk/arm64/machine_routines.c、pexpert/arm/pe_init.c中完整DW_TAG_structure_type定义一致：sizeof=736/0x2e0，CommandLine偏移0x6c、DW_AT_count=608，bootFlags偏移0x2d0，memSizeActual偏移0x2d8。

这将此前“原始头文件差异”推进为“成功产物的实际编译类型差异”。当前DarwinBoot结构为0x480、CommandLine1024、MemorySizeActual偏移0x478，与该内核不兼容；仍不构成运行验收，也不能解释不含XNU的v4黑屏。

下一项：形成Darwin22专用最小加载器patch，同时调整结构、局部命令行缓冲区及长度校验；仅缩短结构会使现有CopyMem的1024字节写入越界。以新子模块提交为输入检查，再逐项迁移构建适配；内存窗口/板值保持既定决策。
