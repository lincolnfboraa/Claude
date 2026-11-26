import os; os.environ.setdefault("BORA_APROVAR_ROTEIRO", "0")
"""Teste do storytelling: marcas de repetição, regras do prompt, gancho (título exato x ideia) e vocabulário do cliente."""
import os, subprocess, sys, tempfile, types
os.environ['BORA_TRABALHO'] = tempfile.mkdtemp()
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import motor, plano, vocabulario, montagem
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
pal = lambda t: [{'w': w, 's': i * .3, 'e': i * .3 + .25} for i, w in enumerate(t.split())]
# repetições
m = plano.marcar_repeticoes(pal('esse estudo chama Flow e ele falou que 24%, uma redução de 24 % no risco'))
ok('número dito duas vezes: marca o primeiro (o "24%,")', m == {8}, str(sorted(m)))
m = plano.marcar_repeticoes(pal('o que eu eu quero dizer é que o que eu quero dizer é simples'))
ok('gagueira e falso começo: marca a primeira tentativa', {2, 3, 4, 5} <= m and 12 not in m and 14 not in m, str(sorted(m)))
ok('fala normal sem repetição: nada marcado', not plano.marcar_repeticoes(pal('hoje vamos falar sobre a saúde dos seus rins e como cuidar deles')))
txt = plano.numerar([pal('que 24%, uma redução de 24 %')], ['a.mov'])
ok('a transcrição que a IA lê mostra ⟲ no primeiro 24%', '24%,⟲' in txt and '24 ' in txt and '24⟲' not in txt, txt.splitlines()[-1])
for trecho in ('Estrutura (sempre', 'ANTES da prova', 'SOMA ao resto', '⟲', 'releia o roteiro', 'NÃO são o texto do título', 'nunca diga que um deles não está disponível'):
    ok(f'prompt tem a regra: {trecho}', trecho in plano.SISTEMA or trecho.replace('NÃO são', 'NÃO é') in plano.SISTEMA)
# gancho
G = motor.gancho_texto
ok('o comentário "Gostei do gancho de..." vira IDEIA (não vai pra caixa)', G('Gostei do gancho de “o que essa armadura tem a ver com mounjaro e ozempic”')[0] == '')
ok('título curto de verdade vai exato', G('Precisa fazer força pra fazer xixi?') == ('Precisa fazer força pra fazer xixi?', ''))
ok('título inteiro entre aspas: tira as aspas', G('“Você sabia?”') == ('Você sabia?', ''))
ok('"tipo...", "exemplo..." e textos longos são ideia', G('tipo: 3 sinais de que seu rim pede ajuda')[0] == '' and G('x ' * 60)[0] == '' and G('')[0] == '')
# vocabulário
voc = vocabulario.carregar('fabiola')
ok('vocabulário da Fabiola carregado', voc and 'Mounjaro' in voc['termos'] and voc['corrigir'].get('zempique') == 'Ozempic')
fix = lambda t: ' '.join(x['w'] for x in vocabulario.aplicar(pal(t), voc))
ok('corrige nomes de remédios e junta "sema glutida"', fix('da sema glutida e o monjaro, a tiresepatida') == 'da semaglutida e o Mounjaro, a tirzepatida', fix('da sema glutida e o monjaro, a tiresepatida'))
ok('não come o artigo ("é o zempique" vira "é o Ozempic")', fix('é o zempique') == 'é o Ozempic', fix('é o zempique'))
ok('cliente sem vocabulário: sem mudança', vocabulario.carregar('thehouse') is None and vocabulario.aplicar(pal('o monjaro'), None) == pal('o monjaro'))
ok('vocabulário do DNA também vale', 'Flow' in vocabulario.carregar('x', {'vocabulario': ['Flow']})['termos'])
# a dica chega no Whisper em toda janela (hotwords) e a correção entra no que é gravado
T = tempfile.mkdtemp(); vid = os.path.join(T, 'a.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=300:r=16000:d=2', '-c:a', 'aac', vid], check=True)
cap = {}
class Fake:
    def transcribe(self, a, **kw):
        cap.update(kw); W = lambda w, s, e: types.SimpleNamespace(word=' ' + w, start=s, end=e)
        return [types.SimpleNamespace(words=[W('o', 0.1, 0.2), W('monjaro', 0.3, 0.8), W('sema', 1.0, 1.2), W('glutida', 1.2, 1.7)])], None
montagem._modelo = Fake()
r = montagem.transcrever(vid, os.path.join(T, 't.json'), voc)
ok('Whisper recebe os termos como hotwords', 'Mounjaro' in (cap.get('hotwords') or ''), (cap.get('hotwords') or '')[:40])
ok('a transcrição gravada já sai corrigida', [x['w'] for x in r] == ['o', 'Mounjaro', 'semaglutida'], str([x['w'] for x in r]))
montagem._modelo = None
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
