# QuickStart 设备列表兼容修复

候选固件 `25.12.6-20261124.3` 尚未构建发布。界面包为 `luci-app-quickstart 0.12.10-r2`；QuickStart 后台继续是 `0.13.1-r2`。本次不修改 Go 后台二进制，不修改 Technitium 或 Console 源码，不修改 Netdata。

## 来源与每项修改

- 来源是 [固定 iStoreOS 镜像中的资产](../packages/istoreos-ui-2026110611/ui-source.json)，构建时校验原始 LuCI 控制器、模板和编译后 JS 摘要；不声称修改了未提供源码的 Go 服务。
- 原生后台在 lan 没有 ARP 记录时返回 `exit status 1`；只在已认证、HTTP 200、该确切错误、lan 有效且确实无邻居时，将它兼容为成功的空设备列表。
- 默认 lan 的成功列表保留原生设备、厂商与控制元数据。
- 可选择多个逻辑接口，从 ubus 解析到实际设备，只读取已完成的本地 ARP 条目，不主动扫描。
- 多接口或非 lan 的发现列表设为只读；拦截该模式下的原生 `/lanctrl/` 写请求，避免把原本只操作 lan 的配置误用到其他接口。配置请使用 OpenWrt、Technitium 等对应管理页。
- 真实后端错误、无效接口、响应解析失败明确显示；鉴权失败不转为成功响应，其他 API 继续原代理行为。
- 静态资源统一更新版本指纹，避免旧浏览器缓存仍使用吞掉错误的 JS。

## 使用

页面为 **首页 → 设备管理**，路径 `/cgi-bin/luci/admin/quickstart/devicemanagement`。不配置时沿用 `lan`。接口选择通过 UCI 维护，本次没有增加界面选择器，例如：

```sh
uci -q delete quickstart.main.device_interfaces
uci add_list quickstart.main.device_interfaces='lan'
uci add_list quickstart.main.device_interfaces='rescue'
uci commit quickstart
```

刷新设备管理页面即可。接口名须是实际存在的逻辑接口，最多 16 个；邻居列表最多 4096 项，超限明确报错。恢复默认时删除该项并提交。

跨三层终端没有本机 ARP，仍不会自动成为完整设备清单。本次没有集成交换机 SNMP、Technitium 租约或 nlbwmon 活跃 IP；nlbwmon 的按 IP 统计是另一项修复。列表为空也不代表终端离线。

## 验证与回滚

- 纯 Lua 检查空 ARP、接口选择、邻居过滤、保留元数据及鉴权／真实错误。
- 克隆隔离 VM 上复现原生 `exit status 1`，LuCI 返回成功的空数组。
- 选取 lan 和 wan 后实际返回两个接口的邻居；写请求收到 403，DHCP 配置摘要保持不变。
- 未认证请求继续失败，不返回兼容设备列表。
- Mac Chrome 显示两个接口的设备和只读提示；配置不存在的接口后显示明确错误；恢复默认 lan 后警告消失且正常列表恢复。

原 VM 磁盘保留；生产更新前须自行保存匹配的旧 APK。回滚安装旧 `luci-app-quickstart`，删除 `quickstart.main.device_interfaces`；如回退到旧版，空 ARP 错误也会恢复。测试不改生产设备、不刷整机。新固件仍需构建和整体验收后再发布。实际 API 与浏览器检查见[验收数据](evidence/quickstart-devices-20261124/acceptance.json)。
