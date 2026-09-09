const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
function resolveDependency(name) {
  try { return require.resolve(name); }
  catch (error) { if (process.env.SWARM_NODE_MODULES) return require.resolve(path.join(process.env.SWARM_NODE_MODULES, name)); throw error; }
}
const { chromium } = require(resolveDependency('playwright'));

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'evidence', 'ui');
const webRoot = path.join(root, 'web');
const fixture = JSON.parse(fs.readFileSync(path.join(webRoot, 'data', 'session.json'), 'utf8').replace(/^\uFEFF/, ''));
const axePath = process.env.SWARM_AXE_PATH || resolveDependency('axe-core/axe.min.js');
const results = { timestamp: new Date().toISOString(), browser: 'Isolated Chromium-compatible headless context', sources: ['http://127.0.0.1:8766', 'http://127.0.0.1:8767/swarm-signal-openlab/'], checks: [], screenshots: [], pageErrors: [], networkFailures: [] };
fs.mkdirSync(output, { recursive: true });

async function check(name, run) {
  try { const detail = await run(); results.checks.push({ name, passed: true, detail: detail ?? null }); console.log('PASS ' + name); }
  catch (error) { results.checks.push({ name, passed: false, error: error.message }); console.log('FAIL ' + name + ': ' + error.message); }
}

const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
  const prefix = '/swarm-signal-openlab/';
  if (!pathname.startsWith(prefix)) { res.writeHead(404); res.end('Not found'); return; }
  const relative = pathname.slice(prefix.length) || 'index.html';
  const file = path.resolve(webRoot, relative);
  if (!file.startsWith(webRoot + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); res.end('Not found'); return; }
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.pdf': 'application/pdf', '.csv': 'text/csv', '.mp4': 'video/mp4', '.vtt': 'text/vtt', '.jpg': 'image/jpeg', '.png': 'image/png' };
  const size = fs.statSync(file).size;
  const headers = { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Accept-Ranges': 'bytes' };
  const range = req.headers.range && /^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
  if (range) {
    const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start > end || start >= size) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); res.end(); return; }
    res.writeHead(206, { ...headers, 'Content-Length': end - start + 1, 'Content-Range': `bytes ${start}-${end}/${size}` });
    fs.createReadStream(file, { start, end }).pipe(res);
  } else { res.writeHead(200, { ...headers, 'Content-Length': size }); fs.createReadStream(file).pipe(res); }
});

