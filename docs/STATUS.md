# STATUS

更新：2026-10-25。**实机仍为PROBE18到MAC/Image4 panic(2)，未到BSD/root/iOS。v26已证伪“补AMNM属性即可”：当前dtless缓存不含该标识符。兼容候选仅模型通过，未打包或实测。**

## 当前实机与有效产物

PROBE18实机已运行首线程，PE_init_iokit返回，走过中断使能调用及commpage，停于mac_policy_initmach内AppleImage4 5.0.0的`failed to get mix-n-match policy: %d`，参数2。横纹消失，A02A=0、A02B=4、A02C=1；一次VBAR交接和使能调用不证明硬件IRQ工作。

最近设备后验仍为2026-10-25 18:19:42北京时间Android完成1/A槽/boot_a、vendor_boot_a、init_boot_a三SHA与试前一致。无人工恢复待办；不是实时查询。本轮无设备动作。

有效内核d6f101e4dfb670e7aa44cd6f51d447feb5d433e5c5883152b5a574da1a09479e，镜像c89cfa52c165562693ab0868dddeeb1225995bb5f30e3899df58a888197e8dde，ADT9846c7dadd23bf544190c45ba3db437fb83265cb180ad6c54cd3a3fedee20d93，包reports/xnu-first-entry/entry-probe-18.json。本轮绑定/回读复验与原Image4五例通过，未改包18历史。

## 当前卡点与新增证据

v26执行原生SecureDTIsLockedDown选择代码、真实chip getter/版本6缓存构建和初始化AMNM调用/panic边。原生IsLockedDown=false会选择pmap dtless；其22项描述符没有AMNM，出货ADT及合法4字节1的对象夹具均panic(2)，且缓存路线不读取该属性。缺属性仍是真实输入问题，但不足以解释或修复完整路线。该结论取代D-046中仅据SecureDT后备路线的首因排序。

104字节兼容候选仅对dtless的AMNM调用原生Darwin IOKit getter，不构造策略或吞掉错误。18项模型检查、重复编译一致与错误绕过负候选拒绝通过；其他缓存标识符和原SecureDT后备行为保持。IORegistry对象/OSData边界为显式夹具，不是实机provider读回。候选未写入内核或启动包，出货策略未选。

隔离夹具使用禁止混配值并修正路由后，真实初始化下一停点为BNCH读取panic（级别参数0、errno2）。出货manifest-properties节点存在但没有BNCH，boot-manifest-hash缺失。级别0不是nuwa实测Apple安全状态。集成源码的owner image-set摘要属于后续root/cache路径，不能当作前级Apple manifest或倒填当前字段。

下一步建立早于MAC的真实非Apple平台nonce/manifest/身份输入来源，再将兼容改动和输入一起集成新候选并绑定新包。不能补空字段、伪造fuse/摘要/可信链或跳过MAC。BSD/root、IRQ/计时器/控制器、必要驱动及用户态仍未验证，不能宣称内核完成。

## 证据与边界

- v26完整因果：[Image4 provider操作记录](operations/2026-10-25-v26-image4-runtime-provider.md)；reports/kernel-entry-probe/2026-10-25-v26/{image4-runtime-provider,execution}.json。
- v25实机证据reports/xnu-entry-probe-trial/2026-10-25-v25/；显示/向量/740差分等既有离线回归见reports/kernel-entry-probe/2026-10-25-v25/及[操作记录](operations/2026-10-25-v25-first-thread-display.md)。模型OSKext bzero异常不是实机卡点。
- [主线交接](operations/2026-10-25-mainline-handoff.md)固定有效包与续接命令。保持TCR、板值、内存/身份、只读资料库、loadable=false/runtime_qualified=false和媒体仅本地。
- 未push、未触发新CI。本轮仅模型候选与审计，不重复启动包18。
