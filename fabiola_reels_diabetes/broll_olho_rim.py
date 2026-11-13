#!/usr/bin/env python3
"""B-roll animado 'olho -> rim: os mesmos microvasos' no estilo da marca (traço fino creme sobre marinho).
Uso: python3 broll_olho_rim.py <saida.mov> [altura=1920]
Gera ~4,5 s a 30 fps, desenhado quadro a quadro (PIL com superamostragem), sem imagens de banco."""
import sys, os, math, random, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
OH = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
OW = OH * 9 // 16
SS = 2                                   # superamostragem para traço suave
W, H = OW * SS, OH * SS
k = W / 1080                             # escala em relação ao layout de 1080x1920
FPS, DUR = 30, 5.3
NAVY, NAVY2 = (15, 28, 74), (22, 40, 98)
CREME, BRANCO = (200, 185, 167), (245, 242, 236)
here = os.path.dirname(os.path.abspath(__file__))
F_SERIF = ImageFont.truetype(os.path.join(here, 'fonts', 'Merriweather-BlackItalic.ttf'), int(118 * k))
F_LAB = ImageFont.truetype(os.path.join(here, 'fonts', 'Poppins-Medium.ttf'), int(40 * k))
F_SUB = ImageFont.truetype(os.path.join(here, 'fonts', 'Poppins-SemiBold.ttf'), int(64 * k))

def ease(x):  # ease-in-out
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def seg(t, a, b): return ease((t - a) / (b - a))
def mix(c1, c2, a): return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))

# ---- árvore de vasos da retina (gerada uma vez, revelada aos poucos) ----
rnd = random.Random(11)
VASOS = []   # (x1,y1,x2,y2,larg,ordem 0..1) em coordenadas relativas ao centro do círculo, raio 1
def galho(x, y, ang, comp, larg, prof, ordem):
    if prof == 0 or comp < 0.04: return
    passos = 4
    for i in range(passos):
        ang += rnd.uniform(-0.25, 0.25)
        nx, ny = x + math.cos(ang) * comp / passos, y + math.sin(ang) * comp / passos
        if nx * nx + ny * ny > 0.93: return
        VASOS.append((x, y, nx, ny, larg, ordem + i / passos * 0.25))
        x, y = nx, ny
    for d in (-1, 1):
        galho(x, y, ang + d * rnd.uniform(0.35, 0.8), comp * 0.72, larg * 0.7, prof - 1, ordem + 0.25)
DISCO = (-0.38, 0.05)
for a in (-1.1, -0.45, 0.35, 1.05, 2.4, 3.6):
    galho(DISCO[0], DISCO[1], a, 0.62, 5.0, 4, 0.0)
mx = max(v[5] for v in VASOS)
VASOS = [(a, b, c, d, e, f / mx) for a, b, c, d, e, f in VASOS]

# ---- glomérulo (novelo de capilares) ----
rnd2 = random.Random(5)
GLOM = []
for j in range(14):   # alças
    cx, cy, r = rnd2.uniform(-0.22, 0.22), rnd2.uniform(-0.22, 0.22), rnd2.uniform(0.3, 0.5)
    a0 = rnd2.uniform(0, 6.28)
    pts = [(cx + r * math.cos(a0 + t / 40 * 6.0) * (0.6 + 0.4 * math.sin(t / 6)),
            cy + r * math.sin(a0 + t / 40 * 6.0) * (0.6 + 0.4 * math.cos(t / 7))) for t in range(41)]
    GLOM.append((pts, j / 14))

def circulo_vasos(dr, cx, cy, R, prog, tipo, alpha_bg=1.0):
    dr.ellipse((cx - R, cy - R, cx + R, cy + R), fill=mix(NAVY, NAVY2, alpha_bg), outline=CREME, width=max(2, int(3 * k * SS / 2)))
    if tipo == 'olho':
        # disco óptico e mácula
        d = DISCO
        rr = R * 0.09
        dr.ellipse((cx + d[0] * R - rr, cy + d[1] * R - rr, cx + d[0] * R + rr, cy + d[1] * R + rr), outline=CREME, width=max(2, int(3 * k)))
        rm = R * 0.06
        dr.ellipse((cx + 0.35 * R - rm, cy - rm, cx + 0.35 * R + rm, cy + rm), fill=mix(NAVY2, CREME, 0.25))
        for x1, y1, x2, y2, lg, o in VASOS:
            if o <= prog:
                dr.line((cx + x1 * R, cy + y1 * R, cx + x2 * R, cy + y2 * R), fill=CREME, width=max(2, int(lg * k * 1.1)))
    else:
        # arteríola que entra e sai + novelo de alças
        dr.line((cx - R * 0.95, cy - R * 0.55, cx - R * 0.25, cy - R * 0.12), fill=CREME, width=max(2, int(5 * k)))
        dr.line((cx - R * 0.95, cy - R * 0.32, cx - R * 0.25, cy + 0.02 * R), fill=CREME, width=max(2, int(4 * k)))
        for pts, o in GLOM:
            if o <= prog:
                n = max(2, int(len(pts) * min(1, (prog - o) * 4)))
                dr.line([(cx + x * R, cy + y * R) for x, y in pts[:n]], fill=CREME, width=max(2, int(4 * k)), joint='curve')

