"""Motor de edição do Bora Studio.
nova_edicao / ajuste: transcreve os originais, a IA monta o plano no DNA do cliente, ffmpeg monta a prévia 480p (HDR do original),
  os textos entram no padrão aprovado e a prévia vai pro app.
final: renderiza de novo a partir dos ORIGINAIS na resolução nativa (4K), com e sem legenda + .srt, num .zip (sem compressão)."""
import glob, json, os, re, shutil, subprocess, time, urllib.request
import insercoes, montagem, textos

TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')

class Andamento:
    """Porcentagem que anda dentro das etapas longas + previsão do que falta, pela velocidade medida no próprio render.
    passes: [(rótulo, peso, pct_ini, pct_fim)]; peso = tempo relativo por quadro (textos 4K = 1)."""
    def __init__(s, etapa, passes):
        s.etapa, s.passes, s.taxa, s.total = etapa, passes, None, None
    def restante(s, i, feito):
        if not s.taxa or not s.total: return None
        return round(((s.total - feito) * s.passes[i][1] + sum(p[1] for p in s.passes[i + 1:]) * s.total) / s.taxa)
    def inicio(s, i, total):
        s.total = total; nome, _, a, _ = s.passes[i]
        prev = s.restante(i, 0)
        s.etapa(nome, a, **({'previsao_s': prev} if prev else {}))
        ref = []                                       # relógio começa no 1º quadro (não conta a preparação dos cards)
        def cb(frac, feito):
            if not ref: ref[:] = [time.time(), feito]
            el, q = time.time() - ref[0], feito - ref[1]
            if q >= 30 and el >= 8: s.taxa = q / el * s.passes[i][1]           # quadros/s de uma etapa de peso 1
            n, _, a2, b2 = s.passes[i]; prev = s.restante(i, feito)
            s.etapa(n, a2 + int((b2 - a2) * frac), detalhe=f'quadro {feito} de {total}', **({'previsao_s': prev} if prev else {}))
        return cb

def _arquivos(pid, meta):
    arqs = [a['caminho'] for a in (meta.get('arquivos') or []) if os.path.exists(a.get('caminho', ''))]
    return arqs or sorted(glob.glob(os.path.join(TRAB, pid, 'original_*.*')))

def nomes_originais(meta, arqs):
    """Nome que o editor enviou (IMG_1705.MOV) de cada original, na mesma ordem de arqs; o caminho no servidor é original_NN.mov."""
    por = {a.get('caminho'): a.get('nome') for a in (meta.get('arquivos') or []) if a.get('nome')}
    return [por.get(a) or os.path.basename(a) for a in arqs]

def _diagnostico_enquadramento(pid, cli_id, arqs, nomes, papeis, pasta, meta, sb):
    """Fase 1 do enquadramento: mede rostos por take (uma vez por projeto) e guarda o resumo no projeto e a folha de quadros no bucket. Não muda nenhum corte; nunca derruba a edição."""
    try:
        cache = os.path.join(pasta, 'enquadramento_diag2.json')      # v2: a 1ª versão não lia vídeo girado (iPhone) e gravou vazio
        if os.path.exists(cache) or os.environ.get('BORA_DIAG_ENQ', '1') == '0': return
        import enquadramento
        jpg = os.path.join(pasta, 'diag_enquadramento.jpg')
        res = enquadramento.diagnosticar(arqs, nomes, jpg, papeis)
        json.dump(res or [], open(cache, 'w'))
        if not res: return
        if os.path.exists(jpg): _subir(sb, f'{cli_id}/{pid}/diag_enquadramento.jpg', jpg, 'image/jpeg')
        m2 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m2['enquadramento_diag'] = res; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m2})
    except Exception as e:
        print('diagnóstico de enquadramento:', str(e)[:120], flush=True)

ESTADO_ROSTOS = {}

def medir_rostos(pl, pal, arqs, pasta, etapa=None):
    """Rostos nos takes de fala usados no plano (cache por arquivo): o render usa pra não cortar ninguém no zoom e deixar respiro em cima."""
    if os.environ.get('BORA_ENQUADRAMENTO', '1') == '0': return {}
    try:
        import enquadramento
        G = montagem.indice_global(pal); usados = sorted({G[int(sg['palavra_inicio'])][0] for sg in pl.get('segmentos') or []})
        if etapa: etapa('Olhando onde estão as pessoas em cada take', 34)
        out = {}
        for ai in usados:
            cache = os.path.join(pasta, f'rostos2_{ai + 1:02d}.json')
            if os.path.exists(cache): r = json.load(open(cache))
            else:
                r = enquadramento.rostos_no_tempo(arqs[ai])
                if r: json.dump(r, open(cache, 'w'))                      # vazio não fica guardado: tenta de novo no próximo
            ESTADO_ROSTOS[str(ai)] = {'quadros': len(r), 'com_rosto': sum(1 for _, cs in r if cs), 'erro': '' if r else enquadramento.ULTIMO_ERRO[0][:160]}
            if any(cs for _, cs in r): out[str(ai)] = r
        return out
    except Exception as e:
        print('medir rostos:', str(e)[:120], flush=True); return {}

def _subir(sb, caminho, arq, tipo):
    url = os.environ['SUPABASE_URL'].rstrip('/') + f'/storage/v1/object/previas/{caminho}'
    r = urllib.request.Request(url, data=open(arq, 'rb').read(), method='POST',
                               headers={'apikey': os.environ['SUPABASE_SECRET'], 'Content-Type': tipo, 'x-upsert': 'true'})
    urllib.request.urlopen(r, timeout=600).read()

def _transcricoes(pid, arqs, etapa, vocab=None):
    pal = []
    for i, a in enumerate(arqs, 1):
        etapa(f'Transcrevendo {"o vídeo" if len(arqs) == 1 else f"o vídeo {i} de {len(arqs)}"}', 8 + int(17 * (i - 1) / len(arqs)))
        pal.append(montagem.transcrever(a, os.path.join(TRAB, pid, f'transcricao_{i:02d}.json'), vocab))
    if not any(pal): raise RuntimeError('não encontrei fala nos vídeos enviados')
    return pal

PREFIXOS_IDEIA = re.compile(r'^\s*(gostei|gosto|tipo|algo como|algo assim|ex\.?\s*:|exemplo|sugest|ideia|pode ser|que tal|quero|manter|mantenha|usar|use|comece|come[çc]ar|abrir com|abra com|inspir)', re.I)
def gancho_texto(frase):
    """O que o editor escreveu no campo do gancho: (título EXATO, ideia). Observação ('Gostei do gancho de...', 'tipo...', 'exemplo...') ou texto
    longo é IDEIA (a IA cria o título a partir dela); só o que parece título de verdade (curto, ou inteiro entre aspas) vai pra caixa sem mudar."""
    f = (frase or '').strip()
    if not f: return '', ''
    if PREFIXOS_IDEIA.match(f) or len(f) > 90: return '', f
    m = re.fullmatch(r'[“"«](.+)[”"»]', f)
    return (m.group(1).strip() if m else f), ''

CRF_4K = {'leve': 24, 'alta': 16, 'maxima': 10}          # qualidade do 4K escolhida na aprovação (CRF menor = mais bits = mais fiel)
def crf_4k(meta):
    """CRF do final 4K: o escolhido no app ('qualidade_4k'); sem escolha, BORA_Q4K do bora.env; sem ele, 'alta' (CRF 16)."""
    q = (meta or {}).get('qualidade_4k') or os.environ.get('BORA_Q4K', 'alta')
    return CRF_4K.get(q, CRF_4K['alta'])

