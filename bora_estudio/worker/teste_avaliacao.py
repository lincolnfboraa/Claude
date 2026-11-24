"""Nota da IA: monta o pedido (quadros + falas + pedido do editor), limita a nota entre 0 e 10 e não quebra sem resposta."""
import json, os, sys, types, shutil, subprocess, tempfile
import avaliacao, plano
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
T = tempfile.mkdtemp(); prev = os.path.join(T, 'p.mp4')
subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=270x480:d=9', '-pix_fmt', 'yuv420p', prev], check=True)
pal = [[{'w': w, 's': i, 'e': i + .5} for i, w in enumerate('botina da Pelicato custava R$219,90 hoje'.split())]]
pl = {'segmentos': [{'palavra_inicio': 0, 'palavra_fim': 5, 'quadro': 'medio'}], 'broll': [], 'destaques': [{'texto': 'metade do preço'}], 'usar_titulo': False}
visto = {}
class Resp:
    def __init__(s, txt): s.output_text, s.model = txt, 'gpt-teste'
class Cli:
    def __init__(s, **k): s.responses = s
    def create(s, **k): visto.update(k); return Resp(json.dumps({'nota': 12, 'motivo': 'm', 'criterios': {c: {'nota': -1, 'motivo': 'porque'} for c in avaliacao.CRITERIOS}, 'problemas': [{'segundo': 3, 'problema': 'x'}] * 10, 'resumo': 'ok'}))
sys.modules['openai'] = types.SimpleNamespace(OpenAI=Cli); plano.IA, plano.MODELO_GPT = 'gpt', 'gpt-teste'
n = avaliacao.avaliar(prev, pl, pal, 'inclua o IMG_1705', [{'item': 'Duração', 'detalhe': '9 s'}], T, 'cliente Agropec (loja agro)')
txt = visto['input'][0]['content'][0]['text']
ok('pedido leva falas, pedido do editor, destaques e verificação', 'botina da Pelicato' in txt and 'IMG_1705' in txt and 'metade do preço' in txt and 'Duração' in txt and 'Agropec' in txt and 'gancho' in txt)
ok('manda a folha de quadros como imagem', visto['input'][0]['content'][1]['type'] == 'input_image')
ok('nota e critérios ficam entre 0 e 10; no máximo 8 problemas', n['nota'] == 10 and all(v['nota'] == 0 and v['motivo'] for v in n['criterios'].values()) and set(n['criterios']) == set(avaliacao.CRITERIOS) and n['motivo'] and len(n['problemas']) == 8)
shutil.rmtree(T)
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
