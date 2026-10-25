# v26：Image4 provider路由反例与AMNM兼容候选

## 当前结果

实机仍是PROBE18在MAC/Image4 panic(2)，没有新设备动作。新增离线证据推翻“补mix-n-match-prevention-status即可修复”的充分性：当前原生SecureDTIsLockedDown=false会选择pmap dtless，其chip-instance描述符表没有AMNM。即使对象夹具有合法4字节1，原初始化仍到同一panic(2)。

新增104字节兼容候选仅在dtless已选择且标识符为AMNM时调用原生Darwin IOKit读取器。18项检查、独立重编译一致和错误绕过负候选拒绝通过。候选只在模型内安装，未写入出货内核/ADT/启动包，也未选择出货策略。

提供禁止混配值的隔离夹具安装兼容候选后，真实初始化越过AMNM调用，下一处为`failed to read boot nonce hash: secure boot level = %#llx: %d`，参数0、2。不能称为实机越过MAC或内核完成。

## 固定输入和证据等级

输入内核仍为1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6；出货探针d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e；ADT9846c7dadd23bf544190c45ba3db437fb83265cb180ad6c54cd3a3fedee20d93。包18绑定/回读和原Image4五例复验通过。

脚本核对出货所有donor/prelink段及SecureDTIsLockedDown代码与固定输入一致。执行原始Image4读取器、标识符迭代器、chip-instance创建器、SecureDT和初始化切片；IORegistry对象查找、虚调用、OSData类型转换/长度/字节和日志边界是显式夹具，不是实机provider快照或完整连续内核启动。

报告：reports/kernel-entry-probe/2026-10-25-v26/{image4-runtime-provider,execution}.json。兼容候选SHA256为ad2bb3e06d60ea2fee50de9f642e2feec6ac89e594071af1f8e5b4408006aa39；链接VA只用于隔离模型，不是实机装载地址审批。

## 指令因果

1. 初始化0xfffffff0046e98cc在0xfffffff0046e9948调用GOT绑定的原生SecureDTIsLockedDown；0xfffffff00790568c的真实代码为mov w0,#0与ret，不是夹具返回值。
2. 原选择代码写全局0xfffffff005cacea8为0xfffffff005cad110，即pmap dtless表，其bool回调为0xfffffff0046ea9c8。
3. 执行getter 0xfffffff0046f0f30按当前crypto-hash-method选择SHA-384 AP descriptor，再执行0xfffffff0046ec264创建原始版本6缓存，保留真实缺项mask。后续切片也执行原effective-chip getter。
4. dtless回调先以0xfffffff0046e5600查chip-instance描述符。0xfffffff005cac8c0开始的22项真实表没有enum12 AMNM或enum11 CHMH；查不到AMNM直接ENOENT，不读取属性。
5. 原初始化0xfffffff0046e99c4的间接调用、错误分支和panic格式都执行。出货ADT与加入合法4字节1的对象夹具均panic(2)，这满足交接要求的最小证伪反例。

判断：**路由不能表达AMNM与出货属性缺失是两个独立问题**。前者由真实指令、表清单和合法输入反例支持，置信程度高；真实实机对象状态仍未读回。后者由出货ADT及真实SecureDT/IOKit读取器支持。只改ADT不足以解决完整路线。

## 兼容候选

patches/xnu-8796-candidates/image4-amnm-provider.S的入口约定是原读取器保存现场后的0xfffffff0046ea000。缓存为空回原SecureDT；缓存非空但标识符非12回原缓存；只有AMNM交原Darwin IOKit getter 0xfffffff0046efe7c，再回原尾声。不直接构造布尔值、返回成功或跳过MAC。

IOKit helper 0xfffffff0046f07e8要求OSData，缺属性=2、类型错误=96、超容量=84，失败保留输出。原读取器接受空属性并解释为允许混配；回归保留原行为，不意味着允许空属性出货。

18项检查涵盖6个直接IOKit场景、2个缓存初始化反例、描述符表、6个兼容场景、原生下一BNCH停点、8个其他缓存标识符不变、9个原SecureDT后备标识符不变。检查callee-saved/SP和错误输出哨兵；把BLR改成直接成功的负候选必须被拒绝。

