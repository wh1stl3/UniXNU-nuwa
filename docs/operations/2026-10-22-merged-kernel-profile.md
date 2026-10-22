# 合并版8796源内核构建入口

## 输入与补丁保留

新增config/kernel-merged-profile.json固定wh1stl3/UniXNU@76dd641及四个所需模块：ArmCpu、ArmDTPlatform、ArmVirtPlatform、NativePrelink。旧baseline默认配置和原fork工作流保留，新增设备仓kernel-merged-source.yml独立工作流；使用--profile merged才启用新输入。

scripts/audit-merged-kernel-inputs.py通过完整Git树和blob对象核对原48项选择：46份上游patch未变，2份有变化；按原字节和顺序，48项在只读8796源树上的RAM应用全部通过。仅此核心48项序列重验，不把它写成60项全序列重新执行；11份CI兼容和1份donor桥接保持原哈希，由构建输入检查覆盖。

两项变化：

- offline-owner-systemos-mount.patch：设备已有8796专用候选，继续优先使用，保持CI15字节。
- zzy-native-gpu-addon-mount.patch：将原已验证patch以原字节保存在设备候选目录，SHA bf53de7363413b00c06fa71071bb9bb4f8daddec2ecf7b33435bb0d99adf6ebb，避免随上游更新替换其语义。

最新两份原始上游patch分别对8796执行独立git apply --check均失败，具体kern_exec上下文见reports/upstream-merge/kernel-input-review.json。zzy在本仓严格虚拟解析器还触发裸空行限制；不能把解析器限制叫作上游补丁损坏，Git的独立结果只证明其对当前8796源树上下文不适用。未盲目导入新GPU/挂载功能。

## 构建脚本审查

新build-xnu-4k-baseline.sh SHA d4e4e63291cd044c22ec11e61ec1bb246ecea77e2261f88c19aabc4137e59fbe，原build-firehose.sh字节不变。审查实际diff：新增ERR命令定位、bootstrap开关、额外可选晚期patch逆序处理、owner cache UUID参数、crypto bootstrap判断和archive stamp缺失处理。当前源码配置未开启新bootstrap/owner/crypto路径，运行特性开关沿原入口保持。

现有5组精确替换/命令捕获上下文计数全部匹配。真实inputs函数在RAM读取新脚本及经Git blob证明未变的来源文件，完成48+11+1=60项输入哈希检查与两份适配Bash语法检查。检查不会将新来源全树复制到本仓，也不修改只读源树。

feeds.toml相对75bc在上游已有变化；本仓没有修改它，也没有采用它自动切换XNU版本。隔离源码构建不复制feed，仍使用原显式8796环境输入。这里保留原行为，不声称上游feed字节等于75bc。新libpthread/corecrypto脚本和xnu_symbols.py有变更，其对应运行功能未在此配置启用；完整相关ABI仍待后续审查。

## 验证与执行边界

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-merged-kernel-inputs.py
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/ci/build-8796-source.py --base D:/Code/PortingiOS/common/sources/UniXNU --check
```

前者真实合并版适配函数与Bash语法通过，后者旧基线回归输入检查通过。完整编译必须在macOS Actions，以记录的Xcode16.4/iphoneos工具执行；合并版平台驱动的真实编译/链接结果待CI，不能继承CI15通过。

工作流只取四个固定模块，脚本再次核对主仓/模块HEAD。它生成源内核和三平台静态库并重链接其中两库，收集日志/实际make参数/对象和符号证据，不执行NativePrelink emit、不生成EFI/FD或Android boot镜像、不访问设备、不改board/feed或_verified。Darwin22加载器patch属于另一路固件候选，不被此次内核CI编译。

下一步推送设备提交后以完整device_ref触发新工作流，先确认输入门，再按实际第一处编译/链接错误推进。原baseline工作流继续可用，禁止将此profile静态通过写成合并版编译成功。

## CI调度记录

设备输入3a210b1a4a9ed4633e14b567fea32c590162baf3已推送并触发[39793231214](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39793231214)。本轮查询仍queued，steps为空；证据reports/kernel-ci/39793231214/dispatch.json。未取得编译日志或产物，不提前判断成功/失败，不重复触发同任务。
