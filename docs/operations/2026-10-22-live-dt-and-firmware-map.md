# 当前Android设备树与固件映射复核

## 采集与边界

2026-10-22，ADB同时连接enuma与nuwa。按ro.product.device筛选唯一nuwa，再核对实际FDT的model含nuwa、compatible含kalama；未对enuma执行重启、镜像或root操作。只读读取/sys/firmware/fdt，结束nuwa sys.boot_completed=1。序列号不保留；完整二进制仅out/live-nuwa-dt/。设备树938828B，SHA256 f4636276599dd5b8c483692745994d1a8285542c30943e901f2717e23378f8a8。该哈希覆盖动态Android FDT，不要求不同启动后保持相同。

复核命令：

```powershell
python -X utf8 -B scripts/collect-nuwa-live-dt.py --output reports/firmware-ci/39802617878/live-dt-map-comparison.json
```

脚本要求fresh报告路径。证据包含选择的原始属性hex、各级address/size cells、固定固件源码hash、32项静态区间交集和启动状态，不写入板配置或_verified。采集到的是Android当前FDT，不能证明新候选ABL传入x0或UEFI运行映射相同。

## 对下一入口实验的影响

| 实际Android属性 | 当前固件源码 | 结论 |
| --- | --- | --- |
| splash_region: [0xb8000000,0xbab00000)，45MiB | Display Reserved同区间 | 当前Android保留区吻合；面板时序/电源/候选handoff后的显示可见性仍未验证 |
| initrd: [0xb5fb2000,0xb7fff1d4) | Kernel Reserved: [0xa8000000,0xb8000000) | 当前initrd位于该源码保留区内；新容器的实际地址、生命周期、可读映射与所有权仍须确认 |
| ramoops@0xa7000000: [0xa7000000,0xa7400000) | FD Reserved首1MiB + UEFI FD后3MiB | 现布局不能把整个Android ramoops区域直接用于固件留存日志：固件拷贝本身覆盖后3MiB。不能据此定位黑屏，也不能据此声称这些区域同时冲突 |

UEFI源码已有Log Buffer [0xa7605000,0xa760d000)，但Android保留区名字与固件自用名字不是持久性/安全性证明；没有选择新日志地址，没有启用logger/写RAM，更没有生成诊断镜像。早期日志方案仍须明确首次可写阶段、cache策略、固件各阶段保护、重启到Android前后覆盖和读取路径。不要把Fastboot读RAM或Android pstore自动识别视作已有能力。

## 构建阻塞

独立固件CI39802617878在Install build tools持续约11分钟，未进入编译；旧成功CI39764322744该步骤39秒。请求取消以读取真实安装日志，随后依据具体阻塞设定有限重试和超时；取消本身不是固件编译失败证据。

取消后取得真实日志：Install build tools在下载azure.archive.ubuntu.com的cross-GCC依赖，多次Get后数分钟Ign；cpp-13-aarch64与libgcc-13-dev-arm64已出现，取消时仍在gcc-13-aarch64的21.1MB包。未出现源编译器错误。记录install-diagnostics.txt、console-metadata.json及result.json；产物上传报No files是构建未开始后的次生错误，不是独立固件失败。

最小修复：仅runner的ubuntu.sources中把Azure Ubuntu镜像改为archive.ubuntu.com HTTPS，保留Ubuntu签名/发行版/包列表；apt update 180s、install 360s，连接30s/重试2次/锁60s，步骤10min，显式非交互模式。没有改项目feed或固件输入。Bash语法检查通过，是否改善网络要由新CI实测，不能把有限超时写成网络已修复。
