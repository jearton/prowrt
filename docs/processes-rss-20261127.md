# 进程页：RSS、CPU 增量与数值排序

这是通用固件对已验证现场实现的整合，属于尚未发布的 `luci-mod-status` r2 候选；旧正式镜像不会自动增加本功能。菜单仍为「状态 → 进程」，URL 仍为 `/cgi-bin/luci/admin/status/processes`。

## 调整清单

1. 读取 `/proc/PID/status` 的 `VmRSS`，显示 RSS MiB 和 RSS / `MemTotal` 百分比；百分比保留一位小数。RSS 包含共享驻留页，不能把所有进程的 RSS 相加当作整机已用内存。
2. CPU 使用进程 `utime + stime` 的两次采样增量，除以 `/proc/stat` 前 8 项的整机总时间增量；不重复累加 guest 时间。整机总算力为 100%，不是每个核各计 100%。
3. 使用 PID + starttime 区分进程身份；首次、新进程、PID 复用或计数回退显示“—”，等待下一次有效采样。
4. 读取进程后再次核对 starttime，跳过已退出或读取期间被复用的 PID；内核线程无 VmRSS 时按 0 处理。
5. 页面打开时每 5 秒刷新，重复调用合并为一个进行中的请求；失败明确提示并保留上次数据，恢复后继续更新。没有新增服务、cron 或持久采样缓存。
6. 默认按 CPU 降序；CPU、内存表头按原始数值切换升降序，自动刷新保持本页当前选择。自行更新表体，避免 UITable 按显示字符串再次排序。
7. 保留挂起、终止、强制终止操作，继续使用原 `/bin/kill` 和既有写权限。只读会话按钮禁用，后端文件执行权限没有放宽。
8. 新数据路由 `/cgi-bin/luci/admin/status/prowrt_processes` 只接受已认证 GET，复用 `luci-mod-status-processes` 的 `luci.getProcessList` 读取权限；不新增账号和 ACL 权限。HTTP／HTTPS 分别读取对应 Cookie，兼容旧 `sysauth`，响应禁止缓存。
9. 使用通用 `prowrt` 模块和资源名，不含现场地址、网络接口、账号或绑定源 IP。菜单只更改进程 action，保留 PR19 的连接页 action，原 `status/processes.js` 仍保留。
10. 构建前核对源文件和配方摘要；整合到原生 `luci-mod-status`，显式声明 Lua runtime 和 nixio 依赖。这些依赖已在本固件原清单中，无需新增常驻组件。

## 实现文件

- [采样模块](../packages/prowrt-processes/metrics.lua) → `/usr/lib/lua/luci/prowrt_process_metrics.lua`
- [认证只读控制器](../packages/prowrt-processes/controller.lua) → `/usr/lib/lua/luci/controller/prowrt_processes.lua`
- [进程页面](../packages/prowrt-processes/processes.js) → `/www/luci-static/resources/view/status/prowrt-processes-v1.js`
- [来源与文件锁](../packages/prowrt-processes/series.json)、[构建整合](../scripts/prepare-prowrt-processes.py)

整合顺序为先应用连接页修复，再应用进程页；源菜单或配方不符合已审查输入时停止。没有复制整份现场菜单或 RPC 后台覆盖固件，也没有修改生产设备。

## 已完成的相关验证

- Lua 固定样例：带括号进程名、RSS 和比例、内核线程、已退出／复用 PID、CPU 总量排除重复 guest 计数。
- JavaScript：CPU 增量、数值升降序、缺样本／计数回退、只读信号保护、单并发刷新、失败保留旧结果。
- 隔离 VM 和 Mac Chrome：实际 RSS 比例、实际 CPU 增量、一位小数、5 秒更新、CPU／内存双向排序及刷新后保持选择。
- 匿名和注销后拒绝；授权读取成功、未授权读取 403，只读会话的信号按钮禁用；POST 返回 405。
- 同时存在相反协议的无效 Cookie 时，HTTP 和 HTTPS 均能使用自己的有效会话读取。
- 模拟 HTTP 503 后保留表格并显示错误，移除错误后自动恢复；连接页仍能读取数据和显示分页。
- 原进程资源保留，测试未向业务进程发送信号，没有新增服务或重启 DNS／代理。

上述是文件级候选验收，完整 CI 镜像仍须重新构建和新盘验收；不能将现场版本或候选盘结果等同于新完整镜像已发布。对应脱敏证据位于 `docs/evidence/processes-rss-20261127/`。

## 升级和回滚

此功能随本固件的原生状态包维护。独立复制三个文件不会自动调整旧版本菜单；普通上游 LuCI 包也不包含这些改动，不应整份安装旧包来恢复某个现场页面。

固件整合没有改变 UCI 业务配置。回滚固件时使用已保留的旧磁盘／原始镜像；文件级实验回滚时恢复原菜单，移除本次新增的三个文件，清理 LuCI 路由索引缓存后重新打开页面。应先核对后续改动，不能用旧整份菜单或 RPC 文件覆盖较新的连接页修复。
