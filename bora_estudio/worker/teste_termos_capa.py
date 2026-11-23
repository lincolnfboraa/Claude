"""Teste dos termos sensíveis (troca na tela) e da capa final (CRM e RQE): troca com artigo certo, índices das legendas, cor HDR da capa,
duração do vídeo e do áudio, e um _renderizar completo sem nome de produto na tela."""
import json, os, subprocess, sys, tempfile
import numpy as np
T = tempfile.mkdtemp(); os.environ['BORA_TRABALHO'] = T
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import vocabulario as V, montagem, motor, textos
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
voc = V.carregar('fabiola'); M = lambda t: V.mascarar_texto(t, voc)
ok('"o Mounjaro e o Ozempic" vira "as canetas" (artigo plural)', M('tem a ver com o Mounjaro e o Ozempic?') == 'tem a ver com as canetas?', M('tem a ver com o Mounjaro e o Ozempic?'))
ok('um produto: "o Ozempic" vira "a caneta"; contração "do" vira "da"', M('Existe efeito com o Ozempic.') == 'Existe efeito com a caneta.' and M('o efeito do Ozempic') == 'o efeito da caneta', M('o efeito do Ozempic'))
ok('começo de frase: maiúscula mantida', M('O Mounjaro ajuda') == 'A caneta ajuda' and M('Ozempic ajuda') == 'Caneta ajuda')
ok('lista com vírgulas e "e": uma palavra só', M('Mounjaro, Ozempic e Wegovy protegem?') == 'Canetas protegem?')
ok('frases diferentes não se juntam', M('usa o Wegovy. E o Ozempic ajuda') == 'usa a caneta. E a caneta ajuda', M('usa o Wegovy. E o Ozempic ajuda'))
ok('texto sem produto fica igual; cliente sem lista não muda', M('o rim protege') == 'o rim protege' and V.mascarar_texto('o Ozempic', V.carregar('thehouse')) == 'o Ozempic')
tok = [{'tok': w, 's': i * .3, 'e': i * .3 + .25, 'i': i} for i, w in enumerate('ver com o Mounjaro e o Ozempic? Essas'.split())]
nt = V.mascarar_tokens(tok, voc); sw = nt[3]
ok('token trocado cobre o tempo e os índices das palavras antigas', sw['tok'] == 'canetas?' and sw['i'] == 3 and sw['i2'] == 6 and abs(sw['s'] - 0.9) < 1e-6 and abs(sw['e'] - 2.05) < 1e-6, str((sw['tok'], sw['i'], sw.get('i2'))))
ro = textos.Roteiro(nt, 4.0, '#FFFFFF', '#C8B9A7'); ro.destaque({'estilo': 'pop', 'palavra_inicio': 5, 'palavra_fim': 5, 'linhas': [{'texto': 'X', 'papel': 'grande'}]})
ok('destaque num índice que a troca engoliu ainda acha a legenda', len(ro.t_destaques) == 1)
ok('termos_na_tela acha o que sobrou e ignora o que foi trocado', V.termos_na_tela('texto com Ozempic e mounjaro', voc) == ['Mounjaro', 'Ozempic'] and V.termos_na_tela('as canetas', voc) == [])
# capa: cor HDR certa
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)
png = os.path.join(T, 'capa.png')
from PIL import Image, ImageDraw
im = Image.new('RGB', (1080, 1920), (10, 27, 77)); ImageDraw.Draw(im).ellipse((380, 700, 700, 1020), outline=(245, 235, 222), width=14); im.save(png)
p, tg = montagem.x265('arib-std-b67')
clip = os.path.join(T, 'capa.mp4'); montagem.capa_clip(png, clip, 216, 384, 1.0, True, 14, p, tg)
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height,pix_fmt,color_transfer,color_primaries,nb_frames:format=duration', '-of', 'json', clip], capture_output=True, text=True).stdout)
st = pr['streams'][0]
ok('capa: tamanho, 10 bits, HLG e BT.2020', (st['width'], st['height'], st['pix_fmt'], st['color_transfer'], st['color_primaries']) == (216, 384, 'yuv420p10le', 'arib-std-b67', 'bt2020'), str(st))
ok('capa: 1 s (30 quadros)', abs(float(pr['format']['duration']) - 1.0) < 0.1, pr['format']['duration'])
def luma(t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', clip, '-frames:v', '1', '-vf', 'format=gray10le', '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, '<u2').reshape(384, 216)
y_fim = luma(0.9)[20:60, 20:60].mean()
a = np.array([10, 27, 77], np.float32) / 255; sig = montagem._hlg((a ** 2.4) @ montagem._M_HLG.T * 0.62); esp = 64 + 876 * (0.2627 * sig[0] + 0.6780 * sig[1] + 0.0593 * sig[2])
esp_gray = (esp - 64) * 1023 / 876                       # o gray10le do ffmpeg reescala o Y limitado pra faixa total
ok('capa: a cor do fundo bate com a conversão SDR->HLG dos textos (±6 códigos)', abs(y_fim - esp_gray) < 6, f'lido {y_fim:.0f}, esperado {esp_gray:.0f}')
ok('capa: entra com fade (primeiro quadro bem mais escuro)', luma(0.0)[20:60, 20:60].mean() < y_fim - 30, f'{luma(0.0)[20:60, 20:60].mean():.0f} -> {y_fim:.0f}')
# render completo com termos sensíveis e capa
orig = os.path.join(T, 'orig.mp4')
ff('-f', 'lavfi', '-i', 'testsrc2=s=540x960:r=30000/1001:d=14', '-f', 'lavfi', '-i', 'sine=f=300:r=48000:d=14', '-af', 'volume=0.3', '-c:v', 'libx265', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p10le',
   '-x265-params', 'log-level=none:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc', '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc', '-c:a', 'aac', '-shortest', orig)
