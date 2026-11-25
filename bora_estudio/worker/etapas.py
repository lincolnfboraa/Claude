"""Storytelling em três etapas (GPT ou Claude, mesmo motor do plano), cada uma salva no projeto:

1. MAPA dos originais: por take, os trechos com papel (gancho, contexto, explicação, prova, fechamento, chamada, bastidor, problema),
   qualidade e observação de imagem, cada um com arquivo e intervalo de origem.
2. ROTEIRO: a ideia central e as falas LITERAIS em sequência (gancho, contexto, desenvolvimento, ponte, fechamento), cada uma com arquivo e intervalo.
   Antes de seguir, é validado: a abertura é respondida? as falas se ligam? o fechamento conclui a ideia? Se não, refaz uma vez com a crítica.
3. PLANO DE EDIÇÃO: o roteiro vira cortes, enquadramento, destaques, B-roll e título (plano.gerar com os segmentos travados no roteiro).

Ajustes partem da versão escolhida: pedido só de texto (card, destaque, título, legenda) mexe só nos textos (áudio e cortes iguais);
pedido de outro fechamento ou de outra fala troca só a parte do roteiro citada e registra qual fala entrou no lugar.
"""
import json, os, time
import plano

PAPEIS_MAPA = ['gancho', 'contexto', 'explicacao', 'prova', 'ponte', 'fechamento', 'chamada', 'bastidor', 'repeticao', 'erro', 'outro']
PAPEIS_ROTEIRO = ['gancho', 'contexto', 'desenvolvimento', 'prova', 'ponte', 'fechamento', 'chamada', 'bastidor']

ESQ_MAPA = {'type': 'object', 'additionalProperties': False, 'required': ['tema', 'trechos', 'ideias_centrais'],
    'properties': {'tema': {'type': 'string', 'description': 'do que o material todo trata, em uma frase'},
                   'ideias_centrais': {'type': 'array', 'items': {'type': 'string'}, 'description': '2 ou 3 ideias centrais possíveis para o vídeo'},
                   'trechos': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                       'required': ['palavra_inicio', 'palavra_fim', 'papel', 'quem', 'emocao', 'resumo', 'qualidade', 'obs_imagem'],
                       'properties': {'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                                      'papel': {'type': 'string', 'enum': PAPEIS_MAPA},
                                      'quem': {'type': 'string', 'description': 'quem fala (ex.: Fabiola, o marido cardiologista, os dois)'},
                                      'emocao': {'type': 'string', 'enum': ['alta', 'media', 'baixa'], 'description': 'história pessoal, humor, surpresa, revelação = alta'},
                                      'resumo': {'type': 'string', 'description': 'o que é dito, curto'},
                                      'qualidade': {'type': 'string', 'enum': ['boa', 'media', 'ruim'], 'description': 'fala limpa e completa = boa; hesitação, frase cortada ou erro = ruim'},
                                      'obs_imagem': {'type': 'string', 'description': 'o que acontece na imagem nesse trecho (quem aparece, plano, gente passando, câmera), vazio se nada a notar'}}}}}}

_PARTE = {'type': 'object', 'additionalProperties': False, 'required': ['papel', 'palavra_inicio', 'palavra_fim', 'motivo'],
          'properties': {'papel': {'type': 'string', 'enum': PAPEIS_ROTEIRO}, 'palavra_inicio': {'type': 'integer'}, 'palavra_fim': {'type': 'integer'},
                         'motivo': {'type': 'string', 'description': 'por que essa fala, nesse ponto da história'}}}
