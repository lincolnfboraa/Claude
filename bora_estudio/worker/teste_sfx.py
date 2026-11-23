"""Teste dos efeitos sonoros automáticos (tudo sintético, sem Drive e sem IA):
 1. processar(): pico no alvo, duração limitada, ponto de impacto
 2. eventos_sfx(): whoosh só em troca de história, espaçamento, pop nos destaques
 3. misturar_sfx(): a voz fora dos efeitos fica igual, os efeitos aparecem nos tempos certos, sem clipar, mesma duração
 4. render_base() completo com efeitos num vídeo sintético"""
import os, subprocess, sys, tempfile
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
os.environ.setdefault('BORA_TRABALHO', tempfile.mkdtemp())
import biblioteca, montagem
T = tempfile.mkdtemp(); R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)
def pcm(arq, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-af', 'pan=mono|c0=c0', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout   # 1º canal (sem somar)
    return np.frombuffer(raw, np.float32)
rms = lambda x: float(np.sqrt((x ** 2).mean()) + 1e-12)
db = lambda x: 20 * np.log10(x + 1e-12)

# 1) processar
ff('-f', 'lavfi', '-i', 'anoisesrc=d=3:c=pink:a=0.8,afade=t=in:d=0.4,afade=t=out:st=1.0:d=1.0', os.path.join(T, 'w_cru.mp3'))
ff('-f', 'lavfi', '-i', 'sine=f=900:d=0.3', '-af', 'adelay=200:all=1,afade=t=out:st=0.4:d=0.1', os.path.join(T, 'p_cru.wav'))
pw = biblioteca.processar(os.path.join(T, 'w_cru.mp3'), os.path.join(T, 'w.wav'), 'whoosh')
pp = biblioteca.processar(os.path.join(T, 'p_cru.wav'), os.path.join(T, 'p.wav'), 'pop')
w, p = pcm(os.path.join(T, 'w.wav')), pcm(os.path.join(T, 'p.wav'))
ok('whoosh: pico em -18 dBFS (±0,6)', abs(db(np.abs(w).max()) + 18) < 0.6, f'{db(np.abs(w).max()):.2f} dB')
ok('pop: pico em -15 dBFS (±0,6)', abs(db(np.abs(p).max()) + 15) < 0.6, f'{db(np.abs(p).max()):.2f} dB')
ok('whoosh limitado a 1,3 s e pop a 0,6 s', len(w) / 48000 <= 1.31 and len(p) / 48000 <= 0.61, f'{len(w) / 48000:.2f} s / {len(p) / 48000:.2f} s')
ok('silêncio do começo do pop foi aparado (impacto perto do início)', pp < 0.2, f'impacto em {pp} s')
ok('ponto de impacto do whoosh dentro do arquivo', 0 <= pw <= 1.3, f'{pw} s')

# 2) eventos
F = montagem.FPS; pcs = [(0, 0, 150, 'medio'), (0, 160, 300, 'medio'),            # corte de pausa: sem whoosh
                         (0, 300, 450, 'fechado'),                                 # outro enquadramento: whoosh
                         (1, 0, 200, 'fechado'),                                   # outro take: whoosh
                         (1, 210, 400, 'fechado'), (1, 1000, 1200, 'fechado')]     # salto de 20 s no bruto: whoosh
ev = montagem.eventos_sfx(pcs, [1.0, 1.3, 9.0, 25.0], 33.0)
whoosh = [t for t, k in ev if k == 'whoosh']; pops = [t for t, k in ev if k == 'pop']
ok('whoosh só nas trocas de história (3), não no corte de pausa', len(whoosh) == 3, str(whoosh))
ok('whooshes espaçados por pelo menos 2,5 s', all(b - a >= 2.5 for a, b in zip(whoosh, whoosh[1:])))
ok('pops: 0,8 s entre eles e fora dos whooshes', all(b - a >= 0.8 for a, b in zip(pops, pops[1:])) and all(abs(p_ - w_) > 0.35 for p_ in pops for w_ in whoosh), str(pops))
ok('nada nos primeiros 0,3 s nem nos últimos 0,3 s', all(0.3 <= t <= 32.7 for t, _ in ev))

# 3) mistura
ff('-f', 'lavfi', '-i', 'sine=f=220:r=48000:d=12', '-af', 'volume=0.25', '-ac', '1', os.path.join(T, 'voz.wav'))
sem, com = os.path.join(T, 'sem.wav'), os.path.join(T, 'com.wav')            # PCM sem perda: compara só o caminho do sinal, sem ruído de AAC
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(T, 'voz.wav'), '-af', 'volume=0.0dB,alimiter=limit=0.84:attack=5:release=50:level=disabled,aresample=48000', '-c:a', 'pcm_s24le', sem], check=True)
montagem.misturar_sfx(os.path.join(T, 'voz.wav'), 0.0, [(2.0, os.path.join(T, 'w.wav')), (7.0, os.path.join(T, 'p.wav'))], com, codec=('-c:a', 'pcm_s24le'))
a, b = pcm(sem), pcm(com)
ok('mesma duração com e sem efeitos', abs(len(a) - len(b)) < 48000 * 0.05, f'{len(a) / 48000:.2f} s / {len(b) / 48000:.2f} s')
n = min(len(a), len(b)); a, b = a[:n], b[:n]
longe = slice(int(9.5 * 48000), int(11.5 * 48000))                                    # sem efeito nenhum
ok('voz longe dos efeitos idêntica (diferença < 0,2 dB)', abs(db(rms(b[longe])) - db(rms(a[longe]))) < 0.2, f'{db(rms(b[longe])) - db(rms(a[longe])):.3f} dB')
ok('voz longe dos efeitos: sem erro de forma de onda (SNR > 40 dB)', db(rms(a[longe])) - db(rms(a[longe] - b[longe])) > 40, f'{db(rms(a[longe])) - db(rms(a[longe] - b[longe])):.0f} dB')
dif = np.abs(b - a)
ok('whoosh aparece em 2,0 s e o pop em 7,0 s', dif[int(2.0 * 48000):int(3.0 * 48000)].max() > 0.05 and dif[int(7.0 * 48000):int(7.4 * 48000)].max() > 0.05)
ok('sem clipar (pico < 0,95)', np.abs(b).max() < 0.95, f'{np.abs(b).max():.3f}')
canais = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels', '-of', 'csv=p=0', com], capture_output=True, text=True).stdout.strip()
ok('canais da voz preservados (mono)', canais == '1', canais)

