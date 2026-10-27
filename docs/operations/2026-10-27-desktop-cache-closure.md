# 完整根准备：缓存引用与四个入口的静态库路径闭包

本轮按DEVELOPMENT-STAGES的S05/S06推进，继承平台独立验收、ResourceFork读取/exec/EL0及239门的未完成状态。仅离线：在线查格式原始资料，三个组件只读挂载；不用实机，不运行镜像程序，不提交、不改现有镜像或板值。

## 完成结果

新增`desktop_cache.py`、`desktop_namespace.py`、`audit-desktop-cache.py`、`test-desktop-cache.py`。最终证据为`reports/desktop-readiness/2026-10-27-cache-r1/{audit-r3,tests-r3,qualification}.json`，此前r1/r2结果保留，不覆盖。

| 项目 | 本轮结果与范围 |
| --- | --- |
| 原始输入 | OS/SystemOS/AppOS分别新算SHA256、SHA384，匹配既有固定组件；只读前后摘要一致，三个挂载均退出 |
| 主/子缓存文件集合 | 主缓存声明42个子缓存；逐个核对文件后缀、UUID、首映射与VM offset，另核对symbols UUID；共44个文件 |
| 缓存映射/索引 | 映射文件范围、VM重叠及被引用地址检查；2710个镜像路径索引，未把主/子文件当成彼此独立的缓存 |
| 四个入口 | 磁盘上的launchd、dyld、SpringBoard、backboardd与已固定库存摘要一致；显式入口优先读取实际磁盘文件，避免被同名缓存项替代 |
| 递归静态库路径 | 1103个节点、17649条依赖边；0条缺失必需依赖，0条未解析上下文token；6条缺失弱依赖边涉及4个路径 |
| 回归 | 14项测试通过：子缓存成功路径、错误UUID/后缀/表界限/映射/地址/缺文件、截断命令、lazy依赖、同名入口、虚拟跨层链接/越根/循环/非目录 |

缺失弱依赖路径是`/usr/appleinternal/lib/liblinkguard.dylib`、`/usr/local/lib/libobjc-env.dylib`、`/System/Library/PrivateFrameworks/MLCompilerRuntime.framework/MLCompilerRuntime`和`/System/Library/PrivateFrameworks/Darwinup.framework/Darwinup`。同一弱依赖可由多个消费者引用，不能把6条边当成6个文件。保持原弱依赖语义，没有造空库或修改Mach-O。

这是**主/子文件引用及四个入口的静态库路径闭包**，不是全部2710个库的递归闭包，也不是符号绑定、导出/reexport语义、fixup/rebase、dlopen、CodeDirectory/CMS/AMFI或实际dyld运行资格。没有把完整OS中的文件存在提升为桌面通过。

## 组合命名空间方案

解析器在图像自己的逻辑根内解析绝对/相对链接，记录最终组件、路径、权限、uid/gid与链接链；拒绝越根、循环及穿越普通文件。使用明确声明的虚拟绑定：

| 逻辑位置 | 来源 |
| --- | --- |
| `/` | 完整OS组件 |
| `/System/Cryptexes/OS` | SystemOS组件根 |
| `/System/Cryptexes/App` | AppOS组件根 |
| `/System/Library/Caches/com.apple.dyld` | SystemOS中的同名缓存目录 |

最后一项是**拟定的缓存目录绑定**：本次检查完整OS在此位置没有现有项，不会在本模型中遮盖已有目录。它还没有实现成内核挂载、root overlay或组装镜像。该模型只检查所选路径/依赖，不宣称穷尽完整根内所有冲突、链接和元数据。实际组装仍须确定挂载/复制策略、全部链接与元数据保留，不能将模型路径直接写成设备已挂载事实。

## 对当前卡点的影响

完整OS的这些启动/桌面入口具备可解析的必需静态库路径；不能再仅凭独立framework文件缺失就认定缺库。现用PROBE41仍是RestoreRamDisk根；本次没有将完整OS替换进去，故不是原生ResourceFork读取问题的修复，也没有推进实机EL0前沿。

下一依赖是完整根组装契约、可写Data布局/所有权、532项主launch配置的实际服务范围及IPC/设备需求审阅；然后核验iOS16显示/输入接口。当前不批量放行恢复服务、不解除239门、不改变认证路径。底层timer/IPI/DMA及UFS资格仍分别保留，静态库路径闭包不替它们验收。

## 执行与复验

工作根`D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；WSL Ubuntu-22.04 Python3，项目脚本严格串行。以下为已执行的最终命令，输出已存在，仅供追溯；续验另选新输出/挂载目录：

```powershell
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-desktop-cache.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-cache-r1/tests-r3.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-desktop-cache.py --work /var/tmp/nuwa-desktop-cache-20261027-r3 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-cache-r1/audit-r3.json
```

首次12项测试与audit通过后，发现应保留LC_LAZY_LOAD_DYLIB依赖，补第13项并用新路径复验。随后审查发现入口dyld被同名cache项优先匹配；改为显式入口读取磁盘，补第14项负对照，再用新路径复验。早期结果不冒充最终源码通过，最终资格只绑定r3。完整源镜像每轮均只读检查前后摘要；没有改写旧报告。

APFS工具固定SHA256 `4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922`。父组件库存`reports/desktop-readiness/2026-10-27-system-r1/audit.json`，原始身份仍为d22ap/iPhone10,3/iOS16.7.16/20H392。PROBE41不重编，仍以原包资格为准，本轮资格另绑定当前包摘要。

## 公开原始依据

[UniXNU平台/root/Data指南](https://unixnu.com/porting/platform)用于依赖与验收边界。格式参照Apple dyld固定tag `dyld-1066.8`的[缓存格式](https://github.com/apple-oss-distributions/dyld/blob/dyld-1066.8/cache-builder/dyld_cache_format.h)和[原始缓存访问实现](https://github.com/apple-oss-distributions/dyld/blob/dyld-1066.8/common/DyldSharedCache.cpp)，APSL-2.0；2026-10-27在线查阅。没有复制上游实现；参照版本不代表已确定20H392中dyld自身的精确构建版。实际格式字段、UUID、映射、路径和命令来自上述本机只读输入。最初尝试的include/mach-o头路径返回404，正确文件位于cache-builder，没有通过放宽检查处理该路径错误。
