# uhttpd 网页停止响应：权限检查阻塞

截至 2026-11-26：隔离环境复现了与现场相同的阻塞路径，异步权限检查补丁及候选 APK 的相关验收通过。**现场第一次权限请求为何未收到完成回复，仍未定位。** 本项没有修改生产设备，没有自动提交、push 或发布新版完整固件。

## 证据与结论

- 现场 uhttpd 进程仍存在，监听队列积压，本机请求静态文件也超时；重启后恢复。没有 CPU、内存或文件描述符耗尽证据。
- 历史系统调用记录为 `poll`、1 个描述符、超时 `0x1b7740`，换算为 1,800,000 ms（30 分钟）。该记录没有保存 pollfd 内存内容，不能单凭它确定当时等待的文件描述符。
- 固件锁定 uhttpd `373145f72c884c36a2b16f7f47e74ffae06bd754`。其 HTTP UBUS 权限检查同步调用 `session.access`，超时为 `conf.script_timeout * 500` ms。
- OpenClash 原版安装脚本为流式日志设置 `script_timeout=3600`，因而权限检查超时变为 30 分钟。这段设置来自原版 OpenClash，并非本项目新增。
- `rpcd` 的 `session.access` 检查网页会话是否有权调用指定 UBUS 对象和方法。它不同于用户再次输入密码；例如已登录用户读取状态、执行管理操作仍须经过权限检查。
- 在独立 UBUS socket、独立 HTTP 端口上，让模拟权限服务暂不完成回复：原版 uhttpd 进入同样的 `poll(..., 1800000)`，静态文件请求 2 秒超时。正常权限回复时，原版可返回测试结果。
- 这证明同步权限等待能够阻塞整个 HTTP 事件循环，也与现场特征吻合；它**尚不能证明现场 rpcd 曾因哪项操作漏回、延迟或丢失回复**。`rpcd` 停在 `epoll_wait` 同样不能单独解释原因。

源码依据：[uhttpd ubus.c](https://github.com/openwrt/uhttpd/blob/373145f72c884c36a2b16f7f47e74ffae06bd754/ubus.c)、[锁定 libubus 请求实现](https://github.com/openwrt/ubus/blob/24864e78/libubus-req.c)。

## 本次调整（逐项）

1. 将旧式 JSON-RPC、REST 调用和订阅接口的 `session.access` 权限检查改为异步请求，等待期间继续运行 HTTP 事件循环。
2. 将权限检查超时独立设为 5000 ms，避免继承长时间流式日志的脚本超时；不改变 OpenClash 的流式日志配置。
3. 只有收到成功完成且 `access=true` 才执行操作。拒绝、缺失或超时回复都不能放行；调用接口超时返回 JSON-RPC 超时错误，订阅接口拒绝访问。
4. 等待期间复制会话、对象、方法与参数，绑定请求清理；客户端断开时取消异步请求和定时器。迟到回复不能执行已超时的操作。
5. 保留原版显式 `ubus_noauth` 行为；固件没有启用它，没有关闭认证，也不增加自动重启任务。
6. 固件准备脚本校验锁定 recipe 和补丁 SHA256，源码变化时停止构建，要求重新审查。`uhttpd` 与选中的 `uhttpd-mod-ubus` 构建版本调整为 `2026.08.24~373145f7-r2`，同步更新最终包清单期望值。
7. 增加按需取证脚本；不自动运行、不安装新常驻服务、不修改生产配置。

文件：`patches/uhttpd/100-async-acl.patch`、`patches/uhttpd/series.json`、`scripts/prepare-uhttpd.py`、`scripts/check-uhttpd.py`、`scripts/build-full.sh`、对应 CI 工作流、`scripts/capture-uhttpd.sh`。测试模拟服务位于 `tests/uhttpd-acl/mock.c`，不进入固件。

本补丁只消除这条同步 ACL 调用的阻塞。原版对象查找等其他同步 UBUS 操作仍存在；不能据此承诺任何 Web 故障都已消除。

## 已完成的相关验收

- 私有 UBUS 服务模拟权限不回复：原版静态请求超时，修复版静态请求 HTTP200，实测 0.279 ms。
- 三种接口同时等待权限：其他静态请求继续返回；5 秒后受影响请求拒绝或超时，不执行管理操作。
- 正常授权、拒绝访问、REST、JSON-RPC 批量调用通过。
- 第一项权限超时后，批量请求继续执行后续有效项；允许的订阅接口仍能接收事件。
- 权限回复迟于超时时，不执行受保护方法；随后正常请求仍成功。
- 10 个客户端提前断开后，HTTP 进程 FD 数恢复为测试前的 8 个。
- 接真实 rpcd，以临时受限会话验证：允许 `system.board`，拒绝未授权的 `system.info`；测试会话已销毁。
- 候选 APK 离线升级成功；实际安装的模块在相同权限故障下仍可响应静态页面；系统原 HTTP 静态资源正常。
- 降级回原 r1 成功；原模块 SHA256、`/etc/config/uhttpd` 均与测试前一致，主 HTTP 服务恢复正常。
- 以上在 VM9000 的保留测试盘执行，未声称生产故障已通过安装补丁解决；原工作盘与电源状态恢复见 [验收数据](evidence/uhttpd-20261126/acceptance.json)。

## 候选包与回滚

候选包只替换同 ABI 的 UBUS 模块，适用于已核对 `x86_64`、uhttpd `2026.08.24~373145f7-r1`、libubus ABI `20251202`、libblobmsg-json ABI `20260213` 的本项目系统。不要在其他版本上直接安装。Linux 189 使用锁定 SDK 编译模块并用原生 `apk mkpkg` 打包；它是隔离验收的候选热修包，不是已经发布的新固件。

- 候选 r2 SHA256：`2911e6c9acf6069cc8fc090b9017c9c783aee4b6a2b700e82afda79560c6d07c`
- 匹配旧 r1 SHA256：`de770041806e87207d99aafaf735a02ad4068a97295d2510d225384ba61ed4aa`

经授权并核对版本、校验和后，可通过本地文件安装（无需网络）：

```sh
apk --no-network --repositories-file /dev/null --allow-untrusted add /tmp/uhttpd-mod-ubus-2026.08.24~373145f7-r2.apk
```

回滚为相同命令安装对应 r1 文件。两个包保留原版安装后的服务 reload 行为；已验证在配置未变化时，reload 不会替换进程中已加载的模块。经授权安装或回滚后，需要执行 `/etc/init.d/uhttpd restart`，再核对新进程和实际模块摘要。这会短暂断开网页连接，不需要重启路由器或改 DNS／代理。随后必须验证静态页面、登录和权限控制，不能只看 APK 命令或包版本。

## 下次故障取证

`sh scripts/capture-uhttpd.sh 新建输出目录` 在重启前保存进程状态、系统调用、FD 与 socket 信息，执行有限时的静态文件和只读 ACL 探测；若已有 strace/timeout，则最多跟踪 8 秒，字符串长度设为 0，避免采集 Cookie、密码和 RPC 正文。它不会主动安装 strace，也不会重启服务。

脚本已在隔离 VM 验证；物理机执行仍应按运维授权流程。完整原始取证文件保留在受控位置，不上传含内网拓扑的原始日志。需要结合当时 uhttpd 等待的确切 FD、UBUS socket 收发与 rpcd 同时响应情况，才能继续判断最初未回包的原因。
