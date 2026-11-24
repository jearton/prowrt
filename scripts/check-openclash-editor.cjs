// SPDX-License-Identifier: GPL-3.0-or-later
// Test real browser multipart submission; no router or service configuration.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.join(__dirname, '../sources/full/package/custom/luci-app-openclash');
const common = fs.readFileSync(path.join(root, 'root/www/luci-static/resources/openclash/js/common.js'), 'utf8');
const helper = common.slice(common.indexOf('function ocStreamEditorOnSubmit('), common.indexOf('// Single source for the F10'));
const template = fs.readFileSync(path.join(root, 'luasrc/view/openclash/config_merge_editor.htm'), 'utf8');
const guard = template.slice(template.indexOf('if (myEditor_use && myEditor_use.form)'), template.indexOf('if (myEditor_use && myEditor_def)'));
const readonly = fs.readFileSync(path.join(root, 'luasrc/view/openclash/readonly_config.htm'), 'utf8');
assert(!/<textarea[^>]*\bname\s*=/i.test(readonly), 'Runtime YAML still has a submit name');
const report = [];

async function main() {
  const browser = await chromium.launch({executablePath: process.env.CHROME_EXECUTABLE, headless: true});
  try {
    for (const scenario of ['small-save', 'large-save', 'large-apply', 'no-file-transfer', 'helper-load-failed', 'cancelled-submit']) {
      const context = await browser.newContext();
      const page = await context.newPage();
      page.setDefaultTimeout(10000);
      let request;
      await context.route('http://127.0.0.1:19092/**', async route => {
        if (route.request().method() === 'POST') {
          request = route.request();
          return route.fulfill({status: 200, contentType: 'text/html', body: '<p>accepted</p>'});
        }
        return route.fulfill({status: 200, contentType: 'text/html', body: `<form action="/submit" method="post"><input name="token" value="fixture-csrf"><textarea id="source" name="cbid.table.1.user"></textarea><textarea id="runtime" readonly></textarea><button id="save" name="cbid.table.1.Commit" value="1">Save</button><button id="apply" name="cbid.table.1.Apply" value="1">Apply</button></form>`});
      });
      await page.goto('http://127.0.0.1:19092/');
      const source = 'mixed-port: 17890\nproxies: []\nproxy-groups: []\nrules:\n  - DOMAIN,firmware-upload.example,DIRECT\n  - MATCH,DIRECT\n' + (scenario === 'small-save' ? '' : '# 中文 YAML transport fixture\n'.repeat(6000));
      const runtime = '# readonly running config\n'.repeat(6000);
      await page.evaluate(({source, runtime}) => {
        window.myEditor_use = document.getElementById('source');
        window.myEditor_def = document.getElementById('runtime');
        myEditor_use.value = source;
        myEditor_def.value = runtime;
        window.alert = () => { window.__alerted = true; };
      }, {source, runtime});
      await page.addScriptTag({content: guard});
      if (scenario !== 'helper-load-failed') {
        await page.addScriptTag({content: helper + '\nocStreamEditorOnSubmit(myEditor_use);'});
      }
      if (scenario === 'no-file-transfer') await page.evaluate(() => { window.DataTransfer = undefined; });
      if (scenario === 'cancelled-submit') await page.evaluate(() => {
        myEditor_use.form.addEventListener('submit', event => event.preventDefault());
      });
      const blocked = ['no-file-transfer', 'helper-load-failed', 'cancelled-submit'].includes(scenario);
      if (blocked) {
        await page.click('#apply');
        await page.waitForTimeout(100);
        assert(!request, `${scenario} sent a form despite failed upload preparation`);
        assert.equal(await page.locator('#source').inputValue(), source);
        assert.equal(await page.locator('#source').isDisabled(), false);
        if (scenario !== 'cancelled-submit') assert(await page.evaluate(() => window.__alerted));
      } else {
        await Promise.all([page.waitForURL('**/submit'), page.click(scenario === 'large-apply' ? '#apply' : '#save')]);
        assert(request);
        const data = request.postDataBuffer();
        const type = request.headers()['content-type'];
        const boundary = /boundary=(.+)$/.exec(type)[1];
        const parts = data.toString('utf8').split('--' + boundary).filter(part => part.includes('Content-Disposition'));
        assert(parts.some(part => part.includes('name="oc_editor_content"; filename="content.yaml"') && part.split('\r\n\r\n')[1] === source + '\r\n'));
        assert(!parts.some(part => part.includes('name="cbid.table.1.user"')));
        assert(!parts.some(part => part.includes(runtime)));
        assert(!data.includes(Buffer.from('oc-editor-streamed')));
        // Ordinary fields remain small even when both displayed YAMLs exceed 100 KiB.
        assert(parts.filter(part => !part.includes('filename=')).every(part => Buffer.byteLength(part) < 100 * 1024));
        assert(parts.some(part => part.includes('name="token"')));
        if (scenario !== 'small-save') assert(Buffer.byteLength(source) > 159133);
      }
      report.push({scenario, sourceBytes: Buffer.byteLength(source), runtimeBytes: Buffer.byteLength(runtime), status: 'passed'});
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
