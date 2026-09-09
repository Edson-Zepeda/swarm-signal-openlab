"""Render a measured-evidence explainer, 1920x1080/30fps, with Spanish narration.

Pillow draws original vectors; all quantitative marks come from recorded JSON.
Only the public narration text is sent to Edge TTS. Cached audio allows offline builds.
"""
from __future__ import annotations
import argparse
import asyncio
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import subprocess
import time
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'media'
ASSETS = MEDIA / 'video'
W,H,FPS = 1920,1080,30
BG = '#080d13'; PANEL='#10171f'; LINE='#22313c'; WHITE='#edf3f4'; MUTED='#9baebc'
LIME='#b9f45b'; CYAN='#6ce0e9'; PURPLE='#b99bff'; AMBER='#ffc275'
FFMPEG=shutil.which('ffmpeg'); FFPROBE=shutil.which('ffprobe')
VOICE='es-MX-JorgeNeural'

@lru_cache(maxsize=60)
def font(size=32,bold=False,mono=False):
    filename='consola.ttf' if mono else 'segoeuib.ttf' if bold else 'segoeui.ttf'
    location=Path('C:/Windows/Fonts')/filename
    if not location.exists():
        location=Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return ImageFont.truetype(str(location),int(size))

def text(d,s,x,y,size=32,color=WHITE,bold=False,anchor=None,mono=False):
    d.text((int(x),int(y)),str(s),font=font(size,bold,mono),fill=color,anchor=anchor)

def box(d,rect,color=PANEL,outline=LINE,radius=24,width=2):
    d.rounded_rectangle(tuple(map(int,rect)),radius=radius,fill=color,outline=outline,width=width)

