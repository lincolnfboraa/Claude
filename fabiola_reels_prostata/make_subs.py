#!/usr/bin/env python3
"""Gera legendas (ASS com título, frases de destaque e cards + SRT) sincronizadas ao vídeo montado.
Uso: python3 make_subs.py <palavras_whisper.json> <saida_base>
 - palavras_whisper.json: transcrição com tempos por palavra do ÁUDIO JÁ MONTADO
 - o texto exibido vem do roteiro revisado abaixo (ortografia corrigida manualmente);
   o Whisper só fornece os tempos. '|' separa blocos de legenda, *palavra* = destaque.
 - blocos cobertos por uma FRASE DE DESTAQUE (lista DESTAQUES) não aparecem como legenda comum.
Fontes: pasta fonts/ (Poppins e Playfair Display, licença OFL)."""
import json, sys, re, difflib, os
from PIL import ImageFont

here = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(here, 'fonts')
words = json.load(open(sys.argv[1]))
base = sys.argv[2]
segs = json.load(open(os.path.join(here, 'timeline_render.json')))['segmentos']
seg = {s['id']: s for s in segs}

ROTEIRO = [
    "O que esse canudinho | tem a ver | com câncer de próstata?",
    "Quando a gente pensa na próstata, | a gente tem que entender | que a próstata, | ela engloba a uretra. | É como se você tivesse | um canudinho | onde passa o xixi | e ela vai fechando.",
    "Quando ela vai crescendo, | ela vai fechando | esse buraco.",
    "Então, existem alguns sintomas | de câncer de próstata | que você precisa saber. | Um deles é quando você tem que forçar pra fazer xixi.",
    "E aí significa | que isso aqui está fechando, | esse buraquinho | está fechando.",
    "Mas, falando do seu rim, | a gente tem que entender | que o câncer de próstata | pode ter efeitos | no seu rim.",
    "Uma das coisas | que pode acontecer | é que quando fecha | essa passagem de urina, | você pode fazer | uma obstrução da urina | e fazer uma insuficiência renal. | Hoje em dia, | como a gente chama, | uma injúria renal aguda.",
    "Existem outros mecanismos | que podem provocar | problema renal, | principalmente com o uso | das medicações quimioterápicas | para o tratamento do câncer.",
    "Por isso, | procure um urologista | e, se você tiver | problema renal, | entre em contato | com o nefrologista.",
]

# ---------- alinhamento roteiro x tempos do Whisper ----------
norm = lambda s: re.sub(r'[^0-9a-záàâãéêíóôõúç]', '', s.lower())
W, wmap = '', []
for i, w in enumerate(words):
    n = norm(w['w']); W += n; wmap += [i]*len(n)
chunks = [c.strip() for frase in ROTEIRO for c in frase.split('|')]
R, rspans = '', []
for ci, c in enumerate(chunks):
    for tok in c.split():
        n = norm(tok); rspans.append((len(R), len(R)+len(n), ci, tok)); R += n
sm = difflib.SequenceMatcher(None, R, W, autojunk=False)
r2w = {}
for a, b, size in sm.get_matching_blocks():
    for k in range(size): r2w[a+k] = b+k
tokens = []
for (s0, s1, ci, tok) in rspans:
    hits = [wmap[r2w[k]] for k in range(s0, s1) if k in r2w]
    tokens.append({'ci': ci, 'tok': tok, 's': words[hits[0]]['s'] if hits else None, 'e': words[hits[-1]]['e'] if hits else None})
for i, t in enumerate(tokens):
    if t['s'] is None:
        prev = next((tokens[j]['e'] for j in range(i-1, -1, -1) if tokens[j]['e'] is not None), 0)
        t['s'] = t['e'] = prev
blocos = []
for ci, c in enumerate(chunks):
    ts = [t for t in tokens if t['ci'] == ci]
    blocos.append({'txt': c, 's': ts[0]['s'], 'e': ts[-1]['e']})
for i, b in enumerate(blocos):
    nxt = blocos[i+1]['s'] if i+1 < len(blocos) else b['e'] + 0.6
    b['e'] = min(max(b['e'], b['s']+0.35), nxt if nxt - b['e'] < 0.5 else b['e'] + 0.3)
