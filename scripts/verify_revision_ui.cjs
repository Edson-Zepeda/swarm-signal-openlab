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
const output = path.join(root, 'evidence', 'revision', 'ui');
const webRoot = path.join(root, 'web');
const fixture = JSON.parse(fs.readFileSync(path.join(webRoot, 'data', 'session.json'), 'utf8').replace(/^\uFEFF/, ''));
const videoTimeline = JSON.parse(fs.readFileSync(path.join(root, 'media', 'video', 'timeline.json'), 'utf8').replace(/^\uFEFF/, ''));
const demoOnly = process.argv.includes('--demo-only');
const externalDemoUrl = demoOnly && process.env.SWARM_DEMO_URL ? new URL(process.env.SWARM_DEMO_URL).href : null;
const reportName = demoOnly ? 'demo-qa.json' : 'qa.json';
const axePath = process.env.SWARM_AXE_PATH || resolveDependency('axe-core/axe.min.js');
const results = { timestamp: new Date().toISOString(), browser: 'Isolated Chromium-compatible headless context', sources: ['http://127.0.0.1:8766', 'http://127.0.0.1:8767/swarm-signal-openlab/'], checks: [], screenshots: [], pageErrors: [], resourceErrors: [], expectedStaticApiProbes: [] };
results.scope = demoOnly ? 'Updated demo only; dashboard QA is preserved in qa.json.' : 'Full dashboard and demo';
if (demoOnly) results.sources = [externalDemoUrl || 'http://127.0.0.1:8767/swarm-signal-openlab/demo.html'];
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
  if (!externalDemoUrl) await new Promise(resolve => server.listen(8767, '127.0.0.1', resolve));
  const browser = await chromium.launch({ ...(process.env.SWARM_BROWSER_EXECUTABLE ? { executablePath: process.env.SWARM_BROWSER_EXECUTABLE } : {}), headless: true });
  results.browserVersion = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  page.on('pageerror', error => results.pageErrors.push(error.message));
  page.on('response', response => { if (response.status() < 400) return; const item = { url: response.url(), status: response.status() }; (new URL(response.url()).pathname === '/api/state' ? results.expectedStaticApiProbes : results.resourceErrors).push(item); });
  const base = 'http://127.0.0.1:8767/swarm-signal-openlab/';
  const shot = async (name, fullPage = true) => { const target = path.join(output, name + '.png'); if (fullPage) await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: target, fullPage }); results.screenshots.push(path.relative(root, target)); };
  const loaded = async () => page.waitForFunction(() => Number(document.querySelector('#metricSamples').textContent) > 0);
  const seek = async value => page.locator('#replaySlider').evaluate((el, value) => { el.value = String(value); el.dispatchEvent(new Event('input', { bubbles: true })); }, value);
  const axe = async selector => { await page.addScriptTag({ path: axePath }); return page.evaluate(async selector => (await window.axe.run(selector || document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })), selector); };

  if (!demoOnly) {
  await page.goto(base, { waitUntil: 'networkidle' }); await loaded();
  await check('Entry stays at the top with delivery and mode visible', async () => {
    const state = await page.evaluate(() => ({ scroll: scrollY, hash: location.hash, heading: document.querySelector('h1').innerText, navTop: document.querySelector('.workspace-nav').getBoundingClientRect().top, deliveryTop: document.querySelector('.delivery-links').getBoundingClientRect().top, status: document.querySelector('#connectionStatus').textContent }));
    await shot('01-public-entry', false); assert.equal(state.scroll, 0); assert.equal(state.hash, ''); assert(state.navTop >= 0 && state.navTop < 900); assert.match(state.status, /Captura grabada/); return state;
  });
  await check('Delivery opens evidence and browser Back restores Monitor', async () => {
    await page.locator('[data-open-view=evidencia]').click(); assert(await page.locator('#evidencia').isVisible()); assert.match(page.url(), /view=evidencia/); await page.goBack(); assert(await page.locator('#monitor').isVisible()); return { history: 'Back restores view' };
  });
  for (const route of ['?view=propuesta', '#evidencia', '#monitor']) await check('Deep link ' + route, async () => {
    await page.goto(base + route, { waitUntil: 'networkidle' }); await loaded();
    const view = route.includes('propuesta') ? 'propuesta' : route.includes('evidencia') ? 'evidencia' : 'monitor'; assert(await page.locator('#' + view).isVisible()); assert.equal(await page.evaluate(() => scrollY), 0); assert.equal(new URL(page.url()).hash, ''); return { url: page.url(), scrollY: 0 };
  });
  await page.goto(base, { waitUntil: 'networkidle' }); await loaded();
  await check('Primary playback and pause are consistent', async () => {
    await page.locator('#replaySpeed').selectOption('8'); await page.locator('#captureButton').click(); await page.waitForTimeout(650);
    const n = Number(await page.locator('#metricSamples').textContent()); assert(n > 3 && n < 60); assert.equal(await page.locator('#captureButton').textContent(), 'Pausar reproducción');
    await page.locator('#captureButton').click(); const value = await page.locator('#replaySlider').inputValue(); await page.waitForTimeout(400); assert.equal(await page.locator('#replaySlider').inputValue(), value); assert.equal(await page.locator('#playButton').getAttribute('aria-label'), 'Reproducir captura'); return { speed: '8x', samples: n, paused: true };
  });
  await check('Seek uses exact frames, quality abstention and no invented spectrum', async () => {
    const stamp = value => typeof value === 'number' ? (value > 1e11 ? value / 1000 : value) : Date.parse(value) / 1000;
    const start = stamp(fixture.samples[0].timestamp), end = stamp(fixture.samples.at(-1).timestamp); const inspected = [];
    for (const position of [0, 50, 125, 250, 500, 750, 1000]) {
      await seek(position); const count = Number(await page.locator('#metricSamples').textContent()); assert.equal(count, fixture.samples.filter(s => stamp(s.timestamp) <= start + (end - start) * position / 1000).length);
      const frame = position === 1000 ? fixture : fixture.frames.filter(f => f.index <= count - 1).at(-1);
      const labels = { active: 'SEÑAL VARIABLE', present_still: 'CAMBIO SUAVE', absent: 'SEÑAL ESTABLE' };
      const expected = frame?.quality?.ready === false || !frame?.classification ? 'SIN VEREDICTO' : labels[frame.classification.motion_level]; assert.equal(await page.locator('#readingTag').textContent(), expected);
      if (!frame?.spectrum?.length) assert.equal(await page.locator('#spectrumBars rect').count(), 0);
      assert.match(await page.locator('#replaySlider').getAttribute('aria-valuetext'), /de .* segundos/); inspected.push({ position, count, expected, bars: await page.locator('#spectrumBars rect').count() });
    } return inspected;
  });
  await check('Static CSV contains every original sample', async () => {
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#exportButton').click()]); const target = path.join(output, 'static-export.csv'); await download.saveAs(target);
    const lines = fs.readFileSync(target, 'utf8').replace(/^\uFEFF/, '').trim().split(/\r?\n/); assert.equal(lines.length, fixture.samples.length + 1); return { samples: lines.length - 1 };
  });
  await check('Comparison reports all real captures and data quality', async () => {
    const data = JSON.parse(fs.readFileSync(path.join(webRoot, 'data', 'comparison.json'), 'utf8').replace(/^\uFEFF/, ''));
    await page.locator('#comparisonPanel > summary').click(); await page.locator('#comparisonRows tr').first().waitFor();
    const texts = await page.locator('#comparisonRows tr').allTextContents(); assert.equal(texts.length, data.sessions.length);
    data.sessions.forEach((s, index) => { assert(texts[index].includes(s.label)); assert(texts[index].includes(String(s.count))); assert(texts[index].includes(s.windows_eligible ? `${s.windows_valid} / ${s.windows_eligible}` : 'Sin elegibles')); });
    assert.match(await page.locator('#comparisonPhysical').textContent(), /sin confirmar/); assert.equal(await page.locator('#comparisonSeries path').count(), data.sessions.length);
    await page.locator('#comparisonPanel').evaluate(el => el.scrollIntoView({ block: 'start' })); await shot('02-comparison', false); return { sources: data.sessions.map(s => ({ label: s.label, count: s.count, eligible: s.windows_eligible, valid: s.windows_valid })), physicalConfirmed: data.physical.confirmed_sessions };
  });
  await check('Local help has startup steps and returns keyboard focus', async () => {
    await page.locator('.local-help-trigger').click(); assert.equal(await page.locator('#localHelpDialog').getAttribute('aria-labelledby'), 'localHelpTitle');
    assert.match(await page.locator('#localHelpDialog').innerText(), /Iniciar.cmd/); assert.match(await page.locator('#localHelpDialog').innerText(), /Etiqueta solo/); assert.equal(await page.evaluate(() => document.activeElement.closest('#localHelpDialog')?.id), 'localHelpDialog');
    const violations = await axe('#localHelpDialog'); assert.equal(violations.length, 0, JSON.stringify(violations)); await shot('03-local-help', false); await page.keyboard.press('Escape'); assert.equal(await page.locator('#localHelpDialog').isVisible(), false); assert.equal(await page.evaluate(() => document.activeElement.classList.contains('local-help-trigger')), true); return { labelled: true, violations: 0, focusRestored: true };
  });
  await check('Evidence statuses follow sources and stage five has a real image', async () => {
    await page.locator('[data-tab=evidencia]').click(); const stages = fixture.evidence.stages;
    assert.equal(await page.locator('#evidenceStages article').count(), stages.length);
    const completed = stages.filter(s => ['complete', 'passed', 'verified', 'done'].includes(s.status)).length;
    assert.equal(await page.locator('#evidenceProgress').textContent(), `${completed} / ${stages.length}`);
    const images = await page.locator('#evidenceStages .evidence-preview img').evaluateAll(els => els.map(el => ({ src: el.src, loaded: el.complete && el.naturalWidth > 0 })));
    assert(images.length > 0, 'A real monitoring screenshot must be linked.'); for (const image of images) { const response = await page.request.get(image.src); assert.equal(response.status(), 200); }
    await shot('04-evidence'); return { completed, stages: stages.length, images };
  });
  await check('Proposal and delivery documents resolve within subpath', async () => {
    await page.locator('[data-tab=propuesta]').click(); assert(await page.locator('#propuesta a[href="docs/SwarmSignal_Propuesta.pdf"]').isVisible());
    for (const file of ['docs/SwarmSignal_Informe.pdf', 'docs/SwarmSignal_Propuesta.pdf', 'demo.html']) { const r = await page.request.get(base + file); assert.equal(r.status(), 200); }
    const content = await page.locator('#propuesta').innerText(); for (const phrase of ['dron', 'Raspberry Pi', 'motores apagados', 'laptop']) assert(content.includes(phrase));
    await shot('05-proposal'); return { documents: '200', stationaryProposal: true };
  });
  for (const width of [320, 390, 768, 1440]) for (const tab of ['monitor', 'evidencia', 'propuesta']) await check(`Responsive ${width}px ${tab}`, async () => {
    await page.setViewportSize({ width, height: 900 }); await page.locator(`[data-tab=${tab}]`).click(); await page.waitForTimeout(160);
    const m = await page.evaluate(() => ({ viewport: innerWidth, pageWidth: document.documentElement.scrollWidth, body: parseFloat(getComputedStyle(document.body).fontSize), labels: [...document.querySelectorAll('.metric-label,#captureButton,#sessionPicker')].map(el => parseFloat(getComputedStyle(el).fontSize)), axes: [...document.querySelectorAll('#signalTicks .axis-text')].map(el => parseFloat(getComputedStyle(el).fontSize)) }));
    assert(m.pageWidth <= width, JSON.stringify(m)); assert(m.body >= 16); assert(m.labels.every(n => n >= 14)); assert(m.axes.every(n => n >= 14));
    if (width === 390 || width === 768) await shot(`${tab}-${width}`); return m;
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await check('Keyboard navigation between product views', async () => { await page.locator('[data-tab=monitor]').focus(); await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => document.activeElement.dataset.tab), 'evidencia'); await page.keyboard.press('Enter'); assert(await page.locator('#evidencia').isVisible()); return 'Tab and Enter'; });
  for (const tab of ['monitor', 'evidencia', 'propuesta']) await check('Axe WCAG ' + tab, async () => { await page.locator(`[data-tab=${tab}]`).click(); const violations = await axe(); assert.equal(violations.length, 0, JSON.stringify(violations)); return { violations: 0 }; });

  await check('Real local server is reachable and offers local capture without starting it', async () => {
    const api = await page.request.get('http://127.0.0.1:8766/api/state'); assert.equal(api.status(), 200); const state = await api.json(); assert(Array.isArray(state.samples));
    const livePage = await context.newPage(); await livePage.goto('http://127.0.0.1:8766', { waitUntil: 'networkidle' }); await livePage.waitForFunction(() => !document.querySelector('#sessionPicker').disabled || document.querySelector('#connectionStatus').textContent.includes('Capturando'));
    const status = await livePage.locator('#connectionStatus').textContent(); assert(!status.includes('Cargando'));
    if (state.status !== 'collecting' && !state.pending_save) { await livePage.locator('#captureButton').click(); await livePage.locator('#captureDialog').waitFor({ state: 'visible' }); assert.equal(await livePage.locator('#captureGroundTruth').inputValue(), 'unconfirmed'); await livePage.keyboard.press('Escape'); }
    await livePage.close(); return { realApi: true, state: state.status, status, captureStarted: false };
  });

  // These adapter/save/error scenarios exercise the UI against explicit fixtures;
  // they do not operate physical hardware or count as experimental evidence.
  const fake = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); const local = await fake.newPage();
  let mocked = { ...fixture, mode: 'live', status: 'ready', frames: [], pending_save: false }; let requests = []; let offline = false;
  await local.route('**/api/**', route => {
    const endpoint = new URL(route.request().url()).pathname;
    if (offline && endpoint === '/api/state') return route.abort('connectionrefused');
    if (endpoint === '/api/start') { requests.push(JSON.parse(route.request().postData())); return route.fulfill({ status: 400, json: { error: 'Prueba de interfaz: captura física no iniciada.' } }); }
    if (endpoint === '/api/stop') { requests.push({ action: 'retry-save' }); mocked = { ...mocked, pending_save: false, error: null, status: 'ready' }; return route.fulfill({ json: mocked }); }
    if (endpoint === '/api/interfaces') return route.fulfill({ json: { interfaces: ['Wi-Fi A', 'Wi-Fi B'], selection_required: true } });
    if (endpoint === '/api/sessions') return route.fulfill({ json: { sessions: [] } });
    if (endpoint === '/api/comparison') return route.fulfill({ json: { sessions: [] } });
    return route.fulfill({ json: mocked });
  });
  await local.goto(base, { waitUntil: 'networkidle' });
  await check('Local capture dialog is named, labelled by operator and selects adapter', async () => {
    await local.locator('#captureButton').click(); assert.equal(await local.locator('#captureDialog').getAttribute('aria-labelledby'), 'captureDialogTitle'); assert.equal(await local.evaluate(() => document.activeElement.id), 'captureLabel'); assert.equal(await local.locator('#captureGroundTruth').inputValue(), 'unconfirmed');
    await local.locator('#captureInterface').selectOption('Wi-Fi B'); await local.locator('#captureGroundTruth').selectOption('walking'); assert.match(await local.locator('.dialog-note').first().textContent(), /cruza entre laptop y router/);
    await local.locator('#submitCapture').click(); await local.locator('#captureError:not(.hidden)').waitFor(); assert.equal(requests.at(-1).ground_truth, 'walking'); assert.equal(requests.at(-1).interface, 'Wi-Fi B');
    await local.keyboard.press('Escape'); await local.locator('#captureButton').click(); assert.equal(await local.locator('#captureGroundTruth').inputValue(), 'unconfirmed'); await local.keyboard.press('Escape'); return { fixtureOnly: true, request: requests.at(-1), reset: 'unconfirmed' };
  });
  await check('Pending save remains retryable and blocks new capture', async () => {
    mocked = { ...mocked, status: 'save_error', pending_save: true, error: 'No se pudo escribir la captura.' }; await local.waitForFunction(() => document.querySelector('#stopButton').textContent === 'Reintentar guardado'); assert(await local.locator('#captureButton').isHidden()); assert(await local.locator('#stopButton').isEnabled()); assert.match(await local.locator('#notice').textContent(), /escribir/);
    await local.locator('#stopButton').click(); await local.waitForFunction(() => document.querySelector('#stopButton').classList.contains('hidden')); assert.equal(requests.at(-1).action, 'retry-save'); return { fixtureOnly: true, savedOnRetry: true };
  });
  await check('Disconnected receiver is never shown as live and recovers', async () => {
    mocked = { ...mocked, status: 'collecting', mode: 'live' }; await local.waitForFunction(() => document.querySelector('#connectionStatus').textContent.includes('Capturando')); offline = true;
    await local.waitForFunction(() => document.querySelector('#readingTag').textContent === 'LECTURA RETENIDA'); assert(await local.locator('#stopButton').isDisabled()); assert.equal(await local.locator('#readingGlyph').evaluate(el => el.classList.contains('active')), false);
    await local.setViewportSize({ width: 768, height: 900 }); await local.waitForTimeout(200); assert.equal(await local.locator('#readingTag').textContent(), 'LECTURA RETENIDA');
    offline = false; await local.waitForFunction(() => document.querySelector('#connectionStatus').textContent.includes('Capturando')); assert(await local.locator('#stopButton').isEnabled()); return { fixtureOnly: true, retainedLabel: true, recovered: true };
  });
  await fake.close();
  }
  await page.goto(externalDemoUrl || base + 'demo.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await check('Demo playback, seek, audio and captions', async () => {
    await page.waitForFunction(() => document.querySelector('#demoVideo').readyState >= 1);
    const meta = await page.locator('#demoVideo').evaluate(v => ({ duration: v.duration, width: v.videoWidth, height: v.videoHeight, captions: [...v.textTracks].map(t => t.language) })); assert(Math.abs(meta.duration - videoTimeline.duration_seconds) < .15); assert.equal(meta.width, 1920); assert(meta.captions.includes('es'));
    const chapterTimes = await page.locator('.chapter').evaluateAll(els => els.map(el => Number(el.dataset.time))); assert.equal(chapterTimes.length, videoTimeline.scenes.length); chapterTimes.forEach((time, i) => assert(Math.abs(time - videoTimeline.scenes[i].start) < .01)); meta.chapters = chapterTimes;
    const chapter = page.locator('.chapter').nth(Math.floor(await page.locator('.chapter').count() / 2)); const chapterStart = Number(await chapter.getAttribute('data-time'));
    await chapter.click();
    try { await page.waitForFunction(start => { const v = document.querySelector('#demoVideo'); return !v.paused && v.currentTime > start + 1.8; }, chapterStart); }
    catch (error) { const observed = await page.locator('#demoVideo').evaluate(v => ({ time: v.currentTime, duration: v.duration, paused: v.paused, ready: v.readyState, seekable: Array.from({ length: v.seekable.length }, (_, i) => [v.seekable.start(i), v.seekable.end(i)]) })); throw new Error(`Chapter target ${chapterStart}s was not reached: ${JSON.stringify(observed)}. ${error.message}`); }
    const play = await page.locator('#demoVideo').evaluate(v => ({ position: v.currentTime, audio: v.webkitAudioDecodedByteCount, error: v.error?.code || null })); assert(play.audio > 0); assert.equal(play.error, null); await page.locator('#demoVideo').evaluate(v => v.pause()); await shot(demoOnly ? '07-demo-updated' : '06-demo'); return { ...meta, ...play };
  });
  await check('Axe WCAG demo', async () => { const violations = await axe(); assert.equal(violations.length, 0, JSON.stringify(violations)); return { violations: 0 }; });
  for (const width of [320, 390, 768]) await check('Demo responsive ' + width, async () => { await page.setViewportSize({ width, height: 900 }); const w = await page.evaluate(() => document.documentElement.scrollWidth); assert(w <= width); if (width === 390) await shot(demoOnly ? 'demo-updated-390' : 'demo-390'); return { width, pageWidth: w }; });
  await check('No JavaScript exceptions', async () => { assert.equal(results.pageErrors.length, 0, JSON.stringify(results.pageErrors)); return results.pageErrors; });
  await check('All requested static assets resolve', async () => { assert.equal(results.resourceErrors.length, 0, JSON.stringify(results.resourceErrors)); return { resourceErrors: 0, expectedLocalStaticApiProbes: results.expectedStaticApiProbes.length }; });
  results.passed = results.checks.every(c => c.passed); results.summary = { passed: results.checks.filter(c => c.passed).length, failed: results.checks.filter(c => !c.passed).length };
  fs.writeFileSync(path.join(output, reportName), JSON.stringify(results, null, 2)); await browser.close(); if (server.listening) await new Promise(resolve => server.close(resolve)); console.log(JSON.stringify(results.summary)); process.exitCode = results.passed ? 0 : 1;
})().catch(error => { results.fatal = error.stack; fs.writeFileSync(path.join(output, reportName), JSON.stringify(results, null, 2)); console.error(error); server.close(); process.exit(1); });


