#!/usr/bin/env python3
"""Monta o Reels a partir de timeline.json.
Uso: python3 render.py <pasta_intermediarios> <saida.mp4> [legendas.ass] [altura_saida]
altura_saida: 3840 (4K), 1920 (1080p, padrão) ou 1280 (preview 720p).
Se existir <pasta>/<fonte>.offset, o intermediário começa nesse segundo do original.
Intermediários = MOVs originais convertidos de HLG para SDR em 1440x2560 (ver README.md)."""
import json, sys, subprocess, os
FPS = 30000/1001
here = os.path.dirname(os.path.abspath(__file__))
t = json.load(open(os.path.join(here, 'timeline.json')))
src_dir, out = sys.argv[1], sys.argv[2]
ass = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] not in ('', '-') else None
OH = int(sys.argv[4]) if len(sys.argv) > 4 else 1920
OW = OH*9//16
_f = os.path.join(src_dir, t['segmentos'][0]['fonte'] + '.mov')
W, H = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                '-of', 'csv=p=0', _f], capture_output=True, text=True).stdout.split()[0].split(','))
args, fc, cat = ['ffmpeg', '-v', 'error', '-y'], [], []

def pedacos(seg):
    """[in,out] menos cortes manuais ('cortes') e pausas automáticas ('pausas'), em quadros inteiros."""
    rem = sorted([(c['de'], c['ate']) for c in seg.get('cortes', [])] + [tuple(p) for p in seg.get('pausas', [])])
    out, cur = [], seg['in']
    for a, b in rem:
        if a > cur: out.append((cur, a))
        cur = max(cur, b)
    if seg['out'] > cur: out.append((cur, seg['out']))
    res = []
    for a, b in out:
        fa, fb = round(a*FPS), round(b*FPS)
        if fb - fa >= 2: res.append((fa, fb))
    return res

offset, n = 0.0, 0
for s in t['segmentos']:
    q = t['enquadramentos'][s['quadro']]
    cx, cy = s.get('centro', t['centro_rosto'][s['fonte']])
    cw, ch = round(W/q['zoom']/2)*2, round(H/q['zoom']/2)*2
    x = min(max(cx*W - cw/2, 0), W-cw); y = min(max(cy*H - q['face_y']*ch, 0), H-ch)
    off = os.path.join(src_dir, s['fonte']+'.offset')
    off = float(open(off).read()) if os.path.exists(off) else 0.0
    s['out_start'] = round(offset, 3); s['pedacos'] = []
    for fa, fb in pedacos(s):
        tin, dur = fa/FPS - off, (fb-fa)/FPS
        args += ['-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', os.path.join(src_dir, s['fonte']+'.mov')]
        i = n; n += 1
        fc.append(f"[{i}:v]crop={cw}:{ch}:{int(x)}:{int(y)},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001,trim=duration={dur:.4f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[{i}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.010,afade=t=out:st={max(dur-0.012,0):.4f}:d=0.012[a{i}]")
        cat.append(f"[v{i}][a{i}]")
        s['pedacos'].append({'fonte_de': round(fa/FPS, 3), 'fonte_ate': round(fb/FPS, 3), 'saida_de': round(offset, 3)})
        offset += dur
    s['out_end'] = round(offset, 3)
vpost = "null"   # sem filtro de cor: só a conversão HDR->SDR feita nos intermediários
if ass: vpost = f"subtitles={ass}:fontsdir={os.path.join(here, 'fonts')}"
fc.append(''.join(cat) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append(f"[cv]{vpost},format=yuv420p[vo]")
fc.append("[ca]highpass=f=80,afftdn=nf=-32:nr=8,equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.0:g=1.5,"
          "acompressor=threshold=-21dB:ratio=2.5:attack=8:release=160:makeup=1.5,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=48000[ao]")
args += ['-filter_complex', ';'.join(fc), '-map', '[vo]', '-map', '[ao]',
         '-c:v', 'libx264', '-preset', 'slow' if OH <= 1920 else 'medium', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
         '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-r', '30000/1001',
         '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', out]
subprocess.run(args, check=True)
json.dump(t, open(os.path.join(here, 'timeline_render.json'), 'w'), ensure_ascii=False, indent=1)
print('ok', out, round(offset, 2), 's')
