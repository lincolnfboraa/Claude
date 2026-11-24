"""Plano de edição feito pela IA (Claude pelo SDK `anthropic`, ou GPT pelo SDK `openai` com BORA_IA=gpt).
Entrada: transcrição numerada palavra a palavra, DNA ativo do cliente, regras globais, briefing e o histórico de feedback.
Saída: JSON validado por esquema (structured outputs): segmentos, título, destaques, correções e resumo.
A IA só escolhe e ordena o que FOI falado; nunca inventa fala. O vídeo em si é montado pelo ffmpeg (montagem.py)."""
import json, os, re, unicodedata

from montagem import TREMOR_ALTO as TREMOR
MODELO = os.environ.get('BORA_MODELO', 'claude-opus-5-5')
IA = os.environ.get('BORA_IA', 'claude').lower()             # quem monta o storytelling: claude ou gpt
MODELO_GPT = os.environ.get('BORA_MODELO_GPT', '')               # modelo da OpenAI (obrigatório com BORA_IA=gpt)

ESQUEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['segmentos', 'usar_titulo', 'titulo', 'destaques', 'insercoes', 'broll', 'correcoes', 'cores', 'resumo', 'nao_feito'],
    'properties': {
        'segmentos': {'type': 'array', 'description': 'Trechos na ORDEM do vídeo final. Cada um é um intervalo contínuo de palavras de um mesmo arquivo.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['palavra_inicio', 'palavra_fim', 'quadro', 'motivo'],
                'properties': {'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'quadro': {'type': 'string', 'enum': ['total', 'aberto', 'medio', 'fechado']}, 'motivo': {'type': 'string'}}}},
        'usar_titulo': {'type': 'boolean'},
        'titulo': {'type': 'object', 'additionalProperties': False, 'required': ['rotulo', 'tema', 'pergunta'],
            'properties': {'rotulo': {'type': 'string'}, 'tema': {'type': 'string'}, 'pergunta': {'type': 'string'}}},
        'destaques': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['estilo', 'palavra_inicio', 'palavra_fim', 'linhas'],
            'properties': {'estilo': {'type': 'string', 'enum': ['pop', 'serifa', 'lettering', 'palavra_solta', 'preco', 'selo']},
                           'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                           'linhas': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['texto', 'papel'],
                               'properties': {'texto': {'type': 'string'}, 'papel': {'type': 'string', 'enum': ['pequena', 'grande']}}}}}}},
        'insercoes': {'type': 'array', 'description': 'Uso dos ANEXOS (imagens/vídeos enviados). Vazio se não houver anexos.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['anexo', 'palavra_inicio', 'palavra_fim', 'modo'],
                'properties': {'anexo': {'type': 'integer', 'description': 'número do anexo (1, 2, ...)'},
                               'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'modo': {'type': 'string', 'enum': ['tela_cheia', 'flutuando']}}}},
        'broll': {'type': 'array', 'description': 'Cenas de ambiente (B-roll, vídeos SEM fala listados abaixo) cobrindo a imagem durante a locução. A voz continua por baixo. Vazio se não houver B-roll.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['video', 'palavra_inicio', 'palavra_fim', 'inicio_s', 'velocidade', 'motivo'],
                'properties': {'video': {'type': 'integer', 'description': 'número do B-roll (1, 2, ...)'},
                               'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'inicio_s': {'type': 'number', 'description': 'segundo do vídeo de ambiente onde a cena começa: o melhor momento, com a câmera firme (veja os quadros e o tremor)'},
                               'velocidade': {'type': 'number', 'description': '1 = normal; 0.5 a 0.9 = câmera lenta, pra cena curta cobrir mais tempo'}, 'motivo': {'type': 'string'}}}},
        'correcoes': {'type': 'array', 'description': 'Grafia correta de palavras que a transcrição errou (só ortografia, nunca trocar o que foi dito).',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['palavra', 'texto'],
                      'properties': {'palavra': {'type': 'integer'}, 'texto': {'type': 'string'}}}},
        'cores': {'type': 'object', 'additionalProperties': False, 'required': ['legenda', 'destaque'],
            'description': 'Cor em hexadecimal (#RRGGBB) só se o feedback pedir mudança de cor; senão string vazia.',
            'properties': {'legenda': {'type': 'string'}, 'destaque': {'type': 'string'}}},
        'resumo': {'type': 'string', 'description': 'Uma ou duas frases sobre o que esta versão REALMENTE aplica. Nunca cite algo que o motor não faz.'},
        'nao_feito': {'type': 'string', 'description': 'O que o feedback pediu e o motor ainda não consegue fazer (ex.: imagens, B-roll). String vazia se tudo foi aplicado.'},
    },
}

