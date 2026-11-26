'use strict';
'require view';
'require fs';
'require ui';
'require poll';
'require request';

return view.extend({
 previous: null,
 rows: [],
 sortKey: 'cpu',
 descending: true,
 load: function() { return this.fetchMetrics(); },
 fetchMetrics: function() {
  return request.get(L.url('admin/status/prowrt_processes'), { cache: false }).then(function(r) {
   if (!r.ok) throw new Error('进程数据读取失败（HTTP ' + r.status + '）');
   var data = r.json();
   if (!data || !Array.isArray(data.processes) || !(data.total_ticks > 0)) throw new Error('进程数据格式无效');
   return data;
  });
 },
 consume: function(data) {
  var old = this.previous, previousByPid = {}, delta = old ? data.total_ticks - old.total_ticks : 0;
  if (old) old.processes.forEach(function(p) { previousByPid[p.pid] = p; });
  this.rows = data.processes.map(function(p) {
   var before = previousByPid[p.pid];
   p.cpu = delta > 0 && before && before.start === p.start && p.ticks >= before.ticks
    ? Math.min(100, (p.ticks - before.ticks) / delta * 100) : null;
   return p;
  });
  this.previous = data;
 },
 compare: function(a, b) {
  var key = this.sortKey, av = a[key], bv = b[key];
  if (av == null || bv == null) return av == null && bv == null ? a.pid - b.pid : av == null ? 1 : -1;
  return (this.descending ? bv - av : av - bv) || a.pid - b.pid;
 },
 setSort: function(key) {
  if (this.sortKey === key) this.descending = !this.descending;
  else { this.sortKey = key; this.descending = true; }
  this.updateTable();
 },
 handleSignal: function(signum, pid) {
  if (this.readonly) return;
  return fs.exec('/bin/kill', ['-' + signum, String(pid)]).then(L.bind(function() {
   return this.refresh();
  }, this)).catch(function(e) { ui.addNotification(null, E('p', e.message)); });
 },
 updateTable: function() {
  var self = this;
  var rows = this.rows.slice().sort(this.compare.bind(this)).map(function(p) {
   return [p.pid, p.user, E('span', {style:'word-break: break-word'}, p.command),
    p.cpu == null ? '—' : p.cpu.toFixed(1) + '%',
    (p.rss_kib / 1024).toFixed(1) + ' MiB', p.memory_percent.toFixed(1) + '%',
    E('div', {style:'display:flex;gap:4px;flex-wrap:nowrap'}, [[1, _('Hang Up')], [15, _('Terminate')], [9, _('Kill')]].map(function(action) {
     return E('button', {class:'btn ' + (action[0] === 1 ? 'cbi-button-action' : 'cbi-button-negative'),
      disabled:self.readonly || null, click:ui.createHandlerFn(self, 'handleSignal', action[0], p.pid)}, action[1]);
    }))];
  });
  this.body.replaceChildren.apply(this.body, rows.map(function(row, index) {
   return E('tr', {class:'tr cbi-rowstyle-' + (index % 2 ? 2 : 1)}, row.map(function(value) {
    return E('td', {class:'td'}, value == null ? '' : value);
   }));
  }));
  [['cpu', this.cpuButton], ['memory_percent', this.memoryButton]].forEach(function(item) {
   var active = self.sortKey === item[0];
   item[1].textContent = (item[0] === 'cpu' ? 'CPU 使用率（%）' : '内存使用率（%）') + (active ? (self.descending ? ' ▼' : ' ▲') : ' ↕');
   item[1].parentNode.setAttribute('aria-sort', active ? (self.descending ? 'descending' : 'ascending') : 'none');
  });
 },
 refresh: function() {
  if (this.pending) return this.pending;
  this.pending = this.fetchMetrics().then(L.bind(function(data) {
   this.consume(data);this.updateTable();
   this.status.textContent = '每 5 秒自动刷新；最近更新：' + new Date().toLocaleTimeString() + '。CPU 以整机总算力为 100%；— 表示等待两次有效采样。';
  }, this)).catch(L.bind(function(e) {
   this.status.textContent = '刷新失败，显示上次数据：' + e.message;
  }, this)).finally(L.bind(function() { this.pending = null; }, this));
  return this.pending;
 },
 render: function(data) {
  this.readonly = !L.hasViewPermission();
  this.cpuButton = E('button', {class:'btn', click:L.bind(this.setSort, this, 'cpu')}, 'CPU 使用率（%） ▼');
  this.memoryButton = E('button', {class:'btn', click:L.bind(this.setSort, this, 'memory_percent')}, '内存使用率（%） ↕');
  this.body = E('tbody', {});
  this.table = E('table', {class:'table'}, [E('thead', {}, E('tr', {class:'tr table-titles'}, [
   E('th', {class:'th'}, 'PID'), E('th', {class:'th'}, _('Owner')), E('th', {class:'th'}, _('Command')),
   E('th', {class:'th'}, this.cpuButton), E('th', {class:'th'}, '实际内存（RSS）'),
   E('th', {class:'th'}, this.memoryButton), E('th', {class:'th'}, _('Actions'))])), this.body]);
  this.status = E('p', {}, '每 5 秒自动刷新；CPU 等待第二次采样，内存为 RSS / 物理内存总量。');
  this.consume(data);this.updateTable();
  poll.add(L.bind(this.refresh, this), 5);
  return E([], [E('h2', {}, _('Processes')), this.status,
   E('p', {}, '内存按 RSS 显示，包含共享驻留页，各进程数值相加不等于整机已用内存。点击 CPU 或内存表头切换升降序。'),
   E('div', {class:'cbi-section',style:'overflow-x:auto'}, this.table)]);
 },
 handleSaveApply:null, handleSave:null, handleReset:null
});
