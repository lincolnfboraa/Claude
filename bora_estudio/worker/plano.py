"""Plano de edição feito pela IA (Claude, via SDK oficial `anthropic`).
Entrada: transcrição numerada palavra a palavra, DNA ativo do cliente, regras globais, briefing e o histórico de feedback.
Saída: JSON validado por esquema (structured outputs): segmentos, título, destaques, correções e resumo.
A IA só escolhe e ordena o que FOI falado; nunca inventa fala. O vídeo em si é montado pelo ffmpeg (montagem.py)."""
import json, os
import anthropic

from montagem import TREMOR_ALTO as TREMOR
MODELO = os.environ.get('BORA_MODELO', 'claude-opus-5-5')

ESQUEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['segmentos', 'usar_titulo', 'titulo', 'destaques', 'insercoes', 'broll', 'correcoes', 'cores', 'resumo', 'nao_feito'],
    'properties': {
        'segmentos': {'type': 'array', 'description': 'Trechos na ORDEM do vídeo final. Cada um é um intervalo contínuo de palavras de um mesmo arquivo.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['palavra_inicio', 'palavra_fim', 'quadro', 'motivo'],
                'properties': {'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'quadro': {'type': 'string', 'enum': ['aberto', 'medio', 'fechado']}, 'motivo': {'type': 'string'}}}},
        'usar_titulo': {'type': 'boolean'},
        'titulo': {'type': 'object', 'additionalProperties': False, 'required': ['rotulo', 'tema', 'pergunta'],
            'properties': {'rotulo': {'type': 'string'}, 'tema': {'type': 'string'}, 'pergunta': {'type': 'string'}}},
        'destaques': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
            'required': ['estilo', 'palavra_inicio', 'palavra_fim', 'linhas'],
            'properties': {'estilo': {'type': 'string', 'enum': ['pop', 'serifa', 'lettering', 'palavra_solta']},
                           'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                           'linhas': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['texto', 'papel'],
                               'properties': {'texto': {'type': 'string'}, 'papel': {'type': 'string', 'enum': ['pequena', 'grande']}}}}}}},
        'insercoes': {'type': 'array', 'description': 'Uso dos ANEXOS (imagens/vídeos enviados). Vazio se não houver anexos.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['anexo', 'palavra_inicio', 'palavra_fim', 'modo'],
                'properties': {'anexo': {'type': 'integer', 'description': 'número do anexo (1, 2, ...)'},
                               'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'modo': {'type': 'string', 'enum': ['tela_cheia', 'flutuando']}}}},
        'broll': {'type': 'array', 'description': 'Cenas de ambiente (B-roll, vídeos SEM fala listados abaixo) cobrindo a imagem durante a locução. A voz continua por baixo. Vazio se não houver B-roll.',
            'items': {'type': 'object', 'additionalProperties': False, 'required': ['video', 'palavra_inicio', 'palavra_fim', 'inicio_s', 'motivo'],
                'properties': {'video': {'type': 'integer', 'description': 'número do B-roll (1, 2, ...)'},
                               'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                               'inicio_s': {'type': 'number', 'description': 'segundo do vídeo de ambiente onde a cena começa: o melhor momento, com a câmera firme (veja os quadros e o tremor)'},
                               'motivo': {'type': 'string'}}}},
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
- Cada segmento termina numa palavra completa e fecha o pensamento; nunca corte no meio de uma frase.
- Respeite a duração e o ritmo do DNA do cliente. Varie o enquadramento entre segmentos (aberto, medio, fechado) pra dar dinamismo, sem pular de fechado pra fechado em sequência.
- Título (usar_titulo): rótulo curto em caixa alta (ex.: DIA MUNDIAL DO DIABETES), tema de uma ou duas palavras e uma pergunta curta. Use quando o tema pedir.
- Destaques: no máximo 3 ou 4 frases de destaque, variando os estilos no mesmo vídeo (pop, serifa, lettering), mais 2 ou 3 palavras soltas (estilo palavra_solta: só a palavra-chave, uma linha 'grande'). Os textos das linhas saem exatamente das palavras faladas no intervalo palavra_inicio..palavra_fim; a palavra principal fica numa linha 'grande', as de apoio em 'pequena'. Nada de destaque em todo lugar.
- Hierarquia: 1) DNA Global Bora (as 'obrigatorias' e as 10 'regras_fundamentais' nunca são quebradas), 2) DNA do cliente (estilo, ritmo, cores, ganchos), 3) briefing e ajustes do projeto (valem só para este vídeo), 4) aprendizados confirmados. Em conflito, vale o nível mais alto; as cores da Bora nunca vão para o cliente. Se o DNA do cliente for provisório, seja conservador.
- Em ajustes: aplique exatamente o que o feedback pede, mexendo o mínimo no resto do plano anterior.

