# 固件发布与下载

ProWrt 在 GHCR 仅发布一种制品：定制固件包，包含 EFI 镜像、APK 软件包清单和 SHA-256 校验和。统一路径为 `ghcr.io/jearton/prowrt`，正式版和 CI 候选用 tag 区分。使用 ORAS 下载并核对校验和：

```sh
oras pull ghcr.io/jearton/prowrt:v25.12.6-20261120.2
sha256sum -c SHA256SUMS
```

当前统一路径的不可变下载引用：

```sh
oras pull ghcr.io/jearton/prowrt@sha256:225bfe83d665046f748fc822b323f68493b15f20036b535bfb575b04950ed31a
```

2026-11-23 的[发布验收](https://github.com/jearton/prowrt/actions/runs/45124061421)已通过：使用空 registry 凭据配置匿名完整拉取，再核对 SHA-256 和 gzip 完整性。三个文件与两条旧路径的内容完全一致，详见[发布证据](evidence/ghcr-root-20261123/publication.json)。此次只调整发布路径，固件内容和版本不变。

此前 `/firmware` 路径的不可变下载引用继续保留：

```sh
oras pull ghcr.io/jearton/prowrt/firmware@sha256:6da4b4c51cd088e2afb5e2aafdd551b24f25881abd2058f69499a529c9822c9a
```

也可以从 [v25.12.6-20261120.2 的 GitHub Release](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120.2) 直接下载镜像和 SHA-256。

安装或升级前，先在隔离环境复验 EFI 启动、IPv6 禁用、LuCI 和 DNS。保留旧磁盘和配置备份。具体步骤见[固件方案](firmware.md)。

本次镜像由 189 Linux 构建并在独立 VM 全新安装，完成 Netdata 预置概览的离线、无云账号、独立 Chrome/Safari 与重启验收。[本轮记录与截图](netdata-overview-acceptance-20261120.md)。完整源码 CI 构建和发布附件/GHCR 校验属于独立流程，不能将浏览器 CI 通过表述为完整源码 CI 已完成。

本次[GHCR 发布工作流](https://github.com/jearton/prowrt/actions/runs/44681488699)已完成：下载 Release、核对 tag 上清单、推送 OCI，并按摘要重新拉回验证。匿名访问也已核对 7 个 Release 附件摘要及 3 个 OCI layer。[发布证据](evidence/netdata-overview-20261120/publication.json)。当时发布的旧命名空间不可变引用（改名后继续保留）：

```sh
oras pull ghcr.io/jearton/openwrt-pro/firmware@sha256:18298a9616ea62f169e96cdfe7b7e475e988bc11e7e69f23d231d1edc65b2308
```

本次源码版本的[完整源码 CI 重建](https://github.com/jearton/prowrt/actions/runs/44681072770)已成功，独立于此前完成的 189 构建与最终镜像 VM 验收。

上一版 [v25.12.6-20261120](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120) 的附件和 OCI 摘要保持不变。

## ProWrt 改名与历史发布

2026-11-23 项目更名为 ProWrt，仓库为 `jearton/prowrt`。改名阶段使用 `ghcr.io/jearton/prowrt/firmware`，随后统一简化为 `ghcr.io/jearton/prowrt`；正式版与 CI 候选均发布到该单一固件制品路径。此前两条 `/firmware` 路径的版本和摘要保留。已有 Release、Git tag、附件名称、内容和校验和不变。新命名空间可以使用同一历史版本标签重新发布经过校验的附件；OCI 来源等元数据随仓库名变化，新 OCI manifest 摘要须单独核对，不能沿用旧摘要。改名阶段已通过[发布与回拉](https://github.com/jearton/prowrt/actions/runs/45121685855)、[空凭据匿名全量拉取](https://github.com/jearton/prowrt/actions/runs/45122617287)以及[首次启动回归](https://github.com/jearton/prowrt/actions/runs/45122212857)。详见[迁移与验证](prowrt-rename-20261123.md)。

当前路径调整、历史保留和匿名下载校验见 [GHCR 路径记录](ghcr-root-20261123.md)。

## 持续集成

推送到 main 或创建 PR 后，GitHub Actions 检查清单摘要、Netdata 补丁、构建缓存边界、固件身份检查和 Compose 的回环端口映射。完整构建加入持久下载与 ccache，输出阶段耗时，但不跳过完整编译和隔离启动检查。[缓存和版本机制](build-cache-and-version.md)

新增版本机制的发布包包含镜像、APK 清单、`build.json` 和 `SHA256SUMS`。发布工作流核对外部校验和、gzip、tag / VERSION / 源码提交，并从实际磁盘根分区读取内嵌身份与附件比较；发布为 GHCR 同名版本后按 OCI 摘要拉回核验。历史 tag 使用各自原有的三文件流程。发布后再用空 registry 凭据配置匿名解析、按摘要拉取并复验；手动执行时可启用 `verify_only`，只检查已有公开制品，不重新推送或改写版本。

## 25.12.6-20261124.1 候选

尚未发布。候选将包含独立锁定的 Zashboard 3.30.0 和 MetaCubeXD 1.276.0，保留官方稳定 Mihomo 1.19.34；同时包含前序的 DNS 默认策略、版本元数据和构建缓存调整。用户已确认面板交互验收通过，[打包和验收记录](openclash-dashboards-20261124.md)与[逐项补丁清单](../patches/README.md)分别维护。

正式发布必须使用包含面板改动的同一干净源码提交构建，并完成镜像身份、包清单、全新启动、隔离服务验证及匿名下载校验。先前成功的 CI 构建不包含本次面板更新，不能作为该候选的发布附件。

## 发布下一版

1. 在构建前修改 `VERSION`，提交本次源码和配置；从干净的提交按[构建步骤](firmware.md)在 Linux 构建和验收固件。构建产物内含该提交及版本。历史 `manifests/` 继续作为包版本基线，允许差异由构建脚本显式维护；新镜像的最终摘要使用构建产物自己的 `SHA256SUMS`，不要为写入镜像摘要再创建一个提交并把它误当成镜像源码。
2. 对实际构建的同一个源码提交创建 `v` 加 `VERSION` 的 Git tag，例如 `v25.12.6-20261123.1`。不能把候选产物挂到另一个提交上发布。
3. 用同名 tag 创建 GitHub Release，将同一次验收产物的以下四个文件原样上传并发布：
   - `openwrt-x86-64-generic-squashfs-combined-efi.img.gz`
   - `openwrt-x86-64-generic.manifest`
   - `build.json`
   - `SHA256SUMS`
4. 查看 **Publish ProWrt firmware to GHCR** 的 Actions 日志。重新发布已存在的 Release 可通过工作流的手动触发入口执行。新的固件内容使用新版本 tag。

完整定制版的构建入口为 **Build full firmware and publish candidate**。工作流在 GitHub 托管的 Linux x86_64 runner 上编译，对照已发布的 APK 清单和构建脚本声明的差异逐项检查名称与版本，并验证所有内核模块的 ABI。通过后生成 `ci-运行编号-尝试次数` 的 GHCR 候选镜像。手动重跑从 Actions 的 workflow_dispatch 入口进入。命名 Release 的发布流程见上文。首次创建的 GitHub Package 默认私有，公开仓库的所有者可在该 Package 的设置里将它切换为 Public。[GitHub Packages 可见性说明](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility#configuring-visibility-of-packages-for-your-personal-account)
