# 固件启动验收与 CI 故障记录

## 两类验收

- 完整镜像验收由 Build full firmware 工作流执行。它编译固定的 OpenWrt 和 feeds、核对软件包版本与全部 kmod 的内核 ABI，然后将生成的 EFI 镜像解压到全新的临时磁盘启动。
- Technitium 初始化回归由 Reproduce Technitium first boot 工作流执行。它使用按 SHA256 固定的历史发布镜像，安装已发布的 Technitium APK、应用当前固件的初始化和 ttyd init 脚本，再以全新的 DNS 数据目录验证。这个测试用于快速定位集成问题，不能替代完整新镜像验收。

完整构建在启动验收前上传名为 unverified-firmware 的临时制品。这个名称表示尚未验收，不能当作正式发布。只有启动验收通过，工作流才推送 GHCR 候选镜像并重新拉取、核对 SHA256。

初始化回归所用的旧镜像缺少 HTTPS 证书生成工具，因此测试额外安装按 SHA256 固定的官方 px5g 辅助包。交付固件中的 px5g 由固定 OpenWrt 源码编译，版本由镜像包清单检查；回归辅助包不决定交付版本。

## 网络与凭证边界

测试运行于 Linux CI runner 的独立 network namespace：

- namespace 中只有 loopback 和专用于单台 QEMU guest 的 TAP，没有物理接口或默认路由。
- 测试客户端使用 192.168.1.2/24，直接访问 guest LAN 192.168.1.1。
- namespace 关闭 IPv6；guest 保留内核参数 ipv6.disable=1。
- 不连接生产 LAN、Tailnet、WAN 或宿主机业务网络，不修改生产 DNS 和防火墙。
- 测试通过串口写入一次性的 SSH 公钥。私钥、known_hosts 和测试磁盘只保存在临时目录，退出时销毁；发布的压缩镜像不包含这把测试密钥。
- HTTP、HTTPS 和 WebSocket 测试使用临时 VM 自己的 LuCI 会话，不使用物理机凭证。

测试完成后关闭 QEMU、删除临时磁盘和网络 namespace。排查失败时保留在 CI 日志中的内容包括服务状态、监听端口、DNS 条件转发区、相关日志，以及 DNS 报文摘要，不输出管理员初始密码或会话 token。

## 验收项目

| 项目 | 必须满足 |
| --- | --- |
| LuCI | 未登录请求被要求认证；登录后能打开 Technitium LuCI 页面 |
| Netdata | 本地仪表盘可获取；charts API 包含 system.cpu |
| Technitium Console | 服务返回已打包的现代控制台入口 |
| DNS | 外部 LAN 客户端的 UDP/TCP A 查询返回 LAN 地址，PTR 查询返回 openwrt.lan |
| 强制 DNS | 指定不可达的外部 DNS 地址仍取得本机答案；规则计数增加，Technitium 统计保留独立客户端源 IP；关闭规则后停止接管，重启用后恢复；重跑首启默认值保留关闭状态 |
| 终端 | 未登录、伪造 token、错误 Origin 的 WebSocket 均被拒绝；合法 LuCI 会话仍须输入系统用户名和密码；空密码拒绝；重连再次要求登录；认证后实际执行命令 |
| HTTP/HTTPS 会话 | 两种登录态分别可用，HTTPS 会话不能回退用于 HTTP 终端 |
| 包与内核 | 包版本只允许声明过的变化；所有 kmod 依赖与镜像内核 ABI 一致 |
| 打包权限 | 直接检查 squashfs 元数据，公开系统目录允许非 root 服务读取和遍历；shadow 保持私有 |

这些自动检查不代表已经完成 Mac 浏览器、物理网卡、硬件传感器、WAN 出口和代理节点的实机验收。完整交付仍应分别记录浏览器与物理机验证结果。

## 2026-11-19：UDP 转发误报

原来的 CI 使用 QEMU user-mode 网络，将宿主机 127.0.0.1:10553 转发到 guest 的 53 端口。检查表现为 UDP 查询超时。

