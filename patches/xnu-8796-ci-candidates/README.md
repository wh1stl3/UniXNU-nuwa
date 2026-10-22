# 8796实际CI兼容性补丁

本目录不是完整`patches/xnu`模块；源CI组装器将这里明确选择的补丁加入原48项选择。当前两项新增，因此实际为48+2，不改旧38/11和48项历史统计。

`clang17-zero-init.patch`由运行39715232540的真实clang错误触发：8796 MakeInc.def:309的过渡开关已不被该Apple clang17接受。仅删除这个开关，保留前一行`-ftrivial-auto-var-init=zero`，不关闭变量初始化、不压错误、不跳过编译。适用性与保留清零的检查记录在`reports/kernel-ci/39715232540/failure-analysis.json`；完整构建结果以重跑日志为准。

`clang17-uio-stackbuf.patch`由第二轮39716728005的真实数组元素对齐错误触发；保留原typedef，新增声明宏，把36处数组改为char数组并对变量施加原`_Alignof(union iovecs)`对齐，元素字节类型及`UIO_SIZEOF(niov)`范围不变。不是把元素扩大到8字节或去掉对齐；待实际clang17重跑验证。

IIG兼容性使用工具实际支持的`--deployment-target`，在CI环境以`OTHER_IIG_FLAGS=--deployment-target 22.0`传入Makefile已有入口；不修改`IORPC`。选项依据纯文本运行39717772747的iig-help与binary strings（同时含旧/新IORPC生成模板）；正确生成分支仍须以第三轮真实编译及生成代码报告确认。