CRF_INTER = {24: 14, 16: 11, 10: 8}                       # etapas intermediárias do 4K (trechos, B-roll, cards): quase sem perda quando o final pede qualidade
CAPA_FINAL_S = float(os.environ.get('BORA_CAPA_FINAL_S', '3.5'))               # segundos da capa final (CRM e RQE)
def _renderizar(pid, pl, arqs, pal, altura, cores, saida_base, etapa=None, faixa=(45, 80), crf_final=24, pasta=None, anda=None, sfx=None, crf_i=14, vocab=None):
    pasta = pasta or os.path.join(TRAB, pid)
    pcs, tokens, dur = montagem.pecas(pl, arqs, pal, pasta)
    if not pcs: raise RuntimeError('o plano não gerou nenhum trecho')
    base = os.path.join(pasta, f'_base_{altura}.mp4')
    a, b = faixa
    prog = (lambda f, txt='Montando o vídeo a partir dos originais': etapa(txt, a + int((b - a) * f))) if etapa else None
    tokens_orig = tokens                                       # a verificação compara com o que foi FALADO; a tela usa os termos trocados
    if (vocab or {}).get('sensiveis'):                         # nomes comerciais: na tela viram 'a caneta', 'as canetas' (o áudio não muda)
        import vocabulario
        tokens = vocabulario.mascarar_tokens(tokens, vocab)
        pl = {**pl, 'destaques': [{**d, 'linhas': [{**l, 'texto': vocabulario.mascarar_texto(l.get('texto', ''), vocab)} for l in d.get('linhas', [])]} for d in pl.get('destaques', [])]}
        if pl.get('titulo'): pl['titulo'] = {k: (vocabulario.mascarar_texto(v, vocab) if isinstance(v, str) else v) for k, v in pl['titulo'].items()}
        if (pl.get('_gancho') or {}).get('frase'): pl['_gancho'] = {**pl['_gancho'], 'frase': vocabulario.mascarar_texto(pl['_gancho']['frase'], vocab)}
    ro = textos.Roteiro(tokens, dur, cores.get('leg'), cores.get('dest'))
    for d in pl.get('destaques', []): ro.destaque(d)           # antes da montagem: os efeitos sonoros precisam saber quando cada destaque entra
    lista_sfx = None
    if sfx:                                                    # efeitos sonoros (opcional por projeto): whoosh nas trocas de história, pop nos destaques
        lista_sfx = []
        for t, tipo in montagem.eventos_sfx(pcs, ro.t_destaques, dur):
            e = sfx.get(tipo)
            if e and os.path.exists(os.path.join(pasta, e['arquivo'])): lista_sfx.append((max(0.0, t - float(e.get('pico_s') or 0)), os.path.join(pasta, e['arquivo'])))
        print(f'efeitos sonoros: {len(lista_sfx)} no vídeo', flush=True)
    capa = next((x for x in pl.get('_anexos', []) if x.get('capa_final') and os.path.exists(x.get('caminho', ''))), None)      # capa final anexada no app
    hdr = montagem.render_base(pcs, arqs, base, altura, crf_i, prog, sfx=lista_sfx or None, capa={'imagem': capa['caminho'], 'dur': CAPA_FINAL_S} if capa else None,
                               rostos=pl.get('_rostos'))
    if pl.get('broll') and pl.get('_broll_arquivos'):
        if etapa: etapa('Encaixando as cenas de ambiente (B-roll)', a + int((b - a) * 0.9))
        base = montagem.aplicar_broll(base, os.path.join(pasta, f'_broll_{altura}.mp4'), pl, tokens, dur, arqs, altura, pasta, hdr, crf=crf_i)
    anexos = [x for x in pl.get('_anexos', []) if os.path.exists(x.get('caminho', '')) and not x.get('capa_final')]     # a capa final não entra nas inserções da IA
    if pl.get('insercoes') and anexos:
        cb = anda.inicio(0, montagem.quadros(base)) if anda else (etapa('Encaixando imagens e vídeos anexados', b) if etapa else None)
        base = insercoes.aplicar(base, os.path.join(pasta, f'_ins_{altura}.mp4'), pl, tokens, dur, anexos, pasta, hdr, prog=cb, crf=crf_i)
    if ro.desfoque: base = montagem.desfocar(base, os.path.join(pasta, f'_selo_{altura}.mp4'), ro.desfoque, crf_i)
    logo = os.path.join(pasta, pl.get('_logo_selo') or 'logo_cliente.png')    # logo do cliente embaixo do selo de campanha (se existir na pasta do projeto)
    if ro.selos and os.path.exists(logo):
        t0s, t1s = ro.selos[0]; base = montagem.sobrepor_imagem(base, os.path.join(pasta, f'_logo_{altura}.mp4'), logo, t0s + 0.15, t1s, 0.5, 0.635, 0.6, hdr, crf_i)
    g = pl.get('_gancho') or {}; modelo = g.get('template') or 'ia'
    tit = dict(pl.get('titulo') or {})
    if g.get('frase'): tit['frase'] = g['frase']; tit['pergunta'] = g['frase'] if modelo in ('premium', 'ia') else tit.get('pergunta', '')
    mostrar = modelo != 'nenhum' and (pl.get('usar_titulo') or (modelo != 'ia' and (g.get('frase') or tit.get('tema'))))
    if mostrar and (tit.get('tema') or tit.get('frase') or tit.get('pergunta')):
        s0 = pl['segmentos'][0]; fim1 = [t['e'] for t in tokens if int(s0['palavra_inicio']) <= t['i'] <= int(s0['palavra_fim'])]
        seg1 = max(fim1) if fim1 else 3.0
        ro.titulo(tit, min(max(seg1 + 1.0, 3.0), 5.5), 'premium' if modelo == 'ia' else modelo, cores.get('caixa'))
    ro.gravar(saida_base)
    return base, hdr, dur + (CAPA_FINAL_S if capa else 0), tokens_orig

def _final_nome(cliente_nome, titulo):
    return ''.join(c for c in f"{cliente_nome}_{titulo}".replace(' ', '_') if c.isalnum() or c in '_-')[:60]

