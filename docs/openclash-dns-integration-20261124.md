# OpenClash 原生 DNS 模式扩展与升级维护

适用候选：ProWrt `25.12.6-20261124.2`、OpenClash `0.48.002-r3`。本页区分原生配置预设、必要的联动补丁和验证结果；未发布前不表示历史镜像已更新。

## 界面与行为

在 **服务 → OpenClash → 插件设置 → DNS 设置 → 本地 DNS 劫持** 中保留三个原生选项，增加「使用 Technitium 转发」「使用 AdGuard Home 转发」。不再另设一套分流开关或主 DNS 服务选择器。

- Dnsmasq 转发：沿用原生 dnsmasq 配置修改及恢复行为。
- 防火墙转发：沿用原生直接送到 Mihomo DNS 端口的行为。
- Technitium／AdGuard 转发：普通 DNS 进入本机 53，再由所选主 DNS 转给 Mihomo；启动时检查监听并校正全局上游。
- 启动流程中的配置检查、API 或防火墙校正失败会明确报错，不静默回退公共 DNS。
- 停止 OpenClash 保留主 DNS 上游及本机 DNS 规则；有效缓存、本地区域继续可用，依赖核心的未缓存公网查询会暂时失败。
- 切换为「禁用」或原生模式后，只停用本功能管理的重定向，不自动恢复公共上游，不删除管理员的独立防火墙规则。

新装预选 Technitium 转发，OpenClash 本身仍默认停用。尚未完成配置并启动核心的新装系统，Technitium 继续使用原有首启公共 DoT 上游，不能只因预选菜单就被转到空端口。升级已有系统保留其 OpenClash 配置，不强行切换模式或替换管理员的自定义覆写脚本。

## 多区域与双 DNS 入口

- 首次选择所有内网来源防火墙区域，支持多选并保存。普通新装默认 `lan`；内部上联可由管理员明确选入，不按网口名称推断可信程度。
- 来源网段可留空，表示所选内网区域的全部来源，不写死为某个维护 IP。
- DNS 入口支持多个本机 IPv4 地址；留空自动采用本机非回环 IPv4 地址。
- 直接查询这些入口时不改写目标地址；其余 IPv4 TCP／UDP 53 查询送到本机 53。自动模式使用内核本机 REDIRECT；手动指定入口列表时，以第一项为本地 DNAT 目标。接口地址变化后由 hotplug 更新入口集合，无需重启核心。
- DNS INPUT 放行仅涉及 53，不扩大 LuCI、SSH、5380、终端、监控或核心控制器的访问权限。
- 使用原生 fw4 配置；已存在的本地 53 接管规则会被检测并复用，其来源限制仍由原规则管理。原有规则目的地冲突时拒绝叠加规则，提示管理员先处理。
- 旧 ProWrt 的标准 LAN DNS 规则在形状一致时可由新模式接管管理；自定义站点规则不会被整份覆盖。
- OpenClash 代理链提前放行普通 53，交给本机 DNS 规则，避免透明 UDP 接管绕过主 DNS；不处理主 DNS 到回环 7874 的内部链路。
- 此功能不宣称接管 DoH、DoT、IPv6 或不经过路由器的流量。

物理现场的 `core`、`ikuai`、`lan` 和双入口仅用于设计核对，不写入通用固件。现场当前由同一 Technitium 服务监听两个地址，不能当作双实例容灾。

## DNS 分流使用原生预设

路径：**服务 → OpenClash → 覆写设置 → DNS 设置**。

1. 导入自己的订阅／配置并使用 Redir-Host。
2. 在原生自定义 DNS 服务器列表中编辑预置的 Google、Cloudflare DoH，分别在「指定代理组」选择订阅已有组；固件不创建或写死代理组。
3. 打开原生「自定义 DNS」和「Nameserver-Policy」；默认预置 `geosite:cn` 通过 AliDNS、DNSPod DoH 直连，Bootstrap 使用 AliDNS IP DoH。
4. 不追加 WAN DNS、默认 DNS，`respect-rules=false`。DNS 出口由原生条目的 `#代理组` 指定。
5. 原生自定义覆写脚本预置独立节点域名 DNS（AliDNS／DNSPod DoH `#DIRECT`），替换原生策略文件中的域名策略，并清理订阅遗留 `fallback`、`fallback-filter`、`proxy-server-nameserver-policy`、`direct-nameserver`、`direct-nameserver-follow-policy`。
6. 启动前只读检查原生选择是否存在、生成结果是否保留所选组；检查脚本不生成 DNS 分流、不改业务组、节点或 rules。未选组或组已删除时阻止启用预设，不静默降级直连。

预置字段是普通 OpenClash UCI 条目、策略文件与原生覆写脚本，用户可以在原生入口维护。关闭／移除预置条目后仍可采用自己的原生 DNS 配置。共享缓存的这套预设要求 Redir-Host，不静默切换 Fake-IP；Fake-IP 的客户端分组方案单独配置。

TLS 证书校验保持开启。DNSSEC 的固件默认值仍为关闭，这不是修复污染的方法。缓存、TTL、serve-stale 均不被联动改写；已有答案仍按原缓存生命周期存在。

## API、凭证与生命周期

