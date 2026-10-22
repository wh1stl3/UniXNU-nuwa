# 8796 候选补丁（未接入构建）

这里只含8个适配候选，**不是完整 `patches/xnu` 覆盖模块**。不要重命名成xnu或替换基座模块，否则会遮掉其余补丁。

通过 `scripts/prepare-8796-context-candidates.py` 从只读8796源文件在内存中生成前5项diff；再由 `scripts/check-8796-sequence.py` 适配public-entitlements、SystemOS及boot-progress。源文件不落盘，记录上游原补丁与候选的SHA-256。前5项独立 `git apply --check` 静态检查通过；后3项纳入完整选择集的内存顺序模拟及合并diff只读检查，不能把有前置依赖的boot-progress当作独立通过。未执行磁盘累积应用或编译。

适配理由及范围见 `docs/operations/2026-10-22-8796-context-candidates.md` 与 `docs/operations/2026-10-22-8796-selected-sequence.md`。feed未改，board内存/地址字段未改。