ESQ_ROTEIRO = {'type': 'object', 'additionalProperties': False,
    'required': ['ideia_central', 'promessa_da_abertura', 'partes', 'validacao', 'bastidores_considerados'],
    'properties': {'ideia_central': {'type': 'string'},
                   'promessa_da_abertura': {'type': 'string', 'description': 'a pergunta ou promessa que o gancho cria e que o vídeo precisa responder'},
                   'partes': {'type': 'array', 'items': _PARTE},
                   'bastidores_considerados': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['palavra_inicio', 'usou', 'motivo'],
                                               'properties': {'palavra_inicio': {'type': 'integer'}, 'usou': {'type': 'boolean'}, 'motivo': {'type': 'string'}}},
                                               'description': 'cada trecho de bastidor do mapa: se entrou e por quê'},
                   'validacao': {'type': 'object', 'additionalProperties': False, 'required': ['abertura_respondida', 'ligacao_entre_falas', 'fechamento_conclui', 'comentario'],
                                 'properties': {'abertura_respondida': {'type': 'boolean'}, 'ligacao_entre_falas': {'type': 'boolean'},
                                                'fechamento_conclui': {'type': 'boolean'}, 'comentario': {'type': 'string'}}}}}

ESQ_AJ_ROTEIRO = {'type': 'object', 'additionalProperties': False, 'required': ['tipo', 'trocas', 'resumo'],
    'properties': {'tipo': {'type': 'string', 'enum': ['so_texto', 'imagem', 'roteiro'],
                            'description': "so_texto = só cards, destaques, título, legenda ou cor (áudio e cortes iguais); imagem = enquadramento, B-roll, zoom; roteiro = trocar, tirar ou incluir falas"},
                   'trocas': {'type': 'array', 'description': 'só em roteiro: as partes que mudam (índice da parte atual; -1 = nova parte no fim)',
                              'items': {'type': 'object', 'additionalProperties': False, 'required': ['parte', 'acao', 'nova', 'motivo'],
                                        'properties': {'parte': {'type': 'integer'}, 'acao': {'type': 'string', 'enum': ['trocar', 'remover', 'adicionar']},
                                                       'nova': {'anyOf': [_PARTE, {'type': 'null'}]}, 'motivo': {'type': 'string'}}}},
                   'resumo': {'type': 'string'}}}

CUSTO = []                                                         # etapas desta versão: nome, segundos, tokens de entrada e saída

def _chamar(sistema, conteudo, esquema, nome):
    t0 = time.time()
    r = plano._chamar_gpt(sistema, conteudo, esquema) if plano.IA == 'gpt' else plano._chamar_claude(sistema, conteudo, esquema)
    u = r.get('_uso') or {}
    CUSTO.append({'etapa': nome, 'segundos': round(time.time() - t0, 1), 'entrada': u.get('entrada'), 'saida': u.get('saida'), 'modelo': r.get('_modelo')})
    return r

def _sistema(cliente, dna, regras, extra=''):
    return [plano.SISTEMA + ('\n\n' + extra if extra else ''),
            'DNA Global Bora (sempre prevalece):\n' + json.dumps({k: v for k, v in regras.items() if k != 'historico'}, ensure_ascii=False),
            'DNA do cliente:\n' + json.dumps({'cliente': cliente.get('nome'), 'segmento': cliente.get('segmento'), **(dna or {})}, ensure_ascii=False)]

def origem(palavras, nomes, a, b):
    """(arquivo, início s, fim s, texto literal) de um intervalo de palavras."""
    import montagem
    G = montagem.indice_global(palavras); a, b = max(0, int(a)), min(len(G) - 1, int(b))
    ai = G[a][0]; ws = [palavras[G[i][0]][G[i][1]] for i in range(a, b + 1) if G[i][0] == ai]
    return nomes[ai], round(ws[0]['s'], 1), round(ws[-1]['e'], 1), ' '.join(w['w'] for w in ws)

