"""Motor de edição do Bora Studio.
nova_edicao / ajuste: transcreve os originais, a IA monta o plano no DNA do cliente, ffmpeg monta a prévia 480p (HDR do original),
  os textos entram no padrão aprovado e a prévia vai pro app.
final: renderiza de novo a partir dos ORIGINAIS na resolução nativa (4K), com e sem legenda + .srt, num .zip (sem compressão)."""
import glob, json, os, time, urllib.request
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

def _subir(sb, caminho, arq, tipo):
    url = os.environ['SUPABASE_URL'].rstrip('/') + f'/storage/v1/object/previas/{caminho}'
    r = urllib.request.Request(url, data=open(arq, 'rb').read(), method='POST',
                               headers={'apikey': os.environ['SUPABASE_SECRET'], 'Content-Type': tipo, 'x-upsert': 'true'})
    urllib.request.urlopen(r, timeout=600).read()

def _transcricoes(pid, arqs, etapa):
    pal = []
    for i, a in enumerate(arqs, 1):
        etapa(f'Transcrevendo {"o vídeo" if len(arqs) == 1 else f"o vídeo {i} de {len(arqs)}"}', 8 + int(17 * (i - 1) / len(arqs)))
        pal.append(montagem.transcrever(a, os.path.join(TRAB, pid, f'transcricao_{i:02d}.json')))
    if not any(pal): raise RuntimeError('não encontrei fala nos vídeos enviados')
    return pal

def _renderizar(pid, pl, arqs, pal, altura, cores, saida_base, etapa=None, faixa=(45, 80), crf_final=24, pasta=None, anda=None):
    pasta = pasta or os.path.join(TRAB, pid)
    pcs, tokens, dur = montagem.pecas(pl, arqs, pal, pasta)
    if not pcs: raise RuntimeError('o plano não gerou nenhum trecho')
    base = os.path.join(pasta, f'_base_{altura}.mp4')
    a, b = faixa
    prog = (lambda f, txt='Montando o vídeo a partir dos originais': etapa(txt, a + int((b - a) * f))) if etapa else None
    hdr = montagem.render_base(pcs, arqs, base, altura, 14, prog)
    anexos = [x for x in pl.get('_anexos', []) if os.path.exists(x.get('caminho', ''))]
    if pl.get('insercoes') and anexos:
        cb = anda.inicio(0, montagem.quadros(base)) if anda else (etapa('Encaixando imagens e vídeos anexados', b) if etapa else None)
        base = insercoes.aplicar(base, os.path.join(pasta, f'_ins_{altura}.mp4'), pl, tokens, dur, anexos, pasta, hdr, prog=cb)
    ro = textos.Roteiro(tokens, dur, cores.get('leg'), cores.get('dest'))
    if pl.get('usar_titulo') and pl.get('titulo', {}).get('tema'):
        seg1 = next((t['e'] for t in tokens if t['i'] >= pl['segmentos'][0]['palavra_fim']), 3.0)
        ro.titulo(pl['titulo'], min(max(seg1 + 1.0, 3.0), 5.5))
    for d in pl.get('destaques', []): ro.destaque(d)
    ro.gravar(saida_base)
    return base, hdr, dur, tokens

def _final_nome(cliente_nome, titulo):
    return ''.join(c for c in f"{cliente_nome}_{titulo}".replace(' ', '_') if c.isalnum() or c in '_-')[:60]

