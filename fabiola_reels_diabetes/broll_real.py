#!/usr/bin/env python3
"""B-roll realista 'olho -> rim: os mesmos microvasos' a partir das ilustrações geradas no Figma (pasta broll/).
Movimento de câmera (zoom/pan com ease) + transição + textos no padrão da marca.
Uso: python3 broll_real.py <saida.mp4> [altura=1920]"""
import sys, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

out = sys.argv[1]
OH = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
OW = OH * 9 // 16
k = OW / 1080
here = os.path.dirname(os.path.abspath(__file__))
OLHO = Image.open(os.path.join(here, 'broll', 'olho_retina.png')).convert('RGB')
RIM = Image.open(os.path.join(here, 'broll', 'rim_glomerulo.png')).convert('RGB')
FPS, DUR = 30, 5.6
CREME, BRANCO = (200, 185, 167), (255, 255, 255)
F_LAB = ImageFont.truetype(os.path.join(here, 'fonts', 'Poppins-Medium.ttf'), int(46 * k))
F_SUB = ImageFont.truetype(os.path.join(here, 'fonts', 'Poppins-SemiBold.ttf'), int(70 * k))
F_SERIF = ImageFont.truetype(os.path.join(here, 'fonts', 'Merriweather-BlackItalic.ttf'), int(118 * k))
F_TAG = ImageFont.truetype(os.path.join(here, 'fonts', 'Poppins-Medium.ttf'), int(26 * k))

def ease(x): x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def seg(t, a, b): return ease((t - a) / (b - a))
def lerp(a, b, p): return a + (b - a) * p

def camera(img, cx, cy, zoom):
    """recorta a imagem com centro (cx,cy) normalizado e zoom (1 = imagem inteira) e escala para OWxOH"""
    w, h = img.size
    cw, ch = w / zoom, h / zoom
    x0 = min(max(cx * w - cw / 2, 0), w - cw); y0 = min(max(cy * h - ch / 2, 0), h - ch)
    return img.resize((OW, OH), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))

def texto(im, txt, fonte, y, cor, alpha, espac=0):
    if alpha <= 0: return im
    camada = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(camada)
    larg = sum(d.textlength(c, font=fonte) for c in txt) + espac * (len(txt) - 1)
    x = (im.size[0] - larg) / 2
    sombra = Image.new('RGBA', im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sombra)
    xx = x
    for c in txt:
        ds.text((xx + 3 * k, y + 5 * k), c, font=fonte, fill=(0, 0, 0, int(170 * alpha)))
        d.text((xx, y), c, font=fonte, fill=cor + (int(255 * alpha),)); xx += d.textlength(c, font=fonte) + espac
    sombra = sombra.filter(ImageFilter.GaussianBlur(7 * k))
    im = Image.alpha_composite(im.convert('RGBA'), sombra)
    return Image.alpha_composite(im, camada).convert('RGB')

def quadro(t):
    # olho: começa no olho e desce pelo cone até a retina (0 a 2,9 s)
    p = seg(t, 0.2, 2.9)
    a = camera(OLHO, 0.5, lerp(0.24, 0.685, p), lerp(1.55, 1.45, p))
    # rim: começa dentro do glomérulo e se afasta até revelar o rim (2,6 a 5,6 s)
    if t >= 2.6:
        q = seg(t, 2.8, 5.4)
        b = camera(RIM, 0.5, lerp(0.70, 0.50, q), lerp(1.5, 1.0, q))
        im = Image.blend(a, b, seg(t, 2.6, 3.1))
    else:
        im = a
    a = seg(t, 3.7, 4.2)
    if a > 0:   # degradê escuro no topo para a frase final
        g = Image.new('L', (1, OH)); gp = g.load()
        for y in range(OH): gp[0, y] = int(205 * a * max(0, 1 - y / (OH * 0.36)) ** 1.4)
        im = Image.composite(Image.new('RGB', (OW, OH), (8, 12, 30)), im, g.resize((OW, OH)))
    im = texto(im, 'os mesmos', F_SUB, 150 * k, BRANCO, seg(t, 3.8, 4.3))
    im = texto(im, 'microvasos', F_SERIF, 232 * k, CREME, seg(t, 3.9, 4.4))
    im = texto(im, 'ilustração', F_TAG, OH - 300 * k, (230, 230, 230), 0.8)
    return im

tmp = tempfile.mkdtemp(prefix='brollreal_')
n = int(DUR * FPS)
for i in range(n):
    quadro(i / FPS).save(os.path.join(tmp, f'f{i:04d}.png'))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f%04d.png'),
                '-c:v', 'libx264', '-crf', '14' if OH > 854 else '24', '-pix_fmt', 'yuv420p', '-r', str(FPS), out], check=True)
print('ok', out, n, 'quadros')