SISTEMA = """Você é o editor-chefe da Bora Soluções Digitais. Planeja Reels verticais a partir da transcrição palavra a palavra dos vídeos brutos de um cliente.
Seu trabalho: storytelling, gancho, cortes e textos. Música, efeitos sonoros e transições ficam com a equipe da Bora depois.

Como planejar
- Escolha e ordene trechos do que FOI falado (por índice de palavra). Nunca invente, monte ou altere falas; reordenar só quando não distorce o sentido.
- Comece pelo gancho mais forte que existe no material (pergunta curiosa, situação de identificação ou cena com objeto). Nada de "olá", "agora eu vou falar", "hoje eu vou".
- Corte falsos começos, repetições, gaguejos e frases abandonadas: prefira a última tentativa completa de cada frase.
- Estrutura (sempre, mesmo em vídeo curto): 1) gancho; 2) contexto: o que é o assunto e por que importa pra quem assiste (quem não sabe nada precisa entender ANTES da prova); 3) desenvolvimento e evidência (dados, estudos, explicação); 4) fechamento com orientação ou chamada. Se o gancho usa uma metáfora ou um objeto (ex.: uma armadura), retome-o no contexto ou no fechamento em vez de abandoná-lo. Dados e estudos só entram DEPOIS de o espectador entender de que se trata.
- O briefing que pede pra manter falas ou trechos (ex.: 'manter os estudos') vale, mas SOMA ao resto: não autoriza deixar de fora o contexto que explica essas falas. Se o material tem uma introdução que explica o tema, ela entra antes da evidência.
- Palavras seguidas de ⟲ na transcrição são o PRIMEIRO de um par repetido (gagueira, falso começo ou número dito duas vezes). Quase sempre pule as marcadas e fique com a versão completa: divida em dois segmentos seguidos do mesmo arquivo, deixando as marcadas de fora. Só mantenha uma repetição se ela for proposital (ênfase).
- Antes de responder, releia o roteiro na ordem dos segmentos, como será ouvido: sem repetição, sem salto de assunto, com o contexto antes da evidência.
- Observações do editor sobre o gancho NÃO são o texto do título: use como inspiração (crie um título curto e natural), a menos que venham marcadas como texto EXATO.
- Os templates de título (premium, caixa, impacto, sem título) são desenhados pelo motor: nunca diga que um deles não está disponível.
- Cada segmento termina numa palavra completa e fecha o pensamento; nunca corte no meio de uma frase.
- Preço 'de X por Y': destaque estilo 'preco' com duas linhas: 'De R$X' (pequena, sai riscada em vermelho) e 'por R$Y' (grande, na cor de destaque); use em TODA oferta do vídeo, pra manter o padrão.
- Selo de campanha ('selo'): quando a fala anuncia a campanha (ex.: Black Friday), um selo no meio da tela com o fundo escurecido e desfocado: linhas curtas ('BLACK' pequena, 'FRIDAY' grande, 'até 50%' pequena). No máximo 1 por vídeo, longe dos preços.
- Respeite a duração e o ritmo do DNA do cliente. Varie o enquadramento entre segmentos (aberto, medio, fechado) pra dar dinamismo, sem pular de fechado pra fechado em sequência. 'total' = quadro inteiro, sem zoom: use quando houver duas ou mais pessoas no quadro ou alguém perto da borda (olhe as folhas de quadros das falas); nunca corte uma pessoa na lateral.
- Título (usar_titulo): rótulo curto em caixa alta (ex.: DIA MUNDIAL DO DIABETES), tema de uma ou duas palavras e uma pergunta curta. Use quando o tema pedir.
- Destaques: no máximo 3 ou 4 frases de destaque, variando os estilos no mesmo vídeo (pop, serifa, lettering), mais 2 ou 3 palavras soltas (estilo palavra_solta: só a palavra-chave, uma linha 'grande'). Os textos das linhas saem exatamente das palavras faladas no intervalo palavra_inicio..palavra_fim; a palavra principal fica numa linha 'grande', as de apoio em 'pequena'. Nada de destaque em todo lugar.
- Hierarquia: 1) DNA Global Bora (as 'obrigatorias' e as 10 'regras_fundamentais' nunca são quebradas), 2) DNA do cliente (estilo, ritmo, cores, ganchos), 3) briefing e ajustes do projeto (valem só para este vídeo), 4) aprendizados confirmados. Em conflito, vale o nível mais alto; as cores da Bora nunca vão para o cliente. Se o DNA do cliente for provisório, seja conservador.
- Em ajustes: aplique exatamente o que o feedback pede, mexendo o mínimo no resto do plano anterior.

O que o motor sabe fazer (e só isso): escolher e ordenar falas, cortar, enquadramento aberto/medio/fechado, título, destaques (pop, serifa, lettering, palavra_solta), corrigir grafia e trocar as cores da legenda e dos destaques (campo cores, em #RRGGBB; nomes comuns: bege/creme da Fabiola = #C8B9A7, branco = #FFFFFF).
Também encaixa os ANEXOS enviados (lista abaixo, quando houver) no campo insercoes: 'tela_cheia' cobre a tela durante a fala indicada (B-roll, com a voz por baixo); 'flutuando' põe a imagem menor ao lado da pessoa, com leve desfoque e flutuação. Vídeos anexados entram sempre em tela cheia. Cada inserção fica durante as palavras palavra_inicio..palavra_fim; normalmente 1,5 a 6 s.
B-roll (campo broll): quando houver vídeos de ambiente (sem fala) listados com imagem, encaixe-os DURANTE a locução, cobrindo a imagem da pessoa enquanto a voz continua. Escolha a cena que ilustra o que está sendo dito (ex.: ela fala do espaço, entra a sala; fala da recepção, entra a fachada). Regras: nunca no gancho (primeiro segmento) nem no título; nunca no mesmo intervalo de um destaque; cada B-roll dura de 1,5 a 4 s (palavra_inicio..palavra_fim dentro de um mesmo trecho falado); no máximo 1 a cada 8 a 10 s de vídeo; não repita a mesma cena; mostre o rosto de novo entre um B-roll e outro. Sem vídeos de ambiente, broll fica vazio.
Escolha do momento (inicio_s), como um editor que assistiu o take inteiro: olhe a folha de quadros e o tremor de cada segundo e comece a cena no MELHOR momento: câmera firme (tremor baixo durante toda a duração da cena), enquadramento limpo e a ação que interessa acontecendo (o brinde, a logo aparecendo, a porta abrindo, a sala inteira à mostra). Nunca use um trecho tremido nem o começo do take só por ser o começo. Se o pedido citar um take ou um momento (ex.: 'o brinde final do IMG_2967'), ache nos quadros o segundo em que ele aparece e comece cerca de 1 s antes. Se a cena fecha o vídeo, ela fica até o último quadro, então escolha um trecho que aguente até o fim. Em motivo, diga por que escolheu aquele segundo.
Títulos e destaques já saem com sombra só nas letras, sem bloco ou degradê atrás (regra geral do motor): pedidos de tirar o bloco de sombra estão atendidos, não liste isso em nao_feito. A intensidade da sombra ainda não é ajustável.
O motor NÃO cria imagens nem vídeos novos: sem anexo ou vídeo de ambiente, não existe B-roll. Também não faz animações, efeitos, transições, zoom animado, música ou mudanças na imagem.
Se o feedback pedir algo que o motor não faz, aplique o resto e escreva claramente em nao_feito o que ficou de fora. O resumo descreve apenas o que esta versão aplica de verdade; nunca diga que fez algo que não está no plano."""

