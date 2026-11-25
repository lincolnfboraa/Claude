"""Revisão interna: prévia abaixo da nota mínima volta pra correção antes de chegar ao editor; entrega a melhor rodada."""
import json, os, shutil, sys, tempfile
T = tempfile.mkdtemp(); os.environ['BORA_TRABALHO'] = T
import motor
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
motor.TRAB = T; pid = 'p1'; pasta = os.path.join(T, pid); os.makedirs(pasta)
def nota(x, enq=8): return {'nota': x, 'motivo': 'm', 'criterios': {c: {'nota': (enq if c == 'enquadramento' else 8), 'motivo': 'porque ' + c} for c in ('gancho', 'storytelling', 'cortes', 'enquadramento', 'complemento')},
                            'problemas': [{'segundo': 14.5, 'fim': 16, 'problema': 'homem cortado na lateral', 'mudanca_esperada': 'quadro total de 14 a 16 s', 'opcoes': ['cortar o trecho']}], 'conferencia': [], 'resumo': 'r'}
def cenario(notas):
    pedidos, entregue, rodada = [], {}, [0]
    def grava(k):
        json.dump({'rodada': k}, open(os.path.join(pasta, 'plano_v6.json'), 'w')); open(os.path.join(pasta, 'previa_v6.mp4'), 'w').write(f'video {k}')
    grava(0); fila = list(notas)
    vistos_esp.clear()
    def av(pac, res, sb_, pasta=None, esperado=()): vistos_esp.append(list(esperado)); return fila.pop(0)
    motor.avaliar_previa = av
    def prep(p, et, sb, correcao=None): pedidos.append(correcao); rodada[0] += 1; return pac
    motor.preparar = prep
    motor.concluir = lambda pac, res, sb, pasta=None, nota=None: entregue.update(nota=nota, plano=json.load(open(os.path.join(pasta_, 'plano_v6.json'))), video=open(os.path.join(pasta_, 'previa_v6.mp4')).read())
    pac = {'projeto_id': pid, 'n': 6, 'plano': 'plano_v6.json'}
    motor.revisar_e_concluir({}, pac, {'arquivos': ['previa_v6.mp4']}, lambda *a, **k: None, None, lambda pc: (grava(rodada[0]), {'arquivos': ['previa_v6.mp4']})[1])
    return pedidos, entregue
pasta_ = pasta
vistos_esp = []
ped, ent = cenario([nota(5.5, 4), nota(8.2)])
ok('nota 5,5: corrige antes de entregar e entrega a rodada boa', len(ped) == 1 and ent['nota']['nota'] == 8.2 and ent['plano']['rodada'] == 1 and ent['video'] == 'video 1')
ok('o pedido de correção leva problema com o segundo, motivo e dica do quadro total', '14 a 16 s: homem cortado' in ped[0] and 'MUDANÇA: quadro total' in ped[0])
ok('enquadramento baixo sugere quadro total', "'total'" in ped[0])
ped, ent = cenario([nota(8.0)])
ok('nota boa de primeira: entrega sem refazer', not ped and ent['nota']['nota'] == 8.0)
ped, ent = cenario([nota(6.8), nota(5.0), nota(6.0)])
ok('correções piores: entrega a melhor rodada (a primeira) com plano e vídeo dela', len(ped) == 2 and ent['nota']['nota'] == 6.8 and ent['plano']['rodada'] == 0 and ent['video'] == 'video 0', str(ent.get('nota', {}).get('nota')))
ok('nota guarda o histórico das rodadas', [r['nota'] for r in ent['nota']['rodadas']] == [6.8, 5.0, 6.0] and ent['nota']['entregue'] == 0)
ok('a rodada seguinte recebe a mudança esperada pra conferir', vistos_esp[0] == [] and 'quadro total de 14 a 16 s' in vistos_esp[1][0])
ok('nenhuma rodada passou: marca decisão editorial com trecho e opções', ent['nota']['decisao_editorial']['trechos'][0]['opcoes'] == ['cortar o trecho'] and ent['nota']['decisao_editorial']['trechos'][0]['fim'] == 16)
ped, ent = cenario([nota(5.5, 4), nota(8.2)])
ok('passou: sem decisão editorial', 'decisao_editorial' not in ent['nota'])
ped, ent = cenario([None])
ok('sem avaliação (IA fora): entrega normal, sem travar', not ped and ent['nota'] is False)
ok('critério abaixo de 6 reprova mesmo com nota alta', not motor.passou(nota(8.0, 5)) and motor.passou(nota(7.5)))
m = {'nota_ia_v6': {'nota': 5.5, 'motivo': 'gente cortada', 'criterios': {'enquadramento': {'nota': 4, 'motivo': 'homem cortado aos 14 s'}}, 'problemas': [{'segundo': 14.5, 'problema': 'homem cortado'}]}, 'nota_editor_v6': {'nota': 5}}
t = motor.avaliacao_anterior(m, 7)
ok('ajuste usa a avaliação da versão anterior por categoria, com a nota do editor', 'enquadramento 4' in t and 'o editor deu 5' in t and '14 s' in t and motor.avaliacao_anterior({}, 7) == '')
shutil.rmtree(T)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
