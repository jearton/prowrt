# 实时信息连接页：大列表引起 rpcd 重启和退出登录

本项针对「状态 → 实时信息 → 连接」，与 OpenClash 的 Zashboard 连接页无关。固件准备脚本锁定 LuCI `75a306df84a020c57a631ef5b4c02ace56d93387`，生成 `luci-base`、`luci-mod-status` 的 `26.288.56989~75a306d-r2` 修订。已随 `25.12.6-20261126.1` 发布，[完整镜像验收](acceptance-20261127.md)与文件级候选分别记录。

## 已复现的根因

- 原页每 3 秒通过 UBUS 的 `luci.getConntrackList` 请求整张连接表并渲染。
- 在隔离 VM 的原页建立 2500 条真实 TCP 连接时可以显示；5000 条时表格停在收集中、rpcd PID 变化，uhttpd PID 不变、静态 HTTP 仍返回 200。
- rpcd 重启丢失内存中的 LuCI 会话；同一个原 Cookie 再访问受保护页面返回 403 和登录要求，Mac Chrome 显示登录页。
- 同版本 libubox 实际编码 5000 条记录为 1,180,020 字节，超过 UBUS 的 1,048,576 字节上限。UBUS 服务端拒绝过大消息并断开提供方，rpcd 随后退出并被 procd 拉起。
- 这是有记录的上游问题：[OpenWrt #9747](https://github.com/openwrt/openwrt/issues/9747)、[LuCI #4816](https://github.com/openwrt/luci/issues/4816)。不能据此将所有历史网页故障归因于该路径。

## 调整清单

1. 使用 LuCI 原生 `fs.read_direct`，从已认证 HTTP 下载 `/proc/net/nf_conntrack`，避免将完整列表塞入 UBUS。
2. 给实时信息 ACL 精确增加该文件、`/etc/protocols` 的只读权限和 `cgi-io.download`；保留认证，不开放匿名下载。
3. 浏览器解析完整快照，先对全部结果筛选和数值排序，再每页显示 100 条；可以翻页，不截断为前 100 条。
4. 小型连接曲线保持 3 秒更新；完整列表改为 10 秒并且不重叠请求。手工刷新复用进行中的请求，失败明确显示错误。
5. 旧 `getConntrackList` 限制最多 1000 条和保守 512 KiB blob 预算，达到限制即停止解析、返回 `UBUS_STATUS_NOT_SUPPORTED=8` 及说明。它不是权限错误，不伪装成登录过期，不静默返回不完整列表。
6. 为连接解析回调增加显式返回 `false` 时停止的能力，其他原调用的语义保持。
7. 使用独立资源名 `status/connections_prowrt_v1` 与 `tools/prowrt_conntrack_v1`；原菜单 URL 不变，避免旧浏览器继续复用原连接页脚本。
8. 构建前验证上游源文件、配方与补丁摘要；输入变化时停止，要求重新审查。同步严格包清单的 r2 期望，不放宽其他版本检查。

本固件内核启用了 conntrack procfs。本实现不声称适用于没有 `/proc/net/nf_conntrack` 的任意 OpenWrt 内核；读取失败会显示错误。没有新增后台 API、常驻采集进程或自动重启任务。

## 实现与文件级更新

- [页面](../packages/luci-connections/connections.js)、[解析和全表分页](../packages/luci-connections/conntrack.js)
- [旧 API 防护](../packages/luci-connections/legacy-guard.patch)、[精确替换块](../packages/luci-connections/legacy-blocks.json)
- [源文件锁](../packages/luci-connections/series.json)、[固件准备](../scripts/prepare-luci-connections.py)
- [维护主机合并工具](../packages/luci-connections/apply-files.py)、[来源与保留检查](../scripts/check-luci-connections.py)

`apply-files.py` 在维护主机对路由器备份文件的暂存目录执行；路由器不需要 Python。先用 `--check` 审核，再生成变更，并按输出的前后 SHA256 核对安装。精确变更 6 个路径：

- 更新 `/usr/share/ucode/luci/sys.uc` 中的目标回调块。
- 更新 `/usr/share/rpcd/ucode/luci` 的 `getConntrackList` 方法。
- 更新 `/usr/share/luci/menu.d/luci-mod-status.json` 中连接页的 action，保留其他菜单，包括现场 RSS 进程页。
- 扩充 `/usr/share/rpcd/acl.d/luci-mod-status.json` 的实时信息只读 ACL，保留其他 ACL。
- 新增 `/www/luci-static/resources/view/status/connections_prowrt_v1.js`。
- 新增 `/www/luci-static/resources/tools/prowrt_conntrack_v1.js`。

目标块已经被其他方案修改时停止；不能整份复制旧 RPC 后台或菜单来覆盖现场改动。应用前备份这 6 个路径及其存在状态，核对原包和文件哈希；写后核对新哈希，导入 `luci.sys` 检查模块语法，编译检查 RPC 文件，再执行一次 `rpcd reload` 加载新 ACL 与方法，重新打开连接页验收。无需重启整机、代理或 DNS。

回滚恢复备份的 4 个旧文件，删除仅本次新建的两个资源，执行 `rpcd reload`，重新打开页面。恢复旧页后不要再次用过大的列表触发已复现故障。包版本号在文件级补丁后保持原值，不能用包版本证明热修已生效；应核对文件摘要和实际请求路径。

## 验证状态

- 源码锁定整合、精确合并、RSS 其它改动保留、幂等和目标块变化拒绝：通过。
- 解析单元验证含 IPv4/NAT、双向计数、IPv6、TIME_WAIT、全表数值排序及 10000 条完整分页：通过。
- Mac Chrome 100 条真实 TCP 连接：HTTP 读取、100 行分页、下一页、全表筛选、排序和登录保持通过。
- Mac Chrome 5000／10000 条真实 TCP 连接：完整解析 5008／10005 条，含管理连接；每页 100 条，下一页、筛选找齐所有测试连接、数值排序通过。
- 两次 rpcd PID 均保持不变，原登录 Cookie 继续访问受保护页面成功；主线程最长任务分别 52／94 ms，无页面脚本错误。
- 旧接口超限返回 UBUS 状态 8；没有认证错误，原登录保持。
- 匿名 HTTP 文件读取返回 403；模拟 503 后显示明确错误，再次读取正常后恢复；重复刷新最多 1 个列表请求。
- [文件级候选验收数据与截图](evidence/luci-connections-20261127/file-level-acceptance.json)已经保留。此轮在已发布镜像的保留测试盘应用文件补丁，不冒充新完整镜像验收。
- 完整镜像 CI、新盘安装、5000／10000 条连接及公开下载验收均通过，源码与原始镜像一致；[完整结果](acceptance-20261127.md)。