def _n(t): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', t.lower()).encode('ascii', 'ignore').decode())

def marcar_repeticoes(pw):
    """Posições (no arquivo) do PRIMEIRO de um par repetido: gagueira ('eu eu'), falso começo (o mesmo par de palavras dito de novo logo adiante,
    marca o trecho todo da primeira tentativa) ou número dito duas vezes ('24%, uma redução de 24%'). É só um aviso pra IA, que decide."""
    n = [_n(w['w']) for w in pw]; m = set()
    fecha = lambda a, b: any(pw[k]['w'].rstrip()[-1:] in '.?!' for k in range(a, b))      # frase completa no meio: é lista (ofertas), não falso começo
    for i in range(len(pw)):
        if not n[i]: continue
        if i + 1 < len(pw) and n[i + 1] == n[i] and len(n[i]) <= 12: m.add(i)
        if i + 1 < len(pw) and n[i + 1] and len(n[i]) + len(n[i + 1]) >= 5:
            for j in range(i + 2, min(len(pw) - 1, i + 14)):
                if n[j] == n[i] and n[j + 1] == n[i + 1]:
                    if not fecha(i, j): m.update(range(i, j))
                    break
        if n[i].isdigit():
            for j in range(i + 1, min(len(pw), i + 8)):
                if n[j] == n[i]:
                    if not fecha(i, j): m.add(i)
                    break
    return m