- API 只连接 `127.0.0.1`，可设置实际管理端口。默认 Technitium 5380、AdGuard Home 3000；该字段不改变服务端口。
- Technitium 使用原生 API token，或在初始密码仍有效时使用现有初始密码文件。AdGuard Home 使用其账号密码。
- 凭证目录 `/etc/openclash/dns-link/` 为 0700、凭证为 0600；空白密码字段保留已保存值，不写入 UCI 或命令行参数。
- 启动流程在核心启动前校正上游，就绪后读回；正确时不写。核心随后启动失败也不恢复公共 DNS。
- 复用既有 OpenClash watchdog 检查偏离；主 DNS 的包 init 增加一次有上限的启动校正，不新增 cron 或常驻轮询。
- 仅保存新服务选择不会借用旧服务的激活记录；新服务由下一次启动流程激活。
- 认证失败记录阻止反复登录，也不会把校正失败返回为启动成功。
- Technitium 只写 `forwarders` 和 `forwarderProtocol`。AdGuard Home 更新全局 `upstream_dns` 并清空 `fallback_dns`，保留 `[/域名/]` 条件转发。存在外部 `upstream_dns_file` 时拒绝自动接管，提示先迁移，避免覆盖文件内的业务规则。区域、客户端例外、DHCP、过滤、缓存和管理员设置保留。
- Technitium Server、Console、AdGuard Home 程序源码均未修改。固件包 init 回调修订为 Technitium `15.6.2-r3`、AdGuard Home `0.107.79-r2`；独立 `luci-app-technitium` 发布不因此改变。

查看：插件设置中的最近应用状态；`ruby /usr/share/openclash/dns_link.rb status`；`logread -e openclash-dns-link`；`/tmp/openclash.log`；网络 → 防火墙 → 端口转发／通信规则／IP 集合。状态记录不是替代实时原生 API 回读的健康探针。

回滚：先关闭新模式，按 `/etc/openclash/dns-link/before-<服务>.json` 通过主 DNS 原生界面恢复原上游；按私有 `firewall-before` 快照审阅并只恢复本功能涉及的规则，不能整份覆盖后续网络修改。首次修改前的值与配置保留在 root 专用目录，禁止公开上传。固件异常使用保留的旧镜像及对应配置。

## 超过 100 KiB 的 YAML

- LuCI 对 multipart 普通字段有 100 KiB 限制。只读运行 YAML 曾随表单提交，现场 145,967 字节运行配置导致 parser 报错；源文件为合法 159,133 字节 YAML。
- 只读模板保留 DOM ID、显示和比较，去掉提交 name。
- 源文件保持原生文件流式提交与 CSRF 校验，不放大全局限制、不写 marker。
- 提交辅助脚本缺失、文件传输不支持或提交取消时保留编辑内容，无法安全传输就阻止应用。
- 包修订号加入资源 URL，避免继续使用旧辅助脚本。

## 以后升级 OpenClash

- 独立补丁和清单：`patches/openclash/0001-prowrt-integration.patch`、`series.json`。
- 构建入口先运行 `scripts/prepare-openclash.py`：自动重放或验证补丁，核对版本、兼容文件和修补后的摘要；不兼容则中止，不发布缺补丁的镜像。
- CI 用未打补丁的基线重放，再次重放检查幂等性，修改兼容输入确认拒绝。后续升级上游必须更新已审阅的来源／兼容清单并通过相关验收。
- 固件内保存公开集成标识 `/usr/share/prowrt/openclash-integration.json`。
- 首启通过 APK 原生事务将定制 OpenClash 固定到明确版本，避免普通 `apk upgrade` 静默换为未适配包；不改 APK 数据库。
- 上游一键插件更新被阻止，并提示使用 ProWrt 发布渠道。核心与面板更新入口不因此被当作插件更新拦截。
- 升级 OpenClash 走经过 ProWrt 补丁适配的新固件。显式解除版本约束或强制安装未适配官方包会覆盖补丁，不属于支持的保留路径。
- APK 约束回滚：在明确准备切换到上游包时执行 `apk add luci-app-openclash` 解除精确版本要求；这不是正常 ProWrt 升级步骤。

## 验证记录

本轮在历史镜像的隔离工作盘上覆盖候选源码验证，尚不等于最终固件镜像验收：

- 原生 LuCI 保存／应用 243,271 字节合法 YAML，文件 SHA256 完整一致，新增 REJECT 规则实际生效。
- 原生 DNS 条目选择已有 `CI` 代理组，生成结果保留指定出口；未选／不存在的组由只读检查拒绝。
- 两个虚拟接口、两个本机 DNS 地址，UDP／TCP 查询与外部目的地 53 拦截通过；直接查询本机地址未增加 DNAT 计数。
- 使用额外来源网段从内部上联查询成功，未限定为上联对端地址；5380 管理访问仍被拒绝。
- 接口地址增删触发入口集合刷新，Mihomo PID 保持不变。
- Technitium 原生 API 和带密码、ujail 运行的 AdGuard Home API 校正及停止不回退通过，AdGuard 条件转发保留。
- APK 精确版本事务及阻止未适配一键插件更新已在工作盘验证；最终 r3 包固定仍须在新镜像中复验。
- Ruby 单元检查 10 项、42 个断言；服务启动回调与补丁重放／版本拒绝检查均通过。

最终镜像构建、默认首启和 Mac 浏览器验收结果将在完成后补充。
