"""Análise dos brutos ANTES da seleção editorial.

Etapas (tempos sempre nos arquivos ORIGINAIS):
  1. Varredura econômica, sem IA: a cada 0,5 s mede tremor da câmera, nitidez, luz e áudio de cada take.
  2. Candidatos: frases faladas (pela transcrição) e trechos firmes dos vídeos de ambiente.
  3. Detalhe temporal nas bordas: a 30 quadros/s em volta da entrada e da saída de cada candidato
     (movimento brusco, mudança de imagem). Ambiente pode ter a borda ajustada; fala nunca (não corta palavra).
  4. Avaliação visual contextual pelo Claude: uma folha por take com 3 quadros por intervalo (entrada, meio, saída)
     + métricas + fala. Devolve descrição, problemas, função narrativa, nota, se é utilizável e incertezas.
  5. Catálogo: lista de intervalos avaliados. O planejador só pode escolher intervalos daqui.
Depois do render, `conferir_previa` olha a prévia montada (cortes e B-rolls) com o mesmo critério.

Liga com BORA_ANALISE_BRUTOS=1 no motor (desligado por padrão). Modelo da etapa visual: BORA_MODELO_VISUAL.
"""
import base64, json, os, subprocess, time
import numpy as np
import montagem

PASSO = 0.5                     # resolução da varredura (s)
FPS_VARR = 10                   # quadros/s da varredura
W, H = 144, 256                 # tamanho reduzido pra medir (vertical)
MODELO_VISUAL = os.environ.get('BORA_MODELO_VISUAL', 'claude-opus-5-5')
ESFORCO_VISUAL = os.environ.get('BORA_ESFORCO_VISUAL', 'low')
PRECOS = {'claude-opus-5-5': (4.0, 20.0), 'claude-sonnet-5-5': (2.0, 10.0), 'claude-haiku-5-5': (0.10, 0.50)}   # US$ por 1M tokens
FUNCOES = ['gancho', 'contexto', 'desenvolvimento', 'prova', 'emocao', 'cta', 'encerramento', 'ambiente', 'transicao', 'descartar']

