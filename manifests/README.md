# x86/64 镜像清单

本目录对应 [v25.12.6-20261120.2](https://github.com/jearton/prowrt/releases/tag/v25.12.6-20261120.2)，包含 469 个包，189 Linux 增量构建。

Netdata 2.13.0-r5、LuCI Netdata 0.1-r3 使用预置原生 System Overview，离线、无云账号、换浏览器自动初始化，并保留个人布局。其余功能沿用既有版本：Technitium 15.6.2-r2、Console 1.4.2、LuCI Technitium 1.1.0-r1、Argon 3.1.4、ttyd 1.7.7-r6、kmod-bonding。IPv6 禁用，AdGuard Home 默认停用，Docker 不在镜像内。

压缩 EFI 镜像为 173922628 字节，SHA256：

```text
c0f28710b3f6430699772bf9b8d4f9cd888e88aafd7e4d71e4f681f0982dff11
```

[本轮最终镜像验收](../docs/netdata-overview-acceptance-20261120.md)记录准确范围、截图和回滚点。该验收不代表既有 DNSSEC 问题已修复，也不覆盖物理传感器和所有网络功能重新测试。此前 v25.12.6-20261120 的镜像和附件保持不变。
