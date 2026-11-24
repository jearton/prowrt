# 构建缓存、耗时和 ProWrt 版本

本页描述新增的构建机制；已发布的历史镜像不会自动获得版本文件。实际冷、热构建耗时须以相应 Actions run 和 `build-metrics` 附件为准，不能把单元检查当作完整固件验收。

## 查询固件版本

- LuCI：进入「状态 → 概览」，查看 ProWrt 区块的版本、源码提交、源码时间、目标和 CI 运行编号。
- 命令行：`prowrt-version` 查看完整摘要，`prowrt-version --short` 只输出版本，`prowrt-version --json` 输出原始 JSON。
- 离线排查：读取 `/rom/usr/share/prowrt/build.json`；没有 `/rom` 的运行方式回退到 `/usr/share/prowrt/build.json`。
- 历史镜像没有此记录，不能只根据 OpenWrt 底座号推断 ProWrt 定制版本。

`VERSION` 是发布号的唯一维护入口，格式为 `25.12.6-20261123.1`，Git tag 加 `v` 前缀。相同发布号不能发布不同固件。源码提交、OpenWrt 底座、锁文件摘要和 CI run 由构建脚本自动生成。源码时间是提交时间，不冒充编译完成时间；实际执行时间见 Actions 和耗时报告。

版本记录属于固件身份，不加入 `/etc`、UCI 或配置备份清单。CLI 和 LuCI 优先读取只读 `/rom`，防止恢复旧 overlay 中的同名记录后显示旧版本。没有修改 `DISTRIB_RELEASE`、OpenWrt 软件源 URL、Technitium 或 Console 源码。

## 缓存边界

- `dl/`：OpenWrt 原生下载目录，原配方的摘要检查继续生效。保存前按文件更新时间淘汰至 2 GiB。
- `assets/`：iStoreOS UI 来源镜像，使用完整 SHA-256 命名；每次命中重新核对内容，损坏时重新下载，临时下载完成且通过摘要校验后才替换。保存上限为 512 MiB。
- `ccache/`：C/C++ 编译缓存，上限 2 GiB；使用 compiler content 检查，源码、头文件及编译选项仍由 ccache 检查。
- 不保存整个构建树、host 工具安装目录、staging_dir、build_dir、根文件系统、旧 `files/`、运行配置、密钥或凭证。
- 编译缓存按 runner OS、架构、主机 GCC 版本、全部来源锁和构建配置摘要分区。修改 `VERSION` 不会让编译缓存整体失效。
- 下载缓存按 OS、架构恢复，跨来源版本时仍检查原始摘要。缓存 miss 不影响正常完整构建。
- 使用 run ID / attempt 创建不可变缓存快照，兼容前缀恢复最近的快照。只有 `main` 保存缓存，分支手动构建只读取。
- 下载与编译缓存合计最多约 4.5 GiB/次快照；GitHub 仓库配额和淘汰策略仍然适用，不保证每次都能命中。

CI 缓存位于 `$RUNNER_TEMP/prowrt-cache`，新源码树位于 `$RUNNER_TEMP/openwrt`，保持现有禁止复用旧构建树的检查。构建完成后、VM 验收前保存可复用输入；失败的 VM 不会产生正式版，缓存本身也不作为固件验收证据。

Linux 手动构建可以显式指定独立目录；构建目录与输出目录必须不存在，缓存路径不允许空格、shell/make 展开字符或与这两个目录互相包含：

```sh
OPENWRT_CACHE_ROOT=/srv/prowrt-cache \
OPENWRT_METRICS_DIR=/srv/prowrt-metrics/run-001 \
  ./scripts/build-full.sh /srv/builds/prowrt-001 /srv/artifacts/prowrt-001
```

手动构建不指定缓存路径时保留 OpenWrt 自身的临时下载与 ccache 行为。正式验收要求源码目录干净，禁止将未提交修改或不匹配 `GITHUB_SHA` 的 checkout 发布为正式固件。

## 耗时验证