def numerar(palavras, arquivos, papeis=None):
    """Transcrição numerada: '[12] palavra (3.42)' agrupada por arquivo e por frase. Vídeos de ambiente não entram (os índices continuam valendo)."""
    linhas, g = [], 0
    for ai, pw in enumerate(palavras):
        if papeis and papeis[ai] == 'ambiente':
            linhas.append(f"\n=== Arquivo {ai + 1}: {os.path.basename(arquivos[ai])} (vídeo de ambiente, B-roll; não use como fala) ==="); g += len(pw); continue
        linhas.append(f"\n=== Arquivo {ai + 1}: {os.path.basename(arquivos[ai])} ===")
        frase = []; marcas = marcar_repeticoes(pw)
        for k, w in enumerate(pw):
            frase.append(f"[{g}]{w['w']}" + ('⟲' if k in marcas else ''))
            fim_frase = w['w'][-1:] in '.?!' or (k + 1 < len(pw) and pw[k + 1]['s'] - w['e'] > 0.8)
            if fim_frase or k == len(pw) - 1:
                linhas.append(f"({pw[k - len(frase) + 1]['s']:.1f}s) " + ' '.join(frase)); frase = []
            g += 1
    return '\n'.join(linhas)

def gerar(palavras, arquivos, cliente, dna, regras, briefing='', anterior=None, feedbacks=(), anexos=(), papeis=None, brolls=(), exigidos=(), falas=()):
    dna_txt = json.dumps({'cliente': cliente.get('nome'), 'segmento': cliente.get('segmento'), 'status': cliente.get('status'), **(dna or {})}, ensure_ascii=False)
    pedido = [f"Transcrição numerada (use os números entre colchetes):\n{numerar(palavras, arquivos, papeis)}"]
    if briefing: pedido.append(f"Briefing do projeto: {briefing}")
    if anexos: pedido.append('Anexos disponíveis para inserções:\n' + '\n'.join(f"{i}. {a['nome']} ({'vídeo' if a['tipo'] == 'video' else 'imagem'}, enviado na v{a.get('versao', 1)})" for i, a in enumerate(anexos, 1)))
    if anterior:
        pedido.append("Plano da versão anterior:\n" + json.dumps({k: v for k, v in anterior.items() if not k.startswith('_')}, ensure_ascii=False))
        pedido.append("Feedback do editor sobre as versões (o último é o que vale agora):\n" + '\n'.join(f"- v{n}: {t}" for n, t in feedbacks))
        pedido.append("Devolva o plano completo revisado.")
    else:
        pedido.append("Monte o plano da primeira versão.")
    sistema = [SISTEMA, 'DNA Global Bora (sempre prevalece):\n' + json.dumps({k: v for k, v in regras.items() if k != 'historico'}, ensure_ascii=False),
               'DNA do cliente:\n' + dna_txt]
    import montagem
    amb = {i for i, p in enumerate(papeis or []) if p == 'ambiente'}; G = montagem.indice_global(palavras)
    for tentativa in (0, 1):
        conteudo = _conteudo('\n\n'.join(pedido), brolls, falas)
        plano = _chamar_gpt(sistema, conteudo) if IA == 'gpt' else _chamar_claude(sistema, conteudo)
        plano = validar(plano, sum(len(p) for p in palavras), amb, len(brolls), G)
        falta = sorted(set(exigidos) - {G[int(sg['palavra_inicio'])][0] for sg in plano['segmentos']})
        if not falta or tentativa: break
        pedido.append('ATENÇÃO: o plano que você acabou de montar NÃO usou ' + ', '.join(f"o Arquivo {i + 1} ({os.path.basename(arquivos[i])})" for i in falta) +
                      ', e o editor pediu que ele entre no storytelling. Refaça o plano com pelo menos um trecho de fala de cada um desses arquivos, no ponto da história em que fizer mais sentido.')
    return plano

