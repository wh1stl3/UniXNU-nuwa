# 固定 r4 loader：静态语义与独立来源链记录

2026-11-11，主控接受的固定r4 loader静态review **PASS**、独立机械来源链 **PASS**。
本次只读已有证据做文档汇总，更新本身 **self-checked**；不重新提取/解压/构建/测试。
设备HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a`，基座
`693f5d9cae8a408dd18b39f3f9fdc4228c934241` 不变，无stage/commit/push。

## 证据与绑定链

静态review证据：`out/loader-r4-binding-20261111-review/`，包含PE/PDB工具输出、
DarwinBoot.disasm.txt及固定镜像提取中间物。
独立机械证据：`out/verifier-loader-r4-binding-20261111/binding.json`、
`completion-r2/`、`completion-r2/source-pin-correction.json`。
下表字段来自现存JSON/PE-PDB文本及主控交付；本次没有重算或替换原产物。

| 链节 | 固定绑定 |
|---|---|
| 镜像 | `.cache/boot-stage12-v4-r4.img`，1495040B，SHA256 `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| 压缩切片 | offset4096、len1483112；binding.json kernel_bytes=1483112、SHA256 `bba190dbef0972a9c768b4b0a88520731bb8e006dd1e2d511f255aa5c70f3cc9` |
| 解压 | 完整输出3145920B=192B shim+3145728B FD；FD tail与留存FD逐字节相同，SHA256 `85bb651a746304343f5baf0d2e1f158405b4054e7886a2815e568fde59fd9256` |
| FD内DarwinBoot | 文件GUID `1B64AF87-8415-4B57-9B16-680D70913B9F`，提取PE28160B，与留存EFI一致，SHA256 `c347f889e8d5d6f166dc8261db2c7e821821e9e181a56fcb936367220d51e5b8` |
| PE→PDB | GUID `C799CBB3-6552-A3F6-4C4C-44205044422E`，age1；PDB SHA256 `580e646114a1c210eb442f8cc3d327b69dd815effb8b73b3b381d0901678816b` |
| PDB→源码 | PDB列DarwinBoot.c rawMD5 `0cb90eaefd580063c3ec721505036027`，匹配实际CRLF源码 |
| 源码→Git | DarwinBoot源仓固定COMMIT `3c75734014cdab0acd9541e88057b7606ee7ae08` 中 `DarwinBootPkg/Driver/DarwinBoot.c`，BLOB `3b6cafc015e19dc291a0bbfd7fe6af71103360db` |

`binding.json` 实际记录 image_bytes/image_sha256、kernel_bytes/kernel_sha256、
shim_bytes/shim_prefix_bytes、fd_tail_bytes/fd_tail_sha256、fd_matches_build=true，
以及pe_candidates的路径/bytes/sha256。留存FD引用为
`../uefi-nuwa/Build/nuwaPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`；本次不触碰该构建树。
PE提取路径在JSON内准确指向上述GUID的section0.pe。
`pe-headers.txt`记录PE CodeView GUID字节及PDBAge=1，`pdb-files.txt`记录同GUID/age和源码MD5。
其中切片offset、独立完整解压/逐字节比较及PDB SHA的接受结论来自主控交付，
不是本次再次执行的声明；未在这些JSON保存的工具完整argv不补造。

## 解压退出码与源码pin纠正

- **独立gzip实际exit2，trailing garbage ignored**；仍得到完整3145920B输出，
  后续FD比较通过。不得写为gzip exit0；reviewer历史exit1不是此次独立执行值。
  `completion-r2/`保留完整切片及shim-fd输出；gzip的exit2依据主控核实的实际执行，
  本次读取的JSON不含其完整command/exit日志，不伪造缺失字段或cwd。
- 此前verifier错误比较COMMIT/BLOB导致的FAIL已明确撤回，不能继续保留“源码不匹配”结论。
  原失败/中间证据保留，不删除或重写。来源链正确比较是
  `git show 3c75734014cdab0acd9541e88057b7606ee7ae08:DarwinBootPkg/Driver/DarwinBoot.c`，
  而不是把commit对象当文件blob；这里记录已交付比较对象，不声称本次执行此命令。
- `completion-r2/source-pin-correction.json`真实字段：git_show_exit=0、stderr空；
  source_raw_bytes=37480、rawMD5如上；source_without_cr_bytes=pinned_bytes=36608，
  equal_after_cr_removal=true；pinned_git_blob_sha1为上述BLOB，
  pinned_sha256=`f3815791ad63b87b11ee28118ad1f35a7d0c5258ea70b7b76eda68914fa2b8cf`。
  即实际CRLF源码去CR后与固定commit:path逐字节一致，原始MD5与PDB匹配。

## 静态语义结论与严格范围

主控接受reviewer对**固定r4**的静态路径判读：仅4类memory-map修补，不注入CHMH/love，
保留BNCH；释放的是读取文件的pool，不是交接window。
这是固定来源绑定后的静态结论，不是本次重新分析代码或执行loader。
独立机械来源链PASS证明上述镜像/FD/PE/PDB/源码绑定，
**不等于全部静态语义被重新独立执行**，不扩展到其他固件/来源版本。

与[wrapper独立主机证据](owner-payload-host-20261111.md)分开：包装验证仍只消费旧固定
prepared kernel `fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`。
新native/prelink/诊断最终布局尚未交付，新hash消费能力未完成；不称新诊断候选、认证、
stage5或设备通过，不静默放宽wrapper门禁。本轮不轮询observer构建或更新共享交接。

文档收尾仅在设备仓cwd运行porting-record check及git diff --check；
真实command/cwd/exit在本轮最终报告。无网络/设备/研究/测试/构建命令。
