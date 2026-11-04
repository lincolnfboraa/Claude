# Verificação pós-render: classifica cada frame pela cor da tela do celular e compara com timeline.
# NOTIF = tela navy | CATALOGO = tela bege | MISTO = as duas (só permitido na TRANSIÇÃO)
import sys, glob, subprocess, tempfile, os
import numpy as np
from PIL import Image
video = sys.argv[1]
tmp = tempfile.mkdtemp()
subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', 'crop=560:1100:260:720,scale=56:110', f'{tmp}/f%03d.png'], check=True)
phase = lambda f: 'PROBLEMA' if f < 60 else ('TRANSICAO' if f < 120 else 'SOLUCAO')
allowed = {'PROBLEMA': {'NOTIF'}, 'TRANSICAO': {'NOTIF', 'MISTO', 'CATALOGO'}, 'SOLUCAO': {'CATALOGO'}}
seq, errs = [], []
for i, p in enumerate(sorted(glob.glob(f'{tmp}/f*.png'))):
    light = (np.asarray(Image.open(p).convert('L'), dtype=float) > 170).mean()
    st = 'CATALOGO' if light > 0.75 else ('NOTIF' if light < 0.45 else 'MISTO')
    seq.append(st)
    if st not in allowed[phase(i)]: errs.append(f'frame {i} ({phase(i)}): {st}')
runs, s = [], 0
for i in range(1, len(seq) + 1):
    if i == len(seq) or seq[i] != seq[s]: runs.append(f'{seq[s]} {s}-{i-1}'); s = i
print('render:', ' | '.join(runs))
back = [i for i in range(1, len(seq)) if seq[i] == 'NOTIF' and 'CATALOGO' in seq[:i]]
if back: errs.append(f'notificação voltou depois do catálogo nos frames {back[:5]}...')
print('FALHOU:\n' + '\n'.join(errs) if errs else 'render OK: estados só aparecem nos intervalos permitidos')
sys.exit(1 if errs else 0)
