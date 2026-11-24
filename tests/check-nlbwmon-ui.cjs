// SPDX-License-Identifier: GPL-3.0-or-later
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const columns = ['family','mac','ip','layer7','conns','rx_bytes','rx_pkts','tx_bytes','tx_pkts'];
const fixture = { columns, data: [
  [4,'00:00:00:00:00:00','192.168.88.10','HTTP',1,100,1,20,1],
  [4,'00:00:00:00:00:00','192.168.88.10','DNS',2,200,2,40,2],
  [4,'00:00:00:00:00:00','192.168.88.11','HTTP',4,400,4,80,4],
  [4,'02:00:00:00:00:01','192.168.1.2','HTTP',8,800,8,160,8],
  [6,'02:00:00:00:00:01','fd00::2','HTTP',16,1600,16,320,16]
] };
const tables = {}, counters = {};
const context = vm.createContext({
  view: { extend: x => x }, rpc: { declare: () => () => {} },
  E: (tag, attrs, children) => ({tag, attrs, children}), _: x => x,
  cbi_update_table: (id, rows) => tables[id] = rows
});
vm.runInContext('String.prototype.format = function() { return this.toString(); };', context);
const source = fs.readFileSync(process.argv[2], 'utf8').replace(
  'let trafficData = { columns: [], data: [] };', 'let trafficData = ' + JSON.stringify(fixture) + ';');
const page = vm.runInContext('(function(){' + source + '\n})()', context);
page.pie = () => {}; page.kpi = (id, value) => counters[id] = value;
assert.equal(page.formatHostname('192.168.88.10'), '192.168.88.10');
assert.equal(page.formatHostname('fd00::2'), 'fd00::2');
page.renderHostData();
let rows = tables['#host-data'];
assert.equal(rows.length, 3);
let host = rows.find(r => r[1].children === '192.168.88.10');
assert(host); assert.equal(host[1].attrs.href, '#192.168.88.10');
assert.equal(host[2][0], 3); assert.equal(host[3][0], 300);
assert.equal(rows.find(r => r[1].children === '192.168.88.11')[3][0], 400);
assert.equal(rows.find(r => r[1].children === '02:00:00:00:00:01')[3][0], 2400);
page.renderHostData();
assert.equal(tables['#host-data'].find(r => r[1].children === '192.168.88.10')[3][0], 300);
page.renderIPv6Data();
assert.equal(tables['#ipv6-data'].length, 3);
assert(tables['#ipv6-data'].some(r => r[1] === '192.168.88.11'));
console.log('LuCI host/IP grouping, detail links, totals and old record format passed');
