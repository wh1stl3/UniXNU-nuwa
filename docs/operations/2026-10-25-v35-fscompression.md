# v35 / PROBE27：类型4解压组件的正常初始化

PROBE26实测第二次exec已到文件属性和执行权限检查之后，250=vn_rdwr文件头读取调用亮、251后继暗，Mach-O/dyld后续未见。保留的聚合ENOENT和首项242属于先前完成结果的可能性已由D-063说明，不能继续当作当前读取的返回。原图03259a98仅本地，v34/screen.json；Android1/A槽/三SHA恢复闭环已完成，无待恢复。

固定APFS d180c38d只读属性审计v35/exec-compression.json确认launchd和dyld都有com.apple.decmpfs，类型4、资源分叉，解压长度分别541600/922912字节。核对SHA与既有文件相同，挂载已卸载。固定工具66b86bd525e8cb90f9012543be89b1f092b75cf3/GPL-2.0；主机能解压不等于内核解压器已初始化。

固定XNU1b191cb58250d0705d8a51287127505aa4bc0789，bsd/kern/decmpfs.c SHA9d5c0d486cd31222e007e6335aed0ce1e3bd6e609ab02005ac61d03dd421471c，APSL-2.0。源码206至259表明：decompressors[type]为空而IOCatalogue知道对应驱动时，等待MatchingResource注册；1090起正常register_decmpfs_decompressor写真实注册表并发布资源。预链接包含com.apple.AppleFSCompression.AppleFSCompressionTypeZlib，不证明其实际启动。类型4槽为原生_decompressors(0xfffffff007ae95b0)+32；正常加载API为_OSKextLoadKextWithIdentifier(0xfffffff007824574)，均来自固定内核符号。

首要假设是压缩读取等待类型4组件注册；仍可能已注册而停在mac_vnode_check_read或APFS/VNOP读取内部。实机尚未读到注册表，不能将初始化缺失宣称为已证根因。最小证伪：若264黄色表示已注册且读取仍停，则排除“缺注册”为本轮解释；若加载后真实指针出现且251及后续点推进，支持此修复，但仍须看后续原生结果。

实现patches/xnu-8796-candidates/fscompression-oskext-start.S在实际init exec之前、vfsinit和BSD初始化之后检查类型4注册指针。非空直接继续；为空只请求上述真实OSKext生命周期，记录实际返回和实际表项后继续。无直接kmod入口调用、无写假注册表、无跳过认证或原生错误。helper保留x0至x8、x29/x30、全部SIMD、FPCR/FPSR；外层保存x9至x28/NZCV。首进程回退时再次检查，可避免重复注册。

264蓝=加载请求、264黄=原已注册；265绿=API返回或已注册，单独不证明初始化成功。A02A为真实加载状态，A033为真实类型4注册指针；异常/panic另按其布局解释。原240至263、尝试数、原生exec结果与恢复用户态释放守卫保持；没有新增成功终点。

8项实际hook执行检查覆盖已注册跳过、正常加载、失败、成功但未注册及有无视频，校验调用目标/标识、上下文保存、实际状态，不执行真实OSKext生命周期或解压函数。模型的注册写入仅是明确API边界替身，交付helper无该写入；另监测helper不直接写原生表。新增强制fscompression-startup证据及缺失/删项反例，不能凭“返回0”打包宣称成功。

最终候选v35/build.json，内核bca646e7498e6dc2b2efa7fa02a248c717067313eb0958707b8e27989175cdbc，58449920字节；ADT34acf64bacffe26f602d62b3bc84b8d415bac1695c3cef832e6d9248926f3b34。完整回归、独立重建与实际包回读完成前不得试启动。根镜像、运输、FD/shim、内存表/TCR、iOS16/8796身份及*_verified保持；用户决定暂不全量迁移上游，沿用有效基线处理当前读取问题。无flash/erase/改槽、push/新CI或媒体上传。

## 离线完成与启动门