[带抓包的回归任务](https://github.com/jearton/prowrt/actions/runs/44542892904)证明：

- 初始化脚本成功退出，并生成完成标记。
- Technitium 监听 IPv4 TCP/UDP 53，私网递归限制仍有效。
- VM 内查询 Technitium、LAN 地址及 dnsmasq 5353 均得到正确答案。
- 抓包显示外部查询到达 guest，guest 立即返回正确的 UDP A 应答，但宿主机转发端口没有交付回复。
- 同一路径的 TCP 查询成功。

修复是让 CI 测试客户端通过独立 namespace 中的 TAP 直接访问 LAN，移除这条验收路径对 QEMU UDP 端口转发的依赖。[首次 TAP 回归](https://github.com/jearton/prowrt/actions/runs/44544187698)已通过 UDP/TCP A 与 PTR 检查，随后暴露了下述独立的 HTTPS 问题。没有通过放宽固件 DNS ACL 或防火墙消除误报。

## 2026-11-19：HTTPS 缺少证书生成依赖

上述首次 TAP 回归中，LuCI 登录和 DNS 检查通过，HTTPS 登录因 443 未监听而失败。配置中已声明监听 443，但历史镜像既没有 px5g，也没有 openssl 命令，uHTTPd 无法在首次启动时生成证书。

固件配置补入 px5g-mbedtls，并将它加入严格包版本检查。该包属于 OpenWrt 官方组件，不修改 LuCI 或 Technitium 的认证实现。HTTP/HTTPS 和终端会话的全部检查继续保留。

## 2026-11-19：ttyd 不能读取 uHTTPd 的 DER 证书

[加入证书生成工具后的回归](https://github.com/jearton/prowrt/actions/runs/44545464681)中，uHTTPd 已监听 443，ttyd 日志报 PEM routines::no start line，终端端口未监听。uHTTPd 默认生成 DER 编码的证书，ttyd 的 libwebsockets/OpenSSL 后端要求 PEM。

ttyd 补丁 r4 通过官方 openssl-util 将配置中的 DER 或 PEM 证书和私钥规范化为运行时 PEM：

- 原证书和私钥保持原样，procd 继续跟踪它们的变化。
- 临时目录权限为 0700，生成的证书和私钥权限均为 0600。
- 输入错误时停止启动，不降低 LuCI 会话和 WebSocket 权限要求。
- EC/RSA、DER/PEM 四种组合及错误输入均由实际 OpenSSL 转换验证。

修复后的[隔离回归任务](https://github.com/jearton/prowrt/actions/runs/44547973505)于 2026-11-19 通过：LuCI HTTP/HTTPS 登录、Technitium 控制台、Netdata 图表 API、LAN 的 UDP/TCP A 和 PTR、终端页面及实际 shell 命令全部通过；未登录、伪造会话和错误 Origin 的 WebSocket 被拒绝，HTTPS 会话经 HTTP 访问终端也被拒绝。guest 的 IPv6 内核禁用参数和无 IPv6 地址均已检查。这是初始化回归结果，完整新镜像仍由独立构建任务另行验收。

## 2026-11-20：原生构建归档带入私有目录权限

189 的完整镜像在 9000 的新磁盘上停在 procd 的 ubus 阶段。1 核与 4 核均不能完成启动。串口中观察到子进程等待 RCU，但这个栈不能单独证明内核故障。清理内核后重编译，内核摘要和全部模块均未变化；旧工作镜像恢复后正常启动。

直接检查故障镜像的 squashfs 元数据，确认根目录、usr 等公开路径被打包为 0700。首次导入的构建 overlay 保留了私有归档目录权限。ubus 等降权服务无法遍历这些路径，与 [OpenWrt 上游权限问题记录](https://github.com/openwrt/openwrt/issues/9545)的症状一致。

构建入口明确设置 umask 022，并将只包含公开默认配置和 UI 文件的 overlay 目录设为 0755，普通文件设为 0644、已有可执行文件设为 0755，同时删除 AppleDouble 元数据文件。不会对整个 rootfs 递归放宽权限，shadow、私钥和服务数据仍按各自配方保持私有。

scripts/check-rootfs-permissions.py 在打包后直接检查 squashfs 元数据，阻止上述目录权限问题进入发布。修复后的完整镜像仍须重新完成 9000 浏览器与 9001 验收；仅编译成功不能提升为正式 Release。

## 2026-11-20：终端改为每次系统登录

用户的新要求替代此前复用 LuCI 会话直接进入 shell 的交互。r5 保留 LuCI 会话、Origin 和持续授权检查，命令改为由包安装的登录助手调用 /bin/login。root 密码为空或锁定时拒绝打开 shell。首启迁移将此前 /bin/ash -l 的默认配置改为登录助手，保留其他自定义命令。

隔离测试先用空密码的全新磁盘验证拒绝进入，再仅在临时测试磁盘设置随机系统密码。LuCI 登录后，终端必须先出现 login 和 Password 提示，认证后才可执行 root 命令；新建连接须重新登录。测试密码不写入发布镜像、源码或日志。

[r5 隔离回归](https://github.com/jearton/prowrt/actions/runs/44570476983)于 2026-11-20 通过上述全部检查，同时通过 LAN 的 UDP/TCP DNS、强制重定向计数、客户端源 IP 保留、关闭及重新启用规则、升级时保留规则关闭状态等检查。空密码提示会等待用户按 Enter 后退出，避免进程立即结束而导致终端来不及呈现说明。这仍是基于固定历史镜像的初始化回归，不替代新发布镜像的完整启动与浏览器验收。

## 回滚

固件或配置修复未通过时不提升为正式发布，保留已有 Release 和 SHA256。源码可用新的 revert 提交回退；不要替换已有发布镜像的内容。每次修复均以新构建和新临时磁盘重新验收。


## Mac Chrome 的 HTTPS 终端与 HTTP/2

2026-11-20，r5 完整镜像全新安装到 9000 后，Mac Chrome 的 HTTP 终端通过每次系统登录及窗口高度检查，HTTPS 页面却没有显示登录提示。CDP 报告 ERR_HTTP2_PROTOCOL_ERROR，ttyd 日志显示 Origin 被拒绝；同一 HTTPS 会话使用 HTTP/1.1 WebSocket 能取得登录提示。这与 [ttyd 上游问题 #1566](https://github.com/tsl0922/ttyd/issues/1566) 一致：Origin 检查读取 Host，而 HTTP/2 使用 :authority。

r6 只在 LuCI 授权的 TLS 监听设置 ALPN 为 http/1.1，保留来源、LuCI 会话和系统登录三项检查。使用 libwebsockets 的 [alpn 字段](https://libwebsockets.org/lws-api-doc-v4.0-stable/html/structlws__context__creation__info.html)，不要求用户关闭 Chrome 的 HTTP/2。完整镜像 CI 新增 TLS 协商检查，客户端同时提供 h2 和 http/1.1 时必须选中 http/1.1。历史镜像初始化 fixture 不替换 ttyd 二进制，故不以该 fixture 代替此检查。

失败的 r5 完整镜像不作为正式发布。r6 完整镜像已在全新磁盘通过 Mac Chrome HTTP/HTTPS 终端、Netdata、Console、9001 DNS 和重启验收；最终 SHA256、截图与检查边界见[正式验收记录](acceptance-20261120.md)。


## CI 旧镜像 fixture 的 SSH 启动等待

2026-11-20 的 [44575439069](https://github.com/jearton/prowrt/actions/runs/44575439069) 在旧镜像 bootstrap 等待 SSH 时超时，尚未进入新包安装和断言阶段；不能将该结果标记为新固件功能验收失败或成功。排障输出随后能取得 DNS 答案和 Netdata/Console HTTP 响应。bootstrap 原先持有串口 socket 却停止读取，再等待 SSH 150 秒。等待器改为持续排空串口，并给无硬件加速的冷启动 300 秒上限。新镜像的 Mac/PVE/9001 验收结果独立记录，不用 fixture 结果替代。


修复后的[旧镜像初始化回归 44577868930](https://github.com/jearton/prowrt/actions/runs/44577868930)已通过，耗时 3 分 57 秒，完成每次终端登录、空密码拒绝、DNS 接管、源 IP 保留和规则关闭/恢复检查。该回归仍不替代正式镜像的 Mac 验收。正式镜像的[GHCR 发布与摘要回拉校验](https://github.com/jearton/prowrt/actions/runs/44578122539)也已通过，公开不可变引用见[发布文档](releases.md)。

## 2026-11-23 ProWrt 改名后的回归底座

[45121852164](https://github.com/jearton/prowrt/actions/runs/45121852164) 已成功从改名仓库下载旧镜像，并通过独立 `luci-app-technitium` 发布包校验；随后外部 `px5g-mbedtls-13.apk` 与原固定 SHA256 不符，任务在启动 VM 前退出。不能把该失败记为固件启动失败。

回归底座更新为保留的 `v25.12.6-20261120.2` Release，镜像 SHA256 为 `c0f28710b3f6430699772bf9b8d4f9cd888e88aafd7e4d71e4f681f0982dff11`。该镜像已包含从固定源码构建的证书工具，因此移除外部 px5g/OpenSSL APK 下载；仍独立下载、校验并安装三个 Technitium APK，清空 DNS 状态后重启复验初始化。原有 DNS、重定向、HTTP/HTTPS、终端登录与权限断言保留。历史 Release 及其附件不作修改。