def pacote_transcricao(p, sb):
    """Pacote só de transcrição (pro computador de render), ou None se as transcrições já existem."""
    pid = p['projeto_id']
    meta = (sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta') or [{}])[0].get('original_meta') or {}
    arqs = _arquivos(pid, meta); pasta = os.path.join(TRAB, pid)
    if not arqs: return None
    falta = [i for i in range(1, len(arqs) + 1) if not os.path.exists(os.path.join(pasta, f'transcricao_{i:02d}.json'))]
    if not falta: return None
    v = (sb('GET', f"/rest/v1/versoes?id=eq.{p.get('versao_id')}&select=numero") or [{'numero': p.get('versao', 1)}])[0]
    return {'projeto_id': pid, 'tipo': 'previa', 'etapa': 'transcricao', 'versao_id': p.get('versao_id'), 'n': v['numero'], 'altura': 854,
            'arquivos': [os.path.basename(a) for a in arqs], 'transcricoes': [], 'plano': None, 'anexos': []}

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
             'dest': (proj.get('cores_texto') or {}).get('dest') or tx.get('destaque') or (((dna.get('paleta') or {}).get('cores') or [None])[0] if (dna.get('paleta') or {}).get('cores') else '#FFFFFF')}
    pasta = os.path.join(TRAB, pid); os.makedirs(pasta, exist_ok=True)
    etapa('Lendo o pedido', 5)
    pal = _transcricoes(pid, arqs, etapa)
    montagem.liberar_modelo()                         # memória livre pro render
    pac = {'projeto_id': pid, 'tipo': 'final' if tipo == 'final' else 'previa', 'versao_id': v['id'], 'n': v['numero'], 'cliente_id': cli_id,
           'cores': cores, 'arquivos': [os.path.basename(a) for a in arqs], 'transcricoes': [f'transcricao_{i:02d}.json' for i in range(1, len(arqs) + 1)]}

    if tipo in ('nova_edicao', 'ajuste'):
        n = v['numero']
        anterior = None
        ant_arq = os.path.join(pasta, f'plano_v{n - 1}.json')
        if n > 1 and os.path.exists(ant_arq): anterior = json.load(open(ant_arq))
        feedbacks = [(x['numero'], x['feedback']) for x in versoes if x.get('feedback') and x['numero'] < n]
        etapa('A IA está montando o storytelling no DNA do cliente' if not anterior else 'A IA está aplicando o seu ajuste', 28)
        pronto = os.path.join(pasta, f'plano_v{n}.json')
        if os.path.exists(pronto):                     # retomada: reaproveita o plano já pago desta versão
            pl = json.load(open(pronto))
        else:
            import plano as plano_ia                   # só o VPS precisa da IA; o render externo não
            pl = plano_ia.gerar(pal, arqs, cliente, dna, regras, meta.get('briefing', ''), anterior, feedbacks, meta.get('anexos') or [])
        pl['_anexos'] = meta.get('anexos') or []
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
    else:
        raise RuntimeError('tipo de pedido desconhecido: ' + tipo)
    pac['anexos'] = [os.path.basename(a['caminho']) for a in (pl.get('_anexos') or []) if os.path.exists(a.get('caminho', '')) or
                     os.path.exists(os.path.join(pasta, os.path.basename(a.get('caminho', ''))))]
    pac['cores'] = cores
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
        base, hdr, dur, tokens_v = _renderizar(pid, pl, arqs, pal, 854, cores, saida_txt, etapa, (42, 72), pasta=pasta)
        etapa('Textos, título e destaques', 76)
        previa = os.path.join(pasta, f'previa_v{n}.mp4')
        montagem.aplicar_textos(base, saida_txt + '.ass', previa, hdr, 24)
        etapa('Conferindo a prévia (áudio, palavras, resolução, anexos)', 88)
        import validacao
        n_dest = len(pl.get('destaques') or []) if any(',K,' in l for l in open(saida_txt + '.ass')) else 0
        verif = validacao.verificar(previa, pl, tokens_v, dur, 854, hdr, insercoes.APLICADAS if pl.get('insercoes') else 0, n_dest)
        return {'arquivos': [os.path.basename(previa)], 'dur': dur, 'verif': verif}
    altura, nome = pac['altura'], pac['nome']
    etapa('Renderizando o final a partir dos originais', 8)
    fim = os.path.join(pasta, 'final'); os.makedirs(fim, exist_ok=True)
    saida_txt = os.path.join(fim, nome + '_legendas')
    com_ins = bool(pl.get('insercoes') and pl.get('_anexos'))
    # pesos medidos (4K): cards e textos levam tempo parecido por quadro
    passes = ([('Encaixando os cards no 4K', 1.0, 40, 70)] if com_ins else []) + [('Aplicando os textos no 4K', 1.0, 70 if com_ins else 40, 99)]
    anda = Andamento(etapa, passes)
    base, hdr, dur, _ = _renderizar(pid, pl, arqs, pal, altura, cores, saida_txt, etapa, (10, 40), pasta=pasta, anda=anda if com_ins else None)
    k = 1 if com_ins else 0
    leg = os.path.join(fim, nome + f'_{altura}p_legendado.mp4')    # entrega só a versão legendada (economiza um render 4K)
    montagem.aplicar_textos(base, saida_txt + '.ass', leg, hdr, 24, prog=anda.inicio(k, montagem.quadros(base)))
    if os.path.exists(saida_txt + '.srt'): os.remove(saida_txt + '.srt')
    zipf = os.path.join(fim, nome + '_final.zip')
    if os.path.exists(zipf): os.remove(zipf)
    import zipfile                                     # sem compressão (zip -0), funciona igual no Windows
    with zipfile.ZipFile(zipf, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
        z.write(leg, os.path.basename(leg))
    for x in (base, saida_txt + '.ass'):
        if os.path.exists(x): os.remove(x)
    return {'arquivos': [os.path.relpath(zipf, pasta)], 'dur': dur}

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
        return
    zipf = os.path.join(pasta, res['arquivos'][0])
    m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
    m.update({'andamento': None, 'progresso': None, 'final_pronto': True, 'final_zip': zipf, 'final_nome': os.path.basename(zipf),
              'final_mb': round(os.path.getsize(zipf) / 1048576)})
    sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})

def executar(p, etapa, sb):
    """Tudo no próprio VPS (o caminho de sempre)."""
    pac = preparar(p, etapa, sb)
    concluir(pac, renderizar(pac, etapa), sb)
