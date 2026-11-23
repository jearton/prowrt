// SPDX-License-Identifier: GPL-3.0-or-later
// Use real Chrome and a real, isolated Mihomo API with 2,250 live connections.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:19090';
const output = process.argv[3];
// Exercise the actual OpenClash link generator, including hash-route parameters.
const common = fs.readFileSync(path.join(__dirname, '../sources/full/package/custom/luci-app-openclash/root/www/luci-static/resources/openclash/js/common.js'), 'utf8');
const linkContext = {URL, URLSearchParams, window: {location: new URL(base)}};
vm.createContext(linkContext);
vm.runInContext(common.slice(common.indexOf('function ocGetCustomDashboardURL('), common.indexOf('window.ocFullscreenActive =')), linkContext);
const status = {cn_port: new URL(base).port, daip: new URL(base).hostname, dase: ''};
assert(output, 'Evidence directory is required');
fs.mkdirSync(output, {recursive: true});

async function main() {
  const version = await (await fetch(base + '/version')).json();
  assert.match(version.version, /1\.19\.34/);
  const current = await (await fetch(base + '/connections')).json();
  assert.equal(current.connections.length, 2250);
  const browser = await chromium.launch({executablePath: process.env.CHROME_EXECUTABLE,
    headless: true, args: ['--disable-dev-shm-usage']});
  const evidence = {core: version, connections: current.connections.length, measurements: {}};
  try {
    async function offlineContext(options) {
      const context = await browser.newContext(options);
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
      });
      return context;
    }
    async function pageFor(context, panel) {
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      page.setDefaultNavigationTimeout(20000);
      await page.addInitScript(() => {
        window.__qaLongTasks = [];
        new PerformanceObserver(list => {
          for (const entry of list.getEntries()) window.__qaLongTasks.push({start: entry.startTime, duration: entry.duration});
        }).observe({type: 'longtask', buffered: true});
      });
      const url = linkContext.ocBuildDashboardURL(status, panel, true);
      await page.goto(url, {waitUntil: 'domcontentloaded'});
      await page.waitForFunction(() => !location.hash.startsWith('#/setup'), null, {timeout: 20000});
      await page.evaluate(() => { location.hash = '/proxies'; });
      await page.waitForFunction(() => document.body.innerText.includes('QA'), null, {timeout: 20000});
      await page.waitForTimeout(5000);
      return page;
    }

    async function measure(panel) {
      const context = await offlineContext({viewport: {width: 1440, height: 1000}, locale: 'en-US'});
      const page = await pageFor(context, panel);
      const text = await page.locator('body').innerText();
      fs.writeFileSync(path.join(output, panel + '-body.txt'), text);
      await page.screenshot({path: path.join(output, panel + '.png')});
      // The selected QA group proves that the UI has connected to this backend.
      assert.match(text, /QA/, `${panel} did not render the fixture proxy group`);
      const start = await page.evaluate(() => performance.now());
      await page.waitForTimeout(12000);
      const tasks = await page.evaluate(start => window.__qaLongTasks.filter(task => task.start >= start), start);
      const measurement = {seconds: 12, longTasks: tasks, over500ms: tasks.filter(task => task.duration >= 500).length,
        maximumMs: Math.max(0, ...tasks.map(task => task.duration))};
      evidence.measurements[panel] = measurement;
      console.log(`${panel}: ${measurement.over500ms} long tasks over 500 ms`);
      await context.close();
      return measurement;
    }

    await measure('zashboard-legacy');
    const updated = await measure('zashboard');
    assert(updated.over500ms === 0, 'Updated Zashboard still produces recurring half-second stalls');
    const meta = await measure('metacubexd');
    assert(meta.over500ms === 0, 'Updated MetaCubeXD produces half-second stalls');

    // Keep the same browser storage and service-worker registrations while the
    // server-side directory changes from the exact old bundle to the new one.
    const migration = await offlineContext({viewport: {width: 1440, height: 1000}, locale: 'en-US'});
    const page = await pageFor(migration, 'zashboard-upgrade');
    await page.evaluate(() => localStorage.setItem('prowrt-qa-preserved', 'yes'));
    const before = await page.locator('script[type="module"][src]').first().getAttribute('src');
    const control = new URL(base); control.port = '19091';
    assert((await fetch(control.origin + '/upgrade', {method: 'POST'})).ok);
    let after = before;
    for (let attempt = 0; attempt < 3 && after === before; attempt++) {
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.waitForTimeout(2000);
      after = await page.locator('script[type="module"][src]').first().getAttribute('src');
    }
    let hardRefreshRequired = false;
    if (after === before) {
      // Match Chrome's hard refresh: retain localStorage, bypass the old SW
      // for this navigation and explicitly ask the native registration to update.
      hardRefreshRequired = true;
      const cdp = await migration.newCDPSession(page);
      await cdp.send('Network.setBypassServiceWorker', {bypass: true});
      await cdp.send('Network.setCacheDisabled', {cacheDisabled: true});
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.evaluate(async () => {
        const registration = await navigator.serviceWorker.getRegistration();
        if (registration) await registration.update();
      });
      await page.waitForTimeout(5000);
      await cdp.send('Network.setBypassServiceWorker', {bypass: false});
      await cdp.send('Network.setCacheDisabled', {cacheDisabled: false});
      await page.reload({waitUntil: 'domcontentloaded'});
      after = await page.locator('script[type="module"][src]').first().getAttribute('src');
      await cdp.detach();
    }
    assert.notEqual(after, before, 'Existing browser still loads the old dashboard bundle after hard refresh');
    assert.equal(await page.evaluate(() => localStorage.getItem('prowrt-qa-preserved')), 'yes');
    evidence.cacheMigration = {oldEntry: before, newEntry: after, localStoragePreserved: true, hardRefreshRequired};
    await page.screenshot({path: path.join(output, 'cache-migration.png')});
    await migration.close();
  } finally {
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify(evidence, null, 2) + '\n');
    await browser.close();
  }
  console.log(JSON.stringify(evidence, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