def ease(t):
    t=max(0,min(1,t)); return 1-(1-t)**3

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def probe(path):
    return json.loads(subprocess.check_output([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))

def load_evidence():
    # Read the explicit manifest; never pick the first or largest recording.
    sys.path.insert(0, str(ROOT))
    from swarm_signal.analysis import analyze, from_rows, ANALYSIS_VERSION, MAX_JITTER_CV, MAX_INTERVAL_DEVIATION
    config_path=ROOT/'project.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))
    reference=next(r for r in config['recordings'] if r['id']==config['reference_session'])
    session_path=ROOT/reference['source']
    tutorial_path=ROOT/'evidence/tutorial/04_pipeline_15s.json'
    historical_path=ROOT/'evidence/upstream/verification_summary.json'
    verification_path=ROOT/config['verification']
    comparison_path=ROOT/'web/data/comparison.json'
    own_path=ROOT/config['own_tests']
    tutorial=json.loads(tutorial_path.read_text(encoding='utf-8'))
    session=json.loads(session_path.read_text(encoding='utf-8'))
    historical=json.loads(historical_path.read_text(encoding='utf-8'))
    identified=json.loads(verification_path.read_text(encoding='utf-8'))
    comparison=json.loads(comparison_path.read_text(encoding='utf-8'))
    own_cases=list(ET.parse(own_path).getroot().iter('testcase'))
    own_passed=sum(not any(n.find(tag) is not None for tag in ('failure','error','skipped')) for n in own_cases)
    assert own_passed==len(own_cases) and own_passed>0, 'Do not render a passing suite with failures or skips.'
    for record in config['recordings']:
        assert record['kind']=='recorded_real_wifi' and sha(ROOT/record['source'])==record['sha256']
        compared=next(r for r in comparison['sessions'] if r['id']==record['id'])
        assert compared['source_sha256']==record['sha256']
        assert compared['ground_truth']=='unconfirmed'
    assert not comparison['physical']['comparison_ready']
    assert identified['counts']['fail']==0 and identified['source_unchanged']
    assert tutorial['ground_truth']=='unconfirmed' and session['session']['ground_truth']=='unconfirmed'
    revised=analyze(from_rows(session['samples']))
    session.update(revised)
    assert session['classification'] is None and session['spectrum']==[]
    rows=session['samples']; y=np.array([r['rssi_dbm'] for r in rows]); t=np.array([r['timestamp'] for r in rows]); t-=t[0]
    summary={'samples':len(rows),'duration_requested_seconds':session['session']['duration_seconds'],
        'duration_observed_seconds':float(t[-1]),'mean_dbm':float(y.mean()),'min_dbm':float(y.min()),'max_dbm':float(y.max()),
        'effective_hz':float((len(t)-1)/t[-1]),'last_window_samples':session['features']['n_samples'],
        'jitter_cv':session['quality']['jitter_cv'],'max_gap_seconds':session['quality']['max_gap_seconds'],
        'nyquist_hz':session['quality']['nyquist_hz'],'quality_ready':False,'ground_truth':'unconfirmed',
        'analysis_policy_version':ANALYSIS_VERSION,'max_jitter_cv':MAX_JITTER_CV,
        'max_interval_deviation':MAX_INTERVAL_DEVIATION,'motion_band_hz':session['quality']['motion_band']['configured_hz'],
        'nominal_collector_hz':2.0,'nominal_nyquist_hz':1.0}
    verification={**historical,'revision':identified,'comparison':comparison,'project_version':config['version'],
        'own_tests_snapshot':{'tests':len(own_cases),'passed':own_passed,'source':config['own_tests'],
                              'source_sha256':sha(own_path)}}
    paths=[config_path,tutorial_path,historical_path,verification_path,comparison_path,own_path,
           ROOT/'swarm_signal/analysis.py',ROOT/'swarm_signal/collector.py',ROOT/'swarm_signal/experiment.py']
    paths.extend(ROOT/r['source'] for r in config['recordings'])
    provenance=[]
    for path in paths:
        relative=path.relative_to(ROOT).as_posix()
        snapshot=ASSETS/'sources/revision'/relative
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        snapshot.write_bytes(path.read_bytes())
        provenance.append({'path':relative,'sha256':sha(path),'snapshot_path':snapshot.relative_to(ROOT).as_posix()})
    verification['own_tests_snapshot']['snapshot_path']=next(p['snapshot_path'] for p in provenance if p['path']==config['own_tests'])
    return tutorial,session,verification,summary,provenance

def specification(tutorial,session,verification,summary):
    return [
        {'title':'La señal. La evidencia.','label':'SWARM SIGNAL · REVISIÓN 1.1','kind':'intro','minimum':9,
         'narration':'Swarm Signal transforma lecturas reales de Wi-Fi en evidencia reproducible. Esta edición incorpora la auditoría técnica y sus correcciones.'},
        {'title':'Del Wi-Fi al análisis.','label':'PIPELINE REAL','kind':'pipeline','minimum':9,
         'narration':f'El tutorial registró {tutorial["features"]["n_samples"]} muestras con el recolector original. El sistema conecta lectura, extracción de características y clasificación, conservando los datos.'},
        {'title':'Cada lectura cuenta.','label':'REPRODUCCIÓN ACELERADA','kind':'trace','minimum':10,
         'narration':f'La captura de ciento veinte segundos contiene {summary["samples"]} lecturas. La señal varía, pero estas mediciones no tienen etiquetas de movimiento humano verificadas.'},
        {'title':'La calidad cambia entre capturas.','label':'COMPARACIÓN · VENTANAS DE 15 s','kind':'comparison','minimum':12,
         'narration':'Las tres capturas cumplen calidad en tres de ocho, cero de tres y dos de cuatro ventanas elegibles. Esta comparación describe el muestreo; no mide precisión de detección humana.'},
        {'title':'Abstenerse también es un resultado.','label':'ÚLTIMA VENTANA · REFERENCIA DE 120 s','kind':'quality','minimum':11,
         'narration':'La última ventana excede el límite de irregularidad del cinco por ciento. Se conservan las lecturas y se omiten el espectro y la clasificación.'},
        {'title':'La banda completa no está observada.','label':'COBERTURA · ESQUEMA TEÓRICO','kind':'coverage','minimum':10,
         'narration':'A dos muestras por segundo, el límite teórico es un hertz. La banda original de movimiento llega a tres. Su cobertura es parcial.'},
        {'title':'Correcciones comprobadas.','label':'VERIFICACIÓN DE SOFTWARE','kind':'tests','minimum':10,
         'narration':f'La revisión aprueba {verification["own_tests_snapshot"]["passed"]} pruebas propias. Se conservan las {verification["unit"]["passed"]} unitarias y {verification["live_adapted"]["passed"]} integraciones originales, con su evidencia histórica separada.'},
        {'title':'Verificación con límites visibles.','label':'CSI · REFERENCIA SINTÉTICA','kind':'proof','minimum':14,
         'narration':'La referencia sintética CSI conserva su hash exacto. Al identificar el cliente de consulta, la nueva verificación pasa seis fases y omite tres. El error cuatrocientos tres anterior permanece documentado.'},
        {'title':'El siguiente paso: validar.','label':'PROPUESTA SWARM','kind':'proposal','minimum':10,
         'narration':'Un receptor fijo permite comparar quietud y cruces declarados. Esa prueba física sigue pendiente. Después se podrá evaluar el efecto de nodos móviles.'},
    ]

async def make_audio(scenes):
    import edge_tts
    semaphore=asyncio.Semaphore(3)
    async def one(i,scene):
        audio=ASSETS/f'voice_{i+1:02}.mp3'; meta=ASSETS/f'voice_{i+1:02}.json'
        digest=hashlib.sha256((scene['narration']+VOICE+'+3%').encode()).hexdigest()
        if audio.exists() and meta.exists() and json.loads(meta.read_text())['text_hash']==digest:
            return
        async with semaphore:
            words=[]
            comm=edge_tts.Communicate(scene['narration'],VOICE,rate='+3%',boundary='WordBoundary')
            with audio.open('wb') as stream:
                async for part in comm.stream():
                    if part['type']=='audio': stream.write(part['data'])
                    elif part['type']=='WordBoundary':
                        words.append({'text':part['text'],'start':part['offset']/10000000,'end':(part['offset']+part['duration'])/10000000})
            meta.write_text(json.dumps({'voice':VOICE,'generated_voice':True,'text_hash':digest,'text':scene['narration'],'words':words},indent=2,ensure_ascii=False),encoding='utf-8')
    await asyncio.gather(*(one(i,s) for i,s in enumerate(scenes)))

class Renderer:
    def __init__(self,tutorial,session,verification,summary,scenes):
        self.a=tutorial; self.s=session; self.v=verification; self.m=summary; self.scenes=scenes
        self.rows=session['samples']; self.ts=np.array([s['timestamp'] for s in self.rows]); self.ts-=self.ts[0]
        self.ys=np.array([s['rssi_dbm'] for s in self.rows])
        self.bases=[self.base(i,s) for i,s in enumerate(scenes)]

    def base(self,i,scene):
        im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
        # Decorative identity grid, explicitly separate from quantitative charts.
        for x in range(0,W,96):d.line((x,0,x,H),fill='#0d151e',width=1)
        for y in range(0,H,96):d.line((0,y,W,y),fill='#0d151e',width=1)
        box(d,(66,38,102,74),color=LIME,outline=LIME,radius=8)
        d.line((73,58,80,50,87,64,96,48),fill=BG,width=3)
        text(d,'SWARM / SIGNAL',120,37,30,WHITE,True)
        text(d,'OPEN LAB',1748,44,24,MUTED,anchor='rt',mono=True)
        d.line((72,103,1848,103),fill=LINE,width=2)
        text(d,scene['label'],75,144,26,LIME,True,mono=True)
        text(d,scene['title'],72,197,62 if len(scene['title'])>34 else 68,WHITE,True)
        box(d,(1510,137,1848,178),color='#13262b',outline='#2d4750',radius=20)
        badge={'tests':'PRUEBAS EJECUTADAS','proof':'REFERENCIA SINTÉTICA','proposal':'DISEÑO PROPUESTO'}.get(scene['kind'],'ESQUEMA TEÓRICO' if scene['kind']=='coverage' else 'DATOS REPRODUCIDOS')
        text(d,badge,1679,156,20,CYAN,True,anchor='mm')
        text(d,'SWARM · SOFTWARE',75,1017,24,MUTED,mono=True)
        text(d,f'{i+1:02} / {len(self.scenes):02}',1848,1017,24,LIME,anchor='rt',mono=True)
        return im

    def axes(self,d,rect,xmax,ymin,ymax,xticks=4,yticks=4,xlabel='Tiempo (s)',ylabel='RSSI (dBm)'):
        x,y,w,h=rect
        for j in range(yticks+1):
            yy=y+h-h*j/yticks; val=ymin+(ymax-ymin)*j/yticks
            d.line((x,yy,x+w,yy),fill=LINE,width=2)
            text(d,f'{val:g}',x-20,yy,26,MUTED,anchor='rm',mono=True)
        for j in range(xticks+1):
            xx=x+w*j/xticks
            d.line((xx,y,xx,y+h),fill='#17232d',width=1)
            text(d,f'{xmax*j/xticks:g}',xx,y+h+22,25,MUTED,anchor='mt',mono=True)
        text(d,ylabel,x,y-49,25,MUTED)
        text(d,xlabel,x+w,y+h+64,25,MUTED,anchor='rt')

    def trace(self,d,ts,ys,rect,p=1,color=CYAN,xmax=None,ymin=None,ymax=None,marker=True):
        x,y,w,h=rect; xmax=xmax or float(ts[-1]); ymin=ymin if ymin is not None else math.floor(float(min(ys)))-1
        ymax=ymax if ymax is not None else math.ceil(float(max(ys)))+1
        cursor=(len(ts)-1)*max(0,min(1,p)); count=int(cursor)+1
        coords=[(x+w*float(tt)/xmax,y+h-h*(float(v)-ymin)/(ymax-ymin)) for tt,v in zip(ts[:count],ys[:count])]
        if count<len(ts):
            fraction=cursor-int(cursor)
            tt=float(ts[count-1]+fraction*(ts[count]-ts[count-1]))
            value=float(ys[count-1]+fraction*(ys[count]-ys[count-1]))
            coords.append((x+w*tt/xmax,y+h-h*(value-ymin)/(ymax-ymin)))
        if len(coords)>1:
            # Smooth drawing between recorded vertices; never adds sample rows.
            d.line(coords,fill=color,width=4,joint='curve')
            if marker:
                xx,yy=coords[-1]; d.line((xx,y,xx,y+h),fill='#385a63',width=2)
                d.ellipse((xx-8,yy-8,xx+8,yy+8),fill=color)
        return coords[-1]

    def metric(self,d,label,value,unit,x,y,w=430,color=LIME):
        box(d,(x,y,x+w,y+157))
        text(d,label,x+27,y+22,25,MUTED)
        text(d,value,x+27,y+58,58,color,True)
        if unit:text(d,unit,x+w-25,y+99,26,MUTED,anchor='rt')

    def frame(self,index,t,span):
        im=self.bases[index].copy();d=ImageDraw.Draw(im); kind=self.scenes[index]['kind']; p=ease(t/1.6)
        if kind=='intro':
            text(d,'Medir antes',74,344,104,WHITE,True)
            text(d,'de afirmar.',74,464,104,LIME,True)
            text(d,'RSSI real. Código verificable.',80,649,36,MUTED)
            box(d,(1050,338,1845,810))
            rect=(1114,407,670,312)
            # No axes on hero: a decorative crop of the same actual trace.
            self.trace(d,self.ts,self.ys,rect,p=max(.03,min(1,t/8)),xmax=120,ymin=-62,ymax=-55)
            text(d,'REPRODUCCIÓN · CAPTURA DE 120 s',1117,751,25,CYAN,True)
            text(d,'Sin etiquetas humanas verificadas',80,872,32,AMBER)
        elif kind=='pipeline':
            labels=['NETSH','RSSI','RASGOS','DECISIÓN']; xx=[76,537,998,1459]
            for j,(x,label) in enumerate(zip(xx,labels)):
                box(d,(x,328,x+385,443),outline=LIME if t>.7*j else LINE)
                text(d,label,x+192,385,33,LIME if t>.7*j else MUTED,True,anchor='mm')
                if j<3:
                    d.line((x+387,385,x+453,385),fill=LINE,width=3)
                    pos=(t*.55-j*.13)%1;dot=x+389+pos*61
                    d.ellipse((dot-5,380,dot+5,390),fill=CYAN)
            a=self.a['samples'];ts=np.array([r['timestamp'] for r in a]);ts-=ts[0];ys=np.array([r['rssi_dbm'] for r in a])
            rect=(150,543,1070,281);self.axes(d,rect,15,-61,-55,3,3)
            self.trace(d,ts,ys,rect,min(1,t/8),xmax=15,ymin=-61,ymax=-55)
            self.metric(d,'Muestras',str(self.a['features']['n_samples']),'',1324,519,520)
            self.metric(d,'Media',f'{self.a["features"]["mean"]:.2f}','dBm',1324,706,520,CYAN)
            text(d,'Collector → RssiFeatureExtractor → CommodityBackend',78,937,25,MUTED,mono=True)
        elif kind=='trace':
            rect=(150,383,1250,443);self.axes(d,rect,120,-62,-55,4,7)
            prog=min(1,t/max(1,span-1.2));self.trace(d,self.ts,self.ys,rect,prog,xmax=120,ymin=-62,ymax=-55)
            self.metric(d,'Lecturas',str(self.m['samples']),'',1470,356,374)
            self.metric(d,'Rango',f'{self.m["min_dbm"]:.0f} / {self.m["max_dbm"]:.0f}','dBm',1470,539,374,CYAN)
            self.metric(d,'Muestreo efectivo',f'{self.m["effective_hz"]:.2f}','Hz',1470,722,374,PURPLE)
            text(d,'La variación del RSSI no confirma movimiento humano.',78,945,30,AMBER)
        elif kind=='comparison':
            rows=self.v['comparison']['sessions']
            labels=['Referencia de 120 s','Carga simultánea de CPU','Captura de 60 s']
            for j,(record,label) in enumerate(zip(rows,labels)):
                yy=330+j*190
                box(d,(76,yy,1844,yy+163))
                text(d,label,109,yy+28,35,WHITE,True)
                text(d,f'{record["count"]} lecturas · {record["effective_rate_hz"]:.2f} Hz',112,yy+87,28,MUTED)
                windows=record['windows']; segment=76; gap=14; x=760
                for k,window in enumerate(windows):
                    color=LIME if window['ready'] else AMBER if window['eligible'] else MUTED
                    alpha=ease((t-j*.2-k*.08)/1.8)
                    rgb=tuple(int(int(color[i:i+2],16)*alpha) for i in (1,3,5))
                    box(d,(x+k*(segment+gap),yy+49,x+k*(segment+gap)+segment,yy+113),color=rgb,outline=None,radius=10)
                text(d,f'{record["windows_valid"]} / {record["windows_eligible"]}',1803,yy+70,62,LIME if record['windows_valid'] else AMBER,True,anchor='rm')
                text(d,'ventanas aptas',1803,yy+120,24,MUTED,anchor='rm')
            for x,color,label in [(80,LIME,'Cumple'),(340,AMBER,'Abstención'),(686,MUTED,'Fracción final no elegible')]:
                box(d,(x,926,x+22,948),color=color,outline=None,radius=5)
                text(d,label,x+35,920,27,MUTED)
            text(d,'Calidad del muestreo',1840,922,29,WHITE,True,anchor='rt')
        elif kind=='quality':
            last=self.rows[-self.s['features']['n_samples']:];dt=np.diff([r['timestamp'] for r in last]); x,y,w,h=148,408,1020,350
            self.axes(d,(x,y,w,h),len(dt),0,1.5,4,3,'Intervalo entre muestras','Separación temporal (s)')
            n=max(1,int(len(dt)*min(1,t/5)))
            for j,v in enumerate(dt[:n]):
                xx=x+(j+.15)*w/len(dt);hh=float(v)/1.5*h
                box(d,(xx,y+h-hh*p,xx+w/len(dt)*.7,y+h),color=AMBER if v>1 else CYAN,outline=None,radius=5)
            box(d,(1270,350,1844,858),outline='#725636')
            text(d,'Muestreo irregular',1300,388,36,AMBER,True)
            text(d,f'{self.m["jitter_cv"]*100:.1f}%',1300,465,80,WHITE,True)
            text(d,'Variación de intervalos (CV)',1303,566,26,MUTED)
            text(d,f'Límite CV: {self.m["max_jitter_cv"]*100:.0f} %',1303,614,30,AMBER)
            text(d,f'Hueco máximo: {self.m["max_gap_seconds"]:.2f} s',1303,659,27,MUTED)
            box(d,(1296,722,1819,808),color='#30281e',outline='#725636',radius=18)
            text(d,'SIN ESPECTRO NI CLASE',1557,764,30,AMBER,True,anchor='mm')
            text(d,'La abstención conserva la incertidumbre.',78,934,34,WHITE,True)
        elif kind=='coverage':
            x,w=145,1150; ymax=3.0; band_low,band_high=self.m['motion_band_hz']
            limit=self.m['nominal_nyquist_hz']; x_limit=x+w*limit/ymax
            text(d,'Banda original de movimiento',x,339,32,MUTED)
            box(d,(x+w*band_low/ymax,407,x+w,486),color='#173238',outline=CYAN,radius=15)
            text(d,'0.5 – 3 Hz',x+w*.58,446,33,CYAN,True,anchor='mm')
            text(d,'Parte observable a 2 muestras/s',x,550,32,MUTED)
            box(d,(x+w*band_low/ymax,620,x+w,699),color='#30281e',outline='#725636',radius=15)
            end=x+w*band_low/ymax+(x_limit-(x+w*band_low/ymax))*ease(t/2)
            if end>x+w*band_low/ymax+10:
                box(d,(x+w*band_low/ymax,620,end,699),color=LIME,outline=None,radius=12)
            text(d,'Fuera del alcance',x+w*.64,657,33,AMBER,True,anchor='mm')
            d.line((x_limit,380,x_limit,785),fill=LIME,width=3)
            for tick in [0,.5,1,2,3]:
                xx=x+w*tick/ymax;d.line((xx,763,xx,779),fill=MUTED,width=2)
                text(d,f'{tick:g}',xx,798,28,LIME if tick==limit else MUTED,anchor='mt',mono=True)
            text(d,'Frecuencia (Hz)',x+w,855,27,MUTED,anchor='rt')
            box(d,(1404,365,1844,834))
            text(d,'LÍMITE TEÓRICO',1434,407,26,MUTED,True)
            text(d,f'{limit:g} Hz',1434,476,92,LIME,True)
            text(d,'Cobertura parcial',1436,619,33,WHITE,True)
            text(d,'No mide respiración',1436,715,27,AMBER)
            text(d,'Con muestreo irregular, el espectro no se publica.',78,939,34,AMBER)
        elif kind=='tests':
            cards=[('UNITARIAS',self.v['unit']['passed'],'Código original','Suite de RuView',LIME),
                   ('INTEGRACIÓN',self.v['live_adapted']['passed'],'Precheck en español',f'{self.v["live_adapted"]["adaptation"]["assertions_count"]} aserciones intactas',CYAN),
                   ('SWARM SIGNAL',self.v['own_tests_snapshot']['passed'],'Pruebas propias','Core + evidencia',PURPLE)]
            for j,(label,value,detail,sub,color) in enumerate(cards):
                x=76+j*601;box(d,(x,350,x+566,810))
                text(d,label,x+32,391,31,MUTED,True)
                text(d,str(value),x+31,469,137,color,True)
                text(d,'PASS',x+361,561,43,color,True)
                text(d,detail,x+33,675,31,WHITE)
                text(d,sub,x+33,734,27,MUTED)
                for k in range(value):
                    xx=x+33+(k%20)*24;yy=842+(k//20)*14
                    if (k+1)/value<=ease(t/3):box(d,(xx,yy,xx+16,yy+7),color=color,outline=None,radius=4)
            text(d,'Pruebas de software ≠ precisión de detección humana.',78,951,30,AMBER)
        elif kind=='proof':
            box(d,(76,339,1844,661));text(d,'CSI · REFERENCIA SINTÉTICA',109,372,28,MUTED,True)
            text(d,'HASH IDÉNTICO',110,427,70,LIME,True)
            text(d,f'{self.v["csi_proof"]["frames_processed"]} tramas procesadas',1255,459,35,WHITE)
            digest=self.v['csi_proof']['computed_sha256'];revealed=digest[:max(1,int(len(digest)*ease(t/3)))]
            text(d,revealed,110,552,33,CYAN,mono=True)
            text(d,'./verify actual',82,709,31,WHITE,True,mono=True)
            counts=self.v['revision']['counts']
            for x,label,count,color in [(490,'PASS',counts['pass'],LIME),(1180,'SKIP',counts['skip'],MUTED)]:
                box(d,(x,701,x+664,837));text(d,f'{count} {label}',x+332,769,48,color,True,anchor='mm')
            text(d,'Cliente identificado · script original sin cambios',78,892,32,WHITE,True)
            text(d,'HTTP 403 inicial: conservado en el historial',78,941,28,AMBER)
        elif kind=='proposal':
            text(d,'PROPUESTA · POR VALIDAR',77,314,27,AMBER,True)
            cx,cy=574,563
            for radius in (68,110,152):
                pulse=math.sin(t*.8)*7;d.ellipse((cx-radius-pulse,cy-radius-pulse,cx+radius+pulse,cy+radius+pulse),outline='#284a45',width=3)
            box(d,(cx-38,cy-47,cx+38,cy+47),color=LIME,outline=LIME,radius=16)
            d.line((cx,cy-42,cx,cy-83),fill=LIME,width=8)
            text(d,'Receptor fijo',cx,762,39,LIME,True,anchor='mt')
            for j,(xx,yy) in enumerate([(1110,415),(1465,653)]):
                d.line((cx+165,cy,xx-64,yy),fill=LINE,width=3)
                progress=(t*.2+j*.35)%1;px=(cx+165)+(xx-64-cx-165)*progress;py=cy+(yy-cy)*progress
                d.ellipse((px-6,py-6,px+6,py+6),fill=CYAN)
                for dx,dy in [(-42,-28),(42,-28),(-42,28),(42,28)]:d.ellipse((xx+dx-17,yy+dy-17,xx+dx+17,yy+dy+17),outline=CYAN,width=3)
                d.line((xx-42,yy-28,xx+42,yy+28),fill=CYAN,width=4);d.line((xx-42,yy+28,xx+42,yy-28),fill=CYAN,width=4)
            text(d,'Nodos móviles',1340,762,39,CYAN,True,anchor='mt')
            for j,label in enumerate(['Calibrar','Etiquetar','Medir precisión']):
                x=77+j*598;box(d,(x,865,x+565,961));text(d,label,x+282,911,35,WHITE,True,anchor='mm')
        # A continuous progress track supports motion without inventing data.
        elapsed=self.scenes[index]['start']+t;total=self.scenes[-1]['end']
        d.rectangle((72,989,1848,993),fill=LINE);d.rectangle((72,989,72+1776*elapsed/total,993),fill=LIME)
        return im

def captions(scenes):
    items=[]
    for i,scene in enumerate(scenes):
        path=ASSETS/f'voice_{i+1:02}.json'
        if not path.exists():continue
        chunk=[]
        for j,word in enumerate(json.loads(path.read_text(encoding='utf-8'))['words']):
            chunk.append(word)
            if len(chunk)>=9 or word['text'].endswith(('.',':','?')):
                items.append({'start':scene['start']+.25+chunk[0]['start'],'end':scene['start']+.25+chunk[-1]['end'],'text':' '.join(w['text'] for w in chunk)});chunk=[]
        if chunk:items.append({'start':scene['start']+.25+chunk[0]['start'],'end':scene['start']+.25+chunk[-1]['end'],'text':' '.join(w['text'] for w in chunk)})
    def ts(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    srt='\n'.join(f'{i+1}\n{ts(c["start"])} --> {ts(c["end"])}\n{c["text"]}\n' for i,c in enumerate(items))
    (MEDIA/'SwarmSignal_Demo.srt').write_text(srt,encoding='utf-8')
    (MEDIA/'SwarmSignal_Demo.vtt').write_text('WEBVTT\n\n'+srt.replace(',', '.'),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');args=parser.parse_args()
    MEDIA.mkdir(exist_ok=True);ASSETS.mkdir(exist_ok=True)
    assert FFMPEG and FFPROBE,'FFmpeg and ffprobe are required.'
    tutorial,session,verification,summary,provenance=load_evidence();scenes=specification(tutorial,session,verification,summary)
    voice_available=True
    try:asyncio.run(make_audio(scenes))
    except Exception as exc:
        (ASSETS/'voice_error.txt').write_text(str(exc),encoding='utf-8')
        raise RuntimeError('Narration could not be refreshed; do not publish stale audio.') from exc
    offset=0
    for i,scene in enumerate(scenes):
        audio=ASSETS/f'voice_{i+1:02}.mp3';audio_duration=float(probe(audio)['format']['duration']) if voice_available else 0
        seconds=math.ceil(max(scene['minimum'],audio_duration+.9)*FPS)/FPS
        scene.update(start=offset,end=offset+seconds,duration=seconds,audio_duration=audio_duration);offset+=seconds
    assert 75<=offset<=120,f'Adjust narration pacing: planned video is {offset:.1f}s.'
    timeline={'resolution':[W,H],'fps':FPS,'duration_seconds':offset,'voice':VOICE if voice_available else None,
        'generated_voice':voice_available,'source_provenance':provenance,'capture_summary':summary,'scenes':scenes,
        'all_recorded_signal_traces_are_measured_replays':True,
        'non_measurement_visuals':['configured_frequency_coverage','proposed_receiver_nodes'],
        'ground_truth':'unconfirmed','csi_reference_kind':'SYNTHETIC',
        'upstream_commit':verification['upstream']['commit'],'own_tests_snapshot':verification['own_tests_snapshot'],
        'revision':verification['project_version'],'analysis_policy_version':summary['analysis_policy_version'],
        'verification_current':verification['revision'],'comparison_current':verification['comparison'],
        'spectral_peaks_from_irregular_windows_shown':False}
    (ASSETS/'timeline.json').write_text(json.dumps(timeline,indent=2,ensure_ascii=False),encoding='utf-8')
    renderer=Renderer(tutorial,session,verification,summary,scenes)
    for i,scene in enumerate(scenes):renderer.frame(i,min(6,scene['duration']*.65),scene['duration']).save(ASSETS/f'preview_{i+1:02}.png')
    renderer.frame(0,7,scenes[0]['duration']).save(MEDIA/'SwarmSignal_Poster.jpg',quality=94)
    if args.preview: print(json.dumps({'duration':offset,'voice':voice_available}));return
    silent=ASSETS/'video_silent.mp4';log=ASSETS/'render.log'
    command=[FFMPEG,'-hide_banner','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-an','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)]
    with log.open('wb') as stream:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT)
        index=0;begun=time.monotonic();frames=round(offset*FPS)
        for n in range(frames):
            stamp=n/FPS
            while index+1<len(scenes) and stamp>=scenes[index]['end']:index+=1
            local=stamp-scenes[index]['start'];im=renderer.frame(index,local,scenes[index]['duration'])
            # A short true crossfade at every chapter boundary.
            if index>0 and local<.55:
                prev=renderer.frame(index-1,scenes[index-1]['duration']-.55+local,scenes[index-1]['duration'])
                im=Image.blend(prev,im,ease(local/.55))
            process.stdin.write(im.tobytes())
            if n%(FPS*10)==0:print(json.dumps({'rendered_seconds':stamp,'total_seconds':offset,'elapsed_seconds':round(time.monotonic()-begun,1)}),flush=True)
        process.stdin.close();code=process.wait()
    assert code==0,f'FFmpeg failed; inspect {log}'
    output=MEDIA/'SwarmSignal_Demo.mp4'
    if voice_available:
        padded=[]
        for i,scene in enumerate(scenes):
            dest=ASSETS/f'padded_{i+1:02}.wav'
            subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i',str(ASSETS/f'voice_{i+1:02}.mp3'),'-af','adelay=250:all=1,apad',
                            '-t',str(scene['duration']),'-ar','48000','-ac','1',str(dest)],check=True)
            padded.append(dest)
        listing=ASSETS/'audio_concat.txt';listing.write_text(''.join("file '"+p.name+"'\n" for p in padded),encoding='utf-8')
        audio=ASSETS/'narration.wav';subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(audio)],check=True)
        captions(scenes)
        subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(audio),'-i',str(MEDIA/'SwarmSignal_Demo.srt'),
            '-map','0:v','-map','1:a','-map','2:s','-c:v','copy','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-c:s','mov_text',
            '-metadata:s:s:0','language=spa','-metadata','title=Swarm Signal | Evidencia Wi-Fi', '-movflags','+faststart',str(output)],check=True)
    else:shutil.copy2(silent,output)
    report=probe(output);v=next(s for s in report['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'],v['r_frame_rate'])==(W,H,'30/1')
    assert abs(float(report['format']['duration'])-offset)<.15
    verification_report={'output':str(output.relative_to(ROOT)).replace('\\','/'),'sha256':sha(output),
        'duration_seconds':float(report['format']['duration']),'width':v['width'],'height':v['height'],'fps':v['r_frame_rate'],
        'audio_present':any(s['codec_type']=='audio' for s in report['streams']),
        'subtitles_present':any(s['codec_type']=='subtitle' for s in report['streams']),
        'probe':report,'representative_frames':[f'media/video/preview_{i+1:02}.png' for i in range(len(scenes))],
        'visual_review_status':'pending_manual_review'}
    (MEDIA/'video_verification.json').write_text(json.dumps(verification_report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in verification_report.items() if k!='probe'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
