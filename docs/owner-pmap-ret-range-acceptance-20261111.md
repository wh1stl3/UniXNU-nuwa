# 冻结PMAP候选：范围更正链与最终独立静态验收

2026-11-11，**主控接受最终独立静态范围PASS；本次文档/metadata修改self-checked**。
设备HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a`；仅记录现存独立证据，
不重跑Capstone/范围audit/包装/矩阵，不更改冻结二进制或历史JSON。

## 证据阶段，不能混淆

根 `out/pmap-ret-memory-ranges-verifier-20261111/`：

1. `result.json`：最初实际artifact/相对区间，nonoverlap=true、absolute_W_observed=false。
   该阶段主控交付的FAIL针对前review错误的__BOOTDATA引用，不证明实际内存冲突。
   原FAIL及旧证据保留，**其当前FAIL结论已撤回**，不传播错误区间。
2. `correction.json`：status=`partial-verification`，纠正segment/section及栈符号/相对区间。
   其not_verified中仍记早期Capstone SyntaxError，属于当时快照，不是最终缺项。
3. `native-flow/result.json`：status=`static-increment-pass`，列A–E全部PASS及10份短解码证据。
   known_prior_tool_failure明确先前llvm-objdump参数/Capstone调用问题之后已纠正。
   主控确认短Capstone实际exit0；该JSON自身不保存完整command/cwd/exit，不能倒填不存在的字段。

最终PASS是更正边界+后续native-flow+明确复用的先前事实共同支撑，
不是把partial标签或旧FAIL文件修改为PASS，也不是本轮再次执行的结果。

## 正确范围及间隔

冻结kernel SHA256 `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`：

| 对象 | 独立核对的区间/值 |
|---|---|
| __BOOTDATA segment | VA `[0xfffffff007ac0000,0xfffffff007b08000)`，vmsize `0x48000` |
| 其中__data section | VA `[0xfffffff007af0000,0xfffffff007b08000)`，size `0x18000` |
| segment相对W | `[0x3cf8000,0x3d40000)` |
| Args | `[0x43f0000,0x43f1000)` |
| ADT | `[0x43f1000,0x43f43c8)` |
| Trust | `[0x43f5000,0x44052e0)` |
| Top | `0x4408000` |
| __BOOTDATA终点至Args间隔 | `0x6b0000` |

correction中的stack symbols包含intstack guard/stack/top、excepstack/top/high guard；
它们属于正确section范围，不能把其中一个stack符号误当整个segment vmaddr。
W_relative_ranges_disjoint=true，纠正后的回收segment与Args/ADT/Trust/Top无重叠。
合法W下的静态判定不以先测live W/SP为前置，但不能反向声称实际W/SP已观测。

## A–E最小证据闭合

| 检查 | native-flow/result.json实际判读 |
|---|---|
| A getter | LDR segment+0x20取vmsize写size输出，LDR segment+0x18返回vmaddr；不是section start |
| B BOOTDATA free | getter输出对应_segBOOTDATAB/_segSizeBOOTDATA；free x0为segmentVA−gVirtBase+gPhysBase、x1为size；先alloc/换栈/free BL顺序沿用先前已独立验证事实，不冒称本轮重做整链 |
| C PLK gap | 已核对MH_EXECUTE及两个非零PLK size；OR及条件branch使旧gap free路径不走；复用size为PLK_DATA_CONST `0x3a4000`、PLK_TEXT_EXEC `0x16d4000` |
| D Top/avail | arm_vm_init把boot_args输入保存在x23，读+0x20到avail_start；page shift/mask对齐及first_avail store实际解码 |
| E pmap页游标 | 输出页号按page shift移位，next cursor增加1<<shift |

对应证据文件：A-getsegdata、B-bootdata-get/B-bootdata-free-args、
C-plk-getters/C-plk-free-condition、D-top-avail/D-first-avail-inputs/
D-avail-reg-source/D-avail-fn-entry、E-pmap-next-page，均在native-flow/下。
这是固定host-image静态数据流验收，不扩展为任意kernel/所有固件所有权证明。

## 当前主机候选与剩余门禁

范围、冻结profile及[外层包装](owner-vendor-boot-20261111.md)的独立主机验收已完成，
原FAIL/pending快照不再作为当前阻塞。保留GOP/EFI map契约条件；
实时W/SP/GOP、当轮真实EFI map及回收运行期仍未测，不称runtime/认证/stage5/设备通过。
当前**无设备授权**，另reviewer准备操作方案；待用户当轮明确授权及设备身份/槽位等门禁，
本任务不发起授权、不枚举/查询/操作设备。主机候选验收完成不等于已设备ready实测。

外层helper的range_static_review仅未来记录措辞改为稳定“本包装器不验证范围，见独立证据”，
不硬编码动态pending/PASS。历史outer-record.json仍保留创建时pending文本，
这不是当前状态，也不因文档更新被重写；冻结镜像与签名/hash绑定完全不动。

## 本次metadata/文档自检

本次Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`，WSL Ubuntu-22.04/root cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`。Python3.11 `-B -c`只读AST核对唯一稳定范围字段、
核对历史JSON仍保留pending快照，并py_compile该helper到新ignored目录
`out/owner-vendor-boot-close-20261111/`，实际exit0；未导入/执行包装器。
另一次只读Python命令核对三份owner说明/README的当前引用与correction→native-flow分阶段状态，
实际exit0，摘要 `out/owner-vendor-boot-close-20261111/metadata-checks.json`。
首次合并shell检查调用exit1且无输出，其预定新输出目录不存在，未将其计为任何检查通过；
随后拆分显式单行调用得到上述真实结果，不推测无日志失败的根因，没有重包或重复矩阵。

```powershell
# 本轮实际exit0：14 structured areas checked
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
# 本轮实际exit0
git diff --check
```

未跟踪文件另用 `git diff --no-index --check -- NUL <file>` 检查，exit1且零输出仅为新文件差异码。
独立verifier若复核本次唯一metadata行，仅需语法/状态引用/record/diff；不因文字整改重跑已验包装。
