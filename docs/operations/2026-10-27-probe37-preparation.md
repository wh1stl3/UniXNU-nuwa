# PROBE37 / revision45：fetch及type4内部连续观察

本轮合并58个观察点，覆盖固定 `_decmpfs_fetch_uncompressed_data` 和type4 fetch回调。包括共享锁、函数选择、真实间接调用、错误记录、可选原生缓存维护，以及回调内分配、释放、无名读取/处理helper和memmove调用/续接。无名helper仅按固定地址标识，不杜撰符号或把静态目标当实机调用成功。

新增 `scripts/read_fetch_sites.py`、`scripts/test-read-fetch.py`。ID441..466属于fetch，467..498属于固定type4回调；在旧压缩短线下方8像素交错，32×2，入口品红、调用琥珀、成对续接/RET前白色。既有373..440、HEX及全部后续外层路径保留，不新增成功阶段停点。新布局在原1040行显示范围内，不改板值/内存大小/基址/IPSW身份。

作用域要求当前header、线程、实际外层APFS目标、外层调用配对、decmp→fetch→callback帧和原生LR链。固定回调入口还必须匹配实际捕获的间接x8及在途fetch调用位；每个函数内部独立配对，不凭地址命中就认定当前请求。64字节诊断状态每header重置。原生锁/错误/认证/IRQ、缓存策略和239释放门保持，不设置*_verified。

首构建失败：新增供体回调点未加入构建器精确donor_hooks声明，整段字节核验拒绝，未写出候选内核、未部署。原工作目录out/kernel-entry-probe-45-fetch和initial-build-failure.json保留。修正只列出固定callback观察地址，清单之外的整个供体段仍严格逐字节比较。

修正候选out/kernel-entry-probe-45-fetch-r2/kernel-entry-probe.macho，SHA256 `6642a380c215de05b38fac2320f0a097011237bbf28e4e0c15b0b5869738128e`，58560512字节。ADT out/exec-mainline-v45/launch/kernel.macho.adt，SHA256 `02145f42f03511638cba207bc594fca54a1aad46d94423a13a1b7c2d32eb649a`。

45个作用域快速检查、header重置和真实fetch前缀对照通过；仅执行到第一处锁体前，不是完整解压模型。完整34项串行检查正在运行，含全部新增位置的原生状态及像素对照、错误上下文拒绝、布局、缺失配对负对照和证据绑定；尚未完成最终包资格，不可启动。日志reports/kernel-entry-probe/2026-10-27-v45-preparation/regression-console.txt。

此前源码原字节out/before-probe37-source。Media-nuwa原件本地保留，36后验已完成。未提交/推送，不操作其他机型或第二写入者。

## 固定ABI核对

两处原生调用0xfffffff007480474/0xfffffff007480520均把vec放x5、bytes_read指针放x6；fetch前缀用x6清零bytes_read，保存x5/x6，间接调用前重排为x5=1、x6=vec、x7=bytes_read。公开源包含nvec参数，但本二进制内部函数已把它常量化；只按公开C签名解读寄存器会错位。实际指令已核对，两处调用一致，新夹具遵循此布局，未改变任何原生传参。

58个标记对应56个唯一指令地址；两个地址兼作上一调用续接和下一调用，分别记录配对，不能把标记数当独立指令数。正式新增测试要求509项（56×9作用域模式及5项综合检查）。

## 回归中的尺寸基线问题

完整回归在shared-hex的旧尺寸断言失败：旧断言把整包代码与较少观察点的PROBE34比较，新增58个标记后候选总代码221184字节恰好与旧基线相等。1968透明性、476原读取位置、617压缩读取等此前已通过。原execution.json和regression-console.txt不覆盖。

修正比较方法为同一组观察点、同一份生成汇编和链接参数，分别编译共享HEX及内联HEX；先重新编译原汇编并与候选代码逐字节比较，再仅替换普通HEX宏展开方式。内联对照保留同一共享helper/data/所有观察点，未生成可部署镜像。结果258048→221184字节，节省36864字节。像素、缓存重置、无视频、原生分派等原检查保留。

修正过程中还遇到生成汇编哈希与template哈希范围不同：生成文件前附.equ常量，首次完整文件直接对template摘要比较失败。原错误控制台shared-hex-corrected-console.txt保留；修正为核对template后缀，并用重新编译逐字节一致来验证包括常量在内的完整输入。通过控制台shared-hex-controlled-console.txt，代码对照位于out/hex-inline-control-2026-10-27-v45-r2。

候选二进制未改变，保留不受影响且绑定同一候选的已通过检查，只重新执行修正检查与尚未执行项；续接记录execution-continuation.json，全部通过后才形成execution-qualified.json，内含原失败记录路径及摘要。不把失败执行记录改写成通过。

## 最终资格及单次部署

上述核验中状态已成为历史：34项全部完成，1968透明性、476原读取位置、617压缩读取、72短线、509 fetch/type4、59绑定检查通过。execution-qualified.json串联原通过结果及续接结果，失败原件保留。独立内核逐字节一致，最终包回读通过；正式qualification.json位于2026-10-27-v45-r2目录。

包reports/xnu-first-entry/entry-probe-37.json，镜像out/trial-boot/xnu-entry-probe-37-fetch/boot-xnu-first-entry.img，204484608字节，SHA256 6b1b1a211681e1ff5bd1a664ef25957c52dc18d213e9ca5ccf3eb3fd3005bd31。2026-10-27 01:05:07 +08临时发送完成、ACK0，已consumed禁止重发。证据reports/xnu-entry-probe-trial/2026-10-27-v45/{preflight,launch,consumed}.json。启动前新鲜预检Android1/nuwa/kalama/A槽/三SHA一致，启动后不能继续把它当当前设备状态。

本阶段持续启动授权和刚完成的媒体/自行恢复支持观测恢复条件；预检human_capture_source固定描述Fresh confirmation，实际依据以human_capture_confirmation正文为准，不冒称用户对37另行确认。源码增量out/probe37-source.diff。用户随后已报告37媒体落位并回Android，待新后验和媒体核对，继续下一轮。
