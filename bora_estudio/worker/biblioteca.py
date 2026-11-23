"""Biblioteca de assets do Bora Studio (Drive: Bora Claude / Biblioteca / SoundFX e Fontes).

Hoje: efeitos sonoros automáticos (whoosh nos cortes de história, pop nos destaques). As fontes ficam catalogadas
(listar_fontes) pra entrar nos estilos de texto por cliente.

Só o VPS fala com o Drive. Cada som é aparado, normalizado (pico fixo) e tem o ponto de impacto medido; o resultado vai pra pasta
do projeto (sfx_whoosh.wav, sfx_pop.wav) e segue no pacote do render, então o Acer não precisa do Drive.

Troca de som: BORA_SFX_WHOOSH e BORA_SFX_POP no bora.env (pedaço do nome do arquivo no Drive, ex. 'Pop 12').
"""
import json, os, re, subprocess
import numpy as np
import drive

PASTA = os.environ.get('BORA_BIBLIOTECA_NOME', 'Biblioteca')
CACHE = os.path.join(os.environ.get('BORA_TRABALHO', '/trabalho'), '_biblioteca')
SR = 48000
PADRAO = {'whoosh': os.environ.get('BORA_SFX_WHOOSH', 'Classic, Airy'), 'pop': os.environ.get('BORA_SFX_POP', 'Pop 7')}
PALAVRAS = {'whoosh': ('whoosh', 'swoosh'), 'pop': ('pop',)}                 # plano B: qualquer arquivo com essas palavras no nome
PICO_DB = {'whoosh': float(os.environ.get('BORA_SFX_WHOOSH_DB', '-18')), 'pop': float(os.environ.get('BORA_SFX_POP_DB', '-15'))}   # pico, em dBFS
MAX_S = {'whoosh': 1.3, 'pop': 0.6}                                            # duração máxima (o resto é cortado, com fade)
FADE_S = 0.12

def _pasta_biblioteca(sub):
    raiz = drive.achar_pasta(PASTA)
    if not raiz: raise RuntimeError(f"a pasta '{PASTA}' não existe dentro de Bora Claude no Drive")
    fid = drive.achar_pasta(sub, raiz)
    if not fid: raise RuntimeError(f"a pasta '{sub}' não existe dentro de '{PASTA}'")
    return fid

def listar(sub):
    """Arquivos de Biblioteca/<sub> no Drive."""
    return drive.listar_arquivos(_pasta_biblioteca(sub))

def escolher(tipo, itens):
    """Arquivo do tipo (whoosh ou pop): o que tem o padrão no nome; senão o primeiro com a palavra do tipo (preferindo os mais curtos)."""
    nome = lambda f: f['nome'].lower()
    dado = [f for f in itens if PADRAO[tipo].lower() in nome(f)]
    if dado: return dado[0]
    alt = sorted([f for f in itens if any(p in nome(f) for p in PALAVRAS[tipo])], key=lambda f: (f['tamanho'], f['nome']))
    if alt: return alt[0]
    raise RuntimeError(f"não achei um efeito de {tipo} na pasta SoundFX (padrão '{PADRAO[tipo]}')")

def _seguro(nome): return re.sub(r'[^A-Za-z0-9._-]+', '_', nome)

def _decodificar(arq):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x[: len(x) // 2 * 2].reshape(-1, 2).copy()

def processar(origem, destino, tipo):
    """Apara o silêncio do começo, limita a duração (fade no fim), leva o pico a PICO_DB e grava WAV 24 bits estéreo.
    Devolve o segundo (dentro do arquivo gravado) em que o som tem o impacto: é nele que o corte ou destaque acontece."""
    x = _decodificar(origem)
    if not len(x): raise RuntimeError('efeito sonoro vazio ou ilegível: ' + os.path.basename(origem))
    env = np.abs(x).max(axis=1)
    audivel = np.where(env > 10 ** (-55 / 20))[0]
    ini = max(0, int(audivel[0]) - int(0.01 * SR)) if len(audivel) else 0
    x = x[ini: ini + int(MAX_S[tipo] * SR)]
    pico = float(np.abs(x).max())
    if pico <= 1e-6: raise RuntimeError('efeito sonoro sem sinal: ' + os.path.basename(origem))
    x = x * (10 ** (PICO_DB[tipo] / 20) / pico)
    n = len(x); fo, fi = min(int(FADE_S * SR), n // 2), min(int(0.003 * SR), n // 2)
    if fo: x[n - fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))[:, None] ** 2
    if fi: x[:fi] *= np.linspace(0, 1, fi)[:, None]
    suave = np.convolve(np.abs(x).max(axis=1), np.ones(int(0.01 * SR)) / int(0.01 * SR), mode='same')
    pico_s = float(np.argmax(suave)) / SR
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s24le', destino],
                       input=x.astype(np.float32).tobytes(), capture_output=True)
    if r.returncode: raise RuntimeError('não consegui gravar o efeito sonoro: ' + r.stderr.decode()[-120:])
    return round(pico_s, 3)

def preparar_sfx(pasta_projeto):
    """Baixa (com cache) e prepara o whoosh e o pop; grava na pasta do projeto. Devolve {tipo: {arquivo, pico_s, origem}}."""
    itens = listar('SoundFX')
    saida = {}
    for tipo in ('whoosh', 'pop'):
        f = escolher(tipo, itens)
        pasta = os.path.join(CACHE, 'sfx'); os.makedirs(pasta, exist_ok=True)
        cru = os.path.join(pasta, f"{f['id'][:8]}_{_seguro(f['nome'])}")
        drive.baixar(f['id'], cru)
        dest = os.path.join(pasta_projeto, f'sfx_{tipo}.wav')
        saida[tipo] = {'arquivo': os.path.basename(dest), 'pico_s': processar(cru, dest, tipo), 'origem': f['nome']}
    return saida

def listar_fontes():
    """Fontes da biblioteca: [{familia, arquivo, id, tamanho}] (a família sai do nome do arquivo: 'ChamberiText-Bold.otf' -> ChamberiText)."""
    out = []
    for f in listar('Fontes'):
        if not f['nome'].lower().endswith(('.ttf', '.otf')): continue
        out.append({'familia': re.sub(r'(-[^-]*)?\.(ttf|otf)$', '', f['nome'], flags=re.I), 'arquivo': f['nome'], 'id': f['id'], 'tamanho': f['tamanho'],
                    'variavel': 'VariableFont' in f['nome']})
    return out
