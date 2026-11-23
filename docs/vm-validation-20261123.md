# 2026-11-23 候选配置隔离验收（进行中）

本轮基于 20261120.2 验收盘的冷复制工作盘，测试当前源码的 DNS 默认策略和 OpenClash 适配。尚未完成最终镜像重装验收，尚未发布新镜像。禁止用本记录中通过的单项推导全部功能已经通过。

## 范围与恢复点

- 9000 原盘 21 冷复制为工作盘 22，比较字节及 SHA256 一致后启动工作盘。
- 9001 为独立 Debian 客户端；实验 LAN 为 192.168.77.0/24。
- vmbr99 没有宿主地址、物理上联；两台 guest 禁用 IPv6。
- 不修改生产 DNS、Headscale、交换机或 Tailnet。
- 原盘、旧发布保留；测试服务和配置分别备份、恢复并回读。

## 当前通过项

| 项目 | 实际验证 | 边界 |
| --- | --- | --- |
| 公网默认策略 | DNSSEC 关闭，AliDNS＋360 DoT，开启并发、并发数 2；9001 的 54 次 UDP/TCP 查询通过，每轮清空缓存 | 当前实验出口，不能保证所有大陆网络的上游可用性 |
| 真正并行 | 两个受控上游记录请求到达时间；两次差值为 0.043 / 0.121 ms，均在首个答案前到达；交换快慢上游后仍成立 | 测试临时使用 UDP stub，结束恢复双 DoT 并回读 |
| 双上游故障切换 | 分别阻断 AliDNS / 360 的 TLS 端口，另一个仍能回答 | 不把双上游视为严格主备顺序 |
| 原生 DNSSEC 开关 | 临时启用且仅使用经本轮验证的 360 DoT；example.com 返回 AD，dnssec-failed.org 返回 SERVFAIL；结束恢复默认关闭 | 验证开关及本轮路径，不代表所有上游都提供完整证明 |
| 区域和记录 | 新建 Primary；两条 A、CNAME、TXT，实际查询比对 | 测试区域已清理 |
| 已落盘区域备份恢复 | 核对备份含目标 zone 文件；修改 A，实际恢复，原两条 A 重现 | 立即备份存在下节限制 |
| DHCP 名称 | 9001 的设备名 A 和租约 PTR 通过 | dnsmasq 内部 5353，Technitium 条件转发 |
| 强制 DNS | 指定外部 TEST-NET DNS 的 TCP/UDP 53，均由本机回答；关闭规则后外部查询失败，本机直查仍成功；恢复后重验 | 保留原生规则开关 |
| WireGuard | netifd/UCI 配置、独立 Debian peer、握手、实际加密传输 1,474,953,216 字节；未登记源被拒；接口重启后恢复 2,275.9 ms | 虚拟路径，吞吐不是物理线速承诺 |
| OpenClash TCP 与 DNS 分组 | 白名单 Fake-IP、实际代理与 DIRECT 出口不同；非白名单真实 IP 和直连；强制 DNS 仍保留来源分组 | 已授权 TCP 节点；UDP 数据面另行验收 |
| OpenClash UDP 代理 | 独立 Shadowsocks UDP 对端，10 次 400 字节往返；非白名单的真实 IP 和 Fake-IP 请求被提前排除，核心只记录白名单来源 | 测试目标位于隔离 peer，本机防泄漏规则阻断任何目标直出 |
| Tailscale 完整链路 | 独立 Headscale 0.29.7 与 1.104.7 对端；真实隧道传输、ACL 拒绝、子网路由、IPv4 exit node、服务重启和身份保持通过；一次性注册 key 清理、DNS 未被接管 | 控制面和 peer 均在隔离实验网络；未加入生产 Tailnet |
| IPv4 透明监听 | 同一核心：`*` 复现 Redir UDP / TProxy `protocol not available`；`0.0.0.0` 与完整 OpenClash 启动均无该错误 | 内核 `ipv6.disable=1` |

## 新增源码调整

- **DNSSEC 默认策略**：仅修改固件首启初始化为关闭，原生后台和 Console 不改。
- **双加密上游**：AliDNS 和 360 DoT，按主机名验证证书，固定引导 IP。
- **并行查询**：启用 concurrent forwarding，Concurrency 为 2。
- **IPv4 监听**：内核不支持 IPv6 时，OpenClash 生成 `bind-address: 0.0.0.0`。
- **DNS 钩子顺序**：启用本地 DNS 重定向时，在 OpenClash 的 TCP/UDP 接管链前排除对应 LAN 的 53 请求，交给 fw4 本地重定向。
- **UDP 来源访问控制**：Fake-IP UDP 的 TProxy 接管移到来源准入之后，服从来源白名单。
- **包修订号**：OpenClash 0.48.002-r1 标识本项目配方调整，不冒充上游新版本。

## 原生备份限制：记录，不修后台

实测顺序：新建 `prowrt.test`，添加两条 A，查询成功，立即备份，修改 A，恢复备份。备份缺少新建区域，恢复后 NXDOMAIN。

源码依据：Technitium 15.6.2 的 [AuthZoneManager](https://github.com/TechnitiumSoftware/DnsServer/blob/v15.6.2/DnsServerCore/Dns/ZoneManagers/AuthZoneManager.cs) 将区域修改放入待保存集合，定时器为 5 秒；[DnsWebService.BackupConfigAsync](https://github.com/TechnitiumSoftware/DnsServer/blob/v15.6.2/DnsServerCore/DnsWebService.cs) 枚举磁盘 zone 文件写入 ZIP，没有先同步该集合。

用户明确选择“先记录，暂不修改后台”。因此未增加后台补丁，不将此项标为通过；写盘后的备份恢复是独立通过项。原始 ZIP 含服务配置，仅保存在私有验收目录，不上传仓库。

## 待完成

- 其余虚拟网络功能、备用服务和管理页面回归。
- 最终压缩镜像、包清单、内核 ABI、权限检查及全新系统盘启动验收。
- 测试环境回滚及 GitHub / GHCR 发布验收。

公开归一化证据放入 `docs/evidence/vm-validation-20261123/`；代理凭证、私钥、原始服务备份和认证信息不公开。