- `build-metrics.json` 记录主机 CPU 数、架构、runner image、可用空间、恢复的缓存 key，以及来源准备、定制文件、配置、下载、编译、导出验证和隔离启动耗时。
- `ccache.txt` 记录本次运行的缓存命中/未命中统计，不把历史累计值当作本轮收益。
- 即使编译失败也尽力保留阶段耗时和统计。完整日志仍留在 Actions，报告不上传固件运行状态或凭证。
- cache restore/save、主机准备和上传耗时查看 Actions 的独立步骤。比较总耗时时必须包含这些开销，不能只比较编译阶段。
- 首次运行用于生成缓存；之后用相同源码、相同 runner 类型再构建一次，比较端到端耗时、命中率和所有验收项。未完成该对比前不宣称已实现具体提速比例。
- 根文件系统权限、469 包基线及允许的变更、内核模块 ABI、IPv6 禁用和全新 VM 服务检查继续执行。

配置预检工作流在 Linux 上执行实际来源准备、自定义配方安装和 `make defconfig`，检查必需包和外部缓存路径后停止，不生成固件。`feeds uninstall` 会刷新已存在的 `.config`，因此权威 profile 只能在全部自定义配方安装后写入；缓存目录的预先准备不会提前创建 `.config`。此检查用于在 PR 阶段发现选择丢失，不能替代后续完整编译或 VM 验收。

### 同一源码的冷、热构建结果（2026-11-24）

两次均构建 `bdb92fcdbf5fa834cf061ce0f70fa9d742c65b47`，使用 Ubuntu 24.04 的 4 CPU runner，完整编译、清单／ABI 检查和隔离首次启动均通过。

| 指标 | [冷构建 45199745484](https://github.com/jearton/prowrt/actions/runs/45199745484) | [热构建 45217015340](https://github.com/jearton/prowrt/actions/runs/45217015340) |
| --- | --- | --- |
| 恢复已有缓存 | 无 | 恢复前次下载与编译缓存 |
| 编译阶段 | 78 分 06 秒 | 50 分 07 秒 |
| 完整 build job，包含缓存和上传步骤 | 88 分 25 秒 | 62 分 16 秒 |
| 本轮可缓存编译命中 | 4,509 / 40,344（11.18%） | 40,249 / 40,344（99.76%） |

本次对照中，编译阶段缩短 35.8%，完整 job 缩短 29.6%。冷构建的命中来自同一轮内部复用，不代表恢复过历史缓存。热构建仍有 15,425 次不可缓存调用，工具链准备、链接、打包、验证和上传也继续耗时；缓存命中率不能直接当作总耗时降幅。两次不是同一物理 runner，此结果是实际记录，不是每次构建的耗时保证。

原始阶段记录和本轮 ccache 统计见 [冷构建](evidence/build-cache-20261124/cold.json)、[热构建](evidence/build-cache-20261124/warm.json)、[冷 ccache](evidence/build-cache-20261124/cold-ccache.txt)、[热 ccache](evidence/build-cache-20261124/warm-ccache.txt)。后续面板版本变更的构建不混入这组同源码对比。

## 发布检查与回滚

新固件包包含镜像、APK 清单、`build.json` 和 `SHA256SUMS`。`build.json` 与镜像内记录逐字段一致，三个数据文件均列入校验和；固件不能在内部包含自身的最终 SHA-256，最终摘要保存在外部 `SHA256SUMS`。

发布工作流从 tag checkout，要求 `tag == v + VERSION`、嵌入源码提交等于该 checkout，并验证锁定输入、实际磁盘根分区内的记录与附件一致。使用相同构建产物完成候选晋升，不为“正式版”另改版本文件或重新打包。正式 Release 与 GHCR 使用同一组文件；匿名下载后重新验证。

历史 tag、Release、GHCR 路径与附件保持原样，历史 tag 上的原验证流程继续有效。回退代码时使用新的 revert 提交；缓存格式不兼容时递增 `prowrt-v1` / `prowrt-downloads-v1` 命名空间，不恢复旧根文件系统。固件运行异常时回到保留的旧镜像和对应配置。