def pacote_transcricao(p, sb):
    """Pacote só de transcrição (pro computador de render), ou None se as transcrições já existem."""
    pid = p['projeto_id']
    proj = (sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=cliente_id,original_meta') or [{}])[0]
    meta = proj.get('original_meta') or {}
    arqs = _arquivos(pid, meta); pasta = os.path.join(TRAB, pid)
    if not arqs: return None
    falta = [i for i in range(1, len(arqs) + 1) if not os.path.exists(os.path.join(pasta, f'transcricao_{i:02d}.json'))]
    if not falta: return None
    v = (sb('GET', f"/rest/v1/versoes?id=eq.{p.get('versao_id')}&select=numero") or [{'numero': p.get('versao', 1)}])[0]
    return {'projeto_id': pid, 'tipo': 'previa', 'etapa': 'transcricao', 'versao_id': p.get('versao_id'), 'n': v['numero'], 'altura': 854,
            'arquivos': [os.path.basename(a) for a in arqs], 'transcricoes': [], 'plano': None, 'anexos': [],
            'vocabulario': __import__('vocabulario').carregar(proj.get('cliente_id'), (sb('GET', f"/rest/v1/dna_ativo?cliente_id=eq.{proj.get('cliente_id')}&select=dna") or [{}])[0].get('dna'))}

def exigir_takes(arqs, papeis, anexos, textos):
    """Takes de fala que o editor pediu pra entrar no storytelling: o anexo tem o mesmo nome de um original (IMG_1705.mov = IMG_1705.MOV)
    ou o pedido (briefing, último feedback) cita o take. Devolve (índices dos originais, anexos que eram só o mesmo take de novo)."""
    import re
    stems = {i: os.path.splitext(os.path.basename(a))[0].casefold() for i, a in enumerate(arqs) if papeis[i] == 'fala'}      # arqs: nomes dos originais (nomes_originais)
    exig, casados = set(), []
    for x in anexos:
        if x.get('capa_final'): continue
        st = os.path.splitext(str(x.get('nome', '')))[0].casefold()
        for i, s_ in stems.items():
            if st == s_: exig.add(i); casados.append(x)
    txt = ' '.join(t for t in textos if t).casefold()
    for i, s_ in stems.items():
        num = re.sub(r'\D', '', s_)
        if re.search(r'(?<![a-z0-9])' + re.escape(s_) + r'(?![a-z0-9])', txt) or (len(num) >= 3 and re.search(r'(?<!\d)' + num + r'(?!\d)', txt)): exig.add(i)
    return exig, casados

def preparar(p, etapa, sb, correcao=None):
    """Parte leve (fica no VPS): lê o pedido, transcreve (com cache), a IA monta o plano e grava o PACOTE de render.
    O pacote só tem nomes de arquivo relativos à pasta do projeto, então qualquer máquina com os mesmos arquivos renderiza igual."""
    pid, tipo = p['projeto_id'], p['tipo']
    proj = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=*')[0]
    meta, cli_id = proj.get('original_meta') or {}, proj['cliente_id']
    cliente = sb('GET', f'/rest/v1/clientes?id=eq.{cli_id}&select=*')[0]
    dna = (sb('GET', f'/rest/v1/dna_ativo?cliente_id=eq.{cli_id}&select=dna') or [{}])[0].get('dna') or {}
    regras = (sb('GET', '/rest/v1/regras_globais?id=eq.1&select=regras') or [{}])[0].get('regras') or {}
    versoes = sb('GET', f'/rest/v1/versoes?projeto_id=eq.{pid}&select=*&order=numero')
    v = next((x for x in versoes if x['id'] == p.get('versao_id')), versoes[-1])
    arqs = _arquivos(pid, meta)
    if not arqs: raise RuntimeError('os vídeos originais não estão no servidor; envie de novo pelo app')
    tx = (dna.get('texto') or {})
    cores = {'leg': (proj.get('cores_texto') or {}).get('leg') or tx.get('legenda') or '#FFFFFF',
             'dest': (proj.get('cores_texto') or {}).get('dest') or tx.get('destaque') or (((dna.get('paleta') or {}).get('cores') or [None])[0] if (dna.get('paleta') or {}).get('cores') else '#FFFFFF'),
             'caixa': (proj.get('cores_texto') or {}).get('caixa') or tx.get('caixa') or '#1E2A47'}
    pasta = os.path.join(TRAB, pid); os.makedirs(pasta, exist_ok=True)
    etapa('Lendo o pedido', 5)
    import vocabulario
    vocab = vocabulario.carregar(cli_id, dna)                 # termos do cliente (nomes de remédios, estudos...) pro Whisper
    pal = _transcricoes(pid, arqs, etapa, vocab)
    montagem.liberar_modelo()                         # memória livre pro render
    pac = {'projeto_id': pid, 'tipo': 'final' if tipo == 'final' else 'previa', 'versao_id': v['id'], 'n': v['numero'], 'cliente_id': cli_id,
           'cores': cores, 'vocabulario': vocab, 'arquivos': [os.path.basename(a) for a in arqs], 'transcricoes': [f'transcricao_{i:02d}.json' for i in range(1, len(arqs) + 1)]}

    if tipo in ('nova_edicao', 'ajuste'):
        # fala x ambiente: escolha do app (papel_usuario) ou pela quantidade de fala; ambiente vira B-roll pra IA (com um quadro de cada)
        info = meta.get('arquivos') or []
        papeis = [montagem.classificar(pal[i], arqs[i], (info[i] if i < len(info) else {}).get('papel_usuario')) for i in range(len(arqs))]
        if all(p == 'ambiente' for p in papeis): papeis = ['fala'] * len(arqs)       # sem nenhuma locução: trata tudo como fala
        brolls = []
        for i, a in enumerate(arqs):
            if papeis[i] == 'ambiente':
                etapa('Separando quadros das cenas de ambiente', 26)
                jpg, tempos = montagem.folha_take(a, os.path.join(pasta, f'broll_{i + 1:02d}_folha.jpg'))
                cache_t = os.path.join(pasta, f'broll_{i + 1:02d}_tremor.json')      # tremor só se já foi medido (medição é feita depois, só nos escolhidos)
                trem = json.load(open(cache_t)) if os.path.exists(cache_t) else None
                if jpg: brolls.append({'n': len(brolls) + 1, 'ai': i, 'nome': (info[i] if i < len(info) else {}).get('nome') or os.path.basename(a),
                                       'dur': montagem.duracao(a), 'jpg': jpg, 'tempos': tempos, 'tremor': trem})
        if info and any((x.get('papel') != papeis[i]) for i, x in enumerate(info[:len(papeis)])):
            m2 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
            for i, x in enumerate((m2.get('arquivos') or [])[:len(papeis)]): x['papel'] = papeis[i]
            sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m2})
        n = v['numero']
        anterior = None
        ant_arq = os.path.join(pasta, f'plano_v{n - 1}.json')
        if n > 1 and os.path.exists(ant_arq): anterior = json.load(open(ant_arq))
        feedbacks = [(x['numero'], x['feedback']) for x in versoes if x.get('feedback') and x['numero'] < n]
        if correcao:                                      # revisão interna: refaz o plano desta versão com os problemas que a avaliação achou
            atual = os.path.join(pasta, f'plano_v{n}.json')
            if os.path.exists(atual): anterior = json.load(open(atual)); os.replace(atual, os.path.join(pasta, f'plano_v{n}_revisado_{int(time.time())}.json'))
            feedbacks = feedbacks + [(n, correcao)]
        nomes = nomes_originais(meta, arqs)
        _diagnostico_enquadramento(pid, cli_id, arqs, nomes, papeis, pasta, meta, sb)
        exigidos, casados = exigir_takes(nomes, papeis, meta.get('anexos') or [], [meta.get('briefing', '')] + [t for nn, t in feedbacks if nn < n][-1:])
        etapa('A IA está montando o storytelling no DNA do cliente' if not anterior else 'A IA está aplicando o seu ajuste', 28)
        pronto = os.path.join(pasta, f'plano_v{n}.json')
        if os.path.exists(pronto):                     # retomada: reaproveita o plano já pago desta versão
            pl = json.load(open(pronto))
        else:
            import plano as plano_ia                   # só o VPS precisa da IA; o render externo não
            g = meta.get('gancho') or {}; exata, ideia = gancho_texto(g.get('frase'))
            tpl = g.get('template')
            pedido_gancho = ''
            if tpl == 'nenhum': pedido_gancho = 'Gancho definido pelo editor: SEM título no gancho (usar_titulo = false).'
            else:
                if tpl in ('premium', 'caixa', 'impacto'): pedido_gancho = f'Gancho definido pelo editor: título no template {tpl} (o motor desenha).'
                if exata: pedido_gancho += f' Texto do título EXATO, não altere: "{exata}". Preencha titulo.tema com a palavra-chave dessa frase e escolha a fala de abertura que combina com ela.'
                if ideia: pedido_gancho += (f' Ideia do editor para o gancho (inspiração, NÃO é o texto final do título): "{ideia}". Crie um título curto (até 8 palavras), natural e no tom do cliente a partir dela;'
                                            ' se ela citar uma fala do vídeo, abra com essa fala.')
            sens = (vocab or {}).get('sensiveis') or {}; pedido_sens = ''
            if sens.get('termos'):
                pedido_sens = ('Termos sensíveis (nomes comerciais de medicamentos: ' + ', '.join(sens['termos'][:8]) + '): NÃO use em título, destaque nem palavra solta, e prefira não escolher trechos que só '
                               'citem marca; a legenda troca por termos genéricos. Prefira trechos que falem das medicações como classe e do cuidado com o rim, sem promessa de efeito nem tom de venda.')
            anexos_ia = [a for a in (meta.get('anexos') or []) if not a.get('capa_final') and a not in casados]       # o mesmo take de novo não é inserção: é pedido de uso
            pedido_sens += (' ' + avaliacao_anterior(meta, n)) if n > 1 and not correcao else ''
            mt = marcas_texto(meta, nomes, pal)
            if mt: pedido_sens += '\n' + mt
            if exigidos: pedido_sens += ' O editor pediu que ' + ', '.join(f'o Arquivo {i + 1} ({nomes[i]})' for i in sorted(exigidos)) + ' ENTRE no storytelling, com falas dele (não como inserção em tela cheia).'
            if any(a.get('capa_final') for a in (meta.get('anexos') or [])): pedido_sens += ' Uma capa final (CRM e RQE) será acrescentada depois do último trecho: o fechamento da fala não precisa citar o CRM.'
            falas = []                                  # quadros dos takes de fala: a IA evita trecho com gente entrando, produto sendo trocado etc.
            for i, a in enumerate(arqs):
                if papeis[i] != 'fala': continue
                try:
                    d_ = montagem.duracao(a); jpg, tempos = montagem.folha_take(a, os.path.join(pasta, f'fala_{i + 1:02d}_folha.jpg'), largura=200, k=min(16, max(6, int(d_ / 2))))
                    if jpg: falas.append({'n': i + 1, 'nome': nomes[i], 'dur': d_, 'jpg': jpg, 'tempos': tempos})
                except Exception as e: print('folha da fala:', str(e)[:100], flush=True)
            pl = None
            if os.environ.get('BORA_TRES_ETAPAS', '1') != '0':      # mapa dos originais -> roteiro validado -> plano de edição (cada um salvo)
                try:
                    pl = tres_etapas(meta, n, pasta, pal, nomes, papeis, arqs, cliente, dna, regras, feedbacks, brolls, falas, exigidos, anexos_ia,
                                     '\n'.join(x for x in (pedido_gancho, pedido_sens.strip()) if x), correcao, etapa, sb, pid, anterior)
                except Exception as e:
                    import traceback; traceback.print_exc(); print('três etapas falhou, usando o plano direto:', str(e)[:150], flush=True); pl = None
            if pl is None and anterior and os.environ.get('BORA_AJUSTE_PONTUAL', '1') != '0' and not any(a.get('versao') == n - 1 for a in anexos_ia):      # ajuste PONTUAL: só muda o que o pedido cita, o resto fica travado
                pedido_aj = correcao or (feedbacks[-1][1] if feedbacks else '')
                sel = selecoes_texto(meta, n, anterior, pal, arqs, pasta)
                if sel: pedido_aj = (pedido_aj + '\n' if pedido_aj else '') + sel
                if pedido_aj.strip():
                    etapa('A IA está ajustando só os trechos pedidos', 28)
                    try:
                        pl = plano_ia.ajustar(pal, nomes, cliente, dna, regras, anterior, pedido_aj, brolls, falas, papeis,
                                              '\n'.join(x for x in (pedido_gancho, pedido_sens.strip()) if x))
                    except Exception as e:
                        print('ajuste pontual falhou, refazendo o plano:', str(e)[:150], flush=True); pl = None
                    if pl is not None and exigidos:
                        G_ = montagem.indice_global(pal)
                        if set(exigidos) - {G_[int(sg['palavra_inicio'])][0] for sg in pl['segmentos']}: pl = None
            if pl is None:
                pl = plano_ia.gerar(pal, nomes, cliente, dna, regras, '\n'.join(x for x in (meta.get('briefing', ''), pedido_gancho, pedido_sens.strip()) if x), anterior, feedbacks, anexos_ia, papeis, brolls, exigidos=exigidos, falas=falas)
        pl['_marcas'] = onde_entraram({**pl, '_broll_arquivos': [b['ai'] for b in brolls]}, meta, nomes, pal, arqs, pasta)
        pl['_anexos'] = [a for a in (meta.get('anexos') or []) if a not in casados]; pl['_exigidos'] = [nomes[i] for i in sorted(exigidos)]; pl['_exigidos_i'] = sorted(exigidos)
        pl['_gancho'] = {**(meta.get('gancho') or {}), 'frase': gancho_texto((meta.get('gancho') or {}).get('frase'))[0]}   # template e título EXATO (observação do editor não vira título)
        pl['_broll_arquivos'] = [b['ai'] for b in brolls]
        escolhidos = {int(b['video']) for b in pl.get('broll') or []}
        if escolhidos: etapa('Medindo a estabilidade das cenas escolhidas', 30)
        for b in brolls:                               # mede o tremor só dos takes que a IA escolheu (cache pros ajustes)
            if b['n'] in escolhidos and b['tremor'] is None:
                b['tremor'] = montagem.tremor_por_segundo(arqs[b['ai']], os.path.join(pasta, f"broll_{b['ai'] + 1:02d}_tremor.json"))
        pl['_broll_tremor'] = [b['tremor'] for b in brolls]
        ESTADO_ROSTOS.clear(); pl['_rostos'] = medir_rostos(pl, pal, arqs, pasta, etapa)
        try:                                              # o que o enquadramento conseguiu medir (aparece no projeto, pra conferir)
            m3 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
            m3[f'enquadramento_v{n}'] = {nomes[int(k)] if int(k) < len(nomes) else k: v for k, v in ESTADO_ROSTOS.items()}; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m3})
        except Exception as e: print('estado do enquadramento:', str(e)[:100], flush=True)
        json.dump(pl, open(os.path.join(pasta, f'plano_v{n}.json'), 'w'), ensure_ascii=False, indent=1)
        import re
        novas = {k: v for k, v in {'leg': (pl.get('cores') or {}).get('legenda', ''), 'dest': (pl.get('cores') or {}).get('destaque', '')}.items()
                 if re.fullmatch(r'#[0-9A-Fa-f]{6}', (v or '').strip())}
        if novas:                                       # cor pedida no feedback vale desta versão em diante
            cores.update(novas)
            sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'cores_texto': {**(proj.get('cores_texto') or {}), **novas}})
        pac.update({'plano': f'plano_v{n}.json', 'altura': 854})
    elif tipo == 'final':
        planos = sorted(glob.glob(os.path.join(pasta, 'plano_v*.json')), key=lambda x: int(x.rsplit('_v', 1)[1].split('.')[0]))
        if not planos: raise RuntimeError('não encontrei o plano aprovado deste projeto')
        pl = json.load(open(planos[-1]))
        if not pl.get('_anexos') and meta.get('anexos'):
            pl['_anexos'] = meta['anexos']; json.dump(pl, open(planos[-1], 'w'), ensure_ascii=False, indent=1)
        w, h = montagem.sondar(arqs[0])[:2]
        altura = min(max(w, h), 3840); altura -= altura % 2
        pac.update({'plano': os.path.basename(planos[-1]), 'altura': altura, 'nome': _final_nome(cliente['nome'], proj['titulo'])})
        pac['crf_final'] = crf_4k(meta)                  # o Acer só obedece: quem decide a qualidade é o servidor
    else:
        raise RuntimeError('tipo de pedido desconhecido: ' + tipo)
    pac['anexos'] = [os.path.basename(a['caminho']) for a in (pl.get('_anexos') or []) if os.path.exists(a.get('caminho', '')) or
                     os.path.exists(os.path.join(pasta, os.path.basename(a.get('caminho', ''))))]
    pac['cores'] = cores
    if meta.get('sfx'):                                   # efeitos sonoros automáticos ligados no projeto
        try:
            import biblioteca
            pac['sfx'] = biblioteca.preparar_sfx(pasta)
        except Exception as e:                            # sem Drive ou sem a pasta: o vídeo sai igual, sem os sons
            print('efeitos sonoros indisponíveis, segue sem eles:', e, flush=True); pac['sfx'] = None; pac['sfx_aviso'] = str(e)[:150]
    json.dump(pac, open(os.path.join(pasta, f"pacote_{pac['tipo']}_v{pac['n']}.json"), 'w'), ensure_ascii=False, indent=1)
    return pac