尚未集成诊断内核：单独修路由不能形成有推进价值的实机包。不重写PROBE18，不绕开原donor保护；以后集成需要显式记录该处兼容修改、差分、候选metadata和新包绑定，不能声称新候选donor全部未变。

## 后续输入契约

出货`/chosen/manifest-properties`节点存在，但只有name、没有BNCH；`/chosen/boot-manifest-hash`缺失。真实IOKit读取器还列出CEPO/BORD/CHIP/SDOM/ECID/ESEC/IUOU/RSCH/AMNM/EUOU/FPGT/ESDM/CHMH缺项。既有effective-security-mode-sep不能代替实际要求的effective-security-mode-ap。这些缺项不授权伪造Apple fuse或板级身份。

兼容候选与禁止混配夹具让原生SecureDT查到manifest-properties节点，随后BNCH返回2，按原effective-chip descriptor当前级别0走原panic。级别0只是该模型真实descriptor的输入，不是nuwa实测Apple secure-boot状态。

复核固定集成源码e553e467ebfe7642e9f483d3977a57066c6d1aef的offline-owner-boot-manifest.patch：它计算已验证root/cache集合的SHA-384、发布VerifiedRoot.OwnerBootSet.v1域元数据并拒绝覆盖已有身份。该调用属于后续root/cache路径；它不是前级Apple Image4 manifest，时间上也不能倒填当前MAC前的BNCH/CHMH。此次未将它移植为默认值。

下一步实现并核验早于MAC的真实非Apple平台nonce/manifest/身份输入来源，绑定实际启动集合，并保留Apple认证失败与owner认证的区分；再将兼容改动和输入一起形成新包。没有来源就保留错误，不用0、空值、随机摘要冒充可信链。这里是未完成工程依赖，没有新增全局审批项。

公开机制参照：[Apple xnu-8796.141.3 device_tree.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/pexpert/gen/device_tree.c)和[img4/runtime.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/EXTERNAL_HEADERS/img4/runtime.h)。后者说明AMNM会影响nonce/CHMH约束；本轮具体路由结论以本机固定指令为准。

## 重放和边界

在D:/Code/UniXNU-nuwa串行执行，任一步非零立即停止，不用旧bin冒充新编译：

```powershell
wsl -d Ubuntu-22.04 -- clang --target=aarch64-none-elf -c /mnt/d/Code/UniXNU-nuwa/patches/xnu-8796-candidates/image4-amnm-provider.S -o /mnt/d/Code/UniXNU-nuwa/out/image4-mainline-v26/amnm-provider.o
wsl -d Ubuntu-22.04 -- ld.lld -Ttext=0xfffffff003dc4000 --entry=image4_amnm_provider /mnt/d/Code/UniXNU-nuwa/out/image4-mainline-v26/amnm-provider.o -o /mnt/d/Code/UniXNU-nuwa/out/image4-mainline-v26/amnm-provider.elf
wsl -d Ubuntu-22.04 -- llvm-objcopy -O binary --only-section=.text /mnt/d/Code/UniXNU-nuwa/out/image4-mainline-v26/amnm-provider.elf /mnt/d/Code/UniXNU-nuwa/out/image4-mainline-v26/amnm-provider.bin
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/audit-image4-runtime-provider.py --adt out/trial-boot/xnu-entry-probe-18-vectors/kernel.macho.adt --adapter out/image4-mainline-v26/amnm-provider.bin --output out/image4-mainline-v26/replay.json
```

execution.json保留重建命令、错误绕过负候选stderr及早期夹具修正：最初错误的指令pin被拒绝，按真实08ae00d0修正；最初续接夹具将x20保留为哨兵引发非法读取，改为原初始化全局页和真实effective-chip getter后才验收。manifest节点存在的结论由解析及真实查找复核，不能沿用“节点缺失”的早期猜测。

没有修改出货探针/显示/打包器，不重跑无关740检查。最近设备后验仍为2026-10-25 18:19:42北京时间Android1/A槽/三SHA一致，未实时查询。无设备命令、push、新CI或媒体上传，资格仍false。