def _chamar_claude(sistema, conteudo):
    import anthropic
    client = anthropic.Anthropic()                      # lê ANTHROPIC_API_KEY do ambiente
    with client.beta.messages.stream(
        model=MODELO, max_tokens=32000,
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',     # se o modelo recusar, o servidor tenta outro
        output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': ESQUEMA}},
        system=[{'type': 'text', 'text': sistema[0]}] + [{'type': 'text', 'text': t, 'cache_control': {'type': 'ephemeral'}} for t in sistema[1:]],
        messages=[{'role': 'user', 'content': conteudo}],
    ) as st:
        msg = st.get_final_message()
    if msg.stop_reason == 'refusal':
        raise RuntimeError('a IA recusou o pedido: ' + str(getattr(msg.stop_details, 'explanation', '')))
    if msg.stop_reason == 'max_tokens':
        raise RuntimeError('o plano ficou grande demais (max_tokens)')
    plano = json.loads(next(b.text for b in msg.content if b.type == 'text'))
    plano['_modelo'] = msg.model
    plano['_uso'] = {'entrada': msg.usage.input_tokens, 'saida': msg.usage.output_tokens}
    return plano

def _chamar_gpt(sistema, conteudo):
    """Mesmo pedido e mesmo esquema, pela OpenAI (Responses API, JSON estrito). Lê OPENAI_API_KEY do ambiente."""
    from openai import OpenAI
    if not MODELO_GPT: raise RuntimeError('defina BORA_MODELO_GPT no bora.env (modelo da OpenAI que monta o storytelling)')
    blocos = [{'type': 'text', 'text': conteudo}] if isinstance(conteudo, str) else conteudo
    entrada = []
    for b in blocos:
        if b['type'] == 'text': entrada.append({'type': 'input_text', 'text': b['text']})
        elif b['type'] == 'image':
            src = b['source']; entrada.append({'type': 'input_image', 'image_url': f"data:{src['media_type']};base64,{src['data']}", 'detail': 'auto'})
    r = OpenAI(timeout=900).responses.create(
        model=MODELO_GPT, instructions='\n\n'.join(sistema), input=[{'role': 'user', 'content': entrada}],
        text={'format': {'type': 'json_schema', 'name': 'plano_bora', 'schema': ESQUEMA, 'strict': True}},
        max_output_tokens=32000, store=False)
    if r.status == 'incomplete':
        raise RuntimeError('o plano do GPT veio incompleto: ' + str(getattr(r.incomplete_details, 'reason', '')))
    for item in r.output or []:
        for c in getattr(item, 'content', None) or []:
            if getattr(c, 'type', '') == 'refusal': raise RuntimeError('o GPT recusou o pedido: ' + c.refusal)
    plano = json.loads(r.output_text)
    plano['_modelo'] = r.model
    plano['_uso'] = {'entrada': r.usage.input_tokens, 'saida': r.usage.output_tokens}
    return plano

