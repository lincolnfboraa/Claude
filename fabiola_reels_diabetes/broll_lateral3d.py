#!/usr/bin/env python3
"""Objetos 3D recortados (olho e rim) entrando pelas laterais e flutuando ao lado da Dra. Fabiola, fundo transparente.
Inspirado nos reels com objetos recortados que saem da borda da tela.
Uso: python3 broll_lateral3d.py <pasta_saida> <altura> <t_olho_entra> <t_rim_entra> <t_sai>"""
import sys, os, math
from PIL import Image, ImageFilter

out, OH = sys.argv[1], int(sys.argv[2])
t_olho, t_rim, t_sai = map(float, sys.argv[3:6])
OW = OH * 9 // 16; k = OW / 1080
here = os.path.dirname(os.path.abspath(__file__))
FPS = 30; DUR = t_sai + 0.1

def prepara(arq, largura):
    im = Image.open(os.path.join(here, 'broll', arq)).convert('RGBA')
    h = int(im.height * largura / im.width)
    im = im.resize((int(largura), h), Image.LANCZOS)
    # sombra suave deslocada
    pad = int(largura * 0.12)
    base = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    a = im.getchannel('A').point(lambda v: int(v * 0.55))
    sh.paste(Image.new('RGBA', im.size, (0, 0, 0, 255)), (pad + int(largura * 0.03), pad + int(largura * 0.05)), a)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(largura * 0.04)))
    base.alpha_composite(im, (pad, pad))
    return base
OLHO = prepara('olho_3d_recorte.png', 390 * k)
RIM = prepara('rim_3d_recorte.png', 320 * k)

def ease_out(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3
def ease_in(x): x = max(0.0, min(1.0, x)); return x ** 3

os.makedirs(out, exist_ok=True)
#           imagem  entra  centro final (x, y)      vem de      giro inicial  fase
OBJ = [(OLHO, t_olho, (118 * k, 450 * k), -1, -14, 0.0),
       (RIM, t_rim, (985 * k, 500 * k), +1, 12, 1.9)]
for i in range(int(DUR * FPS)):
    t = i / FPS
    fr = Image.new('RGBA', (OW, OH), (0, 0, 0, 0))
    for img, t0, (cx, cy), lado, giro, fase in OBJ:
        if t < t0: continue
        p = ease_out((t - t0) / 0.7)                    # desliza da borda e assenta
        q = ease_in((t - (t_sai - 0.5)) / 0.5)          # sai pela mesma borda
        x = cx + lado * (1 - p) * 520 * k + lado * q * 560 * k
        boia = math.sin((t - t0) * 1.8 + fase) * 9 * k
        rot = giro * (1 - p) + math.sin((t - t0) * 1.1 + fase) * 2.0
        alfa = min(1.0, (t - t0) / 0.25) * (1 - q)
        if alfa <= 0: continue
        im = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alfa < 1: im.putalpha(im.getchannel('A').point(lambda v: int(v * alfa)))
        fr.paste(im, (int(x - im.width / 2), int(cy - im.height / 2 + boia)), im)   # paste aceita coordenada negativa (objeto saindo da borda)
    fr.save(os.path.join(out, f'l{i:04d}.png'))
print('ok', out, int(DUR * FPS), 'quadros')
