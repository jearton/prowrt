# OpenClash 面板升级与验收

## 版本与来源

| 组件 | 原内置版本 | 本次锁定版本 | 来源 |
| --- | --- | --- | --- |
| OpenClash | 0.48.002-r1 | 0.48.002-r2 | [官方 v0.48.002](https://github.com/vernesong/OpenClash/releases/tag/v0.48.002)，r2 为本项目包修订 |
| Zashboard | 1.48.0 | 3.30.0 | [官方 Release](https://github.com/Zephyruso/zashboard/releases/tag/v3.30.0) 的完整 dist.zip，包含本地字体 |
| MetaCubeXD | 实际入口 1.176.0 | 1.276.0 | [官方 Release](https://github.com/MetaCubeX/metacubexd/releases/tag/v1.276.0) 的 compressed-dist.tgz |
| Mihomo | 1.19.34 | 1.19.34 | 官方稳定核心，未切换 Smart |

此前仅锁定 OpenClash 配方来源，没有独立审查其中携带的面板版本；上游配方的新版本不代表内置静态面板同步更新。旧 Zashboard 入口与所锁定的上游 OpenClash 提交逐字节一致；本次增加独立来源锁，避免再次仅凭插件版本推断面板版本。

两个面板的版本、tag、提交、附件 URL 与 SHA-256 记录在 [ui.lock.json](../sources/full/package/custom/luci-app-openclash/ui.lock.json)。安装时验证摘要、压缩包路径、文件类型和本地入口资源，再整体替换目标目录；没有修改官方分发的 JavaScript。所有更新应同时增加 OpenClash 包修订号，防止已安装设备将新资源误认为相同包版本。

## 已确认的验收与边界

- 用户于 2026-11-24 明确确认面板交互验收通过。
- 实际官方压缩包已通过安装工具检查，旧目录中的遗留分块被移除，入口依赖资源均位于本地。
- Mac Chrome 通过同一官方 Mihomo 1.19.34 后端对照，后端建立 2,250 条真实 HTTP CONNECT 连接，目标仅为隔离测试进程的回环监听。
- 首轮 12 秒稳定窗口内，Zashboard 1.48.0 出现 6 次超过 500 ms 的长任务，最长 2,305 ms；3.30.0 同一窗口为 0 次长任务。这项结果是面板性能检查，不能代替最终固件启动或业务网络验收。
- 浏览器自动化首次用错了 MetaCubeXD 查询参数位置：新版 Nuxt 使用 hash 路由，应沿用 OpenClash 原生生成的 `/#/setup?hostname=...&port=...`。已修正测试工具以直接调用原生链接生成器，不据此给面板或 OpenClash 增加兼容补丁。
- 最终固件的包版本、首次启动和发布校验结果须记录到对应 Release。本文不把本地分支或旧版 CI 构建标为已发布镜像。

## 可重复检查

```sh
python3 -m unittest discover -s tests -p 'test_openclash_ui.py' -v
python3 scripts/check-openclash-ui.py /tmp/prowrt-ui-check
```

浏览器性能与缓存迁移工具为 [check-openclash-browser.cjs](../scripts/check-openclash-browser.cjs)，后端由 [openclash-ui-fixture.py](../scripts/openclash-ui-fixture.py) 提供；仅在已授权的隔离 Linux 环境启动官方 Mihomo。测试监听仅限回环，默认十分钟自动清理。不要将实验控制端口开放到 LAN/WAN；Mac 不执行 Docker 构建。

## 回滚与其他组件

- 升级前保留旧 APK、固件和配置，回滚可安装旧包或挂回原系统盘；本项目不在浏览器升级检查中清除用户的 localStorage。
- 本次仅更新两个面板，GeoSite、Country.mmdb 和系统依赖没有随之升级，不能表述为 OpenClash 的所有依赖均为最新。
- 来源访问控制与 LAN DNS 重定向是独立功能，见[逐项补丁清单](../patches/README.md)。严格来源准入的上游 Dev 独立复现仍待完成，尚未作为确认的上游 bug 提交。
