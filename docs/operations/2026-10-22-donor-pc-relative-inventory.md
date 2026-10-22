# iPhone donor外部PC-relative编码与既有候选字节保持

2026-10-22 16:33；仅只读分析，不生成/重写预链接、诊断或固件镜像。

## 已取得的结果

- 对同一真实iPhone donor及参考组件选择，固定官方NativePrelink实现仍在0xfffffff005b8c1cc拒绝外部PC-relative编码。
- 完整清点得到236,910项内部编码，另有12项未验收外部编码，全部在com.apple.kec.Libm，4项为ADRP；位点与参考报告豁免集合完全一致，无新增或遗漏。
- 参考报告的9个已知常量池逐一核对完整字节hash，并要求digest确实存在于固定官方工具的池清单；未使用只看前缀的豁免。
- 对已存在的参考候选读回核对，30段组件__TEXT_EXEC共4,201,824字节，与donor逐段完全相同，完整hash写入pc-relative-inventory.json。没有运行修改后的emit或生成新候选。

以上分别证明编码清点/常量池完整指纹/已有代码字节保持；不证明未知站点是数据，也不证明跨映射指令语义、完整ABI或硬件。已有候选不是损坏文件的证据，与其是否可运行是不同验收项。

## 参考豁免的准确分类

实际是6项窗口外放行、6项external_pc_relative_inline_data入口oracle放行。前次artifacts-review.json按不存在的reason键归类，误将12项都列为窗口外；已根据实际kind字段更正。12项总数与4项ADRP、产物SHA及其他可用性结论不变，时间线记录保留。

四项ADRP均属于窗口外类别；剩余两项窗口外是解码的直接分支。入口oracle的6项包含ADR、测试位分支和比较分支。函数入口集合不包含数据地址和全部内部代码落点，所以“目标不是已知入口”不能单独作为恒定数据判据。所有12项在本仓仍标为unqualified，不自动继承豁免。

## 复现

```text
python -X utf8 -B scripts/ci/audit-donor-pc-relative.py --donor D:/Code/PortingiOS/nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho --selection-report D:/Code/PortingiOSWithUniXNU/.work/kernel-prelinked.json --existing-candidate D:/Code/PortingiOSWithUniXNU/.work/kernel-prelinked.macho --output reports/donor-compat/pc-relative-inventory.json
```

脚本只调用固定工具的解析和instruction_inventory函数；不会调用emit，不会改源文件或未知指令检查。报告有工具SHA、真实donor/candidate SHA、12项原始字/文件偏移/上下文字节、30项前后hash及官方拒绝原文。分析用参考选择，不采纳board的roots、slide或其他板值。

下一步等待第十三轮VFS/平台archive真实结果，再做本仓内核的只读plan。若要对这12处作数据豁免，先建立完整常量区间和代码/引用证据；镜像生成/上机另按既定硬停处理。没有把本次静态证据写成QEMU或实机通过。
