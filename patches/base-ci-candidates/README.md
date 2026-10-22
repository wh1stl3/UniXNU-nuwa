# 官方macOS工作流候选

`official-macos-observability.patch` **仅供审阅，未安装、未运行**。它修改基座fork中的`.github/workflows/macos.yml`，不属于设备仓的`patches/xnu`模块，不能让模块解析器把它当作XNU补丁应用。

唯一适用输入：UniXNU提交`e95b37d97875bd8b30c976fcdef44d35d9c27bf3`，原workflow SHA-256为`ba9a1b60371aa93e1a2a6a8524bab0db876d67081a32540a210063b223c5ad81`。本地75bc基线没有该workflow，不能直接套用。

改动：默认steps为kernel；固定macos-15-intel和Xcode16.4；缺少该Xcode路径或IIG时失败；记录实际ImageVersion、SDK与Apple clang；构建失败时也尝试上传已有日志、编译记录及原始内核产物。未添加诊断镜像生成步骤。官方现有额外steps选项仍在，未来首轮只允许选择kernel。

生成及检查（只读API证据+进程内文本，不调用Git）：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/prepare-official-ci-candidate.py
```

检查结果见`reports/official-ci-plan/candidate-check.json`。只证明5个hunk的精确上下文和结果文本一致；YAML/Actions实际执行、当前runner上的Xcode/IIG、8796编译、链接及设备运行均未验证。该补丁不改变官方仍为10063/iOS17的源构建配置，也不补齐nuwa defconfig、archive或donor输入，不能单靠它启动iOS16构建。具体门槛见[报告](../../docs/operations/2026-10-22-official-ci-route.md)。
