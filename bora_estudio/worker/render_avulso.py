#!/usr/bin/env python3
"""Render final 4K de uma versão aprovada direto na máquina local (ex.: Acer), sem app, sem banco e sem VPS.
Usa a pasta do projeto copiada do VPS (/opt/bora/trabalho/<projeto>): originais, transcrições, plano aprovado
(o plano_vN.json mais recente), anexos e os trechos 4K já prontos (_trechos_<altura>, reaproveitados).
Mesmo motor da produção (motor.renderizar): mesma timeline, cortes, legendas, cards, DNA e cores.

Uso: python3 render_avulso.py <pasta_do_projeto> --nome Fabiola_Pedron_IMG_2575 [--leg #FFFFFF] [--dest #C8B9A7] [--plano plano_v5.json]
Resultado: <pasta>/final/<nome>_final.zip (legendado, sem legenda e .srt)."""
import glob, json, os, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
os.environ.setdefault('BORA_INTERMEDIARIO', 'x265')    # x265 = mesmos trechos já prontos no VPS (reaproveitados)
import montagem, motor

def arg(nome, padrao=None):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else padrao

pasta = os.path.abspath(sys.argv[1])
planos = sorted(glob.glob(os.path.join(pasta, 'plano_v*.json')), key=lambda x: int(x.rsplit('_v', 1)[1].split('.')[0]))
plano = arg('--plano', os.path.basename(planos[-1]) if planos else None)
if not plano: sys.exit('não achei plano_vN.json na pasta')
pl = json.load(open(os.path.join(pasta, plano)))
originais = sorted(f for f in glob.glob(os.path.join(pasta, 'original_*.*')) if not f.endswith('.parcial'))
trans = [f'transcricao_{i:02d}.json' for i in range(1, len(originais) + 1)]
falta = [f for f in trans + [os.path.basename(a.get('caminho', '')) for a in pl.get('_anexos') or []] if not os.path.exists(os.path.join(pasta, f))]
if falta: sys.exit('faltam arquivos na pasta: ' + ', '.join(falta))
w, h = montagem.sondar(originais[0])[:2]; altura = min(max(w, h), 3840); altura -= altura % 2
cache = os.path.join(pasta, f'_trechos_{altura}')
prontos = len(glob.glob(os.path.join(cache, '*r.mp4'))) if os.path.isdir(cache) else 0
pac = {'projeto_id': os.path.basename(pasta), 'tipo': 'final', 'versao_id': 'avulso', 'n': int(plano.split('_v')[1].split('.')[0]),
       'cliente_id': 'avulso', 'altura': altura, 'nome': arg('--nome', 'Bora_final'),
       'cores': {'leg': arg('--leg', '#FFFFFF'), 'dest': arg('--dest', '#FFFFFF')},
       'arquivos': [os.path.basename(f) for f in originais], 'transcricoes': trans, 'plano': plano,
       'anexos': [os.path.basename(a['caminho']) for a in pl.get('_anexos') or []]}
print(f"plano {plano} | {len(originais)} originais | {altura}p | {len(pl['segmentos'])} trechos na timeline | {prontos} trechos 4K já prontos no cache", flush=True)
t0 = time.time(); marcas = []
def etapa(texto, pct=None, **_):
    if not marcas or marcas[-1][1] != texto:
        marcas.append((round(time.time() - t0), texto)); print(f"{time.strftime('%H:%M:%S')} {pct if pct is not None else '':>3}% {texto}", flush=True)
res = motor.renderizar(pac, etapa, pasta)
print(f"\nPRONTO em {round(time.time() - t0)} s: {os.path.join(pasta, res['arquivos'][0])}")
for i, (t, txt) in enumerate(marcas):
    fim = marcas[i + 1][0] if i + 1 < len(marcas) else round(time.time() - t0)
    print(f'  {fim - t:>5} s  {txt}')
