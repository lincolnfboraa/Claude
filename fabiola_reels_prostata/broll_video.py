#!/usr/bin/env python3
"""Transforma um clipe de B-roll (ex.: animação gerada no Canva) em sequência PNG RGBA de tela cheia, ajustada a uma
duração alvo (acelera/desacelera levemente) e com fade de entrada/saída, para aplicar sobre o HDR com render_hdr_texto.py.
Uso: python3 broll_video.py <clipe.mp4> <pasta_saida> <altura> <duracao_alvo> [fade=0.25]"""
import sys, os, subprocess, json
clip, out, OH, dur = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
fade = float(sys.argv[5]) if len(sys.argv) > 5 else 0.25
OW = OH * 9 // 16
d0 = float(json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', clip],
                                     capture_output=True, text=True).stdout)['format']['duration'])
os.makedirs(out, exist_ok=True)
vf = (f"setpts=PTS*{dur/d0:.5f},fps=30000/1001,scale={OW}:{OH}:force_original_aspect_ratio=increase:flags=lanczos,crop={OW}:{OH},"
      f"format=rgba,fade=t=in:st=0:d={fade}:alpha=1,fade=t=out:st={dur-fade:.3f}:d={fade}:alpha=1")
subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', clip, '-an', '-vf', vf, '-t', f'{dur:.3f}',
                os.path.join(out, 'l%04d.png')], check=True)
# image2 numera a partir de 1; o leitor espera l0000
fs = sorted(os.listdir(out))
for i, f in enumerate(fs): os.rename(os.path.join(out, f), os.path.join(out, f'tmp{i:04d}.png'))
for i in range(len(fs)): os.rename(os.path.join(out, f'tmp{i:04d}.png'), os.path.join(out, f'l{i:04d}.png'))
print('ok', len(fs), 'quadros')
