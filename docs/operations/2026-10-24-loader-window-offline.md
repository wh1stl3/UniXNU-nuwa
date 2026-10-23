# OS入口续接：分配选择主机验证与运输缺口

## 已完成的具体工作

check-loader-window-host.py从UniXNU75bc13dd固定git对象读取RunEnd/AllocateWindow，内存应用本仓0005后验证两个函数文本仍相同，源码不落盘。真实分析内核5a128fb2重算SHA，读取其最小非零段VA0xfffffff003dc8000；2MiB同余偏移0x1c8000。以照片最大合并区0x8c0000000/0x240000000构造主机描述符子集，加明确标注的合成边界案例。它不是照片128项原始完整内存图。

WSL clang ASan/UBSan（nonPIE）执行原分配选择函数12项通过：512MiB/1/2/4/8GiB选择、9GiB整区无法容纳同余偏移、低区不足选高区、乱序相邻/扩展stride、分配拒绝、保留区/缺口不跨越、GetMap错误。以上大小只为主机案例，不写入board/ADT。实际计算候选为0x8c01c8000，高位没有截断；这只是测试结果，不是目标地址分配或配置决定。真实AllocatePages由记录适配器替代，不能称EFI/实机窗口通过。

报告reports/loader-window-host/results.json含固定函数SHA、完整编译执行命令和结果；首次编译缺主机UINT8适配声明的失败留out/loader-window-host/failed.json，修正适配器后新目录v2通过，未修改目标分配算法。

## 明确判断

**当前最直接的OS启动阻塞是尚无完整且可读取的合格负载，不能继续归因于HOB。** 本轮菜单配置本来就exit。现有4MiB配置FAT容量小于58,335,232B分析预链接文件；原样profile无法容纳它。分析候选仍loadable=false、early_security_initializers为空、组件/结构ABI未验；真实ADT和root provider链仍缺。将它直接塞入镜像既不能证明运输，也无法回答内核入口问题。

**高地址分配选择目前不是首要嫌疑。** 固定函数在照片范围子集上能选出完整64位候选，但真实UEFI页分配/映射/内核入口尚未执行；9GiB可见范围不保证同样大小请求，更不授权owned_memory_size。RunEnd还会合并相邻Conventional描述符而不比较Attribute；当前照片17项已合并范围无法重建全部原始属性。应在未来实际分配诊断中核对，当前不擅改算法。

UEFI2.10A规范[AllocatePages/GetMemoryMap](https://uefi.org/specs/UEFI/2.10_A/07_Services_Boot_Services.html#efi-boot-services-allocatepages)说明成功分配才获得所请求页；属性位描述能力、不一定当前设置。故本轮照片write-back最大范围不能独自证明实际缓存属性和内核所有权。报告continuation.json记录该区分。

## 接下来如何落实

优先设计独立大文件读取/长度/SHA诊断，保持菜单退出动作，不执行XNU，不需要假ADT。运输可选USB FAT、扩大独立FV资源或已审查UFS卷；不能假定UFP连PC就可见USB盘。USB需独立host/OTG证据；扩大FV需重新核验3MiB FD压缩预算与DXE峰值，不能从4MiB成功外推64MiB。UFS尚无经审查写入目标，本轮不写分区。

并行意义上的工作顺序（不指派额外代理）：离线逐项核对ArmCpu/ArmDTPlatform所需ADT属性与真实nuwa DT，保留未知项；独立审查prelink初始化及root provider ABI。先文件运输，再真实ADT/实际AllocatePages诊断，再合格内核入口。新增构建不需要先问镜像许可，但实际启动仍先通知用户确认本轮录像/恢复；修改内存配置另审。

本轮仅新增主机验证和离线合同审计，没有手机命令/模式切换、镜像或board/bringup/_verified修改；Heap和坏条目保护保持。Android最近证据仍26ef8efd postcondition北京时间02:55:45，不能冒充新查询。
