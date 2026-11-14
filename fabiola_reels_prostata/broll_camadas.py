#!/usr/bin/env python3
"""Camadas animadas do vídeo de próstata (sequências PNG RGBA, SDR) para aplicar sobre o HDR com render_hdr_texto.py:
  lateral/: próstata normal entrando pela esquerda e trocando suavemente para a aumentada ("ela vai crescendo")
  split/:   painel da tela dividida (metade de cima) com o trato urinário obstruído
Uso: python3 broll_camadas.py <pasta_saida> <altura> <t_entra> <t_troca> <t_sai> <dur_split>  (tempos da lateral relativos ao início dela)"""
import sys, os, math
from PIL import Image, ImageFilter, ImageDraw

out, OH = sys.argv[1], int(sys.argv[2]); t_in, t_tr, t_out, d_split = map(float, sys.argv[3:7])
OW = OH * 9 // 16; k = OW / 1080; FPS = 30000 / 1001
here = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(here, 'broll')

def com_sombra(im, larg):
    h = int(im.height * larg / im.width); im = im.resize((int(larg), h), Image.LANCZOS)
    pad = int(larg * 0.12); base = Image.new('RGBA', (im.width + 2*pad, im.height + 2*pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', im.size, (0, 0, 0, 255)), (pad + int(larg*0.03), pad + int(larg*0.05)), im.getchannel('A').point(lambda v: int(v*0.55)))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(larg*0.04))); base.alpha_composite(im, (pad, pad)); return base
N = com_sombra(Image.open(os.path.join(B, 'prostata_normal_recorte.png')).convert('RGBA'), 360*k)
A = com_sombra(Image.open(os.path.join(B, 'prostata_aumentada_recorte.png')).convert('RGBA'), 330*k)
def eo(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x)**3
def ei(x): x = max(0.0, min(1.0, x)); return x**3

# ---- lateral ----
d = os.path.join(out, 'lateral'); os.makedirs(d, exist_ok=True)
for i in range(int((t_out + 0.1) * FPS)):
    t = i / FPS; fr = Image.new('RGBA', (OW, OH), (0, 0, 0, 0))
    if t >= t_in:
        p = eo((t - t_in) / 0.7); q = ei((t - (t_out - 0.5)) / 0.5)
        cx, cy = 150*k - (1 - p)*520*k - q*560*k, 560*k + math.sin((t - t_in)*1.8)*9*k
        rot = -14*(1 - p) + math.sin((t - t_in)*1.1)*2.0
        mix = max(0.0, min(1.0, (t - t_tr) / 0.6))           # troca normal -> aumentada
        for img, al in ((N, 1 - mix), (A, mix)):
            al *= min(1.0, (t - t_in) / 0.25) * (1 - q)
            if al <= 0.01: continue
            im = img.rotate(rot, resample=Image.BICUBIC, expand=True)
            im.putalpha(im.getchannel('A').point(lambda v: int(v * al)))
            fr.paste(im, (int(cx - im.width/2), int(cy - im.height/2)), im)
    fr.save(os.path.join(d, f'l{i:04d}.png'))

# ---- tela dividida: painel de cima ----
d = os.path.join(out, 'split'); os.makedirs(d, exist_ok=True)
T = Image.open(os.path.join(B, 'trato_urinario_obstrucao.png')).convert('RGB')
PH = int(OH * 0.48)                                            # altura do painel
for i in range(int(d_split * FPS)):
    t = i / FPS
    z = 1.0 + 0.07 * (t / d_split)                             # zoom lento
    sw = T.width / z; sh_ = sw * PH / OW
    if sh_ > T.height: sh_ = T.height; sw = sh_ * OW / PH
    x0 = (T.width - sw) / 2; y0 = (T.height - sh_) * 0.45
    painel = T.resize((OW, PH), Image.LANCZOS, box=(x0, y0, x0 + sw, y0 + sh_)).convert('RGBA')
    ImageDraw.Draw(painel).rectangle((0, PH - max(2, int(5*k)), OW, PH), fill=(143, 176, 216, 255))   # filete azul da paleta
    ent = eo(t / 0.4); sai = ei((t - (d_split - 0.4)) / 0.4)
    y = int(-PH + PH * ent - PH * sai)
    fr = Image.new('RGBA', (OW, OH), (0, 0, 0, 0)); fr.paste(painel, (0, y))
    fr.save(os.path.join(d, f'l{i:04d}.png'))
print('ok')
