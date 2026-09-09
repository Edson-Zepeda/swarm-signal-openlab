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
const videoTimeline = JSON.parse(fs.readFileSync(path.join(root, 'media', 'video', 'timeline.json'), 'utf8').replace(/^\uFEFF/, ''));
const output = path.join(root, 'evidence', 'revision', 'ui');
fs.mkdirSync(output, { recursive: true });
const results = { timestamp: new Date().toISOString(), url: baseUrl, authentication: 'Fresh browser context; no account, stored cookies or user profile.', checks: [], consoleErrors: [], javascriptErrors: [], apiRequests: [], screenshots: [] };
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
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) results.apiRequests.push(request.url()); });
  page.on('console', message => { if (message.type() === 'error') results.consoleErrors.push({ text: message.text(), url: message.location().url || null }); });
  const screenshot = async name => { const file = path.join(output, name + '.png'); await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: file, fullPage: true }); results.screenshots.push(path.relative(root, file)); };

  let fixture;
  await check('Anonymous public dashboard is reachable', async () => {
    const response = await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 45000 });
    assert.equal(response.status(), 200);
    await page.waitForFunction(() => document.querySelector('#metricSamples')?.textContent === '233');
    assert.equal(await page.locator('h1').textContent(), 'RSSI bajo prueba.'); assert.equal(await page.evaluate(() => scrollY), 0);
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
  await check('Published comparison preserves actual capture denominators', async () => {
    const response = await page.request.get(new URL('data/comparison.json', baseUrl).href); assert.equal(response.status(), 200); const comparison = await response.json();
    await page.locator('#comparisonPanel > summary').click(); const rows = await page.locator('#comparisonRows tr').allTextContents(); assert.equal(rows.length, comparison.sessions.length);
    comparison.sessions.forEach((session, i) => { assert(rows[i].includes(String(session.count))); assert(rows[i].includes(session.windows_eligible ? `${session.windows_valid} / ${session.windows_eligible}` : 'Sin elegibles')); });
    assert.match(await page.locator('#comparisonPhysical').textContent(), /sin confirmar/); return comparison.sessions.map(session => ({ label: session.label, samples: session.count, valid: session.windows_valid, eligible: session.windows_eligible }));
  });
  await check('Published delivery and local setup are discoverable', async () => {
    await page.locator('[data-open-view=evidencia]').click(); assert(await page.locator('#evidencia').isVisible()); assert.match(page.url(), /view=evidencia/);
    await page.locator('[data-tab=monitor]').click(); await page.locator('.local-help-trigger').click(); assert.match(await page.locator('#localHelpDialog').innerText(), /Iniciar.cmd/); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.delivery-links a').count(), 5); return { deliveryLinks: 5, setup: 'Iniciar.cmd' };
  });
  await check('Published evidence and PDF links work', async () => {
    await page.locator('[data-tab="evidencia"]').click(); await page.waitForTimeout(500);
    assert.equal(await page.locator('#evidenceProgress').textContent(), `${fixture.evidence.stages.filter(s => s.status === 'complete').length} / ${fixture.evidence.stages.length}`);
    const links = await page.locator('.resource-bar a, #evidenceStages a').evaluateAll(elements => elements.map(el => ({ text: el.textContent.trim(), url: el.href })));
    const checked = [];
    for (const link of links) {
      const response = await page.request.get(link.url); assert.equal(response.status(), 200);
      if (link.url.endsWith('.pdf')) { const bytes = await response.body(); assert.equal(bytes.subarray(0, 5).toString(), '%PDF-'); }
      checked.push({ ...link, status: response.status(), contentType: response.headers()['content-type'] });
    }
    return checked;
  });
  await check('Published demo plays with audio, chapters and subtitles', async () => {
    const response = await page.goto(new URL('demo.html', baseUrl).href, { waitUntil: 'domcontentloaded', timeout: 45000 });
    assert.equal(response.status(), 200);
    await page.waitForFunction(() => document.querySelector('#demoVideo')?.readyState >= 1, undefined, { timeout: 30000 });
    const metadata = await page.locator('#demoVideo').evaluate(video => ({ duration: video.duration, width: video.videoWidth, height: video.videoHeight, subtitles: [...video.textTracks].map(track => track.language) }));
    assert(Math.abs(metadata.duration - videoTimeline.duration_seconds) < .15); assert.equal(metadata.width, 1920); assert.equal(metadata.height, 1080); assert(metadata.subtitles.includes('es'));
    const chapterTimes = await page.locator('.chapter').evaluateAll(els => els.map(el => Number(el.dataset.time))); assert.equal(chapterTimes.length, videoTimeline.scenes.length); chapterTimes.forEach((time, i) => assert(Math.abs(time - videoTimeline.scenes[i].start) < .01)); metadata.chapters = chapterTimes;
    const chapter = page.locator('.chapter').nth(Math.floor(await page.locator('.chapter').count() / 2)); const chapterStart = Number(await chapter.getAttribute('data-time'));
    await chapter.click();
    await page.waitForFunction(start => { const video = document.querySelector('#demoVideo'); return !video.paused && video.currentTime > start + 1.8; }, chapterStart, { timeout: 30000 });
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
    const unexpected = results.consoleErrors;
    assert.equal(unexpected.length, 0, JSON.stringify(unexpected));
    assert.equal(results.apiRequests.length, 0); return { javascriptErrors: 0, unexpectedConsoleErrors: 0, publicApiProbes: results.apiRequests.length };
  });
}

main().catch(error => { results.fatal = error.stack; console.error(error); }).finally(async () => {
  results.passed = !results.fatal && results.checks.length > 0 && results.checks.every(item => item.passed);
  results.summary = { passed: results.checks.filter(item => item.passed).length, failed: results.checks.filter(item => !item.passed).length };
  fs.writeFileSync(path.join(output, 'public-qa.json'), JSON.stringify(results, null, 2));
  if (context) await context.close(); if (browser) await browser.close();
  console.log(JSON.stringify(results.summary)); process.exitCode = results.passed ? 0 : 1;
});

