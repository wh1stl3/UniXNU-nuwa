# 8796实际CI兼容性补丁

本目录不是完整`patches/xnu`模块；源CI组装器将这里明确选择的补丁加入原48项选择。本轮一项新增，因此实际为48+1，不改旧38/11和48项历史统计。

`clang17-zero-init.patch`由运行39715232540的真实clang错误触发：8796 MakeInc.def:309的过渡开关已不被该Apple clang17接受。仅删除这个开关，保留前一行`-ftrivial-auto-var-init=zero`，不关闭变量初始化、不压错误、不跳过编译。适用性与保留清零的检查记录在`reports/kernel-ci/39715232540/failure-analysis.json`；完整构建结果以重跑日志为准。
