#!/usr/bin/env python3
"""Versão SEM TRATAMENTO DE IMAGEM: usa os .MOV originais do iPhone (HDR HLG, 10 bits) e só aplica cortes e recortes.
Codifica trecho por trecho (pouca memória) e junta sem recodificar.
Uso: python3 render_hdr.py <pasta_com_IMG_xxxx.mov> <saida.mp4> [altura=3840]
Rode antes: python3 apara_pausas.py (os cortes vêm de timeline.json)."""
import json, sys, os, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor

FPS = 30000/1001
here = os.path.dirname(os.path.abspath(__file__))
t = json.load(open(os.path.join(here, 'timeline.json')))
src, out = sys.argv[1], sys.argv[2]
OH = int(sys.argv[3]) if len(sys.argv) > 3 else 3840
OW = OH*9//16
W, H = 2160, 3840                       # originais: 3840x2160 com rotação de 90° -> 2160x3840
tmp = tempfile.mkdtemp(prefix='hdr_', dir=os.path.dirname(os.path.abspath(out)))
X265 = 'colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:range=limited:no-sao=1:no-strong-intra-smoothing=1'

def pedacos(seg):
    rem = sorted([(c['de'], c['ate']) for c in seg.get('cortes', [])] + [tuple(p) for p in seg.get('pausas', [])])
    res, cur = [], seg['in']
    for a, b in rem:
        if a > cur: res.append((cur, a))
        cur = max(cur, b)
    if seg['out'] > cur: res.append((cur, seg['out']))
    return [(round(a*FPS), round(b*FPS)) for a, b in res if round(b*FPS) - round(a*FPS) >= 2]

jobs, audio_in, audio_fc = [], [], []
for s in t['segmentos']:
    q = t['enquadramentos'][s['quadro']]
    cx, cy = s.get('centro', t['centro_rosto'][s['fonte']])
    cw, ch = round(W/q['zoom']/2)*2, round(H/q['zoom']/2)*2
    x = int(min(max(cx*W - cw/2, 0), W-cw)); y = int(min(max(cy*H - q['face_y']*ch, 0), H-ch))
    for fa, fb in pedacos(s):
        tin, dur = fa/FPS, (fb-fa)/FPS
        f = os.path.join(src, s['fonte'] + '.mov')
        n = len(jobs)
        jobs.append(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', f, '-an',
                     '-vf', f'crop={cw}:{ch}:{x}:{y},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001',
                     '-frames:v', str(fb-fa),
                     '-c:v', 'libx265', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p10le', '-x265-params', X265,
                     '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc',
                     os.path.join(tmp, f'p{n:03d}.mp4')])
        audio_in += ['-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', f]
        audio_fc.append(f"[{n}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.010,afade=t=out:st={max(dur-0.012,0):.4f}:d=0.012[a{n}]")

_off = 0.0
for s_ in t['segmentos']:
    s_['out_start'] = round(_off, 3)
    for fa, fb in pedacos(s_): _off += (fb - fa) / FPS
    s_['out_end'] = round(_off, 3)
json.dump(t, open(os.path.join(here, 'timeline_render.json'), 'w'), ensure_ascii=False, indent=1)
with ThreadPoolExecutor(2) as ex:
    for r in ex.map(lambda a: subprocess.run(a).returncode, jobs):
        if r: sys.exit('falha ao codificar um trecho')
lst = os.path.join(tmp, 'lista.txt')
open(lst, 'w').write(''.join(f"file 'p{i:03d}.mp4'\n" for i in range(len(jobs))))
vid = os.path.join(tmp, 'video.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', vid], check=True)
n = len(jobs)
aud = os.path.join(tmp, 'audio.m4a')
afc = ';'.join(audio_fc) + ';' + ''.join(f'[a{i}]' for i in range(n)) + f'concat=n={n}:v=0:a=1[ca];' + \
      "[ca]highpass=f=80,afftdn=nf=-32:nr=8,equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.0:g=1.5," \
      "acompressor=threshold=-21dB:ratio=2.5:attack=8:release=160:makeup=1.5,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=48000[ao]"
subprocess.run(['ffmpeg', '-v', 'error', '-y'] + audio_in + ['-filter_complex', afc, '-map', '[ao]', '-c:a', 'aac', '-b:a', '192k', aud], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', vid, '-i', aud, '-map', '0:v', '-map', '1:a', '-c', 'copy', '-tag:v', 'hvc1',
                '-movflags', '+faststart', out], check=True)
print('ok', out)
