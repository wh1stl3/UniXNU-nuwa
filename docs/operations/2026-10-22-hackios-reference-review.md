# 用户提供的HackiOS对照报告核验

原报告已按用户提供内容保存为docs/inherited/hackios-route-comparison-2026-10-22.md，来源/原始及LF归一化SHA-256见reports/hackios-review/source-report.json。报告的建议只作参考，不替代AGENTS、用户已定决策或UniXNU官方契约；原始外部文件未修改。此次没有执行上游代码、克隆源码树、使用预编译文件或操作设备。

## 核对到的事实

已读取报告固定提交的公开仓库和实际实现文件，GitHub API返回内容哈希及短摘录保存于primary-read.json/linux-review.json：

- kernel仓8e61187098f2c26c5daee8f9f72b6416aa64b9ab和userland仓906425b75e02b4f99eb5d7bb1ef7c9583472d772确有源码。不能再按“只公开官网”评价。报告固定的是8796.121.2/iOS16.5；当前nuwa的8796.141.3/iOS16.7.16身份保持。
- gen-iig-stubs.py为已有_Impl生成转接，其余方法返回Unsupported；源码明确用户态DriverKit驱动不可用。xnu/README.md还将导出/symbolset错误与make非零退出列为已知局限。不能据此取消我们真实IIG、完整make退出码和最终符号检查。
- xnu/files/osfmk/arm64/kpc.c报告PMU不可用，计数相关接口返回0/不支持。它展示另一种明确缩减性能接口的实现，不能直接作为SM8550 PMU已适配的证据。
- Linux xnu-clang包装器选择Mach-O目标并剔除部分Apple参数；compat头将类型签名/summary降级为固定描述。它不是已经提供了当前WSL预检所缺的等价XNU内建、真实IIG和完整sysroot证明。
- loader_return.c保留UEFI环境，通过/chosen/loader-return返回，源码要求避免与UEFI同时驱动同一硬件。可借鉴早期日志设计；不能直接套用redwood地址、固件、DMA或设备所有权规则。

## 对当前主线的作用

先把Linux包装/8796缺源处理和返回加载器日志列入后续对照入口，继续完成现有源CI，再解决Darwin22 archive/NativePrelink闭包。没有改换基座、donor、页大小或loader，没有导入IIG桩或内核服务替代实现。nuwa的板级、硬件交接、供体绑定仍待本仓独立验证。当前已获得真实IIG生成与关键对象证据，不据报告取消这条验收链。

主要原始来源：

- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/README.md
- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/README.md
- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu-deps/gen-iig-stubs.py
- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu-deps/hostinc/xnu_clang_compat.h
- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/files/osfmk/arm64/kpc.c
- https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/files/osfmk/arm64/loader_return.c
- https://github.com/oosexgang/hackios-xnu-userland/blob/906425b75e02b4f99eb5d7bb1ef7c9583472d772/README.md