O que o motor sabe fazer (e só isso): escolher e ordenar falas, cortar, enquadramento aberto/medio/fechado, título, destaques (pop, serifa, lettering, palavra_solta), corrigir grafia e trocar as cores da legenda e dos destaques (campo cores, em #RRGGBB; nomes comuns: bege/creme da Fabiola = #C8B9A7, branco = #FFFFFF).
Também encaixa os ANEXOS enviados (lista abaixo, quando houver) no campo insercoes: 'tela_cheia' cobre a tela durante a fala indicada (B-roll, com a voz por baixo); 'flutuando' põe a imagem menor ao lado da pessoa, com leve desfoque e flutuação. Vídeos anexados entram sempre em tela cheia. Cada inserção fica durante as palavras palavra_inicio..palavra_fim; normalmente 1,5 a 6 s.
B-roll (campo broll): quando houver vídeos de ambiente (sem fala) listados com imagem, encaixe-os DURANTE a locução, cobrindo a imagem da pessoa enquanto a voz continua. Escolha a cena que ilustra o que está sendo dito (ex.: ela fala do espaço, entra a sala; fala da recepção, entra a fachada). Regras: nunca no gancho (primeiro segmento) nem no título; nunca no mesmo intervalo de um destaque; cada B-roll dura de 1,5 a 4 s (palavra_inicio..palavra_fim dentro de um mesmo trecho falado); no máximo 1 a cada 8 a 10 s de vídeo; não repita a mesma cena; mostre o rosto de novo entre um B-roll e outro. Sem vídeos de ambiente, broll fica vazio.
Escolha do momento (inicio_s), como um editor que assistiu o take inteiro: olhe a folha de quadros e o tremor de cada segundo e comece a cena no MELHOR momento: câmera firme (tremor baixo durante toda a duração da cena), enquadramento limpo e a ação que interessa acontecendo (o brinde, a logo aparecendo, a porta abrindo, a sala inteira à mostra). Nunca use um trecho tremido nem o começo do take só por ser o começo. Se o pedido citar um take ou um momento (ex.: 'o brinde final do IMG_2967'), ache nos quadros o segundo em que ele aparece e comece cerca de 1 s antes. Se a cena fecha o vídeo, ela fica até o último quadro, então escolha um trecho que aguente até o fim. Em motivo, diga por que escolheu aquele segundo.
O motor NÃO cria imagens nem vídeos novos: sem anexo ou vídeo de ambiente, não existe B-roll. Também não faz animações, efeitos, transições, zoom animado, música ou mudanças na imagem.
Se o feedback pedir algo que o motor não faz, aplique o resto e escreva claramente em nao_feito o que ficou de fora. O resumo descreve apenas o que esta versão aplica de verdade; nunca diga que fez algo que não está no plano."""

def numerar(palavras, arquivos, papeis=None):
    """Transcrição numerada: '[12] palavra (3.42)' agrupada por arquivo e por frase. Vídeos de ambiente não entram (os índices continuam valendo)."""
    linhas, g = [], 0
    for ai, pw in enumerate(palavras):
        if papeis and papeis[ai] == 'ambiente':
            linhas.append(f"\n=== Arquivo {ai + 1}: {os.path.basename(arquivos[ai])} (vídeo de ambiente, B-roll; não use como fala) ==="); g += len(pw); continue
        linhas.append(f"\n=== Arquivo {ai + 1}: {os.path.basename(arquivos[ai])} ===")
        frase = []
        for k, w in enumerate(pw):
            frase.append(f"[{g}]{w['w']}")
            fim_frase = w['w'][-1:] in '.?!' or (k + 1 < len(pw) and pw[k + 1]['s'] - w['e'] > 0.8)
            if fim_frase or k == len(pw) - 1:
                linhas.append(f"({pw[k - len(frase) + 1]['s']:.1f}s) " + ' '.join(frase)); frase = []
            g += 1
    return '\n'.join(linhas)

def gerar(palavras, arquivos, cliente, dna, regras, briefing='', anterior=None, feedbacks=(), anexos=(), papeis=None, brolls=()):
    client = anthropic.Anthropic()                      # lê ANTHROPIC_API_KEY do ambiente
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
    with client.beta.messages.stream(
        model=MODELO, max_tokens=32000,
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',     # se o modelo recusar, o servidor tenta outro
        output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': ESQUEMA}},
        system=[{'type': 'text', 'text': SISTEMA},
                {'type': 'text', 'text': 'DNA Global Bora (sempre prevalece):\n' + json.dumps({k: v for k, v in regras.items() if k != 'historico'}, ensure_ascii=False), 'cache_control': {'type': 'ephemeral'}},
                {'type': 'text', 'text': 'DNA do cliente:\n' + dna_txt, 'cache_control': {'type': 'ephemeral'}}],
        messages=[{'role': 'user', 'content': _conteudo('\n\n'.join(pedido), brolls)}],
    ) as st:
        msg = st.get_final_message()
    if msg.stop_reason == 'refusal':
        raise RuntimeError('a IA recusou o pedido: ' + str(getattr(msg.stop_details, 'explanation', '')))
    if msg.stop_reason == 'max_tokens':
        raise RuntimeError('o plano ficou grande demais (max_tokens)')
    plano = json.loads(next(b.text for b in msg.content if b.type == 'text'))
    plano['_modelo'] = msg.model
    plano['_uso'] = {'entrada': msg.usage.input_tokens, 'saida': msg.usage.output_tokens}
    import montagem
    amb = {i for i, p in enumerate(papeis or []) if p == 'ambiente'}
    return validar(plano, sum(len(p) for p in palavras), amb, len(brolls), montagem.indice_global(palavras))

def _conteudo(texto, brolls):
    """Texto do pedido + um quadro de cada vídeo de ambiente, pra IA saber o que tem em cada cena."""
    if not brolls: return texto
    import base64
    blocos = [{'type': 'text', 'text': texto + '\n\nVídeos de ambiente disponíveis para B-roll. De cada um: uma folha com vários quadros '
               '(da esquerda pra direita, linha de cima e depois a de baixo, no segundo indicado) e o tremor da câmera em cada segundo '
               f'(0 = firme; acima de {TREMOR} = tremido, não use esse trecho):'}]
    for b in brolls:
        tr = ' '.join(f'{i}s:{x:g}' for i, x in enumerate(b.get('tremor') or []))
        qs = ', '.join(f'{t:g} s' for t in b.get('tempos') or [])
        blocos.append({'type': 'text', 'text': f"B-roll {b['n']}: {b['nome']}, {b['dur']:.1f} s. Quadros em: {qs}. Tremor por segundo: {tr or 'não medido'}"})
        blocos.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(b['jpg'], 'rb').read()).decode()}})
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