def renderizar(pac, etapa, pasta=None):
    """Parte pesada (VPS ou render externo): só ffmpeg, a partir dos arquivos da pasta. Não fala com o banco.
    Devolve o resultado: arquivos gerados (nomes na pasta), duração e a verificação da prévia."""
    pid = pac['projeto_id']; pasta = pasta or os.path.join(TRAB, pid)
    arqs = [os.path.join(pasta, a) for a in pac['arquivos']]
    pal = [json.load(open(os.path.join(pasta, t))) for t in pac['transcricoes']]
    pl = json.load(open(os.path.join(pasta, pac['plano'])))
    pl['_anexos'] = [{**a, 'caminho': os.path.join(pasta, os.path.basename(a.get('caminho', '')))} for a in (pl.get('_anexos') or [])]
    cores, n = pac['cores'], pac['n']
    if pac['tipo'] == 'previa':
        etapa('Cortando pausas e montando', 40)
        saida_txt = os.path.join(pasta, f'textos_v{n}')
        base, hdr, dur, tokens_v = _renderizar(pid, pl, arqs, pal, 854, cores, saida_txt, etapa, (42, 72), pasta=pasta, sfx=pac.get('sfx'), vocab=pac.get('vocabulario'))
        etapa('Textos, título e destaques', 76)
        previa = os.path.join(pasta, f'previa_v{n}.mp4')
        montagem.aplicar_textos(base, saida_txt + '.ass', previa, hdr, 24)
        etapa('Conferindo a prévia (áudio, palavras, resolução, anexos)', 88)
        import validacao
        n_dest = len(pl.get('destaques') or []) if any(',K,' in l for l in open(saida_txt + '.ass')) else 0
        verif = validacao.verificar(previa, pl, tokens_v, dur, 854, hdr, insercoes.APLICADAS if pl.get('insercoes') else 0, n_dest, vocab=pac.get('vocabulario'), base=base)
        if pl.get('_exigidos'):
            G = montagem.indice_global(pal); usados = {G[int(sg['palavra_inicio'])][0] for sg in pl['segmentos']}
            faltou = [nm for nm, i in zip(pl['_exigidos'], pl.get('_exigidos_i') or []) if i not in usados]
            verif.insert(-2, {'item': 'Takes pedidos entraram', 'ok': not faltou, 'detalhe': ('todos usados: ' + ', '.join(pl['_exigidos'])) if not faltou else 'ficou de fora: ' + ', '.join(faltou)})
        if (pac.get('vocabulario') or {}).get('sensiveis'):
            sobra = validacao.termos_na_tela(open(saida_txt + '.ass', encoding='utf-8').read(), pac['vocabulario'])
            verif.insert(-2, {'item': 'Sem nome de produto no texto', 'ok': not sobra, 'detalhe': 'legendas, destaques e título com termos genéricos' if not sobra else 'sobrou na tela: ' + ', '.join(sobra)})
        return {'arquivos': [os.path.basename(previa)], 'dur': dur, 'verif': verif}
    altura, nome = pac['altura'], pac['nome']
    etapa('Renderizando o final a partir dos originais', 8)
    fim = os.path.join(pasta, 'final'); os.makedirs(fim, exist_ok=True)
    saida_txt = os.path.join(fim, nome + '_legendas')
    com_ins = bool(pl.get('insercoes') and pl.get('_anexos'))
    # pesos medidos (4K): cards e textos levam tempo parecido por quadro
    passes = ([('Encaixando os cards no 4K', 1.0, 40, 70)] if com_ins else []) + [('Aplicando os textos no 4K', 1.0, 70 if com_ins else 40, 99)]
    anda = Andamento(etapa, passes)
    base, hdr, dur, _ = _renderizar(pid, pl, arqs, pal, altura, cores, saida_txt, etapa, (10, 40), pasta=pasta, anda=anda if com_ins else None, sfx=pac.get('sfx'), vocab=pac.get('vocabulario'), crf_i=CRF_INTER.get(int(pac.get('crf_final') or 24), 14))
    k = 1 if com_ins else 0
    leg = os.path.join(fim, nome + f'_{altura}p_legendado.mp4')    # entrega só a versão legendada (economiza um render 4K)
    montagem.aplicar_textos(base, saida_txt + '.ass', leg, hdr, int(pac.get('crf_final') or 24), prog=anda.inicio(k, montagem.quadros(base)))
    if os.path.exists(saida_txt + '.srt'): os.remove(saida_txt + '.srt')
    etapa('Conferindo o 4K (resolução, HDR e taxa de bits)', 99)
    try:
        import validacao
        verif = validacao.verificar_final(leg, dur, altura, hdr, int(pac.get('crf_final') or 24))
    except Exception as e:
        verif = [{'item': 'Verificação do 4K', 'ok': None, 'detalhe': 'não verificado: ' + str(e)[:80]}]
    zipf = os.path.join(fim, nome + '_final.zip')
    if os.path.exists(zipf): os.remove(zipf)
    import zipfile                                     # sem compressão (zip -0), funciona igual no Windows
    with zipfile.ZipFile(zipf, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        z.write(leg, os.path.basename(leg))
    for x in (base, saida_txt + '.ass'):
        if os.path.exists(x): os.remove(x)
    return {'arquivos': [os.path.relpath(zipf, pasta)], 'dur': dur, 'verif': verif}

def concluir(pac, res, sb, pasta=None, nota=None):
    """Grava o resultado no banco e no Storage (sempre no VPS). Mesmo efeito de antes da separação."""
    pid, n, cli_id = pac['projeto_id'], pac['n'], pac['cliente_id']; pasta = pasta or os.path.join(TRAB, pid)
    if pac['tipo'] == 'previa':
        pl = json.load(open(os.path.join(pasta, pac['plano'])))
        previa = os.path.join(pasta, res['arquivos'][0])
        caminho = f'{cli_id}/{pid}/v{n}.mp4'; _subir(sb, caminho, previa, 'video/mp4')
        tl = _timeline(previa, pasta, n)                    # faixa com 1 quadro por segundo (timeline do app, pra marcar trechos no ajuste)
        if tl:
            try: _subir(sb, f'{cli_id}/{pid}/v{n}_timeline.jpg', tl['arq'], 'image/jpeg'); tl = {'path': f'{cli_id}/{pid}/v{n}_timeline.jpg', 'n': tl['n'], 'w': tl['w'], 'h': tl['h']}
            except Exception as e: print('timeline:', str(e)[:100], flush=True); tl = None
        sb('PATCH', f"/rest/v1/versoes?id=eq.{pac['versao_id']}", {'status': 'revisao', 'previa_path': caminho, 'resumo': (pl.get('resumo') or f'Versão {n}') + (f" Ainda não aplicado (o motor não faz ainda): {pl['nao_feito']}" if (pl.get('nao_feito') or '').strip() else '')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'status': 'revisao'})
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m.update({'andamento': None, 'progresso': None, 'dur': f"{round(res['dur'])} s", f'validacao_v{n}': res.get('verif')})
        if tl: m[f'timeline_v{n}'] = tl
        if pl.get('_marcas'): m[f'marcas_v{n}'] = pl['_marcas']
        if pl.get('usar_titulo'): m.update({'rotulo': pl['titulo'].get('rotulo'), 'pergunta': pl['titulo'].get('pergunta')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
        if nota:                                          # nota da revisão interna (a que foi entregue)
            m[f'nota_ia_v{n}'] = nota; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
        return
    zipf = os.path.join(pasta, res['arquivos'][0])
    m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
    m.update({'andamento': None, 'progresso': None, 'final_pronto': True, 'final_zip': zipf, 'final_nome': os.path.basename(zipf),
              'final_mb': round(os.path.getsize(zipf) / 1048576),
              'final_crf': pac.get('crf_final'), 'validacao_final': res.get('verif')})
    sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})

NOTA_MIN = float(os.environ.get('BORA_NOTA_MIN', '7.5'))     # abaixo disso (ou algum critério abaixo de 6) a prévia volta pra correção antes de chegar ao editor
REVISOES = int(os.environ.get('BORA_REVISOES', '0'))           # rodadas de correção automática por versão

def avaliar_previa(pac, res, sb, pasta=None, esperado=()):
    """Nota de 0 a 10 da IA pra prévia (critérios com motivo e problemas com o segundo), ou None se não der pra avaliar."""
    if os.environ.get('BORA_NOTA_IA', '1') == '0': return None
    try:
        import avaliacao
        pid, n = pac['projeto_id'], pac['n']; pasta = pasta or os.path.join(TRAB, pid)
        previa = os.path.join(pasta, res['arquivos'][0]); pl = json.load(open(os.path.join(pasta, pac['plano'])))
        pal = [json.load(open(os.path.join(pasta, t))) for t in pac['transcricoes']]
        ant = sb('GET', f'/rest/v1/versoes?projeto_id=eq.{pid}&numero=eq.{n - 1}&select=feedback') if n > 1 else []
        meta0 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        pedido = ' '.join(x for x in ((ant[0].get('feedback') if ant else '') or '', meta0.get('briefing') or '') if x).strip()
        cli = (sb('GET', f"/rest/v1/clientes?id=eq.{pac['cliente_id']}&select=nome,segmento") or [{}])[0]
        dna = (sb('GET', f"/rest/v1/dna_ativo?cliente_id=eq.{pac['cliente_id']}&select=dna") or [{}])[0].get('dna') or {}
        contexto = f"cliente {cli.get('nome')} ({cli.get('segmento') or 'segmento não informado'}). DNA do cliente: " + json.dumps(dna, ensure_ascii=False)[:1800]
        return avaliacao.avaliar(previa, pl, pal, pedido, res.get('verif'), pasta, contexto, esperado)
    except Exception as e:
        print('nota da IA:', str(e)[:150], flush=True); return None

def _timeline(previa, pasta, n, w=96):
    """Uma imagem com 1 quadro por segundo lado a lado (SDR só pra mostrar no app)."""
    try:
        dur = montagem.duracao(previa); k = max(1, min(120, int(dur))); h = round(w * 16 / 9 / 2) * 2
        arq = os.path.join(pasta, f'timeline_v{n}.jpg')
        tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,'
        for t_ in (tm, ''):
            r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', previa, '-vf', f'fps=1,{t_}scale={w}:{h},tile={k}x1', '-frames:v', '1', '-q:v', '5', arq], capture_output=True)
            if r.returncode == 0 and os.path.exists(arq): return {'arq': arq, 'n': k, 'w': w, 'h': h}
    except Exception as e: print('timeline:', str(e)[:100], flush=True)
    return None

TIPOS_MARCA = {'principal': 'FALA PRINCIPAL (tem que entrar)', 'bastidor': 'USAR COMO BASTIDOR (cena de apoio/B-roll ou bastidor no vídeo)', 'considerar': 'CONSIDERAR SE ENCAIXAR (use se melhorar a história)'}

def marcas_texto(meta, nomes, pal):
    """Trechos que o editor marcou nos brutos ao pedir o vídeo ([{arquivo, t0, t1, tipo}] em original_meta.marcas), ligados às palavras."""
    out = []
    G0 = 0; inicio = []
    for pw in pal: inicio.append(G0); G0 += len(pw)
    for k, m in enumerate((meta or {}).get('marcas') or [], 1):
        try: ai = [x.casefold() for x in nomes].index(str(m.get('arquivo', '')).casefold())
        except ValueError: continue
        ws = [inicio[ai] + j for j, w in enumerate(pal[ai]) if w['e'] > float(m['t0']) and w['s'] < float(m['t1'])]
        fala = f"palavras {ws[0]}-{ws[-1]}" if ws else 'sem fala (use a imagem)'
        out.append(f"Marca {k}: Arquivo {ai + 1} ({nomes[ai]}) de {float(m['t0']):.1f} a {float(m['t1']):.1f} s, {fala}: {TIPOS_MARCA.get(m.get('tipo'), m.get('tipo'))}")
    return ('Trechos marcados pelo editor nos brutos (responda cada um no campo marcas; fala principal TEM que entrar; bastidor sem fala vira cena de apoio):\n' + '\n'.join(out)) if out else ''

def onde_entraram(pl, meta, nomes, pal, arqs, pasta):
    """Pra cada trecho marcado: se entrou na prévia e em que segundo, ou o motivo de ter ficado de fora."""
    marcas = (meta or {}).get('marcas') or []
    if not marcas: return []
    try: _, tokens, _ = montagem.pecas(pl, arqs, pal, pasta)
    except Exception as e: print('marcas:', str(e)[:100], flush=True); tokens = []
    G = montagem.indice_global(pal); resp = {int(r.get('marca', 0)): r for r in pl.get('marcas') or []}; out = []
    amb = pl.get('_broll_arquivos') or []
    for k, m in enumerate(marcas, 1):
        try: ai = [x.casefold() for x in nomes].index(str(m.get('arquivo', '')).casefold())
        except ValueError: out.append({**m, 'entrou': False, 'motivo': 'arquivo não encontrado no projeto'}); continue
        t0, t1 = float(m['t0']), float(m['t1'])
        tem = [t for t in tokens if G[t['i']][0] == ai and t0 - 0.2 <= pal[ai][G[t['i']][1]]['s'] <= t1 + 0.2]
        onde = min(t['s'] for t in tem) if tem else None
        if onde is None and ai in amb:                     # vídeo sem fala usado como B-roll: entrou se a cena começa dentro do trecho
            vb = amb.index(ai) + 1
            for b in pl.get('broll') or []:
                if int(b.get('video', 0)) == vb and t0 - 0.5 <= float(b.get('inicio_s') or 0) <= t1:
                    sel = [t for t in tokens if int(b['palavra_inicio']) <= t['i'] <= int(b['palavra_fim'])]
                    if sel: onde = min(t['s'] for t in sel); break
        r = resp.get(k) or {}
        out.append({**m, 'entrou': onde is not None, 'tempo_previa': round(onde, 1) if onde is not None else None,
                    'motivo': '' if onde is not None else (r.get('motivo') or 'a IA não explicou')})
    return out

def tres_etapas(meta, n, pasta, pal, nomes, papeis, arqs, cliente, dna, regras, feedbacks, brolls, falas, exigidos, anexos_ia, extra, correcao, etapa, sb, pid, anterior=None):
    """Mapa dos originais (uma vez por projeto) -> roteiro com falas literais (validado antes do render) -> plano de edição.
    Ajuste parte da versão escolhida (original_meta.base_ajuste = {para: n, base: k}; padrão a anterior): só texto preserva áudio e cortes;
    outro fechamento ou fala troca só a parte citada e registra o que entrou no lugar."""
    import etapas, plano as plano_ia
    etapas.CUSTO.clear(); t_ini = time.time()
    briefing = meta.get('briefing', '') or ''
    arq_mapa = os.path.join(pasta, 'mapa.json')
    if os.path.exists(arq_mapa): mapa = json.load(open(arq_mapa))
    else:
        etapa('Etapa 1: estudando os originais (mapa)', 26)
        mapa = etapas.mapear(pal, nomes, papeis, cliente, dna, regras, briefing, falas, brolls, marcas_texto(meta, nomes, pal))
        json.dump(mapa, open(arq_mapa, 'w'), ensure_ascii=False, indent=1)
    ba = meta.get('base_ajuste') or {}
    base = int(ba['base']) if ba.get('para') == n and ba.get('base') else n - 1
    rot_b = os.path.join(pasta, f'roteiro_v{base}.json'); pl_b = os.path.join(pasta, f'plano_v{base}.json')
    if correcao and anterior and os.path.exists(os.path.join(pasta, f'roteiro_v{n}.json')):     # revisão interna: corrige a própria versão
        base, rot_b = n, os.path.join(pasta, f'roteiro_v{n}.json')
    trocas, tipo, resumo_aj = [], 'novo', ''
    if (base == n or n > 1) and os.path.exists(rot_b) and (base == n or os.path.exists(pl_b)) and not any(a.get('versao') == n - 1 for a in anexos_ia):
        rot0, ant = json.load(open(rot_b)), (anterior if base == n else json.load(open(pl_b)))
        pedido = correcao or (feedbacks[-1][1] if feedbacks else '')
        corr = meta.get(f'roteiro_corrigir_v{base}') or []
        if corr: pedido += '\nCorreções no roteiro (índice [k] da lista): ' + '; '.join(f"parte [{c['parte']}]: {c['texto']}" for c in corr)
        sel = selecoes_texto(meta, n, ant, pal, arqs, pasta)
        if sel: pedido += '\n' + sel
        etapa(f'Etapa 2: ajustando o roteiro a partir da v{base}', 28)
        tipo, rot, trocas, resumo_aj = etapas.ajustar_roteiro(rot0, mapa, pal, nomes, papeis, cliente, dna, regras, pedido, interno=bool(correcao))
        etapa('Etapa 3: plano de edição (só o que mudou)', 32)
        extra2 = extra + ('\n' + etapas.texto_roteiro_para_plano(rot) if tipo == 'roteiro' else '')
        pl = plano_ia.ajustar(pal, nomes, cliente, dna, regras, ant, pedido, brolls, falas, papeis, extra2) or plano_ia.gerar(
            pal, nomes, cliente, dna, regras, '\n'.join(x for x in (briefing, extra2) if x), ant, feedbacks, anexos_ia, papeis, brolls, exigidos=exigidos, falas=falas)
        if tipo == 'so_texto':                         # só texto: áudio e cortes exatamente iguais aos da versão escolhida
            pl['segmentos'] = ant['segmentos']; pl['broll'] = ant.get('broll') or []; rot = rot0
        elif tipo == 'imagem':                          # imagem: mesmas falas, muda enquadramento/B-roll
            rot = rot0; pl = etapas.segmentos_do_roteiro(rot, {**pl, 'segmentos': pl['segmentos']})
        else:
            pl = etapas.segmentos_do_roteiro(rot, pl)
    else:
        etapa('Etapa 2: roteiro com as falas em sequência', 28)
        pedido = '\n'.join(x for x in (extra, correcao or '') if x)
        rot = etapas.roteirizar(mapa, pal, nomes, papeis, cliente, dna, regras, briefing, pedido, sorted(exigidos), meta.get('modo'))
        etapa('Etapa 3: plano de edição', 32)
        pl = plano_ia.gerar(pal, nomes, cliente, dna, regras, '\n'.join(x for x in (briefing, extra, etapas.texto_roteiro_para_plano(rot)) if x),
                            None, feedbacks, anexos_ia, papeis, brolls, exigidos=exigidos, falas=falas)
        pl = etapas.segmentos_do_roteiro(rot, pl)
    u = pl.get('_uso') or {}
    etapas.CUSTO.append({'etapa': 'plano de edição', 'segundos': None, 'entrada': u.get('entrada'), 'saida': u.get('saida'), 'modelo': pl.get('_modelo')})
    rot = etapas.completar(rot, pal, nomes, mapa)
    json.dump(rot, open(os.path.join(pasta, f'roteiro_v{n}.json'), 'w'), ensure_ascii=False, indent=1)
    try:
        rastreio, tempos = rastrear(mapa, rot, pl, pal, arqs, pasta)
        json.dump({'trechos': rastreio, 'tempos': tempos}, open(os.path.join(pasta, f'rastreio_v{n}.json'), 'w'), ensure_ascii=False, indent=1)
    except Exception as e: print('rastreio:', str(e)[:120], flush=True); rastreio, tempos = [], {}
    custo = {'etapas': list(etapas.CUSTO), 'segundos': round(time.time() - t_ini, 1), 'tipo_ajuste': tipo, 'base': base if n > 1 else None}
    pl['_roteiro'] = {'tipo': tipo, 'trocas': trocas, 'resumo_ajuste': resumo_aj}
    try:                                                # as três entregas ficam no projeto (o app mostra e deixa corrigir o roteiro)
        m2 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m2['mapa'] = {'tema': mapa.get('tema'), 'ideias_centrais': mapa.get('ideias_centrais'),
                      'trechos': [{k: t.get(k) for k in ('papel', 'quem', 'emocao', 'arquivo', 'inicio_s', 'fim_s', 'texto', 'qualidade', 'obs_imagem', 'resumo')} for t in mapa.get('trechos') or []]}
        m2[f'roteiro_v{n}'] = {'ideia_central': rot.get('ideia_central'), 'promessa': rot.get('promessa_da_abertura'), 'validacao': rot.get('validacao'), 'problemas': rot.get('problemas') or [],
                               'bastidores': rot.get('bastidores_considerados') or [], 'melhores': [{**x, 'texto': next((t.get('texto') for t in mapa.get('trechos') or [] if int(t['palavra_inicio']) == int(x['palavra_inicio'])), '')} for x in rot.get('melhores_falas') or []], 'tipo_ajuste': tipo, 'base': custo['base'], 'trocas': trocas,
                               'partes': [{k: p.get(k) for k in ('papel', 'arquivo', 'inicio_s', 'fim_s', 'texto', 'motivo', 'obs_imagem')} for p in rot['partes']]}
        if correcao and m2.get(f'custo_v{n}'):          # rodadas da revisão interna somam ao custo da versão (não apagam o mapa e o roteiro)
            ant_c = m2[f'custo_v{n}']; custo = {**custo, 'etapas': (ant_c.get('etapas') or []) + custo['etapas'], 'segundos': round((ant_c.get('segundos') or 0) + custo['segundos'], 1)}
        m2[f'custo_v{n}'] = custo
        m2[f'rastreio_v{n}'] = {'trechos': rastreio, 'tempos': tempos}
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m2})
    except Exception as e: print('salvar roteiro:', str(e)[:120], flush=True)
    return pl

