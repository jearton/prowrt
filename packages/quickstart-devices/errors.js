/* SPDX-License-Identifier: MIT */
(function () {
  'use strict';
  function clear() { document.getElementById('prowrt-device-error')?.remove(); }
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
  function readonly() {
    show(zh() ? '多接口发现为只读视图；DHCP、限速等配置请使用对应的原生管理入口。' :
      'Multi-interface discovery is read-only. Use the native management pages for DHCP and traffic controls.', true);
  }
  window.prowrtDevices = {clear, show, failure, readonly};
})();
