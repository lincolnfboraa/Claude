"""Vocabulário por cliente: termos que o Whisper erra (nomes de remédios, estudos, marcas). Duas ajudas:
 1) os termos vão como dica (hotwords) pro Whisper em toda janela de áudio;
 2) corrigir: depois da transcrição, grafias erradas conhecidas viram a certa (também junta 'sema glutida' em 'semaglutida').
Termos SENSÍVEIS (nomes comerciais de remédios): ficam no áudio, mas na TELA (legenda, destaques, título) são trocados por um termo genérico
('a caneta', 'as canetas'), com o artigo concordando. Também vem do vocabulario.json por cliente ({sensiveis: {termos, singular, plural, genero}}).
Fontes: vocabulario.json (global e por cliente) e, se existir, o campo 'vocabulario' do DNA do cliente (lista de termos ou {termos, corrigir})."""
import json, os, re, unicodedata

ARQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vocabulario.json')

def _n(t): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', (t or '').lower()).encode('ascii', 'ignore').decode())

def carregar(cliente_id=None, dna=None):
    """{'termos': [...], 'corrigir': {errado: certo}} do cliente, ou None se não houver nada."""
    try: base = json.load(open(ARQ))
    except Exception: base = {}
    g = base.get('global') or {}; c = (base.get('clientes') or {}).get(cliente_id or '', {})
    termos = list(g.get('termos', [])) + list(c.get('termos', [])); corrigir = {**g.get('corrigir', {}), **c.get('corrigir', {})}
    extra = (dna or {}).get('vocabulario')
    if isinstance(extra, list): termos += [str(x) for x in extra]
    elif isinstance(extra, dict): termos += [str(x) for x in extra.get('termos', [])]; corrigir.update(extra.get('corrigir', {}))
    termos = list(dict.fromkeys(t.strip() for t in termos if str(t).strip()))
    sens = {**(g.get('sensiveis') or {}), **(c.get('sensiveis') or {}), **((extra or {}).get('sensiveis') or {} if isinstance(extra, dict) else {})}
    if not sens.get('termos'): sens = None
    out = {'termos': termos, 'corrigir': corrigir}
    if sens: out['sensiveis'] = sens
    return out if (termos or corrigir or sens) else None

def dica(vocab):
    """Texto de dica pro Whisper (hotwords), ou None."""
    return ', '.join(vocab['termos']) if vocab and vocab.get('termos') else None

def _com_pontuacao(original, novo):
    m = re.match(r'^(\W*)(.*?)(\W*)$', original, re.S)
    return (m.group(1) + novo + m.group(3)) if m else novo

def aplicar(pal, vocab):
    """Corrige grafias conhecidas em [{w, s, e}] (junta duas palavras quando juntas formam um termo: 'sema' + 'glutida' = 'semaglutida')."""
    if not vocab or not pal or not vocab.get('corrigir'): return pal
    corr = {_n(k): v for k, v in vocab['corrigir'].items() if _n(k)}
    out, i = [], 0
    while i < len(pal):
        w = pal[i]
        if i + 1 < len(pal):
            c2 = _n(w['w']) + _n(pal[i + 1]['w'])
            if c2 in corr and len(c2) >= 8 and len(_n(w['w'])) >= 3:        # primeira palavra curta ('o', 'de', 'e') é artigo ou preposição: não junta
                out.append({**w, 'w': _com_pontuacao(pal[i + 1]['w'], corr[c2]), 'e': pal[i + 1]['e']}); i += 2; continue
        c1 = _n(w['w'])
        out.append({**w, 'w': _com_pontuacao(w['w'], corr[c1])} if c1 in corr else w); i += 1
    return out


# ---------- termos sensíveis: troca na TELA, o áudio fica como foi falado ----------
_SING_F = {'o': 'a', 'a': 'a', 'do': 'da', 'da': 'da', 'no': 'na', 'na': 'na', 'pelo': 'pela', 'pela': 'pela', 'ao': 'à', 'um': 'uma', 'uma': 'uma',
           'esse': 'essa', 'essa': 'essa', 'este': 'esta', 'esta': 'esta', 'aquele': 'aquela', 'aquela': 'aquela'}
_PLUR_F = {'o': 'as', 'a': 'as', 'os': 'as', 'as': 'as', 'do': 'das', 'da': 'das', 'dos': 'das', 'das': 'das', 'no': 'nas', 'na': 'nas', 'nos': 'nas', 'nas': 'nas',
           'pelo': 'pelas', 'pela': 'pelas', 'pelos': 'pelas', 'pelas': 'pelas', 'ao': 'às', 'aos': 'às', 'um': 'umas', 'uma': 'umas',
           'esse': 'essas', 'essa': 'essas', 'esses': 'essas', 'essas': 'essas'}