def rastrear(mapa, rot, pl, pal, arqs, pasta):
    """Caminho de cada trecho do mapa nesta versão: entrou no roteiro? no plano? em que segundo da prévia? Se saiu, em que etapa e por quê.
    Também o tempo retirado (material, escolhido no roteiro, pausas cortadas no render)."""
    import montagem
    def cruza(a, b, lst): return [k for k, x in enumerate(lst) if int(x['palavra_inicio']) <= b and int(x['palavra_fim']) >= a]
    try: _, tokens, dur = montagem.pecas(pl, arqs, pal, pasta)
    except Exception as e: print('rastreio:', str(e)[:100], flush=True); tokens, dur = [], 0
    motivos = {int(x['palavra_inicio']): x.get('motivo', '') for x in (rot.get('melhores_falas') or []) + (rot.get('bastidores_considerados') or []) if not x.get('usou')}
    G = montagem.indice_global(pal); out = []
    for t in (mapa or {}).get('trechos') or []:
        a, b = int(t['palavra_inicio']), int(t['palavra_fim'])
        rp, ps = cruza(a, b, rot.get('partes') or []), cruza(a, b, pl.get('segmentos') or [])
        tk = [x for x in tokens if a <= x['i'] <= b]
        if tk: etapa_, motivo = 'prévia', ''
        elif ps: etapa_, motivo = 'render', 'cortado na montagem (pausa, borda ou palavra fora do trecho)'
        elif rp: etapa_, motivo = 'plano', 'o plano de edição não usou este trecho do roteiro'
        else: etapa_, motivo = 'roteiro', motivos.get(a) or ('erro/repetição' if t.get('papel') in ('erro', 'repeticao') else 'não escolhido pra história')
        out.append({'arquivo': t.get('arquivo'), 'inicio_s': t.get('inicio_s'), 'fim_s': t.get('fim_s'), 'texto': t.get('texto', ''), 'papel': t.get('papel'), 'quem': t.get('quem'),
                    'emocao': t.get('emocao'), 'roteiro': [k + 1 for k in rp], 'plano': [k + 1 for k in ps], 'na_previa': round(min(x['s'] for x in tk), 1) if tk else None,
                    'saiu_em': None if tk else etapa_, 'motivo': motivo})
    falado = lambda ws: sum(w['e'] - w['s'] for w in ws)
    material = sum(falado(pw) for pw in pal)
    escolhido = sum(pal[G[b][0]][G[b][1]]['e'] - pal[G[a][0]][G[a][1]]['s'] for a, b in ((int(s['palavra_inicio']), int(s['palavra_fim'])) for s in pl.get('segmentos') or []))
    tempos = {'material_s': round(material, 1), 'escolhido_s': round(escolhido, 1), 'previa_s': round(dur, 1),
              'tirado_roteiro_s': round(max(0, material - escolhido), 1), 'tirado_pausas_s': round(max(0, escolhido - dur), 1)}
    return out, tempos

