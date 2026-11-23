"""Cartão final animado (logo, nome, CRM/RQE e redes) em 9:16, recomposto do cartão horizontal que o cliente anexa.

Cada elemento é recortado da própria arte (máscara pela luminância, repintada na cor creme da arte), então os textos e
números (CRM, RQE, @) saem idênticos ao original. Fundo liso na cor do cartão. Animação (2,8 s, depois segura):
logo se revela da esquerda pra direita, nome e cargo sobem, linha cresce do centro, redes entram em cascata (ícone pula, @ desliza).
Cartão que não é o desta arte (proporção diferente) entra inteiro, com fade e leve zoom, no mesmo fundo.
"""
import subprocess
import numpy as np
from PIL import Image

DUR_ANIMACAO = 2.8
# (nome, caixa na arte de 2000x667) das peças; ordem de empilhamento no 9:16
CAIXAS = {'logo': (330, 45, 715, 365), 'nome': (110, 365, 900, 460), 'cargo': (270, 470, 750, 530), 'crm': (225, 538, 790, 598),
          'ig_i': (1025, 90, 1165, 225), 'ig_t': (1185, 100, 1940, 210), 'fb_i': (1045, 260, 1130, 392), 'fb_t': (1185, 280, 1890, 370),
          'tt_i': (1030, 430, 1155, 570), 'tt_t': (1185, 450, 1830, 545)}

def _facil(p): p = min(max(p, 0.0), 1.0); return 1 - (1 - p) ** 3
def _volta(p):
    p = min(max(p, 0.0), 1.0); c = 1.70158; return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2
def _prog(t, ini, dur): return (t - ini) / dur

def _cores(im):
    a = np.asarray(im.convert('RGB'), np.float32)
    h, w = a.shape[:2]
    fundo = np.median(a[int(h * .30):int(h * .36), int(w * .02):int(w * .12)].reshape(-1, 3), axis=0)           # azul liso, à esquerda do logo
    lum = a @ np.array([.299, .587, .114], np.float32)
    claro = a[lum > np.percentile(lum, 99.5)]
    return fundo, np.median(claro, axis=0)

def _mascara(im, caixa, fundo, creme):
    x0, y0, x1, y1 = caixa; a = np.asarray(im.convert('RGB').crop(caixa), np.float32)
    lum = a @ np.array([.299, .587, .114], np.float32)
    lf, lc = float(fundo @ [.299, .587, .114]), float(creme @ [.299, .587, .114])
    m = np.clip((lum - lf) / (lc - lf), 0, 1)
    ys, xs = np.where(m > .08)
    if not len(ys): return np.zeros((1, 1), np.float32)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)