_SING_M = {'o': 'o', 'a': 'o', 'do': 'do', 'da': 'do', 'no': 'no', 'na': 'no', 'pelo': 'pelo', 'pela': 'pelo', 'ao': 'ao', 'um': 'um', 'uma': 'um', 'esse': 'esse', 'essa': 'esse'}
_PLUR_M = {'o': 'os', 'a': 'os', 'os': 'os', 'as': 'os', 'do': 'dos', 'da': 'dos', 'dos': 'dos', 'das': 'dos', 'no': 'nos', 'na': 'nos', 'nos': 'nos', 'nas': 'nos',
           'pelo': 'pelos', 'pela': 'pelos', 'ao': 'aos', 'um': 'uns', 'uma': 'uns', 'esse': 'esses', 'essa': 'esses'}

def _mascarar(palavras, vocab):
    """palavras: lista de textos. Devolve [(texto, i0, i1)]: cada item novo e os índices antigos que ele cobre. 'o Mounjaro e o Ozempic' vira 'as canetas'."""
    s = (vocab or {}).get('sensiveis') or {}
    termos = {_n(t) for t in s.get('termos', []) if _n(t)}
    if not termos or not palavras: return [(w, k, k) for k, w in enumerate(palavras)]
    sing, plur = s.get('singular', 'medicação'), s.get('plural', 'medicações')
    A_S, A_P = (_SING_F, _PLUR_F) if s.get('genero', 'f') == 'f' else (_SING_M, _PLUR_M)
    limpa = lambda w: re.sub(r'^\W+|\W+$', '', w)
    n = len(palavras); eh = [_n(limpa(w)) in termos for w in palavras]
    ARTS, CONEC = set(A_S) | set(A_P), {'e', 'ou'}
    out, i = [], 0
    while i < n:
        if not eh[i]: out.append((palavras[i], i, i)); i += 1; continue
        fim, qtd = i, 1
        while palavras[fim].rstrip()[-1:] not in '.?!;:':                  # corrida de produtos: 'Mounjaro e Ozempic', 'o X, o Y e o Z'
            k = fim + 1
            if k < n and _n(palavras[k]) in CONEC: k += 1
            elif not palavras[fim].rstrip().endswith(','): break
            if k < n and _n(palavras[k]) in ARTS and k + 1 < n and eh[k + 1]: k += 1
            if k < n and eh[k]: fim, qtd = k, qtd + 1
            else: break
        plural = qtd >= 2; noun = plur if plural else sing; mp = A_P if plural else A_S
        m = re.search(r'\W+$', palavras[fim]); pont = m.group(0) if m else ''
        comeco_frase = i == 0 or palavras[i - 1].rstrip()[-1:] in '.?!'
        if out and out[-1][1] == out[-1][2] == i - 1 and _n(out[-1][0]) in ARTS:          # o artigo que vinha antes concorda com a palavra nova
            lead, a0, a1 = out.pop(); novo = mp.get(_n(lead), lead)
            out.append((novo[:1].upper() + novo[1:] if lead[:1].isupper() else novo, a0, a1))
        elif comeco_frase: noun = noun[:1].upper() + noun[1:]
        out.append((noun + pont, i, fim)); i = fim + 1
    return out

def mascarar_tokens(tokens, vocab):
    """Tokens da legenda [{tok, s, e, i}] com os nomes sensíveis trocados. A palavra nova cobre o tempo e os índices (i .. i2) das antigas."""
    if not (vocab or {}).get('sensiveis') or not tokens: return tokens
    out = []
    for texto, a, b in _mascarar([t['tok'] for t in tokens], vocab):
        if a == b and texto == tokens[a]['tok']: out.append(tokens[a])
        else: out.append({**tokens[a], 'tok': texto, 'e': tokens[b]['e'], 'i2': tokens[b].get('i2', tokens[b]['i'])})
    return out

def mascarar_texto(texto, vocab):
    """Texto de destaque, título etc. com os nomes sensíveis trocados."""
    if not (vocab or {}).get('sensiveis') or not texto: return texto
    return ' '.join(t for t, _, _ in _mascarar(texto.split(), vocab))

def termos_na_tela(texto, vocab):
    """Nomes sensíveis que ainda aparecem num texto (ex.: o .ass das legendas): [] se está limpo."""
    termos = ((vocab or {}).get('sensiveis') or {}).get('termos', [])
    return [t for t in termos if re.search(r'(?<![A-Za-z0-9])' + re.escape(t) + r'(?![A-Za-z0-9])', texto, re.I)]