def selecoes_texto(meta, n, anterior, pal, arqs, pasta):
    """Trechos que o editor marcou na timeline da versão anterior ([{t0, t1, texto}] em original_meta.selecoes_v{n-1}), já ligados às palavras e itens do plano."""
    sels = (meta or {}).get(f'selecoes_v{n - 1}') or []
    if not sels or not anterior: return ''
    try:
        _, tokens, _ = montagem.pecas(anterior, arqs, pal, pasta)
    except Exception as e:
        print('seleções:', str(e)[:100], flush=True); tokens = []
    out = []
    for k, x in enumerate(sels, 1):
        t0, t1 = float(x.get('t0', 0)), float(x.get('t1', 0)); dentro = [t for t in tokens if t['e'] > t0 and t['s'] < t1]
        if dentro:
            a, b = min(t['i'] for t in dentro), max(t['i'] for t in dentro)
            segs = [i for i, sg in enumerate(anterior.get('segmentos') or []) if int(sg['palavra_inicio']) <= b and int(sg['palavra_fim']) >= a]
            brs = [i for i, br in enumerate(anterior.get('broll') or []) if int(br['palavra_inicio']) <= b and int(br['palavra_fim']) >= a]
            dst = [i for i, d in enumerate(anterior.get('destaques') or []) if int(d['palavra_inicio']) <= b and int(d['palavra_fim']) >= a]
            onde = f"palavras {a}-{b} (\"{' '.join(t['tok'] for t in dentro)}\"); segmento(s) {segs}" + (f'; B-roll {brs}' if brs else '') + (f'; destaque(s) {dst}' if dst else '')
        else: onde = 'sem fala nesse intervalo'
        out.append(f"Trecho marcado {k} ({t0:.1f} s a {t1:.1f} s do vídeo): {onde}. Pedido: {x.get('texto', '').strip() or '(ver pedido geral)'}")
    return 'Trechos que o editor marcou na timeline (mexa só nesses):\n' + '\n'.join(out)

