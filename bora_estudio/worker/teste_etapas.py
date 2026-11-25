"""Três etapas: mapa -> roteiro validado -> plano; ajuste só de texto preserva cortes; troca de fechamento troca só a parte e mostra o que entrou."""
import json, os, sys, tempfile, shutil
T = tempfile.mkdtemp(); os.environ['BORA_TRABALHO'] = T
import plano, etapas, motor
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
frases = [['Quando', 'a', 'gente', 'tem', 'doença', 'renal,', 'o', 'coração', 'sofre.'], ['O', 'risco', 'é', 'maior', 'no', 'coração.'],
          ['Você', 'imagina', 'isso?'], ['e', 'muitas', 'vezes', 'as', 'pessoas', 'não', 'tratam', 'a'], ['Vamos', 'gravar', 'de', 'novo?']]
pal = []; t = 0.0
for f in frases:
    ws = []
    for w in f: ws.append({'w': w, 's': t, 'e': t + 0.3}); t += 0.4
    pal.append(ws)
pal = [sum(pal[:4], []), pal[4]]; nomes = ['IMG_2566.mov', 'IMG_2565.mov']
idx = lambda: None
chamadas = []
def falso(sistema, conteudo, esquema=None):
    txt = conteudo if isinstance(conteudo, str) else conteudo[0]['text']; chamadas.append((esquema, txt))
    if esquema is etapas.ESQ_MAPA:
        return {'tema': 'rim e coração', 'ideias_centrais': ['risco cardiovascular'], 'trechos': [
            {'palavra_inicio': 0, 'palavra_fim': 8, 'papel': 'gancho', 'quem': 'Fabiola', 'emocao': 'media', 'resumo': 'r', 'qualidade': 'boa', 'obs_imagem': 'close dela'},
            {'palavra_inicio': 26, 'palavra_fim': 29, 'papel': 'bastidor', 'resumo': 'combinando gravação', 'qualidade': 'ruim', 'obs_imagem': 'os dois rindo'}]}
    if esquema is etapas.ESQ_ROTEIRO:
        fim = 25 if len([c for c in chamadas if c[0] is etapas.ESQ_ROTEIRO]) == 1 else 17      # 1ª: fecha no meio da frase ('a'); 2ª: fecha em 'isso?'
        return {'ideia_central': 'c', 'promessa_da_abertura': 'p', 'bastidores_considerados': [{'palavra_inicio': 26, 'usou': False, 'motivo': 'fora do assunto'}],
                'partes': [{'papel': 'gancho', 'palavra_inicio': 0, 'palavra_fim': 8, 'motivo': 'm'}, {'papel': 'prova', 'palavra_inicio': 9, 'palavra_fim': 14, 'motivo': 'm'},
                           {'papel': 'fechamento', 'palavra_inicio': 15 if fim == 17 else 18, 'palavra_fim': fim, 'motivo': 'm'}],
                'validacao': {'abertura_respondida': True, 'ligacao_entre_falas': True, 'fechamento_conclui': True, 'comentario': ''}, '_uso': {'entrada': 1000, 'saida': 200}}
    if esquema is etapas.ESQ_AJ_ROTEIRO:
        if 'troca o card' in txt: return {'tipo': 'so_texto', 'trocas': [], 'resumo': 'só o card'}
        return {'tipo': 'roteiro', 'resumo': 'novo fechamento', 'trocas': [{'parte': 2, 'acao': 'trocar', 'nova': {'papel': 'fechamento', 'palavra_inicio': 9, 'palavra_fim': 14, 'motivo': 'conclui'}, 'motivo': 'pedido'}]}
    if esquema is plano.ESQ_AJUSTE:
        return {'refazer_tudo': False, 'resumo': 'card', 'mudancas': [{'tipo': 'destaque', 'acao': 'adicionar', 'indice': -1, 'item': json.dumps({'estilo': 'pop', 'palavra_inicio': 4, 'palavra_fim': 5, 'linhas': [{'texto': 'renal', 'papel': 'grande'}]}), 'motivo': ''}]}
    return {'segmentos': [{'palavra_inicio': 0, 'palavra_fim': 3, 'quadro': 'fechado', 'motivo': 'x'}], 'usar_titulo': False, 'titulo': {'rotulo': '', 'tema': '', 'pergunta': ''},
            'destaques': [], 'insercoes': [], 'broll': [], 'correcoes': [], 'cores': {'legenda': '', 'destaque': ''}, 'resumo': 'r', 'nao_feito': '', 'marcas': [], '_uso': {'entrada': 3000, 'saida': 500}}
plano._chamar_gpt = falso; plano.IA = 'gpt'
meta = {}
def sb(m, path, corpo=None):
    if m == 'GET': return [{'original_meta': json.loads(json.dumps(meta))}]
    meta.clear(); meta.update(corpo['original_meta']); return []