(async () => {
  await new Promise((resolve) => server.listen(8767, '127.0.0.1', resolve));
  const browser = await chromium.launch({ ...(process.env.SWARM_BROWSER_EXECUTABLE ? { executablePath: process.env.SWARM_BROWSER_EXECUTABLE } : {}), headless: true });
  results.browserVersion = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', error => results.pageErrors.push(error.message));
  const screenshot = async (name) => { const target = path.join(output, name + '.png'); await page.screenshot({ path: target, fullPage: true }); results.screenshots.push(path.relative(root, target)); };
  await page.goto('http://127.0.0.1:8766', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => !document.querySelector('#sessionPicker').disabled, undefined, { timeout: 75000 });
  await page.locator('#sessionPicker').selectOption('20260909T062522_420b46');
  await page.waitForFunction(() => document.querySelector('#metricSamples').textContent === '233');
  await check('API recorded session is real and unlabelled', async () => {
    assert.equal(await page.locator('#metricSamples').textContent(), '233');
    assert.match(await page.locator('#physicalCondition').textContent(), /sin etiquetar/);
    assert.match(await page.locator('#connectionStatus').textContent(), /Captura grabada/);
    assert.equal(await page.locator('#readingTag').textContent(), 'SIN VEREDICTO');
    return { samples: 233, status: await page.locator('#readingTitle').textContent() };
  });
  await check('API CSV has all 233 samples', async () => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#exportButton').click()]);
    const save = path.join(output, 'qa_api_export.csv'); await download.saveAs(save);
    const lines = fs.readFileSync(save, 'utf8').trim().split(/\r?\n/);
    assert.equal(lines.length, 234); return { rows: lines.length - 1 };
  });
  await check('API loss does not keep an alive status', async () => {
    await page.locator('#sessionPicker').selectOption('current');
    await page.route('**/api/state', route => route.abort());
    await page.waitForFunction(() => document.querySelector('#connectionStatus').textContent.includes('sin conexión'), undefined, { timeout: 12000 });
    assert.equal(await page.locator('#connectionStatus').evaluate(el => el.classList.contains('live')), false);
    await page.unroute('**/api/state');
    const disconnectedStatus = await page.locator('#connectionStatus').textContent();
    await page.waitForFunction(() => !document.querySelector('#connectionStatus').textContent.includes('sin conexión'), undefined, { timeout: 6000 });
    assert.equal(await page.locator('#notice').isVisible(), false);
    return { disconnectedStatus, recoveredStatus: await page.locator('#connectionStatus').textContent() };
  });
  await page.goto('http://127.0.0.1:8767/swarm-signal-openlab/', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelector('#metricSamples').textContent === '233');
  await check('Static subpath fallback loads actual capture', async () => {
    assert.equal(await page.locator('#metricSamples').textContent(), String(fixture.samples.length));
    assert.match(await page.locator('#captureButton').textContent(), /Reproducir captura/);
    assert.equal(await page.locator('#sessionPicker').isDisabled(), true);
    return { samples: fixture.samples.length, mode: await page.locator('#connectionStatus').textContent() };
  });
  await check('Static playback, pause and speed', async () => {
    await page.locator('#replaySpeed').selectOption('8');
    await page.locator('#playButton').click();
    await page.waitForTimeout(1100);
    const activeCount = Number((await page.locator('#metricSamples').textContent()).replace(/,/g, ''));
    assert(activeCount > 5 && activeCount < 80, 'Playback must advance through actual samples at 8x.');
    await page.locator('#playButton').click();
    const time = await page.locator('#replayTime').textContent();
    await page.waitForTimeout(500);
    assert.equal(await page.locator('#replayTime').textContent(), time);
    assert.equal(await page.locator('#playButton').getAttribute('aria-label'), 'Reproducir captura');
    return { activeCount, pauseTime: time, speed: '8x' };
  });
  await check('Replay uses exact recorded frame classifications', async () => {
    const inspected = [];
    const stamp = value => typeof value === 'number' ? (value > 1e11 ? value / 1000 : value) : Date.parse(value) / 1000;
    const start = stamp(fixture.samples[0].timestamp), end = stamp(fixture.samples.at(-1).timestamp);
    for (const position of [0, 50, 125, 250, 500, 750, 1000]) {
      await page.locator('#replaySlider').evaluate((el, value) => { el.value = String(value); el.dispatchEvent(new Event('input', { bubbles: true })); }, position);
      const count = Number((await page.locator('#metricSamples').textContent()).replace(/,/g, ''));
      const expectedCount = fixture.samples.filter(s => stamp(s.timestamp) <= start + (end - start) * position / 1000).length;
      assert.equal(count, expectedCount);
      const frame = position === 1000 ? fixture : fixture.frames.filter(f => f.index <= count - 1).at(-1);
      const labels = { active: 'SEÑAL VARIABLE', present_still: 'CAMBIO SUAVE', absent: 'SEÑAL ESTABLE' };
      const expected = frame?.quality?.ready === false || !frame?.classification ? 'SIN VEREDICTO' : labels[frame.classification.motion_level];
      const actual = await page.locator('#readingTag').textContent(); assert.equal(actual, expected);
      inspected.push({ position, count, expected, actual });
    }
    return inspected;
  });
  await check('Static CSV has all real samples', async () => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#exportButton').click()]);
    const save = path.join(output, 'qa_static_export.csv'); await download.saveAs(save);
    const lines = fs.readFileSync(save, 'utf8').replace(/^\uFEFF/, '').trim().split(/\r?\n/);
    assert.equal(lines.length, fixture.samples.length + 1);
    assert(lines[1].includes(String(fixture.samples[0].rssi_dbm)));
    assert(lines.at(-1).includes(String(fixture.samples.at(-1).rssi_dbm)));
    return { rows: lines.length - 1 };
  });
  for (const width of [320, 390, 768, 1440]) {
    await check(`Responsive ${width}px monitor no overflow and legible`, async () => {
      await page.setViewportSize({ width, height: width > 1000 ? 1000 : 900 });
      await page.locator('[data-tab="monitor"]').click();
      await page.waitForTimeout(550);
      const measurements = await page.evaluate(() => ({ viewport: innerWidth, pageWidth: document.documentElement.scrollWidth, bodyFont: parseFloat(getComputedStyle(document.body).fontSize), labelFonts: [...document.querySelectorAll('.metric-label, #captureButton, #sessionPicker')].map(el => parseFloat(getComputedStyle(el).fontSize)), axisFonts: [...document.querySelectorAll('#signalTicks .axis-text')].map(el => parseFloat(getComputedStyle(el).fontSize)) }));
      await screenshot('monitor-' + width);
      assert(measurements.pageWidth <= measurements.viewport, `Overflow ${measurements.pageWidth - measurements.viewport}px`);
      assert(measurements.bodyFont >= 16);
      assert(measurements.labelFonts.every(size => size >= 14), 'Primary labels must be at least 14px.');
      assert(measurements.axisFonts.every(size => size >= 13.5));
      return measurements;
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await check('Evidence is six verified, two partial, with accessible links', async () => {
    await page.locator('[data-tab="evidencia"]').click();
    assert.equal(await page.locator('#evidenceProgress').textContent(), '6 / 8');
    assert.equal(await page.locator('.stage-status.complete').count(), 6);
    assert.equal(await page.locator('.stage-status').filter({ hasText: 'PARCIAL' }).count(), 2);
    const links = await page.locator('#evidencia a').evaluateAll(els => els.map(el => ({ text: el.textContent.trim(), href: el.href })));
    const statuses = [];
    for (const link of links) { const response = await page.request.get(link.href); statuses.push({ ...link, status: response.status() }); }
    await screenshot('evidence-1440');
    assert(statuses.every(link => link.status === 200), JSON.stringify(statuses.filter(link => link.status !== 200)));
    return statuses;
  });
  await check('Proposal has drone-specific boundaries', async () => {
    await page.locator('[data-tab="propuesta"]').click();
    const content = await page.locator('#propuesta').innerText();
    for (const phrase of ['dron', 'Raspberry Pi', 'motores apagados', 'laptop', 'Router controlado']) assert(content.includes(phrase), phrase);
    await screenshot('proposal-1440'); return { boundedHardwareProposal: true };
  });
  for (const width of [320, 390, 768]) {
    for (const tab of ['evidencia', 'propuesta']) {
      await check(`Responsive ${width}px ${tab} no overflow`, async () => {
        await page.setViewportSize({ width, height: 900 }); await page.locator(`[data-tab="${tab}"]`).click(); await page.waitForTimeout(550);
        const value = await page.evaluate(() => ({ viewport: innerWidth, pageWidth: document.documentElement.scrollWidth }));
        await screenshot(`${tab}-${width}`); assert(value.pageWidth <= value.viewport, JSON.stringify(value)); return value;
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await check('Keyboard section navigation', async () => {
    await page.locator('[data-tab="monitor"]').focus(); await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.dataset.tab), 'evidencia');
    await page.keyboard.press('Enter'); assert.equal(await page.locator('#evidencia').isVisible(), true);
    await page.keyboard.press('Tab'); await page.keyboard.press('Enter'); assert.equal(await page.locator('#propuesta').isVisible(), true);
    return { navigation: 'Tab and Enter' };
  });
  for (const tab of ['monitor', 'evidencia', 'propuesta']) {
    await check('Axe WCAG ' + tab, async () => {
      await page.locator(`[data-tab="${tab}"]`).click();
      await page.waitForTimeout(550);
      await page.addScriptTag({ path: axePath });
      const audit = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => ({ id: v.id, impact: v.impact, description: v.description, nodes: v.nodes.map(n => ({ target: n.target, failureSummary: n.failureSummary })) })));
      assert.equal(audit.length, 0, JSON.stringify(audit)); return { violations: 0 };
    });
  }
  await page.goto('http://127.0.0.1:8767/swarm-signal-openlab/demo.html', { waitUntil: 'networkidle' });
  await check('Demo duration, chapter seek, playback and audio track', async () => {
    await page.waitForFunction(() => document.querySelector('#demoVideo').readyState >= 1, undefined, { timeout: 15000 });
    const metadata = await page.locator('#demoVideo').evaluate(video => ({ duration: video.duration, width: video.videoWidth, height: video.videoHeight, captions: [...video.textTracks].map(track => ({ language: track.language, label: track.label })) }));
    assert(Math.abs(metadata.duration - 104.8) < 1);
    assert.equal(metadata.width, 1920); assert.equal(metadata.height, 1080);
    assert(metadata.captions.some(track => track.language === 'es'));
    results.videoMetadata = metadata;
    await page.locator('.chapter[data-time="63.267"]').click();
    await page.waitForFunction(() => { const video = document.querySelector('#demoVideo'); return !video.paused && video.currentTime > 63.5; }, undefined, { timeout: 15000 });
    const playback = await page.locator('#demoVideo').evaluate(video => ({ time: video.currentTime, paused: video.paused, audioDecodedBytes: video.webkitAudioDecodedByteCount || 0, muted: video.muted, volume: video.volume, videoError: video.error?.code || null }));
    assert(playback.audioDecodedBytes > 0, 'An audio track must be decoded.');
    assert.equal(playback.videoError, null);
    await page.locator('#demoVideo').evaluate(video => video.pause());
    await screenshot('demo-1440');
    return { ...metadata, ...playback };
  });
  for (const width of [320, 390, 768]) {
    await check(`Responsive ${width}px demo no overflow`, async () => {
      await page.setViewportSize({ width, height: 900 }); await page.waitForTimeout(200);
      const value = await page.evaluate(() => ({ viewport: innerWidth, pageWidth: document.documentElement.scrollWidth }));
      await screenshot(`demo-${width}`); assert(value.pageWidth <= value.viewport, JSON.stringify(value)); return value;
    });
  }
  await check('Axe WCAG demo', async () => {
    await page.setViewportSize({ width: 1440, height: 1000 }); await page.addScriptTag({ path: axePath });
    const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })));
    assert.equal(violations.length, 0, JSON.stringify(violations)); return { violations: 0 };
  });
  await check('No JavaScript exceptions', async () => { assert.equal(results.pageErrors.length, 0); return results.pageErrors; });
  results.passed = results.checks.every(item => item.passed);
  results.summary = { passed: results.checks.filter(item => item.passed).length, failed: results.checks.filter(item => !item.passed).length };
  fs.writeFileSync(path.join(output, 'qa.json'), JSON.stringify(results, null, 2));
  await browser.close(); await new Promise(resolve => server.close(resolve));
  console.log(JSON.stringify(results.summary)); process.exitCode = results.passed ? 0 : 1;
})().catch(error => { results.fatal = error.stack; fs.writeFileSync(path.join(output, 'qa.json'), JSON.stringify(results, null, 2)); console.error(error); server.close(); process.exit(1); });
