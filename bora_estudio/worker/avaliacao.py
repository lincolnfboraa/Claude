"""Nota da IA (0 a 10) pra cada prévia: um editor sênior assiste (quadros a cada 2 s + o que foi falado + o pedido) e dá nota com critérios e problemas.
Roda no VPS depois que a prévia sobe, em segundo plano (não atrasa a entrega). Fica em original_meta.nota_ia_vN; a nota do editor fica em nota_editor_vN (app)."""
import base64, json, os, subprocess
import plano

CRITERIOS = ['gancho', 'storytelling', 'cortes', 'enquadramento', 'complemento']
NOMES = {'gancho': 'Gancho', 'storytelling': 'Storytelling', 'cortes': 'Cortes', 'enquadramento': 'Enquadramento', 'complemento': 'Complemento'}
_CRIT = {'type': 'object', 'additionalProperties': False, 'required': ['nota', 'motivo'],
         'properties': {'nota': {'type': 'number'}, 'motivo': {'type': 'string', 'description': 'por que essa nota, citando o que viu (frase, segundo, cena)'}}}
ESQ = {'type': 'object', 'additionalProperties': False, 'required': ['nota', 'motivo', 'criterios', 'problemas', 'conferencia', 'resumo'],
       'properties': {'nota': {'type': 'number', 'description': '0 a 10, uma casa decimal'},
                      'motivo': {'type': 'string', 'description': 'por que essa nota final, olhando o vídeo como um todo (2 a 4 frases)'},
                      'criterios': {'type': 'object', 'additionalProperties': False, 'required': CRITERIOS, 'properties': {c: _CRIT for c in CRITERIOS}},
                      'problemas': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['segundo', 'fim', 'problema', 'mudanca_esperada', 'opcoes'],
                                                               'properties': {'segundo': {'type': 'number'}, 'fim': {'type': 'number', 'description': 'segundo em que o trecho com problema termina'},
                                                                              'problema': {'type': 'string', 'description': 'o que falhou e por quê'},
                                                                              'mudanca_esperada': {'type': 'string', 'description': 'a mudança concreta que precisa aparecer na próxima versão'},
                                                                              'opcoes': {'type': 'array', 'items': {'type': 'string'}, 'description': 'saídas possíveis se a mudança não puder ser feita (ex.: outra fala real, B-roll, cortar o trecho)'}}}},
                      'conferencia': {'type': 'array', 'description': 'uma por mudança esperada informada no pedido (vazio se nenhuma)',
                                      'items': {'type': 'object', 'additionalProperties': False, 'required': ['mudanca', 'aconteceu', 'comentario'],
                                                'properties': {'mudanca': {'type': 'string'}, 'aconteceu': {'type': 'boolean'}, 'comentario': {'type': 'string'}}}},
                      'resumo': {'type': 'string', 'description': 'uma frase, em português simples'}}}

RUBRICA = """Você é um editor sênior de Reels avaliando uma prévia antes de mostrar ao cliente. Avalie o vídeo como um TODO, no contexto do cliente, do objetivo do vídeo e do pedido do editor.
Seja exigente e honesto: a nota mede se a edição acerta de primeira. Cada nota vem com o MOTIVO, citando o que você viu (a frase, o segundo, a cena).
Escala: 10 = pronto pra postar, nada a mudar; 8 a 9 = detalhe pequeno; 6 a 7 = precisa de um ajuste claro; 4 a 5 = vários problemas ou um grave; 0 a 3 = refazer.
Critérios (0 a 10 cada, com motivo):
- gancho: os primeiros 3 segundos prendem? Frase forte, curiosidade ou oferta clara logo de cara, título (se houver) bom e legível.
- storytelling: a história faz sentido do começo ao fim (gancho, contexto, desenvolvimento, fechamento/chamada), sem repetição, sem fala solta, todas as partes pedidas pelo editor presentes e completas (lista de ofertas inteira, take pedido), fechamento com chamada clara.
- cortes: cortes assertivos: sem frase cortada no meio, sem palavra comida, sem repetição, sem pausa longa, ritmo bom, sem trecho em que outra pessoa entra no quadro ou alguém troca produto na frente de quem fala.
- enquadramento: ninguém cortado na lateral, respiro acima da cabeça, zoom coerente (sem pular de escala sem motivo), câmera firme.
- complemento: o conjunto que apoia a fala: B-roll no momento certo e firme, legenda legível e sem erro (valores, nomes), destaques poucos e bem colocados (nada em cima do rosto), cores e identidade do cliente.
Respeite o estilo APROVADO no DNA do cliente (ex.: legenda pequena minimalista branca com sombra leve, título sem caixa): não tire ponto por isso, só por erro real (texto ilegível, em cima do rosto, valor errado).
Confira se a ÚLTIMA fala fecha a ideia (frase completa, não termina no meio nem numa constatação solta) antes da cartela final; se não fechar, é problema grave de storytelling, com o trecho e a mudança.
Use a verificação 'Legenda legível sobre a imagem' (mede o fundo real): onde ela acusar fundo claro, aponte o trecho.
No storytelling, só cobre o que existe nas gravações: se nenhum take tem orientação ou chamada, diga isso no motivo mas não desça abaixo de 6 só por esse motivo.
História pessoal, humor e emoção são o que prende: nunca peça para remover; se parecem soltos, peça a ordem certa ou uma ponte.
A nota final NÃO é a média: um problema grave (pessoa cortada, pedido do editor ignorado, alguém atravessando o quadro, gancho fraco) puxa a nota pra 6 ou menos.
Em problemas, cite o trecho (segundo e fim), o que falhou e por quê, a mudança concreta que precisa aparecer na próxima versão e as opções se ela não for possível.
Se o pedido trouxer 'Mudanças esperadas', confira CADA uma nesta versão (conferencia: aconteceu sim ou não, com o que viu) e não repita como problema novo o que já foi resolvido. Responda só o JSON."""