def avaliacao_anterior(meta, n):
    """Avaliação da versão anterior (nota da IA por categoria, com motivo e problemas, e a nota do editor) como pedido de melhoria pro ajuste."""
    ia, ed = (meta or {}).get(f'nota_ia_v{n - 1}'), (meta or {}).get(f'nota_editor_v{n - 1}')
    if not ia: return ''
    cats = ' | '.join(f"{k} {c['nota']}: {c['motivo']}" for k, c in (ia.get('criterios') or {}).items() if isinstance(c, dict))
    probs = ' | '.join(f"{round(p['segundo'])} s: {p['problema']}" for p in ia.get('problemas') or [])
    return (f"Avaliação da v{n - 1} por um editor sênior (nota {ia['nota']} de 10" + (f"; o editor deu {ed['nota']}" if ed else '') + f"): {ia.get('motivo', '')} "
            f"Por categoria: {cats}. Problemas: {probs or 'nenhum'}. Neste ajuste, além do pedido do editor (que manda), melhore cada categoria que ficou abaixo de 8, "
            "sem desfazer o que estava bom. Pessoa cortada na borda: quadro 'total'.")

def passou(nota):
    return nota is None or (nota['nota'] >= NOTA_MIN and all(c['nota'] >= 6 for c in nota['criterios'].values()))

