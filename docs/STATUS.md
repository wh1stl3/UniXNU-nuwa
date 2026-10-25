# STATUS

更新：2026-10-25。PROBE26照片03259a98已确认第二次exec到文件头读取：240至249调用/后继均亮，250 vn_rdwr调用亮、251后继暗，252之后Mach-O/dyld未亮。A02C2；保留的A02E=0xF2/242、A0322及A02D/A0302可来自前一次开发路径失败，不能解释为当前读取返回ENOENT。当前首要调查是文件头读取未见返回。Android1/A槽/三SHA后验已完成（v34/postcondition），无待恢复，不重复启动26。只读审计v35/exec-compression.json确认launchd/dyld均decmpfs type4；预链接含Zlib不等于已注册，正在核对正常组件初始化。按用户决定保持当前基线、不做全量上游迁移，继续主线且保留硬停。

最近包26镜像9906e2b7、内核d7f125b5、ADT4e455229，代码5263bbb/启动7153e06。21项串行验证及回读通过；实机仍未到Mach-O/签名/用户态。详见v34操作记录及screen/recovery/postcondition。

下一步核对压缩文件读取等待与type4解压器注册，拟通过正常OSKext生命周期补齐已有Zlib组件初始化，真实状态/错误保留，不写假表或绕过检查、不新增阶段终点。源码依据decmpfs.c:206–259及register_decmpfs_decompressor，主机只读压缩属性仅证明格式，不证明实机等待位置。内核数据注册指针仍待实测。

保留FD/shim/内存表/TCR/iOS16/8796身份和*_verified，loadable/runtime_qualified=false；无flash/erase/改槽、push/新CI、原始媒体上传。fastboot查询缺失变量记录后重进一次不单独硬停；具体目标/日志/恢复门保持，人工等待继续离线工作。
