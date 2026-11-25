/* SPDX-License-Identifier: MIT */
(function () {
  'use strict';
  function clear() {
    document.getElementById('prowrt-device-error')?.remove();
    document.getElementById('prowrt-readonly-style')?.remove();
  }
  function show(message, warning) {
    clear();
    const root = document.getElementById('app');
    if (!root) return;
    const box = document.createElement('div');
    box.id = 'prowrt-device-error';
    box.className = 'alert-message ' + (warning ? 'warning' : 'error');
    box.setAttribute('role', 'alert');
    box.textContent = message;
    root.parentNode.insertBefore(box, root);
  }
  const zh = () => String(window.vue_lang || '').startsWith('zh');
  function failure(error) {
    show((zh() ? '设备列表读取失败：' : 'Unable to load the device list: ') +
      String(error?.message || error || (zh() ? '未知错误' : 'Unknown error')), false);
  }
  function readonly(snmp) {
    const message = snmp ? (zh() ?
      '设备列表为只读视图，含跨三层 SNMP ARP 记录；每60秒采集，失败记录最多保留180秒。ARP记录不等于实时在线。速率来自OpenWrt流量统计，无数据时显示“—”。DHCP、限速请使用原生管理入口。' :
      'Read-only SNMP inventory: collected every 60 seconds, expires after 180 seconds. ARP observations do not prove a device is online. Rates use OpenWrt traffic statistics; missing data shows “—”. Use native management pages.') :
      (zh() ? '多接口发现为只读视图；DHCP、限速等配置请使用对应的原生管理入口。' :
      'Multi-interface discovery is read-only. Use the native management pages for DHCP and traffic controls.');
    show(message, true);
    if (!document.getElementById('prowrt-readonly-style')) {
      const style = document.createElement('style');style.id = 'prowrt-readonly-style';
      style.textContent = '#app table thead th:last-child,#app table tbody td:last-child{display:none}';
      document.head.appendChild(style);
    }
  }
  window.prowrtDevices = {clear, show, failure, readonly};
})();