PROBE27条件初始化真实类型4解压组件候选离线完成。22项串行回归全部通过：1052透明性、25Image4、6pthread、15exec边界、8解压启动模型、7根输入、36绑定及既有入口/MMU/向量/显示回归。独立重建逐字节一致，新包实际FAT回读及旧包26复验通过。预检2026-10-25T23:50:46.940487+08:00确认Android1/A槽/三SHA与v34后验一致；沿用本轮连续实拍、已验证按键恢复和用户最新继续主线指令，条件未报告失效，尚未启动27。

权威包reports/xnu-first-entry/entry-probe-27.json；镜像out/trial-boot/xnu-entry-probe-27-fscompression/boot-xnu-first-entry.img，204484608B，SHA256 06913eaf3124e2634a2c9e654f66b374ece2caf2fed790dea8b6578b0d34955d。内核bca646e7498e6dc2b2efa7fa02a248c717067313eb0958707b8e27989175cdbc，58449920B；ADT34acf64bacffe26f602d62b3bc84b8d415bac1695c3cef832e6d9248926f3b34；真实APFS d180c38d、192MiB运输、-v rd=md0保持。代码父d5878f0，本轮提交号以git log为准，无push/新CI。

构建在既有连续链上新增--fscompression，verify-image4-entry-candidate.py串行22项原命令和输出见v35/execution.json。8项FS模型及缺失/删项反例强制绑定，独立重建v35/reproduce.json；build_xnu_boot_package.py --validate回读包27及旧26。新鲜授权上下文原文保留于v35/preflight，不虚构用户另答了本包问题。

## 本轮启动

PROBE27于2026-10-25T23:53:48.080828+08:00仅一次临时boot ACK，代码45a57de，镜像06913eaf；等待菜单电源Enter后的完整画面，重点A02A加载状态、A033实际type4注册指针、264/265及250/251。ACK不证明解压器已注册、读取已返回或exec成功；本轮Android恢复后验尚未取得，不重复启动或第二候选。已有连续推进授权和具体画面/恢复条件沿用，新鲜Android1/A槽/三SHA预检一致。取图后trial-v4-firmware.py recover --package reports/xnu-first-entry/entry-probe-27.json --evidence reports/xnu-entry-probe-trial/2026-10-25-v35/recovery.json；再record-nuwa-trial-state.py对比本轮preflight补postcondition。人工等待继续离线工作，真实故障和明确硬停/未授权设备内容更改边界保持；fastboot查询缺失变量按已定规则处理。启动证据v35/launch.json。

## PROBE27实机核图与最终收尾（2026-10-26）

PROBE27照片核验与恢复收尾完成。264黄色/265绿色，A02A=0，A033=FFFFFFF005F48EF8（用户纠正末尾EF8，原图已复核），证明观察到了类型4表项已存在的分支；加载请求蓝色未见，不能把A02A0说成一次真实加载调用返回0。250文件头读取调用亮、251后继暗，Mach-O/dyld未到；缺少类型4空表项已不能解释当前观察停点。2026-10-26T00:16:10.211478+08:00恢复驱动确认Android完成1；2026-10-26T00:19:12.450574+08:00后验确认Android1/A槽/三分区SHA与本轮预检一致，恢复关闭，无待人工操作。按用户要求本轮到照片验证、文档与提交为止，不构建或启动下一候选。

原图62f86fe67cad0e6f0facb9a4262f78d5b26ee1947d5957a6ca7080ea9a76736d（4898922B）仅本地out/trial-evidence/entry-probe-27/user-screen.jpg；文字/采样reports/xnu-entry-probe-trial/2026-10-25-v35/screen.json。A02C=2，A02D/A030=2，A02E=0xF2/242、A032=2是跨尝试保留结果，不能当作本次未返回读取的errno。A02F0，未观察任务切换/签名或239释放守卫。候选静态0xfffffff005f48ef8为version3及五个非零回调地址，与读数相符；这不是运行时内存转储或解压执行证明。

D-065据此将“当前缺少类型4空表项”假设排除，D-064条件初始化实现保留但不宣称修复成功。下一轮以新的2026-10-26-mainline-handoff.md为准；本轮按用户要求只落档/提交，不启动下一候选。
