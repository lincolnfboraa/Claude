"""Ajuste pontual: a IA devolve só mudanças; o resto do plano fica igual. Trechos marcados na timeline viram palavras e itens do plano."""
import json, sys
import plano
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
pal = [[{'w': f'p{i}', 's': i * 0.5, 'e': i * 0.5 + 0.4} for i in range(12)]]
atual = {'segmentos': [{'palavra_inicio': 0, 'palavra_fim': 5, 'quadro': 'medio', 'motivo': 'a'}, {'palavra_inicio': 6, 'palavra_fim': 11, 'quadro': 'medio', 'motivo': 'b'}],
         'broll': [], 'destaques': [{'estilo': 'pop', 'palavra_inicio': 2, 'palavra_fim': 2, 'linhas': [{'texto': 'x', 'papel': 'grande'}]}], 'correcoes': [], 'insercoes': [],
         'usar_titulo': False, 'titulo': {'rotulo': '', 'tema': '', 'pergunta': ''}, 'cores': {'legenda': '', 'destaque': ''}, 'resumo': 'r', 'nao_feito': ''}
vistos = []
def falso(sistema, conteudo, esquema=None):
    vistos.append((sistema, conteudo if isinstance(conteudo, str) else conteudo[0]['text'], esquema))
    return {'refazer_tudo': False, 'resumo': 'quadro total no 2º trecho', 'mudancas': [{'tipo': 'segmento', 'acao': 'trocar', 'indice': 1, 'item': json.dumps({'quadro': 'total'}), 'motivo': 'pessoa cortada'}]}
plano._chamar_gpt = falso; plano.IA = 'gpt'
n = plano.ajustar(pal, ['IMG_1.MOV'], {'nome': 'x'}, {}, {}, atual, 'abre o quadro no fim')
ok('usa o esquema de mudanças e mostra o plano com índices', vistos[0][2] is plano.ESQ_AJUSTE and '[1] palavras 6-11' in vistos[0][1] and 'AJUSTE PONTUAL' in vistos[0][0][0])
ok('muda só o item pedido; o resto igual', n['segmentos'][1]['quadro'] == 'total' and n['segmentos'][0] == atual['segmentos'][0] and n['destaques'] == atual['destaques'])
ok('o plano original não é alterado', atual['segmentos'][1]['quadro'] == 'medio')
plano._chamar_gpt = lambda s, c, e=None: {'refazer_tudo': True, 'resumo': '', 'mudancas': []}
ok('pedido que muda a história inteira devolve None (o motor refaz o plano)', plano.ajustar(pal, ['a'], {}, {}, {}, atual, 'muda tudo') is None)
m = plano.aplicar_mudancas(atual, [{'tipo': 'destaque', 'acao': 'remover', 'indice': 0, 'item': '', 'motivo': ''},
                                   {'tipo': 'segmento', 'acao': 'adicionar', 'indice': 1, 'item': json.dumps({'palavra_inicio': 3, 'palavra_fim': 4, 'quadro': 'total', 'motivo': 'n'}), 'motivo': ''},
                                   {'tipo': 'titulo', 'acao': 'trocar', 'indice': 0, 'item': json.dumps({'usar_titulo': True, 'tema': 'Botina'}), 'motivo': ''}])
ok('remover, adicionar na posição e trocar título', not m['destaques'] and [s['palavra_inicio'] for s in m['segmentos']] == [0, 3, 6] and m['usar_titulo'] and m['titulo']['tema'] == 'Botina')
import motor
motor.montagem.pecas = lambda pl, a, p, pasta: (None, [{'i': i, 's': i * 0.5, 'e': i * 0.5 + 0.4, 'tok': f'p{i}'} for i in range(12)], 6)
t = motor.selecoes_texto({'selecoes_v3': [{'t0': 3.0, 't1': 4.0, 'texto': 'o rapaz aparece'}]}, 4, atual, pal, [], '')
ok('trecho marcado vira palavras, segmento e pedido', 'palavras 6-7' in t and 'segmento(s) [1]' in t and 'o rapaz aparece' in t, t[:120])
ok('sem marcação: nada', motor.selecoes_texto({}, 4, atual, pal, [], '') == '')
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
