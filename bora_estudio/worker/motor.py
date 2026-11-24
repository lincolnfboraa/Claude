"""Motor de edição do Bora Studio.
nova_edicao / ajuste: transcreve os originais, a IA monta o plano no DNA do cliente, ffmpeg monta a prévia 480p (HDR do original),
  os textos entram no padrão aprovado e a prévia vai pro app.
final: renderiza de novo a partir dos ORIGINAIS na resolução nativa (4K), com e sem legenda + .srt, num .zip (sem compressão)."""
import glob, json, os, re, time, urllib.request
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

def medir_rostos(pl, pal, arqs, pasta, etapa=None):
    """Rostos nos takes de fala usados no plano (cache por arquivo): o render usa pra não cortar ninguém no zoom e deixar respiro em cima."""
    if os.environ.get('BORA_ENQUADRAMENTO', '1') == '0': return {}
    try:
        import enquadramento
        G = montagem.indice_global(pal); usados = sorted({G[int(sg['palavra_inicio'])][0] for sg in pl.get('segmentos') or []})
        if etapa: etapa('Olhando onde estão as pessoas em cada take', 34)
        out = {}
        for ai in usados:
            cache = os.path.join(pasta, f'rostos_{ai + 1:02d}.json')
            if os.path.exists(cache): r = json.load(open(cache))
            else:
                r = enquadramento.rostos_no_tempo(arqs[ai]); json.dump(r, open(cache, 'w'))
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

def preparar(p, etapa, sb):
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
        nomes = nomes_originais(meta, arqs)
        _diagnostico_enquadramento(pid, cli_id, arqs, nomes, papeis, pasta, meta, sb)
        exigidos, casados = exigir_takes(nomes, papeis, meta.get('anexos') or [], [meta.get('briefing', '')] + [t for _, t in feedbacks[-1:]])
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
            if exigidos: pedido_sens += ' O editor pediu que ' + ', '.join(f'o Arquivo {i + 1} ({nomes[i]})' for i in sorted(exigidos)) + ' ENTRE no storytelling, com falas dele (não como inserção em tela cheia).'
            if any(a.get('capa_final') for a in (meta.get('anexos') or [])): pedido_sens += ' Uma capa final (CRM e RQE) será acrescentada depois do último trecho: o fechamento da fala não precisa citar o CRM.'
            falas = []                                  # quadros dos takes de fala: a IA evita trecho com gente entrando, produto sendo trocado etc.
            for i, a in enumerate(arqs):
                if papeis[i] != 'fala': continue
                try:
                    d_ = montagem.duracao(a); jpg, tempos = montagem.folha_take(a, os.path.join(pasta, f'fala_{i + 1:02d}_folha.jpg'), largura=200, k=min(16, max(6, int(d_ / 2))))
                    if jpg: falas.append({'n': i + 1, 'nome': nomes[i], 'dur': d_, 'jpg': jpg, 'tempos': tempos})
                except Exception as e: print('folha da fala:', str(e)[:100], flush=True)
            pl = plano_ia.gerar(pal, nomes, cliente, dna, regras, '\n'.join(x for x in (meta.get('briefing', ''), pedido_gancho, pedido_sens.strip()) if x), anterior, feedbacks, anexos_ia, papeis, brolls, exigidos=exigidos, falas=falas)
        pl['_anexos'] = [a for a in (meta.get('anexos') or []) if a not in casados]; pl['_exigidos'] = [nomes[i] for i in sorted(exigidos)]; pl['_exigidos_i'] = sorted(exigidos)
        pl['_gancho'] = {**(meta.get('gancho') or {}), 'frase': gancho_texto((meta.get('gancho') or {}).get('frase'))[0]}   # template e título EXATO (observação do editor não vira título)
        pl['_broll_arquivos'] = [b['ai'] for b in brolls]
        escolhidos = {int(b['video']) for b in pl.get('broll') or []}
        if escolhidos: etapa('Medindo a estabilidade das cenas escolhidas', 30)
        for b in brolls:                               # mede o tremor só dos takes que a IA escolheu (cache pros ajustes)
            if b['n'] in escolhidos and b['tremor'] is None:
                b['tremor'] = montagem.tremor_por_segundo(arqs[b['ai']], os.path.join(pasta, f"broll_{b['ai'] + 1:02d}_tremor.json"))
        pl['_broll_tremor'] = [b['tremor'] for b in brolls]
        pl['_rostos'] = medir_rostos(pl, pal, arqs, pasta, etapa)
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
        verif = validacao.verificar(previa, pl, tokens_v, dur, 854, hdr, insercoes.APLICADAS if pl.get('insercoes') else 0, n_dest, vocab=pac.get('vocabulario'))
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

