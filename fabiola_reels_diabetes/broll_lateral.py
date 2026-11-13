#!/usr/bin/env python3
"""Imagens flutuando ao lado da Dra. Fabiola (fundo transparente), no estilo dos reels com objetos recortados.
Recorta os círculos das ilustrações (retina e glomérulo) e gera uma sequência PNG com alfa para sobrepor ao vídeo.
Uso: python3 broll_lateral.py <pasta_saida> <altura> <t_retina_entra> <t_rim_entra> <t_sai>  (tempos relativos ao início da sequência)"""
import sys, os, math
from PIL import Image, ImageDraw, ImageFilter

out, OH = sys.argv[1], int(sys.argv[2])
t_ret, t_rim, t_sai = map(float, sys.argv[3:6])
OW = OH * 9 // 16; k = OW / 1080
here = os.path.dirname(os.path.abspath(__file__))
FPS = 30; DUR = t_sai + 0.4
CREME = (200, 185, 167, 255)

def recorte(arq, cx, cy, r):
    im = Image.open(os.path.join(here, 'broll', arq)).convert('RGBA').crop((cx - r, cy - r, cx + r, cy + r))
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).ellipse((0, 0, 2 * r, 2 * r), fill=255)
    im.putalpha(m); return im
RET = recorte('olho_retina.png', 431, 986, 282)
GLO = recorte('rim_glomerulo.png', 421, 1016, 300)

def disco(src, d):
    """disco com borda creme fina e sombra suave, diâmetro d (px) + margem para a sombra"""
    pad = int(d * 0.18); S = d + 2 * pad
    base = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sh = Image.new('L', (S, S), 0); ImageDraw.Draw(sh).ellipse((pad, pad + d * 0.04, pad + d, pad + d * 1.04), fill=150)
    base.putalpha(sh.filter(ImageFilter.GaussianBlur(d * 0.05)))
    base = Image.composite(Image.new('RGBA', (S, S), (0, 0, 0, 255)), Image.new('RGBA', (S, S), (0, 0, 0, 0)), base.getchannel('A'))
    img = src.resize((d, d), Image.LANCZOS)
    base.alpha_composite(img, (pad, pad))
    ImageDraw.Draw(base).ellipse((pad, pad, pad + d, pad + d), outline=CREME, width=max(2, int(d * 0.012)))
    return base, pad

def ease_back(x):   # entrada com leve "passada" (pop)
    x = max(0.0, min(1.0, x)); c = 1.4
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

os.makedirs(out, exist_ok=True)
D = int(300 * k)
for i in range(int(DUR * FPS)):
    t = i / FPS
    fr = Image.new('RGBA', (OW, OH), (0, 0, 0, 0))
    for src, t0, cx, cy, fase in ((RET, t_ret, 162 * k, 470 * k, 0.0), (GLO, t_rim, 918 * k, 500 * k, 1.7)):
        if t < t0: continue
        p_in = ease_back((t - t0) / 0.45)
        p_out = max(0.0, min(1.0, (t - (t_sai - 0.35)) / 0.35))
        esc = max(0.01, p_in * (1 - 0.25 * p_out))
        alfa = min(1.0, (t - t0) / 0.2) * (1 - p_out)
        if alfa <= 0: continue
        d = max(2, int(D * esc))
        img, pad = disco(src, d)
        if alfa < 1:
            a = img.getchannel('A').point(lambda v: int(v * alfa)); img.putalpha(a)
        boia = math.sin((t - t0) * 2.2 + fase) * 10 * k            # flutuar suave
        rot = math.sin((t - t0) * 1.3 + fase) * 2.5
        img = img.rotate(rot, resample=Image.BICUBIC, expand=False)
        fr.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2 + boia)))
    fr.save(os.path.join(out, f'l{i:04d}.png'))
print('ok', out, int(DUR * FPS), 'quadros')
