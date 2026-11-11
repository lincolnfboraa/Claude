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
    "Uma coisa que me deixa | muito *preocupada* | é que algumas formulações | podem ter até 500% a mais | da dose recomendada | de vitaminas do complexo B | por latinha.",
    "A presença de cafeína | nos energéticos | tem sido uma das causas | de lesão renal.",
    "E alguns energéticos têm | uma quantidade muito alta | de cafeína, | até 300 mg de cafeína | por dose.",
    "Você imagina esse estrago no teu rim?",
    "E tem um outro | que é um nome muito estranho | que eu vou ter que ler | pra vocês, chamado | glucuronolactona, | que é um metabólito | do carboidrato | excretado pelo rim.",
    "Ele, em altas doses, | pode aumentar | a *carga osmótica* do rim, | e pode ser uma causa | de uma *lesão renal aguda*.",
    "Por isso, é interessante | que você preste atenção | na quantidade de energético | que você toma *por dia*,",
    "porque o seu corpo pode não sinalizar | de uma forma tão clara | todo esse excesso.",
    "O que eu estou | dizendo aqui | não é que você | não pode tomar, | mas que você | não tome em excesso.",
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
AZUL = '&HFFB84D&'      # #4DB8FF (destaque)
NAVY = '&H38220E&'      # #0E2238 (caixa do título)
GELO = '&HF7EBDC&'      # #DCEBF7 (caixa clara do título)
FONTES = {  # nome ASS -> (arquivo, fator de escala libass medido, topo das maiúsculas, linha de base) em fração de fs
    'Poppins Medium': ('Poppins-Medium.ttf', 0.5585, 0.24, 0.628),
    'Poppins SemiBold': ('Poppins-SemiBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Bold': ('Poppins-Bold.ttf', 0.557, 0.24, 0.628),
    'Poppins ExtraBold': ('Poppins-ExtraBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Black': ('Poppins-Black.ttf', 0.5565, 0.24, 0.628),
    'Playfair Display': ('PlayfairDisplay.ttf', 0.7037, 0.32, 0.818),
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
    fn = '\\fnPoppins\\b1' if fonte == 'Poppins Bold' else f'\\fn{fonte}\\b0'
    dlg(3, t0, t1, 'K', f"{{{anim}\\fad(110,140){fn}\\fs{fs}\\fsp{sp}\\c{cor}{SOMBRA}}}{txt}")
    return w

def ajusta_fs(txt, fonte, alvo, sp, fs_max):
    fs = fs_max
    while largura(txt, fonte, fs, sp) > alvo and fs > 40: fs -= 2
    return fs

BAIXA = set('acemnorsuvwxz .,?!:;-–')   # letras sem haste/acento: topo na altura-x
DESC = set('gjpqyç')                      # letras com haste descendente
ACENTO_MAI = set('ÃÕÁÉÍÓÚÂÊÔÀ')           # maiúsculas acentuadas: o acento sobe acima da altura da maiúscula
def topo_glifo(txt, fs):   # distância da linha de base até o topo visível da linha
    if any(c in ACENTO_MAI for c in txt): return 0.50 * fs
    return (0.388 if any(c not in BAIXA for c in txt) else 0.305) * fs
def desc_glifo(txt, fs):   # quanto a linha desce abaixo da base
    return 0.10*fs if any(c in DESC for c in txt) else 0.0

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
        alto = topo_glifo(L['txt'], L['fs'])
        if i == 0:
            L['base'] = alto; topo_bloco = 0.0
        else:
            P = linhas[i-1]
            L['base'] = P['base'] + desc_glifo(P['txt'], P['fs'])*0.6 + L.get('gap', gap) + alto
    fundo = linhas[-1]['base'] + desc_glifo(linhas[-1]['txt'], linhas[-1]['fs'])
    desloc = (fundo_y - fundo) if fundo_y else (centro_y - fundo/2)   # fundo_y: ancora a base do bloco (altura da legenda)
    ref = max((L for L in linhas if L['papel'] == 'grande'), key=lambda L: L['w'])
    esq, dir_ = centro_x - ref['w']/2, centro_x + ref['w']/2
    for L in linhas:
        x = {'l': esq + L.get('dx', 0), 'r': dir_ - L.get('dx', 0), 'c': centro_x}[L['alinh']]
        tc = word_start(L['cue'], t0) - 0.04 if L.get('cue') else t0
        linha(tc, t1, L['txt'], L['fonte'], L['fs'], L['cor'], x, L['base'] + desloc, L['alinh'], L['sp'],
              'pop' if L['papel'] == 'grande' else 'slide')
    return t0, t1

BR = '&HFFFFFF&'
FUNDO_DESTAQUE = 1478   # base dos destaques 2 e 3: na altura da legenda, um pouco acima (zona segura do Reels)
# 1) "podem ter até / 500% / a mais" | pequena colada em cima à esquerda, número gigante azul, complemento colado embaixo à direita
destaque(["podem ter até 500% a mais"], [
    dict(txt="podem ter até", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='l', cue='podem', dx=8),
    dict(txt="500%", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='c', cue='500', alvo=440, fs_max=420),
    dict(txt="a mais", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='r', cue='mais', dx=4, gap=2),
], centro_y=955, centro_x=270)
# 2) "você imagina esse / ESTRAGO / no teu rim?" | pequena à direita em cima, gigante azul, pequena à esquerda embaixo
destaque(["Você imagina esse estrago no teu rim?"], [
    dict(txt="você imagina esse", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='r', cue='você', dx=6),
    dict(txt="ESTRAGO", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='c', cue='estrago', alvo=800),
    dict(txt="no teu rim?", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='l', cue='teu', dx=8, gap=2),
], fundo_y=FUNDO_DESTAQUE)
# 3) VIRADA "o seu corpo pode / NÃO / sinalizar" | quatro alturas, grandes coladas
destaque(["porque o seu corpo pode não sinalizar"], [
    dict(txt="o seu corpo pode", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='l', cue='seu', dx=6),
    dict(txt="NÃO", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='l', cue='não', alvo=410, fs_max=340),
    dict(txt="sinalizar", fonte='Poppins Bold', papel='grande', cor=BR, alinh='r', cue='sinalizar', alvo=780, sp=-5, gap=2),
], fundo_y=FUNDO_DESTAQUE)

# ---------- título (estilo dos posts anteriores: caixa escura serifada + caixa clara em itálico) ----------
t0, t1 = 0.0, seg[1]['out_end'] + 0.9
l1, l2, l3 = "ENERGÉTICO PODE", "PREJUDICAR SEUS RINS?", "ENTENDA COMO"
PF = 'Playfair Display'; cap, bl = FONTES[PF][2], FONTES[PF][3]
fs_t = ajusta_fs(l2, PF, 800, 1, 130)
fs_s = int(fs_t*0.82)
wt = max(largura(l1, PF, fs_t, 1), largura(l2, PF, fs_t, 1))
padx, pady, lead = 46, 30, 0.70*fs_t
capH = (bl-cap)*fs_t
bx, by = 540 - (wt+2*padx)/2, 170
bw, bh = wt + 2*padx, capH + lead + 2*pady
def rect(x, y, w, h): return f"m {x:.0f} {y:.0f} l {x+w:.0f} {y:.0f} l {x+w:.0f} {y+h:.0f} l {x:.0f} {y+h:.0f}"
FADE = "\\fad(200,200)"
dlg(0, t0, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c{NAVY}\\1a&H10&\\bord0\\shad0{FADE}\\p1}}{rect(bx, by, bw, bh)}")
base1 = by + pady + capH
for i, l in enumerate((l1, l2)):
    y = base1 + i*lead - bl*fs_t
    dlg(1, t0, t1, 'Card', f"{{\\an8\\pos(540,{y:.0f}){FADE}\\fn{PF}\\i0\\fs{fs_t}\\fsp1\\c&HFFFFFF&\\bord0\\shad0}}{l}")
capS = (bl-cap)*fs_s
sw, sh = largura(l3, PF, fs_s, 3) + 2*padx, capS + 2*24
sx, sy = 540 - sw/2, by + bh
dlg(0, t0+0.35, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c{GELO}\\1a&H00&\\bord0\\shad0{FADE}\\p1}}{rect(sx, sy, sw, sh)}")
dlg(1, t0+0.35, t1, 'Card', f"{{\\an8\\pos(540,{sy + 24 + capS - bl*fs_s:.0f}){FADE}\\fn{PF}\\i1\\fs{fs_s}\\fsp3\\c{NAVY}\\bord0\\shad0}}{l3}")

# ---------- cards informativos ----------
def rrect(x, y, w, h, r):
    return (f"m {x+r} {y} l {x+w-r} {y} b {x+w} {y} {x+w} {y} {x+w} {y+r} l {x+w} {y+h-r} b {x+w} {y+h} {x+w} {y+h} {x+w-r} {y+h} "
            f"l {x+r} {y+h} b {x} {y+h} {x} {y+h} {x} {y+h-r} l {x} {y+r} b {x} {y} {x} {y} {x+r} {y}")
def card(t0, t1, x, y, w, h):
    dlg(0, t0, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c&H38220E&\\1a&H30&\\bord0\\shad0\\fad(160,160)\\p1}}{rrect(x, y, w, h, 26)}")