def _conteudo(texto, brolls, falas=()):
    """Texto do pedido + quadros de cada vídeo de ambiente (B-roll) e de cada take de fala, pra IA ver o que acontece na imagem."""
    if not brolls and not falas: return texto
    import base64
    img = lambda arq: {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(arq, 'rb').read()).decode()}}
    blocos = [{'type': 'text', 'text': texto}]
    if falas:
        blocos.append({'type': 'text', 'text': 'Imagem dos takes de FALA (uma folha por arquivo, quadros da esquerda pra direita, linha de cima e depois a de baixo, no segundo indicado; '
                       'o segundo é o mesmo da transcrição). Olhe a imagem antes de escolher as falas: NÃO use trechos em que outra pessoa entra ou passa no quadro, alguém '
                       'arruma, troca ou coloca produto na frente de quem fala, quem fala sai do lugar, se ajeita ou olha pra fora, ou a câmera mexe. Se a fala desse trecho for '
                       'essencial, cubra com B-roll (campo broll) pelo tempo do problema; senão, pule a frase. Em motivo, cite quando evitou um trecho por causa da imagem.'})
        for f in falas:
            blocos.append({'type': 'text', 'text': f"Arquivo {f['n']}: {f['nome']}, {f['dur']:.1f} s. Quadros em: {', '.join(f'{t:g} s' for t in f['tempos'])}"}); blocos.append(img(f['jpg']))
    if not brolls: return blocos
    blocos.append({'type': 'text', 'text': '\n\nVídeos de ambiente disponíveis para B-roll. De cada um: uma folha com vários quadros '
               '(da esquerda pra direita, linha de cima e depois a de baixo, no segundo indicado) e o tremor da câmera em cada segundo '
               f'(0 = firme; acima de {TREMOR} = tremido, não use esse trecho):'})
    for b in brolls:
        tr = ' '.join(f'{i}s:{x:g}' for i, x in enumerate(b.get('tremor') or []))
        qs = ', '.join(f'{t:g} s' for t in b.get('tempos') or [])
        blocos.append({'type': 'text', 'text': f"B-roll {b['n']}: {b['nome']}, {b['dur']:.1f} s. Quadros em: {qs}. Tremor por segundo: {tr or 'ainda não medido (o motor mede depois da escolha e desloca a cena se estiver tremida); escolha pela imagem dos quadros'}"})
        blocos.append(img(b['jpg']))
    return blocos

def validar(plano, total, ambiente=None, n_broll=0, G=None):
    """Garante índices dentro da transcrição e ordem certa (a IA não consegue apontar pra fala que não existe)."""
    ok = []
    for s in plano['segmentos']:
        a, b = int(s['palavra_inicio']), int(s['palavra_fim'])
        if 0 <= a <= b < total: ok.append(s)
    if not ok: raise RuntimeError('o plano não trouxe nenhum trecho válido')
    plano['segmentos'] = ok
    plano['insercoes'] = [x for x in plano.get('insercoes', []) if 0 <= int(x['palavra_inicio']) <= int(x['palavra_fim']) < total]
    plano['destaques'] = [d for d in plano.get('destaques', []) if 0 <= int(d['palavra_inicio']) <= int(d['palavra_fim']) < total][:7]
    if ambiente and G:                                  # fala de vídeo de ambiente não vira segmento
        plano['segmentos'] = [x for x in plano['segmentos'] if G[int(x['palavra_inicio'])][0] not in ambiente] or plano['segmentos']
    plano['broll'] = [b for b in plano.get('broll') or [] if 1 <= int(b.get('video', 0)) <= n_broll
                      and 0 <= int(b['palavra_inicio']) <= int(b['palavra_fim']) < total][:12]
    return plano
