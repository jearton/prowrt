# 定制补丁索引

## nlbwmon 三层统计候选

- [后台 IP 统计补丁](nlbwmon/100-ip-fallback.patch)：取消每条记录等待 MAC，增加固定容量、5 秒过期的失败缓存，保留真实 MAC 和原数据库格式。
- [LuCI 无 MAC 主机分组](nlbwmon/luci-ip-hosts.patch)：按 IP 区分未知 MAC，保留二层 MAC 汇总及明细链接。
- [构建适配](../scripts/prepare-nlbwmon.py)：校验上游及补丁摘要，生成 r3 后台和界面包。
- [验证与回滚](../docs/nlbwmon-routed-hosts-20261124.md)：原版故障复现、修复验收和适用边界分别记录。

## QuickStart 设备列表兼容候选

- [LuCI 代理适配](../scripts/prepare-quickstart-devices.py)：只修复已认证列表请求的空 ARP 错误，不改 QuickStart Go 二进制。
- [接口与邻居读取](../packages/quickstart-devices/devices.lua)：默认沿用 lan，可选多个逻辑接口；多接口发现只读，不扫描网络。
- [可见错误提示](../packages/quickstart-devices/errors.js)：真实列表失败明确显示，不再只呈现“暂无数据”。
- [使用、验证与回滚](../docs/quickstart-devices-20261124.md)：说明本地邻居发现和跨三层清单的边界。

补丁以相应 OpenWrt 树、LuCI feed 或已引入的插件配方为应用目录。首先查看每个补丁的目标路径，按来源锁准备相同版本，再执行 git apply --check。功能验收见固件文档和菜单清单。

