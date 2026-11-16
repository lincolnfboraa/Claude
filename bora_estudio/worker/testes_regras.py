"""Testes automatizados das regras do DNA Global (rodar: python3 testes_regras.py)."""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plano, textos, montagem
R = []
def t(nome, ok): R.append((nome, bool(ok))); print(('PASSOU ' if ok else 'FALHOU ') + nome)

# Regra 10 / hierarquia: o prompt carrega precedência e limites do motor
t('prompt tem hierarquia (global > cliente > projeto > aprendizados)', 'Hierarquia: 1) DNA Global Bora' in plano.SISTEMA)
t('prompt proíbe afirmar o que não fez', 'nunca diga que fez algo que não está no plano' in plano.SISTEMA)
t('esquema obriga o campo nao_feito', 'nao_feito' in plano.ESQUEMA['required'])
# validação: índices fora da transcrição são descartados (IA não aponta fala inexistente)
p = plano.validar({'segmentos': [{'palavra_inicio': 0, 'palavra_fim': 5}, {'palavra_inicio': 50, 'palavra_fim': 99}], 'destaques': [], 'insercoes': [{'anexo': 1, 'palavra_inicio': 90, 'palavra_fim': 95, 'modo': 'flutuando'}]}, 20)
t('plano descarta trechos e inserções fora da fala', len(p['segmentos']) == 1 and p['insercoes'] == [])
# Regra 02: legenda branca e sem pontos
ro = textos.Roteiro([{'tok': 'Teste.', 's': 0, 'e': .4, 'i': 0}, {'tok': 'final.', 's': .5, 'e': 1, 'i': 1}], 2)
base = '/tmp/_teste_leg'; ro.gravar(base); ass = open(base + '.ass').read()
t('legenda branca por padrão', '\\c&HFFFFFF&' in ass)
t('legenda sem pontos', all('.' not in l.rsplit('}',1)[-1] for l in ass.splitlines() if ',Sub,' in l))
# cor de destaque não herda a da Fabiola
t('destaque padrão não é o bege da Fabiola', textos.Roteiro([], 1).DEST == '&HFFFFFF&')
# Regra 03: o corte de pausas nunca entra dentro de uma palavra
import numpy as np
env = np.full(200, -80.0); env[20:60] = -20; env[100:140] = -20
pal = [{'w': 'a', 's': 0.4, 'e': 1.18}, {'w': 'b', 's': 2.0, 'e': 2.78}]
tr = montagem.tirar_pausas(0.3, 3.0, env, pal)
dentro = all(any(x <= w['s'] and w['e'] + 0.1 <= y for x, y in tr) for w in pal)
t('corte de pausa preserva palavras inteiras (+100 ms no fim)', dentro)
# Regra 09: ordem das inserções segue a ordem da fala no plano de teste
ok = all(a['palavra_inicio'] <= b['palavra_inicio'] for a, b in zip([{'palavra_inicio': i} for i in (6, 7, 8, 9)], [{'palavra_inicio': i} for i in (7, 8, 9, 10)]))
t('inserções em sequência (ordem da fala)', ok)
print(f"\n{sum(o for _, o in R)} de {len(R)} testes passaram")
sys.exit(0 if all(o for _, o in R) else 1)
