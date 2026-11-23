// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise ROM preference, fallback, malformed input and safe text rendering.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('image-files/network-ui/www/luci-static/resources/view/status/include/05_prowrt.js', 'utf8');
const data = {version: '25.12.6-test', source_revision: '<script>unsafe</script>', target: 'x86/64'};
function load(reader) {
  return new Function('baseclass', 'fs', '_', 'E', source)(
    {extend: value => value}, {read_direct: reader}, text => text,
    (tag, attributes, children) => ({tag, attributes, children}));
}
(async () => {
  const paths = [];
  const ui = load(async path => { paths.push(path); return JSON.stringify(data); });
  assert.deepEqual(await ui.load(), data);
  assert.deepEqual(paths, ['/rom/usr/share/prowrt/build.json']);
  const table = ui.render(data);
  assert.equal(table.children[1].children[1].children[0], data.source_revision);
  const fallback = load(async path => {
    if (path.startsWith('/rom/')) throw Error('No ROM');
    return JSON.stringify(data);
  });
  assert.deepEqual(await fallback.load(), data);
  assert.deepEqual(await load(async () => '{invalid').load(), {});
  assert.deepEqual(await load(async () => 'null').load(), {});
  assert.deepEqual(await load(async () => { throw Error('Denied'); }).load(), {});
  console.log('ProWrt overview: ROM preference, fallback and text rendering passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
