'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fmt = new Intl.NumberFormat('es-MX', { maximumFractionDigits: 2 });
  let state = null;
  let samples = [];
  let sessions = [];
  let backendAvailable = false;
  let selectedSession = 'current';
  let playing = false;
  let position = 1;
  let animationFrame = 0;
  let animationTime = 0;
  let lastRender = 0;
  let busy = false;
  let firstLoad = true;
  let toastTimer;
  let csvObjectUrl;
  let lastSignature = '';
  let fetchFailures = 0;
  let comparison = null;
  const text = (id, value) => { $(id).textContent = value; };
  const finite = (value) => typeof value === 'number' && Number.isFinite(value);
  const number = (value, digits = 2) => finite(value) ? value.toLocaleString('es-MX', { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '—';
  const stamp = (value) => typeof value === 'number' ? (value > 1e11 ? value / 1000 : value) : Date.parse(value) / 1000;
  const durationText = (value) => { const seconds = Math.max(0, Math.floor(value || 0)); return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; };
  const actualDuration = (data) => data.length > 1 ? Math.max(0, data[data.length - 1]._time - data[0]._time) : 0;
  const cleanSamples = (data) => (Array.isArray(data) ? data : []).filter((s) => finite(s.rssi_dbm) && Number.isFinite(stamp(s.timestamp))).map((s) => ({ ...s, _time: stamp(s.timestamp) })).sort((a, b) => a._time - b._time);
  const setHidden = (id, hidden) => $(id).classList.toggle('hidden', hidden);

  function createSvg(tag, attrs, value) {
    const el = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, item]) => el.setAttribute(key, String(item)));
    if (value != null) el.textContent = value;
    return el;
  }

  function grid(gridId, ticksId, dimensions, bounds, maxTime, unit = 's') {
    const { width, height, left, right, top, bottom } = dimensions;
    const lines = document.createDocumentFragment();
    const labels = document.createDocumentFragment();
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    for (let i = 0; i <= 3; i++) {
      const y = top + i * plotHeight / 3;
      const value = bounds.max - i * (bounds.max - bounds.min) / 3;
      lines.append(createSvg('line', { x1: left, y1: y, x2: width - right, y2: y, class: 'grid-line' }));
      labels.append(createSvg('text', { x: left - 10, y: y + 4, 'text-anchor': 'end', class: 'axis-text' }, number(value, Math.abs(bounds.max - bounds.min) < 3 ? 1 : 0)));
    }
    for (let i = 0; i <= 4; i++) {
      const x = left + i * plotWidth / 4;
      if (i > 0 && i < 4) lines.append(createSvg('line', { x1: x, y1: top, x2: x, y2: height - bottom, class: 'grid-line', opacity: '.4' }));
      const value = maxTime * i / 4;
      labels.append(createSvg('text', { x, y: height - 7, 'text-anchor': i === 0 ? 'start' : i === 4 ? 'end' : 'middle', class: 'axis-text' }, `${number(value, maxTime < 5 ? 2 : 0)}${unit ? ' ' + unit : ''}`));
    }
    $(gridId).replaceChildren(lines);
    $(ticksId).replaceChildren(labels);
  }

  function points(data, dimensions, bounds, totalTime) {
    const { width, height, left, right, top, bottom } = dimensions;
    const xSize = width - left - right;
    const ySize = height - top - bottom;
    return data.map((point) => [left + point.x / Math.max(totalTime, .001) * xSize, top + (bounds.max - point.y) / Math.max(bounds.max - bounds.min, .001) * ySize]);
  }

  function path(pointsArray) {
    return pointsArray.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  }

  function stats(data) {
    const values = data.map((sample) => sample.rssi_dbm);
    const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
    const variance = values.length > 1 ? values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1) : null;
    const duration = actualDuration(data);
    return { mean, variance, std: variance == null ? null : Math.sqrt(variance), range: values.length ? Math.max(...values) - Math.min(...values) : null, sample_rate_hz: duration > 0 ? (data.length - 1) / duration : 0, n_samples: values.length };
  }

  function rollingVariance(data) {
    if (data.length < 3) return [];
    const result = [];
    let start = 0;
    for (let i = 2; i < data.length; i++) {
      while (start < i && data[start]._time < data[i]._time - 5) start++;
      const slice = data.slice(start, i + 1);
      if (slice.length < 3) continue;
      result.push({ x: data[i]._time - data[0]._time, y: stats(slice).variance });
    }
    return result;
  }

  function spectrum(data) {
    if (data.length < 8) return [];
    const window = data.filter((s) => s._time >= data[data.length-1]._time - 15);
    const signal = window.slice(-256);
    const size = signal.length;
    if (size < 4) return [];
    const sampling = stats(signal).sample_rate_hz;
    if (!sampling) return [];
    const mean = signal.reduce((sum, sample) => sum + sample.rssi_dbm, 0) / size;
    const values = signal.map((sample, index) => (sample.rssi_dbm - mean) * (.5 - .5 * Math.cos(2 * Math.PI * index / (size - 1))));
    const result = [];
    for (let k = 1; k <= Math.floor(size / 2); k++) {
      let real = 0, imag = 0;
      for (let i = 0; i < size; i++) {
        const phase = 2 * Math.PI * k * i / size;
        real += values[i] * Math.cos(phase);
        imag -= values[i] * Math.sin(phase);
      }
      result.push({ hz: k * sampling / size, power: (real * real + imag * imag) / size });
    }
    return result;
  }

  function analysisAt(data) {
    if (position >= .999 || state?.status === 'collecting') return state || {};
    if (!Array.isArray(state?.frames) || !data.length) return {};
    const index = data.length - 1;
    let frame = null;
    for (const candidate of state.frames) {
      if (candidate.index <= index) frame = candidate;
      else break;
    }
    return frame || {};
  }

  function drawSignal(data) {
    const width = Math.max(200, Math.round($('signalChart').getBoundingClientRect().width) || 960);
    const dim = { width, height: width < 500 ? 225 : 240, left: 47, right: 13, top: 14, bottom: 32 };
    $('signalChart').setAttribute('viewBox', `0 0 ${width} ${dim.height}`);
    const values = samples.map((sample) => sample.rssi_dbm);
    const min = values.length ? Math.min(...values) : -80;
    const max = values.length ? Math.max(...values) : -40;
    const pad = Math.max(2, (max - min) * .18);
    const bounds = { min: Math.floor(min - pad), max: Math.ceil(max + pad) };
    const total = Math.max(actualDuration(samples), 1);
    grid('signalGrid', 'signalTicks', dim, bounds, total);
    const firstTime = samples[0]?._time || 0;
    const analysisEnd = data.length ? data[data.length - 1]._time - firstTime : 0;
    const analysisStart = Math.max(0, analysisEnd - 15);
    const plotWidth = dim.width - dim.left - dim.right;
    const windowRect = $('analysisWindow');
    windowRect.setAttribute('x', dim.left + analysisStart / total * plotWidth);
    windowRect.setAttribute('y', dim.top);
    windowRect.setAttribute('width', Math.max(0, (analysisEnd - analysisStart) / total * plotWidth));
    windowRect.setAttribute('height', dim.height - dim.top - dim.bottom);
    text('analysisWindowLabel', data.length ? `Ventana analizada: ${number(analysisStart, 1)}–${number(analysisEnd, 1)} s` : 'Ventana analizada / hasta 15 s');
    text('spectrumWindow', data.length ? `Misma ventana: ${number(analysisStart, 1)}–${number(analysisEnd, 1)} s` : 'Ventana / hasta 15 s');
    const plot = points(data.map((s) => ({ x: s._time - firstTime, y: s.rssi_dbm })), dim, bounds, total);
    const line = path(plot);
    $('signalLine').setAttribute('d', line);
    $('signalGlowPath').setAttribute('d', line);
    $('signalArea').setAttribute('d', plot.length ? `${line} L${plot[plot.length - 1][0]},${dim.height - dim.bottom} L${plot[0][0]},${dim.height - dim.bottom} Z` : '');
    $('signalCursor').style.display = plot.length ? '' : 'none';
    if (plot.length) { $('signalCursor').setAttribute('cx', plot[plot.length - 1][0]); $('signalCursor').setAttribute('cy', plot[plot.length - 1][1]); }
    setHidden('chartEmpty', data.length > 0);
    if (data.length) {
      const mini = points(data.slice(-40).map((s, i) => ({ x: i, y: s.rssi_dbm })), { width: 120, height: 40, left: 0, right: 0, top: 3, bottom: 3 }, bounds, Math.min(39, data.length - 1) || 1);
      $('miniRssi').replaceChildren(createSvg('path', { d: path(mini) }));
    } else $('miniRssi').replaceChildren();
    $('signalChart').setAttribute('aria-label', data.length ? `RSSI: ${data.length} muestras, última lectura ${number(data[data.length - 1].rssi_dbm, 1)} dBm. Rango completo: ${min} a ${max} dBm.` : 'Sin muestras de RSSI.');
  }

  function drawVariance(data) {
    const values = rollingVariance(data);
    const max = values.length ? Math.max(...values.map((v) => v.y)) : 0;
    const width = Math.max(200, Math.round($('varianceChart').getBoundingClientRect().width) || 600);
    const dim = { width, height: 165, left: 38, right: 8, top: 8, bottom: 28 };
    $('varianceChart').setAttribute('viewBox', `0 0 ${width} 165`);
    const total = Math.max(actualDuration(samples), 1);
    const bounds = { min: 0, max: Math.max(.3, max * 1.12) };
    grid('varianceGrid', 'varianceTicks', dim, bounds, total);
    const plot = points(values, dim, bounds, total);
    $('varianceLine').setAttribute('d', path(plot));
    $('varianceArea').setAttribute('d', plot.length ? `${path(plot)} L${plot[plot.length - 1][0]},${dim.height - dim.bottom} L${plot[0][0]},${dim.height - dim.bottom} Z` : '');
    text('variancePeak', values.length ? `Pico ${number(max)} dBm²` : 'Pico —');
    text('varianceWindow', 'Ventana móvil / 5 s');
    $('varianceChart').setAttribute('aria-label', `Varianza en ventanas móviles de 5 segundos. ${values.length ? `Pico ${number(max)} dBm al cuadrado.` : 'Sin muestras suficientes.'}`);
  }

  function drawSpectrum(data) {
    const analysis = analysisAt(data);
    const values = (Array.isArray(analysis.spectrum) ? analysis.spectrum : []).filter((item) => finite(item.hz) && finite(item.power) && item.hz > 0 && item.power >= 0);
    const width = Math.max(200, Math.round($('spectrumChart').getBoundingClientRect().width) || 600);
    const dim = { width, height: 165, left: 38, right: 8, top: 8, bottom: 28 };
    $('spectrumChart').setAttribute('viewBox', `0 0 ${width} 165`);
    const maxPower = values.length ? Math.max(...values.map((v) => v.power)) : 0;
    const maxHz = values.length ? Math.max(...values.map((v) => v.hz)) : Math.max(stats(data).sample_rate_hz / 2, .5);
    grid('spectrumGrid', 'spectrumTicks', dim, { min: 0, max: Math.max(.01, maxPower * 1.15) }, maxHz, '');
    const groups = [];
    const groupSize = Math.max(1, Math.ceil(values.length / 48));
    for (let i = 0; i < values.length; i += groupSize) { const segment = values.slice(i, i + groupSize); groups.push(segment.reduce((best, item) => item.power > best.power ? item : best, segment[0])); }
    const bars = document.createDocumentFragment();
    const barWidth = Math.max(2, Math.min(11, (dim.width - dim.left - dim.right) / Math.max(groups.length, 1) * .7));
    const baseline = dim.height - dim.bottom;
    groups.forEach((item) => {
      const x = dim.left + item.hz / maxHz * (dim.width - dim.left - dim.right);
      const height = maxPower > 0 ? item.power / (maxPower * 1.15) * (baseline - dim.top) : 0;
      if (height > 0) bars.append(createSvg('rect', { x: Math.min(dim.width - dim.right - barWidth, x - barWidth / 2), y: baseline - height, width: barWidth, height, rx: 2 }));
    });
    $('spectrumBars').replaceChildren(bars);
    const peak = maxPower > 0 ? values.reduce((best, item) => item.power > best.power ? item : best, values[0]) : null;
    text('spectrumPeak', !values.length ? 'FFT no disponible' : analysis.quality?.ready === false ? 'Solo exploración espectral' : peak ? `Pico ${number(peak.hz, 3)} Hz` : 'Sin frecuencia dominante');
    $('spectrumChart').setAttribute('aria-label', peak ? `Espectro de potencia. Frecuencia dominante ${number(peak.hz, 3)} Hz.` : 'Sin frecuencia dominante detectable.');
  }

  function renderClassification(data, features) {
    if (backendAvailable && selectedSession === 'current' && fetchFailures >= 2) {
      text('readingTag', 'LECTURA RETENIDA'); text('readingTitle', 'Receptor sin conexión.'); text('readingDescription', 'Se muestra el último dato recibido. Restablece la conexión para continuar.');
      $('readingGlyph').classList.remove('active'); document.querySelector('.reading-panel').dataset.level = ''; return;
    }
    const threshold = finite(state?.thresholds?.variance) ? state.thresholds.variance : .3;
    const analysis = analysisAt(data);
    const authoritative = analysis.classification;
    const quality = analysis.quality;
    let level = null;
    if (quality?.ready !== false && authoritative && ['absent', 'present_still', 'active'].includes(authoritative.motion_level)) level = authoritative.motion_level;
    const wording = {
      active: { tag: 'SEÑAL VARIABLE', title: 'Indicio de movimiento.', description: 'La señal cambia. Contrasta este indicio con lo ocurrido en el entorno.' },
      present_still: { tag: 'CAMBIO SUAVE', title: 'Variación lenta.', description: 'Hay cambios suaves en la señal; por sí solos no confirman presencia.' },
      absent: { tag: 'SEÑAL ESTABLE', title: 'Sin cambio detectado.', description: 'RSSI permanece estable. Esto no descarta que haya personas.' }
    };
    const unavailable = quality?.ready === false;
    const result = wording[level] || { tag: data.length ? 'SIN VEREDICTO' : 'SIN DATOS', title: data.length ? unavailable && quality.reason ? `${quality.reason.replace(/[.!]$/, '')}.` : 'Aún sin veredicto.' : 'Lista para escuchar.', description: data.length ? unavailable ? 'La calidad de esta ventana no permite emitir un indicio confiable.' : 'Esta ventana aún no tiene una clasificación validada por el análisis.' : 'La variación de RSSI permite explorar cambios en el entorno.' };
    text('readingTag', result.tag); text('readingTitle', result.title); text('readingDescription', result.description);
    document.querySelector('.reading-panel').dataset.level = level || '';
    $('readingGlyph').classList.toggle('active', level === 'active' && (playing || state?.status === 'collecting'));
    let detail = `Umbral de varianza: ${number(threshold)} dBm². Análisis de una ventana de 15 s. Es un indicio heurístico, no una detección confirmada de personas.`;
    if (authoritative && finite(authoritative.confidence)) detail += ` Confianza heurística: ${number(authoritative.confidence <= 1 ? authoritative.confidence * 100 : authoritative.confidence, 0)}%.`;
    if (finite(quality?.jitter_cv)) detail += ` Irregularidad del muestreo: ${number(quality.jitter_cv * 100, 1)}%.`;
    if (quality?.reason) detail += ` Calidad: ${quality.reason}.`;
    const band = quality?.motion_band;
    if (band && finite(band.bins)) detail += ` Banda de movimiento: ${band.bins} intervalos espectrales; mínimo ${band.minimum_bins || 2}. Cobertura ${band.coverage === 'full' ? 'completa' : band.coverage === 'partial' ? 'parcial' : 'no disponible'}.`;
    text('classificationDetails', data.length ? detail : 'Se requiere una captura antes de interpretar la señal.');
    $('qualityAction').textContent = comparison?.sessions?.length ? 'Comparar calidad de capturas' : backendAvailable ? 'Preparar otra captura' : 'Medir en mi equipo';
  }

  function renderCharts() {
    const cutoff = samples.length ? samples[0]._time + actualDuration(samples) * position : 0;
    const visible = position >= .999 ? samples : samples.filter((sample) => sample._time <= cutoff);
    const features = stats(visible);
    const last = visible[visible.length - 1];
    text('metricRssi', last ? number(last.rssi_dbm, Number.isInteger(last.rssi_dbm) ? 0 : 1) : '—');
    text('metricVariance', number(features.variance));
    text('metricSamples', fmt.format(visible.length));
    text('metricDuration', durationText(actualDuration(visible)));
    text('sampleRate', features.sample_rate_hz > 0 ? `${number(features.sample_rate_hz, 2)} muestras / s` : 'Sin lectura');
    text('replayTime', durationText(actualDuration(samples) * position));
    text('replayEnd', durationText(actualDuration(samples)));
    $('replaySlider').value = Math.round(position * 1000);
    $('replaySlider').setAttribute('aria-valuetext', `${number(actualDuration(samples) * position, 1)} de ${number(actualDuration(samples), 1)} segundos`);
    $('replaySlider').style.setProperty('--progress', `${position * 100}%`);
    $('playButton').disabled = samples.length < 2;
    $('replaySlider').disabled = samples.length < 2 || state?.status === 'collecting';
    drawSignal(visible); drawVariance(visible); drawSpectrum(visible); renderClassification(visible, features);
  }

  const stagesDefault = [
    { id: 'capture', title: 'Captura de RSSI', summary: 'Lecturas reales con marcas de tiempo.' },
    { id: 'processing', title: 'Procesamiento', summary: 'Limpieza y transformación de la señal.' },
    { id: 'features', title: 'Características', summary: 'Varianza, rango y espectro de potencia.' },
    { id: 'motion', title: 'Movimiento', summary: 'Comparación de condiciones controladas.' },
    { id: 'validation', title: 'Validación', summary: 'Contraste con observación independiente.' },
    { id: 'delivery', title: 'Reproducibilidad', summary: 'Código, datos y ejecución documentada.' }
  ];

  function safeLink(value) {
    if (typeof value !== 'string' || !value) return null;
    try { const url = new URL(value, location.href); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch { return null; }
  }

  function renderEvidence() {
    const evidence = state?.evidence || {};
    const stageData = Array.isArray(evidence.stages) && evidence.stages.length ? evidence.stages : stagesDefault;
    const successful = (status) => ['complete', 'completed', 'verified', 'passed', 'done'].includes(status);
    const complete = stageData.filter((stage) => successful(stage.status)).length;
    text('evidenceProgress', `${complete} / ${stageData.length}`);
    text('evidenceSummary', evidence.summary || (complete ? 'Cada etapa muestra su estado y la evidencia disponible.' : 'Las etapas pendientes requieren evidencia antes de considerarse verificadas.'));
    $('evidenceStages').replaceChildren();
    stageData.forEach((stage, index) => {
      const card = document.createElement('article'); card.className = 'evidence-card';
      const top = document.createElement('div'); top.className = 'evidence-top';
      const numeral = document.createElement('span'); numeral.className = 'stage-number'; numeral.textContent = String(index + 1).padStart(2, '0');
      const badge = document.createElement('span'); badge.className = `stage-status${successful(stage.status) ? ' complete' : ['failed', 'error'].includes(stage.status) ? ' failed' : ''}`; badge.textContent = successful(stage.status) ? 'VERIFICADA' : ['failed', 'error'].includes(stage.status) ? 'POR CORREGIR' : ['partial', 'partially_complete', 'in_progress'].includes(stage.status) ? 'PARCIAL' : 'PENDIENTE';
      top.append(numeral, badge);
      const title = document.createElement('h3'); title.textContent = stage.title || stage.name || `Etapa ${index + 1}`;
      const summary = document.createElement('p'); summary.textContent = stage.summary || stage.description || stage.detail || 'Sin evidencia adjunta.';
      card.append(top, title, summary);
      const links = Array.isArray(stage.artifact_links) && stage.artifact_links.length ? stage.artifact_links : [{ url: stage.artifact_url || stage.url, label: 'Ver evidencia' }];
      const linkGroup = document.createElement('div'); linkGroup.className = 'evidence-links';
      links.forEach((artifact, linkIndex) => {
        const url = safeLink(artifact.url || artifact.href || artifact.path);
        if (!url) return;
        const imageAsset = /\.(png|jpe?g|webp)(?:$|[?#])/i.test(url);
        const link = document.createElement('a'); link.href = url; link.className = 'text-link';
        const label = artifact.label || artifact.title || (imageAsset ? 'Ver captura' : 'Ver evidencia');
        link.textContent = `${label} ↗`; link.setAttribute('aria-label', `${label}: etapa ${index + 1}, ${title.textContent}`); link.target = '_blank'; link.rel = 'noopener';
        if (imageAsset && linkIndex === 0) {
          const previewLink = document.createElement('a'); previewLink.href = url; previewLink.target = '_blank'; previewLink.rel = 'noopener'; previewLink.className = 'evidence-preview'; previewLink.setAttribute('aria-label', `Ampliar captura real de la etapa ${index + 1}`);
          const preview = document.createElement('img'); preview.src = url; preview.alt = `Captura real: ${title.textContent}`; preview.loading = 'lazy'; previewLink.append(preview); card.append(previewLink);
        }
        linkGroup.append(link);
      });
      card.append(linkGroup);
      $('evidenceStages').append(card);
    });
    const condition = { unconfirmed: 'Sin etiqueta', still: 'Quietud', walking: 'Caminando' };
    const started = state?.session?.started_at;
    const startDate = started ? new Date(typeof started === 'number' ? stamp(started) * 1000 : started) : null;
    const pairs = [ ['Sesión', state?.session?.label || 'Sin sesión'], ['Identificador', state?.session?.id || '—'], ['Origen', backendAvailable && state?.mode === 'live' ? 'Adaptador Wi-Fi local' : 'Captura grabada'], ['Inicio', startDate && !Number.isNaN(startDate.getTime()) ? startDate.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'medium' }) : '—'], ['Muestras válidas', fmt.format(samples.length)], ['Duración real', `${number(actualDuration(samples), 1)} s`], ['Condición declarada', condition[state?.session?.ground_truth] || 'Sin etiqueta'], ['Frecuencia de muestreo', stats(samples).sample_rate_hz ? `${number(stats(samples).sample_rate_hz)} Hz` : '—'] ];
    $('metadataGrid').replaceChildren();
    pairs.forEach(([label, value]) => { const item = document.createElement('div'); const term = document.createElement('dt'); term.textContent = label; const definition = document.createElement('dd'); definition.textContent = value; item.append(term, definition); $('metadataGrid').append(item); });
    text('evidenceMode', backendAvailable && state?.mode === 'live' ? 'Datos locales' : 'Captura grabada');
    $('sampleTable').replaceChildren();
    samples.slice(-12).forEach((sample) => { const row = document.createElement('tr'); const date = new Date(sample._time * 1000); [date.toLocaleTimeString('es-MX', { hour12: false }), number(sample.rssi_dbm, 1), sample.quality == null ? '—' : String(sample.quality), sample.phase || '—'].forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }); $('sampleTable').append(row); });
    if (!samples.length) { const row = document.createElement('tr'); const cell = document.createElement('td'); cell.colSpan = 4; cell.textContent = 'Todavía no hay muestras.'; row.append(cell); $('sampleTable').append(row); }
  }

  function setupExport() {
    if (csvObjectUrl) URL.revokeObjectURL(csvObjectUrl);
    const id = state?.session?.id;
    if (backendAvailable && id) { $('exportButton').href = `/api/export.csv?id=${encodeURIComponent(id)}`; $('exportButton').removeAttribute('download'); }
    else if (samples.length) {
      const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
      const csv = ['timestamp,rssi_dbm,quality,phase', ...samples.map((sample) => [sample.timestamp, sample.rssi_dbm, sample.quality, sample.phase].map(quote).join(','))].join('\r\n');
      csvObjectUrl = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
      $('exportButton').href = csvObjectUrl; $('exportButton').download = `swarm-signal-${id || 'captura'}.csv`;
    }
    setHidden('exportButton', !samples.length);
  }

  function updateSessions(list) {
    if (!Array.isArray(list)) return;
    sessions = list;
    const previous = $('sessionPicker').value;
    $('sessionPicker').replaceChildren();
    const current = document.createElement('option'); current.value = 'current'; current.textContent = backendAvailable ? 'Sesión actual' : state?.session?.label || 'Captura grabada'; $('sessionPicker').append(current);
    sessions.forEach((session) => {
      if (!session.id || (!backendAvailable && session.id === state?.session?.id)) return;
      const option = document.createElement('option'); option.value = session.id; option.textContent = session.label || session.id; $('sessionPicker').append(option);
    });
    $('sessionPicker').value = [...$('sessionPicker').options].some((option) => option.value === previous) ? previous : 'current';
    $('sessionPicker').disabled = !backendAvailable || state?.status === 'collecting';
  }

  function renderComparison() {
    const entries = Array.isArray(comparison?.sessions) ? comparison.sessions : [];
    text('comparisonSummary', entries.length ? `${entries.length} registros reales` : 'Sin registros disponibles');
    text('comparisonPhysical', comparison?.physical?.comparison_ready ? comparison.physical.reason || 'Revisa las condiciones declaradas en las fuentes.' : 'Condiciones humanas sin confirmar. Compara calidad de datos, no detección de personas.');
    text('comparisonWindow', `Ventanas disjuntas / ${comparison?.window_seconds || 15} s`);
    const colors = ['#b9f45b', '#6ce0e9', '#b99bff'];
    const legend = $('comparisonLegend'); legend.replaceChildren();
    const rows = $('comparisonRows'); rows.replaceChildren();
    const sources = $('comparisonSources'); sources.replaceChildren();
    entries.forEach((session, index) => {
      const item = document.createElement('span'); const dot = document.createElement('i'); dot.style.backgroundColor = colors[index % colors.length]; item.append(dot, document.createTextNode(session.label || session.id)); legend.append(item);
      const row = document.createElement('tr');
      const label = document.createElement('th'); label.scope = 'row'; label.textContent = session.label || session.id; row.append(label);
      const eligible = finite(session.windows_eligible) ? session.windows_eligible : 0;
      const labels = ['Muestras', 'Hz efectivos', 'Jitter', 'Ventanas válidas'];
      [finite(session.count) ? String(session.count) : '—', number(session.effective_rate_hz), finite(session.jitter_cv) ? `${number(session.jitter_cv * 100, 1)}%` : '—', eligible ? `${session.windows_valid} / ${eligible}` : 'Sin elegibles'].forEach((value, cellIndex) => { const cell = document.createElement('td'); cell.textContent = value; cell.dataset.label = labels[cellIndex]; row.append(cell); });
      rows.append(row);
      const source = document.createElement('div'); source.className = 'comparison-source';
      const title = document.createElement('strong'); title.textContent = session.label || session.id; source.append(title);
      const reason = document.createElement('p'); const reasons = Object.entries(session.reasons || {}).map(([why, count]) => `${why}: ${count}`).join(' · '); reason.textContent = reasons || 'Consulta los resultados de cada ventana en la fuente.'; source.append(reason);
      const url = safeLink(session.source);
      if (url) { const link = document.createElement('a'); link.href = url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Datos originales ↗'; link.setAttribute('aria-label', `Datos originales: ${session.label || session.id}`); source.append(link); }
      if (session.source_sha256) { const hash = document.createElement('code'); hash.textContent = `SHA-256 ${session.source_sha256}`; source.append(hash); }
      sources.append(source);
    });
    drawComparison();
  }

  function drawComparison() {
    const entries = Array.isArray(comparison?.sessions) ? comparison.sessions : [];
    const series = entries.map(session => (session.windows || []).filter(window => finite(window.variance) && finite(window.end_seconds)).map(window => ({ x: window.end_seconds, y: window.variance, index: window.index })));
    const all = series.flat();
    const width = Math.max(200, Math.round($('comparisonChart').getBoundingClientRect().width) || 1000);
    const dim = { width, height: 210, left: 48, right: 12, top: 14, bottom: 33 };
    $('comparisonChart').setAttribute('viewBox', `0 0 ${width} 210`);
    const maximum = all.length ? Math.max(...all.map(point => point.y)) : 1;
    const maxTime = all.length ? Math.max(...all.map(point => point.x)) : 120;
    const bounds = { min: 0, max: Math.max(.1, maximum * 1.13) };
    grid('comparisonGrid', 'comparisonTicks', dim, bounds, maxTime);
    const group = document.createDocumentFragment();
    const colors = ['#b9f45b', '#6ce0e9', '#b99bff'];
    series.forEach((values, index) => {
      const mapped = points(values, dim, bounds, maxTime);
      let d = '';
      mapped.forEach(([x, y], pointIndex) => { d += `${pointIndex === 0 || values[pointIndex].index !== values[pointIndex - 1].index + 1 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)} `; });
      group.append(createSvg('path', { d, stroke: colors[index % colors.length], fill: 'none', 'stroke-width': 2, 'stroke-dasharray': index === 1 ? '6 4' : index === 2 ? '2 4' : '', 'vector-effect': 'non-scaling-stroke' }));
      mapped.forEach(([x, y]) => group.append(createSvg('circle', { cx: x, cy: y, r: 3.5, fill: colors[index % colors.length] })));
    });
    $('comparisonSeries').replaceChildren(group);
    $('comparisonChart').setAttribute('aria-label', `Varianza observada en ventanas disjuntas de ${comparison?.window_seconds || 15} segundos, ${entries.length} capturas. No es una medida de exactitud; los datos están en la tabla siguiente.`);
  }

  async function loadComparison() {
    try { comparison = await fetchJson(backendAvailable ? '/api/comparison' : './data/comparison.json'); }
    catch { comparison = null; }
    renderComparison();
    if (state) renderCharts();
  }

  function openLocalHelp() { $('localHelpDialog').showModal(); $('localHelpDialog').querySelector('.local-steps a').focus(); }

  async function openCapture() {
    if (!backendAvailable || fetchFailures >= 2) { openLocalHelp(); return; }
    if (state?.pending_save) { toast('Guarda primero la captura pendiente.'); return; }
    setHidden('captureError', true);
    $('captureGroundTruth').value = 'unconfirmed';
    document.querySelector('.dialog-note').textContent = 'Mantén el receptor fijo durante la captura.';
    {
      try {
        const result = await fetchJson('/api/interfaces');
        const entries = Array.isArray(result.interfaces) ? result.interfaces : [];
        const select = $('captureInterface'); select.replaceChildren();
        const auto = document.createElement('option'); auto.value = ''; auto.textContent = result.selection_required ? 'Selecciona un adaptador' : 'Automático'; select.append(auto);
        entries.forEach(item => { const option = document.createElement('option'); option.value = typeof item === 'string' ? item : item.name; option.textContent = option.value; select.append(option); });
        select.required = Boolean(result.selection_required);
        setHidden('interfaceField', entries.length < 2 && !result.selection_required);
      } catch { setHidden('interfaceField', true); }
    }
    $('captureDialog').showModal(); $('captureLabel').focus();
  }

  function applyState(next, reset = false) {
    state = next || {};
    samples = cleanSamples(state.samples);
    const collecting = backendAvailable && state.status === 'collecting';
    const pendingSave = Boolean(state.pending_save);
    const isReplay = !backendAvailable || state.mode === 'replay' || selectedSession !== 'current';
    if (collecting || reset) { pause(); position = 1; }
    $('connectionStatus').className = `status-pill ${state.error ? 'error' : collecting ? 'live' : isReplay ? 'replay' : ''}`;
    $('connectionStatus').replaceChildren();
    $('connectionStatus').append(document.createElement('i'), document.createTextNode(pendingSave ? 'Guardado pendiente' : state.error ? 'Captura interrumpida' : collecting ? 'Capturando en vivo' : isReplay ? 'Captura grabada' : 'Receptor listo'));
    setHidden('captureButton', collecting || pendingSave); setHidden('stopButton', !collecting && !pendingSave);
    $('stopButton').textContent = pendingSave ? 'Reintentar guardado' : 'Detener'; $('stopButton').disabled = false;
    $('captureButton').disabled = false;
    $('captureButton').replaceChildren();
    const dot = document.createElement('span'); dot.className = 'capture-dot';
    $('captureButton').append(dot, document.createTextNode(backendAvailable ? 'Iniciar captura' : playing ? 'Pausar reproducción' : 'Reproducir captura'));
    if (!backendAvailable && samples.length < 2) $('captureButton').disabled = true;
    setHidden('replayControls', collecting);
    text('sessionName', state.session?.label || 'Sin sesión');
    text('sessionMeta', collecting ? 'Captura en curso' : isReplay ? 'Datos registrados' : 'Receptor local');
    text('rssiFoot', collecting ? 'Lectura del adaptador' : 'Última lectura visible');
    text('dataProvenance', isReplay ? 'Reproducción de RSSI real. Los cambios pueden tener varias causas.' : 'Lecturas de RSSI. Los cambios pueden tener varias causas.');
    const physicalConditions = { still: 'Condición declarada: quietud', walking: 'Condición declarada: caminando' };
    text('physicalCondition', physicalConditions[state.session?.ground_truth] || 'Movimiento físico sin etiquetar');
    if (state.error) { text('notice', state.error); setHidden('notice', false); }
    else { setHidden('notice', true); }
    if (Array.isArray(state.sessions)) updateSessions(state.sessions); else updateSessions(sessions);
    renderCharts(); renderEvidence(); setupExport();
    if (firstLoad && new URLSearchParams(location.search).get('autoplay') === '1' && samples.length > 1 && !collecting && !reducedMotion) { $('replaySpeed').value = '2'; play(); }
    firstLoad = false;
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(6000), ...options });
    if (!response.ok) {
      let message = `No se pudo completar la solicitud (${response.status}).`;
      try { const body = await response.json(); if (typeof body.error === 'string') message = body.error; } catch { /* HTML responses are not displayed as errors. */ }
      throw new Error(message);
    }
    const result = await response.json();
    if (!result || typeof result !== 'object') throw new Error('Respuesta inválida');
    return result;
  }

  async function initialize() {
    try {
      if (!['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) throw new Error('Public replay');
      const next = await fetchJson('/api/state');
      if (!Array.isArray(next.samples)) throw new Error('No hay API local');
      backendAvailable = true; applyState(next, true); lastSignature = JSON.stringify(next);
    } catch {
      backendAvailable = false;
      try { const next = await fetchJson('./data/session.json'); applyState({ ...next, mode: 'replay' }, true); }
      catch { applyState({ mode: 'replay', status: 'idle', samples: [], error: 'No hay una captura disponible en esta página.' }); }
    }
    if (backendAvailable) {
      try { const result = await fetchJson('/api/sessions'); updateSessions(Array.isArray(result) ? result : result.sessions); } catch { /* The current capture remains available. */ }
      window.setInterval(poll, 1000);
    }
    loadComparison();
  }

  async function poll() {
    if (busy || document.hidden || selectedSession !== 'current') return;
    busy = true;
    try {
      const next = await fetchJson('/api/state');
      const recoveringConnection = fetchFailures >= 2;
      fetchFailures = 0;
      const signature = JSON.stringify(next);
      if (signature !== lastSignature || recoveringConnection) { const previousId = state?.session?.id; lastSignature = signature; applyState(next, previousId !== next.session?.id); }
    } catch {
      fetchFailures++;
      if (fetchFailures >= 2) { text('notice', 'Se perdió la conexión con el receptor. Se conserva la última lectura.'); setHidden('notice', false); $('connectionStatus').className = 'status-pill error'; $('connectionStatus').replaceChildren(document.createTextNode('Receptor sin conexión')); $('readingGlyph').classList.remove('active'); text('readingTag', 'LECTURA RETENIDA'); text('readingTitle', 'Receptor sin conexión.'); text('readingDescription', 'Se muestra el último dato recibido. Restablece la conexión para continuar.'); $('captureButton').disabled = true; $('stopButton').disabled = true; }
    } finally { busy = false; }
  }

  function pause() {
    playing = false; cancelAnimationFrame(animationFrame);
    $('playButton').setAttribute('aria-label', 'Reproducir captura');
    $('playButton').innerHTML = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7 4 9 6-9 6z"/></svg>';
    $('readingGlyph').classList.remove('active');
    if (!backendAvailable) { text('captureButton', 'Reproducir captura'); $('captureButton').setAttribute('aria-pressed', 'false'); }
  }

  function play() {
    if (samples.length < 2 || state?.status === 'collecting') return;
    if (position >= .999) position = 0;
    playing = true; animationTime = performance.now(); lastRender = 0;
    $('playButton').setAttribute('aria-label', 'Pausar reproducción');
    $('playButton').innerHTML = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 4h3v12H5zM12 4h3v12h-3z"/></svg>';
    if (!backendAvailable) { text('captureButton', 'Pausar reproducción'); $('captureButton').setAttribute('aria-pressed', 'true'); }
    cancelAnimationFrame(animationFrame);
    animationFrame = requestAnimationFrame(animateReplay);
  }

  function animateReplay(now) {
    if (!playing) return;
    const elapsed = (now - animationTime) / 1000;
    animationTime = now;
    position = Math.min(1, position + elapsed * Number($('replaySpeed').value) / Math.max(actualDuration(samples), 1));
    if (now - lastRender > (reducedMotion ? 500 : 110) || position >= 1) { renderCharts(); lastRender = now; }
    if (position >= 1) { pause(); renderCharts(); }
    else animationFrame = requestAnimationFrame(animateReplay);
  }

  function toast(message) { text('toast', message); setHidden('toast', false); clearTimeout(toastTimer); toastTimer = setTimeout(() => setHidden('toast', true), 4000); }

  function requestedView() { return new URLSearchParams(location.search).get('view') || location.hash.slice(1) || 'monitor'; }

  function showTab(id, { historyMode = 'push', initial = false } = {}) {
    if (!['monitor', 'evidencia', 'propuesta'].includes(id)) id = 'monitor';
    document.querySelectorAll('.view').forEach((view) => { const active = view.id === id; view.hidden = !active; view.classList.toggle('active', active); });
    document.querySelectorAll('.tab').forEach((tab) => { const active = tab.dataset.tab === id; tab.classList.toggle('active', active); active ? tab.setAttribute('aria-current', 'page') : tab.removeAttribute('aria-current'); });
    const url = new URL(location.href);
    url.hash = '';
    id === 'monitor' ? url.searchParams.delete('view') : url.searchParams.set('view', id);
    if (historyMode !== 'none') history[historyMode === 'replace' ? 'replaceState' : 'pushState']({ view: id }, '', url.pathname + url.search);
    if (!initial && document.querySelector('.intro').getBoundingClientRect().bottom < 0) document.querySelector('.workspace-nav').scrollIntoView({ block: 'start', behavior: reducedMotion ? 'instant' : 'smooth' });
    if (id === 'monitor' && state) renderCharts();
  }

  document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => showTab(button.dataset.tab)));
  document.querySelectorAll('[data-open-view]').forEach(link => link.addEventListener('click', event => { event.preventDefault(); showTab(link.dataset.openView); }));
  document.querySelector('.brand').addEventListener('click', (event) => { event.preventDefault(); showTab('monitor'); window.scrollTo({ top: 0, behavior: reducedMotion ? 'instant' : 'smooth' }); });
  addEventListener('popstate', () => showTab(requestedView(), { historyMode: 'none', initial: true }));
  addEventListener('hashchange', () => { if (['monitor', 'evidencia', 'propuesta'].includes(location.hash.slice(1))) showTab(requestedView(), { historyMode: 'replace', initial: true }); });
  let resizeTimer;
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state) renderCharts(); if ($('comparisonPanel').open) drawComparison(); }, 120); });
  $('playButton').addEventListener('click', () => playing ? pause() : play());
  $('replaySlider').addEventListener('input', () => { pause(); position = Number($('replaySlider').value) / 1000; renderCharts(); });
  $('replaySpeed').addEventListener('change', () => { animationTime = performance.now(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && playing) pause(); });
  $('fullscreenButton').addEventListener('click', async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); } catch { toast('La pantalla completa no está disponible.'); } });
  $('captureButton').addEventListener('click', () => { if (!backendAvailable) { playing ? pause() : play(); } else openCapture(); });
  document.querySelectorAll('.local-help-trigger').forEach(button => button.addEventListener('click', openLocalHelp));
  $('closeLocalHelp').addEventListener('click', () => $('localHelpDialog').close());
  $('localHelpDialog').addEventListener('click', event => { if (event.target !== $('localHelpDialog')) return; const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close(); });
  $('qualityAction').addEventListener('click', () => {
    if (comparison?.sessions?.length) { $('comparisonPanel').open = true; drawComparison(); $('comparisonPanel').scrollIntoView({ block: 'start', behavior: reducedMotion ? 'instant' : 'smooth' }); $('comparisonPanel').querySelector('summary').focus({ preventScroll: true }); }
    else backendAvailable ? openCapture() : openLocalHelp();
  });
  $('comparisonPanel').addEventListener('toggle', () => { if ($('comparisonPanel').open) drawComparison(); });
  $('captureGroundTruth').addEventListener('change', () => { document.querySelector('.dialog-note').textContent = $('captureGroundTruth').value === 'walking' ? 'Laptop fija; cruza entre laptop y router.' : 'Mantén el receptor fijo durante la captura.'; });
  $('closeDialog').addEventListener('click', () => $('captureDialog').close());
  $('captureDialog').addEventListener('click', (event) => { if (event.target === $('captureDialog')) { const rect = $('captureDialog').getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) $('captureDialog').close(); } });
  $('captureForm').addEventListener('submit', async (event) => {
    event.preventDefault(); $('submitCapture').disabled = true; setHidden('captureError', true);
    try {
      const result = await fetchJson('/api/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ label: $('captureLabel').value.trim() || 'Captura Wi-Fi', duration_seconds: Number($('captureDuration').value), ground_truth: $('captureGroundTruth').value, interface: $('captureInterface').value || null }) });
      if (result.error) throw new Error(result.error);
      selectedSession = 'current'; $('sessionPicker').value = 'current'; position = 1; $('captureDialog').close(); toast('Captura iniciada.');
      if (Array.isArray(result.samples)) applyState(result, true); else await poll();
    } catch (error) { text('captureError', error.message === 'Failed to fetch' ? 'No se pudo conectar con el receptor.' : error.message); setHidden('captureError', false); }
    finally { $('submitCapture').disabled = false; }
  });
  $('stopButton').addEventListener('click', async () => { const retry = Boolean(state?.pending_save); $('stopButton').disabled = true; try { const result = await fetchJson('/api/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); if (Array.isArray(result.samples)) applyState(result, true); else await poll(); if (result.error || result.pending_save) throw new Error(result.error || 'El guardado sigue pendiente.'); toast(retry ? 'Captura guardada.' : 'Captura detenida y guardada.'); } catch (error) { toast(error.message || 'No se pudo guardar la captura. Reintenta.'); } finally { $('stopButton').disabled = false; } });
  $('sessionPicker').addEventListener('change', async () => {
    const selected = $('sessionPicker').value; pause();
    try {
      const next = await fetchJson(selected === 'current' ? '/api/state' : `/api/session?id=${encodeURIComponent(selected)}`);
      selectedSession = selected;
      applyState(selected === 'current' ? next : { ...next, mode: 'replay', status: 'ready' }, true);
      $('sessionPicker').value = selected;
    } catch { $('sessionPicker').value = selectedSession; toast('No se pudo abrir esta captura.'); }
  });
  const initialView = requestedView();
  showTab(initialView, { historyMode: 'replace', initial: true });
  // A named section hash can otherwise scroll the page after this deferred script.
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  window.scrollTo(0, 0);
  window.addEventListener('load', () => window.scrollTo(0, 0), { once: true });
  initialize();
})();

