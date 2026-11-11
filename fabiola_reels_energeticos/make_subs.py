#!/usr/bin/env python3
"""Gera legendas (ASS com grafismos + SRT) sincronizadas ao vídeo montado.
Uso: python3 make_subs.py <palavras_whisper.json> <saida_base>
 - palavras_whisper.json: transcrição com tempos por palavra do ÁUDIO JÁ MONTADO
 - o texto exibido vem do roteiro revisado abaixo (ortografia corrigida manualmente);
   o Whisper só fornece os tempos. '|' separa blocos de legenda, *palavra* = destaque."""
import json, sys, re, difflib, os

here = os.path.dirname(os.path.abspath(__file__))
words = json.load(open(sys.argv[1]))
base = sys.argv[2]
segs = json.load(open(os.path.join(here, 'timeline_render.json')))['segmentos']
seg = {s['id']: s for s in segs}

ROTEIRO = [
    "Uma coisa que me deixa | muito *preocupada* | é que algumas formulações | podem ter até *500%* a mais | da dose recomendada | de vitaminas do complexo B | por latinha.",
    "A presença de cafeína | nos energéticos | tem sido uma das causas | de possibilidade | de *lesão renal*.",
    "O ideal é que a gente | ingira no máximo | *400 mg* de cafeína | ao dia.",
    "E alguns energéticos, | eles têm uma quantidade | muito alta de cafeína, | que variam entre 80 | até 300 mg de cafeína | por dose.",
    "Você imagina | esse *estrago* | disso no teu rim?",
    "Porque o seu corpo | pode *não sinalizar* | assim, de uma forma | tão clara, | todo esse excesso.",
    "O que eu estou | dizendo aqui | não é que você | não pode tomar, | mas que você | *não tome em excesso*.",
]

norm = lambda s: re.sub(r'[^0-9a-záàâãéêíóôõúç]', '', s.lower())
# string do whisper com mapa caractere -> palavra
W, wmap = '', []
for i, w in enumerate(words):
    n = norm(w['w']); W += n; wmap += [i]*len(n)
# blocos do roteiro -> palavras
chunks = []
for frase in ROTEIRO:
    for c in frase.split('|'):
        chunks.append(c.strip())
R, rspans, rw = '', [], []
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
# interpola tokens sem correspondência
for i, t in enumerate(tokens):
    if t['s'] is None:
        prev = next((tokens[j]['e'] for j in range(i-1, -1, -1) if tokens[j]['e'] is not None), 0)
        t['s'] = t['e'] = prev
blocos = []
for ci, c in enumerate(chunks):
    ts = [t for t in tokens if t['ci'] == ci]
    blocos.append({'txt': c, 's': ts[0]['s'], 'e': ts[-1]['e']})
for i, b in enumerate(blocos):  # segura até o próximo bloco (máx. 0,5 s extra)
    nxt = blocos[i+1]['s'] if i+1 < len(blocos) else b['e'] + 0.6
    b['e'] = min(max(b['e'], b['s']+0.35), nxt if nxt - b['e'] < 0.5 else b['e'] + 0.3)

def word_start(txt, nth=0):
    hits = [t['s'] for t in tokens if norm(t['tok']).startswith(norm(txt))]
    return hits[nth]

