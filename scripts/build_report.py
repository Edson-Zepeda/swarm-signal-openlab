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

def own_count():
    for path in [ROOT / 'evidence/own_tests.xml', ROOT / 'evidence/tests/own.xml', ROOT / 'evidence/tests/project.xml', ROOT / 'evidence/own.xml']:
        if path.exists():
            node = ET.parse(path).getroot()
            cases = list(node.iter('testcase'))
            passed = sum(not any(c.tag in {'failure', 'error', 'skipped'} for c in case) for case in cases)
            return passed, path.relative_to(ROOT).as_posix()
    raise FileNotFoundError('Falta evidencia XML de las pruebas propias. Ejecuta pytest --junitxml=evidence/own_tests.xml.')

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

    def chart(self, xs, ys, top, height, title, ylabel, color='#237c87', points=False, ymax=None, ymin=None):
        self.text(title, M, top, 12, True)
        left, right, bottom, plot_top = M+43, W-M-10, top-height+31, top-24
        low = math.floor(min(ys)) if ymin is None else ymin
        high = math.ceil(max(ys)) if ymax is None else ymax
        if high == low: high += 1
        xmin,xmax = min(xs),max(xs)
        if xmax == xmin: xmax += 1
        for i in range(5):
            y = bottom+(plot_top-bottom)*i/4
            val = low+(high-low)*i/4
            self.c.setStrokeColor(HexColor('#d8e2e7')); self.c.setLineWidth(.55)
            self.c.line(left,y,right,y)
            self.text(f'{val:.1f}' if abs(high-low)<5 else f'{val:.0f}', M+2,y-3,8.5,color=MUTED)
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


