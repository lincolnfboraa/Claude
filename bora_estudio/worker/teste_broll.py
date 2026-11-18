"""Teste do B-roll com vídeo real (iPhone 4K HDR HLG): classificação fala x ambiente, quadros pra IA, plano validado,
encaixe em HDR durante a locução (voz contínua) na prévia 480p e no final 4K. A IA é simulada (plano escrito à mão)."""
import glob, json, os, shutil, subprocess, sys
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
SP = '/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad'
P = SP + '/broll/proj'; shutil.rmtree(SP + '/broll', ignore_errors=True); os.makedirs(P)
os.environ['BORA_TRABALHO'] = SP + '/broll'
import montagem, motor, plano
RAW = SP + '/prost/raw/IMG_2589.MOV'
R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
def info(a):
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,pix_fmt,color_transfer,color_primaries',
                                   '-of', 'json', a], capture_output=True, text=True).stdout)['streams'][0]
    return f"{s['width']}x{s['height']} {s['pix_fmt']} {s['color_transfer']} {s['color_primaries']}"
def quadro(a, n, saida):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a, '-vf', f'select=eq(n\\,{n}),scale=270:480', '-frames:v', '1', saida], check=True)
    from PIL import Image; return Image.open(saida).convert('RGB')
def dif(a, b):
    import numpy as np; return float(np.abs(np.asarray(a, float) - np.asarray(b, float)).mean())
def md5a(a): return subprocess.run(['ffmpeg', '-v', 'error', '-i', a, '-map', '0:a', '-f', 'md5', '-'], capture_output=True, text=True).stdout.strip()

# originais: 1 take com fala (real) + 1 cena de ambiente (outro trecho do mesmo iPhone, sem som, HDR mantido)
os.symlink(RAW, P + '/original_01.mov')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '60', '-t', '8', '-i', RAW, '-an', '-vf', 'hflip', '-c:v', 'libx265', '-preset', 'ultrafast', '-crf', '16',
                '-x265-params', 'log-level=0:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc', '-pix_fmt', 'yuv420p10le',
                '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc', P + '/original_02.mov'], check=True)
shutil.copy(SP + '/tr_vps.json', P + '/transcricao_01.json')
arqs = [P + '/original_01.mov', P + '/original_02.mov']
pal = [montagem.transcrever(a, P + f'/transcricao_{i:02d}.json') for i, a in enumerate(arqs, 1)]

# 1) classificação
pap = [montagem.classificar(pal[i], arqs[i]) for i in range(2)]
ok('take com fala vira locução, vídeo sem som vira ambiente', pap == ['fala', 'ambiente'], str(pap))
ok('escolha do app manda (Fala/Ambiente)', montagem.classificar(pal[0], arqs[0], 'ambiente') == 'ambiente' and montagem.classificar([], arqs[1], 'fala') == 'fala')
ok('vídeo sem trilha de áudio não quebra a transcrição', pal[1] == [])

# 2) o que a IA recebe
jpg = montagem.quadro_jpg(arqs[1], P + '/broll_02.jpg')
ok('quadro do ambiente gerado pra IA', jpg and os.path.getsize(jpg) > 5000)
txt = plano.numerar(pal, arqs, pap)
ok('transcrição pra IA mostra o ambiente como B-roll, sem falas dele', '(vídeo de ambiente, B-roll' in txt and '[0]' in txt)
blocos = plano._conteudo('pedido', [{'n': 1, 'nome': 'sala.MOV', 'dur': 8.0, 'jpg': jpg}])
ok('pedido leva a imagem do B-roll', isinstance(blocos, list) and any(b['type'] == 'image' for b in blocos))
ok('esquema da IA tem o campo broll', 'broll' in plano.ESQUEMA['required'])

# 3) plano (IA simulada): 1 B-roll no 3º segmento, um inválido e um apontando pra vídeo inexistente
pl = json.load(open(SP + '/trab/teste/plano_v1.json')); pl['segmentos'] = pl['segmentos'][:3]; pl['insercoes'] = []
s3 = pl['segmentos'][2]
pl['broll'] = [{'video': 1, 'palavra_inicio': s3['palavra_inicio'], 'palavra_fim': s3['palavra_inicio'] + 6, 'inicio_s': 2.0, 'motivo': 'teste'},
               {'video': 7, 'palavra_inicio': 5, 'palavra_fim': 8, 'inicio_s': 0, 'motivo': 'inválido'}]
pl = plano.validar(pl, sum(len(p) for p in pal), {1}, 1, montagem.indice_global(pal))
ok('validação descarta B-roll inválido', len(pl['broll']) == 1)
pl['_broll_arquivos'] = [1]; pl['_anexos'] = []
json.dump(pl, open(P + '/plano_v1.json', 'w'), ensure_ascii=False)

# 4) prévia 480p com e sem B-roll
def render(com, altura, nome):
    p2 = dict(pl); p2['broll'] = pl['broll'] if com else []
    base, hdr, dur, tok = motor._renderizar('proj', p2, arqs, pal, altura, {'leg': '#FFFFFF', 'dest': '#C8B9A7'}, P + f'/t_{nome}', None, pasta=P)
    out = P + f'/{nome}.mp4'; montagem.aplicar_textos(base, P + f'/t_{nome}.ass', out, hdr, 24); return out, tok
sem, tok = render(False, 854, 'sem480'); com, _ = render(True, 854, 'com480')
t0 = next(t['s'] for t in tok if t['i'] >= pl['broll'][0]['palavra_inicio']); q = round(t0 * 30000 / 1001)
ok('B-roll aplicado', montagem.BROLL_APLICADOS == 1)
d_dentro = dif(quadro(sem, q + 15, P + '/a.png'), quadro(com, q + 15, P + '/b.png'))
d_fora = dif(quadro(sem, 10, P + '/c.png'), quadro(com, 10, P + '/d.png'))
ok('durante a fala marcada a imagem é a cena de ambiente', d_dentro > 15, f'diferença {d_dentro:.1f}')
ok('fora do B-roll a imagem é a mesma (gancho intacto)', d_fora < 2, f'diferença {d_fora:.1f}')
ok('voz contínua: áudio idêntico com e sem B-roll', md5a(sem) == md5a(com))
ok('HDR mantido na prévia', info(com) == info(sem) and 'arib-std-b67' in info(com), info(com))

# 5) final 4K com B-roll
com4, _ = render(True, 3840, 'com4k')
ok('4K com B-roll em HDR', 'arib-std-b67 bt2020' in info(com4) and info(com4).startswith('2160x3840'), info(com4))
print(f'\n{sum(R)} de {len(R)} verificações passaram')
