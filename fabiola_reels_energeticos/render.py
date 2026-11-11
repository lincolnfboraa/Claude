#!/usr/bin/env python3
"""Monta o Reels a partir de timeline.json.
Uso: python3 render.py <pasta_intermediarios> <saida.mp4> [legendas.ass] [altura_saida]
altura_saida: 1920 (final, padrão) ou 1280 (preview 720p).
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
W, H = 1440, 2560
args, fc, cat = ['ffmpeg', '-v', 'error', '-y'], [], []
offset = 0.0
for i, s in enumerate(t['segmentos']):
    fi, fo = round(s['in']*FPS), round(s['out']*FPS)
    tin, dur = fi/FPS, (fo-fi)/FPS
    off = os.path.join(src_dir, s['fonte']+'.offset')
    if os.path.exists(off): tin -= float(open(off).read())
    args += ['-ss', f'{tin:.4f}', '-t', f'{dur:.4f}', '-i', os.path.join(src_dir, s['fonte']+'.mov')]
    q = t['enquadramentos'][s['quadro']]
    cx, cy = s.get('centro', t['centro_rosto'][s['fonte']])
    cw, ch = round(W/q['zoom']/2)*2, round(H/q['zoom']/2)*2
    x = min(max(cx*W - cw/2, 0), W-cw); y = min(max(cy*H - q['face_y']*ch, 0), H-ch)
    fc.append(f"[{i}:v]crop={cw}:{ch}:{int(x)}:{int(y)},scale={OW}:{OH}:flags=lanczos,setsar=1,fps=30000/1001,trim=duration={dur:.4f},setpts=PTS-STARTPTS[v{i}]")
    fc.append(f"[{i}:a]atrim=duration={dur:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={dur-0.015:.4f}:d=0.015[a{i}]")
    cat.append(f"[v{i}][a{i}]")
    s['out_start'] = round(offset, 3); offset += dur; s['out_end'] = round(offset, 3)
n = len(t['segmentos'])
vpost = "eq=contrast=1.04:saturation=1.03:gamma=1.01,unsharp=5:5:0.35:5:5:0"
if ass: vpost += f",subtitles={ass}:fontsdir={os.path.join(here, 'fonts')}"
fc.append(''.join(cat) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append(f"[cv]{vpost},format=yuv420p[vo]")
fc.append("[ca]highpass=f=80,afftdn=nf=-32:nr=8,equalizer=f=250:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.0:g=1.5,"
          "acompressor=threshold=-21dB:ratio=2.5:attack=8:release=160:makeup=1.5,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=48000[ao]")
args += ['-filter_complex', ';'.join(fc), '-map', '[vo]', '-map', '[ao]',
         '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
         '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-r', '30000/1001',
         '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', out]
subprocess.run(args, check=True)
json.dump(t, open(os.path.join(here, 'timeline_render.json'), 'w'), ensure_ascii=False, indent=1)
print('ok', out, round(offset, 2), 's')