def concluir(pac, res, sb, pasta=None):
    """Grava o resultado no banco e no Storage (sempre no VPS). Mesmo efeito de antes da separação."""
    pid, n, cli_id = pac['projeto_id'], pac['n'], pac['cliente_id']; pasta = pasta or os.path.join(TRAB, pid)
    if pac['tipo'] == 'previa':
        pl = json.load(open(os.path.join(pasta, pac['plano'])))
        previa = os.path.join(pasta, res['arquivos'][0])
        caminho = f'{cli_id}/{pid}/v{n}.mp4'; _subir(sb, caminho, previa, 'video/mp4')
        sb('PATCH', f"/rest/v1/versoes?id=eq.{pac['versao_id']}", {'status': 'revisao', 'previa_path': caminho, 'resumo': (pl.get('resumo') or f'Versão {n}') + (f" Ainda não aplicado (o motor não faz ainda): {pl['nao_feito']}" if (pl.get('nao_feito') or '').strip() else '')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'status': 'revisao'})
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m.update({'andamento': None, 'progresso': None, 'dur': f"{round(res['dur'])} s", f'validacao_v{n}': res.get('verif')})
        if pl.get('usar_titulo'): m.update({'rotulo': pl['titulo'].get('rotulo'), 'pergunta': pl['titulo'].get('pergunta')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
        import threading                                  # nota da IA em segundo plano: a prévia já foi entregue
        threading.Thread(target=_nota_ia, args=(pac, previa, pl, pasta, res.get('verif'), sb), daemon=True).start()
        return
    zipf = os.path.join(pasta, res['arquivos'][0])
    m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
    m.update({'andamento': None, 'progresso': None, 'final_pronto': True, 'final_zip': zipf, 'final_nome': os.path.basename(zipf),
              'final_mb': round(os.path.getsize(zipf) / 1048576),
              'final_crf': pac.get('crf_final'), 'validacao_final': res.get('verif')})
    sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})

def _nota_ia(pac, previa, pl, pasta, verif, sb):
    """Nota de 0 a 10 da IA pra prévia (critérios e problemas com o segundo). Falha não afeta nada."""
    if os.environ.get('BORA_NOTA_IA', '1') == '0': return
    try:
        import avaliacao
        pid, n = pac['projeto_id'], pac['n']
        pal = [json.load(open(os.path.join(pasta, t))) for t in pac['transcricoes']]
        ant = sb('GET', f'/rest/v1/versoes?projeto_id=eq.{pid}&numero=eq.{n - 1}&select=feedback') if n > 1 else []
        meta0 = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        pedido = ' '.join(x for x in ((ant[0].get('feedback') if ant else '') or '', meta0.get('briefing') or '') if x).strip()
        cli = (sb('GET', f"/rest/v1/clientes?id=eq.{pac['cliente_id']}&select=nome,segmento") or [{}])[0]
        dna = (sb('GET', f"/rest/v1/dna_ativo?cliente_id=eq.{pac['cliente_id']}&select=dna") or [{}])[0].get('dna') or {}
        contexto = f"cliente {cli.get('nome')} ({cli.get('segmento') or 'segmento não informado'}). DNA do cliente: " + json.dumps(dna, ensure_ascii=False)[:1800]
        nota = avaliacao.avaliar(previa, pl, pal, pedido, verif, pasta, contexto)
        if not nota: return
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m[f'nota_ia_v{n}'] = nota; sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
    except Exception as e:
        print('nota da IA:', str(e)[:150], flush=True)

def executar(p, etapa, sb):
    """Tudo no próprio VPS (o caminho de sempre)."""
    pac = preparar(p, etapa, sb)
    concluir(pac, renderizar(pac, etapa), sb)