def _gray(video, fps, ini=None, dur=None):
    a = ['ffmpeg', '-v', 'error'] + (['-ss', f'{ini:.3f}'] if ini else []) + ['-i', video] + (['-t', f'{dur:.3f}'] if dur else [])
    raw = subprocess.run(a + ['-an', '-vf', f'fps={fps},scale={W}:{H},format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8)[: len(raw) // (W * H) * W * H].reshape(-1, H, W).astype(np.float32)

def _nitidez(q):
    """Variância do laplaciano por quadro (maior = mais nítido)."""
    lap = 4 * q[:, 1:-1, 1:-1] - q[:, :-2, 1:-1] - q[:, 2:, 1:-1] - q[:, 1:-1, :-2] - q[:, 1:-1, 2:]
    return lap.reshape(len(q), -1).var(axis=1)

def _audio(video, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = int(16000 * PASSO); k = max(1, int(np.ceil(dur / PASSO)))
    db, clip = [], []
    for i in range(k):
        b = x[i * n:(i + 1) * n]
        db.append(round(float(20 * np.log10(np.sqrt((b ** 2).mean()) + 1e-6)), 1) if len(b) else -90.0)
        clip.append(round(float((np.abs(b) > 0.99).mean()), 4) if len(b) else 0.0)
    return db, clip

def varredura(video, cache=None):
    """Métricas a cada PASSO segundos: tremor (px/quadro), nitidez relativa ao melhor trecho do take (0-1), luz, estouro, áudio."""
    if cache and os.path.exists(cache): return json.load(open(cache))
    t0 = time.time(); dur = montagem.duracao(video); q = _gray(video, FPS_VARR)
    d = np.array(montagem.deslocamentos(q), np.float32).reshape(-1, 2)
    salto = np.r_[0.0, 0.0, np.hypot(*np.diff(d, axis=0).T)][:len(q)] if len(d) > 1 else np.zeros(len(q))
    nit = _nitidez(q) if len(q) else np.zeros(0)
    ref = float(np.percentile(nit, 90)) if len(nit) else 1.0
    por = max(1, int(FPS_VARR * PASSO)); k = max(1, int(np.ceil(dur / PASSO)))
    agg = lambda v, f: [round(float(f(v[i * por:(i + 1) * por])), 3) if len(v[i * por:(i + 1) * por]) else 0.0 for i in range(k)]
    db, clip = _audio(video, dur)
    m = {'passo': PASSO, 'dur': round(dur, 3), 'tremor': agg(salto, np.mean), 'nitidez': agg(nit / (ref or 1.0), np.median),
         'luz': agg(q.mean(axis=(1, 2)) / 255 if len(q) else np.zeros(0), np.mean),
         'estouro': agg((q > 250).mean(axis=(1, 2)) if len(q) else np.zeros(0), np.mean),
         'audio_db': db[:k], 'clip': clip[:k], 'segundos_analise': round(time.time() - t0, 1)}
    if cache: json.dump(m, open(cache, 'w'))
    return m

def _janela(m, chave, a, b):
    p = m['passo']; v = m[chave][int(a / p): max(int(a / p) + 1, int(np.ceil(b / p)))]
    return v or [0.0]

def problemas_tecnicos(m, a, b, fala):
    pr = []
    tr = _janela(m, 'tremor', a, b)
    if max(tr) > montagem.TREMOR_ALTO:
        ruins = [round(a + i * m['passo'], 1) for i, x in enumerate(tr) if x > montagem.TREMOR_ALTO]
        pr.append(f"tremor da câmera em {', '.join(f'{x:g}s' for x in ruins[:6])}")
    if min(_janela(m, 'nitidez', a, b)) < 0.45: pr.append('trecho desfocado ou borrado')
    if max(_janela(m, 'estouro', a, b)) > 0.25: pr.append('luz estourada')
    if np.mean(_janela(m, 'luz', a, b)) < 0.12: pr.append('imagem escura')
    if fala:
        if max(_janela(m, 'clip', a, b)) > 0.005: pr.append('áudio clipado (distorcido)')
        if np.mean(_janela(m, 'audio_db', a, b)) < -38: pr.append('voz baixa')
    return pr

def candidatos(ai, video, palavras_arq, g0, papel, m):
    """Intervalos candidatos do take. Fala: uma frase por intervalo (palavras globais g0..). Ambiente: trechos firmes de 1,5 a 6 s."""
    dur, out = m['dur'], []
    if papel == 'fala':
        frase = []
        for k, w in enumerate(palavras_arq):
            frase.append(k)
            fim = w['w'][-1:] in '.?!' or (k + 1 < len(palavras_arq) and palavras_arq[k + 1]['s'] - w['e'] > 0.8)
            if fim or k == len(palavras_arq) - 1:
                a, b = palavras_arq[frase[0]]['s'], palavras_arq[frase[-1]]['e']
                out.append({'arquivo': ai, 'tipo': 'fala', 'inicio': round(max(0.0, a - 0.12), 2), 'fim': round(min(dur, b + 0.15), 2),
                            'palavras': [g0 + frase[0], g0 + frase[-1]], 'fala': ' '.join(palavras_arq[i]['w'] for i in frase)})
                frase = []
        return out
    p = m['passo']; ok = [t <= montagem.TREMOR_ALTO and n >= 0.45 for t, n in zip(m['tremor'], m['nitidez'])]
    i = 0
    while i < len(ok):
        if not ok[i]: i += 1; continue
        j = i
        while j < len(ok) and ok[j]: j += 1
        a, b = i * p, min(dur, j * p)
        while b - a >= 1.5:                            # trechos firmes longos viram pedaços de até 6 s
            fim = min(b, a + 6.0) if b - a > 7.5 else b
            out.append({'arquivo': ai, 'tipo': 'ambiente', 'inicio': round(a, 2), 'fim': round(fim, 2), 'palavras': None, 'fala': ''})
            a = fim
        i = j
    if not out:                                        # nada firme: registra o take inteiro, marcado, pra IA saber que existe e é ruim
        out.append({'arquivo': ai, 'tipo': 'ambiente', 'inicio': 0.0, 'fim': round(dur, 2), 'palavras': None, 'fala': '', 'sem_trecho_firme': True})
    return out

def detalhar(video, iv, m):
    """Olha a 30 quadros/s a entrada e a saída. Movimento brusco perto da borda: no ambiente, a borda anda pra depois/antes dele;
    na fala, só registra (não pode cortar palavra)."""
    pr = []
    for lado in ('entrada', 'saida'):
        c = iv['inicio'] if lado == 'entrada' else iv['fim']
        a = max(0.0, c - 0.4); q = _gray(video, 30, a, 1.0)
        if len(q) < 3: continue
        d = np.array(montagem.deslocamentos(q), np.float32).reshape(-1, 2)
        salto = np.hypot(*np.diff(d, axis=0).T) if len(d) > 1 else np.zeros(0)
        picos = [round(a + (i + 2) / 30, 2) for i, x in enumerate(salto) if x > 3 * montagem.TREMOR_ALTO]
        if not picos: continue
        if iv['tipo'] == 'ambiente':
            if lado == 'entrada' and max(picos) + 0.1 < iv['fim'] - 1.5: iv['inicio'] = round(max(picos) + 0.1, 2); pr.append(f'entrada movida pra depois de um tranco em {max(picos):g}s')
            elif lado == 'saida' and min(picos) - 0.1 > iv['inicio'] + 1.5: iv['fim'] = round(min(picos) - 0.1, 2); pr.append(f'saída antecipada por um tranco em {min(picos):g}s')
            else: pr.append(f'tranco de câmera na {lado} ({picos[0]:g}s)')
        else:
            pr.append(f'movimento brusco na {lado} ({picos[0]:g}s)')
    iv['problemas_tecnicos'] = problemas_tecnicos(m, iv['inicio'], iv['fim'], iv['tipo'] == 'fala') + pr
    iv['metricas'] = {'tremor_max': max(_janela(m, 'tremor', iv['inicio'], iv['fim'])), 'nitidez_min': min(_janela(m, 'nitidez', iv['inicio'], iv['fim'])),
                      'audio_db': round(float(np.mean(_janela(m, 'audio_db', iv['inicio'], iv['fim']))), 1)}
    return iv

def folha_intervalos(video, ivs, saida, largura=160):
    """Uma folha: cada linha é um intervalo, com 3 quadros (entrada, meio, saída). Convertida pra SDR só pra IA enxergar."""
    if os.path.exists(saida): return saida
    hdr = montagem.sondar(video)[2] in ('arib-std-b67', 'smpte2084')
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,' if hdr else ''
    tempos = [t for iv in ivs for t in (iv['inicio'] + 0.15, (iv['inicio'] + iv['fim']) / 2, max(iv['inicio'], iv['fim'] - 0.15))]
    for t_ in (tm, ''):
        args = ['ffmpeg', '-v', 'error', '-y']
        for t in tempos: args += ['-ss', f'{t:.2f}', '-i', video]
        n = len(tempos); fc = ';'.join(f'[{i}:v]trim=end_frame=1,{t_}scale={largura}:-2,setsar=1[q{i}]' for i in range(n))
        linhas = ''.join(f';[q{3 * r}][q{3 * r + 1}][q{3 * r + 2}]hstack=3[l{r}]' for r in range(len(ivs)))
        fc += linhas + (';' + ''.join(f'[l{r}]' for r in range(len(ivs))) + f'vstack={len(ivs)}[o]' if len(ivs) > 1 else ';[l0]null[o]')
        r = subprocess.run(args + ['-filter_complex', fc, '-map', '[o]', '-frames:v', '1', '-q:v', '5', saida], capture_output=True)
        if r.returncode == 0 and os.path.exists(saida): return saida
    return None

ESQ_VISUAL = {'type': 'object', 'additionalProperties': False, 'required': ['intervalos'], 'properties': {'intervalos': {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False,
    'required': ['id', 'descricao_visual', 'problemas_visuais', 'funcao_narrativa', 'nota', 'utilizavel', 'incertezas'],
    'properties': {'id': {'type': 'string'}, 'descricao_visual': {'type': 'string', 'description': 'o que aparece: pessoa, enquadramento, ambiente, ação'},
                   'problemas_visuais': {'type': 'array', 'items': {'type': 'string'}},
                   'funcao_narrativa': {'type': 'string', 'enum': FUNCOES},
                   'nota': {'type': 'integer', 'description': '0 a 10: qualidade da imagem pra entrar no vídeo'},
                   'utilizavel': {'type': 'boolean'}, 'incertezas': {'type': 'string', 'description': 'o que não dá pra saber só pelos quadros; vazio se nada'}}}}}}

SIS_VISUAL = """Você é um editor de vídeo sênior avaliando os brutos ANTES da montagem (Reels 9:16 de clientes da Bora).
Cada folha é um take: cada LINHA é um intervalo (id indicado no texto), com 3 quadros: entrada, meio e saída.
Junto vêm as medições automáticas (tremor da câmera, nitidez, áudio) e a fala do intervalo.
Para cada intervalo, avalie a IMAGEM como ela vai aparecer no vídeo: enquadramento, rosto (olhos fechados, careta, virada, cortado), estabilidade,
foco, luz, objetos ou pessoas atrapalhando, ação que interessa (no ambiente: a cena mostra bem o lugar? há um momento forte, ex. brinde, logo, porta abrindo?).
Use as medições: tremor acima de {tr} px/quadro é câmera tremendo. Não invente o que não dá pra ver: se algo depende do movimento entre os quadros
ou do áudio, diga em incertezas. Função narrativa: o papel mais provável do intervalo no vídeo (fala: pelo conteúdo; ambiente: 'ambiente' ou 'transicao').
Marque utilizavel=false só quando a imagem compromete a entrega (tremido forte, desfocado, rosto cortado, take com erro visível)."""

def _uso(msg, modelo):
    u = msg.usage; pe, ps = PRECOS.get(modelo, PRECOS['claude-opus-5-5'])
    ent = u.input_tokens + (getattr(u, 'cache_creation_input_tokens', 0) or 0) * 1.25 + (getattr(u, 'cache_read_input_tokens', 0) or 0) * 0.1
    return {'entrada': u.input_tokens, 'saida': u.output_tokens, 'custo_usd': round((ent * pe + u.output_tokens * ps) / 1e6, 4)}

def avaliar_visual(lotes, client=None, modelo=MODELO_VISUAL):
    """lotes: [(texto, [jpg, ...]), ...]. Uma chamada por lote. Devolve ({id: avaliação}, uso total)."""
    import anthropic
    client = client or anthropic.Anthropic()
    res, uso = {}, {'entrada': 0, 'saida': 0, 'custo_usd': 0.0, 'chamadas': 0, 'segundos': 0.0}
    for texto, jpgs in lotes:
        t0 = time.time(); cont = []
        for j in jpgs:
            cont.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(j, 'rb').read()).decode()}})
        cont.append({'type': 'text', 'text': texto})
        with client.beta.messages.stream(model=modelo, max_tokens=32000, betas=['server-side-fallback-2026-07-01'], fallbacks='default',
                                         output_config={'effort': ESFORCO_VISUAL, 'format': {'type': 'json_schema', 'schema': ESQ_VISUAL}},
                                         system=[{'type': 'text', 'text': SIS_VISUAL.format(tr=montagem.TREMOR_ALTO), 'cache_control': {'type': 'ephemeral'}}],
                                         messages=[{'role': 'user', 'content': cont}]) as st:
            msg = st.get_final_message()
        if msg.stop_reason in ('refusal', 'max_tokens'): raise RuntimeError(f'avaliação visual interrompida: {msg.stop_reason}')
        for x in json.loads(next(b.text for b in msg.content if b.type == 'text'))['intervalos']: res[x['id']] = x
        u = _uso(msg, modelo); uso['entrada'] += u['entrada']; uso['saida'] += u['saida']; uso['custo_usd'] += u['custo_usd']
        uso['chamadas'] += 1; uso['segundos'] += round(time.time() - t0, 1)
    uso['custo_usd'] = round(uso['custo_usd'], 4)
    return res, uso

