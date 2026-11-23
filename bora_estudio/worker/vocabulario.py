"""Vocabulário por cliente: termos que o Whisper erra (nomes de remédios, estudos, marcas). Duas ajudas:
 1) os termos vão como dica (hotwords) pro Whisper em toda janela de áudio;
 2) corrigir: depois da transcrição, grafias erradas conhecidas viram a certa (também junta 'sema glutida' em 'semaglutida').
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
    return {'termos': termos, 'corrigir': corrigir} if (termos or corrigir) else None

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
