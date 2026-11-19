"""Textos do vídeo (ASS 1080x1920 + SRT), no padrão aprovado na Fabiola:
legenda minimal branca sem pontos, título T1b (rótulo + tema em serifa itálica + pergunta, mesma largura),
frases de destaque empilhadas (Poppins pop, serifa itálica, lettering letra a letra) e palavra solta.
Entrada: tokens já no tempo do vídeo montado [{'tok','s','e','i'}] (i = índice da palavra no plano) e o plano da IA."""
import os, random
from PIL import ImageFont

FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONTES = {  # nome ASS -> (arquivo, fator libass, topo das maiúsculas, linha de base) em fração de fs
    'Poppins Medium': ('Poppins-Medium.ttf', 0.5585, 0.24, 0.628),
    'Poppins SemiBold': ('Poppins-SemiBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Bold': ('Poppins-Bold.ttf', 0.557, 0.24, 0.628),
    'Poppins Black': ('Poppins-Black.ttf', 0.5565, 0.24, 0.628),
    'Merriweather Black Italic': ('Merriweather-BlackItalic.ttf', 0.573, 0.28, 0.71),
    'Inter': ('Inter-Regular.otf', 0.8116, 0.185, 0.775),
    'Inter Bold': ('Inter-Bold.otf', 0.8108, 0.185, 0.775),
}
_pil = {}
def largura(txt, fonte, fs, sp=0):
    arq, k = FONTES[fonte][0], FONTES[fonte][1]
    f = _pil.setdefault(arq, ImageFont.truetype(os.path.join(FD, arq), 100))
    bb = f.getbbox(txt)
    return (bb[2] - bb[0]) * k * fs / 100 + sp * (len(txt) - 1)

def cor_ass(hexa, padrao='#FFFFFF'):
    h = (hexa or padrao).lstrip('#')
    return f'&H{h[4:6]}{h[2:4]}{h[0:2]}&'.upper()

def ts_ass(t):
    t = max(t, 0); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
def ts_srt(t):
    ms = int(round(max(t, 0) * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

SOMBRA = '\\bord3\\3c&H000000&\\3a&H9A&\\blur7\\shad6\\4c&H000000&\\4a&H48&'
SH_LEG = '\\bord1\\3a&HFF&\\shad3\\4c&H000000&\\4a&H70&\\blur4'
Y_LEG = 1920 - 345            # linha de base da legenda (zona segura do Reels)
FUNDO_DESTAQUE = 1478         # base dos destaques, logo acima da legenda
BAIXA = set('acemnorsuvwxz .,?!:;-–'); DESC = set('gjpqyç'); ACENTO_MAI = set('ÃÕÁÉÍÓÚÂÊÔÀ')
LIMPA = str.maketrans('', '', '.')

def capf(f): return FONTES[f][3] - FONTES[f][2]
def topo_glifo(txt, fs, f):
    c = capf(f)
    if any(ch in ACENTO_MAI for ch in txt): return 1.29 * c * fs
    return (c if any(ch not in BAIXA for ch in txt) else 0.78 * c) * fs
def desc_glifo(txt, fs, f): return 0.26 * capf(f) * fs if any(ch in DESC for ch in txt) else 0.0
def ajusta_fs(txt, fonte, alvo, sp, fs_max):
    fs = fs_max
    while largura(txt, fonte, fs, sp) > alvo and fs > 40: fs -= 2
    return fs

class Roteiro:
    def __init__(self, tokens, fim, cor_leg='#FFFFFF', cor_dest='#FFFFFF'):
        self.tokens, self.fim, self.ev = tokens, fim, []
        self.BR, self.DEST = cor_ass(cor_leg), cor_ass(cor_dest, '#FFFFFF')
        self.blocos = self._blocos()

    def dlg(self, layer, t0, t1, st, txt): self.ev.append(f"Dialogue: {layer},{ts_ass(t0)},{ts_ass(t1)},{st},,0,0,0,,{txt}")

    def _blocos(self):
        """Legenda de 2 a 4 palavras (até ~22 letras), quebrando em pontuação e pausas."""
        bl, cur = [], []
        for k, t in enumerate(self.tokens):
            cur.append(t)
            txt = ' '.join(x['tok'] for x in cur)
            prox = self.tokens[k + 1] if k + 1 < len(self.tokens) else None
            quebra = (prox is None or t['tok'][-1:] in '.?!,;:' or (prox['s'] - t['e']) > 0.35
                      or len(cur) >= 4 or len(txt) >= 22 or (prox and len(txt) + 1 + len(prox['tok']) > 26))
            if quebra and (len(cur) >= 2 or prox is None or t['tok'][-1:] in '.?!' or (prox and prox['s'] - t['e'] > 0.35)):
                bl.append({'txt': txt, 's': cur[0]['s'], 'e': cur[-1]['e'], 'i0': cur[0]['i'], 'i1': cur[-1]['i']}); cur = []
        if cur: bl.append({'txt': ' '.join(x['tok'] for x in cur), 's': cur[0]['s'], 'e': cur[-1]['e'], 'i0': cur[0]['i'], 'i1': cur[-1]['i']})
        for i, b in enumerate(bl):
            nxt = bl[i + 1]['s'] if i + 1 < len(bl) else b['e'] + 0.6
            b['e'] = min(max(b['e'], b['s'] + 0.35), nxt if nxt - b['e'] < 0.5 else b['e'] + 0.3)
        return bl

    def inicio_palavra(self, i):
        t = next((t for t in self.tokens if t['i'] >= i), None)
        return t['s'] if t else 0.0

    def linha(self, t0, t1, txt, fonte, fs, cor, x, base_y, alinh='l', sp=0, entrada='slide'):
        w = largura(txt, fonte, fs, sp); topo = base_y - FONTES[fonte][3] * fs
        if entrada == 'pop':
            cx = {'l': x + w / 2, 'r': x - w / 2, 'c': x}[alinh]; cy = topo + fs / 2
            anim = f"\\an5\\pos({cx:.0f},{cy:.0f})\\fscx72\\fscy72\\t(0,150,\\fscx106\\fscy106)\\t(150,240,\\fscx100\\fscy100)"
        else:
            an = {'l': 7, 'r': 9, 'c': 8}[alinh]
            anim = f"\\an{an}\\move({x:.0f},{topo + 24:.0f},{x:.0f},{topo:.0f},0,180)"
        fn = {'Poppins Bold': '\\fnPoppins\\b1', 'Inter Bold': '\\fnInter\\b1'}.get(fonte, f'\\fn{fonte}\\b0')
        self.dlg(3, t0, t1, 'K', f"{{{anim}\\fad(110,140){fn}\\fs{fs}\\fsp{sp}\\c{cor}{SOMBRA}}}{txt}")

    def linha_letras(self, t0, t1, txt, fonte, fs, cor, x, base_y, alinh='l', sp=0, dur=0.55):
        """Lettering letra a letra (sobe com atraso aleatório, ease-out, desfoque que some), quadro a quadro."""
        rnd = random.Random(7 + len(txt)); w = largura(txt, fonte, fs, sp)
        esq = {'l': x, 'r': x - w, 'c': x - w / 2}[alinh]; topo = base_y - FONTES[fonte][3] * fs
        fn = {'Poppins Bold': '\\fnPoppins\\b1', 'Inter Bold': '\\fnInter\\b1'}.get(fonte, f'\\fn{fonte}\\b0')
        tag = f"{fn}\\fs{fs}\\fsp{sp}\\c{cor}"
        def sombra(a):
            op = 1 - a / 255; a3 = int(255 - (255 - 0x9A) * op * op); a4 = int(255 - (255 - 0x48) * op * op)
            return f"\\1a&HFF&\\bord3\\3c&H000000&\\3a&H{a3:02X}&\\blur7\\shad6\\4c&H000000&\\4a&H{a4:02X}&"
        Q = 1 / 30
        for i, ch in enumerate(txt):
            if ch == ' ': continue
            cx = esq + (largura(txt[:i] + 'x', fonte, fs, sp) - largura('x', fonte, fs, 0) if i else 0)
            atraso = rnd.uniform(0, 0.16); dy = fs * (0.22 + rnd.uniform(0, 0.38)); n = int(dur / Q)
            for f in range(n):
                p = 1 - (1 - (f + 1) / n) ** 3; a = int(max(0, 1 - p * 1.8) * 255); y = topo + dy * (1 - p); ta = t0 + atraso + f * Q
                self.dlg(2, ta, ta + Q + 0.001, 'K', f"{{\\an7\\pos({cx:.1f},{y:.1f}){tag}{sombra(a)}}}{ch}")
                self.dlg(4, ta, ta + Q + 0.001, 'K', f"{{\\an7\\pos({cx:.1f},{y:.1f}){tag}\\bord0\\shad0\\blur{(1 - p) * 4:.1f}\\1a&H{a:02X}&}}{ch}")
            tf = t0 + atraso + n * Q
            self.dlg(2, tf, t1, 'K', f"{{\\an7\\pos({cx:.1f},{topo:.1f})\\fad(0,140){tag}{sombra(0)}}}{ch}")
            self.dlg(4, tf, t1, 'K', f"{{\\an7\\pos({cx:.1f},{topo:.1f})\\fad(0,140){tag}\\bord0\\shad0}}{ch}")

    def destaque(self, d):
        """d (do plano): estilo pop|serifa|lettering|palavra_solta, palavra_inicio/fim (fala coberta), linhas [{texto, papel}]."""
        i0, i1 = d['palavra_inicio'], d['palavra_fim']
        cobre = [b for b in self.blocos if b['i1'] >= i0 and b['i0'] <= i1]
        if not cobre: return
        t0 = cobre[0]['s'] - 0.05
        k = self.blocos.index(cobre[-1])
        t1 = min(self.blocos[k + 1]['s'], cobre[-1]['e'] + 1.2) if k + 1 < len(self.blocos) else self.fim
        for b in cobre: b['oculto'] = True
        est = d['estilo']
        linhas = d['linhas'] if est != 'palavra_solta' else [{'texto': d['linhas'][0]['texto'] if d['linhas'] else '', 'papel': 'grande'}]
        L = []
        for j, ln in enumerate(linhas):
            txt = ln['texto'].strip().translate(LIMPA)
            if not txt: continue
            grande = ln['papel'] == 'grande'
            if est in ('serifa', 'palavra_solta') and grande: f, sp, alvo, fsm = 'Merriweather Black Italic', -2, 770, 230
            elif est == 'lettering': f, sp, alvo, fsm = ('Inter Bold', -8, 860, 240) if grande else ('Inter', -3, 0, 96)
            else: f, sp, alvo, fsm = ('Poppins Black', -4, 720, 330) if grande else ('Poppins SemiBold', -1, 0, 118)
            fs = ajusta_fs(txt, f, alvo, sp, fsm) if grande else fsm
            if not grande and largura(txt, f, fs, sp) > 860: fs = ajusta_fs(txt, f, 860, sp, fs)
            cue = next((t for t in self.tokens if i0 <= t['i'] <= i1 and t['tok'].lower().strip('.,?!') == txt.split()[0].lower().strip('.,?!')), None)
            L.append({'txt': txt, 'f': f, 'fs': fs, 'sp': sp, 'grande': grande, 'cor': self.DEST if grande else self.BR,
                      'alinh': 'c' if (grande or est in ('lettering', 'palavra_solta')) else ('l' if j == 0 else 'r'),
                      'tc': (cue['s'] - 0.04) if cue else t0, 'w': largura(txt, f, fs, sp)})
        if not L: return
        for j, x in enumerate(L):
            alto = topo_glifo(x['txt'], x['fs'], x['f'])
            x['base'] = alto if j == 0 else L[j - 1]['base'] + desc_glifo(L[j - 1]['txt'], L[j - 1]['fs'], L[j - 1]['f']) * 0.6 + 6 + alto
        fundo = L[-1]['base'] + desc_glifo(L[-1]['txt'], L[-1]['fs'], L[-1]['f']); desloc = FUNDO_DESTAQUE - fundo
        ref = max(L, key=lambda x: x['w']); esq, dir_ = 540 - ref['w'] / 2, 540 + ref['w'] / 2
        for x in L:
            px = {'l': esq + 8, 'r': dir_ - 6, 'c': 540}[x['alinh']]
            if est == 'lettering': self.linha_letras(x['tc'], t1, x['txt'], x['f'], x['fs'], x['cor'], px, x['base'] + desloc, x['alinh'], x['sp'])
            else: self.linha(x['tc'], t1, x['txt'], x['f'], x['fs'], x['cor'], px, x['base'] + desloc, x['alinh'], x['sp'], 'pop' if x['grande'] else 'slide')

    @staticmethod
    def _quebra(txt, f, fs, W, sp=0):
        """Quebra a frase em linhas que cabem em W px."""
        linhas, atual = [], ''
        for w in txt.split():
            t = (atual + ' ' + w).strip()
            if atual and largura(t, f, fs, sp) > W: linhas.append(atual); atual = w
            else: atual = t
        return linhas + ([atual] if atual else [])

    @classmethod
    def _equilibra(cls, txt, f, fs, W, nmax):
        """Menor número de linhas (até nmax) com larguras parecidas, sem deixar palavra sozinha na última linha."""
        total = largura(txt, f, fs); maior = max(largura(w, f, fs) for w in txt.split())
        for n in range(1, nmax + 1):
            alvo = max(maior, total / n)
            while alvo <= W:                           # alarga aos poucos até caber em n linhas parecidas
                L = cls._quebra(txt, f, fs, alvo)
                if len(L) <= n: return L
                alvo *= 1.04
        return None

    def titulo(self, tit, t1, modelo='premium', cor_caixa=None):
        """Título do gancho no template escolhido: premium (T1b), caixa (frase num retângulo sólido) ou impacto (frase grande)."""
        if modelo == 'caixa': return self._titulo_caixa(tit, t1, cor_caixa)
        if modelo == 'impacto': return self._titulo_impacto(tit, t1)
        return self._titulo_premium(tit, t1)

    def _titulo_caixa(self, tit, t1, cor_caixa):
        """Frase em caixa alta dentro de um retângulo sólido (cor da caixa); rótulo pequeno embaixo, na cor de destaque."""
        frase = (tit.get('frase') or tit.get('pergunta') or tit.get('tema') or '').upper().translate(LIMPA)
        if not frase: return
        f, W, fs = 'Poppins Bold', 860, 112
        while fs > 50 and not self._equilibra(frase, f, fs, W, 3): fs -= 4
        L = (self._equilibra(frase, f, fs, W, 3) or self._quebra(frase, f, fs, W))[:3]
        lh = round(fs * 1.12); pad_x, pad_y = 34, round(fs * 0.34)
        wmax = max(largura(x, f, fs, 0) for x in L)
        topo = 960; x0, x1 = 540 - wmax / 2 - pad_x, 540 + wmax / 2 + pad_x
        y1 = topo + pad_y * 2 + lh * len(L) - round(fs * 0.12)
        cx = cor_ass(cor_caixa or '#1E2A47', '#1E2A47')
        self.dlg(0, 0, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c{cx}\\1a&H00&\\bord0\\shad3\\4c&H000000&\\4a&H90&\\fad(250,250)\\p1}}m {x0:.0f} {topo} l {x1:.0f} {topo} l {x1:.0f} {y1} l {x0:.0f} {y1}")
        for k, x in enumerate(L):
            base = topo + pad_y + lh * k + round(fs * FONTES[f][3])
            self.dlg(2, 0.1 + 0.08 * k, t1, 'Card', f"{{\\an2\\pos(540,{base:.0f})\\fad(300,250)\\fn{f}\\fs{fs}\\c{self.BR}\\bord0\\shad0}}{x}")
        rot = (tit.get('rotulo') or '').upper()
        if rot:
            fr = 46; base = y1 + 22 + round(fr * FONTES['Poppins SemiBold'][3])
            self.dlg(2, 0.3, t1, 'Card', f"{{\\an2\\pos(540,{base:.0f})\\fad(350,250)\\fnPoppins SemiBold\\fs{fr}\\fsp3\\c{self.DEST}{SOMBRA}}}{rot}")

    def _titulo_impacto(self, tit, t1):
        """Frase grande em caixa alta (Poppins Black), palavra-chave na cor de destaque, entrada com pop."""
        frase = (tit.get('frase') or tit.get('pergunta') or tit.get('tema') or '').upper().translate(LIMPA)
        if not frase: return
        chave = (tit.get('tema') or '').upper()
        palavras = frase.split()
        if not chave or chave not in frase: chave = max(palavras, key=len)
        f, W, fs = 'Poppins Black', 920, 150
        while fs > 60 and not self._equilibra(frase, f, fs, W, 3): fs -= 6
        L = (self._equilibra(frase, f, fs, W, 3) or self._quebra(frase, f, fs, W))[:4]
        lh = round(fs * 1.02); topo = 940
        for k, x in enumerate(L):
            txt = ' '.join(f"{{\\c{self.DEST}}}{w}{{\\c{self.BR}}}" if w.strip('?!,') in chave.split() else w for w in x.split())
            base = topo + lh * k + round(fs * FONTES[f][3])
            t0 = 0.08 * k
            self.dlg(2, t0, t1, 'Card', f"{{\\an2\\pos(540,{base:.0f})\\fn{f}\\fs{fs}\\c{self.BR}{SOMBRA}\\fscx70\\fscy70\\t(0,180,\\fscx104\\fscy104)\\t(180,260,\\fscx100\\fscy100)\\fad(120,250)}}{txt}")

    def _titulo_premium(self, tit, t1):
        """Título T1b: três linhas coladas com a mesma largura, entrada em cascata. Sombra só nas letras (regra geral: sem bloco/degradê atrás)."""
        lab, tema, sub = (tit.get('rotulo') or '').upper(), tit.get('tema') or '', tit.get('pergunta') or ''
        if not tema: return
        fl, spl, fsM, fsQ = 56, 9, 250, 80
        wt0 = largura(tema, 'Merriweather Black Italic', fsM, 0)
        if wt0 > 900: fsM = ajusta_fs(tema, 'Merriweather Black Italic', 900, 0, 250); wt0 = largura(tema, 'Merriweather Black Italic', fsM, 0)
        wl0 = largura(lab, 'Poppins Medium', fl, spl) if lab else 0
        W = max(wl0, wt0, largura(sub, 'Poppins SemiBold', fsQ, -1) if sub else 0)
        if W > 940: W = 940
        if lab: spl = spl + (W - wl0) / max(len(lab) - 1, 1)
        spM = (W - wt0) / max(len(tema) - 1, 1)
        if sub:
            while largura(sub, 'Poppins SemiBold', fsQ + 1, -1) <= W: fsQ += 1
            while largura(sub, 'Poppins SemiBold', fsQ, -1) > W and fsQ > 40: fsQ -= 1
        capf_ = lambda f, fs: capf(f) * fs
        def tit_(tt0, f, txt, fs, sp, base, cor):
            top = base - FONTES[f][3] * fs; w = largura(txt, f, fs, sp)
            self.dlg(2, tt0, t1, 'Card', f"{{\\an7\\move({540 - w / 2:.0f},{top + 18:.0f},{540 - w / 2:.0f},{top:.0f},0,450)\\fad(350,300)\\fn{f}\\fs{fs}\\fsp{sp:.1f}\\c{cor}{SOMBRA}}}{txt}")
        b1 = 1010
        if lab: tit_(0, 'Poppins Medium', lab, fl, spl, b1, self.DEST)
        b2 = b1 + 16 + capf_('Merriweather Black Italic', fsM); tit_(0.15, 'Merriweather Black Italic', tema, fsM, spM, b2, self.DEST)
        if sub: b3 = b2 + capf_('Poppins SemiBold', fsQ) * 0.78 + 26; tit_(0.3, 'Poppins SemiBold', sub, fsQ, -1, b3, self.BR)

    def gravar(self, base):
        for b in self.blocos:
            if not b.get('oculto'):
                self.dlg(2, b['s'], b['e'], 'Sub', f"{{\\blur5\\c{self.BR}}}{b['txt'].translate(LIMPA)}")
        head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                "Style: Sub,Poppins SemiBold,88,&H00FFFFFF,&H00FFFFFF,&HFF000000,&HA6000000,0,0,0,0,100,100,-0.3,0,1,1,3,2,110,110,420,1\n"
                "Style: K,Poppins SemiBold,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
                "Style: Card,Poppins,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,0,0,0,1\n\n"
                "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        open(base + '.ass', 'w').write(head + '\n'.join(self.ev) + '\n')
        with open(base + '.srt', 'w') as f:
            for i, b in enumerate(self.blocos, 1):
                f.write(f"{i}\n{ts_srt(b['s'])} --> {ts_srt(b['e'])}\n{b['txt'].translate(LIMPA)}\n\n")