| 组件 | 补丁 |
| --- | --- |
| Netdata | [配置权限](custom-ipv4/netdata-config-readable.patch)、[容器网卡采集](custom-ipv4/netdata-container-network.patch)、[原生概览打包](custom-ipv4/netdata-overview.patch)、[LuCI 本地仪表盘和「实时监控」标题](custom-ipv4/netdata-luci-bundled-dashboard.patch)；Netdata 2.13.0-r5 包含[本地模板与初始化适配](../packages/netdata/files/overview)、[CSP 与本地字体处理](../packages/netdata/prepare-overview.py)；LuCI 0.1-r3 默认打开原生概览，含逐接口实时表格与 RX/TX 历史曲线；本机节点身份变化时只更新预置函数卡的节点绑定，保留个人布局。兼容性边界与验收见[记录](../docs/netdata-overview-acceptance-20261120.md) |
| ttyd | [LAN 监听、LuCI 会话、WebSocket 权限校验和 DER/PEM 证书适配](custom-ipv4/ttyd-luci-session.patch)；r6 保留证书适配、每次系统登录及空密码拒绝；LuCI TLS 监听仅协商 HTTP/1.1，避开 Chrome HTTP/2 WebSocket 的 Origin 误拒绝；[配置迁移](../sources/full/files/etc/uci-defaults/93-ttyd-luci-session)；[LuCI 协议适配与自适应终端高度](../image-files/network-ui/www/luci-static/resources/view/ttyd/term.js) |
| LuCI | [iptables 后端识别](custom-ipv4/luci-nftables-legacy-warning.patch)、[文件管理样式](custom-ipv4/luci-filemanager-layout.patch) |
| Tailscale | [Tailscale 文件归属](custom-ipv4/tailscale-file-ownership.patch) |
| Technitium | [独立原生包与 LuCI 项目](https://github.com/jearton/luci-app-technitium) · [固定源码提交](../technitium-luci.lock.json) · [固件首启策略](../sources/full/files/usr/libexec/technitium-provision) · [LAN DNS 和防火墙默认值](../sources/full/files/etc/uci-defaults/93-technitium-dns) |
| OpenClash、DDNS-GO、Go | [Mihomo 配方](custom-ipv4/openclash-mihomo.Makefile)、[DDNS-GO 版本](custom-ipv4/ddns-go-6.17.8.patch)、[Go 版本](custom-ipv4/golang-1.27.4.patch) |
| 负载均衡、限速 | [mwan3 构建依赖](custom-ipv4/mwan3-build-dependency.patch)、[EQoS x86](custom-ipv4/eqos-x86.patch)、[EQoS Plus Bash](custom-ipv4/eqosplus-bash.patch) |
| 工具 | [Arpbind](custom-ipv4/arpbind-pinned-luci-include.patch)、[Autoreboot](custom-ipv4/autoreboot-pinned-luci-include.patch)、[FileTransfer LuCI](custom-ipv4/filetransfer-pinned-luci-include.patch)、[FileTransfer APK](custom-ipv4/filetransfer-apk.patch)、[Ramfree](custom-ipv4/ramfree-pinned-luci-include.patch) |
| 构建权限 | [构建入口](../scripts/build-full.sh)固定 umask 并归一化公开 overlay 的权限；[squashfs 元数据检查](../scripts/check-rootfs-permissions.py)拒绝非 root 服务无法遍历的系统目录，保留 shadow 等私有文件权限 |

[Quickstart r5 补丁](../packages/quickstart-home-r5/quickstart-openwrt.patch) 对应较早的 Quickstart 源码配置。当前网络界面方案的 Quickstart 来源见 [iStoreOS 资产锁](../packages/istoreos-ui-2026110611/ui-source.json)。

## 2026-11-23 候选源码调整

- [Technitium 首启策略](../sources/full/files/usr/libexec/technitium-provision)：DNSSEC 关闭、AliDNS＋360 DoT、并行数 2；不修改后台及 Console，不重写已初始化系统的管理员设置。
- [OpenClash 配置生成](../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/yml_change.sh)：内核禁用 IPv6 时生成 IPv4 监听地址，避免 TProxy 监听报错。
- [OpenClash 来源准入顺序](../sources/full/package/custom/luci-app-openclash/root/etc/init.d/openclash)：在兼容模式开启 UDP 代理的分支，将来源访问控制放在 Fake-IP UDP 接管之前。这是本项目的严格来源策略适配；原生来源流量表本身排除 Fake-IP 目标，不能据此宣称上游确认存在 bug。无补丁 Dev 版的独立复现和上游反馈尚未完成。
- [本地 DNS 顺序适配](../sources/full/files/usr/libexec/prowrt-openclash-dns)：只在已有本地 LAN DNS 重定向启用、目标 53 时，排除对应 LAN 的代理链 53 请求；由 OpenClash 启动规则后调用，管理员关闭规则时不主动开启。
- [包修订号](../sources/full/package/custom/luci-app-openclash/Makefile)：0.48.002-r1 区分上述策略调整；r2 更新下列两个面板的打包来源，保留官方稳定 Mihomo 1.19.34。
- 后台“立即备份遗漏尚未落盘区域”仅[记录为原生限制](../docs/vm-validation-20261123.md)，用户决定暂不修改，因此没有对应后台补丁。

上述条目是当前源码变更，须随最终镜像重新验收；不是历史发布镜像已自动升级的声明。

## 2026-11-24 面板打包调整

- [独立来源锁](../sources/full/package/custom/luci-app-openclash/ui.lock.json)：Zashboard 从内置 1.48.0 更新为 3.30.0，MetaCubeXD 从实际入口使用的 1.176.0 更新为 1.276.0；分别锁定官方 Release 附件、源码提交和 SHA-256。
- [下载配方](../sources/full/package/custom/luci-app-openclash/Makefile)：通过 OpenWrt 的下载流程取回已锁定附件，复用下载缓存并验证摘要。
- [静态资源安装](../sources/full/package/custom/luci-app-openclash/prepare-ui.py)：先验证压缩包与本地入口资源，再整体替换面板目录，清除旧版分块；直接使用官方分发文件，不修改面板程序。
- [包内来源记录](../scripts/lan-vm.py)：首次启动核对 `/usr/share/prowrt/openclash-ui.json` 与固件 `build.json` 中两个面板的版本和摘要。
- [固件身份](../scripts/build-metadata.py)：把面板来源锁纳入构建输入摘要，避免只显示 OpenClash 插件版本而遗漏内置面板版本。
- [安装检查](../scripts/check-openclash-ui.py)：检查实际官方附件能离线加载本地入口资源，并验证旧文件被替换。
- [浏览器检查工具](../scripts/check-openclash-browser.cjs)：使用原生 OpenClash 链接生成器和独立 Mihomo 测试后端，记录连接性能与缓存迁移；用户的面板交互验收与工具结果分别记录。
- 此次没有切换 Smart 核心，也没有升级 GeoSite、Country.mmdb 或系统依赖；这些组件不能仅凭插件版本号被标为“全部最新”。

## 构建缓存与固件身份

- [版本入口](../VERSION)：单独维护 ProWrt 发布号，不改 OpenWrt 底座版本和 APK 软件源。
- [固件元数据](../scripts/build-metadata.py)：构建时生成版本、源码提交、来源锁摘要和 CI 编号，禁止将脏目录作为正式构建发布。
- [命令行查询](../sources/full/files/usr/bin/prowrt-version)：优先读取只读 `/rom` 的固件身份，避免旧配置备份覆盖版本显示。
- [LuCI 概览](../image-files/network-ui/www/luci-static/resources/view/status/include/05_prowrt.js)：增加 ProWrt 区块，使用与 CLI 相同的版本记录；[ACL](../image-files/network-ui/usr/share/rpcd/acl.d/prowrt-version.json)仅允许读取公开元数据。
- [下载缓存](../scripts/build-cache.py)：独立目录保存 OpenWrt 下载与 SHA-256 寻址的 iStoreOS UI 输入，保留原始摘要验证。
- [编译缓存](../.github/workflows/build-firmware.yml)：ccache 跨次持久化、compiler content 检查、容量限制、按输入分区；仅 main 保存。
- [耗时报告](../scripts/build-metrics.py)：记录分阶段耗时、失败状态、主机资源、缓存来源；本轮 ccache 统计随 CI 附件保留。
- [发布检查](../scripts/check-build-identity.py)：不挂载磁盘，直接从组合镜像内的 squashfs 读取版本，与附件、tag 和源码提交比对。
- [首次启动检查](../scripts/lan-vm.py)：从实际启动的镜像执行 `prowrt-version`，检查 CLI、LuCI include 和 ACL 存在。
- 适用范围、操作与回滚见[维护说明](../docs/build-cache-and-version.md)。没有修改 Technitium 或 Console 源码。

## 2026-11-24 原生 DNS 模式与大配置（候选 r3）

- [独立补丁](openclash/0001-prowrt-integration.patch)与[兼容清单](openclash/series.json)：维护原生下拉扩展、API 联动、界面、大配置及升级保护；构建先重放／校验，不兼容中止。
- [原生设置入口](../sources/full/package/custom/luci-app-openclash/luasrc/model/cbi/openclash/settings.lua)：扩展本地 DNS 劫持下拉，沿用原生选项，不另建分流开关。
- [附属配置](../sources/full/package/custom/luci-app-openclash/luasrc/openclash_dns.lua)：选择内网来源区域、可选 CIDR、多个本机 DNS 地址及私有 API 凭证。
- [原生 UCI 预设](../sources/full/package/custom/luci-app-openclash/root/etc/config/openclash)：Google／Cloudflare DoH 与引导项；代理组首次从订阅现有组选择，不写死。
- [原生策略文件](../sources/full/package/custom/luci-app-openclash/root/etc/openclash/custom/openclash_custom_domain_dns_policy.list)与[原生覆写脚本预设](../sources/full/package/custom/luci-app-openclash/root/etc/openclash/custom/openclash_custom_overwrite.sh)：国内直连、独立节点解析与订阅 DNS 残留清理，不改业务规则。
- [只读原生配置检查](../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_native_check.rb)：拒绝缺失的用户所选组，不生成分流／代理组。
- [API 适配](../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_link.rb)：仅校正主 DNS 全局上游，读回验证、认证失败保护，停止不恢复。
- [fw4 配置](../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_firewall.rb)：内网多区域、来源可选限制、双入口例外、精确 DNS INPUT；复用已有规则并记录回滚值。
- [代理避让](../sources/full/files/usr/libexec/prowrt-openclash-dns)：根据本地 53 接管规则对应的区域，自动让普通 DNS 先退出代理链。
- [DNS 包启动回调](../scripts/prepare-dns-service-hook.py)：Technitium r3、AdGuard Home r2 仅添加有上限的启动校正，不修改程序或 Console，不增加 cron／常驻轮询。
- [只读模板](../sources/full/package/custom/luci-app-openclash/luasrc/view/openclash/readonly_config.htm)与[提交辅助](../sources/full/package/custom/luci-app-openclash/root/www/luci-static/resources/openclash/js/common.js)：运行 YAML 不提交；源文件流式提交，失败保留编辑内容，不放大全局上限。
- [APK 约束](../sources/full/package/custom/luci-app-openclash/root/etc/uci-defaults/99-prowrt-openclash-pin)与[一键更新保护](../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/openclash_update.sh)：普通升级不能静默换成未适配上游包。
- [维护说明](../docs/openclash-dns-integration-20261124.md)：菜单路径、默认范围、已有配置兼容、升级和回滚。

## LuCI 连接页大列表修复（2026-11-27 候选）

- [原生认证 HTTP 页面](../packages/luci-connections/connections.js)：全快照解析、全表筛选／数值排序、100 行分页，图表和列表分别刷新。
- [解析模块](../packages/luci-connections/conntrack.js)：保留连接原始方向与双向计数，不通过 UBUS 搬运大列表。
- [旧 RPC 防护](../packages/luci-connections/legacy-guard.patch)：有界解析，超限返回非认证错误，不伪造完整成功。
- [独立来源锁与文件级合并](../packages/luci-connections)：只改相关方法、菜单 action 和 ACL，保留其它现场定制。
- [构建整合](../scripts/prepare-luci-connections.py)：严格核对固定上游文件与配方，构建 r2 并同步最终包清单。
- [根因、实际验收与回滚](../docs/luci-connections-20261127.md)：连接页故障与 uhttpd 权限阻塞分别记录，不能混为一个根因。
