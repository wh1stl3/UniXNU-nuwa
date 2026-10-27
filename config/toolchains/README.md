# WSL 8796工具链输入

这里是本仓自有的**主机工具链清单**，不是board.toml schema、设备配置或feed覆盖。

`wsl-8796.example.json`保留已知本机工具路径及文件SHA-256；clang14虽然文件身份已固定，仍未通过XNU特征门。未知IIG/sysroot/SDK版本为null，即TODO，不是假路径。

在WSL运行：

```sh
/mnt/d/Code/PortingiOSLegacy/.venv-wsl/bin/python -B scripts/wsl_kernel_adapter.py plan
```

输出写本仓reports/wsl-firststage，缺输入退出2。`adapter-plan.json`明确executable=false；没有make执行子命令，没有fetch、Git apply、源树装配或镜像生成动作。

输入供应后应新建明确命名的主机profile，记录来源/版本/哈希，再用 `--config PATH` 检查。不要通过空stub、宏替换类型内建、伪造IR或关闭allocator检查满足门槛。当前profile不是可构建宣告。

每份sysroot清单采用自有JSON格式 `{"files":{"relative/path":"sha256"}}`，路径不得逃逸或经符号链接逃逸对应root。空清单拒绝。清单哈希匹配仅验证列出文件完整性，不能证明SDK完整或目标ABI兼容。host的null指未登记完整输入清单；已有Linux宿主头文件样例检查成功，不意味着宿主头文件在物理上缺失。

MIG smoke仅运行已固定身份的migcom，生成独立样例C/头文件到out/；没有编译生成的目标代码，也不能替代IIG或完整MIG前端/8796接口验收。
