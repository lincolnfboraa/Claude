"""Cartão de identificação sobre o vídeo (lower third) em 9:16, feito da própria arte do cartão azul do cliente (logo, nome, CRM/RQE, redes).

Medidas (1080x1920): largura 980 (laterais 50), proporção 3:1 da arte (altura ~322), base em y 1440, acima da zona do Reels (y 1470 em diante).
Cada peça é recortada da arte (máscara pela luminância, na cor creme dela), então textos e números saem idênticos ao original.
Anima: cartão sobe com fade, logo se revela, nome e cargo sobem, linha vertical cresce, redes entram em cascata, segura, e sai descendo.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE_Y, LARG = 1440, 980
CAIXAS = {'logo': (330, 45, 715, 365), 'nome': (110, 365, 900, 460), 'cargo': (270, 470, 750, 530), 'crm': (225, 538, 790, 598),
          'ig_i': (1025, 90, 1165, 225), 'ig_t': (1185, 100, 1940, 210), 'fb_i': (1045, 260, 1130, 392), 'fb_t': (1185, 280, 1890, 370),
          'tt_i': (1030, 430, 1155, 570), 'tt_t': (1185, 450, 1830, 545)}
CARTAO = (8, 8, 1992, 659)                    # retângulo do cartão na arte (2000x667)
LINHA = (951, 66, 956, 606)                   # divisória vertical na arte

def _facil(p): p = min(max(p, 0.0), 1.0); return 1 - (1 - p) ** 3
def _volta(p):
    p = min(max(p, 0.0), 1.0); c = 1.70158; return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2
def _prog(t, ini, dur): return (t - ini) / dur

class Faixa:
    def __init__(self, arte, OW, OH, dur_s=5.0):
        self.OW, self.OH, self.dur = OW, OH, dur_s; s = self.s = OW / 1080.0
        im = Image.open(arte).convert('RGBA'); im = Image.alpha_composite(Image.new('RGBA', im.size, (14, 31, 71, 255)), im).convert('RGB').resize((2000, 667), Image.LANCZOS)
        a = np.asarray(im, np.float32); lum = a @ np.array([.299, .587, .114], np.float32)
        self.fundo = np.median(a[200:230, 20:120].reshape(-1, 3), axis=0) / 255
        self.creme = np.median(a[lum > np.percentile(lum, 99.5)], axis=0) / 255
        lf, lc = float(lum[200:230, 20:120].mean()), float(np.median(lum[lum > np.percentile(lum, 99.5)]))
        k = LARG * s / (CARTAO[2] - CARTAO[0]); self.k = k
        self.mx = round(40 * s); self.cw, self.ch = round(LARG * s), round((CARTAO[3] - CARTAO[1]) * k)
        self.rw, self.rh = self.cw + 2 * self.mx, self.ch + 2 * self.mx
        self.x0, self.y0 = (OW - self.rw) // 2, round(BASE_Y * s) - self.ch - self.mx
        raio = round(36 * s)
        c = Image.new('L', (self.rw * 2, self.rh * 2), 0); ImageDraw.Draw(c).rounded_rectangle((self.mx * 2, self.mx * 2, (self.mx + self.cw) * 2, (self.mx + self.ch) * 2), radius=raio * 2, fill=255)
        self.cartao = np.asarray(c.resize((self.rw, self.rh), Image.LANCZOS), np.float32) / 255
        sh = Image.new('L', (self.rw, self.rh), 0); ImageDraw.Draw(sh).rounded_rectangle((self.mx, self.mx + round(10 * s), self.mx + self.cw, self.mx + self.ch + round(10 * s)), radius=raio, fill=255)
        self.sombra = np.asarray(sh.filter(ImageFilter.GaussianBlur(round(14 * s))), np.float32) / 255 * 0.45
        self.p = {}                                                              # peça -> (máscara float, x, y) no espaço da região do cartão
        for n, (x0, y0, x1, y1) in CAIXAS.items():
            m = np.clip((lum[y0:y1, x0:x1] - lf) / (lc - lf), 0, 1); m = np.clip((m - 0.1) / 0.9, 0, 1); ys, xs = np.where(m > .1)
            if not len(ys): continue
            m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]; ox, oy = x0 + xs.min(), y0 + ys.min()
            w, h = max(1, round(m.shape[1] * k)), max(1, round(m.shape[0] * k))
            r = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS), np.float32) / 255
            self.p[n] = (r, self.mx + round((ox - CARTAO[0]) * k), self.mx + round((oy - CARTAO[1]) * k))
        self.linha = (self.mx + round((LINHA[0] - CARTAO[0]) * k), self.mx + round((LINHA[1] - CARTAO[1]) * k), max(2, round(3 * s)), round((LINHA[3] - LINHA[1]) * k))

    def _pintar(self, pre, n, alfa=1.0, dx=0, dy=0, esc=1.0, corte=None):
        m, x, y = self.p[n]
        if esc != 1.0:
            w, h = max(1, round(m.shape[1] * esc)), max(1, round(m.shape[0] * esc))
            x += (m.shape[1] - w) // 2; y += (m.shape[0] - h) // 2
            m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32) / 255
        self._cola(pre, m, x + dx, y + dy, alfa, corte)

    def _cola(self, pre, m, x, y, alfa=1.0, corte=None):
        h, w = m.shape
        if corte is not None:
            suave = max(8, w // 6); m = m * np.clip(1 - (np.arange(w) - corte * (w + suave)) / suave, 0, 1)[None, :]
        H, W = pre.shape[:2]; xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if xb <= xa or yb <= ya: return
        mm = (m[ya - y:yb - y, xa - x:xb - x] * alfa)[..., None]
        pre[ya:yb, xa:xb, :3] = pre[ya:yb, xa:xb, :3] * (1 - mm) + self.creme * mm

    def regiao(self, t):
        s = self.s
        pre = np.zeros((self.rh, self.rw, 3), np.float32); pre[:] = self.fundo
        self._pintar(pre, 'logo', esc=0.9 + 0.1 * _facil(_prog(t, 0.3, 0.9)), corte=_facil(_prog(t, 0.3, 0.9)))
        for n, ini in (('nome', 0.75), ('cargo', 0.9), ('crm', 1.05)):
            e = _facil(_prog(t, ini, 0.5)); self._pintar(pre, n, e, dy=round((1 - e) * 18 * s))
        e = _facil(_prog(t, 0.6, 0.5)); lx, ly, lw, lh = self.linha; h = round(lh * e)
        if h > 1: self._cola(pre, np.full((h, lw), 0.85, np.float32), lx, ly + (lh - h) // 2)
        for n, ini in (('ig', 1.0), ('fb', 1.22), ('tt', 1.44)):
            pi = _prog(t, ini, 0.45); self._pintar(pre, n + '_i', min(1.0, max(0.0, pi * 3)), esc=max(0.05, 0.55 + 0.45 * _volta(pi)))
            et = _facil(_prog(t, ini + 0.1, 0.5)); self._pintar(pre, n + '_t', et, dx=round((1 - et) * -60 * s))
        c = self.cartao; A = c + self.sombra * (1 - c)
        return pre * c[..., None], A

    def quadro(self, t):
        """Camada RGBA premultiplicada (altura OH, largura OW) no instante t, com entrada e saída."""
        s, D = self.s, self.dur
        ent = _facil(_prog(t, 0.0, 0.45)); sai = _facil(_prog(t, D - 0.4, 0.4)); vis = ent * (1 - sai)
        ya = self.y0 + round((1 - ent) * 70 * s + sai * 40 * s)
        pre, A = self.regiao(t); cam = np.zeros((self.OH, self.OW, 4), np.float32)
        ys0, ye0 = max(0, ya), min(self.OH, ya + self.rh)
        if ye0 > ys0:
            f = slice(ys0 - ya, ye0 - ya); cam[ys0:ye0, self.x0:self.x0 + self.rw, :3] = pre[f] * vis; cam[ys0:ye0, self.x0:self.x0 + self.rw, 3] = A[f] * vis
        return cam

def sobre(fundo, cam):
    """Compõe a camada premultiplicada sobre o fundo RGB (float 0 a 1)."""
    return fundo * (1 - cam[..., 3:4]) + cam[..., :3]
