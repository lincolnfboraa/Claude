"""Take pedido pelo editor (anexo com o mesmo nome de um original, ou citado no pedido) tem que entrar no storytelling."""
import os, sys
import motor, plano
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
arqs = ['/t/original_01.mov', '/t/original_02.mov', '/t/original_03.mov', '/t/original_04.mov']
# nomes originais vêm dos arquivos do projeto: aqui usamos nomes reais pra casar
arqs = ['/t/IMG_1703.MOV', '/t/IMG_1704.MOV', '/t/IMG_1705.MOV', '/t/IMG_1706.MOV']; pap = ['fala', 'fala', 'fala', 'ambiente']
ex, cas = motor.exigir_takes(arqs, pap, [{'nome': 'IMG_1705.mov', 'tipo': 'video'}], [''])
ok('anexo com o mesmo nome do original (maiúscula/minúscula) vira pedido de uso', ex == {2} and len(cas) == 1)
ex, cas = motor.exigir_takes(arqs, pap, [], ['', 'Faltou o IMG_1704 no storytelling'])
ok('take citado no feedback entra como exigido', ex == {1} and not cas)
ex, _ = motor.exigir_takes(arqs, pap, [], ['coloca o 1705 no meio'])
ok('só o número (1705) também vale', ex == {2})
ex, cas = motor.exigir_takes(arqs, pap, [{'nome': 'logo.png', 'tipo': 'imagem'}, {'nome': 'IMG_1706.mov', 'tipo': 'video'}], [''])
ok('imagem diferente e vídeo de ambiente continuam sendo anexo normal', not ex and not cas)
ex, cas = motor.exigir_takes(arqs, pap, [{'nome': 'capa.png', 'capa_final': True}], ['IMG_17050 e 17051'])
ok('capa final e números parecidos não confundem', not ex and not cas)
# o plano é refeito uma vez se o take pedido ficou de fora
pal = [[{'w': f'a{i}', 's': i, 'e': i + .5} for i in range(5)] for _ in range(3)]       # 3 arquivos de 5 palavras (0-4, 5-9, 10-14)
chamadas = []
def falso(sistema, conteudo):
    chamadas.append(conteudo if isinstance(conteudo, str) else conteudo[0]['text'])
    ini = 0 if len(chamadas) == 1 else 10
    return {'segmentos': [{'palavra_inicio': ini, 'palavra_fim': ini + 4, 'quadro': 'medio', 'motivo': 'x'}], 'insercoes': [], 'destaques': [], 'broll': []}
plano._chamar_gpt = falso; plano.IA = 'gpt'
pl = plano.gerar(pal, ['/t/a.mov', '/t/b.mov', '/t/c.mov'], {'nome': 'x'}, {}, {}, '', None, (), (), ['fala'] * 3, (), exigidos={2})
ok('plano sem o take pedido: refaz uma vez com aviso e passa a usar o take', len(chamadas) == 2 and 'NÃO usou' in chamadas[1] and pl['segmentos'][0]['palavra_inicio'] == 10, f'{len(chamadas)} chamadas')
chamadas.clear(); plano.gerar(pal, ['/t/a.mov', '/t/b.mov', '/t/c.mov'], {'nome': 'x'}, {}, {}, '', None, (), (), ['fala'] * 3, ())
ok('sem take exigido: uma chamada só', len(chamadas) == 1)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
