# STATUS

更新：2026-10-25。PROBE27条件初始化真实类型4解压组件候选离线完成。22项串行回归全部通过：1052透明性、25Image4、6pthread、15exec边界、8解压启动模型、7根输入、36绑定及既有入口/MMU/向量/显示回归。独立重建逐字节一致，新包实际FAT回读及旧包26复验通过。预检2026-10-25T23:50:46.940487+08:00确认Android1/A槽/三SHA与v34后验一致；沿用本轮连续实拍、已验证按键恢复和用户最新继续主线指令，条件未报告失效，尚未启动27。

权威包reports/xnu-first-entry/entry-probe-27.json；镜像out/trial-boot/xnu-entry-probe-27-fscompression/boot-xnu-first-entry.img，204484608B，SHA256 06913eaf3124e2634a2c9e654f66b374ece2caf2fed790dea8b6578b0d34955d。内核bca646e7498e6dc2b2efa7fa02a248c717067313eb0958707b8e27989175cdbc，58449920B；ADT34acf64bacffe26f602d62b3bc84b8d415bac1695c3cef832e6d9248926f3b34；真实APFS d180c38d、192MiB运输、-v rd=md0保持。代码父d5878f0，本轮提交号以git log为准，无push/新CI。

最近内核实测PROBE26：第二次exec到文件头读取250亮/251暗，240至249已达；Mach-O/dyld未到。保留ENOENT来自前一次开发路径失败的可能性明确，不能认定当前读取返回2。原图03259a98仅本地，v34 screen/recovery/postcondition；Android1/A槽/三SHA已恢复闭环，无待恢复。

只读审计确认launchd/dyld使用decmpfs type4，已有Zlib预链接组件不证明实际注册。新helper在实际init exec前读取原生注册表slot4：非空跳过，空时请求正常OSKext加载并记录真实返回与表项。无直接组件入口或注册表写入，无原生错误/认证改写，无新增成功终点。264蓝=加载请求、264黄=原已注册；265绿只表示返回/已存在，需结合A02A实际加载状态和A033实际注册指针解释。若已注册仍不读，则证伪缺注册假设并转查读取内部等待。模型未执行实际生命周期或解压函数，不宣称实机修复。

下一步即时通知后仅一次临时boot，菜单电源Enter后保存完整最终画面，包括右侧264/265及A02A/A033和原读取/exec点。取得画面后固定原厂临时boot恢复Android1，再与v35/preflight对比A槽/三SHA；恢复未确认不启动第二候选。人工等待继续离线工作。若日志或恢复条件失效，按AGENTS §3停在启动前。

按用户决定保持当前基线，暂不全量迁移新UniXNU框架。FD/shim、板内存/TCR、iOS16/8796身份和*_verified不变，loadable/runtime_qualified=false；无flash/erase/改槽或原始媒体上传。fastboot getvar缺失变量保留日志、重进一次不单独硬停；必要目标/日志/恢复门不放宽。

源码、测试局限及命令见[本轮记录](operations/2026-10-25-v35-fscompression.md)。