def build_report():
    r=Report(DOCS/'SwarmSignal_Informe.pdf','SWARM SIGNAL | Informe de evidencia')
    y=r.new('WiFi medido.\nEvidencia verificable.'.replace('\n','<br/>'),'Informe técnico · Reto de Software',True)
    y=H-204
    y=r.para('Sensado RSSI en Windows y propuesta de integración a SWARM.',M,y,CW,14,color='#aabac5')-24
    y=r.kpis([(str(len(p_rows)),'muestras en el tutorial'),(str(len(rows)),'muestras en sesión extendida'),(f"{verification['unit']['passed']} + {verification['live_adapted']['passed']}",'unitarias + live adaptadas')],y,True)
    y=r.para('El pipeline ejecutó la clasificación <b>ACTIVE</b> en la ventana del tutorial. El movimiento físico y la presencia humana no fueron confirmados.',M,y,CW,13,color=WHITE)-22
    stage=[('01-02','Entorno y WiFi','Windows 11 conectado. Evidencia del SO.'),('03-04','Lectura y pipeline','RSSI directo; 15 s solicitados.'),('05','Monitor','Captura real; entorno sin etiqueta física.'),('06-07','Integración y pruebas',f'CommodityBackend; {OWN} pruebas propias.'),('08','Verificación','CSI: PASS. ./verify completo: FAIL.')]
    for num,title,desc in stage:
        r.text(num,M,y-10,10,True,CYAN);r.text(title,M+55,y-10,12,True,WHITE)
        y=r.para(desc,M+55,y-17,CW-55,10.5,color='#aabac5')-18
    r.box(M,118,CW,55,PANEL)
    r.para('Pendiente: ensayo humano etiquetado. Avanzado Skybrush: falta la copia asignada de VantTec y su tutorial.',M+13,107,CW-26,10.6,color='#d4e0e7',leading=14)

    y=r.new('Entorno y lectura directa','Etapas 01 · 02 · 03')
    y=r.para('Se clonó y fijó RuView. La captura usa el adaptador WiFi del equipo mediante netsh; no se instaló hardware de sensado adicional.',M,y)-20
    y=r.table(['Componente','Evidencia observada'],[
        ('Sistema',env['os']),('Python',env['python'].split(' (')[0]),
        ('Dependencias',f"NumPy {env['packages']['numpy']} · SciPy {env['packages']['scipy']} · pytest {env['packages']['pytest']}"),
        ('Adaptador','Realtek 8822CE · Wi-Fi · 5 GHz · canal 161'),
        ('Conectividad','Estado: conectado. Identificadores de red omitidos.')],[131,CW-131],y)-22
    r.text('Commit de origen',M,y,10,True);y-=16
    r.text(source_commit,M,y,9.2,font='Mono');y-=28
    y=r.kpis([(f"{single['sample']['rssi_dbm']:.0f} dBm",'lectura individual original'),(f"{env['strict_netsh_reading']['rssi_dbm']:.0f} dBm",'verificación del SO'),('100 %','calidad del SO')],y)
    y=r.note('Son lecturas consecutivas, no simultáneas. El valor 0 de calidad que entrega el colector original es un error de idioma: ignora “Señal”. No representa calidad real nula.',y)-19
    y=r.para('<b>Adaptación local.</b> Se decodifica UTF-8 con alternativa OEM, se selecciona la interfaz conectada y se exige RSSI directo. Una lectura ausente genera error; nunca se sustituye por -80 dBm. Ruido y contadores de bytes no medidos quedan excluidos.',M,y,size=11.5)-16
    r.para('Fuentes de evidencia: 01_environment.json, 02_netsh.txt y 03_single_reading.json, en evidence/tutorial/. El RSSI de la lectura original se conserva.',M,y,size=9.5,color=MUTED)

    y=r.new('La ventana de 15 segundos','Etapa 04 · Datos del pipeline original')
    y=r.kpis([(f"{pf['mean']:.2f}",'RSSI medio (dBm)'),(f"{pf['variance']:.3f}",'varianza (dBm²)'),(f"{pf['sample_rate_hz']:.3f}",'tasa efectiva (Hz)')],y)
    px=[v['timestamp']-p_rows[0]['timestamp'] for v in p_rows];py=[v['rssi_dbm'] for v in p_rows]
    y=r.chart(px,py,y,197,'Figura 1. RSSI original, 30 muestras','dBm',points=True)-5
    n=len(py);signal=[(v-statistics.mean(py))*.5*(1-math.cos(2*math.pi*i/(n-1))) for i,v in enumerate(py)]
    frequencies=[k*pf['sample_rate_hz']/n for k in range(1,n//2+1)]
    powers=[abs(sum(v*cmath.exp(-2j*math.pi*k*t/n) for t,v in enumerate(signal)))**2/n for k in range(1,n//2+1)]
    y=r.chart(frequencies,powers,y,157,'Figura 2. Espectro Hann de la misma ventana','Energía relativa',color='#5365a1',ymin=0)-2
    y=r.note(f"<b>Salida algorítmica: {pipeline['classification']['motion_level'].upper()}.</b> Varianza {pf['variance']:.3f} ≥ 0.3; energía de movimiento {pf['motion_band_power']:.3f} ≥ 0.1. El score 100% es heurístico, no exactitud medida.",y)-14
    r.para(f"15 s solicitados; {pf['duration_seconds']:.2f} s entre primera y última muestra. Nyquist: {pf['sample_rate_hz']/2:.3f} Hz. La banda nominal 0.5-3 Hz queda truncada por el muestreo. No se infieren signos vitales ni causas de la variación. Datos: evidence/tutorial/04_pipeline_15s.json.",M,y,size=10.1,color=MUTED)

    y=r.new('El muestreo también importa','Etapa 05 · Monitor y sesión extendida')
    y=r.kpis([(str(len(rows)),'muestras reales'),(f'{duration:.2f} s','cobertura temporal'),(f'{observed_rate:.3f} Hz','tasa de toda la sesión')],y)
    sx=[v['timestamp']-rows[0]['timestamp'] for v in rows];sy=[v['rssi_dbm'] for v in rows]
    y=r.chart(sx,sy,y,172,'Figura 3. Sesión solicitada de 120 s','dBm')
    y=r.note(f"<b>Ventana final sin veredicto.</b> Su jitter relativo es {session['quality'].get('jitter_cv',0):.3f}, superior al límite 0.25. La aplicación rechaza la clasificación aunque conserva los datos. netsh registró {session['capture_diagnostics']['netsh_error_count']} errores.",y)-15
    y=r.chart(sx[1:],dt,y,174,'Figura 4. Intervalos entre muestras consecutivas','Segundos',color='#5365a1',ymin=0)
    r.para(f"Condición: no confirmada. Latencia media de netsh: {session['capture_diagnostics']['mean_netsh_latency_seconds']:.3f} s. Datos: evidence/sessions/{session_file.name}. Las figuras son reconstrucciones de mediciones guardadas, no señales sintéticas.",M,y,size=9.8,color=MUTED)

    y=r.new('El monitor en funcionamiento','Etapa 05 · Evidencia visual')
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
    y=r.para('<b>Mejoras verificadas.</b> Se impide iniciar otra sesión mientras se guarda la anterior; callbacks y temporizadores obsoletos se descartan. Ventanas incompletas, huecos y muestreo irregular suspenden el veredicto. El servidor acepta acceso local y rechaza origen externo.',M,y,size=11.5)-15
    y=r.para('La prueba live de “variación” original imprime valores pero no contiene una aserción. Aprobar la batería demuestra ejecución e invariantes de software; no sensibilidad, especificidad ni validación en personas.',M,y,size=10.5,color=MUTED)-15
    r.para('Trazabilidad: evidence/upstream/verification_summary.json, unit.xml, live_original.xml, live_adapted.xml y live_precheck_locale.patch. Pruebas propias: '+escape(OWN_EVIDENCE)+'.',M,y,size=9.3,color=MUTED)

    y=r.new('Verificar sin ocultar los fallos','Etapa 08 · ./verify sin modificaciones')
    y=r.kpis([('5','fases PASS'),('1','fase FAIL'),('3','fases SKIP')],y)
    descriptions=[('1','PASS','Hash del pipeline Python'),('2','PASS','Revisión de generadores aleatorios'),('3','SKIP','Rust: Cargo / v2 no disponibles'),('4','SKIP','PyO3: Cargo / binding no disponibles'),('5','PASS','Invariante identity_risk_score'),('6','FAIL','Registro crates: primer endpoint HTTP 403'),('7','PASS','Paquete npm publicado'),('8','PASS','Manifiesto Docker amd64 + arm64'),('9','SKIP','Daemon Docker no disponible')]
    y=r.table(['Fase','Estado','Resultado observado'],descriptions,[48,70,CW-118],y,font=10.2)-17
    y=r.para('<b>Resultado global: FAIL, salida 1.</b> El script interpreta fallos HTTP como paquetes ausentes; el 403 observado no prueba que no existan los 12 crates. No se afirma haber ejecutado Rust ni el contenedor.',M,y,size=11)-16
    y=r.note('<b>La prueba CSI específica sí pasó.</b> 100 frames de una referencia sintética versionada en Git produjeron 100 vectores y un hash idéntico. No se regeneró la expectativa ni se usó tolerancia.',y)-13
    r.text('SHA-256 calculado = esperado',M,y,9.7,True);y-=16
    digest=verification['csi_proof']['computed_sha256']
    r.text(digest[:32],M,y,9.7,font='Mono');y-=13;r.text(digest[32:],M,y,9.7,font='Mono');y-=22
    r.para('Evidencia: 03_verify_original_shell.log y 05_csi_proof_original.log. Esta repetibilidad matemática es independiente de la captura física RSSI.',M,y,size=9.3,color=MUTED)

    y=r.new('Del escritorio a SWARM','Propuesta · Investigación aplicada')
    y=r.para('Un nodo transportado por dron puede ayudar a priorizar inspecciones. La primera versión mide con el receptor apoyado y un transmisor controlado. Cada alerta solicita revisión; ninguna salida negativa declara un sector seguro.',M,y,size=13)-20
    steps=[('01','TRANSPORTAR','Dron lleva el nodo.'),('02','APOYAR','Geometría estable.'),('03','MEDIR','Ventanas de 15 s.'),('04','CONTRASTAR','Inspección adicional.')]
    kw=(CW-24)/4
    for i,(num,title,desc) in enumerate(steps):
        x=M+i*(kw+8);r.box(x,y,kw,103,NAVY);r.text(num,x+11,y-25,19,True,LIME);r.text(title,x+11,y-48,8.6,True,WHITE);r.para(desc,x+11,y-58,kw-22,9.4,color='#b7c5cf',leading=12.6)
    y-=125
    y=r.para(f"<b>Fundamento observado.</b> En la ventana original hubo {pf['range']:.0f} dBm de rango y clasificación ACTIVE sin etiqueta humana. En la sesión extendida el filtro rechazó el resultado final por jitter. La prioridad es separar cambios de radio, del receptor y de personas; aún no medir alcance de rescate.",M,y,size=11.8)-20
    y=r.table(['Prueba siguiente','Qué resolvería'],[
        ('Quietud / cruce humano','Registrar etiquetas independientes, repetidas y sincronizadas.'),
        ('Mover solo el receptor','Cuantificar falsas alarmas por posición y orientación.'),
        ('Obstáculos y geometrías','Comparar condiciones específicas con calibración separada.'),
        ('Criterio de avance','Conteos de aciertos, omisiones, falsas alarmas, latencia y pérdida de muestras.')],[160,CW-160],y,font=10.5)-20
    y=r.note('No hay validación de presencia, localización, respiración o pulso. CSI y varios receptores son investigación futura, no prestaciones demostradas.',y)-15
    r.para('NIST describe atenuación, multitrayectoria e interferencias en emergencias [4]. El control de posición del dron requiere estimación válida [5]; no garantiza canal radioeléctrico constante. Espressif ofrece CSI por subportadora [6], con validación propia pendiente.',M,y,size=10.2,color=MUTED)

    y=r.new('Reproducible y defendible','Entrega · Evidencias y fuentes')
    y=r.table(['Etapa','Archivo principal'],[
        ('01-02','evidence/tutorial/01_environment.json · 02_netsh.txt'),
        ('03-04','evidence/tutorial/03_single_reading.json · 04_pipeline_15s.json'),
        ('05','evidence/sessions/ + evidence/ui/monitor-live.png'),
        ('06','evidence/tutorial/06_commodity_backend.json'),
        ('07-08','evidence/upstream/verification_summary.json y logs'),
        ('Propuesta','docs/SwarmSignal_Propuesta.pdf')],[65,CW-65],y,font=10.1)-18
    r.text('Reproducción local',M,y,12,True);y-=18
    commands=['python -m pytest tests -q', 'python -m swarm_signal.server', 'python scripts/capture.py --seconds 120', 'python scripts/build_report.py']
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
        'Proponemos evaluar un nodo WiFi transportado por un dron de SWARM para priorizar la inspección de sectores accesibles después de un desastre. El dron coloca el nodo o se apoya, y un transmisor controlado establece el enlace. El sistema registra ventanas de 15 segundos y entrega alertas para una inspección complementaria. No identifica personas ni certifica que un sector esté vacío.',
        f'La prueba original registró {len(p_rows)} muestras en {pf["duration_seconds"]:.2f} segundos entre primera y última lectura, a {pf["sample_rate_hz"]:.3f} Hz. El RSSI medio fue {pf["mean"]:.2f} dBm, con varianza {pf["variance"]:.3f} dBm², y el clasificador produjo ACTIVE. Como no hubo etiquetas físicas, no podemos atribuir esa salida a movimiento humano. En la sesión extendida de {len(rows)} muestras, la ventana final se rechazó por muestreo irregular. Ambas observaciones justifican controlar la calidad antes de emitir una alerta.',
        'El primer ensayo usaría receptor inmóvil. Desplazarlo o girarlo modifica la propagación; el control de vuelo no elimina ese factor. Compararemos quietud, cruces humanos y movimiento del receptor sin personas, con etiquetas sincronizadas, repeticiones y calibración separada de la evaluación. Después variaremos obstáculos y geometrías. Registraremos aciertos, omisiones, falsas alarmas, latencia y muestras perdidas antes de proponer alcance operativo.',
        'La integración requiere portar el colector Windows a un nodo ligero, sincronizar telemetría, evaluar masa y energía, disponer de transmisor propio y descartar ventanas durante desplazamientos. El RSSI cuantizado y el muestreo cercano a 2 Hz limitan la información; un único enlace no ofrece coordenadas ni signos vitales confiables. CSI y varios receptores serían una etapa posterior con validación independiente. El beneficio esperado es aportar evidencia complementaria para decidir dónde inspeccionar primero, manteniendo la decisión final en el equipo de rescate.'
    ]

def build_proposal():
    r=Report(DOCS/'SwarmSignal_Propuesta.pdf','SWARM SIGNAL | Propuesta de aplicación')
    y=r.new('Un nodo que llega con el dron','Propuesta de aplicación · SWARM')
    for paragraph in proposal_paragraphs():y=r.para(escape(paragraph),M,y,size=11.5,leading=16.7)-17
    y=r.note('Estado: propuesta experimental. Movimiento humano no confirmado. Ensayo físico etiquetado pendiente.',y,fill='#e8f0e5')-13
    r.para('Base: mediciones incluidas en el informe; RuView issue #36; NIST TN 1713; documentación oficial de PX4 y ESP-CSI. Los enlaces completos aparecen en el informe técnico.',M,y,size=9.3,color=MUTED)
    r.finish()
    (DOCS/'Propuesta.md').write_text('# Un nodo que llega con el dron\n\n'+'\n\n'.join(proposal_paragraphs())+'\n\nEstado: propuesta experimental; movimiento humano no confirmado.\n',encoding='utf-8')


def render_and_check():
    summary=[]
    for name,expected in [('SwarmSignal_Informe',9),('SwarmSignal_Propuesta',1)]:
        document=pymupdf.open(DOCS/(name+'.pdf'))
        assert len(document)==expected,(name,len(document))
        for index,page in enumerate(document):
            page.get_pixmap(matrix=pymupdf.Matrix(1.35,1.35)).save(REVIEW/f'{name}-{index+1:02d}.png')
            text=page.get_text()
            assert '\ufffd' not in text and len(text)>100
        summary.append({'file':name+'.pdf','pages':len(document),'rendered':len(document),
                        'physical_ground_truth':'unconfirmed','input_session':session_file.name})
    (REVIEW/'render_check.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    build_report();build_proposal();render_and_check()