def mapear(palavras, nomes, papeis, cliente, dna, regras, briefing='', falas=(), brolls=(), marcas=''):
    texto = (f"Transcrição numerada de TODOS os originais:\n{plano.numerar(palavras, nomes, papeis)}\n\n" + (f"Briefing: {briefing}\n\n" if briefing else '') +
             (marcas + '\n\n' if marcas else '') +
             'ETAPA 1, MAPA DOS ORIGINAIS: estude TODO o material antes de qualquer decisão. Divida as falas em trechos (frases ou ideias completas) e diga o papel de cada um, quem fala, a emoção, '
             'a qualidade (hesitação, frase cortada, repetição = ruim) e o que a imagem mostra naquele momento (use as folhas de quadros). Conversas fora do assunto, '
             'combinações de gravação e erros são bastidor, erro ou repeticao. Não monte o vídeo ainda.')
    r = _chamar(_sistema(cliente, dna, regras), plano._conteudo(texto, brolls, falas), ESQ_MAPA, 'mapa')
    total = sum(len(p) for p in palavras); r['trechos'] = [t for t in r.get('trechos') or [] if 0 <= int(t['palavra_inicio']) <= int(t['palavra_fim']) < total]
    for t in r['trechos']:
        arq, s0, s1, lit = origem(palavras, nomes, t['palavra_inicio'], t['palavra_fim']); t.update(arquivo=arq, inicio_s=s0, fim_s=s1, texto=lit)
    return r

def _checar(rot, palavras):
    """Validação por código além da da IA: partes válidas e o fechamento termina em frase completa."""
    import montagem
    G = montagem.indice_global(palavras); problemas = []
    if not rot.get('partes'): return ['roteiro sem partes']
    ult = rot['partes'][-1]; w = palavras[G[int(ult['palavra_fim'])][0]][G[int(ult['palavra_fim'])][1]]['w']
    if w.rstrip()[-1:] not in '.?!': problemas.append(f"a última fala termina em '{w}', no meio da frase")
    v = rot.get('validacao') or {}
    if not v.get('abertura_respondida'): problemas.append('a abertura não é respondida: ' + v.get('comentario', ''))
    if not v.get('ligacao_entre_falas'): problemas.append('falta ligação entre as falas: ' + v.get('comentario', ''))
    if not v.get('fechamento_conclui'): problemas.append('o fechamento não conclui a ideia: ' + v.get('comentario', ''))
    return problemas

def duracao_alvo(dna, briefing=''):
    """(mínimo, máximo) em segundos a partir do DNA ('30 a 60 s...', aprovados maiores contam) e do briefing."""
    import re
    txt = ' '.join(str(x) for x in ((dna or {}).get('duracao') or '', briefing or ''))
    ns = [int(x) for x in re.findall(r'(\d{2,3})\s*(?:a|s|seg|-|,|\))', txt)]
    if not ns: return 45, 90
    return max(35, min(ns)), max(max(ns), 60)

def segundos_roteiro(rot, palavras):
    import montagem
    G = montagem.indice_global(palavras); tot = 0.0
    for p in rot.get('partes') or []:
        a, b = int(p['palavra_inicio']), int(p['palavra_fim'])
        tot += palavras[G[b][0]][G[b][1]]['e'] - palavras[G[a][0]][G[a][1]]['s']
    return tot * 0.88                                                 # pausas cortadas no render