pasta = os.path.join(T, 'p'); os.makedirs(pasta)
pl = motor.tres_etapas(meta, 1, pasta, pal, nomes, ['fala', 'fala'], ['a', 'b'], {'nome': 'Fabiola'}, {}, {}, [], [], [], set(), [], '', None, lambda *a: None, sb, 'p')
rot = json.load(open(os.path.join(pasta, 'roteiro_v1.json')))
ok('mapa salvo com arquivo, intervalo e texto literal', os.path.exists(os.path.join(pasta, 'mapa.json')) and meta['mapa']['trechos'][0]['arquivo'] == 'IMG_2566.mov' and meta['mapa']['trechos'][0]['texto'].startswith('Quando'))
ok('roteiro que fechava no meio da frase foi refeito antes do render', sum(1 for c in chamadas if c[0] is etapas.ESQ_ROTEIRO) == 2 and rot['partes'][-1]['texto'].endswith('isso?'))
ok('cada fala do roteiro aponta arquivo e intervalo, com a observação de imagem', all(p['arquivo'] and p['fim_s'] > p['inicio_s'] for p in rot['partes']) and rot['partes'][0]['obs_imagem'] == 'close dela')
ok('plano usa exatamente as partes do roteiro', [(s['palavra_inicio'], s['palavra_fim']) for s in pl['segmentos']] == [(p['palavra_inicio'], p['palavra_fim']) for p in rot['partes']])
ok('bastidor considerado e registrado', meta['roteiro_v1']['bastidores'][0]['motivo'] == 'fora do assunto')
ok('custo e tempo por etapa registrados', [e['etapa'] for e in meta['custo_v1']['etapas']] == ['mapa', 'roteiro', 'roteiro (refeito)', 'plano de edição'] and meta['custo_v1']['etapas'][1]['entrada'] == 1000)
json.dump(pl, open(os.path.join(pasta, 'plano_v1.json'), 'w'))
chamadas.clear()
pl2 = motor.tres_etapas(meta, 2, pasta, pal, nomes, ['fala', 'fala'], ['a', 'b'], {'nome': 'Fabiola'}, {}, {}, [(1, 'troca o card do gancho')], [], [], set(), [], '', None, lambda *a: None, sb, 'p')
ok('pedido só de texto: mesmos cortes e áudio da versão escolhida', pl2['segmentos'] == pl['segmentos'] and pl2['_roteiro']['tipo'] == 'so_texto' and len(pl2['destaques']) == 1)
ok('mapa não é refeito no ajuste', not any(c[0] is etapas.ESQ_MAPA for c in chamadas))
json.dump(pl2, open(os.path.join(pasta, 'plano_v2.json'), 'w'))
meta['base_ajuste'] = {'para': 3, 'base': 1}
pl3 = motor.tres_etapas(meta, 3, pasta, pal, nomes, ['fala', 'fala'], ['a', 'b'], {'nome': 'Fabiola'}, {}, {}, [(2, 'quero outro fechamento')], [], [], set(), [], '', None, lambda *a: None, sb, 'p')
r3 = meta['roteiro_v3']
ok('ajuste parte da versão escolhida (v1)', r3['base'] == 1)
ok('outro fechamento: troca só a parte 2 e mostra o que entrou no lugar', r3['trocas'][0]['antes'].endswith('isso?') and r3['trocas'][0]['depois'].startswith('O risco') and r3['partes'][0] == meta['roteiro_v1']['partes'][0])
ras = meta['rastreio_v1']
ok('rastreio por versão: cada trecho do mapa diz onde entrou ou em que etapa saiu', len(ras['trechos']) == 2 and ras['trechos'][1]['saiu_em'] == 'roteiro' and ras['trechos'][1]['motivo'] == 'fora do assunto' and ras['trechos'][0]['roteiro'] == [1])
ok('tempo retirado: material, escolhido e prévia', set(ras['tempos']) >= {'material_s', 'escolhido_s', 'previa_s', 'tirado_roteiro_s', 'tirado_pausas_s'})
mapa = json.load(open(os.path.join(pasta, 'mapa.json')))
r = etapas.roteirizar(mapa, pal, nomes, ['fala', 'fala'], {}, {}, {}, modo={'tipo': 'limpar'})
ok('modo só limpar pausas: falas na ordem gravada, sem bastidor e sem chamar a IA', [p['palavra_inicio'] for p in r['partes']] == [0] and r['partes'][0]['texto'].startswith('Quando'))
chamadas.clear(); etapas.roteirizar(mapa, pal, nomes, ['fala', 'fala'], {}, {}, {}, modo={'tipo': 'resumir', 'segundos': 20})
ok('modo resumir: pede o limite à IA', 'até 20 s' in chamadas[0][1])
shutil.rmtree(T)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