def txt(t0, t1, x, y, s):
    dlg(1, t0, t1, 'Card', f"{{\\an8\\pos({x},{y})\\fad(160,160)}}{s}")
# nome da médica
t0 = seg[3]['out_start'] + 0.25; t1 = t0 + 4.2
card(t0, t1, 190, 205, 700, 170)
txt(t0, t1, 540, 222, "{\\fnPoppins SemiBold\\fs82\\c&HFFFFFF&}Dra. Fabiola Pedron\\N{\\fnPoppins Medium\\fs66\\c" + AZUL + "}Médica nefrologista")
# glucuronolactona (fala: metabólito do carboidrato excretado pelo rim)
t0, t1 = word_start('glucuronolactona') - 0.15, seg[8]['out_start'] - 0.05
card(t0, t1, 150, 185, 780, 215)
txt(t0, t1, 540, 192, "{\\fnPoppins\\b1\\fs118\\fsp-2\\c&HFFFFFF&}Glucuronolactona")
txt(t0, t1, 540, 290, "{\\fnPoppins Medium\\fs64\\c&HDDDDDD&}metabólito do carboidrato,\\Nexcretado pelo rim")

# ---------- legendas comuns ----------
for b in blocos:
    if b.get('oculto'): continue
    s = b['txt'].replace('*', '')
    dlg(2, b['s'], b['e'], 'Sub', f"{{\\blur5}}{s}")

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
        f.write(f"{i}\n{ts_srt(b['s'])} --> {ts_srt(b['e'])}\n{b['txt'].replace('*', '')}\n\n")
print(len(blocos), 'blocos de legenda,', sum(1 for b in blocos if b.get('oculto')), 'viraram frase de destaque')