def catalogo(arqs, palavras, papeis, pasta, nomes=None, client=None, modelo=MODELO_VISUAL, etapa=None, visual=True):
    """Catálogo de intervalos avaliados de todos os takes (cache em pasta/catalogo.json, refeito se os arquivos mudarem)."""
    chave = [os.path.getsize(a) for a in arqs]
    arq_cat = os.path.join(pasta, 'catalogo.json')
    if os.path.exists(arq_cat):
        c = json.load(open(arq_cat))
        if c.get('chave') == chave and (c.get('visual') or not visual): return c
    nomes = nomes or [os.path.basename(a) for a in arqs]
    t0 = time.time(); ivs, g0, metr = [], 0, {}
    for ai, a in enumerate(arqs):
        if etapa: etapa(f'Analisando os brutos ({ai + 1} de {len(arqs)}): movimento, nitidez e áudio', 20 + int(5 * ai / len(arqs)))
        m = varredura(a, os.path.join(pasta, f'varredura_{ai + 1:02d}.json')); metr[ai] = m
        for iv in candidatos(ai, a, palavras[ai], g0, papeis[ai], m): ivs.append(detalhar(a, iv, m))
        g0 += len(palavras[ai])
    for n, iv in enumerate(ivs, 1): iv['id'] = f'I{n}'; iv['nome'] = nomes[iv['arquivo']]
    t_tec = round(time.time() - t0, 1)
    uso = {'entrada': 0, 'saida': 0, 'custo_usd': 0.0, 'chamadas': 0, 'segundos': 0.0}
    if visual:
        if etapa: etapa('A IA está olhando os brutos (quadros de cada trecho)', 26)
        lotes, atual, imgs = [], [], []
        for ai, a in enumerate(arqs):
            meus = [iv for iv in ivs if iv['arquivo'] == ai]
            for k in range(0, len(meus), 6):            # até 6 intervalos por folha (folha de 480 px de largura)
                parte = meus[k:k + 6]
                jpg = folha_intervalos(a, parte, os.path.join(pasta, f'folha_{ai + 1:02d}_{k // 6 + 1}.jpg'))
                if not jpg: continue
                imgs.append(jpg)
                atual.append(f"Folha {len(imgs)} ({nomes[ai]}, {'fala' if papeis[ai] == 'fala' else 'ambiente'}), linhas de cima pra baixo:\n" + '\n'.join(
                    f"  {iv['id']}: {iv['inicio']:g}-{iv['fim']:g} s | fala: {iv['fala'] or '(sem fala)'} | medições: {iv['metricas']} | "
                    f"problemas técnicos: {'; '.join(iv['problemas_tecnicos']) or 'nenhum'}" for iv in parte))
                if len(imgs) == 8:                     # até 8 folhas por chamada
                    lotes.append(('\n\n'.join(atual), imgs)); atual, imgs = [], []
        if imgs: lotes.append(('\n\n'.join(atual), imgs))
        av, uso = avaliar_visual(lotes, client, modelo)
        for iv in ivs:
            x = av.get(iv['id'])
            if x: iv.update({k: x[k] for k in ('descricao_visual', 'problemas_visuais', 'funcao_narrativa', 'nota', 'utilizavel', 'incertezas')})
            else: iv.update({'descricao_visual': '', 'problemas_visuais': [], 'funcao_narrativa': 'descartar', 'nota': 0, 'utilizavel': False, 'incertezas': 'a IA não avaliou este intervalo'})
    for iv in ivs:
        iv['problemas'] = iv.pop('problemas_tecnicos', []) + iv.get('problemas_visuais', [])
        if not visual: iv.setdefault('utilizavel', not any('tremor' in p or 'desfoc' in p for p in iv['problemas']))
    c = {'chave': chave, 'visual': visual, 'modelo': modelo if visual else None, 'intervalos': ivs,
         'tempos': {'tecnica_s': t_tec, 'visual_s': uso['segundos'], 'total_s': round(time.time() - t0, 1)}, 'uso': uso}
    json.dump(c, open(arq_cat, 'w'), ensure_ascii=False, indent=1)
    return c

