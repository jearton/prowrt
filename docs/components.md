# 额外组件与菜单

下表只列定制方案涉及的组件。已安装版本以该次镜像 manifest 为准，第三方精确提交及哈希见 [来源锁](../custom-sources.lock.json)。

| LuCI 菜单 | 组件 | 说明 |
| --- | --- | --- |
| 登录页、系统 → Argon 主题设置 | [Argon 3.1.4](https://github.com/jerrykuku/luci-theme-argon) | 主题、壁纸和中文设置 |
| 首页、网络向导 | [iStoreOS Quickstart](https://github.com/istoreos/quickstart)、[iStore](https://github.com/linkease/istore) | 首页、网络向导和应用入口；隐藏存储、下载和远程穿透卡片 |
| 系统 → 实时监控 | [Netdata 2.13.0](https://github.com/netdata/netdata)、LuCI 入口 | 预置本地概览、逐接口流量和主机指标 |
| 系统 → 终端 | [ttyd](https://github.com/tsl0922/ttyd) | 校验 LuCI 写权限后仍需输入系统用户名和密码；终端高度自适应 |
| 系统 → 文件管理、文件传输、磁盘管理、分区扩容 | LuCI File Manager、FileTransfer、[DiskMan](https://github.com/sbwml/luci-app-diskman)、[PartExp](https://github.com/sirpdboy/luci-app-partexp) | 本机系统维护 |
| 系统 → 定时重启、关机、自定义命令 | Autoreboot、PoweroffDevice、LuCI Commands | 管理操作 |
| 服务 → Technitium DNS | [Technitium 15.6.2](https://github.com/TechnitiumSoftware/DnsServer) · [控制台 1.4.2](https://github.com/byGarcia/technitium-console) · [LuCI 插件](https://github.com/jearton/luci-app-technitium) | 主 DNS、域名区域、广告过滤和查询统计 |
| 服务 → AdGuard Home | [AdGuard Home 0.107.79](https://github.com/AdguardTeam/AdGuardHome) | 可选 DNS 过滤，随镜像提供，默认停用 |
| 服务 → OpenClash | [OpenClash 0.48.002-r2](https://github.com/vernesong/OpenClash)、[Mihomo 1.19.34](https://github.com/MetaCubeX/mihomo)、[Zashboard 3.30.0](https://github.com/Zephyruso/zashboard)、[MetaCubeXD 1.276.0](https://github.com/MetaCubeX/metacubexd) | 基于规则的代理分流；面板使用独立的版本和 SHA-256 锁定 |
| 服务 → DDNS-GO | [DDNS-GO 6.17.8](https://github.com/jeessy2/ddns-go) | 动态 DNS |
| VPN → Tailscale、WireGuard | [LuCI Tailscale 1.2.17](https://github.com/jearton/luci-app-tailscale)、[Tailscale 1.104.7](https://github.com/tailscale/tailscale)、WireGuard | 远程接入和隧道 |
| 服务 → OAF 行为管理 | [OpenAppFilter](https://github.com/destan19/OpenAppFilter) | 应用识别与过滤 |
| 网络 → 负载均衡、定时限速、SQM 队列管理 | [nftables mwan3](https://github.com/dl12345/mwan3)、EQoS/EQoS Plus、SQM | 多 WAN 策略、限速和队列管理 |
| 网络 → 流量统计、网速测试、IP/MAC 绑定 | nlbwmon、vnStat2、iperf3/LibreSpeed、Arpbind | 计量、测速和静态邻居 |
| 网络 → 接口、防火墙 | 原生 netifd 支持 Macvlan、多 PPPoE、fw4 软件流量卸载 | 对应旧 Macvlan、多拨、Turbo ACC 的部分功能；双 WAN 与硬件选项按设备验收 |

固件服务集中于路由、DNS、VPN、流量管理和监控。Technitium 使用原生后台和控制台；镜像不包含 Docker、Samba、WebDAV、DDNSTO、下载服务和网易云解锁。
