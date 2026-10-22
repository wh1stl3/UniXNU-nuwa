# 8796 donor VFS桥接与完整指针表清点

## 结论

当前源内核与已核验iPhone donor，在参考组件选择的65,348项指针绑定中只有APFS的_vfs_getvfs_with_vfsops缺失。已准备真实上游实现的回移候选，纳入下一轮输入；完整60项231 hunks、配方hash/bash语法静态检查通过，实际编译/绑定仍待CI。未生成预链接镜像、未采纳board的roots/slide/initializer数值。

## 清点证据

scripts/ci/audit-donor-bindings.py读取实际MH_EXECUTE及donor的_PrelinkInfoDictionary/_PrelinkLinkKASLROffsets，用固定解析器检查段/符号，遍历实际指针表，不为缺失符号填假地址，也不emit。仅将已核验相同donor的参考报告组件集用作分析输入；组件选择不是正式硬件/board配置。

命令参数：

```text
python -X utf8 -B scripts/ci/audit-donor-bindings.py --kernel out/kernel-ci/39742250205/nuwa-8796-source-39742250205/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped --donor D:/Code/PortingiOS/nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho --selection-report D:/Code/PortingiOSWithUniXNU/.work/kernel-prelinked.json --output reports/donor-compat/current-kernel-bindings.json
```

同一命令换成参考run24实际内核，输出reference-kernel-bindings.json。两次都是41,095项kernel绑定及24,253项component绑定，总数与已存在参考report的bindings/计数一致；参考输入0错误，本仓输入1错误，见inventory-crosscheck.json。缺失项为APFS原始指针位点0xfffffff006eac110，目标0xfffffff00734c520，其donor导出名为_vfs_getvfs_with_vfsops。这里只记录读取到的地址，不填入board或重定位镜像。

工具只检查指针表名字/依赖闭包，未验证布局、PC-relative指令、全部非表内引用、C++结构/调用约定、初始化/运行时。零缺失也不能写成完整预链接ABI通过。

## 回移实现与语义

候选patches/xnu-8796-donor-candidates/vfs-getvfs-with-vfsops.patch来自并行仓经审查补丁，仅更改bsd/sys/mount.h的声明、bsd/vfs/vfs_subr.c的实际函数以及config/BSDKernel.exports。

函数执行mount_list_lookupby_fsid(fsid,0,0)，有mount且mnt_op不匹配时返回NULL，其余返回真实mount。函数定义与只读10063上游bsd/vfs/vfs_subr.c:1955去空白后相同；底层lookup函数与8796现有实现也相同，包含获取/释放mount_list_lock的条件及withref处理，参数0,0不新增引用。没有返回恒成功、假mount或性能provider。

scripts/ci/check-donor-compat.py对实际下一轮补丁顺序在内存应用，逐一比对函数/底层helper、唯一声明和导出；vfs-static-check.json记录主源码hash和行号。next-sequence-check.json为60项231 hunks，next-source-input-check.json区分48项原选择、11项CI兼容及1项donor桥接，输入与配方语法静态检查通过。正在运行的第十二轮仍使用旧59项，不混写成已编译此候选。

下一步取第十二轮平台库结果，按真实首错修复后以新输入进行完整构建。只有取得本候选实际Mach-O导出后，才重跑本仓donor只读plan和清点。iPhone donor真实身份/hash已独立核对，保持4KiB/iOS16及feed不变；boot-progress/watchdog和镜像硬停继续有效。


## 2026-10-22 16:47 实际编译后核对

CI13真实内核SHA08c23dc162e934a2e9c59780da0a3d69c8f7f422c9f167b80a87b10e550927e3已包含VFS桥接，指针绑定65,348项零失败，唯一APFS缺口已消除。官方只读plan也通过119段布局检查，参考roots/slide仅为分析输入，不是本仓配置。reports/donor-compat/ci13-kernel-bindings.json及ci13-readonly-plan.json；仍未emit，PC-relative、完整ABI和硬件未验证。