def texto_para_plano(cat):
    """Catálogo em texto compacto pro planejador (sem imagens)."""
    linhas = []
    for iv in cat['intervalos']:
        pal = f" | palavras [{iv['palavras'][0]}]-[{iv['palavras'][1]}]" if iv.get('palavras') else ''
        linhas.append(f"{iv['id']} | arquivo {iv['arquivo'] + 1} {iv['nome']} | {iv['inicio']:g}-{iv['fim']:g} s | {iv['tipo']}{pal} | "
                      f"{'UTILIZÁVEL' if iv.get('utilizavel') else 'NÃO USAR'} nota {iv.get('nota', '?')} | função: {iv.get('funcao_narrativa', '?')} | "
                      f"visual: {iv.get('descricao_visual') or '-'} | problemas: {'; '.join(iv.get('problemas') or []) or 'nenhum'} | "
                      f"incertezas: {iv.get('incertezas') or '-'}" + (f" | fala: {iv['fala']}" if iv.get('fala') else ''))
    return '\n'.join(linhas)

# ---------- conferência da prévia montada ----------

def cortes(video, limiar=40.0):
    """Tempos de troca de imagem na prévia (diferença média entre quadros seguidos)."""
    q = _gray(video, 30)
    if len(q) < 2: return []
    dif = np.abs(np.diff(q, axis=0)).mean(axis=(1, 2))
    return [round((i + 1) / 30, 2) for i, x in enumerate(dif) if x > limiar]