def _folha(previa, saida, passo=2.0):
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', previa], capture_output=True, text=True).stdout or 0)
    n = max(1, min(32, int(dur / passo))); passo = dur / n; cols = 8; lin = -(-n // cols)
    tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,'
    for t_ in (tm, ''):
        r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', previa, '-vf', f'fps=1/{passo:.3f},{t_}scale=180:-2,tile={cols}x{lin}', '-frames:v', '1', '-q:v', '4', saida], capture_output=True)
        if r.returncode == 0 and os.path.exists(saida): return saida, [round(i * passo, 1) for i in range(n)], dur
    return None, [], dur

def avaliar(previa, pl, pal, pedido, verif, pasta, contexto='', esperado=(), livro=''):
    """Devolve {nota, criterios, problemas, resumo, modelo} ou None."""
    import montagem
    jpg, tempos, dur = _folha(previa, os.path.join(pasta, 'avaliacao_folha.jpg'))
    if not jpg: return None
    G = montagem.indice_global(pal); fala = []
    for k, sg in enumerate(pl.get('segmentos') or []):
        a, b = int(sg['palavra_inicio']), int(sg['palavra_fim'])
        fala.append(f"{k + 1}. ({sg.get('quadro')}) " + ' '.join(pal[G[i][0]][G[i][1]]['w'] for i in range(a, b + 1) if i < len(G)))
    br = [f"B-roll {b.get('video')} nas palavras {b.get('palavra_inicio')} a {b.get('palavra_fim')}: {b.get('motivo', '')}" for b in pl.get('broll') or []]
    tit = pl.get('titulo') or {}
    texto = ((f"Contexto do cliente e do vídeo: {contexto}\n\n" if contexto else '') + f"Prévia de {dur:.1f} s. Quadros na folha (da esquerda pra direita, linha por linha) nos segundos: {', '.join(f'{t:g}' for t in tempos)}.\n\n"
             f"Pedido do editor pra esta versão: {pedido or '(primeira versão, sem pedido de ajuste)'}\n\n"
             f"Falas usadas, na ordem (a 1ª é o gancho):\n" + '\n'.join(fala) + '\n\n' + ('B-roll:\n' + '\n'.join(br) + '\n\n' if br else '') +
             (f"Título: {tit.get('rotulo', '')} / {tit.get('tema', '')} / {tit.get('pergunta', '')}\n" if pl.get('usar_titulo') else '') +
             'Destaques: ' + ', '.join(str(d.get('texto') or '') for d in pl.get('destaques') or []) + '\n\n'
             'Verificação automática: ' + '; '.join(f"{x['item']}: {x['detalhe']}" for x in verif or []) +
             ('\n\nMudanças esperadas nesta versão (confira cada uma):\n' + '\n'.join(f'- {m}' for m in esperado) if esperado else ''))
    img = base64.b64encode(open(jpg, 'rb').read()).decode()
    if plano.IA == 'gpt':
        from openai import OpenAI
        r = OpenAI(timeout=300).responses.create(model=plano.MODELO_GPT, instructions=(livro + '\n\n' if livro else '') + RUBRICA, store=False, max_output_tokens=4000,
            input=[{'role': 'user', 'content': [{'type': 'input_text', 'text': texto}, {'type': 'input_image', 'image_url': f'data:image/jpeg;base64,{img}', 'detail': 'high'}]}],
            text={'format': {'type': 'json_schema', 'name': 'avaliacao', 'schema': ESQ, 'strict': True}})
        out, modelo = json.loads(r.output_text), r.model
    else:
        import anthropic
        msg = anthropic.Anthropic().messages.create(model=plano.MODELO, max_tokens=4000, system=(livro + '\n\n' if livro else '') + RUBRICA,
            output_config={'format': {'type': 'json_schema', 'schema': ESQ}},
            messages=[{'role': 'user', 'content': [{'type': 'text', 'text': texto}, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img}}]}])
        out, modelo = json.loads(next(b.text for b in msg.content if b.type == 'text')), msg.model
    lim = lambda x: round(min(10.0, max(0.0, float(x))), 1)
    out['nota'] = lim(out['nota']); out['criterios'] = {c: {'nota': lim(v['nota']), 'motivo': v['motivo']} for c, v in out['criterios'].items()}
    out['problemas'] = out['problemas'][:8]; out['conferencia'] = out.get('conferencia') or []; out['modelo'] = modelo
    return out
