# ProWrt

ProWrt 是基于 OpenWrt 25.12.6 x86/64 的 IPv4 路由器定制固件。使用 APK，内置 LuCI、实时监控和原生 Technitium DNS。默认禁用 IPv6，镜像验收使用独立实验 LAN。AdGuard Home 随镜像提供，默认停用。

**[下载最新固件](https://github.com/jearton/prowrt/releases/latest)**：在发布页的 Assets 中下载 x86/64 UEFI 镜像和 `SHA256SUMS`，写盘前先校验。具体变更及适用范围以所选版本的发布说明为准。

**验收记录**：[v25.12.6-20261126](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261126) 完整编译通过 483 包版本、内核 ABI、权限和身份校验；[同镜像独立 CI 复验](https://github.com/jearton/prowrt/actions/runs/45707970121)及 PVE 新盘安装后的 Mac Chrome 检查通过。首次 CI 的终端重连中断及具体范围见[本版验收记录](docs/acceptance-20261126.md)。物理网口映射和硬件驱动仍需在目标设备验证。

**升级注意**：先备份配置和数据，保留旧启动盘或镜像。升级不会覆盖已初始化的 Technitium 设置；启用 OpenClash DNS 联动后，停止 OpenClash 不会自动恢复主 DNS 的公网上游，未缓存的公网域名可能暂时无法解析。

自 v25.12.6-20261124.3 起包含 Zashboard 3.30.0、MetaCubeXD 1.276.0，保留 Mihomo 1.19.34，见[面板打包与验收记录](docs/openclash-dashboards-20261124.md)。

历史记录：[v25.12.6-20261120.2](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120.2) 的 [Netdata 镜像验收](docs/netdata-overview-acceptance-20261120.md)、[登录与终端基线](docs/acceptance-20261120.md)及[扩展验收](docs/vm-extended-validation-20261120.md)仍可查阅。该版本在 AliDNS DoH 配合 Technitium DNSSEC 校验时曾出现部分公网域名 `SERVFAIL`。v25.12.6-20261124.3 调整了首启默认值，不能据此认定原问题已修复；另见[发布前的 VM 验收](docs/vm-validation-20261123.md)和[补丁清单](patches/README.md)。

项目仓库已由 `jearton/openwrt-pro` 更名为 [`jearton/prowrt`](https://github.com/jearton/prowrt)。历史 Release、版本标签和固件附件保留；GHCR 统一使用 `ghcr.io/jearton/prowrt`，仅发布定制固件，正式版与 CI 候选通过版本 tag 区分。通用插件 [`luci-app-technitium`](https://github.com/jearton/luci-app-technitium) 保持独立。迁移范围与校验见[改名记录](docs/prowrt-rename-20261123.md)和 [GHCR 路径调整](docs/ghcr-root-20261123.md)。

## 功能清单

### OpenWrt 原生功能

| 菜单或入口 | 功能 |
| --- | --- |
| 状态 | 系统与接口概览、路由表、防火墙规则、系统日志和进程 |
| 系统 | 系统设置、账号密码、Dropbear SSH、启动项、计划任务、挂载点、备份恢复、固件升级、重启和 APK 软件包管理 |
| 网络 → 接口 | 有线 WAN/LAN、静态地址、DHCP 客户端、PPPoE、桥接、VLAN 和静态路由 |
| 网络 → DHCP/DNS | dnsmasq-full 提供 IPv4 DHCP、静态租约和本地设备名解析 |
| 网络 → 防火墙 | firewall4 / nftables 分区、NAT、端口转发、流量规则和软件流量卸载 |

原生功能来自 [OpenWrt](https://github.com/openwrt/openwrt) 和 [LuCI](https://github.com/openwrt/luci)。下表所列为本镜像额外集成的功能和对原有界面的定制，其中也包括从官方 feeds 选入的附加包。

### 定制集成

| LuCI 菜单或入口 | 功能 | 开源来源 |
| --- | --- | --- |
| 首页、网络向导、iStore | 仪表盘、网络向导、应用入口 | [Quickstart](https://github.com/istoreos/quickstart)、[iStore](https://github.com/linkease/istore) |
| 登录页、系统 → Argon 主题设置 | 中文主题设置、登录壁纸和菜单样式 | [Argon](https://github.com/jerrykuku/luci-theme-argon) |
| 系统 → 实时监控、状态 → 统计 | CPU、内存、网口、cgroup 流量和系统历史图表 | [Netdata](https://github.com/netdata/netdata)、[Netdata LuCI 入口](https://github.com/immortalwrt/luci/tree/6dafdfc6a918044f3d4beea816076b6c82c19919/applications/luci-app-netdata)、[collectd](https://github.com/collectd/collectd) |
| 系统 → 终端、Web 管理 | 受限 Web 终端和 uHTTPd 管理 | [ttyd](https://github.com/tsl0922/ttyd)、[LuCI uHTTPd](https://github.com/openwrt/luci/tree/75a306df84a020c57a631ef5b4c02ace56d93387/applications/luci-app-uhttpd) |
| 系统 → 文件管理、文件传输 | 管理和传输路由器文件 | [LuCI File Manager](https://github.com/openwrt/luci/tree/75a306df84a020c57a631ef5b4c02ace56d93387/applications/luci-app-filemanager)、[Lean LuCI](https://github.com/coolsnowwolf/luci/tree/f43c53a60f11f5d635b7127c775e9c04e2be191d) |
| 系统 → 磁盘管理、分区扩容 | 查看本机磁盘和调整分区 | [DiskMan](https://github.com/sbwml/luci-app-diskman)、[PartExp](https://github.com/sirpdboy/luci-app-partexp) |
| 系统维护 | 定时重启、关机、释放内存、自定义命令 | [Lean LuCI](https://github.com/coolsnowwolf/luci/tree/f43c53a60f11f5d635b7127c775e9c04e2be191d)、[PoweroffDevice](https://github.com/sirpdboy/luci-app-poweroffdevice)、[LuCI Commands](https://github.com/openwrt/luci/tree/75a306df84a020c57a631ef5b4c02ace56d93387/applications/luci-app-commands) |
| 服务 → Technitium DNS | 主 DNS、内网域、广告过滤和 DNS 统计；固件默认接管 LAN 的 TCP/UDP 53 请求 | [Technitium DNS Server](https://github.com/TechnitiumSoftware/DnsServer)、[technitium-console](https://github.com/byGarcia/technitium-console)、[LuCI 插件](https://github.com/jearton/luci-app-technitium) |
| 服务 → AdGuard Home | 可选 DNS 过滤服务，默认停用 | [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) |
| 服务 → OpenClash | Mihomo 代理和规则分流 | [OpenClash](https://github.com/vernesong/OpenClash)、[Mihomo](https://github.com/MetaCubeX/mihomo) |
| 服务 → DDNS-GO | 动态域名更新 | [DDNS-GO](https://github.com/jeessy2/ddns-go)、[LuCI 插件](https://github.com/sirpdboy/luci-app-ddns-go) |
| 服务 → OAF 行为管理 | 应用识别和访问控制 | [OpenAppFilter](https://github.com/destan19/OpenAppFilter) |
| VPN、网络 → 接口 | Tailscale 管理及 WireGuard 接口支持 | [Tailscale](https://github.com/tailscale/tailscale)、[LuCI Tailscale](https://github.com/jearton/luci-app-tailscale)、[WireGuard Tools](https://git.zx2c4.com/wireguard-tools/) |
| 网络 → 负载均衡、定时限速、SQM | 多 WAN 策略、按规则限速、队列管理 | [mwan3 nftables 版本](https://github.com/dl12345/mwan3)、[Lean LuCI](https://github.com/coolsnowwolf/luci/tree/f43c53a60f11f5d635b7127c775e9c04e2be191d)、[EQoS Plus](https://github.com/sirpdboy/luci-app-eqosplus)、[SQM](https://github.com/tohojo/sqm-scripts) |
| 服务 → 带宽监控；网络 → 网速测试、IP/MAC 绑定 | 客户端和接口计量、测速、静态邻居 | [nlbwmon](https://github.com/jow-/nlbwmon)、[vnStat 配方](https://github.com/openwrt/packages/tree/093d551675b1119a06ef224d419905e8d6b2af1a/net/vnstat2)、[网速测试 LuCI](https://github.com/muink/luci-app-netspeedtest)、[iperf3](https://github.com/esnet/iperf)、[LibreSpeed](https://github.com/librespeed/speedtest-go)、[Lean LuCI](https://github.com/coolsnowwolf/luci/tree/f43c53a60f11f5d635b7127c775e9c04e2be191d) |
| 网络 → DHCP/DNS、Macvlan | 定制快捷页面，沿用 OpenWrt 原生配置接口 | [本项目菜单和页面](image-files/network-ui)、[netifd](https://git.openwrt.org/project/netifd.git) |
| 网络 → 接口 | 完整版构建启用以太网链路聚合驱动 `kmod-bonding` | [OpenWrt bonding 配方](https://github.com/openwrt/openwrt/blob/v25.12.6/package/kernel/linux/modules/netsupport.mk) |

原生 DNS 菜单和部署步骤见 [Technitium 使用文档](docs/technitium.md)。实际包版本以对应构建随附的 APK 清单为准。

### 首页功能集成（25.12.6-20261126）

以下调整已纳入本版完整镜像，并完成同镜像 CI、PVE 全新安装及 Mac Chrome 验收；**历史发布 `25.12.6-20261124.3` 不包含这些新增项**。

- **FastNet 0.8.10**：首页“网络测速”直接打开内置 LuCI 页面，不再弹出安装提示；来源为 [iStoreOS app hub](https://github.com/istoreos/istoreos-app-hub/tree/ed25f14656254b63f6adee57584742a6ccbfca04/apps/fastnet)，版本与 SHA256 见 [锁文件](fastnet.lock.json)。
- **FastNet 访问范围**：移除官方安装脚本自动创建的 WAN TCP 3200 放行规则；不删除用户已有防火墙规则。
- **家长控制**：删除首页卡片，保留 OAF 的原生服务入口和已有配置。
- **浮动网关**：隐藏设备管理“全局设置”中的页签，不安装 floatip。
- **限速入口**：全局设置的 IP 限速、限速设备列表及对应快捷操作统一打开现有“网络 → 定时限速（EQoS）”，不再检查 `app-meta-eqos` 是否安装；不自动启用限速。
- **SNMP 设备发现**：保留只读设备列表、首页发现数量及已有名称缓存；随包提供可配置采集器，默认不配置交换机、不启用采集，不带任何现场地址或凭据。升级保留旧采集器，避免重复轮询。
- **原有测速工具**：继续保留 `luci-app-netspeedtest`。FastNet 当前界面含“5 次体验／论坛激活”提示，不承诺无限免费设备测速。

具体版本、验收边界、配置保留和回滚见 [FastNet 与首页维护说明](docs/quickstart-fastnet-20261126.md)。

现场新增的同源流量速率／排序和逐 IP 默认固定限速留待下一版。本版升级会替换相关包文件，仅保留 UCI 不能保留现场包文件补丁；依赖这些能力的生产系统先使用独立测试磁盘验证。

### 本项目的补丁和调整

以下分别列出源码补丁、随包页面和固件默认配置；不是每项都通过 `.patch` 文件实现。

#### Web 服务、连接页与进程页候选更新

- **uhttpd 权限等待**：异步检查权限并单独限制为 5 秒，保留拒绝和超时保护；[机制、验收与边界](docs/uhttpd-acl-block-20261126.md)。
- **连接页大列表**：使用已认证 HTTP 读取完整连接表，全表筛选／排序后每页 100 条；旧 UBUS 接口超限明确拒绝，避免 rpcd 重启导致掉线；[实现、验证与回滚](docs/luci-connections-20261127.md)。
- **进程页 RSS 与排序**：显示实际驻留内存和一位小数，按整机总算力计算 CPU 增量，5 秒刷新、数值升降序，保留原权限与信号操作；[实现与验收](docs/processes-rss-20261127.md)。
- **发布状态**：本组改动尚未发布新完整镜像，不能将候选文件验收写成固件已发布。

#### 三层统计与设备列表

- **nlbwmon 后台**：查不到终端 MAC 时立即按 IP 记账，使用固定容量的短期失败缓存，避免逐连接等待造成队列溢出；保留实际观测增量和原数据库格式。
- **流量统计界面**：未知 MAC 按 IP 分开显示，已知设备仍按真实 MAC 汇总；详见[验证与回滚](docs/nlbwmon-routed-hosts-20261124.md)。
- **QuickStart 空列表**：兼容已验证的空 ARP 返回错误，真实接口／服务错误明确显示。
- **QuickStart 多接口**：可通过 UCI 选择发现接口；多接口列表只读，不扫描、不伪造跨三层 MAC；详见[使用说明](docs/quickstart-devices-20261124.md)。
- **交付状态**：首次集成版为 [`25.12.6-20261124.3`](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261124.3)，本版继续保留这些修复；完整镜像及匿名下载验收见[发布记录](docs/releases.md)。

#### Netdata 实时监控

- **网卡采集器**：补入 `cgroup-network` 及配套脚本，用于采集容器网络接口。
- **配置读取权限**：修正 Netdata 配置文件权限，使服务运行用户可以读取。
- **菜单和标题**：将菜单名称与页面标题统一为“实时监控”。
- **默认概览**：LuCI 默认进入新版原生 Dashboard 的 System Overview，预置六仪表及 CPU、内存、磁盘、网络、传感器分组。
- **新浏览器初始化**：从固件内置模板初始化原生 Dashboard，无需云账号、联网或手工导入布局。
- **个人布局保留**：保留原生编辑器保存的布局，包括主动清空的布局；不同浏览器的个人修改独立保存。
- **存储异常回退**：浏览器禁止存储或遇到未知缓存格式时显示恢复入口，保留已有记录。
- **逐接口实时表格**：分别展示物理口、网桥、VLAN、虚拟接口、bond 聚合口和成员口的实时收发、包速率、丢包及状态。
- **逐接口历史曲线**：按接口分别绘制 RX、TX 曲线，新增接口自动发现；不将不同网络层的重复流量相加。
- **接口采集范围**：保留 `lo`、IFB 等默认会被跳过的接口。
- **本机节点绑定**：Agent 身份变化时更新预置接口函数卡的本机绑定，保留个人布局。
- **本地资源**：通过 CSP 限制页面资源来源，并补齐随包字体路径，支持离线显示。

实现文件和兼容性边界见 [Netdata 概览验收](docs/netdata-overview-acceptance-20261120.md)。

#### 网页终端

- **LuCI 会话校验**：进入 ttyd 前校验管理员登录态和访问权限。
- **WebSocket 来源校验**：检查终端连接的 Origin。
- **系统账号认证**：每次打开终端都要求输入系统用户名和密码，不自动登录 shell。
- **空密码限制**：拒绝空密码账号进入网页终端。
- **证书适配**：兼容 LuCI 使用的 DER、PEM 证书格式。
- **Chrome HTTPS 兼容**：LuCI TLS 终端监听只协商 HTTP/1.1，避开 HTTP/2 WebSocket 的 Origin 误拒绝。
- **入口协议适配**：LuCI 终端入口复用当前协议、主机和会话路径。
- **终端高度**：按窗口剩余高度展开输入区域，减少底部留白。

实现文件见 [ttyd 补丁](patches/custom-ipv4/ttyd-luci-session.patch)和 [LuCI 终端页面](image-files/network-ui/www/luci-static/resources/view/ttyd/term.js)。

#### LuCI、主题和首页

- **文件管理布局**：调整路径栏、按钮、标签和表格宽度，改善窄窗口及权限、修改时间列的显示。
- **防火墙告警识别**：区分 iptables 的 nftables 后端与真正的 legacy 规则，避免将前者误报为旧版规则。
- **DHCP/DNS 快捷页面**：增加沿用 OpenWrt 原生配置接口的快捷入口。
- **Macvlan 快捷页面**：增加沿用 netifd 的接口配置入口。
- **菜单布局和翻译**：通过菜单覆盖文件及中文翻译调整入口、名称和排序，参考杭州办公室的布局。
- **默认主题**：首启选用 Argon，并设置 Bing 在线壁纸来源。
- **首页存储卡片**：隐藏 Quickstart 的存储服务卡片。
- **首页下载卡片**：隐藏 Quickstart 的下载服务卡片。
- **首页远程域名卡片**：隐藏 Quickstart 的远程域名卡片。

实现文件见 [LuCI 补丁](patches/README.md)、[菜单和页面覆盖](image-files/network-ui)及[首启配置](sources/full/files/etc/uci-defaults/92-custom-ipv4)。

#### DNS 和固件默认行为

- **IPv6**：通过启动参数 `ipv6.disable=1` 默认禁用。
- **Netdata 自启**：默认随系统启动，并提供 LAN 访问入口。
- **ttyd 自启**：默认随系统启动，并限制为 LAN 管理入口。
- **Technitium 原生集成**：固定独立项目的源码提交，集成 DNS Server、Console、.NET 运行时及 LuCI 管理页面。
- **主 DNS**：首启启用 Technitium，监听 IPv4 53 端口。
- **默认上游**：自 `v25.12.6-20261124.3` 起，新装首启使用 AliDNS 与 360 DoT，使用证书校验和固定引导 IP。
- **并行查询**：首启启用 concurrent forwarding，并发数为 2；缓存未命中时同时请求两个公网上游。
- **DNSSEC 默认值**：本固件首启设置为关闭；原生 Console 的 Settings → General → DNSSEC 可以自行开启。通用后台包默认值不变。
- **升级保留 DNS 设置**：已完成初始化的安装不会因升级而覆盖管理员的 DNSSEC、上游及并发设置；需要使用新默认值时在原生 Console 手动调整。
- **广告过滤默认值**：首启启用 Technitium blocking，并使用 NXDOMAIN 拦截响应。
- **dnsmasq 分工**：保留 DHCP，将 DNS 监听移到内部 5353 端口，供租约设备名解析使用。
- **租约名转发**：为 `lan` 和首启 LAN 对应的 IPv4 `/24` 反向区创建到 dnsmasq 的转发。
- **Advanced Forwarding**：随包提供并在首启安装扩展，为 DNS 分流提供基础。
- **强制 LAN DNS**：将 LAN 的 IPv4 TCP/UDP 53 请求重定向至本机，保留客户端源 IP；升级时保留管理员对该规则的启停选择。
- **DHCP 下发 DNS**：LAN 未配置 DNS 选项时，补充下发路由器地址。
- **OpenClash DNS 模式**：新装预选 Technitium 转发，OpenClash 本身仍默认停用；启用后由本地主 DNS 的 53 端口接收，不直接绕过主 DNS。
- **OpenClash IPv4 监听**：内核禁用 IPv6 时将核心监听地址改为 `0.0.0.0`，避免透明 UDP 监听的 IPv6 套接字报错。
- **DNS 与透明代理顺序**：强制 LAN DNS 规则启用时，LAN 的 53 请求先退出 OpenClash 接管链，再由 fw4 重定向给 Technitium，保留来源分组。
- **UDP 来源准入**：在接管 Fake-IP 的 UDP 流量前应用 LAN 来源访问控制，避免 Fake-IP 绕过来源白名单。
- **原生 DNS 分流预设**：复用 OpenClash 的自定义 DNS、指定代理组、Nameserver-Policy 和覆写脚本；首次选择订阅已有组，不写死组名，不覆盖业务规则和节点。
- **主 DNS 转发模式**：扩展原生本地 DNS 劫持下拉，选择 Technitium／AdGuard Home 后自动处理上游校正、所选内网区域的 53 接管和代理避让；支持双 DNS 入口，停止时不恢复公共上游。新装未配置并启动核心时不激活上游校正。
- **升级保留补丁**：独立补丁及兼容清单在构建时自动重放／检查，失败阻止发布；APK 精确版本约束与一键更新保护阻止未适配包覆盖。
- **联动凭证和回滚**：凭证保存在 root 专用文件中，首次调整前记录原全局上游；已有 watchdog 检查偏离，主 DNS 启动时执行一次校正，不增加常驻进程。
- **大 YAML 保存和应用**：只读运行配置不参与提交，源配置走文件流式提交；保留原生 CSRF 校验和 100 KiB 普通字段上限，传输不支持时阻止应用并保留编辑内容。
- **内部 DNS 端口保护**：防火墙拒绝客户端直接访问 5353、7874 端口。
- **WAN 访问保护**：防火墙拒绝从 WAN 访问 Technitium 的 53、5380 端口。
- **AdGuard Home 备用**：保留软件包，默认停用。
- **Docker 移除**：不集成 Docker、Compose、containerd、runc 及 Dockerman，构建时检查无残留启用项。
- **可选服务默认停用**：OpenClash、DDNS-GO、Tailscale、mwan3、OAF、UnblockNeteaseMusic 和 SQM 默认不自启，按实际需求配置启用。

实现文件见 [Technitium 首启策略](sources/full/files/usr/libexec/technitium-provision)、[DNS 和防火墙默认值](sources/full/files/etc/uci-defaults/93-technitium-dns)及[构建配置](profiles/network-ui.config)。

新增可选功能的界面路径、适用版本、验收与回滚见 [OpenClash DNS 联动和大配置维护说明](docs/openclash-dns-integration-20261124.md)。

#### 打包和构建兼容性

- **Tailscale 文件归属**：将配置文件与服务脚本的安装归属统一到管理包，避免与核心包重复安装。
- **Tailscale 构建路径**：修正自定义目录下的 Go 构建规则引用。
- **FileTransfer APK 安装**：将原有 IPK/opkg 安装入口改为 APK/apk。
- **FileTransfer 文件处理**：校验上传文件名、拒绝符号链接覆盖，并对 shell 参数和页面输出转义。
- **EQoS x86 依赖**：去掉 x86 不适用的 QCA NSS 依赖。
- **EQoS Plus 运行依赖**：补充 Bash 依赖。
- **mwan3 构建依赖**：修正 `libnetfilter-conntrack` 的依赖名称。
- **Arpbind 构建路径**：固定引用所选 LuCI feed 的 `luci.mk`。
- **Autoreboot 构建路径**：固定引用所选 LuCI feed 的 `luci.mk`。
- **FileTransfer 构建路径**：固定引用所选 LuCI feed 的 `luci.mk`。
- **Ramfree 构建路径**：固定引用所选 LuCI feed 的 `luci.mk`。
- **Technitium 构建输入**：通过独立项目的锁文件固定源码提交。
- **Mihomo 构建输入**：使用固定配方预装核心。
- **DDNS-GO 构建输入**：固定版本和源码摘要。
- **Go 工具链输入**：固定版本和源码摘要。
- **公开文件权限**：固定构建 umask，归一化公开 overlay 的目录、可执行文件和普通文件权限。
- **根文件系统权限检查**：检查 squashfs 目录能被非 root 服务遍历，同时保留私有文件权限。
- **软件包清单检查**：逐项核对包名、版本和允许的版本差异。
- **内核 ABI 检查**：逐项核对内核模块与镜像内核的 ABI。
- **ProWrt 版本**：由 `VERSION` 生成固件身份；LuCI「状态 → 概览」与 `prowrt-version` 读取同一记录，优先使用只读固件中的版本。
- **下载缓存**：CI 跨次复用公开下载资源，命中后继续执行原始摘要校验。
- **编译缓存**：CI 跨次复用 ccache，按工具链和输入分区，不缓存旧根文件系统或完整构建树。
- **构建耗时**：输出各阶段耗时、主机资源和本轮 ccache 统计；完整构建与全新启动检查继续执行。
- **发布身份检查**：校验 Git tag、`VERSION`、源码提交、外部 `build.json` 和镜像内部记录一致。

对应文件和应用位置见 [定制补丁索引](patches/README.md)。

## 文档和下载

- [固件方案、定制步骤与升级](docs/firmware.md)
- [额外组件与 LuCI 菜单](docs/components.md) · [定制补丁索引](patches/README.md)
- [日常使用和验收](docs/usage.md) · [从 U 盘启动或安装到内置 SSD](docs/physical-install.md)
- [Technitium、DNS 分流和升级](docs/technitium.md)
- [CI、GitHub Packages 与固件下载](docs/releases.md) · [构建产物摘要与 APK 清单](manifests/README.md)
- [固件版本查询、构建缓存和耗时验证](docs/build-cache-and-version.md)
- [隔离启动验收与 CI 故障记录](docs/ci-acceptance.md)
- [Netdata 界面与第三方插件对照](docs/netdata-ui-comparison.md)
- [底座和 feeds 锁定版本](sources.lock.json) · [第三方来源](custom-sources.lock.json)

项目代码采用 GPL-3.0-or-later。各上游组件按其原许可证使用。源码锁和示例配置可公开复用，生成的镜像、软件包签名密钥和 DNS 数据在部署环境独立保管。