# 4) render_base completo
ff('-f', 'lavfi', '-i', 'testsrc2=s=1080x1920:r=30000/1001:d=8', '-f', 'lavfi', '-i', 'sine=f=300:d=8', '-c:v', 'libx265', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p10le',
   '-x265-params', 'log-level=none', '-c:a', 'aac', '-shortest', os.path.join(T, 'orig.mp4'))
pcs2 = [(0, 0, 90, 'medio'), (0, 90, 180, 'fechado')]
sai = os.path.join(T, 'base.mp4')
montagem.render_base(pcs2, [os.path.join(T, 'orig.mp4')], sai, 854, 20, None, sfx=[(2.5, os.path.join(T, 'w.wav')), (0.5, os.path.join(T, 'p.wav'))])
d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', sai], capture_output=True, text=True).stdout)
ok('render_base com efeitos gera vídeo com áudio', os.path.exists(sai) and 5.5 < d < 6.5, f'{d:.2f} s')
# 5) biblioteca com Drive simulado (nomes reais da pasta SoundFX)
import shutil, drive
nomes = ['Beep 1.mp3', 'Pop 12.mp3', 'Pop 7.wav', 'Typing 2.mp3', 'ES_Swooshes, Whoosh, Designed, Generic, Air - Epidemic Sound.mp3',
         'ES_Swooshes, Whoosh, Classic, Airy - Epidemic Sound.mp3', 'ES_Designed, Boom, Low Hit - Epidemic Sound.mp3']
fonte = {n: os.path.join(T, 'w_cru.mp3') if n.endswith('mp3') else os.path.join(T, 'p_cru.wav') for n in nomes}
drive.achar_pasta = lambda nome, pai=None: 'id_' + nome
drive.listar_arquivos = lambda pasta: ([{'id': f'f{i}abcdefgh', 'nome': n, 'tamanho': 1000 + i, 'mime': 'audio/x'} for i, n in enumerate(nomes)] if pasta == 'id_SoundFX' else
    [{'id': 'x1', 'nome': 'ChamberiText-Bold.otf', 'tamanho': 9, 'mime': 'font/otf'}, {'id': 'x2', 'nome': 'Roboto-VariableFont_wdth,wght.ttf', 'tamanho': 9, 'mime': 'font/ttf'}, {'id': 'x3', 'nome': 'leia.txt', 'tamanho': 1, 'mime': 'text/plain'}])
def _baixar(fid, destino, prog=None): shutil.copy(fonte[nomes[int(fid[1:].split('a')[0])]], destino); return 1
drive.baixar = _baixar
biblioteca.CACHE = os.path.join(T, 'cache'); proj = os.path.join(T, 'proj'); os.makedirs(proj)
r = biblioteca.preparar_sfx(proj)
ok('escolheu o whoosh "Classic, Airy" e o pop "Pop 7"', 'Classic, Airy' in r['whoosh']['origem'] and r['pop']['origem'] == 'Pop 7.wav', f"{r['whoosh']['origem'][:30]} / {r['pop']['origem']}")
ok('gravou sfx_whoosh.wav e sfx_pop.wav na pasta do projeto', all(os.path.exists(os.path.join(proj, e['arquivo'])) for e in r.values()))
biblioteca.PADRAO['pop'] = 'não existe'; r2 = biblioteca.preparar_sfx(proj)
ok('padrão ausente: cai no pop mais curto da pasta', r2['pop']['origem'].startswith('Pop'), r2['pop']['origem'])
f = biblioteca.listar_fontes()
ok('fontes: só .ttf/.otf, família pelo nome e variável marcada', [x['familia'] for x in f] == ['ChamberiText', 'Roboto'] and f[1]['variavel'] and not f[0]['variavel'], str([x['familia'] for x in f]))
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