def roteirizar(mapa, palavras, nomes, papeis, cliente, dna, regras, briefing='', pedido='', exigidos=()):
    total = sum(len(p) for p in palavras)
    quem = sorted({t.get('quem') for t in (mapa or {}).get('trechos') or [] if t.get('quem') and t.get('papel') not in ('bastidor', 'erro', 'repeticao')})
    base = (f"Transcrição numerada:\n{plano.numerar(palavras, nomes, papeis)}\n\nMAPA DOS ORIGINAIS (etapa 1):\n" + json.dumps(mapa, ensure_ascii=False) + '\n\n' +
            (f"Briefing: {briefing}\n\n" if briefing else '') + (f"Pedido do editor: {pedido}\n\n" if pedido else '') +
            ('Arquivos que TÊM que entrar: ' + ', '.join(nomes[i] for i in exigidos) + '\n\n' if exigidos else '') +
            'ETAPA 2, ROTEIRO: escolha a ideia central e monte as falas em sequência, só com fala real (intervalos de palavras do mapa ou da transcrição; frases inteiras). '
            'Estrutura: gancho que cria uma pergunta, contexto, desenvolvimento ou prova, ponte quando o assunto muda, fechamento que RESPONDE a abertura e conclui a ideia '
            '(chamada se existir). Prefira trechos de qualidade boa. Responda cada bastidor do mapa. Valide honestamente: a abertura é respondida? as falas se ligam? o fechamento conclui?\n'
            'SEM DURAÇÃO FIXA: o tamanho do vídeo é consequência da estrutura, do contexto e do storytelling. Use todos os momentos que fortalecem a história e corte só o que não serve a ela.\n'
            'EMOÇÃO E PERSONAGENS: comece por um momento que prenda (história pessoal, humor, revelação, emoção alta no mapa) quando existir. '
            + (f'Falam no material: {", ".join(quem)}. Cada pessoa que fala tem um papel na história: use falas de cada uma, e quem aparece em tela precisa ter motivo pra estar ali. ' if len(quem) > 1 else '')
            + 'Bastidor com emoção (riso, cumplicidade, erro engraçado) pode entrar como respiro ou fechamento se combinar com o tom do cliente.')
    rot, problemas = None, []
    for tentativa in (0, 1):
        texto = base + (('\n\nO roteiro anterior falhou na validação: ' + '; '.join(problemas) + '. Corrija: troque a fala que não liga, inclua uma ponte gravada ou escolha outro fechamento que conclua.') if problemas else '')
        rot = _chamar(_sistema(cliente, dna, regras), texto, ESQ_ROTEIRO, 'roteiro' if not tentativa else 'roteiro (refeito)')
        rot['partes'] = [p for p in rot.get('partes') or [] if 0 <= int(p['palavra_inicio']) <= int(p['palavra_fim']) < total]
        problemas = _checar(rot, palavras)
        seg = segundos_roteiro(rot, palavras)
        if len(quem) > 1:
            usados = {t.get('quem') for t in mapa.get('trechos') or [] for p in rot['partes'] if int(t['palavra_inicio']) <= int(p['palavra_fim']) and int(t['palavra_fim']) >= int(p['palavra_inicio'])}
            faltam = [q for q in quem if q not in usados]
            if faltam: problemas.append('quem fala no material e ficou sem nenhuma fala: ' + ', '.join(faltam))
        rot['segundos'] = round(seg, 1)
        if not problemas: break
    rot['problemas'] = problemas                                   # sobra = vai pro editor decidir (o fluxo segue, mas avisa)
    return completar(rot, palavras, nomes, mapa)

def completar(rot, palavras, nomes, mapa=None):
    """Cada parte ganha arquivo, intervalo de origem, fala literal e as observações de imagem do mapa naquele trecho."""
    for p in rot.get('partes') or []:
        arq, s0, s1, lit = origem(palavras, nomes, p['palavra_inicio'], p['palavra_fim'])
        obs = [t['obs_imagem'] for t in (mapa or {}).get('trechos') or [] if t.get('obs_imagem') and int(t['palavra_inicio']) <= int(p['palavra_fim']) and int(t['palavra_fim']) >= int(p['palavra_inicio'])]
        p.update(arquivo=arq, inicio_s=s0, fim_s=s1, texto=lit, obs_imagem=' | '.join(obs))
    return rot

def aplicar_trocas(rot, trocas):
    """Troca só as partes citadas; as outras ficam exatamente iguais. Devolve (roteiro novo, lista do que entrou no lugar de quê)."""
    partes = [dict(p) for p in rot.get('partes') or []]; feitas = []; remover = set(); novas_fim = []
    for t in trocas or []:
        k, nova = int(t.get('parte', -1)), t.get('nova')
        if t['acao'] == 'trocar' and 0 <= k < len(partes) and nova:
            feitas.append({'parte': k, 'antes': partes[k].get('texto', ''), 'depois': None, 'motivo': t.get('motivo', '')}); partes[k] = dict(nova); feitas[-1]['_nova'] = k
        elif t['acao'] == 'remover' and 0 <= k < len(partes):
            remover.add(k); feitas.append({'parte': k, 'antes': partes[k].get('texto', ''), 'depois': '(removida)', 'motivo': t.get('motivo', '')})
        elif t['acao'] == 'adicionar' and nova:
            novas_fim.append((k, dict(nova))); feitas.append({'parte': k, 'antes': '', 'depois': None, 'motivo': t.get('motivo', ''), '_add': len(novas_fim) - 1})
    out = []
    for k, p in enumerate(partes):
        out += [n for kk, n in novas_fim if kk == k]
        if k not in remover: out.append(p)
    out += [n for kk, n in novas_fim if kk < 0 or kk >= len(partes)]
    return {**rot, 'partes': out}, feitas

