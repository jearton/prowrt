# 2026-11-20 虚拟机扩展验收

对象为 [v25.12.6-20261120](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120)，EFI 压缩镜像 SHA256：`842079ee87cd5ad0dbdff84d1edf22c09715441adf2177f31ad17fa301520023`。本轮在该镜像验收盘的冷复制工作副本中配置功能，没有修改发布附件，不能将实验配置当作固件已经具备的默认行为。

**结论：多项网络功能通过隔离实测，但不能宣布全部验收通过。默认 AliDNS DoH 配合 Technitium 本地 DNSSEC 校验，存在部分公网域名 SERVFAIL 的未通过项。** 原有记录仅验证 `example.com`，不足以覆盖该问题。

## 环境和授权

用户明确批准了[隔离验收计划](vm-extended-validation-plan.md)。9000 为 4 vCPU / 4096 MiB 的 x86/64 EFI 路由器，9001 为 Debian 实验客户端。实验 LAN 为 192.168.77.0/24，vmbr99 无宿主地址和物理上联。两台 guest 均保持 IPv6 禁用。

测试前正常关闭 9000，将原盘 16 冷复制为工作盘 17，逐字节比较一致后才启动工作盘。保存两台 VM 配置、其余 13 台 VM 的配置摘要以及宿主 IPv4/IPv6 主路由表。虚拟 WAN、VPN 对端和 VLAN 都在 guest 内建立；没有更改生产交换机、DNS、Headscale 或 Tailnet。

## 结果

| 项目 | 判定 | 实际检查及限制 |
| --- | --- | --- |
| bonding active-backup | 通过 | 两条虚拟链路，活动链路断开后切到备用链路，断开前后及恢复后 ping 均无丢包 |
| bonding 802.3ad | 通过 | 两端虚拟 LACP 协商出 2 个成员；断开一条后剩 1 个成员且可通信，恢复后回到 2 个成员 |
| WireGuard | 通过，有恢复时间 | UCI/netifd 与内核 WireGuard 对接独立 Debian peer；握手、双向 ping、实际加密流量通过。接口重启恢复用时 12.02 秒，期间 4 次探测失败，不是无损切换 |
| VLAN / DHCP / 防火墙 | 通过 | VLAN 777 的实际 DHCP DORA 获得 172.30.77.13，网关和 DNS 正确；租约设备名可解析；不能访问管理 LAN 客户端 |
| mwan3 双 WAN | 通过 | 两套 namespace 上游，40 条新连接分配为 20/20；断链后 10 条新连接全部走存活上游；恢复后重新使用两个出口。未测试已有连接无损迁移 |
| SQM / CAKE | 通过 | 设置上行 5000、下行 8000 kbit/s，实测 4.61 / 7.55 Mbps；CAKE/IFB 计数增加，停止后解除限速 |
| SQM 受载延迟 | 已测量 | 空闲 RTT 均值 0.176 ms，CAKE 上行负载时 0.592 ms、下行负载时 0.674 ms，无丢包。此为虚拟 veth 路径，不是运营商线路的 bufferbloat 评分 |
| AdGuard Home 备用 | 通过 | 官方 procd 服务使用独立 DNS 3053 和回环管理 3001；本地/公网查询、临时过滤规则及删除恢复通过；主 Technitium 未中断，结束后保持停用 |
| Tailscale | 部分验证 | 1.104.7 本地守护进程及 LuCI/RPC 返回正常，状态 NeedsLogin。未注册到 Tailnet；对端握手、subnet route、exit node 和真实 ACL 未验证 |
| OpenClash / Mihomo | 有条件通过 | Mihomo v1.19.34，使用已授权节点实测 TCP HTTPS 直连和代理；出口不同，核心日志与连接源匹配。DNS 测试使用下述临时转发配置，不能据此消除默认 DNSSEC 失败项 |
| 源 IP / Fake-IP | 通过 | 白名单客户端得到 Fake-IP 并进入核心；独立 macvlan 客户端得到真实 IP，透明转发链提前返回且核心 TCP 日志不出现该源地址；非白名单出口与直连一致 |
| 强制 DNS 53 | 通过 | 两个源组向 TEST-NET 外部 DNS 发起查询仍由本机处理，保留各自源组的 Fake-IP / 真实 IP 行为；LAN 不能直接使用内部 5353/7874 |
| 显式代理端口白名单 | 额外规则通过，非默认交付 | 原生 LAN ACL 约束透明代理。工作副本额外增加防火墙 INPUT 规则后，非白名单无法连接 7890–7895，白名单仍可连接和代理。TCP 端口可达不等于未经认证即可使用代理 |
| 启用 OpenClash 后重启 | 通过 | 工作副本启用自启后重启，OpenClash、Netdata、ttyd、Technitium 运行；再次验证白名单 Fake-IP、TCP 代理和非白名单真实 IP/直连。发布镜像仍默认关闭 OpenClash |
| Mac Chrome 菜单 | 页面渲染通过 | 45 个生效页面渲染，无页面脚本错误或本地资源加载失败；覆盖状态、接口、DHCP、防火墙、磁盘、文件管理、SQM、mwan3、Technitium、备用 AdGuard、Tailscale 等。没有点击保存、测速、格式化或升级等动作，不能将页面渲染当作这些动作已通过 |
| 防火墙页面 | 通过 | 本轮页面没有“检测到旧版规则”告警 |
| 备份结构 | 通过 | 实际生成 sysupgrade 备份，核对 network/firewall/dhcp、Technitium dns.config、webservice.config 和 lan.zone；原始备份未导出且已删除。未执行覆盖恢复 |
| 温度 / RPM / PWM | 未验证 | VM 没有真实 hwmon 传感器，必须在目标物理机验收 |

