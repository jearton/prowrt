# Technitium DNS

OpenWrt 完整镜像内置 Technitium DNS 15.6.2、ASP.NET Core 10.0.15 musl x86/64 运行时、technitium-console 1.4.2 和 Advanced Forwarding 5.2，由 procd 启动。AdGuard Home 和它的 LuCI 菜单作为备用预装，默认停用。

后台和 LuCI 插件统一来自 [luci-app-technitium](https://github.com/jearton/luci-app-technitium)，源码提交固定在 `technitium-luci.lock.json`。通用包首次安装默认停止且关闭开机启动，本固件通过 `93-technitium-dns` 显式开启，并由网络启动后的 `technitium-provision` 一次性服务配置 DNS 分流、租约名转发和 Advanced Forwarding。软件包升级保留既有启停状态和数据。

## 第一次登录

进入 **服务 → Technitium DNS**，确认服务已运行，打开控制台。控制台监听 TCP 5380，使用自己的管理员账户。用户名为 `admin`，通过已受保护的 SSH 管理连接读取 `/etc/technitium/setup-password`。登录后更改密码，删除一次性密码文件。Technitium 配置保存在 `/etc/technitium/data`，位于系统配置备份范围内。

远程管理可以通过受限的 SSH 转发访问路由器的 `127.0.0.1:5380`。控制台仅在可信管理网络使用。防火墙禁止 WAN 访问 DNS 和控制台。

## DNS 和 OpenClash

- 客户端从 dnsmasq 获取 DHCPv4 租约，DNS 指向路由器的 53 端口，由 Technitium 服务。
- 固件默认将 LAN 客户端经过路由器的 TCP/UDP 53 请求重定向到本机 53，即使终端手动指定外部普通 DNS，也由本机 Technitium 处理。规则名为 `Force LAN DNS to router`，可在「网络 → 防火墙 → 端口转发」关闭；升级保留已有规则的开关及修改。
- Technitium 条件转发 `.lan` 和初始化时所在 /24 LAN 的反向区到 `127.0.0.1:5353`，由 dnsmasq 回答租约、静态主机名和 PTR。
- 当前源码首启将公网查询交给两个 DoT 上游：`dns.alidns.com (223.5.5.5)` 和 `dot.360.cn (101.226.4.6)`，并行查询，Concurrency 为 `2`。括号中的固定地址用于引导连接，TLS 仍按域名校验证书。已发布的 20261120.2 使用旧的 AliDNS DoH 默认值。
- 当前源码首启将 DNSSEC Validation 设为关闭。这是用户确认的默认策略调整，不代表公共上游的 DNSSEC 证明缺失已被修复。原生 Console 的 **Settings → General → DNSSEC → Enable DNSSEC Validation** 可以直接设置；本项目不新增此开关，也不更改独立通用包的原生默认值。
- 自建区域、多个 A 记录、广告拦截列表、白名单和统计在 Technitium 控制台维护。逐条查询日志按需在 Apps 安装 Query Logs (SQLite) 并设置保留期限。
- OpenClash 默认停用，其 53 端口重定向保持关闭。需要 Fake-IP 时，在 Technitium 的 **Advanced Forwarding** 按客户端源 IP 划分组，只将代理白名单客户端需要 Fake-IP 的域名交给 `127.0.0.1:7874`。其他查询继续走真实 IP 上游。两处白名单使用相同的固定租约地址。
- OpenClash 配置、订阅凭证、用户内网区域和设备白名单由管理员配置。

候选源码在 **服务 → OpenClash → 插件设置 → DNS 设置 → 本地 DNS 劫持** 增加 Technitium／AdGuard Home 转发模式，启动时校正主 DNS 上游，停止时不恢复公共 DNS。分流复用原生覆写 DNS 设置的预置条目，首次选择订阅已有代理组；多区域、双入口与升级说明见 [维护说明](openclash-dns-integration-20261124.md)。

修改 LAN 网段或 DHCP 域后，在控制台同步修改条件转发区和反向区。 路由器重启后，动态租约名称随客户端重新取得租约而恢复。如果 dnsmasq 已能回答该名称，Technitium 仍显示 NXDOMAIN，可在控制台的 Cache 删除对应名称和 PTR 的缓存。切换到备用 AdGuard Home 时，先在备用端口确认应答，再在维护窗口停 Technitium 并让 AdGuard Home 接管 LAN 的 53 端口。

强制 DNS 是本固件的 fw4 策略，通用 `luci-app-technitium` 不默认创建它。规则只匹配 LAN 的 IPv4 TCP/UDP 53，保留客户端源 IP，不匹配路由器自身发出的查询或内部 5353/7874 链路。修改 Technitium DNS 监听端口时，同步修改这条规则的目标端口。DoH、DoT、VPN 内的 DNS 和未经过本路由器的流量不由这条规则接管。

启用 OpenClash 时，本固件在其透明代理链中先排除上述规则所在 LAN 的 53 请求，让 fw4 的本地重定向生效。仅关闭 OpenClash 自己的 DNS Hijack 不足以处理其通用 UDP TProxy 钩子的优先级。停用本地重定向或更改目标端口后，该适配不主动创建或开启规则；调整后重载防火墙及 OpenClash，并验证最终链顺序。

## 备份的已知限制

本轮实测：创建区域、添加记录后立即下载原生备份，压缩包遗漏了尚未写入磁盘的新区域；恢复该备份后该区域不存在。原生服务器对区域使用 5 秒定时写盘，备份直接读取磁盘文件。

用户决定先记录、不修改后台源码。已经写盘的区域通过了实际备份、修改、恢复和查询对比；“立即备份”仍是未通过项，不能将等待写盘后的结果算作该问题已经修复。备份前确认最近修改已保存，下载后核对备份包含目标 `zones/<域名>.zone`，并保留之前的可恢复备份。证据与边界见[本轮记录](vm-validation-20261123.md)。

## 从旧镜像升级

先备份旧固件、OpenWrt 配置、AdGuard YAML，以及容器版 Technitium 的数据目录。新镜像首启会配置 LAN 的主 DNS 和 DHCP 辅助端口。升级后在控制台导入自有区域和设置，复核现有 DHCP 选项指向路由器。涉及防火墙、网络和服务启动的改动应先在隔离环境验收。

回退时使用旧镜像及其配置备份，恢复原来的 AdGuard 入口和 Technitium 容器数据。旧方案见 [容器版部署记录](technitium-legacy-docker.md)。

当前首启初始化由 `/etc/technitium/provisioned` 标记保护。升级已有原生 Technitium 安装不会重新应用新默认值；要改为本轮策略，请在原生 Console 手动关闭 DNSSEC、选择 TLS 和上述两个上游、开启 Concurrent Forwarding 并将 Concurrency 设为 `2`，保存后分别验证公网解析和内网条件转发。
