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
    "Seu pai deve ter, | sua mãe deve ter, | seu avô deve ter, | o seu vizinho deve ter. | É uma epidemia mundial.",
    "Nesse mês de novembro, | a gente tem uma data | muito importante, | que é o Dia Mundial | do Diabetes.",
    "Mas o diabetes | vai muito além | desse açúcar no sangue.",
    "O que esse diabetes | pode fazer no seu rim?",
    "A incidência de doença renal em pacientes diabéticos gira em torno de 30% a 40%.",
    "Vocês já viram falar | do fundo do olho | para o diabético? | O fundo do olho | é um exame | extremamente importante | em pacientes diabéticos | e ele reflete também a lesão renal. | Você sabia disso?",
    "Os vasos que têm | dentro do olho, | aqueles microvasos, | eles são parecidos | com os microvasos | que têm dentro do rim. | Quando a gente consegue | ver lesão nesses microvasos | no olho, | a gente já sabe | que tem lesão no rim.",
    "As primeiras lesões de rim | acontecem com a | perda de proteína. | É aquela história | do filtro de café | que perde o pó. | Quando você perde esse pó, | você mostra que o teu rim, | o teu filtro, | não está íntegro, | ele tem furos a mais | que estão passando | o que não deveria passar.",
    "Às vezes, | a função continua normal, | mas você já tem o início | dessa doença renal.",
    "Lembrando que a doença renal | só começa a ter sintomas | quando a gente já perdeu mais de 60% da função.",
    "A maioria das vezes | você não percebe, | você só vai perceber | no exame de sangue.",
    "Hoje em dia, | nós temos inúmeras | medicações novas, | então nós temos | muitas coisas | para fazer por você.",
    "Então, a minha dica aqui | é de que você peça | para o teu médico | fazer um exame de urina | e um exame de creatinina | para você.",
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
AZUL = '&HA7B9C8&'      # #C8B9A7 creme/bege da paleta da Dra. Fabiola (cor da palavra em destaque)
NAVY = '&H4A1C0F&'      # #0F1C4A azul-marinho da paleta (caixa do título)
GELO = '&HA7B9C8&'      # #C8B9A7 bege da paleta (caixa clara do título)
FONTES = {  # nome ASS -> (arquivo, fator de escala libass medido, topo das maiúsculas, linha de base) em fração de fs
    'Poppins Medium': ('Poppins-Medium.ttf', 0.5585, 0.24, 0.628),
    'Poppins SemiBold': ('Poppins-SemiBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Bold': ('Poppins-Bold.ttf', 0.557, 0.24, 0.628),
    'Poppins ExtraBold': ('Poppins-ExtraBold.ttf', 0.557, 0.24, 0.628),
    'Poppins Black': ('Poppins-Black.ttf', 0.5565, 0.24, 0.628),
    'Playfair Display': ('PlayfairDisplay.ttf', 0.7037, 0.32, 0.818),
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
    base_tag = f"{fn}\\fs{fs}\\fsp{sp}\\c{cor}{sombra}"
    Q = 1/30
    for i, ch in enumerate(txt):
        if ch == ' ': continue
        cx = esq + (largura(txt[:i] + 'x', fonte, fs, sp) - largura('x', fonte, fs, 0) if i else 0)
        atraso = rnd.uniform(0, 0.16)
        dy = fs * (0.22 + rnd.uniform(0, 0.38))          # altura aleatória de partida
        n = int(dur / Q)
        for f in range(n):
            p = 1 - (1 - (f + 1)/n) ** 3                 # ease-out cúbico
            a = max(0, 1 - p*1.8)                        # some a transparência rápido
            y = topo + dy*(1 - p)
            ta = t0 + atraso + f*Q
            dlg(3, ta, ta + Q + 0.001, 'K', f"{{\\an7\\pos({cx:.1f},{y:.1f})\\alpha&H{int(a*255):02X}&\\blur{(1-p)*6:.1f}{base_tag}}}{ch}")
        dlg(3, t0 + atraso + n*Q, t1, 'K', f"{{\\an7\\pos({cx:.1f},{topo:.1f})\\fad(0,140){base_tag}}}{ch}")
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
# 1) DADO "doença renal em diabéticos / 30% a 40%"
destaque(["A incidência de doença renal em pacientes diabéticos gira em torno de 30% a 40%."], [
    dict(txt="doença renal em diabéticos", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='l', cue='doença', dx=6, fs=104),
    dict(txt="30% a 40%", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='c', cue='30', alvo=780),
], fundo_y=FUNDO_DESTAQUE)
# 2) CURIOSIDADE "o fundo do olho reflete / LESÃO RENAL"
destaque(["e ele reflete também a lesão renal."], [
    dict(txt="o fundo do olho reflete", fonte='Poppins SemiBold', papel='pequena', cor=BR, alinh='r', cue='reflete', dx=6),
    dict(txt="LESÃO RENAL", fonte='Poppins Black', papel='grande', cor=AZUL, alinh='c', cue='lesão', alvo=820),
], fundo_y=FUNDO_DESTAQUE)
# 3) VIRADA no estilo do preset "lettering 01" (Helvetica -> Inter, letras juntas, subida aleatória letra a letra)
destaque(["quando a gente já perdeu mais de 60% da função."], [
    dict(txt="já perdeu mais de", fonte='Inter', papel='pequena', cor=BR, alinh='c', cue='perdeu', fs=96, sp=-3, letras=True),
    dict(txt="60% da função", fonte='Inter Bold', papel='grande', cor=AZUL, alinh='c', cue='60', alvo=860, fs_max=260, sp=-8, letras=True, gap=10),
], fundo_y=FUNDO_DESTAQUE)

# ---------- título: faixa no peito, como nos vídeos aprovados (cor do tema: azul do símbolo do diabetes) ----------
AZUL_DIAB = '&H9C4F1B&'    # #1B4F9C
t0, t1 = 0.0, seg[1]['out_end'] - 0.05
PF = 'Playfair Display'
fs_t = ajusta_fs("DIABETES", PF, 760, 6, 150)
by, bh = 1010, 230
def rect(x, y, w, h): return f"m {x:.0f} {y:.0f} l {x+w:.0f} {y:.0f} l {x+w:.0f} {y+h:.0f} l {x:.0f} {y+h:.0f}"
FADE = "\\fad(200,250)"
dlg(0, t0, t1, 'Card', f"{{\\an7\\pos(0,0)\\1c{AZUL_DIAB}\\1a&H18&\\bord0\\shad0{FADE}\\p1}}{rect(0, by, 1080, bh)}")
y1 = by + 26 - FONTES[PF][2]*fs_t
dlg(1, t0, t1, 'Card', f"{{\\an7\\pos({540 - largura('DIABETES', PF, fs_t, 6)/2:.0f},{y1:.0f}){FADE}\\fn{PF}\\fs{fs_t}\\fsp6\\c&HFFFFFF&\\bord0\\shad0}}DIABETES")
dlg(1, t0+0.3, t1, 'Card', f"{{\\an2\\pos(540,{by+bh-22:.0f}){FADE}\\fnPoppins\\b1\\fs96\\c&HFFFFFF&\\bord0\\shad0}}o que ele pode fazer no seu rim?")

# ---------- legendas comuns ----------
for b in blocos:
    if b.get('oculto'): continue
    s = b['txt'].replace('*', '').replace('.', '')   # padrão: legenda sem pontos
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
        f.write(f"{i}\n{ts_srt(b['s'])} --> {ts_srt(b['e'])}\n{b['txt'].replace('*', '').replace('.', '')}\n\n")
print(len(blocos), 'blocos de legenda,', sum(1 for b in blocos if b.get('oculto')), 'viraram frase de destaque')