FIM = seg[max(seg)]['out_end']

def word_start(txt, after=0.0):
    return next(t['s'] for t in tokens if norm(t['tok']).startswith(norm(txt)) and t['s'] >= after - 0.01)

def ts_ass(t):
    t = max(t, 0); return f"{int(t//3600)}:{int(t % 3600//60):02d}:{t % 60:05.2f}"
def ts_srt(t):
    ms = int(round(t*1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"

# ---------- tipografia ----------
AZUL = '&HD8B08F&'      # #8FB0D8 azul claro (Novembro Azul), harmonizado com o marinho e o cinza-azulado da paleta da Dra. Fabiola
NAVY = '&H4A1C0F&'      # #0F1C4A azul-marinho da paleta (caixa do título)
GELO = '&HA7B9C8&'      # #C8B9A7 bege da paleta (caixa clara do título)
FONTES = {  # nome ASS -> (arquivo, fator de escala libass medido, topo das maiúsculas, linha de base) em fração de fs
    'Poppins Medium': ('Poppins-Medium.ttf', 0.5585, 0.24, 0.628),
    'Poppins SemiBold': ('Poppins-SemiBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Bold': ('Poppins-Bold.ttf', 0.557, 0.24, 0.628),
    'Poppins ExtraBold': ('Poppins-ExtraBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Black': ('Poppins-Black.ttf', 0.5565, 0.24, 0.628),
    'Playfair Display': ('PlayfairDisplay.ttf', 0.7037, 0.32, 0.818),
    'Merriweather Black Italic': ('Merriweather-BlackItalic.ttf', 0.573, 0.28, 0.71),   # preset lettering 24
    'Inter': ('/usr/share/fonts/opentype/inter/Inter-Regular.otf', 0.8116, 0.185, 0.775),      # substituta gratuita da Helvetica Neue
    'Inter Bold': ('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 0.8108, 0.185, 0.775),
}
_pil = {}
def largura(txt, fonte, fs, sp=0):
    arq, k = FONTES[fonte][0], FONTES[fonte][1]
    f = _pil.setdefault(arq, ImageFont.truetype(os.path.join(FD, arq), 100))
    bb = f.getbbox(txt)
    return (bb[2]-bb[0]) * k * fs/100 + sp*(len(txt)-1)

ev = []
def dlg(layer, t0, t1, style, txt):
    ev.append(f"Dialogue: {layer},{ts_ass(t0)},{ts_ass(t1)},{style},,0,0,0,,{txt}")

SOMBRA_MARINHO = '\\bord4\\3c&HFFFFFF&\\3a&H00&\\blur1\\shad6\\4c&H000000&\\4a&H48&'   # marinho precisa de contorno claro sobre a blusa vinho
SOMBRA = '\\bord3\\3c&H000000&\\3a&H9A&\\blur7\\shad6\\4c&H000000&\\4a&H48&'
def linha(t0, t1, txt, fonte, fs, cor, x, base_y, alinh='l', sp=0, entrada='slide', bold=False):
    """Desenha uma linha posicionada pela linha de base. alinh: l (x = borda esquerda), r (x = borda direita), c (x = centro)."""
    w = largura(txt, fonte, fs, sp)
    topo = base_y - FONTES[fonte][3]*fs
    if entrada == 'pop':   # cresce a partir do centro
        cx = {'l': x + w/2, 'r': x - w/2, 'c': x}[alinh]; cy = topo + fs/2
        anim = f"\\an5\\pos({cx:.0f},{cy:.0f})\\fscx72\\fscy72\\t(0,150,\\fscx106\\fscy106)\\t(150,240,\\fscx100\\fscy100)"
    else:                  # desliza 24 px de baixo pra cima
        an, xx = {'l': (7, x), 'r': (9, x), 'c': (8, x)}[alinh]
        anim = f"\\an{an}\\move({xx:.0f},{topo+24:.0f},{xx:.0f},{topo:.0f},0,180)"
    fn = {'Poppins Bold': '\\fnPoppins\\b1', 'Inter Bold': '\\fnInter\\b1'}.get(fonte, f'\\fn{fonte}\\b0')
    sombra = SOMBRA_MARINHO if cor == NAVY else SOMBRA
    dlg(3, t0, t1, 'K', f"{{{anim}\\fad(110,140){fn}\\fs{fs}\\fsp{sp}\\c{cor}{sombra}}}{txt}")
    return w

import random
def linha_letras(t0, t1, txt, fonte, fs, cor, x, base_y, alinh='l', sp=0, semente=7, dur=0.55):
    """Recria o preset 'lettering 01' do CapCut ('Subida aleatória' + 'Deslizar para cima' + fade):
    todas as letras sobem JUNTAS, cada uma com atraso e altura aleatórios pequenos, com curva de desaceleração
    (ease-out) e desfoque que some. Calculado quadro a quadro (30 fps) porque o \\move do ASS é linear."""
    rnd = random.Random(semente + len(txt))
    w = largura(txt, fonte, fs, sp)
    esq = {'l': x, 'r': x - w, 'c': x - w/2}[alinh]
    topo = base_y - FONTES[fonte][3]*fs
    fn = {'Poppins Bold': '\\fnPoppins\\b1', 'Inter Bold': '\\fnInter\\b1'}.get(fonte, f'\\fn{fonte}\\b0')
    sombra = SOMBRA_MARINHO if cor == NAVY else SOMBRA
    tag = f"{fn}\\fs{fs}\\fsp{sp}\\c{cor}"
    def sombra_tag(a):   # camada de baixo: só sombra/contorno, acompanhando o fade da letra
        op = 1 - a/255                                   # opacidade da letra; a sombra acompanha proporcionalmente
        a3 = int(255 - (255 - 0x9A)*op*op); a4 = int(255 - (255 - 0x48)*op*op)
        return (f"\\1a&HFF&\\bord3\\3c&H000000&\\3a&H{a3:02X}&\\blur7"
                f"\\shad6\\4c&H000000&\\4a&H{a4:02X}&")
    Q = 1/30
    for i, ch in enumerate(txt):
        if ch == ' ': continue
        cx = esq + (largura(txt[:i] + 'x', fonte, fs, sp) - largura('x', fonte, fs, 0) if i else 0)
        atraso = rnd.uniform(0, 0.16)
        dy = fs * (0.22 + rnd.uniform(0, 0.38))          # altura aleatória de partida
        n = int(dur / Q)
        for f in range(n):
            p = 1 - (1 - (f + 1)/n) ** 3                 # ease-out cúbico
            a = int(max(0, 1 - p*1.8) * 255)             # transparência da letra (some rápido)
            y = topo + dy*(1 - p)
            ta = t0 + atraso + f*Q
            dlg(2, ta, ta + Q + 0.001, 'K', f"{{\\an7\\pos({cx:.1f},{y:.1f}){tag}{sombra_tag(a)}}}{ch}")
            dlg(4, ta, ta + Q + 0.001, 'K', f"{{\\an7\\pos({cx:.1f},{y:.1f}){tag}\\bord0\\shad0\\blur{(1-p)*4:.1f}\\1a&H{a:02X}&}}{ch}")
        tf = t0 + atraso + n*Q
        dlg(2, tf, t1, 'K', f"{{\\an7\\pos({cx:.1f},{topo:.1f})\\fad(0,140){tag}{sombra_tag(0)}}}{ch}")
        dlg(4, tf, t1, 'K', f"{{\\an7\\pos({cx:.1f},{topo:.1f})\\fad(0,140){tag}\\bord0\\shad0}}{ch}")
    return w

def ajusta_fs(txt, fonte, alvo, sp, fs_max):
    fs = fs_max
    while largura(txt, fonte, fs, sp) > alvo and fs > 40: fs -= 2
    return fs

BAIXA = set('acemnorsuvwxz .,?!:;-–')   # letras sem haste/acento: topo na altura-x
DESC = set('gjpqyç')                      # letras com haste descendente
ACENTO_MAI = set('ÃÕÁÉÍÓÚÂÊÔÀ')           # maiúsculas acentuadas: o acento sobe acima da altura da maiúscula
def capf(fonte): return FONTES.get(fonte, FONTES['Poppins SemiBold'])[3] - FONTES.get(fonte, FONTES['Poppins SemiBold'])[2]
def topo_glifo(txt, fs, fonte='Poppins SemiBold'):   # distância da linha de base até o topo visível da linha
    c = capf(fonte)
    if any(ch in ACENTO_MAI for ch in txt): return 1.29 * c * fs
    return (c if any(ch not in BAIXA for ch in txt) else 0.78 * c) * fs
def desc_glifo(txt, fs, fonte='Poppins SemiBold'):   # quanto a linha desce abaixo da base
    return 0.26 * capf(fonte) * fs if any(ch in DESC for ch in txt) else 0.0

def destaque(chunk_txts, linhas, centro_y=1010, alvo=830, centro_x=540, gap=6, fundo_y=None):
    """Frase de destaque: linhas empilhadas de cima pra baixo, cada uma ENCOSTADA na anterior
    (folga 'gap' px entre a base/haste de uma e o topo das letras da seguinte, igual ao padrão dos posts).
    linhas: dicts {txt, fonte, papel ('pequena'|'grande'), cor, alinh ('l','r','c'), cue (palavra que dispara a entrada), dx (recuo)}"""
    idx = [i for i, b in enumerate(blocos) if b['txt'].replace('*', '') in chunk_txts]
    t0 = blocos[idx[0]]['s'] - 0.05
    t1 = min(blocos[idx[-1]+1]['s'], blocos[idx[-1]]['e'] + 1.2) if idx[-1]+1 < len(blocos) else FIM
    for i in idx: blocos[i]['oculto'] = True
    for L in linhas:
        if L['papel'] == 'grande':
            L['sp'] = L.get('sp', -4); L['fs'] = ajusta_fs(L['txt'], L['fonte'], L.get('alvo', alvo), L['sp'], L.get('fs_max', 330))
        else:
            L['sp'] = L.get('sp', -1); L['fs'] = L.get('fs', 118)
        L['w'] = largura(L['txt'], L['fonte'], L['fs'], L['sp'])
    # empilhamento vertical colado
    y, topo_bloco = 0.0, None
    for i, L in enumerate(linhas):
        alto = topo_glifo(L['txt'], L['fs'], L['fonte'])
        if i == 0:
            L['base'] = alto; topo_bloco = 0.0
        else:
            P = linhas[i-1]
            L['base'] = P['base'] + desc_glifo(P['txt'], P['fs'], P['fonte'])*0.6 + L.get('gap', gap) + alto
    fundo = linhas[-1]['base'] + desc_glifo(linhas[-1]['txt'], linhas[-1]['fs'], linhas[-1]['fonte'])
    desloc = (fundo_y - fundo) if fundo_y else (centro_y - fundo/2)   # fundo_y: ancora a base do bloco (altura da legenda)
    ref = max((L for L in linhas if L['papel'] == 'grande'), key=lambda L: L['w'])
    esq, dir_ = centro_x - ref['w']/2, centro_x + ref['w']/2
    for L in linhas:
        x = {'l': esq + L.get('dx', 0), 'r': dir_ - L.get('dx', 0), 'c': centro_x}[L['alinh']]
        tc = word_start(L['cue'], t0) - 0.04 if L.get('cue') else t0
        if L.get('letras'):
            linha_letras(tc, t1, L['txt'], L['fonte'], L['fs'], L['cor'], x, L['base'] + desloc, L['alinh'], L['sp'])
        else:
            linha(tc, t1, L['txt'], L['fonte'], L['fs'], L['cor'], x, L['base'] + desloc, L['alinh'], L['sp'],
                  'pop' if L['papel'] == 'grande' else 'slide')
    return t0, t1

BR = '&HFFFFFF&'
FUNDO_DESTAQUE = 1478   # base dos destaques 2 e 3: na altura da legenda, um pouco acima (zona segura do Reels)
# PALAVRA SOLTA: "canudinho" (a analogia com o objeto que ela segura)
destaque(["um canudinho"], [
    dict(txt="canudinho", fonte='Merriweather Black Italic', papel='grande', cor=AZUL, alinh='c', cue='canudinho', alvo=760, fs_max=230, sp=-2),
], fundo_y=FUNDO_DESTAQUE)
# 1) IDENTIFICAÇÃO (Poppins pop): "quando você tem que / FORÇAR / pra fazer xixi"
destaque(["Um deles é quando você tem que forçar pra fazer xixi."], [
    dict(txt="quando você tem que", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='l', cue='quando', dx=8),
    dict(txt="FORÇAR", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='c', cue='forçar', alvo=720, fs_max=330),
    dict(txt="pra fazer xixi", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='r', cue='fazer', dx=6, gap=2),
], fundo_y=FUNDO_DESTAQUE)
# (destaque 'insuficiência renal' removido: a tela dividida já ilustra a obstrução e os rins)
# 3) MECANISMO 2 (lettering letra a letra, Inter): "das medicações / quimioterápicas"
destaque(["das medicações quimioterápicas"], [
    dict(txt="das medicações", fonte='Inter', papel='pequena', cor=BR, alinh='c', cue='medicações', fs=96, sp=-3, letras=True),
    dict(txt="quimioterápicas", fonte='Inter Bold', papel='grande', cor=AZUL, alinh='c', cue='quimioterápicas', alvo=860, fs_max=240, sp=-8, letras=True, gap=10),
], fundo_y=FUNDO_DESTAQUE)
# PALAVRA SOLTA: "nefrologista" (fechamento, a especialidade dela)
destaque(["com o nefrologista."], [
    dict(txt="nefrologista", fonte='Merriweather Black Italic', papel='grande', cor=AZUL, alinh='c', cue='nefrologista', alvo=780, fs_max=230, sp=-2),
], fundo_y=FUNDO_DESTAQUE)

# ---------- título T1b: rótulo espaçado + tema em serifa itálica + pergunta, MESMA largura, sem caixa ----------
import math
t0, t1 = 0.0, seg[1]['out_end'] + 1.0
lab, tema, sub = 'NOVEMBRO AZUL', 'Próstata', 'pode prejudicar seus rins?'
fl, spl, fsM = 56, 9, 250
wl0 = largura(lab, 'Poppins Medium', fl, spl); wt0 = largura(tema, 'Merriweather Black Italic', fsM, 0)
fsQ = 80                                          # pergunta com tamanho fixo de leitura; as linhas de cima se espaçam até a largura dela
W = max(wl0, wt0, largura(sub, 'Poppins SemiBold', fsQ, -1))
spl = spl + (W - wl0) / (len(lab) - 1)            # o mais estreito ganha espaçamento até a largura do bloco
spM = (W - wt0) / (len(tema) - 1)
while largura(sub, 'Poppins SemiBold', fsQ + 1, -1) <= W: fsQ += 1
capf_ = lambda f, fs: (FONTES[f][3] - FONTES[f][2]) * fs
def rect(x, y, w, h): return f"m {x:.0f} {y:.0f} l {x+w:.0f} {y:.0f} l {x+w:.0f} {y+h:.0f} l {x:.0f} {y+h:.0f}"
dlg(0, t0, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c&H120A06&\\1a&H6E&\\bord0\\shad0\\blur90\\fad(300,300)\\p1}}{rect(-300, 960, 1680, 400)}")
def tit(tt0, f, txt_, fs, sp, base, cor):
    top = base - FONTES[f][3]*fs; w = largura(txt_, f, fs, sp)
    fn = '\\fnPoppins\\b1' if f == 'Poppins Bold' else f'\\fn{f}'
    dlg(2, tt0, t1, 'Card', f"{{\\an7\\move({540-w/2:.0f},{top+18:.0f},{540-w/2:.0f},{top:.0f},0,450)\\fad(350,300){fn}\\fs{fs}\\fsp{sp:.1f}\\c{cor}{SOMBRA}}}{txt_}")
b1 = 1010; tit(t0, 'Poppins Medium', lab, fl, spl, b1, AZUL)
b2 = b1 + 16 + capf_('Merriweather Black Italic', fsM); tit(t0+0.15, 'Merriweather Black Italic', tema, fsM, spM, b2, AZUL)
b3 = b2 + capf_('Poppins SemiBold', fsQ)*0.78 + 26; tit(t0+0.3, 'Poppins SemiBold', sub, fsQ, -1, b3, BR)

# ---------- legendas comuns ----------
LEGENDA_DINAMICA = os.environ.get('LEGENDA_DINAMICA') == '1'
Y_LEG = 1920 - 345                     # linha de base da legenda (mesma zona segura do Reels)
SH_LEG = '\\bord1\\3a&HFF&\\shad3\\4c&H000000&\\4a&H70&\\blur4'
_ciclo = {'curta': 0, 'media': 0}
def modo_legenda(ci, n_pal, txt):
    """Jogo de legendas: alterna fina (palavra por palavra), forte, gigante e espaçada, por fala."""
    if n_pal <= 2:
        _ciclo['curta'] += 1
        return ['forte', 'espacada', 'gigante'][_ciclo['curta'] % 3] if len(txt) <= 18 else 'forte'
    if n_pal == 3:
        _ciclo['media'] += 1
        return 'gigante' if _ciclo['media'] % 3 == 0 and len(txt) <= 20 else 'forte'
    return 'fina'
for ci, b in enumerate(blocos):
    if b.get('oculto'): continue
    s = b['txt'].replace('*', '').replace('.', '')   # padrão: legenda sem pontos
    if not LEGENDA_DINAMICA:
        dlg(2, b['s'], b['e'], 'Sub', f"{{\\blur5}}{s}"); continue
    pal = [t for t in tokens if t['ci'] == ci]
    modo = modo_legenda(ci, len(pal), s)
    if modo == 'fina':        # pequena e leve, a frase se monta palavra por palavra
        partes = ''.join(f"{{\\alpha&HFF&\\t({int((t['s']-b['s'])*1000)},{int((t['s']-b['s'])*1000)+90},\\alpha&H00&)}}{t['tok'].replace('.', '').replace('*', '')} " for t in pal)
        dlg(2, b['s'], b['e'], 'Sub', f"{{\\an2\\pos(540,{Y_LEG})\\fnInter\\b0\\fs64\\fsp-2\\c&HFFFFFF&{SH_LEG}}}{partes.strip()}")
    elif modo == 'forte':     # negrito médio, entra inteira com um pop curto
        dlg(2, b['s'], b['e'], 'Sub', f"{{\\an2\\pos(540,{Y_LEG})\\fnPoppins\\b1\\fs118\\fsp-3\\c&HFFFFFF&{SH_LEG}\\fscx90\\fscy90\\t(0,90,\\fscx100\\fscy100)}}{s}")
    elif modo == 'gigante':   # negrito médio um pouco maior que o 'forte'
        fs = ajusta_fs(s, 'Poppins Black', 760, -3, 150)   # médio (não estoura a largura)
        dlg(2, b['s'], b['e'], 'Sub', f"{{\\an2\\pos(540,{Y_LEG+10})\\fnPoppins Black\\fs{fs}\\fsp-3\\c&HFFFFFF&{SH_LEG}\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}}{s}")
    else:                     # espaçada: palavras afastadas, uma a uma
        partes = '\\h\\h\\h\\h'.join(f"{{\\alpha&HFF&\\t({int((t['s']-b['s'])*1000)},{int((t['s']-b['s'])*1000)+90},\\alpha&H00&)}}{t['tok'].replace('.', '')}" for t in pal)
        dlg(2, b['s'], b['e'], 'Sub', f"{{\\an2\\pos(540,{Y_LEG})\\fnInter\\b0\\fs84\\fsp-1\\c&HFFFFFF&{SH_LEG}}}{partes}")

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Poppins SemiBold,88,&H00FFFFFF,&H00FFFFFF,&HFF000000,&HA6000000,0,0,0,0,100,100,-0.3,0,1,1,3,2,110,110,420,1
Style: K,Poppins SemiBold,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Card,Poppins,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(base + '.ass', 'w').write(head + '\n'.join(ev) + '\n')
with open(base + '.srt', 'w') as f:  # SRT completo (inclui as falas que viraram destaque)
    for i, b in enumerate(blocos, 1):
        f.write(f"{i}\n{ts_srt(b['s'])} --> {ts_srt(b['e'])}\n{b['txt'].replace('*', '').replace('.', '')}\n\n")
print(len(blocos), 'blocos de legenda,', sum(1 for b in blocos if b.get('oculto')), 'viraram frase de destaque')
