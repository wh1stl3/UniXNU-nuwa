# 官方仓库与macOS Actions接入审查

## 当前结论

**官方确有macOS build工作流，适合作为云端构建入口；nuwa完整8796设备构建仍未就绪。** 已完成固定提交只读核验与候选；用户后续解除Git命令限制、选择公开设备仓，已登录wh1stl3并创建基座fork与设备仓。专用源构建入口见[首轮CI](2026-10-22-source-kernel-ci.md)。尚无内核构建通过证据。

官方[构建指南](https://unixnu.com/building#macos-runner)要求fork基座以运行Actions，同时传入独立设备仓。[sheng构建](https://unixnu.com/zh/devices/sheng)保留基座、设备仓与UEFI固件仓三部分，设备仓用`-D`接入。nuwa对应关系：

| 目标仓库 | 职责 | 本轮状态 |
| --- | --- | --- |
| `wh1stl3/UniXNU` | 基座fork、macOS工作流及必要的基座适配 | 未认证API返回404，无法区分私有和不存在 |
| `wh1stl3/UniXNU-nuwa` | 本设备仓：board、8796覆盖、defconfig、driver/kit及脚本 | 同上；本地内容未发布 |
| `wh1stl3/uefi-nuwa` | 独立固件仓 | 同上；当前内核CI准备不依赖创建此仓 |

上述表格保留未认证查询时的结果。用户随后明确表示三个仓库尚未创建，且“Git的所有命令都允许”；仓库是否存在不再需要猜测。发现本机`C:/Program Files/GitHub CLI/gh.exe`可用，但`gh api user --jq .login`提示尚未登录，已启动网页授权等待用户确认账号。一次性登录代码不写入仓库或报告。

## 固定输入与复现

- 本地基座：`75bc13dd34dc4e403826793739e316a264ce00dd`，不变。
- 本次查询main后固定审查：`e95b37d97875bd8b30c976fcdef44d35d9c27bf3`；不能把它描述为后续任何时刻的最新提交。
- workflow：[该提交的macos.yml](https://github.com/UniXNU/UniXNU/blob/e95b37d97875bd8b30c976fcdef44d35d9c27bf3/.github/workflows/macos.yml)，SHA-256：`ba9a1b60371aa93e1a2a6a8524bab0db876d67081a32540a210063b223c5ad81`。
- [remote-audit.json](../../reports/official-ci-plan/remote-audit.json)记录GET URL、提交、文件hash、行号摘录、子模块pin、差异和目标仓库读取结果；API内容在内存验证Git blob SHA-1，不建立上游源码树副本。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/audit-official-macos-ci.ps1 -Ref e95b37d97875bd8b30c976fcdef44d35d9c27bf3 -Owner wh1stl3
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/prepare-official-ci-candidate.py
```

以上脚本不调用Git、不dispatch CI；联网审计首次在沙箱失败后按工具要求获准只读联网重试。生成器仅在内存还原经hash核验的workflow，保存diff与检查结果。已有`local-comparison.json`与两个diff只代表75bc和缓存fb2bb的历史对比。

## 上游差异及跟进判断

API compare显示目标比75bc领先75个提交。compare最多返回300个文件，因此另取双方完整recursive tree，确认均未truncated，按路径/blob比较得到**491个变化条目**（新增/删除按路径计，非rename归并数）。完整清单在`comparison.complete_tree_delta`；不能将300文件当成完整差异。对选定文件做hash、行号摘录与可用patch审查，不宣称已逐项审完491项。

本次核验的workflow、kernel.py、baseline、feeds均不同于75bc与缓存fb2bb。相关变化：

| 部位 | 固定提交证据 | 对本仓的影响 |
| --- | --- | --- |
| archive调度 | `scripts/unixnu/kernel.py:47-68`，新增`CONFIG_XNU_BUILD_ARCHIVES`门；`83-102`先bootstrap记录、准备storage头、再构建archives | 可复用设计；不能只复制缓存fb2bb逻辑，未来nuwa配置须显式处理该开关 |
| bootstrap | 同文件`90`传`XNU_BOOTSTRAP=1`；baseline `52-56`识别该模式 | 记录存在不代表完整链接成功；旧的“调度缺失”结论仅适用于75bc |
| XNU补丁 | `patches/xnu/`新增4项、修改2项；NativePrelink改为子模块 | 现有48项静态结论仍只属于75bc输入，不能平移到该提交 |
| NativePrelink | `.gitmodules:58-60`；gitlink `kits/NativePrelink`固定`2b6ffb50117eee820b98aca9bd51b5c7dfb2970e` | tree中原两项patch显示删除是子模块边界变化，不能断言上游删掉安全初始化功能；该子模块内容尚未审查 |
| 版本/产物 | feeds `10,14`仍10063；baseline `770-771`硬编码iOS17，`778`仍消费`.unstripped.noctf` | macOS本身不能解决8796产物与目标版本错位 |
| 预链接 | `scripts/unixnu/cli.py:128-130`的kernel步骤仍无条件调用build后prelink | `steps=kernel`不是“只编译、不依赖donor”的模式；当前board没有prelink输入，不能直接运行 |

**本轮不整体跟进上游、不切feed。** 新工作流候选以固定的官方版本为审查对象；正式移植须先确定用于8796的基座输入，再针对那组输入验证补丁与构建路径。不能为了取得CI绿灯改用10063、sheng defconfig或iPad donor。

## 官方工作流实际行为

下列行号均针对上述固定版本`macos.yml`：

- `72`：`macos-latest`，没有固定Xcode；`88-105`报告部分工具并安装Homebrew工具。
- `75-82`：checkout基座与独立设备仓。`110-112`：先选defconfig，再fetch包括corecrypto-2023、IOStorageFamily等引用。
- `139-144`：`pre_build`在fetch之后执行。不能把此钩子当成“首次fetch前覆盖XNU版本”的入口。
- `146-152`：kernel构建始终执行；`154-181`按steps有条件构建userdata/payload。默认`kernel userdata`不符合本次内核范围。
- `183-201`：上传kernel/payload/log及可选userdata；原上传没有`always()`，前面失败会跳过。没有上传原始XNU内核或compile JSON的明确路径。
- `203-207`：最后清理IPSW、feeds及固件缓存。基座自身的fetch/baseline包含Git clone/apply。用户最新回复已解除Git命令限制，不再为这件事要求重复审批；只读资料库边界和四类硬停继续有效。

本轮尚未验证Actions checkout是否完整准备当前全部子模块/外部引用，也未运行Xcode、IIG或内核make。官方有工作流是可行路径证据，**不是本项目构建成功证据**。

## 已完成的候选

[official-macos-observability.patch](../../patches/base-ci-candidates/official-macos-observability.patch)仅修改官方工作流：默认kernel、固定macos-15-intel与Xcode16.4路径，检查IIG，记录实际ImageVersion/SDK/Apple clang，失败时尝试收集日志、compile JSON和已有原始内核产物。未生成诊断/固件镜像；该diff不是设备XNU补丁模块。

[candidate-check.json](../../reports/official-ci-plan/candidate-check.json)：5个hunk在内存中精确匹配，结果文本等于预期，**静态检查通过**。未执行Git apply，未安装workflow，也未执行YAML/Actions；没有QEMU或实机验证。runner固定仍不等于镜像软件永久固定，缺指定Xcode时显式失败。

选择macos-15-intel/Xcode16.4的依据：[GitHub runner说明](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)、[runner软件清单](https://raw.githubusercontent.com/actions/runner-images/main/images/macos/macos-15-Readme.md)，以及旧资料库`common/reports/xnu-compiler-ci-39471523232.json`保存的[主机编译器样例](https://github.com/wh1stl3/xnu-compiler-probe/actions/runs/39471523232)。该样例`full_kernel_built=false`，只用于选择主机，不继承旧P16/SWEET内核结论；本轮实际runner工具链未验证。

## 真正发起前的门槛

| 项 | 当前状态与所需工作 |
| --- | --- |
| 远端输入 | owner已定wh1stl3，用户确认三个仓库未创建；GitHub CLI网页登录待完成。后续需要精确device_ref，不能用本地未提交内容冒充 |
| 基座版本 | 75bc是既有48项结论的输入；官方CI新版本是e95b。先完成有范围的移植/回移设计及依赖核对，不能把491项整体更新混入本次提交 |
| 8796源构建 | 完整补丁模块、nuwa defconfig、iOS16编译/链接参数、`.unstripped`消费者仍待适配；feed保持10063不动，后续单项跟进 |
| archive/ABI | 用8796真实compile记录重建static archives，完成boot-progress回调和watchdog问题；不能导入sheng的Darwin23绑定库 |
| donor | 核验iPhone10,3/d22ap/20H392的kernelcache与预链接值，或设计明确的只编译入口；不能填假slide、roots或initializer来绕过CLI |
| 执行范围 | 用户已允许全部Git命令；仅在获准的工作位置执行，不改两个只读旧仓或上游来源树。不因Git授权自动改feed、板值或生成镜像 |
| 首轮产物 | 仅允许明确的kernel范围；userdata/payload/package/firmware/bootimg与设备动作不在本次范围。触及四类硬停时另写NEED-REVIEW后停 |

用户提出Actions并回复“继续”支持该方向，R-003 A的WSL审批历史保留，后续主机方向由D-008记录。后续已选择固定75bc做独立源内核编译入口，完整设备构建仍复用官方路线并受ABI/donor门限制。WSL工具链输入仍不齐；没有把云端路径建议写成本机内核构建通过。