palavras = 'Isso tem a ver com o Mounjaro e o Ozempic nos rins hoje e também com a Wegovy sim certo bom ok fim'.split()
pal = [[{'w': w, 's': 0.3 + i * 0.45, 'e': 0.3 + i * 0.45 + 0.4} for i, w in enumerate(palavras)]]
pl = {'segmentos': [{'palavra_inicio': 0, 'palavra_fim': len(palavras) - 1, 'quadro': 'medio', 'motivo': ''}], 'usar_titulo': False, 'titulo': {}, 'broll': [], 'insercoes': [], 'correcoes': [],
      'destaques': [{'estilo': 'pop', 'palavra_inicio': 6, 'palavra_fim': 8, 'linhas': [{'texto': 'Mounjaro e Ozempic', 'papel': 'grande'}]}], '_anexos': [{'nome': 'capa.png', 'caminho': png, 'tipo': 'imagem', 'capa_final': True}]}
cores = {'leg': '#FFFFFF', 'dest': '#C8B9A7', 'caixa': '#1E2A47'}
sem = motor._renderizar('p', {**pl, '_anexos': []}, [orig], pal, 854, cores, os.path.join(T, 't_sem'), pasta=T, vocab=None)
import shutil; shutil.copy(sem[0], os.path.join(T, 'base_sem.mp4')); sem = (os.path.join(T, 'base_sem.mp4'),) + tuple(sem[1:])    # as duas montagens gravam o mesmo _base_854.mp4
com = motor._renderizar('p', pl, [orig], pal, 854, cores, os.path.join(T, 't_com'), pasta=T, vocab=voc)
dur = lambda f, tipo='v': float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', tipo + ':0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.split()[0])
ok('com capa: vídeo a capa (CAPA_FINAL_S) a mais e a duração devolvida inclui a capa', abs(dur(com[0]) - dur(sem[0]) - motor.CAPA_FINAL_S) < 0.15 and abs(com[2] - sem[2] - motor.CAPA_FINAL_S) < 1e-6, f'{dur(sem[0]):.2f} -> {dur(com[0]):.2f} s')
ok('com capa: o áudio também cresce (silêncio) e acompanha o vídeo', abs(dur(com[0], 'a') - dur(com[0])) < 0.2, f'áudio {dur(com[0], "a"):.2f} s, vídeo {dur(com[0]):.2f} s')
ass = open(os.path.join(T, 't_com.ass'), encoding='utf-8').read(); ass0 = open(os.path.join(T, 't_sem.ass'), encoding='utf-8').read()
ok('legendas e destaque sem nome de produto, com "caneta"', not V.termos_na_tela(ass, voc) and 'caneta' in ass and 'artigo' not in ass, str(V.termos_na_tela(ass, voc)))
ok('sem a lista de termos o nome continua na tela (prova que a troca é a lista)', len(V.termos_na_tela(ass0, voc)) >= 2)
ok('a verificação (palavras faladas) recebe o texto ORIGINAL, não o trocado', 'Mounjaro' in [t['tok'] for t in com[3]] and 'canetas' not in [t['tok'] for t in com[3]])
ult = subprocess.run(['ffmpeg', '-v', 'error', '-sseof', '-0.5', '-i', com[0], '-frames:v', '1', '-vf', 'format=gray10le', '-f', 'rawvideo', '-'], capture_output=True).stdout
yy = np.frombuffer(ult, '<u2')[:480 * 854].reshape(854, 480)[40:100, 40:100].mean()
ok('o fim do vídeo montado é a capa (fundo azul-marinho)', abs(yy - esp_gray) < 25, f'lido {yy:.0f}, esperado {esp_gray:.0f}')
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
