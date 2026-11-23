# Netdata 原生概览与逐接口流量验收

[v25.12.6-20261120.2](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120.2) 保留 **Netdata 2.13.0 原生 Dashboard、图表渲染器和编辑器**，通过随固件打包的模板初始化每个新浏览器。LuCI「系统 → 实时监控」默认显示 System Overview、六仪表、CPU、内存、磁盘、网络和传感器分组。

此前[原生能力验证](netdata-native-dashboard-validation-20261120.md)中“换浏览器自动读取布局”未通过；本轮补齐初始化后通过。未恢复已归档的旧版前端。先前 r4 的草稿制品没有发布，本次最终制品为 r5，包含逐接口增强。

## 网络部分

- 原生 `network-interfaces` 表格分别显示每个接口的收发速率、包速率、丢包和状态；可按名称、类型筛选和排序。接口名较长时可调整原生列宽。
- 两张原生曲线分别显示 **逐接口 RX、逐接口 TX**，按 `net.net` 的 instance 分组，不把全部接口压成一个总量。
- 物理口、网桥、VLAN、veth、隧道、bond 聚合口与成员口各自呈现。原生 Type 列区分 physical / virtual，具体接口按名称识别，不将网桥、bond、VLAN伪装成物理接口。
- 新增接口自动发现，无须重新导入布局。保留 `lo`、IFB 等默认会被跳过的接口；部分新虚拟接口存在上游 **40 秒发现延迟**，未修改采集核心来绕过该机制。
- 同一数据包会经过物理口、bond、VLAN、网桥等多层，**不能直接相加当作总流量**。

最终镜像的隔离实验在页面已经打开后创建 bond、两个 veth 成员、VLAN、WireGuard 和 IFB。表格与历史曲线自动发现全部 10 个接口；4 Mbit/s TCP 试验中，bond、VLAN 和活动成员分别采到 4.20 Mbit/s，备用成员和未发流量的接口为 0。测试后删除全部临时接口、命名空间及 iperf 进程，网络、防火墙、DHCP 配置摘要保持不变。[逐接口证据](evidence/netdata-overview-20261120/interfaces.json)。

![最终镜像：各接口实时流量](images/netdata-overview-20261120/interfaces-live.png)

![最终镜像：逐接口 RX/TX 曲线](images/netdata-overview-20261120/interfaces-curves.png)

## 实现与升级维护

[preset.json](../packages/netdata/files/overview/preset.json) 提供版本 2 模板；[bootstrap.js](../packages/netdata/files/overview/bootstrap.js) 在原生应用启动前初始化 IndexedDB，再进入本机原生 Dashboard。默认 OpenWrt 主机名对应原生 slug `openwrt`，不能直接将显示名称拼入路由。

两个空白浏览器会获得相同模板。个人修改在各浏览器独立保存，**不跨浏览器同步**。原生 Save 后的布局、主动清空的布局均保留；升级模板不会覆盖已有个人布局。未知缓存结构或禁用存储时显示恢复入口，不静默覆盖记录。

接口函数卡必须绑定当前 Agent 的节点 ID。初始化动态读取本机 ID；后续身份变化时，只重新绑定属于本模板、仍指向此前本机的函数卡，不重置个人布局或覆盖用户手动选择的其他节点。

[资源准备脚本](../packages/netdata/prepare-overview.py) 限制页面资源为本地来源，补齐原生字体的根路径；不改原生 JS 渲染代码。云、registry 等外部资源由 CSP 阻断，不影响本地图表。[资产提取脚本](../packages/netdata/extract-asset.sh) 仅解析 makeself 声明的边界，不执行上游安装器。

[概览补丁](../patches/custom-ipv4/netdata-overview.patch) 将资源打进 **Netdata 2.13.0-r5**；[LuCI 补丁](../patches/custom-ipv4/netdata-luci-bundled-dashboard.patch) 为 **0.1-r3**，统一“实时监控”标题和默认地址。接口采集设置位于 [netdata.conf](../packages/netdata/files/netdata.conf)。完整定制见[补丁索引](../patches/README.md)。

核心升级后必须重新验证原生缓存结构、路由、图表参数和函数节点绑定。[浏览器验收脚本](../scripts/check-netdata-overview.cjs)与[CI](../.github/workflows/check-netdata.yml)运行真实原生页面，等待有效采样后检查，不把 HTTP 200 当作实时图表通过。

## 最终制品

基于 OpenWrt 25.12.6 x86/64，含 469 个包。除 Netdata、LuCI 入口、概览及接口采集默认值，本轮未改变已有 DNS、终端认证或网络策略。全部包版本和内核模块 ABI 逐项匹配；`kmod-bonding` 保留。

| 制品 | SHA256 |
| --- | --- |
| EFI gzip 镜像，173922628 字节 | `c0f28710b3f6430699772bf9b8d4f9cd888e88aafd7e4d71e4f681f0982dff11` |
| 原始镜像，2164555264 字节 | `ad0e4952613fb7250480e00bf1e4129f64d4d2ad579f662bf0e862e9d32e56e8` |
| APK 清单 | `b4890cfd9ca182b4d300861842c1733208afb33845b5d512fb2e427bc2b4152e` |