虚拟 iperf3 的数 Gbit/s 结果只用于证明实际业务流量，不能用作物理网卡、交换机、加密或路由器线速承诺。代理节点配置为 `udp: false`，本轮没有验证 UDP 代理。核心还记录了 Redir UDP / TProxy 的 `protocol not available` 错误；IPv4 TCP 实测通过，错误原因未验证，不能写成日志完全正常。

## 默认 DNSSEC 未通过项

恢复默认转发策略时，`api.ipify.org`、`checkip.amazonaws.com` 等查询出现 SERVFAIL，扩展错误为 RRSIGsMissing。签名域名 `example.com` 可正常解析，因此此前的单域名检查没有发现问题。结束时重新挂回原盘 16，再由 9001 对这三个域名查询，仍复现相同的通过/失败差异，确认不是工作副本的 OpenClash 实验配置独有的问题。

Technitium 的 DNS Client API 指向 AliDNS DoH 时报告父区负向 DS 证明缺少 RRSIG；9001 用验证 TLS 证书的独立 DoH 查询也取得了缺少 DNSSEC 证明的响应。这支持“当前上游路径返回资料不完整”的判断。对 DNSPod DoH 的探测也报告缺少签名，不能将未经验证的上游替换直接标为修复；是否涉及具体上游、网络路径或其它因素，仍需进一步隔离定位。

为了单独验证 OpenClash，**只在工作副本的 Advanced Forwarding 实验转发器中暂时设置 `dnssecValidation=false`**，使真实 IP 查询正常后再执行代理和源组测试。全局 DNSSEC 设置、原盘和发布镜像没有因此关闭校验。测试后通过正式 API 恢复原 App 配置并回读比较一致。

下一版须解决该默认兼容性问题，再覆盖签名域名、未签名域名、故意损坏的 DNSSEC 域名和冷缓存启动。不能仅改一个普通域名重试成功，或在文档中悄悄关闭 DNSSEC 后宣布通过。

## 测试工具修正

保留了首次失败记录，以下属于测试方法修正，不计作功能自动通过：DHCP 未配置地址前改用原始包接收 Offer；多 WAN 上游 stub 改用系统已有的 uhttpd 守护方式；重启检查按实际 procd 状态和重命名后的 clash 进程判断。WireGuard 重启首次探测失败属于实际恢复间隔，已如实计入上表。

菜单中的旧 routes 页面被 `ip-full` 依赖条件排除，直接访问得到 404；实际生效的 routesj 页面渲染通过。没有修改固件来消除这个条件分支。

## 结束状态

收尾核验通过：

- 恢复前冷校验原盘 16 的 SHA256 与测试前一致，随后挂回并启动 9000。工作盘 17 保留作排障证据；没有删除旧磁盘。
- 原盘的 Netdata、ttyd、Technitium 均开机启用且运行；OpenClash、Tailscale、mwan3、SQM 保持默认关闭，IPv6 仍禁用。
- 9001 恢复关机，VM 配置与测试前一致。9000 的原配置恢复，仅额外保留工作盘为未使用磁盘。
- 其余 13 台 VM 配置摘要、宿主 IPv4/IPv6 主路由表一致。vmbr99 没有宿主地址或物理成员，管理 namespace 没有默认路由且禁用 IPv6。
- 临时 namespace、接口、代理配置、额外输入规则、客户端工具及 SSH 密钥已清理；Technitium App 配置通过 API 恢复并回读。原盘不存在此次临时 SSH 密钥。

发布 Release 附件保持不变。上述默认 DNSSEC 问题仍待下一版修复；恢复原盘不代表修复该缺陷。

登录页、终端每次系统认证、终端高度以及 Netdata 实际图表的独立验收见[完整镜像验收](acceptance-20261120.md)。经典 Netdata Dashboard 尚未接回，界面差异见[Netdata 对照](netdata-ui-comparison.md)。
