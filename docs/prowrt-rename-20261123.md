# ProWrt 项目改名

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
