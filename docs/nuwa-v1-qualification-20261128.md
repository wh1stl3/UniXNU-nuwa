# nuwa v1 写入资格：主机核对（2026-11-28）

**结论：设备写入资格 BLOCKED；目标初始化顺序在当前实际 v1 入口也未实现。**
主机自检仅运行模拟介质，未接设备、刷写、重启或开放写门；独立 verifier 未复跑。
当前工作树以 `964d7e09c9397dcc306caba88fdbacc2ab82f35f` 为基座，含既有未提交变更。

## 资格矩阵

| 资格 | 必要证据 | 当前来源与缺项 |
| --- | --- | --- |
| 冷启动身份：窗口、seed、几何、所有权 | 独立获取、非零的当前 boot/session、domain、media 身份，和每项证据一致；已验证的 firmware 重新初始化、LU0/4096 B、主备 GPT 与预期身份、窗口/保留区、已知根块、overlay 世代；seed 与实际载入逻辑 seed 绑定，目标窗口范围/内容及所有权获确认。`Gate.h:38–64`、`Provider.h:57–90` 是检查合同，`NativeRamBlock.cpp:464–478` 是运行时 seed 计算位置。 | 旧 NEON 两张画面经主控转述：LU0 计数、4 KiB、主备 GPT/id 和 placement 曾报告正常，[记录](nuwa-ufs-neon-20261126-observation.md) 指明无镜像级启动关联、部分采样不证全窗口。该快照不是本次冷启动身份/排他所有权。`KernelPort.inc:18–27` 的独立预期身份及冷启动八项均为空；当前 seed/世代与窗口状态也未获得可绑定本次新域的完整证据。**阻塞**。 |
| DMA/队列独占 | 旧 firmware/其他 producer 已被可靠停止且不能重新提交；全部在途 DMA、迟到完成和旧映射访问已终止，新的控制器/域和队列取得独占所有权，并保持到命令完成。`oldDmaExcluded` 必须绑定同一独立身份；slot/host 仍要检查隔离与所有权。 | 历史队列观察 `RSR=1`、`DB=0` 不能证明停止和 DMA 排空，见 [队列观察](nuwa-ufs-queue-five-run-20261114.md) 与 [设计](nuwa-data-write-design-20261125.md#r4隔离到经验证冷启动历史候选self-checked)。`KernelPort.inc:13–16,22–27` 明确无可信旧 DMA 排除或可靠 reinit 证据。模拟的 `producerStopped && dmaDone` 只是 fixture 对 `oldDmaExcluded` 的输入，不是实际停止/排空机制。**阻塞**。 |
| FUA 能力及完成语义 | 特定设备/LU/路径的 `WRITE(10)` FUA 能力及完成后非易失介质承诺有可信来源；每笔命令本身还须归属正确、全长成功，见下文。 | 历史 NEON `MS 1/1` 是主控转述的 DPOFUA/WCE 报告，非耐久性证明；[FUA-permissive 试验](nuwa-fua-trial-20261127-observation.md)的底层是非 FUA 写，不能提供 FUA 证据。`KernelPort.inc:28` 始终返回 false；无实机 FUA 持久/断电证据。**阻塞**。 |

正常生产实例固定 `Provider<CandidatePort, false>`（`KernelPort.inc:35–36`）；boot 参数
仅为请求。测试使用 `NUWA_DATA_WRITE_OPT_IN=1`、独立文件、模拟身份/完成响应与
fixture `Provider<HostFilePort>`，不改变或资格化生产实例。

### 什么完成才算 FUA 成功

本项目软件合同要求 `WRITE(10)` 的 FUA 位置 1、LUN 0、4096 B、单块，且已证该
设备/路径的 FUA 耐久合同；准备共享数据前和敲 doorbell 前的 ownership guard 均成立。只有提交槽实际
完成、没有其他 DB 位/致命状态、最终 DB 为零、OCS 为零，响应 UPIU type/LUN/tag
归属正确、response code 为零、SCSI `GOOD`、无额外 sense/残差且实长 4096 B，
`RetainedWritePort` 才接受 `FullFua`（`CombinedRead::issue`、
`RetainedResponse.inc`、`RetainedRead.inc`、`RetainedWrite.inc`）。
CHECK CONDITION、残差、坏归属、非零 OCS、fatal、超时都不是成功，且不能继续发布；
超时不证明原 DMA 已归还。`Provider::sync()` 只检查门禁和状态，不发介质 flush。
即使上述响应全对，缺少设备 FUA 耐久证据也不得声称断电持久。

## 负例（self-checked）

从实际 `NativeRamBlock::attachStore` 经 staged store、`Provider` 到 mock transport
计数，七种“三类资格不是全部成立”的组合均拒绝 open，随后直接 store write/sync
也拒绝，底层写命令数均为 **0**；producer 未停和 DMA 未排空另外各单独置假，
均为 **0**。下表 1 只是主机模型值：

| 身份 | DMA/队列 | FUA | 底层写命令 |
| ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 |
| 0 | 1 | 0 | 0 |
| 1 | 1 | 0 | 0 |
| 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 0 |
| 0 | 1 | 1 | 0 |

## 目标顺序的模拟参考流程（self-checked，非实际 v1 入口）

`tests/test-nuwa-v1-qualification.cpp:referenceInit` 是**只在测试中手动拼装**的参考
流程：人工令三项资格成立，用合成的较宽 `V3::Media` 窗口经实际 `Provider`、
`RetainedWritePort`、staged `CombinedRead` 编码与模拟回复，先写三次零，再调用
上游 `persist::Overlay::open`。它直接打开测试 provider，不是实际
`openCandidateData`/`NativeRamBlock::attachStore` 的初始化路径，不能证明实际路径
能擦除锚点、授权更宽窗口或安全初始化。对捕获的命令，模拟 `GOOD` 仅表示普通文件
`pwrite` 完成、没有 `fdatasync` 或持久性承诺；创建输入时的文件准备操作不计入
模拟底层命令。

实际捕获的 68 条 CDB **每条**检查 opcode `0x2a`、byte 1 `0x08`（FUA=1）、
LU0、transfer length 1，实际 LBA 与以下顺序逐条一致；首次 67 条 payload 全零，
第 68 条是该模拟 seed 的有效 v1 header。下列每项为 `序号:绝对4 KiB LBA`，
全部 `WRITE(10), FUA=1, blocks=1`：

```text
01:59491258  02:57393401  03:57393402  04:59491259
05:59491260  06:59491261  07:59491262  08:59491263
09:59491264  10:59491265  11:59491266  12:59491267
13:59491268  14:59491269  15:59491270  16:59491271
17:59491272  18:59491273  19:59491274  20:59491275
21:59491276  22:59491277  23:59491278  24:59491279
25:59491280  26:59491281  27:59491282  28:59491283
29:59491284  30:59491285  31:59491286  32:59491287
33:59491288  34:59491289  35:59491290  36:59491291
37:59491292  38:59491293  39:59491294  40:59491295
41:59491296  42:59491297  43:59491298  44:59491299
45:59491300  46:59491301  47:59491302  48:59491303
49:59491304  50:59491305  51:59491306  52:59491307
53:59491308  54:59491309  55:59491310  56:59491311
57:59491312  58:59491313  59:59491314  60:59491315
61:59491316  62:59491317  63:59491318  64:59491319
65:59491320  66:59491321  67:59491322  68:59491258
```

其中 01 作废 v1 header、02–03 清 v3 锚点、04–67 升序清 64 个 bitmap、
68 发布 header：**67 个不同 LBA、68 笔单块写**。模型逐一在前 67 笔注入可归属
CHECK CONDITION，67/67 均停在故障命令、没有最终 header 写；最终 header 本身
失败也不报成功。另在第 4 笔注入残差、错误 tag、超时、非零 OCS、fatal，五例
均不提交最终 header。这些是模拟响应，不证明真实写失败时介质未改变。

## 实际 v1 入口的差异与阻塞

模拟三项资格均成立后，调用真实 `NativeRamBlock::attachStore`，当前
`PersistOverlay.h:101–106` 的首笔实际写是 **59491259**，而非应有的
**59491258**；之后依次清到 59491322 并写 59491258，共 **65** 笔，
不清两个 v3 锚点。逐条 CDB 同样核对为单块 FUA `WRITE(10)`。
对现有 64 个 bitmap 写逐次注入失败，64/64 不继续提交最终 header；
但测试先放入有效旧 header 和非零 bitmap，前面至少一个 bitmap 已成功清零时，
旧 header 仍然有效。这不能满足本次要求的先作废 header 合同。真实 v1 入口
对可识别 v3 锚点还会在 preflight 拒绝打开，而不是清它们。

因此阻塞清单为：

1. 缺当前新域可独立绑定的 boot/domain/media、窗口、seed、几何、根块、
   世代及所有权证据。
2. 缺旧 producer 排除、在途 DMA 排空和独占队列的可信证据。
3. 缺该设备/LU 实际 FUA 成功及其持久性证据；以模拟 `GOOD` 或接受 FUA 位代替无效。
4. 当前实际入口缺前置 v1 header 作废与两锚点清理；目标 68 笔只由参考 fixture
   发出，还缺真实实现及对初始化范围、旧内容/恢复和失败状态的审查。生产门禁
   维持关闭；任何涉及 DMA/队列/锁或启动链的后续改动需按规则升级审查。

## 复跑及输入绑定

WSL Ubuntu-22.04，C++17、ASan/UBSan；所有镜像均为临时目录里的普通稀疏文件，
每个用例新进程，故障响应为模拟值。复跑命令（只做主机测试）：

```sh
cd /mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126
/home/wh1stl3/.local/bin/python3.11 -B tests/test-nuwa-v1-entry.py \
  /mnt/d/Code/PortingiOS/UniXNU \
  out/nuwa-v1-shape-20261128-build/nuwa-data-provider/NativeUfs.cpp \
  out/nuwa-v1-shape-20261128-build/nuwa-data-provider/CombinedRead.h \
  --qualification
```

命令 exit 0，完整逐条输出位于 `out/nuwa-v1-qualification-20261128.log`；
上述表格和结论不依赖该被忽略文件作为唯一证据。编译前曾因将原 `main` 重命名为
普通函数、缺显式 return 而在 `tests/test-nuwa-v1-entry.cpp` 末尾触发
`-Werror=return-type`；补 `return 0` 后重跑得到上述结果。

`porting-record.py check --device <worktree>` 返回 `nuwa: 14 structured areas checked`。
加 `--base origin/main` 时，WSL Git 无法解析工作树 `.git` 中的 Windows
`D:/...` gitdir，命令 exit 1；带 base 的检查未完成，不以无 base 的结果代替。

| 输入 | SHA-256 |
| --- | --- |
| `tests/test-nuwa-v1-entry.cpp` | `1a1c600ca2c9c2f9ace92c85a7f0bced78868e10d0a7faf9e7a8c73d46d010e9` |
| `tests/test-nuwa-v1-entry.py` | `685d6fed38822b534e9432ee2cd6d71fb250d3a4c319630841330e7d79b167f2` |
| `tests/test-nuwa-v1-qualification.cpp` | `077b86feb5f150753760b62f0ed56fcdc7d3bb94814d89ccd9f23eb9e79c7ce2` |
| `tests/test-nuwa-retained-response.cpp` | `e1300e4f0c18b6793b171b18869411a2ef17b607a1dff6f05d32f9c2aa983adf` |
| `tests/NuwaDataFixtureGpt.h` | `724ff5c577021a0d4224606a73ecc45be90121b8c4a616d9b2aafc452adab285` |
| `package/nuwa-ramblock/NativeRamBlock.cpp` | `2e9904549a4dee31a17b0fb52924f7baa373c6b5aa7617991d0acd562d6ff64e` |
| `package/nuwa-data-write/Gate.h` | `2cddbd31f6d8d092f244c83ebd7b7af3049bffc6b3b442753dc7336fb2d2cf8f` |
| `package/nuwa-data-write/Provider.h` | `b3be16bc83d91ce07867e2c3d753b67f755d19a9a0aa60c026774f9df1474b25` |
| `package/nuwa-data-write/KernelPort.inc` | `8db35f5f9ad7328b558928aeb7a51e10733b3c4b8d93a0fefe94cf13c6416ab5` |
| `package/nuwa-data-write/RetainedWrite.inc` | `a7f05597de7b29fda70100364ac18f771f83d26ccdb60e4e4d2d78420383f20c` |
| `package/nuwa-data-write/RetainedRead.inc` | `0ca15ad9a4ddf44d04f8b332a6ab806b9e3da24d0119d867132f2c6354d1bb69` |
| `package/nuwa-data-write/RetainedResponse.inc` | `68c358c4ca0707489df8947dbb1f966ee6c48d3d63aaf02ba9ae271f0682e36f` |
| staged `NativeUfs.cpp` | `84a57e15d653578ad467feeb31f16a52b0d97cd0df0c03bdd3d0676ff412eb6d` |
| staged `CombinedRead.h` | `cf28e51ca9153f708dab1add52dd80f803470f4fc780148cd816945f6c8a6167` |
| staged dependency `TransferPoll.h` | `742df51cdce6d06df6bf93294176f01305c9d1359c8ffdfb99daff7b76a1ece3` |
| staged dependency `PreservedNop.h` | `0add0e8d1115dbbb9b7b54f1222ed795767f773ad6d340914616bbd755bde584` |
| staged dependency `RootReadSession.h` | `3c40d91d6d38f648a245d973e820fa49fe328d1a069e1a92beeb96ddb3cd6142` |
| UniXNU `drivers/RamBlock/DirectDisk.h` | `c17bcf4f740b3d440555e24b9c37d8c95c9313e6c515c1a4894e4876f984764c` |
| UniXNU `drivers/RamBlock/PersistOverlay.h` | `5b74d81d5f31743624893377b0e037ffeea0cc30caad880c8209e57d79adca83` |

上游实现复用：`UniXNU/UniXNU@693f5d9cae8a408dd18b39f3f9fdc4228c934241` 的
RamBlock v1（BSD-2-Clause-Patent）；retained transport 复用现有设备仓主机 fixture。