def conferir_previa(previa, pl, pasta, client=None, modelo=MODELO_VISUAL, visual=True):
    """Confere a prévia: tremor por segundo fora dos cortes (técnico) e, com a IA, quadros logo antes/depois de cada corte e no meio dos B-rolls."""
    t0 = time.time(); dur = montagem.duracao(previa); cs = cortes(previa)
    m = varredura(previa); p = m['passo']; achados = []
    perto = lambda t: any(abs(t - c) < 0.6 for c in cs)
    for i, x in enumerate(m['tremor']):
        if x > montagem.TREMOR_ALTO and not perto(i * p + p / 2): achados.append({'t': round(i * p, 1), 'problema': f'câmera tremendo ({x:g} px/quadro)', 'origem': 'medição'})
    uso = {'custo_usd': 0.0, 'entrada': 0, 'saida': 0}
    if visual and cs:
        pts = sorted({round(min(dur - 0.05, max(0.05, c + d)), 2) for c in cs for d in (-0.12, 0.12)})[:48]
        ivs = [{'inicio': pts[i] - 0.15, 'fim': pts[i] + 0.15} for i in range(len(pts))]
        jpgs = []
        for k in range(0, len(ivs), 6):
            parte = [{'inicio': x['inicio'], 'fim': x['fim']} for x in ivs[k:k + 6]]
            j = folha_intervalos(previa, parte, os.path.join(pasta, f'_conf_{k // 6 + 1}.jpg'))
            if j: jpgs.append(j)
        txt = ('Conferência da PRÉVIA montada. Cada linha é um ponto logo antes ou logo depois de um corte (3 quadros em volta). Pontos em segundos, '
               'de cima pra baixo e folha por folha: ' + ', '.join(f'P{i + 1}={t:g}s' for i, t in enumerate(pts)) +
               '. Use o id P<n>. Aponte só problemas reais: rosto ou cabeça cortados, texto ilegível ou em cima do rosto, cena de ambiente tremida, '
               'começando no meio de um movimento ou sem relação com a fala, corte feio. Plano: ' +
               json.dumps({'broll': pl.get('broll'), 'segmentos': len(pl.get('segmentos', []))}, ensure_ascii=False)[:3000])
        av, uso = avaliar_visual([(txt, jpgs)], client, modelo)
        for k, x in av.items():
            if x.get('problemas_visuais') or not x.get('utilizavel', True):
                i = int(k[1:]) - 1 if k[1:].isdigit() else -1
                achados.append({'t': pts[i] if 0 <= i < len(pts) else None, 'problema': '; '.join(x.get('problemas_visuais') or ['ruim']), 'origem': 'IA',
                                'incertezas': x.get('incertezas', '')})
    return {'cortes': len(cs), 'achados': sorted(achados, key=lambda a: a['t'] or 0), 'uso': uso, 'segundos': round(time.time() - t0, 1)}
