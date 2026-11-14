#!/usr/bin/env python3
"""Animação programada (sem IA): corte da próstata com a uretra no meio; a glândula cresce, as paredes comprimem
o canal e o fluxo de urina diminui até virar gotas. Saída: MP4 (SDR) para entrar como B-roll.
Uso: python3 anim_uretra.py <saida.mp4> [largura=720] [dur=8]"""
import sys, os, math, subprocess
import numpy as np
from PIL import Image, ImageFilter

out = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 720
DUR = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
H = W * 16 // 9; FPS = 30
k = W / 720
rng = np.random.default_rng(3)

def ease(x): x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)
def fbm(h, w, oct=5, seed=1):
    r = np.random.default_rng(seed); acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(oct):
        s = 2 ** (o + 2)
        g = r.random((h // s + 2, w // s + 2)).astype(np.float32)
        g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        acc += g * amp; tot += amp; amp *= 0.55
    return acc / tot

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
cx, cy = W / 2, H * 0.56
TEX = fbm(H, W, 6, 7)                       # textura fibrosa do tecido
FIB = fbm(H, W, 4, 11)
# fundo marinho com vinheta
bg = np.zeros((H, W, 3), np.float32)
vig = 1 - 0.55 * np.clip(np.hypot((xx - W/2) / W, (yy - H/2) / H) * 1.6, 0, 1)
for i, c in enumerate((11, 20, 52)): bg[..., i] = c / 255 * vig

def glandula(s):
    """máscara suave da próstata (formato de castanha) com escala s"""
    nx = (xx - cx) / (250 * k * s); ny = (yy - cy) / (300 * k * s)
    ny2 = ny + 0.18 * nx ** 2                    # leve formato de coração/castanha
    d = np.sqrt(nx ** 2 + (ny2 * (1.05 - 0.12 * np.sign(ny2))) ** 2)
    return np.clip((1 - d) / 0.04, 0, 1), d

part_y = rng.random(400) * H; part_x = rng.normal(0, 0.28, 400); part_r = rng.uniform(1.2, 3.2, 400) * k
proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                         '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
N = int(DUR * FPS)
for f in range(N):
    t = f / FPS
    g = ease((t - 1.6) / (DUR - 3.2))           # 0 = normal, 1 = aumentada e canal quase fechado
    s = 1.0 + 0.16 * g
    m, d = glandula(s)
    # canal: meia-largura que encolhe, com as paredes empurradas para dentro no meio (onde a glândula é mais grossa)
    w0 = 46 * k
    prof = np.exp(-((yy - cy) / (250 * k * s)) ** 4)          # aperto só dentro da glândula, máximo no meio
    meia = np.maximum(w0 * (1 - 0.93 * g * prof), 2.5 * k)
    dx = np.abs(xx - cx)
    parede = np.clip((dx - meia) / (16 * k), 0, 1)        # 0 dentro do canal, 1 no tecido
    # tecido: cor rosada com textura, sombreamento pela borda da glândula e escurecimento perto do canal
    sombra = np.clip(1 - d, 0, 1) ** 0.45
    perto = np.exp(-np.maximum(dx - meia, 0) / (40 * k))
    base_c = np.array([0.72, 0.30, 0.28], np.float32)
    tec = base_c[None, None, :] * (0.55 + 0.45 * TEX[..., None]) * (0.55 + 0.45 * sombra[..., None])
    tec += np.array([0.12, 0.05, 0.05]) * (FIB[..., None] - 0.5)
    tec *= (1 - 0.35 * perto[..., None] * g)               # tecido "apertando" fica mais escuro perto do canal
    # brilho de borda e luz de cima à esquerda
    luz = np.clip(((cx - xx) * 0.6 + (cy - yy)) / (420 * k), -1, 1)
    tec *= (0.85 + 0.25 * luz[..., None])
    # parede interna da uretra (mucosa clara e brilhante)
    mucosa = np.exp(-np.abs(dx - meia) / (7 * k))[..., None] * np.array([0.95, 0.62, 0.60])
    img = bg.copy()
    tubo = np.clip(1 - np.abs((yy - cy) / (H * 0.62)), 0, 1)             # uretra continua acima e abaixo da glândula
    canal_m = (dx < meia + 16 * k) * (tubo > 0)
    tec_m = m[..., None] * parede[..., None]
    img = img * (1 - tec_m) + tec * tec_m
    img = img + mucosa * 0.6 * (m[..., None] + (1 - m[..., None]) * canal_m[..., None] * 0.6) * (dx < meia + 22 * k)[..., None]
    # parede externa da uretra fora da glândula
    fora = (1 - m) * (np.abs(dx - meia - 8 * k) < 8 * k) * (tubo > 0.02)
    img = img * (1 - fora[..., None] * 0.8) + fora[..., None] * 0.8 * np.array([0.78, 0.42, 0.40])
    # urina: faixa amarela translúcida + partículas descendo, velocidade proporcional à abertura
    dentro = (dx < meia * 0.85) * (tubo > 0)
    fluxo = 0.62 * (1 - 0.55 * g * prof)
    cil = np.sqrt(np.clip(1 - (dx / np.maximum(meia * 0.85, 1)) ** 2, 0, 1))      # volume do tubo (cilindro)
    uri = np.array([0.96, 0.80, 0.34])[None, None, :] * (0.55 + 0.45 * cil[..., None]) + 0.25 * (cil[..., None] ** 8)
    a_ = (dentro * fluxo)[..., None]
    img = img * (1 - a_) + uri * a_
    # paredes abaulando: sombra na borda interna do tecido onde o canal estrangula
    borda = np.exp(-np.abs(dx - meia) / (22 * k)) * prof * g * m
    img *= (1 - 0.35 * borda[..., None])
    vel = (900 * k) * (1 - 0.93 * g)
    part_y = (part_y + vel / FPS) % H
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    px = pil.load()
    meia_c = meia[:, int(cx)]
    for i in range(len(part_y)):
        py = int(part_y[i])
        if g > 0.75 and (i % 4): continue                     # canal quase fechado: só gotas
        x = int(cx + part_x[i] * meia_c[min(py, H - 1)])
        r = int(part_r[i])
        for yy2 in range(max(0, py - r * (3 if g < 0.6 else 1)), min(H, py + r)):
            for xx2 in range(max(0, x - r), min(W, x + r)):
                c = px[xx2, yy2]; px[xx2, yy2] = (min(255, c[0] + 40), min(255, c[1] + 34), min(255, c[2] + 6))
    pil = pil.filter(ImageFilter.GaussianBlur(0.6 * k))
    proc.stdin.write(pil.tobytes())
proc.stdin.close(); proc.wait(); print('ok', out)
