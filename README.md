# ProWrt

ProWrt 是基于 OpenWrt 25.12.6 x86/64 的 IPv4 路由器定制固件。使用 APK，内置 LuCI、实时监控和原生 Technitium DNS。默认禁用 IPv6，镜像验收使用独立实验 LAN。AdGuard Home 随镜像提供，默认停用。

最新发布：[v25.12.6-20261120.2](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120.2)。新增 Netdata 2.13.0 原生 System Overview、全部网络接口实时表格和逐接口 RX/TX 曲线，预置布局可离线、无云账号、跨浏览器自动初始化；[本轮镜像验收](docs/netdata-overview-acceptance-20261120.md)。含 `kmod-bonding`，Netdata、ttyd 默认自启；终端每次要求系统登录并填满窗口剩余高度。查看[登录与终端基线验收](docs/acceptance-20261120.md)及[补丁清单](patches/README.md)。

已知问题：扩展验收发现默认 AliDNS DoH 配合 Technitium DNSSEC 校验时，部分公网域名返回 SERVFAIL，尚未修复。不能将本版本标为全部功能验收通过；通过项目、实验配置和未验证范围见[VM 扩展验收](docs/vm-extended-validation-20261120.md)。

下一版候选的源码已按用户确认调整：DNSSEC 首启默认关闭，公网上游使用 AliDNS＋360 DoT，并行查询两个上游。独立包及原生 Console 的 DNSSEC 开关不改动。隔离工作盘的并发、故障切换、DNS 分组及 OpenClash 联测结果见[本轮记录](docs/vm-validation-20261123.md)；这些结果不代表新镜像已经发布或完成最终验收。

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
| 网络 → 流量统计、网速测试、IP/MAC 绑定 | 客户端和接口计量、测速、静态邻居 | [nlbwmon](https://github.com/jow-/nlbwmon)、[vnStat 配方](https://github.com/openwrt/packages/tree/093d551675b1119a06ef224d419905e8d6b2af1a/net/vnstat2)、[网速测试 LuCI](https://github.com/muink/luci-app-netspeedtest)、[iperf3](https://github.com/esnet/iperf)、[LibreSpeed](https://github.com/librespeed/speedtest-go)、[Lean LuCI](https://github.com/coolsnowwolf/luci/tree/f43c53a60f11f5d635b7127c775e9c04e2be191d) |
| 网络 → DHCP/DNS、Macvlan | 定制快捷页面，沿用 OpenWrt 原生配置接口 | [本项目菜单和页面](image-files/network-ui)、[netifd](https://git.openwrt.org/project/netifd.git) |
| 网络 → 接口 | 完整版构建启用以太网链路聚合驱动 `kmod-bonding` | [OpenWrt bonding 配方](https://github.com/openwrt/openwrt/blob/v25.12.6/package/kernel/linux/modules/netsupport.mk) |

原生 DNS 菜单和部署步骤见 [Technitium 使用文档](docs/technitium.md)。实际包版本以对应构建随附的 APK 清单为准。

### 本项目的补丁和调整

以下分别列出源码补丁、随包页面和固件默认配置；不是每项都通过 `.patch` 文件实现。

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
- **默认上游**：当前源码首启设置 AliDNS 与 360 DoT，使用证书校验和固定引导 IP；已发布的 20261120.2 仍是旧配置。
- **并行查询**：首启启用 concurrent forwarding，并发数为 2；缓存未命中时同时请求两个公网上游。
- **DNSSEC 默认值**：本固件首启设置为关闭；原生 Console 的 Settings → General → DNSSEC 可以自行开启。通用后台包默认值不变。
- **升级保留 DNS 设置**：已完成初始化的安装不会因升级而覆盖管理员的 DNSSEC、上游及并发设置；需要使用新默认值时在原生 Console 手动调整。
- **广告过滤默认值**：首启启用 Technitium blocking，并使用 NXDOMAIN 拦截响应。
- **dnsmasq 分工**：保留 DHCP，将 DNS 监听移到内部 5353 端口，供租约设备名解析使用。
- **租约名转发**：为 `lan` 和首启 LAN 对应的 IPv4 `/24` 反向区创建到 dnsmasq 的转发。
- **Advanced Forwarding**：随包提供并在首启安装扩展，为 DNS 分流提供基础。
- **强制 LAN DNS**：将 LAN 的 IPv4 TCP/UDP 53 请求重定向至本机，保留客户端源 IP；升级时保留管理员对该规则的启停选择。
- **DHCP 下发 DNS**：LAN 未配置 DNS 选项时，补充下发路由器地址。
- **OpenClash DNS 接管**：默认关闭 OpenClash 自身的 DNS 重定向，避免与 Technitium 入口重复接管。
- **OpenClash IPv4 监听**：内核禁用 IPv6 时将核心监听地址改为 `0.0.0.0`，避免透明 UDP 监听的 IPv6 套接字报错。
- **DNS 与透明代理顺序**：强制 LAN DNS 规则启用时，LAN 的 53 请求先退出 OpenClash 接管链，再由 fw4 重定向给 Technitium，保留来源分组。
- **UDP 来源准入**：在接管 Fake-IP 的 UDP 流量前应用 LAN 来源访问控制，避免 Fake-IP 绕过来源白名单。
- **内部 DNS 端口保护**：防火墙拒绝客户端直接访问 5353、7874 端口。
- **WAN 访问保护**：防火墙拒绝从 WAN 访问 Technitium 的 53、5380 端口。
- **AdGuard Home 备用**：保留软件包，默认停用。
- **Docker 移除**：不集成 Docker、Compose、containerd、runc 及 Dockerman，构建时检查无残留启用项。
- **可选服务默认停用**：OpenClash、DDNS-GO、Tailscale、mwan3、OAF、UnblockNeteaseMusic 和 SQM 默认不自启，按实际需求配置启用。

实现文件见 [Technitium 首启策略](sources/full/files/usr/libexec/technitium-provision)、[DNS 和防火墙默认值](sources/full/files/etc/uci-defaults/93-technitium-dns)及[构建配置](profiles/network-ui.config)。

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

对应文件和应用位置见 [定制补丁索引](patches/README.md)。

## 文档和下载

- [固件方案、定制步骤与升级](docs/firmware.md)
- [额外组件与 LuCI 菜单](docs/components.md) · [定制补丁索引](patches/README.md)
- [日常使用和验收](docs/usage.md) · [从 U 盘启动或安装到内置 SSD](docs/physical-install.md)
- [Technitium、DNS 分流和升级](docs/technitium.md)
- [CI、GitHub Packages 与固件下载](docs/releases.md) · [构建产物摘要与 APK 清单](manifests/README.md)
- [隔离启动验收与 CI 故障记录](docs/ci-acceptance.md)
- [Netdata 界面与第三方插件对照](docs/netdata-ui-comparison.md)
- [底座和 feeds 锁定版本](sources.lock.json) · [第三方来源](custom-sources.lock.json)

项目代码采用 GPL-3.0-or-later。各上游组件按其原许可证使用。源码锁和示例配置可公开复用，生成的镜像、软件包签名密钥和 DNS 数据在部署环境独立保管。