def texto(dr, txt, fonte, cx, y, cor, alpha=1.0, espac=0):
    if alpha <= 0: return
    cor = mix(NAVY, cor, alpha)
    if espac:
        w = sum(dr.textlength(c, font=fonte) for c in txt) + espac * (len(txt) - 1)
        x = cx - w / 2
        for c in txt:
            dr.text((x, y), c, font=fonte, fill=cor); x += dr.textlength(c, font=fonte) + espac
    else:
        w = dr.textlength(txt, font=fonte); dr.text((cx - w / 2, y), txt, font=fonte, fill=cor)

def quadro(t):
    im = Image.new('RGB', (W, H), NAVY); dr = ImageDraw.Draw(im)
    cx, cy = W / 2, H * 0.46
    # 1) olho em traço (0 a 0,9 s), some no zoom
    a_olho = seg(t, 0.0, 0.5) * (1 - seg(t, 1.0, 1.4))
    if a_olho > 0:
        ew, eh = 380 * k, 170 * k
        cor = mix(NAVY, CREME, a_olho); lw = max(2, int(4 * k))
        pr = seg(t, 0.0, 0.8)
        n = int(60 * pr)
        topo = [(cx - ew + 2 * ew * i / 60, cy - eh * math.sin(math.pi * i / 60)) for i in range(n + 1)]
        base = [(cx - ew + 2 * ew * i / 60, cy + eh * math.sin(math.pi * i / 60)) for i in range(n + 1)]
        if n > 1: dr.line(topo, fill=cor, width=lw); dr.line(base, fill=cor, width=lw)
        ri = eh * 0.95 * seg(t, 0.35, 0.8)
        dr.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), outline=cor, width=lw)
        rp = ri * 0.42
        dr.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=cor)
        texto(dr, 'FUNDO DO OLHO', F_LAB, cx, cy + eh + 60 * k, CREME, seg(t, 0.4, 0.8) * (1 - seg(t, 1.0, 1.3)), espac=10 * k)
    # 2) zoom: a pupila vira o círculo do fundo do olho (0,9 a 1,5 s)
    R_final = 330 * k
    z = seg(t, 0.9, 1.5)
    # 3) círculo vai para cima/esquerda e o do rim aparece (2,6 a 3,3 s)
    s = seg(t, 2.6, 3.3)
    if t >= 0.9:
        R = (40 * k + (R_final - 40 * k) * z) * (1 - 0.45 * s)
        ox = cx - (W * 0.25) * s; oy = cy - 120 * k * s
        circulo_vasos(dr, ox, oy, R, seg(t, 1.3, 2.6), 'olho')
        texto(dr, 'olho', F_SUB, ox, oy + R + 24 * k, BRANCO, s)
    if t >= 2.6:
        R2 = R_final * 0.55 * seg(t, 2.7, 3.2)
        ox2 = cx + (W * 0.25); oy2 = cy - 120 * k
        if R2 > 2:
            circulo_vasos(dr, ox2, oy2, R2, seg(t, 2.8, 3.6), 'rim')
        texto(dr, 'rim', F_SUB, ox2, oy2 + R_final * 0.55 + 24 * k, BRANCO, seg(t, 3.0, 3.4))
        # sinal de "igual" entre os dois
        a = seg(t, 3.2, 3.5)
        if a > 0:
            c = mix(NAVY, CREME, a); y0 = oy2 - 14 * k
            dr.line((cx - 34 * k, y0, cx + 34 * k, y0), fill=c, width=max(2, int(6 * k)))
            dr.line((cx - 34 * k, y0 + 28 * k, cx + 34 * k, y0 + 28 * k), fill=c, width=max(2, int(6 * k)))
    # 4) frase final (3,4 s em diante)
    a = seg(t, 3.4, 3.9)
    if a > 0:
        texto(dr, 'os mesmos', F_SUB, cx, H * 0.66, BRANCO, a)
        texto(dr, 'microvasos', F_SERIF, cx, H * 0.66 + 80 * k, CREME, a)
    return im.resize((OW, OH), Image.LANCZOS)

tmp = tempfile.mkdtemp(prefix='broll_')
n = int(DUR * FPS)
for i in range(n):
    quadro(i / FPS).save(os.path.join(tmp, f'f{i:04d}.png'))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f%04d.png'),
                '-c:v', 'libx264', '-crf', '14' if OH > 854 else '24', '-pix_fmt', 'yuv420p', '-r', str(FPS), out], check=True)
print('ok', out, n, 'quadros')