class Cartao:
    def __init__(self, caminho, OW, OH):
        im = Image.open(caminho).convert('RGBA'); self.OW, self.OH = OW, OH
        chato = Image.alpha_composite(Image.new('RGBA', im.size, (14, 31, 71, 255)), im).convert('RGB')
        self.reconhecido = abs(im.width / im.height - 2000 / 667) < 0.08
        self.fundo, self.creme = _cores(chato.resize((2000, 667)) if self.reconhecido else chato)
        self.chato = chato
        s = OW / 1080.0; self.s = s
        if not self.reconhecido: return
        base = chato.resize((2000, 667), Image.LANCZOS)
        self.m = {k: _mascara(base, c, self.fundo, self.creme) for k, c in CAIXAS.items()}
        f = 0.92 * s
        # tamanhos finais (px do vídeo) de cada máscara
        k = {n: (1.25 * f if n == 'logo' else 1.1 * f if n in ('nome',) else f) for n in self.m}
        self.t = {n: (max(1, round(m.shape[1] * k[n])), max(1, round(m.shape[0] * k[n]))) for n, m in self.m.items()}
        self.r = {n: np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize(self.t[n], Image.LANCZOS), np.float32) / 255 for n, m in self.m.items()}
        g = lambda v: round(v * f)
        y = 0; pos = {}
        def bloco(n, gap):
            nonlocal y; pos[n] = y; y += self.t[n][1] + gap
        bloco('logo', g(46)); bloco('nome', g(18)); bloco('cargo', g(14)); bloco('crm', g(78))
        self.y_linha = y; y += g(4) + g(70)
        for n in ('ig', 'fb', 'tt'):
            h = max(self.t[n + '_i'][1], self.t[n + '_t'][1]); pos[n + '_i'] = y + (h - self.t[n + '_i'][1]) // 2; pos[n + '_t'] = y + (h - self.t[n + '_t'][1]) // 2; y += h + g(52)
        total = y - g(52); topo = round(845 * s - total / 2)                      # centro da área segura do Reels (y 220 a 1470)
        self.y = {n: topo + v for n, v in pos.items()}; self.y_linha += topo; self.g = g
        # colunas: bloco de cima centrado; linha de redes: ícone + @ centrados juntos (cada linha com a sua largura)
        self.x = {n: (OW - self.t[n][0]) // 2 for n in ('logo', 'nome', 'cargo', 'crm')}
        gap = g(34)
        larg = max(self.t[n + '_i'][0] + gap + self.t[n + '_t'][0] for n in ('ig', 'fb', 'tt')); x0 = (OW - larg) // 2
        for n in ('ig', 'fb', 'tt'):
            self.x[n + '_i'] = x0 + (self.t['ig_i'][0] - self.t[n + '_i'][0]) // 2          # ícones alinhados numa coluna
            self.x[n + '_t'] = x0 + self.t['ig_i'][0] + gap
        self.larg_linha = (x0, x0 + larg)

    def _pintar(self, canvas, n, alfa, dx=0, dy=0, esc=1.0, corte=None):
        mask = self.r[n]
        if esc != 1.0:
            w, h = max(1, round(mask.shape[1] * esc)), max(1, round(mask.shape[0] * esc))
            mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32) / 255
        h, w = mask.shape
        x = self.x[n] + dx + (self.r[n].shape[1] - w) // 2; y = self.y[n] + dy + (self.r[n].shape[0] - h) // 2
        if corte is not None:                                                    # revela da esquerda pra direita com borda suave
            suave = max(8, w // 6); xs = (np.arange(w) - corte * (w + suave)) / suave
            mask = mask * np.clip(1 - xs, 0, 1)[None, :]
        self._cola(canvas, mask * alfa, x, y)

    def _cola(self, canvas, mask, x, y):
        H, W = canvas.shape[:2]; h, w = mask.shape
        xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if xb <= xa or yb <= ya: return
        m = mask[ya - y:yb - y, xa - x:xb - x, None]
        canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - m) + self.creme[None, None, :] / 255 * m

    def quadro(self, t):
        """Imagem RGB float (0 a 1) no instante t (s) do cartão."""
        W, H = self.OW, self.OH
        canvas = np.empty((H, W, 3), np.float32); canvas[:] = self.fundo / 255
        s = self.s
        if not self.reconhecido:
            e = _facil(_prog(t, 0.1, 0.9)); im = self.chato; r = min(W * .86 / im.width, H * .5 / im.height) * (0.94 + 0.06 * e)
            im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
            a = np.asarray(im, np.float32) / 255; x, y = (W - im.width) // 2, (H - im.height) // 2
            hh, ww = a.shape[:2]; self._bloco(canvas, a, x, y, e); return canvas
        self._pintar(canvas, 'logo', 1.0, esc=0.9 + 0.1 * _facil(_prog(t, 0.1, 1.0)), corte=_facil(_prog(t, 0.1, 1.0)))
        for n, ini in (('nome', 0.75), ('cargo', 0.92), ('crm', 1.08)):
            e = _facil(_prog(t, ini, 0.5)); self._pintar(canvas, n, e, dy=round((1 - e) * 22 * s))
        e = _facil(_prog(t, 1.2, 0.5)); xa, xb = self.larg_linha; meio = (xa + xb) // 2; meia = round((xb - xa) / 2 * e)
        if meia > 0: self._cola(canvas, np.full((max(2, round(3 * s)), 2 * meia), 0.55, np.float32), meio - meia, self.y_linha)
        for n, ini in (('ig', 1.45), ('fb', 1.7), ('tt', 1.95)):
            pi = _prog(t, ini, 0.45); ei = _volta(pi); self._pintar(canvas, n + '_i', min(1.0, max(0.0, pi * 3)), esc=max(0.05, 0.55 + 0.45 * ei))
            et = _facil(_prog(t, ini + 0.1, 0.5)); self._pintar(canvas, n + '_t', et, dx=round((1 - et) * -70 * s))
        return canvas

    def _bloco(self, canvas, a, x, y, e):
        H, W = canvas.shape[:2]; h, w = a.shape[:2]
        xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - e) + a[ya - y:yb - y, xa - x:xb - x] * e

def quadros(caminho_img, OW, OH, dur_s, fps=30000 / 1001):
    """Gera os quadros (float RGB 0 a 1) do cartão, um a um."""
    c = Cartao(caminho_img, OW, OH)
    for i in range(max(2, round(dur_s * fps))): yield c.quadro(i / fps)
