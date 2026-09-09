const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

function resolveDependency(name) {
  try { return require.resolve(name); }
  catch (error) { if (process.env.SWARM_NODE_MODULES) return require.resolve(path.join(process.env.SWARM_NODE_MODULES, name)); throw error; }
}
const { chromium } = require(resolveDependency('playwright'));
const baseUrl = process.argv[2] || 'https://edson-zepeda.github.io/swarm-signal-openlab/';
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'evidence', 'ui');
fs.mkdirSync(output, { recursive: true });
const results = { timestamp: new Date().toISOString(), url: baseUrl, authentication: 'Fresh browser context; no account, stored cookies or user profile.', checks: [], consoleErrors: [], javascriptErrors: [], screenshots: [] };
let context;
let browser;

async function check(name, action) {
  try { const detail = await action(); results.checks.push({ name, passed: true, detail: detail ?? null }); console.log('PASS ' + name); }
  catch (error) { results.checks.push({ name, passed: false, error: error.message }); console.log('FAIL ' + name + ': ' + error.message); }
}

async function main() {
  browser = await chromium.launch({ headless: true, ...(process.env.SWARM_BROWSER_EXECUTABLE ? { executablePath: process.env.SWARM_BROWSER_EXECUTABLE } : {}) });
  results.browserVersion = browser.version();
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => results.javascriptErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') results.consoleErrors.push({ text: message.text(), url: message.location().url || null }); });
  const screenshot = async name => { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, fullPage: true }); results.screenshots.push(path.relative(root, file)); };

  let fixture;
  await check('Anonymous public dashboard is reachable', async () => {
    const response = await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 45000 });
    assert.equal(response.status(), 200);
    await page.waitForFunction(() => document.querySelector('#metricSamples')?.textContent === '233');
    assert.equal(await page.locator('h1').textContent(), 'Lee lo invisible.');
    assert.match(await page.locator('#connectionStatus').textContent(), /Captura grabada/);
    assert.match(await page.locator('#captureButton').textContent(), /Reproducir captura/);
    const source = await page.request.get(new URL('data/session.json', baseUrl).href);
    assert.equal(source.status(), 200); fixture = await source.json();
    assert.equal(fixture.samples.length, 233); assert.equal(fixture.frames.length, 233);
    await screenshot('public-monitor');
    return { finalUrl: page.url(), status: response.status(), title: await page.title(), samples: fixture.samples.length, frames: fixture.frames.length };
  });
  await check('Published replay advances, pauses and seeks actual frames', async () => {
    assert(fixture, 'Published fixture must be available.');
    await page.locator('#replaySpeed').selectOption('8'); await page.locator('#playButton').click();
    await page.waitForTimeout(900);
    const progressed = Number((await page.locator('#metricSamples').textContent()).replace(/,/g, ''));
    assert(progressed > 4 && progressed < 70);
    await page.locator('#playButton').click();
    const paused = await page.locator('#replayTime').textContent(); await page.waitForTimeout(350);
    assert.equal(await page.locator('#replayTime').textContent(), paused);
    const inspected = [];
    for (const value of [250, 500, 1000]) {
      await page.locator('#replaySlider').evaluate((el, position) => { el.value = position; el.dispatchEvent(new Event('input', { bubbles: true })); }, String(value));
      const count = Number((await page.locator('#metricSamples').textContent()).replace(/,/g, ''));
      const frame = value === 1000 ? fixture : fixture.frames.filter(item => item.index <= count - 1).at(-1);
      const labels = { active: 'SEÑAL VARIABLE', present_still: 'CAMBIO SUAVE', absent: 'SEÑAL ESTABLE' };
      const expected = frame?.quality?.ready === false || !frame?.classification ? 'SIN VEREDICTO' : labels[frame.classification.motion_level];
      assert.equal(await page.locator('#readingTag').textContent(), expected); inspected.push({ position: value, count, classification: expected });
    }
    return { progressed, paused, inspected };
  });
  await check('Published CSV contains 233 rows', async () => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#exportButton').click()]);
    const target = path.join(output, 'public-export.csv'); await download.saveAs(target);
    const rows = fs.readFileSync(target, 'utf8').trim().split(/\r?\n/).length - 1; assert.equal(rows, 233); return { rows };
  });
  await check('Published evidence and PDF links work', async () => {
    await page.locator('[data-tab="evidencia"]').click(); await page.waitForTimeout(500);
    assert.equal(await page.locator('#evidenceProgress').textContent(), '6 / 8');
    const links = await page.locator('.resource-bar a').evaluateAll(elements => elements.map(el => ({ text: el.textContent.trim(), url: el.href })));
    const checked = [];
    for (const link of links) {
      const response = await page.request.get(link.url); assert.equal(response.status(), 200);
      if (link.url.endsWith('.pdf')) { const bytes = await response.body(); assert.equal(bytes.subarray(0, 5).toString(), '%PDF-'); }
      checked.push({ ...link, status: response.status(), contentType: response.headers()['content-type'] });
    }
    return checked;
  });
  await check('Published demo plays with audio, chapters and subtitles', async () => {
    const response = await page.goto(new URL('demo.html', baseUrl).href, { waitUntil: 'networkidle', timeout: 45000 });
    assert.equal(response.status(), 200);
    await page.waitForFunction(() => document.querySelector('#demoVideo')?.readyState >= 1, undefined, { timeout: 30000 });
    const metadata = await page.locator('#demoVideo').evaluate(video => ({ duration: video.duration, width: video.videoWidth, height: video.videoHeight, subtitles: [...video.textTracks].map(track => track.language) }));
    assert(Math.abs(metadata.duration - 104.8) < 1); assert.equal(metadata.width, 1920); assert.equal(metadata.height, 1080); assert(metadata.subtitles.includes('es'));
    await page.locator('.chapter[data-time="63.267"]').click();
    await page.waitForFunction(() => { const video = document.querySelector('#demoVideo'); return !video.paused && video.currentTime > 63.5; }, undefined, { timeout: 30000 });
    const playback = await page.locator('#demoVideo').evaluate(video => ({ currentTime: video.currentTime, paused: video.paused, decodedAudioBytes: video.webkitAudioDecodedByteCount || 0, muted: video.muted, error: video.error?.code || null }));
    assert(playback.decodedAudioBytes > 0); assert.equal(playback.error, null);
    await page.locator('#demoVideo').evaluate(video => video.pause()); await screenshot('public-demo');
    return { ...metadata, ...playback };
  });
  await check('Published mobile pages have no horizontal overflow', async () => {
    const widths = [];
    for (const relative of ['', 'demo.html']) {
      await page.setViewportSize({ width: 390, height: 900 }); await page.goto(new URL(relative, baseUrl).href, { waitUntil: 'networkidle' });
      const measurement = await page.evaluate(() => ({ viewport: innerWidth, pageWidth: document.documentElement.scrollWidth }));
      assert(measurement.pageWidth <= measurement.viewport); widths.push({ page: relative || 'dashboard', ...measurement });
    }
    return widths;
  });
  await check('No JavaScript errors or unexpected console failures', async () => {
    assert.equal(results.javascriptErrors.length, 0);
    const expectedProbe = entry => /\/api\/state(?:$|\?)/.test(entry.url || '') && /404/.test(entry.text);
    const unexpected = results.consoleErrors.filter(entry => !expectedProbe(entry));
    assert.equal(unexpected.length, 0, JSON.stringify(unexpected));
    return { javascriptErrors: 0, unexpectedConsoleErrors: 0, expectedLocalApiProbe404: results.consoleErrors.filter(expectedProbe).length };
  });
}

main().catch(error => { results.fatal = error.stack; console.error(error); }).finally(async () => {
  results.passed = !results.fatal && results.checks.length > 0 && results.checks.every(item => item.passed);
  results.summary = { passed: results.checks.filter(item => item.passed).length, failed: results.checks.filter(item => !item.passed).length };
  fs.writeFileSync(path.join(output, 'public-qa.json'), JSON.stringify(results, null, 2));
  if (context) await context.close(); if (browser) await browser.close();
  console.log(JSON.stringify(results.summary)); process.exitCode = results.passed ? 0 : 1;
});
