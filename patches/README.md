# 定制补丁索引

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
- [OpenClash 来源准入顺序](../sources/full/package/custom/luci-app-openclash/root/etc/init.d/openclash)：来源访问控制先于 Fake-IP UDP 接管。
- [本地 DNS 顺序适配](../sources/full/files/usr/libexec/prowrt-openclash-dns)：只在已有本地 LAN DNS 重定向启用、目标 53 时，排除对应 LAN 的代理链 53 请求；由 OpenClash 启动规则后调用，管理员关闭规则时不主动开启。
- [包修订号](../sources/full/package/custom/luci-app-openclash/Makefile)：0.48.002-r1 用于区分本项目调整。
- 后台“立即备份遗漏尚未落盘区域”仅[记录为原生限制](../docs/vm-validation-20261123.md)，用户决定暂不修改，因此没有对应后台补丁。

上述条目是当前源码变更，须随最终镜像重新验收；不是历史发布镜像已自动升级的声明。
