"""Plano de edição feito pela IA (Claude, via SDK oficial `anthropic`).
Entrada: transcrição numerada palavra a palavra, DNA ativo do cliente, regras globais, briefing e o histórico de feedback.
Saída: JSON validado por esquema (structured outputs): segmentos, título, destaques, correções e resumo.
A IA só escolhe e ordena o que FOI falado; nunca inventa fala. O vídeo em si é montado pelo ffmpeg (montagem.py)."""
import json, os
import anthropic

MODELO = os.environ.get('BORA_MODELO', 'claude-opus-5-5')

ESQUEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['segmentos', 'usar_titulo', 'titulo', 'destaques', 'insercoes', 'correcoes', 'cores', 'resumo', 'nao_feito'],
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
O motor NÃO cria imagens nem vídeos novos: sem anexo, não existe B-roll. Também não faz animações, efeitos, transições, zoom animado, música ou mudanças na imagem.
Se o feedback pedir algo que o motor não faz, aplique o resto e escreva claramente em nao_feito o que ficou de fora. O resumo descreve apenas o que esta versão aplica de verdade; nunca diga que fez algo que não está no plano."""

def numerar(palavras, arquivos):
    """Transcrição numerada: '[12] palavra (3.42)' agrupada por arquivo e por frase."""
    linhas, g = [], 0
    for ai, pw in enumerate(palavras):
        linhas.append(f"\n=== Arquivo {ai + 1}: {os.path.basename(arquivos[ai])} ===")
        frase = []
        for k, w in enumerate(pw):
            frase.append(f"[{g}]{w['w']}")
            fim_frase = w['w'][-1:] in '.?!' or (k + 1 < len(pw) and pw[k + 1]['s'] - w['e'] > 0.8)
            if fim_frase or k == len(pw) - 1:
                linhas.append(f"({pw[k - len(frase) + 1]['s']:.1f}s) " + ' '.join(frase)); frase = []
            g += 1
    return '\n'.join(linhas)

def gerar(palavras, arquivos, cliente, dna, regras, briefing='', anterior=None, feedbacks=(), anexos=()):
    client = anthropic.Anthropic()                      # lê ANTHROPIC_API_KEY do ambiente
    dna_txt = json.dumps({'cliente': cliente.get('nome'), 'segmento': cliente.get('segmento'), 'status': cliente.get('status'), **(dna or {})}, ensure_ascii=False)
    pedido = [f"Transcrição numerada (use os números entre colchetes):\n{numerar(palavras, arquivos)}"]
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
        messages=[{'role': 'user', 'content': '\n\n'.join(pedido)}],
    ) as st:
        msg = st.get_final_message()
    if msg.stop_reason == 'refusal':
        raise RuntimeError('a IA recusou o pedido: ' + str(getattr(msg.stop_details, 'explanation', '')))
    if msg.stop_reason == 'max_tokens':
        raise RuntimeError('o plano ficou grande demais (max_tokens)')
    plano = json.loads(next(b.text for b in msg.content if b.type == 'text'))
    plano['_modelo'] = msg.model
    plano['_uso'] = {'entrada': msg.usage.input_tokens, 'saida': msg.usage.output_tokens}
    return validar(plano, sum(len(p) for p in palavras))

def validar(plano, total):
    """Garante índices dentro da transcrição e ordem certa (a IA não consegue apontar pra fala que não existe)."""
    ok = []
    for s in plano['segmentos']:
        a, b = int(s['palavra_inicio']), int(s['palavra_fim'])
        if 0 <= a <= b < total: ok.append(s)
    if not ok: raise RuntimeError('o plano não trouxe nenhum trecho válido')
    plano['segmentos'] = ok
    plano['insercoes'] = [x for x in plano.get('insercoes', []) if 0 <= int(x['palavra_inicio']) <= int(x['palavra_fim']) < total]
    plano['destaques'] = [d for d in plano.get('destaques', []) if 0 <= int(d['palavra_inicio']) <= int(d['palavra_fim']) < total][:7]
    return plano
