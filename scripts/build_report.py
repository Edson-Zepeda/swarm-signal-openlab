"""Build evidence-backed PDFs. All plotted numbers come from captured JSON.

Run with a Python environment containing reportlab and pymupdf.
No WiFi capture, network requests or evidence mutation occurs here.
"""
from __future__ import annotations
import cmath
import json
import math
from pathlib import Path
import statistics
import hashlib
import shutil
import xml.etree.ElementTree as ET
from html import escape

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
REVIEW = ROOT / 'tmp' / 'pdf-review'
DOCS.mkdir(exist_ok=True)
REVIEW.mkdir(parents=True, exist_ok=True)
W, H = 595.276, 841.89
M, CW = 42, W - 84
NAVY, PANEL = '#080d13', '#10171f'
LIME, CYAN = '#b9f45b', '#6ce0e9'
INK, MUTED, WHITE = '#102531', '#506474', '#f4f7f8'
RED, AMBER = '#a53832', '#986000'
for name, filename in [('Segoe', 'segoeui.ttf'), ('SegoeB', 'segoeuib.ttf'), ('Mono', 'consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
pdfmetrics.registerFontFamily('Segoe', normal='Segoe', bold='SegoeB', italic='Segoe', boldItalic='SegoeB')

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

verification = read('evidence/upstream/verification_summary.json')
env = read('evidence/tutorial/01_environment.json')
single = read('evidence/tutorial/03_single_reading.json')
pipeline = read('evidence/tutorial/04_pipeline_15s.json')
commodity = read('evidence/tutorial/06_commodity_backend.json')
# This report interprets a specific experiment, not whichever file is newest.
session_file = ROOT / 'evidence/sessions/20260909T062522_420b46.json'
session = json.loads(session_file.read_text(encoding='utf-8'))
rows, p_rows = session['samples'], pipeline['samples']
pf = pipeline['features']
dt = [b['timestamp'] - a['timestamp'] for a, b in zip(rows, rows[1:])]
duration = rows[-1]['timestamp'] - rows[0]['timestamp']
observed_rate = (len(rows) - 1) / duration
source_commit = verification['upstream']['commit']
comparison = read('web/data/comparison.json')
identified_verify = read('evidence/revision/verify_identified.json')
for recording in comparison['sessions']:
    captured=(ROOT/recording['source']).read_bytes()
    assert hashlib.sha256(captured).hexdigest()==recording['source_sha256'], 'Comparación desactualizada.'
    assert len(json.loads(captured)['samples'])==recording['count'], 'Conteo de comparación incoherente.'
assert len(comparison['sessions'])==3, 'El informe evalúa tres sesiones de referencia.'
assert comparison['physical']['confirmed_sessions']==0, 'Revisar las conclusiones al incorporar evidencia física.'
original_verify_hash=next(x['sha256_worktree_bytes'] for x in verification['upstream']['source_files_sha256'] if x['path']=='verify')
assert identified_verify['verify_sha256']==original_verify_hash, 'El verificador cambió desde la ejecución original.'
assert identified_verify['expected_csi_sha256']==verification['csi_proof']['expected_sha256'], 'Cambió la expectativa CSI.'

def own_count():
    for path in [ROOT / 'evidence/revision/own_tests.xml']:
        if path.exists():
            node = ET.parse(path).getroot()
            cases = list(node.iter('testcase'))
            passed = sum(not any(c.tag in {'failure', 'error', 'skipped'} for c in case) for case in cases)
            failed = sum(any(c.tag in {'failure', 'error'} for c in case) for case in cases)
            if failed:
                raise ValueError('La evidencia final contiene fallos; no generar un resumen de aprobación.')
            return passed, path.relative_to(ROOT).as_posix()
    raise FileNotFoundError('Falta evidence/revision/own_tests.xml; conservar las pruebas históricas.')

OWN, OWN_EVIDENCE = own_count()

class Report:
    def __init__(self, path, title):
        self.c = canvas.Canvas(str(path), pagesize=(W, H), pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor('SWARM SIGNAL | Edson Manuel Zepeda Chávez')
        self.page = 0
        self.dark = False

    def new(self, title, eyebrow, dark=False):
        if self.page:
            self.footer()
            self.c.showPage()
        self.page += 1
        self.dark = dark
        self.c.setFillColor(HexColor(NAVY if dark else WHITE))
        self.c.rect(0, 0, W, H, fill=1, stroke=0)
        self.c.setFillColor(HexColor(LIME if dark else INK))
        self.c.rect(M, H - 47, 17, 4, fill=1, stroke=0)
        self.text('SWARM / SIGNAL', M + 27, H - 48, 10, True, WHITE if dark else INK)
        self.text(eyebrow.upper(), M, H - 86, 9.2, True, CYAN if dark else MUTED)
        self.para(title, M, H - 104, CW, 28, True, WHITE if dark else INK, leading=32)
        return H - 159

    def footer(self):
        c = self.c
        c.setStrokeColor(HexColor('#22313c' if self.dark else '#d7e0e5'))
        c.line(M, 39, W - M, 39)
        self.text('OPEN LAB AD2026  /  09 SEP 2026', M, 24, 8, color='#9baebc' if self.dark else MUTED)
        self.text(f'{self.page:02d}', W - M - 14, 24, 8, True, LIME if self.dark else INK)

    def text(self, txt, x, y, size=12, bold=False, color=INK, font=None):
        self.c.setFont(font or ('SegoeB' if bold else 'Segoe'), size)
        self.c.setFillColor(HexColor(color))
        self.c.drawString(x, y, txt)

    def para(self, txt, x, top, width=CW, size=12, bold=False, color=INK, leading=None):
        style = ParagraphStyle('body', fontName='SegoeB' if bold else 'Segoe', fontSize=size,
                               leading=leading or size * 1.42, textColor=HexColor(color),
                               spaceAfter=0, allowWidows=0, allowOrphans=0)
        p = Paragraph(txt, style)
        _, height = p.wrap(width, H)
        if top - height < 48:
            raise ValueError(f'Page {self.page} overflow: {txt[:80]} ends at {top-height:.1f}')
        p.drawOn(self.c, x, top - height)
        return top - height

    def box(self, x, top, width, height, fill='#e9eff2', border=None):
        self.c.setFillColor(HexColor(fill))
        self.c.setStrokeColor(HexColor(border or fill))
        self.c.roundRect(x, top - height, width, height, 10, fill=1, stroke=bool(border))

    def note(self, txt, top, fill='#e8f0e5', color=INK):
        style = ParagraphStyle('n', fontName='Segoe', fontSize=11, leading=15.5, textColor=HexColor(color))
        p = Paragraph(txt, style); _, h = p.wrap(CW - 28, H)
        self.box(M, top, CW, h + 26, fill)
        p.drawOn(self.c, M + 14, top - 13 - h)
        return top - h - 26

    def kpis(self, items, top, dark=False):
        gap = 10; width = (CW - gap * (len(items) - 1)) / len(items)
        for i, (number, label) in enumerate(items):
            x = M + i * (width + gap)
            self.box(x, top, width, 89, PANEL if dark else '#e4ecee')
            self.text(number, x + 13, top - 37, 25, True, LIME if dark else INK)
            self.para(label, x + 13, top - 49, width - 25, 10.3, color='#aabac5' if dark else MUTED, leading=13.5)
        return top - 105

    def table(self, headers, entries, widths, top, font=10.5):
        x = M; self.box(M, top, CW, 29, NAVY)
        for label, width in zip(headers, widths):
            self.text(label, x + 10, top - 19, 10, True, WHITE); x += width
        top -= 29
        for n, row in enumerate(entries):
            ps = []
            for text, width in zip(row, widths):
                st = ParagraphStyle('t', fontName='Segoe', fontSize=font, leading=font*1.3, textColor=HexColor(INK))
                p = Paragraph(str(text), st); _, h = p.wrap(width - 20, H); ps.append((p, h, width))
            rh = max(p[1] for p in ps) + 18
            if top - rh < 51:
                raise ValueError(f'Table overflow page {self.page}: {row}')
            self.c.setFillColor(HexColor('#e8eff1' if n % 2 == 0 else '#f4f7f8'))
            self.c.rect(M, top-rh, CW, rh, fill=1, stroke=0)
            x = M
            for p,h,width in ps:
                p.drawOn(self.c, x+10, top-9-h); x += width
            top -= rh
        return top

    def chart(self, xs, ys, top, height, title, ylabel, color='#237c87', points=False, ymax=None, ymin=None, shade=None):
        self.text(title, M, top, 12, True)
        left, right, bottom, plot_top = M+43, W-M-10, top-height+31, top-24
        low = math.floor(min(ys)) if ymin is None else ymin
        high = math.ceil(max(ys)) if ymax is None else ymax
        if high == low: high += 1
        xmin,xmax = min(xs),max(xs)
        if xmax == xmin: xmax += 1
        if shade:
            lo, hi = max(xmin, shade[0]), min(xmax, shade[1])
            if hi > lo:
                self.c.setFillColor(HexColor('#e0ebd4'))
                self.c.rect(left+(lo-xmin)/(xmax-xmin)*(right-left), bottom,
                            (hi-lo)/(xmax-xmin)*(right-left), plot_top-bottom, fill=1, stroke=0)
        ticks=int(high-low)+1 if ylabel=='dBm' and high-low<=8 else 5
        for i in range(ticks):
            y = bottom+(plot_top-bottom)*i/(ticks-1)
            val = low+(high-low)*i/(ticks-1)
            self.c.setStrokeColor(HexColor('#d8e2e7')); self.c.setLineWidth(.55)
            self.c.line(left,y,right,y)
            self.text(f'{val:.0f}' if ylabel=='dBm' else f'{val:.1f}', M+2,y-3,8.5,color=MUTED)
        for i in range(5):
            val=xmin+(xmax-xmin)*i/4
            self.text(f'{val:.1f}', left+(right-left)*i/4-7,bottom-16,8.5,color=MUTED)
        self.text(ylabel, M, plot_top+9,8.2,color=MUTED)
        self.text('Tiempo desde primera muestra (s)' if xmax>1.2 else 'Frecuencia (Hz)', left,bottom-30,8.5,color=MUTED)
        p=self.c.beginPath()
        for i,(x,y) in enumerate(zip(xs,ys)):
            xx=left+(x-xmin)/(xmax-xmin)*(right-left); yy=bottom+(y-low)/(high-low)*(plot_top-bottom)
            if i==0: p.moveTo(xx,yy)
            else:p.lineTo(xx,yy)
            if points:
                self.c.setFillColor(HexColor(color));self.c.circle(xx,yy,1.9,fill=1,stroke=0)
        self.c.setStrokeColor(HexColor(color));self.c.setLineWidth(1.5);self.c.drawPath(p)
        return top-height-14

    def image(self, path, top, maxheight=190):
        if not path.exists(): return top
        image = ImageReader(str(path));iw,ih=image.getSize();height=min(maxheight,CW*ih/iw);width=height*iw/ih
        self.c.drawImage(image,M+(CW-width)/2,top-height,width,height,mask='auto')
        return top-height-10

    def finish(self):
        self.footer();self.c.save()


def math_note(r, y):
    return r.para('<b>Definiciones.</b> Tasa = (n − 1) / cobertura. Varianza muestral = suma de desviaciones al cuadrado / (n − 1). Jitter = desviación estándar poblacional de los intervalos / intervalo medio. La tasa global no describe cada ventana.', M, y, size=10.5, color=MUTED)


def comparison_table(r, y):
    entries=[]
    for i,s in enumerate(comparison['sessions'], 1):
        entries.append((f'S{i}', str(s['count']), f"{s['coverage_seconds']:.2f}",
                        f"{s['effective_rate_hz']:.3f}", f"{s['sample_variance']:.3f}",
                        f"{s['windows_valid']}/{s['windows_eligible']}"))
    return r.table(['Sesión','n','Segundos','Hz','Var. dBm²','Aptas / elegibles'],entries,[53,44,86,77,94,CW-354],y,font=10.5)


def window_map(r, y):
    r.text('Ventanas de 15 s, sin solapamiento',M,y,12,True)
    y-=25
    max_windows=max(len(s['windows']) for s in comparison['sessions'])
    bw=min(42,(CW-70)/max_windows)
    for i,s in enumerate(comparison['sessions'],1):
        r.text(f'S{i}',M,y-17,11,True)
        for j,window in enumerate(s['windows']):
            fill=LIME if window['ready'] else ('#e8c99c' if window['eligible'] else '#dde5e9')
            r.box(M+43+j*bw,y,bw-5,29,fill)
            r.text(str(j+1),M+52+j*bw,y-19,9,True)
        y-=41
    return r.para('Verde: apta. Arena: abstención. Gris: tramo final corto. Elegibilidad por horizonte nominal ≥14 s; las pérdidas interiores no se eliminan del denominador. Apta no significa presencia confirmada.',M,y,size=10.2,color=MUTED)-17


def add_comparison_page(r):
    y=r.new('Tres capturas, una regla','Comparación · Calidad y variabilidad')
    y=r.para('La revisión vuelve a analizar las mismas muestras con reglas explícitas. No son capturas nuevas ni una comparación de exactitud humana.',M,y,size=12)-19
    y=comparison_table(r,y)-22
    y=window_map(r,y)
    y=math_note(r,y)-18
    y=r.note('<b>Política revisada.</b> Sin remuestrear: cobertura ≥14 s, hueco ≤2 s, CV de intervalos ≤5% y desviación máxima del intervalo ≤15%. La banda de movimiento requiere al menos dos bins observados. Son guardas iniciales de ingeniería, no umbrales de precisión calibrados.',y)-18
    for i,s in enumerate(comparison['sessions'],1):
        y=r.para(f"S{i}: {escape(s['source'])}",M,y,size=8.9,color=MUTED)-4
    r.para('Fuente derivada: web/data/comparison.json. Criterio idéntico para todas las sesiones. Todas las condiciones humanas permanecen sin confirmar.',M,y-6,size=9.3,color=MUTED)


def build_report():
    r=Report(DOCS/'SwarmSignal_Informe.pdf','SWARM SIGNAL | Informe de evidencia')
    y=r.new('WiFi medido.\nEvidencia verificable.'.replace('\n','<br/>'),'Informe técnico · Reto de Software',True)
    y=H-204
    y=r.para('Sensado RSSI en Windows y propuesta de integración a SWARM.',M,y,CW,14,color='#aabac5')-24
    y=r.kpis([(str(len(p_rows)),'muestras en el tutorial'),(str(len(rows)),'muestras en sesión extendida'),(f"{verification['unit']['passed']} + {verification['live_adapted']['passed']}",'unitarias + live adaptadas')],y,True)
    y=r.para('El pipeline ejecutó la clasificación <b>ACTIVE</b> en la ventana del tutorial. El movimiento físico y la presencia humana no fueron confirmados.',M,y,CW,13,color=WHITE)-22
    vc=identified_verify['counts']
    stage=[('01-02','Entorno y WiFi','Windows 11 conectado. Output real incluido.'),('03-04','Lectura y pipeline','RSSI directo; 15 s solicitados.'),('05','Monitor','Captura real; falta ensayo humano confirmado.'),('06-07','Integración y pruebas',f'CommodityBackend; {OWN} pruebas propias.'),('08','Verificación',f"Original: FAIL. Revisión: {vc['pass']} PASS, {vc['skip']} SKIP.")]
    for num,title,desc in stage:
        r.text(num,M,y-10,10,True,CYAN);r.text(title,M+55,y-10,12,True,WHITE)
        y=r.para(desc,M+55,y-17,CW-55,10.5,color='#aabac5')-18
    r.box(M,118,CW,55,PANEL)
    r.para('Pendiente: ensayo humano etiquetado. Avanzado Skybrush: falta la copia asignada de VantTec y su tutorial.',M+13,107,CW-26,10.6,color='#d4e0e7',leading=14)

    y=r.new('Entorno y lectura directa','Etapas 01 · 02 · 03')
    y=r.para('RuView usa el adaptador WiFi de la laptop mediante netsh. No se añadió hardware de sensado.',M,y,size=11.5)-15
    y=r.table(['Componente','Evidencia observada'],[
        ('Sistema',env['os']),('Python',env['python'].split(' (')[0]),
        ('Dependencias',f"NumPy {env['packages']['numpy']} · SciPy {env['packages']['scipy']} · pytest {env['packages']['pytest']}"),
        ('Adaptador','Realtek 8822CE · Wi-Fi · 5 GHz · canal 161')],[131,CW-131],y,font=10.5)-17
    r.text('Commit de origen',M,y,10,True);y-=16
    r.text(source_commit,M,y,9.2,font='Mono');y-=27
    r.text('Output real · netsh wlan show interfaces',M,y,11.5,True);y-=15
    raw=(ROOT/'evidence/tutorial/02_netsh.txt').read_text(encoding='utf-8').splitlines()
    keys=('Nombre','Estado','Banda','Canal','Señal','Rssi')
    excerpt=[line for line in raw if any(line.lstrip().startswith(k) for k in keys)]
    assert len(excerpt)==6, 'Revisar extracto netsh; no sustituir por valores recreados.'
    r.box(M,y,CW,105,NAVY)
    for j,line in enumerate(excerpt):
        r.text(line,M+7,y-18-j*14,9,font='Mono',color=WHITE)
    y-=119
    y=r.note(f"<b>Lectura individual original: {single['sample']['rssi_dbm']:.0f} dBm.</b> El output de arriba registra otra lectura, {env['strict_netsh_reading']['rssi_dbm']:.0f} dBm; no son simultáneas. La calidad 0 del colector original es un error de idioma: ignora ‘Señal’. El SO reportó 100%.",y)-15
    y=r.para('<b>Adaptación local.</b> UTF-8 con alternativa OEM; selección de interfaz conectada y RSSI directo obligatorio. Una lectura ausente produce un error, nunca −80 dBm de relleno. Ruido y contadores no medidos quedan excluidos.',M,y,size=11)-13
    r.para('Extracto literal de 02_netsh.txt; se conservó el archivo completo sanitizado. Entorno y lectura: evidence/tutorial/01_environment.json y 03_single_reading.json.',M,y,size=9.4,color=MUTED)

    y=r.new('La ventana de 15 segundos','Etapa 04 · Datos del pipeline original')
    y=r.kpis([(f"{pf['mean']:.2f}",'RSSI medio (dBm)'),(f"{pf['variance']:.3f}",'varianza (dBm²)'),(f"{pf['sample_rate_hz']:.3f}",'tasa efectiva (Hz)')],y)
    px=[v['timestamp']-p_rows[0]['timestamp'] for v in p_rows];py=[v['rssi_dbm'] for v in p_rows]
    y=r.chart(px,py,y,197,'Figura 1. RSSI original, 30 muestras','dBm',points=True)-5
    n=len(py);signal=[(v-statistics.mean(py))*.5*(1-math.cos(2*math.pi*i/(n-1))) for i,v in enumerate(py)]
    frequencies=[k*pf['sample_rate_hz']/n for k in range(1,n//2+1)]
    powers=[abs(sum(v*cmath.exp(-2j*math.pi*k*t/n) for t,v in enumerate(signal)))**2/n for k in range(1,n//2+1)]
    y=r.chart(frequencies,powers,y,157,'Figura 2. Espectro Hann de la misma ventana','Energía relativa',color='#5365a1',ymin=0,shade=(.5,3)) - 2
    y=r.note(f"<b>Salida algorítmica: {pipeline['classification']['motion_level'].upper()}.</b> Varianza {pf['variance']:.3f} ≥ 0.3; energía de movimiento {pf['motion_band_power']:.3f} ≥ 0.1. El score 100% es heurístico, no exactitud medida.",y)-14
    r.para(f"15 s solicitados; {pf['duration_seconds']:.2f} s de cobertura. Nyquist: {pf['sample_rate_hz']/2:.3f} Hz. Verde: parte observable de la banda nominal 0.5-3 Hz. No se infieren signos vitales ni causas. Datos: evidence/tutorial/04_pipeline_15s.json.",M,y,size=10.1,color=MUTED)

    y=r.new('El muestreo también importa','Etapa 05 · Monitor y sesión extendida')
    y=r.kpis([(str(len(rows)),'muestras reales'),(f'{duration:.2f} s','cobertura temporal'),(f'{observed_rate:.3f} Hz','tasa de toda la sesión')],y)
    sx=[v['timestamp']-rows[0]['timestamp'] for v in rows];sy=[v['rssi_dbm'] for v in rows]
    y=r.chart(sx,sy,y,172,'Figura 3. Sesión solicitada de 120 s','dBm',shade=(duration-15,duration))
    y=r.note(f"<b>Resultado histórico: sin veredicto.</b> En los últimos 15 s, resaltados, el jitter fue {session['quality'].get('jitter_cv',0):.3f}; excedió el límite 0.25 de aquella versión. netsh registró {session['capture_diagnostics']['netsh_error_count']} errores. La revisión posterior usa guardas más estrictas.",y)-15
    y=r.chart(sx[1:],dt,y,174,'Figura 4. Intervalos entre muestras consecutivas','Segundos',color='#5365a1',ymin=0,shade=(duration-15,duration))
    r.para(f"Condición: no confirmada. Latencia media de netsh: {session['capture_diagnostics']['mean_netsh_latency_seconds']:.3f} s. Datos: evidence/sessions/{session_file.name}. Las figuras son reconstrucciones de mediciones guardadas, no señales sintéticas.",M,y,size=9.8,color=MUTED)

    add_comparison_page(r)

    y=r.new('El monitor en funcionamiento','Etapa 05 · Evidencia visual histórica')
    live_candidates=[ROOT/'evidence/ui/monitor-live.png',ROOT/'evidence/ui/live.png']
    live_image=next((p for p in live_candidates if p.exists()),None)
    image=live_image or ROOT/'evidence/ui/replay.png'
    y=r.para('La interfaz distingue captura en vivo, reproducción y calidad insuficiente. Los valores proceden del adaptador del equipo; las animaciones no generan mediciones.',M,y,size=12)-22
    y=r.image(image,y,365)
    caption=('Figura 5. Otra sesión en vivo: 95 muestras a los 47 s visibles. Es distinta del registro de 233 muestras (figura 3); no confirma actividad humana.' if live_image else
             'Figura 5. Captura auténtica de la reproducción local de datos guardados. Este estado no debe confundirse con captura en vivo.')
    y=r.para(caption,M,y,size=10.3,color=MUTED)-22
    y=r.note('<b>Condición física sin confirmar.</b> El usuario no etiquetó un ensayo de quietud y cruce. El requisito de demostrar movimiento humano frente al equipo sigue pendiente, aunque el monitor y la lectura real funcionan.',y)-17
    r.para('Cada sesión conserva sus timestamps, RSSI, calidad y etiqueta declarada. El CSV permite revisar las muestras; el JSON añade parámetros, diagnóstico y resultado del análisis. Archivo visual: '+image.relative_to(ROOT).as_posix()+'.',M,y,size=10.8,color=MUTED)

    y=r.new('Integración sometida a pruebas','Etapas 06 · 07 · Resultados separados')
    y=r.para('<b>Prueba propia con CommodityBackend.</b> El monitor conecta el colector estricto, RssiFeatureExtractor y PresenceClassifier. El ciclo start / get_result / stop alimenta sesiones guardadas y reproducción de las mismas muestras. Capacidades declaradas: PRESENCE y MOTION.',M,y,size=11.5)-20
    cf=commodity['application_result']['features']
    y=r.para(f"<b>Ejecución dedicada:</b> {len(commodity['samples'])} muestras reales; {commodity['checks_passed']} comprobaciones aprobadas. Tras detener la captura, el backend y la aplicación analizaron la misma ventana. Resultado: {commodity['application_result']['classification']['motion_level'].upper()}, varianza {cf['variance']:.3f} dBm² y {cf['duration_seconds']:.2f} s. Registro: 06_commodity_backend.json.",M,y,size=10.7)-17
    y=r.table(['Batería','Resultado','Alcance real'],[
        ('Unitarias upstream',f"{verification['unit']['passed']} PASS",'Entradas sintéticas y mocks originales; 9 pruebas más que las 36 históricas.'),
        ('Integración original','5 SKIP','Precheck en inglés no reconoce la conexión en español.'),
        ('Integración localizada','5 PASS','Solo precheck adaptado en una copia. 15 aserciones intactas; WiFi real.'),
        ('Pruebas propias',f'{OWN} PASS','Parser, ventanas, ciclo de sesiones, integridad y origen HTTP. Fixtures sintéticos.')],[125,76,CW-201],y,font=10.2)-20
    y=r.note('Los comandos del tutorial con PYTHONPATH=archive/v1 fallaron por imports v1.src. Se cambió el directorio de importación a archive; las pruebas unitarias originales no se modificaron.',y)-17
    y=r.para('<b>Revisión del software.</b> Se comprueban guardado recuperable, catálogo aislado, filas e interfaz válidas y cobertura espectral. La revisión final añade rangos HTTP para buscar capítulos del video local y límites temporales que evitan recorridos desmedidos del comparador. Detalle: SwarmSignal_Auditoria.pdf.',M,y,size=11.5)-15
    y=r.para('La prueba live de “variación” original imprime valores pero no contiene una aserción. Aprobar la batería demuestra ejecución e invariantes de software; no sensibilidad, especificidad ni validación en personas.',M,y,size=10.5,color=MUTED)-15
    r.para('Trazabilidad: evidence/upstream/verification_summary.json, unit.xml, live_original.xml, live_adapted.xml y live_precheck_locale.patch. Pruebas propias: '+escape(OWN_EVIDENCE)+'.',M,y,size=9.3,color=MUTED)

    y=r.new('El fallo quedó explicado','Etapa 08 · Original y nueva ejecución')
    vc=identified_verify['counts']
    y=r.kpis([(str(vc['pass']),'PASS en revisión'),(str(vc['fail']),'FAIL en revisión'),(str(vc['skip']),'SKIP en revisión')],y)+8
    brief=['Hash del pipeline Python','Revisión de generadores aleatorios','Rust no ejecutado','Binding PyO3 no ejecutado','Invariante de identidad','Registro crates: cliente identificado','Paquete npm publicado','Manifiesto Docker multiarch','Contenedor no ejecutado']
    revised={int(p['phase']):p for p in identified_verify['phases']}
    descriptions=[(str(p['phase']),p['status'],revised[p['phase']]['status'],brief[p['phase']-1]) for p in verification['full_verify']['phases']]
    y=r.table(['Fase','Antes','Revisión','Alcance'],descriptions,[42,64,69,CW-175],y,font=10.1)-16
    y=r.para(f"<b>Original: FAIL, salida 1.</b> El primer endpoint devolvió HTTP 403. <b>Nueva ejecución: salida {identified_verify['exit_code']}.</b> Se identificó el cliente mediante User-Agent y configuración curl documentada; no se modificó ./verify. Las fases omitidas siguen sin ejecución.",M,y,size=10.8)-15
    y=r.note('<b>La prueba CSI específica sí pasó.</b> 100 frames de una referencia sintética versionada en Git produjeron 100 vectores y un hash idéntico. No se regeneró la expectativa ni se usó tolerancia.',y)-13
    r.text('SHA-256 calculado = esperado',M,y,9.7,True);y-=16
    digest=verification['csi_proof']['computed_sha256']
    r.text(digest[:32],M,y,9.7,font='Mono');y-=13;r.text(digest[32:],M,y,9.7,font='Mono');y-=22
    r.para('Original: evidence/upstream/03_verify_original_shell.log. Revisión: evidence/revision/verify_identified.json y su log. CSI: 05_csi_proof_original.log. No se reemplazaron los resultados históricos.',M,y,size=9.3,color=MUTED)

    y=r.new('Del escritorio a SWARM','Propuesta · Investigación aplicada')
    y=r.para('<b>Escenario inicial:</b> un paso despejado en un simulacro, con router propio a un lado y receptor fijo al opuesto. El dron transportaría el nodo. La hipótesis es que los cruces produzcan más ventanas ACTIVE que la quietud.',M,y,size=12.3)-20
    steps=[('01','TRANSPORTAR','Dron lleva el nodo.'),('02','APOYAR','Geometría estable.'),('03','MEDIR','Ventanas de 15 s.'),('04','CONTRASTAR','Inspección adicional.')]
    kw=(CW-24)/4
    for i,(num,title,desc) in enumerate(steps):
        x=M+i*(kw+8);r.box(x,y,kw,103,NAVY);r.text(num,x+11,y-25,19,True,LIME);r.text(title,x+11,y-48,8.6,True,WHITE);r.para(desc,x+11,y-58,kw-22,9.4,color='#b7c5cf',leading=12.6)
    y-=125
    y=r.para(f"<b>Fundamento observado.</b> En la ventana original hubo {pf['range']:.0f} dBm de rango y clasificación ACTIVE sin etiqueta humana. En la sesión extendida el filtro rechazó el resultado final por jitter. La prioridad es separar cambios de radio, del receptor y de personas; aún no medir alcance de rescate.",M,y,size=11.8)-20
    y=r.table(['Prueba siguiente','Qué resolvería'],[
        ('Contraste fijo','Un par de ensayo; luego tres pares nuevos quietud/cruces de 60 s, con orden alternado y configuración fija.'),
        ('Control del receptor','Mover o girar el sensor sin el cruce humano. Declarar si una persona lo sostiene.'),
        ('Avanzar a otra geometría','≥75% de ventanas elegibles aptas en cada sesión y más ACTIVE en cruces en los tres pares.'),
        ('Si no se cumple','Detener la extrapolación y revisar muestreo, geometría o utilidad del RSSI.')],[148,CW-148],y,font=10.2)-17
    y=r.note('Regla exploratoria propuesta; no es exactitud lograda ni criterio de seguridad. Una alerta pide inspección complementaria; una salida negativa no declara un sector vacío.',y)-13
    r.para('NIST documenta problemas de propagación [4]. PX4 no garantiza canal estable por mantener posición [5]. CSI [6] y sensado en vuelo exigirían validación propia. El ensayo humano permanece pendiente.',M,y,size=9.9,color=MUTED)

    y=r.new('Reproducible y defendible','Entrega · Evidencias y fuentes')
    y=r.table(['Etapa','Archivo principal'],[
        ('01-02','evidence/tutorial/01_environment.json · 02_netsh.txt'),
        ('03-04','evidence/tutorial/03_single_reading.json · 04_pipeline_15s.json'),
        ('05','evidence/sessions/ + evidence/ui/monitor-live.png'),
        ('06','evidence/tutorial/06_commodity_backend.json'),
        ('07-08','evidence/upstream/ y evidence/revision/'),
        ('Comparación','web/data/comparison.json; sesiones fuente intactas'),
        ('Propuesta','docs/SwarmSignal_Propuesta.pdf')],[88,CW-88],y,font=10.1)-18
    r.text('Reproducción local',M,y,12,True);y-=18
    commands=['python -m pytest tests -q', 'python -m swarm_signal.server', 'python scripts/capture.py --seconds 120']
    for command in commands:r.text(command,M,y,9.5,font='Mono');y-=17
    y-=4
    y=r.para('La reproducción pública utiliza registros guardados. La medición en vivo requiere Windows conectado a WiFi. Skybrush continúa pendiente de la copia asignada por VantTec y del tutorial del show real.',M,y,size=10.6)-18
    sources=[
        ('1','RuView: tutorial Windows, issue 36','https://github.com/ruvnet/RuView/issues/36'),
        ('2','Código exacto utilizado: '+source_commit[:12],'https://github.com/ruvnet/RuView/tree/'+source_commit),
        ('3','Microsoft: calidad de señal WLAN','https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_association_attributes'),
        ('4','NIST TN 1713: escenarios RF en emergencias','https://www.nist.gov/publications/structural-and-electromagnetic-scenarios-firefighter-locator-tracking-systems'),
        ('5','PX4: mantenimiento de posición','https://docs.px4.io/main/en/flight_modes_mc/position'),
        ('6','Espressif: ESP-CSI','https://github.com/espressif/esp-csi')]
    r.text('Fuentes primarias · consulta 09/09/2026',M,y,12,True);y-=20
    for num,title,url in sources:
        y=r.para(f'[{num}] <link href="{url}" color="#237c87">{escape(title)}</link>',M,y,size=10.4)-8
    r.para('Uso de IA: apoyo en lectura del tutorial, diagnóstico, implementación, diseño y revisión. Las mediciones, logs y pruebas proceden de ejecuciones identificables; los ejemplos de pruebas se declaran sintéticos.',M,y-6,size=10,color=MUTED)
    r.finish()


def proposal_paragraphs():
    return [
        'Proponemos ensayar un enlace WiFi sobre un paso despejado de un simulacro: router propio a un lado y receptor fijo al opuesto. Un dron de SWARM transportaría y depositaría el nodo; mediría inmóvil. La hipótesis es que los cruces humanos produzcan más ventanas ACTIVE que la quietud. Una alerta pediría inspección complementaria; no identificaría personas ni declararía un sector vacío.',
        f'La ventana original tuvo {len(p_rows)} muestras, {pf["duration_seconds"]:.2f} segundos de cobertura y {pf["sample_rate_hz"]:.3f} Hz; produjo ACTIVE con varianza {pf["variance"]:.3f} dBm². No hubo condición humana confirmada. En la sesión de {len(rows)} muestras, la ventana final se rechazó por irregularidad temporal. Observamos funcionamiento y límites de muestreo, pero todavía no eficacia de detección humana.',
        'Tras un par de ensayo, fijaremos geometría y configuración. Compararemos tres pares nuevos de 60 segundos, quietud y cruces, alternando el orden; registraremos también el movimiento del receptor como posible confusor. Usaremos ventanas de 15 segundos sin solapamiento. Avanzaremos a otra geometría solo si al menos 75% de las ventanas elegibles son aptas en cada sesión y la fracción ACTIVE es mayor durante cruces en los tres pares. Si no se cumple, revisaremos muestreo, geometría o utilidad del RSSI. Esta regla es exploratoria, no exactitud alcanzada ni un estándar de seguridad.',
        'Mover o girar el receptor cambia el canal; el control de vuelo no elimina ese efecto. Integrarlo exige portar el colector Windows, evaluar masa y energía, sincronizar telemetría y descartar mediciones durante desplazamientos. La cuantización de 1 dBm y el muestreo cercano a 2 Hz limitan la información: no se validan coordenadas, signos vitales, víctimas inmóviles ni alcance entre escombros. Sensar en vuelo o usar CSI requiere experimentos posteriores. La decisión de rescate seguirá en manos del equipo humano.'
    ]

def build_proposal():
    r=Report(DOCS/'SwarmSignal_Propuesta.pdf','SWARM SIGNAL | Propuesta de aplicación')
    y=r.new('Un nodo que llega con el dron','Propuesta de aplicación · SWARM')
    for paragraph in proposal_paragraphs():y=r.para(escape(paragraph),M,y,size=11.5,leading=16.7)-17
    y=r.note('Estado: propuesta experimental. Movimiento humano no confirmado. Ensayo físico etiquetado pendiente.',y,fill='#e8f0e5')-13
    r.para('Base: mediciones del informe; RuView #36; NIST TN 1713 y documentación PX4. Protocolo: docs/PRUEBA_PENDIENTE.md. Las fuentes completas están enlazadas en el informe.',M,y,size=9.3,color=MUTED)
    r.finish()
    (DOCS/'Propuesta.md').write_text('# Un nodo que llega con el dron\n\n'+'\n\n'.join(proposal_paragraphs())+'\n\nEstado: propuesta experimental; movimiento humano no confirmado.\n',encoding='utf-8')


def build_audit():
    installation=read('evidence/revision/installation.json')
    ui_qa=read('evidence/revision/ui/qa.json')
    assert installation['status']=='PASS' and all(x['status']=='PASS' for x in installation['checks'])
    assert ui_qa['summary']['failed']==0
    technical_after=ROOT/'docs/audit/TECNICA_DESPUES.md'
    if not technical_after.exists():
        raise FileNotFoundError('Esperar la aceptación técnica antes de publicar mejoras como verificadas.')
    before=ROOT/'docs/audit/screens/01-public-entry.png'
    after=ROOT/'evidence/revision/ui/01-public-entry.png'
    if not before.exists() or not after.exists():
        raise FileNotFoundError('Faltan capturas comparables antes/después de la revisión.')
    r=Report(DOCS/'SwarmSignal_Auditoria.pdf','SWARM SIGNAL | Evaluación crítica y revisión')
    y=r.new('Por qué aún no era 10/10','Evaluación independiente · Antes de mejorar',True)
    y=r.kpis([('7.8/10','rúbrica propia; no oficial'),('394','muestras en tres sesiones'),('0','sesiones con condición física confirmada')],y,True)
    y=r.para('Había mediciones auténticas, cálculos correctos y una propuesta prudente. Faltaban el ensayo físico exigido, una decisión experimental concreta y pruebas de varios fallos de recuperación y muestreo.',M,y,size=13,color=WHITE)-22
    for title,body in [
        ('Cumplimiento parcial','La captura del monitor demuestra adquisición. No demuestra que el participante se movió frente al enlace.'),
        ('Software que debía resistir errores','Una instalación interrumpida, un guardado fallido o una sesión corrupta podían romper la entrega.'),
        ('Una propuesta aún demasiado amplia','Enumeraba métricas sin definir un escenario, una hipótesis contrastable ni cuándo avanzar.')]:
        r.text(title,M,y,12,True,LIME);y-=12
        y=r.para(body,M,y,size=11.3,color='#c0cdd5')-24
    y=r.para('La auditoría se cerró antes de modificar la aplicación. Base: 99de7de05c98. Documento consolidado: docs/AUDITORIA_CRITICA.md; evaluación y reproducciones: docs/audit/.',M,y,size=10.1,color='#b6c5cf')-17
    r.para('<b>Rúbrica propia:</b> tutorial 30/40; propuesta 30/40; rigor 14/15; claridad 4/5. Total: 78/100. Tutorial y propuesta tienen igual peso; los criterios y descuentos están en EVALUACION_ANTES.md.',M,y,size=10.4,color='#c0cdd5')
    r.box(M,116,CW,61,PANEL)
    r.para('Skybrush es opcional y no resta puntos al reto base. La evidencia de movimiento sí es obligatoria. No se asigna una nota oficial ni se acredita la defensa oral del participante.',M+13,104,CW-26,10.8,color=WHITE,leading=14.5)

    y=r.new('Qué cambió y cómo se prueba','Después · Correcciones de software')
    y=r.para(f'La batería final registra <b>{OWN} pruebas propias aprobadas</b>, incluidas correcciones del cierre. Los casos usan fixtures sintéticos; no son nuevas capturas ni ensayos con personas.',M,y,size=12)-18
    y=r.table(['Antes','Revisión comprobada'],[
        ('Guardado fallido sin recuperación','Datos pendientes conservados; error visible y reintento antes de reemplazar la sesión.'),
        ('JSON corrupto rompe catálogo','Archivos inválidos aislados; solicitudes y estado de captura coherentes.'),
        ('Banda sin información produce veredicto','Cobertura espectral explícita; abstención sin suficientes bins y ante irregularidad.'),
        ('Datos o horizontes inválidos','Validación de valores, orden y duración; límites que impiden recorridos desmedidos y descartes silenciosos.'),
        ('CSV vivo o interfaz renombrada falla','Exportación consistente de la captura activa; selección de adaptador conectado.'),
        ('Cuerpo JSON incorrecto inicia captura','Tipos y estructura validados antes de cambiar el estado del laboratorio.'),
        ('El video local no permite buscar','Respuestas HTTP Range para avanzar por capítulos; rangos inválidos rechazados.')],[175,CW-175],y,font=10.7)-19
    y=r.note('<b>La evidencia histórica se preserva.</b> Los registros iniciales mantienen sus resultados. La revisión analiza los datos con una política identificada; no reescribe el pasado para mostrar más aprobaciones.',y)-18
    y=r.para('Aceptación detallada: docs/audit/TECNICA_DESPUES.md. Resultados automatizados: '+OWN_EVIDENCE+'. El iniciador y la exportación se revisan además con los registros de operación de evidence/revision/.',M,y,size=10.2,color=MUTED)-16
    r.para('<b>Instalación:</b> limpia en Python 3.11.9 y recuperación en 3.12.14 aprobadas. Registro: evidence/revision/installation.json. Se instalaron dependencias y se importó la aplicación; no hubo captura física.',M,y,size=10.5)

    y=r.new('Una entrega fácil de recorrer','Antes / después · Interfaz real')
    y=r.para('Mismo tamaño de ventana: 1440 × 900. Las capturas muestran la entrada real antes y después de corregir el recorrido. Son vistas de registros guardados, no una nueva prueba humana.',M,y,size=11.5)-24
    width=(CW-14)/2
    for x,label,path in [(M,'ANTES',before),(M+width+14,'DESPUÉS',after)]:
        r.text(label,x,y,10.5,True)
        im=ImageReader(str(path));iw,ih=im.getSize();height=width*ih/iw
        r.c.drawImage(im,x,y-13-height,width,height,mask='auto')
    y-=width*900/1440+34
    y=r.table(['Problema de recorrido','Mejora'],[
        ('Salto inicial de 342 px','Entrada desde la cabecera; navegación disponible.'),
        ('Entrega y fuentes dispersas','Accesos directos a informe, propuesta, video y evidencia.'),
        ('Monitor enlazado solo a datos','Captura visual enlazada junto con el registro fuente.'),
        ('Reproducción inconsistente','Controles alineados con el estado y navegación accesible.'),
        ('Comparación ausente','Tres sesiones reales, calidad temporal y ventanas sin solapar.')],[185,CW-185],y,font=10.5)-19
    y=r.note('El contenido adicional tiene una función: permitir que el evaluador encuentre el requisito, el resultado y su evidencia. El diseño no cambia qué se midió.',y)-15
    r.para(f"QA registrada: {ui_qa['summary']['passed']} comprobaciones, cero fallos; evidence/revision/ui/qa.json. Capturas: docs/audit/screens/01-public-entry.png y evidence/revision/ui/01-public-entry.png. El monitor vivo histórico se conserva por separado.",M,y,size=9.6,color=MUTED)

    y=r.new('Resultados que se pueden auditar','Después · Cifras y verificación')
    y=r.para('La comparación usa los tres JSON originales y ventanas consecutivas. La variabilidad se describe sin atribuirla a actividad humana ni convertir las muestras en ensayos independientes.',M,y,size=11.8)-18
    y=comparison_table(r,y)-19
    y=window_map(r,y)
    vc=identified_verify['counts']
    y=r.table(['Verificación','PASS','FAIL','SKIP','Salida'],[
        ('Original','5','1','3','1'),
        ('Cliente identificado',str(vc['pass']),str(vc['fail']),str(vc['skip']),str(identified_verify['exit_code']))],
        [CW-240,60,60,60,60],y,font=10.7)-18
    y=r.note('El HTTP 403 se resolvió identificando el cliente en curl. El verificador original y la expectativa CSI no se modificaron. Tres fases siguen omitidas; una salida global exitosa no las convierte en ejecutadas.',y)-16
    r.para('Datos: web/data/comparison.json. Verificación: evidence/upstream/verification_summary.json y evidence/revision/verify_identified.json. La comparación es técnica; no permite calcular sensibilidad, precisión o capacidad de rescate.',M,y,size=10.1,color=MUTED)

    y=r.new('La mejora no sustituye la prueba','Cierre · Criterio y pendientes reales')
    y=r.para('<b>Propuesta refinada:</b> enlace fijo sobre un paso despejado de un simulacro; router conocido y nodo que el dron transportaría. Hipótesis: más ventanas ACTIVE durante cruces que durante quietud.',M,y,size=12)-20
    y=r.table(['Decisión','Condición propuesta'],[
        ('Preparar','Un par de ensayo y después tres pares nuevos de 60 s. Configuración fija, orden alternado y etiquetas reales.'),
        ('Avanzar a otra geometría','≥75% de ventanas elegibles aptas por sesión y más ACTIVE en cruces en los tres pares.'),
        ('Detener y revisar','Si no se cumple, estudiar muestreo, geometría o utilidad del RSSI. No cambiar la regla después para aparentar éxito.'),
        ('Mantener alcance limitado','Una alerta pide otra inspección. Un resultado negativo no descarta personas, víctimas inmóviles ni riesgos.')],[145,CW-145],y,font=10.8)-19
    y=r.note('<b>Falta ejecutar el ensayo físico.</b> La regla del 75% es exploratoria; no expresa precisión lograda, requisito oficial ni seguridad. Ninguna de las sesiones entregadas acredita movimiento humano confirmado.',y)-18
    y=r.para('<b>Defensa oral y IA.</b> Se prepararon un recorrido por el código y un ejercicio con una ventana no vista. Codex apoyó implementación y documentación; la comprensión personal debe demostrarse por el participante. No está acreditada por este PDF.',M,y,size=11.2)-17
    y=r.para('<b>Base de evaluación.</b> Guía SWARM, pp. 3-4: ocho etapas y propuesta de media a una cuartilla; p. 6: documentar fallos es válido. La propuesta final conserva una página. Skybrush depende de los recursos asignados y permanece opcional.',M,y,size=10.6)-17
    r.para('La revisión mejora la calidad técnica y la claridad. La nota previa de 7.8/10 se conserva como registro de una rúbrica propia; no se reemplaza por un 10/10 automático. Cumplimiento físico y utilidad operativa siguen sujetos a evidencia futura.',M,y,size=10.8,color=MUTED)
    r.finish()


def render_and_check():
    summary=[]
    for name,expected in [('SwarmSignal_Informe',10),('SwarmSignal_Propuesta',1),('SwarmSignal_Auditoria',5)]:
        document=pymupdf.open(DOCS/(name+'.pdf'))
        assert len(document)==expected,(name,len(document))
        changed=[]
        for index,page in enumerate(document):
            rendered=REVIEW/f'{name}-{index+1:02d}.png'
            previous=hashlib.sha256(rendered.read_bytes()).hexdigest() if rendered.exists() else None
            page.get_pixmap(matrix=pymupdf.Matrix(1.35,1.35)).save(rendered)
            if hashlib.sha256(rendered.read_bytes()).hexdigest()!=previous:
                changed.append(index+1)
            text=page.get_text()
            assert '\ufffd' not in text and len(text)>100
        summary.append({'file':name+'.pdf','pages':len(document),'rendered':len(document),
                        'sha256':hashlib.sha256((DOCS/(name+'.pdf')).read_bytes()).hexdigest(),
                        'changed_pages':changed,'own_tests_passed':OWN,'own_tests_evidence':OWN_EVIDENCE,
                        'physical_ground_truth':'unconfirmed','input_session':session_file.name,
                        'source_links':sum(len(page.get_links()) for page in document)})
    (REVIEW/'render_check.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    backup=ROOT/'tmp/pdf-before-revision'
    backup.mkdir(exist_ok=True)
    for name in ['SwarmSignal_Informe.pdf','SwarmSignal_Propuesta.pdf']:
        if (DOCS/name).exists() and not (backup/name).exists():
            shutil.copy2(DOCS/name,backup/name)
    assert identified_verify['source_unchanged'], 'No describir el verificador como original si cambió.'
    build_report();build_proposal();build_audit();render_and_check()