def ajustar_roteiro(rot, mapa, palavras, nomes, papeis, cliente, dna, regras, pedido):
    """Classifica o pedido e, se for de roteiro, troca só as partes citadas (o resto travado)."""
    lista = '\n'.join(f"[{k}] {p['papel']} ({p.get('arquivo')} {p.get('inicio_s')} a {p.get('fim_s')} s, palavras {p['palavra_inicio']}-{p['palavra_fim']}): {p.get('texto', '')}"
                      for k, p in enumerate(rot.get('partes') or []))
    texto = (f"Transcrição numerada:\n{plano.numerar(palavras, nomes, papeis)}\n\nMAPA:\n{json.dumps(mapa, ensure_ascii=False)}\n\nROTEIRO ATUAL (aprovado em tudo que o pedido não cita):\n{lista}\n\n"
             f"Pedido do editor: {pedido}\n\nClassifique o pedido. Se for de roteiro, troque SÓ as partes citadas, com fala real (frases inteiras), e mantenha as outras exatamente iguais. "
             'Um novo fechamento tem que concluir a ideia e responder a abertura.')
    r = _chamar(_sistema(cliente, dna, regras), texto, ESQ_AJ_ROTEIRO, 'ajuste do roteiro')
    if r.get('tipo') != 'roteiro': return r.get('tipo'), rot, [], r.get('resumo', '')
    total = sum(len(p) for p in palavras)
    trocas = [t for t in r.get('trocas') or [] if not t.get('nova') or 0 <= int(t['nova']['palavra_inicio']) <= int(t['nova']['palavra_fim']) < total]
    novo, feitas = aplicar_trocas(rot, trocas)
    novo = completar(novo, palavras, nomes, mapa)
    for f in feitas:                                               # mostra qual fala entrou no lugar
        if '_nova' in f: f['depois'] = novo['partes'][min(f.pop('_nova'), len(novo['partes']) - 1)].get('texto', '')
        if '_add' in f: f.pop('_add'); f['depois'] = f['depois'] or '(nova parte)'
    novo['problemas'] = _checar({**novo, 'validacao': {'abertura_respondida': True, 'ligacao_entre_falas': True, 'fechamento_conclui': True}}, palavras)
    return 'roteiro', novo, feitas, r.get('resumo', '')

def segmentos_do_roteiro(rot, pl):
    """Os segmentos do plano passam a ser EXATAMENTE as partes do roteiro (o enquadramento escolhido no plano é mantido pela ordem)."""
    seg = pl.get('segmentos') or []
    pl['segmentos'] = [{'palavra_inicio': int(p['palavra_inicio']), 'palavra_fim': int(p['palavra_fim']),
                        'quadro': (seg[k]['quadro'] if k < len(seg) else 'medio'), 'motivo': f"{p['papel']}: {p.get('motivo', '')}"} for k, p in enumerate(rot['partes'])]
    return pl

def texto_roteiro_para_plano(rot):
    return ('ROTEIRO APROVADO (etapa 2): os segmentos do plano são EXATAMENTE estas partes, nesta ordem (mesmas palavras); decida só enquadramento, título, destaques, '
            'B-roll e correções de grafia:\n' + '\n'.join(f"{k}. {p['papel']}: palavras {p['palavra_inicio']}-{p['palavra_fim']}: {p.get('texto', '')}" + (f" [imagem: {p['obs_imagem']}]" if p.get('obs_imagem') else '')
                                                         for k, p in enumerate(rot['partes'])))
