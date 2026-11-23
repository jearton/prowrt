# ProWrt 项目改名

本文记录改名当时的 `/firmware` 发布路径；当前统一使用 `ghcr.io/jearton/prowrt`，旧路径保留。见[后续路径调整](ghcr-root-20261123.md)。

2026-11-23 将项目名称统一为 **ProWrt**，GitHub 仓库由 `jearton/openwrt-pro` 更名为 [`jearton/prowrt`](https://github.com/jearton/prowrt)。这是仓库和交付命名调整，已发布固件的 OpenWrt 底座、软件包与运行配置不因改名而改变。

## 调整范围

- README 项目名、说明及文档链接统一使用 ProWrt / `jearton/prowrt`。
- Git remote 使用 `git@github.com:jearton/prowrt.git`。
- Technitium 回归工作流通过 `$GITHUB_REPOSITORY` 获取本仓库历史镜像；独立插件仍从 `jearton/luci-app-technitium` 获取。
- Release 发布工作流继续按 `$GITHUB_REPOSITORY` 生成 GHCR 路径，新路径为 `ghcr.io/jearton/prowrt/firmware`。
- 完整构建工作流本来就按仓库变量生成候选制品路径，无需为改名重新编译相同固件。
- `luci-app-technitium` 的仓库、名称和源码锁保持独立。

## 历史保留

4 个既有 Release、5 个 Git tag 及全部 16 个附件保留，不能重打标签或覆盖镜像。历史制品文件名仍使用 `openwrt-x86-64-...`，与既有校验脚本和安装方式兼容。

旧 GHCR 包继续保留，原不可变引用为：

```sh
oras pull ghcr.io/jearton/openwrt-pro/firmware@sha256:18298a9616ea62f169e96cdfe7b7e475e988bc11e7e69f23d231d1edc65b2308
```

`docs/evidence/netdata-overview-20261120/` 中的原始发布证据保留当时的旧仓库和 GHCR 地址，不将历史凭据改写成新地址。

## 验证与回滚

改名前保存仓库身份、Release/附件清单、tag 提交和旧 GHCR manifest；迁移后逐项核对。用相同历史 Release 的附件在新 GHCR 路径发布，再按 OCI 摘要拉回，检查镜像、APK 清单和 SHA256SUMS；新来源元数据使 OCI manifest 摘要与旧值不同，固件文件摘要须保持一致。

回滚时将仓库名称改回 `openwrt-pro`、恢复 Git remote，并 revert 本轮命名提交；不删除新旧发布包或改写 tag。已安装的路由器不受仓库名称回滚影响。

## 迁移结果

仓库 ID `1461569182` 保持一致。4 个 Release 的名称、说明、发布时间和 16 个附件的 ID、名称、大小、摘要均与改名前一致；5 个 tag 的提交 SHA 保持一致。[历史清单核对](evidence/prowrt-rename-20261123/history.json)。

[ProWrt GHCR 发布任务](https://github.com/jearton/prowrt/actions/runs/45121685855)已完成附件下载、校验、发布及按 OCI 摘要回拉验证；[步骤结果](evidence/prowrt-rename-20261123/publication-ci.json)。新不可变引用为：

```sh
oras pull ghcr.io/jearton/prowrt/firmware@sha256:6da4b4c51cd088e2afb5e2aafdd551b24f25881abd2058f69499a529c9822c9a
```

新旧 GHCR 均可匿名读取，三个 payload layer 完全一致；变化仅为 OCI 来源等发布元数据，不能将新旧 OCI manifest 摘要混用。原始改名 API 因当前 PAT 缺少仓库管理写权限返回 403，已通过仓库所有者的 GitHub 设置页完成改名和简介更新。

改名后首次启动回归发现外部证书工具 APK 与原固定摘要不符，失败发生在启动 VM 前。已将 CI 底座改为包含证书工具的固定历史 Release，保留独立插件下载与原有功能断言。过程见 [CI 记录](ci-acceptance.md#2026-11-23-prowrt-改名后的回归底座)。

调整后的[首次启动回归 45122212857](https://github.com/jearton/prowrt/actions/runs/45122212857)已通过，覆盖新仓库下载、独立插件校验、全新 DNS 状态初始化、IPv4 LAN、DNS 重定向及源 IP 保留、LuCI HTTP/HTTPS、终端系统认证和访问权限。[步骤证据](evidence/prowrt-rename-20261123/firstboot-ci.json)。

[匿名全量下载验证 45122617287](https://github.com/jearton/prowrt/actions/runs/45122617287)已通过：使用空的 registry 凭据配置、禁用本地 ORAS 缓存，按摘要完整拉取镜像、APK 清单与 SHA256SUMS，再核对文件内容和 gzip 完整性。本次使用 `verify_only=true`，发布步骤明确跳过，未改写既有版本。[步骤证据](evidence/prowrt-rename-20261123/anonymous-ci.json)、[新旧制品对照](evidence/prowrt-rename-20261123/publication.json)。