def ts_ass(t):
    t = max(t, 0); h = int(t//3600); m = int(t % 3600//60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def ts_srt(t):
    ms = int(round(t*1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"

AMBAR = '&H66D1FF&'   # #FFD166
def rrect(x, y, w, h, r):
    return (f"m {x+r} {y} l {x+w-r} {y} b {x+w} {y} {x+w} {y} {x+w} {y+r} l {x+w} {y+h-r} b {x+w} {y+h} {x+w} {y+h} {x+w-r} {y+h} "
            f"l {x+r} {y+h} b {x} {y+h} {x} {y+h} {x} {y+h-r} l {x} {y+r} b {x} {y} {x} {y} {x+r} {y}")

ev = []
def card(t0, t1, x, y, w, h, alpha='&H38&', layer=0):
    ev.append(f"Dialogue: {layer},{ts_ass(t0)},{ts_ass(t1)},Card,,0,0,0,,{{\\an7\\pos(0,0)\\1c&H161616&\\1a{alpha}\\bord0\\shad0\\fad(160,160)\\p1}}{rrect(x, y, w, h, 26)}")
def txt(t0, t1, x, y, s, style='Card', an=8, extra=''):
    ev.append(f"Dialogue: 1,{ts_ass(t0)},{ts_ass(t1)},{style},,0,0,0,,{{\\an{an}\\pos({x},{y})\\fad(160,160){extra}}}{s}")

# 1) Gancho (pergunta fiel ao tema da gravação)
t0, t1 = 0.0, seg[1]['out_end']
card(t0, t1, 120, 200, 840, 230)
txt(t0, t1, 540, 228, "{\\fnInter Black\\fs74\\c&HFFFFFF&}ENERGÉTICO\\N{\\fs74}FAZ MAL PRO {\\c" + AMBAR + "}RIM?", extra='\\fscx96\\fscy96\\t(0,140,\\fscx100\\fscy100)')
# 2) Dado da vitamina B (fala: "até 500% a mais da dose recomendada... por latinha")
t0, t1 = word_start('500'), seg[2]['out_end']
card(t0, t1, 190, 170, 700, 236)
txt(t0, t1, 540, 190, "{\\fnInter SemiBold\\fs34\\c&HD8D8D8&}VITAMINAS DO COMPLEXO B")
txt(t0, t1, 540, 234, "{\\fnInter Black\\fs96\\c" + AMBAR + "}até +500%")
txt(t0, t1, 540, 348, "{\\fnInter Medium\\fs34\\c&HFFFFFF&}da dose recomendada, por latinha")
# 3) Identificação da médica
t0 = seg[3]['out_start'] + 0.25; t1 = t0 + 4.2
card(t0, t1, 190, 220, 700, 130)
txt(t0, t1, 540, 236, "{\\fnInter Bold\\fs46\\c&HFFFFFF&}Dra. Fabiola Pedron\\N{\\fnInter Medium\\fs34\\c" + AMBAR + "}Médica nefrologista")
# 4) Comparativo de cafeína (fala: máximo ideal 400 mg/dia; energéticos 80 a 300 mg por dose)
t0, t1 = word_start('400'), seg[10]['out_end']
card(t0, t1, 60, 190, 465, 210)
txt(t0, t1, 292, 212, "{\\fnInter SemiBold\\fs30\\c&HD8D8D8&}MÁXIMO IDEAL POR DIA")
txt(t0, t1, 292, 258, "{\\fnInter Black\\fs84\\c&HFFFFFF&}400 mg")
txt(t0, t1, 292, 352, "{\\fnInter Medium\\fs30\\c&HD8D8D8&}de cafeína")
t2 = word_start('80')
card(t2, t1, 555, 190, 465, 210)
txt(t2, t1, 787, 212, "{\\fnInter SemiBold\\fs30\\c&HD8D8D8&}ENERGÉTICOS, POR DOSE")
txt(t2, t1, 787, 258, "{\\fnInter Black\\fs84\\c" + AMBAR + "}80–300")
txt(t2, t1, 787, 352, "{\\fnInter Medium\\fs30\\c&HD8D8D8&}mg de cafeína")

# legendas
for b in blocos:
    s = re.sub(r'\*(.+?)\*', lambda m: '{\\c' + AMBAR + '}' + m.group(1) + '{\\c&HFFFFFF&}', b['txt'])
    ev.append(f"Dialogue: 2,{ts_ass(b['s'])},{ts_ass(b['e'])},Sub,,0,0,0,,{{\\fscx93\\fscy93\\t(0,90,\\fscx100\\fscy100)}}{s}")

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter ExtraBold,62,&H00FFFFFF,&H00FFFFFF,&H50000000,&H90000000,0,0,0,0,100,100,0,0,1,3.2,2.5,2,110,110,345,1
Style: Card,Inter,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(base + '.ass', 'w').write(head + '\n'.join(ev) + '\n')
with open(base + '.srt', 'w') as f:
    for i, b in enumerate(blocos, 1):
        f.write(f"{i}\n{ts_srt(b['s'])} --> {ts_srt(b['e'])}\n{b['txt'].replace('*', '')}\n\n")
print(len(blocos), 'blocos de legenda')