def texto_correcao(nota):
    """Pedido de correção pra IA a partir da avaliação interna."""
    fracos = [f"{k}: {c['motivo']}" for k, c in nota['criterios'].items() if c['nota'] < 8]
    dica = ''
    if nota['criterios'].get('enquadramento', {}).get('nota', 10) < 7:
        dica = " Pessoas cortadas na borda: nesses trechos use quadro 'total' (sem zoom), principalmente com duas pessoas no quadro."
    return (f"Revisão interna antes de entregar (nota {nota['nota']}): faça estas mudanças e mantenha todo o resto igual. "
            + ' | '.join(f"{round(p['segundo'])} a {round(p.get('fim', p['segundo']))} s: {p['problema']} -> MUDANÇA: {p.get('mudanca_esperada', '')}" for p in nota['problemas'])
            + ' | ' + ' | '.join(fracos) + dica)

def revisar_e_concluir(p, pac, res, etapa, sb, render):
    """Antes de entregar: a IA dá nota e diz, por trecho, o que falhou e a MUDANÇA esperada. Abaixo do mínimo, corrige só esses trechos (ajuste pontual)
    e a rodada seguinte confere uma a uma se as mudanças aconteceram. Entrega a melhor rodada; se nenhuma resolveu, marca 'Precisa de decisão editorial'
    com os trechos e as opções. render(pac) -> res."""
    pasta = os.path.join(TRAB, pac['projeto_id']); n = pac['n']; rodadas = []; esperado = []
    for k in range(REVISOES + 1):
        etapa('Revisão interna: um editor sênior está conferindo a prévia', 92 if k == 0 else 93)
        nota = avaliar_previa(pac, res, sb, esperado=[f"{round(x['segundo'])} a {round(x.get('fim', x['segundo']))} s: {x.get('mudanca_esperada', '')}" for x in esperado])
        copia_p, copia_v = os.path.join(pasta, f'plano_v{n}_rodada{k}.json'), os.path.join(pasta, f'previa_v{n}_rodada{k}.mp4')
        shutil.copyfile(os.path.join(pasta, pac['plano']), copia_p); shutil.copyfile(os.path.join(pasta, res['arquivos'][0]), copia_v)
        rot_atual = os.path.join(pasta, f'roteiro_v{n}.json')        # o roteiro desta rodada (o app mostra o da rodada entregue)
        if os.path.exists(rot_atual): shutil.copyfile(rot_atual, os.path.join(pasta, f'roteiro_v{n}_rodada{k}.json'))
        try: snap = (sb('GET', f"/rest/v1/projetos?id=eq.{pac['projeto_id']}&select=original_meta")[0]['original_meta'] or {}).get(f'roteiro_v{n}')
        except Exception: snap = None
        rodadas.append((nota['nota'] if nota else -1, k, nota, dict(res), copia_p, copia_v, snap))
        if passou(nota) or k == REVISOES: break
        esperado = [x for x in nota.get('problemas') or [] if x.get('mudanca_esperada')]
        etapa(f"Revisão interna: nota {str(nota['nota']).replace('.', ',')}, corrigindo antes de te enviar ({k + 1}/{REVISOES})", 30)
        pac = preparar(p, etapa, sb, correcao=texto_correcao(nota))
        res = render(pac)
    _, k, nota, res, copia_p, copia_v, snap = max(rodadas, key=lambda r: (r[0], -r[1]))      # empate: a rodada mais antiga (a correção não melhorou)
    shutil.copyfile(copia_p, os.path.join(pasta, pac['plano'])); shutil.copyfile(copia_v, os.path.join(pasta, res['arquivos'][0]))
    rot_k = os.path.join(pasta, f'roteiro_v{n}_rodada{k}.json')
    if os.path.exists(rot_k): shutil.copyfile(rot_k, os.path.join(pasta, f'roteiro_v{n}.json'))
    if snap:                                                      # o roteiro no app é o da rodada que foi entregue
        try:
            m3 = sb('GET', f"/rest/v1/projetos?id=eq.{pac['projeto_id']}&select=original_meta")[0]['original_meta'] or {}
            m3[f'roteiro_v{n}'] = snap; sb('PATCH', f"/rest/v1/projetos?id=eq.{pac['projeto_id']}", {'original_meta': m3})
        except Exception as e: print('roteiro da rodada entregue:', str(e)[:100], flush=True)
    if nota:
        nota = {**nota, 'rodadas': [{'nota': r[0], 'rodada': r[1], 'conferencia': (r[2] or {}).get('conferencia') or []} for r in rodadas], 'entregue': k}
        if not passou(nota):                                   # nenhuma rodada resolveu: o editor decide, com o trecho marcado e as opções
            ult = rodadas[-1][2] or {}
            nao = [c['mudanca'] for c in ult.get('conferencia') or [] if not c.get('aconteceu')]
            nota['decisao_editorial'] = {'trechos': [{'inicio': x['segundo'], 'fim': x.get('fim', x['segundo']), 'problema': x['problema'],
                                                      'mudanca_esperada': x.get('mudanca_esperada', ''), 'opcoes': x.get('opcoes') or []} for x in nota.get('problemas') or []],
                                         'nao_resolvido': nao}
    concluir(pac, res, sb, nota=nota if nota else False)

def executar(p, etapa, sb):
    """Tudo no próprio VPS (o caminho de sempre)."""
    pac = preparar(p, etapa, sb)
    if pac['tipo'] == 'previa': revisar_e_concluir(p, pac, renderizar(pac, etapa), etapa, sb, lambda pc: renderizar(pc, etapa))
    else: concluir(pac, renderizar(pac, etapa), sb)