189、PVE、Mac 的同一制品均校验一致。导入全新 disk-21 后，在首次启动前再次核对原始磁盘摘要一致。没有将配置过的实验盘作为发布产物。

## 最终镜像验收

9000 全新安装上述镜像，仅设置实验 LAN 和实验登录凭证。测试时 WAN 网卡断开，路由器只有实验 LAN 路由，**无默认路由**；自动化 Chrome 同时阻断非本地来源，Safari 使用实际 macOS 原生应用。

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 全新启动、自启 | 通过 | Netdata 2.13.0-r5、LuCI 0.1-r3；Netdata、ttyd 均 running |
| 离线、无云账号 | 通过 | 本地资源显示六仪表和曲线；`/api/v3/me` 为 `auth:none`、云账号 null |
| 换浏览器自动初始化 | 通过 | 两份独立 Chrome 存储布局相同；实际 Safari 首次访问自动加载概览、接口表和 RX/TX |
| LuCI 默认入口、中文标题 | 通过 | 从实时监控进入原生 Dashboard，标题为“实时监控” |
| 实时数据和逐接口图表 | 通过 | CPU/RAM/I/O/网络 API 有有限数值；10 个动态接口及实际试验流量验证 |
| 原生编辑保存 | 通过 | 修改并 Save 后重新进入保留；本机函数重新绑定不覆盖个人记录 |
| 离线重启 | 通过 | 服务自动启动；旧浏览器保留修改且接口表恢复；全新浏览器 8 项检查再次通过 |
| 存储异常 | 通过 | 未知记录保留；拒绝 IndexedDB 时显示恢复入口 |
| IPv6、实验隔离与清理 | 通过 | IPv6 禁用；桥无物理上联；9001 保持关闭；临时密钥、Agent、代理和转发均撤销 |

[首次浏览器结果](evidence/netdata-overview-20261120/browser.json)、[LuCI](evidence/netdata-overview-20261120/luci.json)、[Safari](evidence/netdata-overview-20261120/safari.json)、[重启服务](evidence/netdata-overview-20261120/reboot.json)、[重启后原浏览器](evidence/netdata-overview-20261120/reboot-browser.json)、[重启后全新浏览器](evidence/netdata-overview-20261120/reboot-browser-fresh.json)。

代码提交 bf72ec0 的[原生浏览器 CI](https://github.com/jearton/prowrt/actions/runs/44679379571)和[仓库 CI](https://github.com/jearton/prowrt/actions/runs/44679379448)通过。浏览器 CI 使用独立 Linux Agent；189 的镜像构建、PVE 全新安装与 GitHub 完整源码构建是独立证据，不混称。此前[完整源码 CI 基线](https://github.com/jearton/prowrt/actions/runs/44575439007)通过，不能将其称为本次 r5 的完整源码构建结果。

![LuCI 默认 System Overview](images/netdata-overview-20261120/luci-overview.png)

![实际 Safari 离线首次加载](images/netdata-overview-20261120/safari-overview.png)

截图补拍于离线重启验收完成、实验 WAN 链路恢复后；原浏览器仍保留个人修改。离线重启本身的服务、路由和浏览器证据见上文 JSON。

![重启后保留个人布局](images/netdata-overview-20261120/reboot-preserved.png)

## 边界与回滚

上述“通过”针对本轮 Netdata 要求。物理温度、RPM、驱动和吞吐性能未在 VM 验收；缺少传感器数据时显示“未检测到指标”，不伪造零值。LuCI 监控嵌入本轮使用 HTTP，未新增 HTTPS 适配。

既有 **Technitium DNSSEC 与默认 AliDNS DoH 对部分域名返回 SERVFAIL** 的问题尚未修复，见[扩展验收](vm-extended-validation-20261120.md)。本次不能报告全部固件功能通过。

9000 保留最终 disk-21 运行，原 disk-16 以及中间测试盘保留；异常时关机切回旧盘。物理机升级前备份配置并保留旧启动盘。浏览器个人布局可用原生编辑器导出，不删除来源不明的记录。

验收后恢复实验 WAN 链路，9001 仍关闭；13 台非目标 VM 配置摘要、宿主路由和 9001 运行配置未变。9001 的说明文字回读从注释形式变成 description 字段，运行配置比较排除该显示格式差异，没有向该 VM 执行配置写入。[隔离回读](evidence/netdata-overview-20261120/isolation.json)、[清理结果](evidence/netdata-overview-20261120/cleanup.json)。

发布交付已通过[GHCR 工作流](https://github.com/jearton/prowrt/actions/runs/44681488699)的完整附件下载、推送、按摘要拉回及 SHA256 核验；匿名发布摘要检查见[证据](evidence/netdata-overview-20261120/publication.json)。最终文档提交 8ad6dd0 的[浏览器 CI](https://github.com/jearton/prowrt/actions/runs/44680887485)与[仓库 CI](https://github.com/jearton/prowrt/actions/runs/44680887735)均通过。
