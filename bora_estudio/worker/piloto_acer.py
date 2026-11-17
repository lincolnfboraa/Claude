#!/usr/bin/env python3
"""Piloto do render 4K no Acer: diagnóstico da máquina + render de um trecho curto, 100% local.
Não fala com o VPS nem com o Supabase (o render externo continua desligado em produção).

O que faz:
1. Diagnóstico: processador, núcleos e memória que o Docker/WSL2 entrega, disco livre, ffmpeg e teste do NVENC.
2. Trecho curto (~6 s): usa o primeiro vídeo em /piloto (um .MOV 4K HDR do iPhone, se você colocar um lá) ou gera um
   clipe sintético 4K HLG. Monta uma timeline com o MESMO motor da produção (cortes, título, destaque, legenda e um card).
3. Renderiza o final em x265 (referência de produção) e, se a placa passar no teste, de novo com NVENC nos intermediários.
4. Mede tempo, pico de memória, confere HDR (HLG, BT.2020, 10 bits) e compara NVENC x x265 (SSIM).
Resultado em /trabalho/piloto/relatorio.json.  Uso: python3 piloto_acer.py [--segundos 6]"""
import glob, json, os, re, shutil, subprocess, sys, threading, time

AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
os.environ.setdefault('BORA_WHISPER', 'small')        # só pra achar o tempo das palavras do trecho de teste
import codificadores, montagem, motor

TRAB = os.environ.get('BORA_TRABALHO', '/trabalho'); BASE = os.path.join(TRAB, 'piloto')
SEG = float(sys.argv[sys.argv.index('--segundos') + 1]) if '--segundos' in sys.argv else 6.0
REL = {}
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)

def diagnostico():
    cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), '?')
    mem = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo') if l.split(':')[0] in ('MemTotal', 'MemAvailable', 'SwapTotal')}
    lim = next((open(f).read().strip() for f in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes') if os.path.exists(f)), 'max')
    lim_mb = None if lim in ('max', '') or int(lim) > 1 << 50 else int(lim) // 1048576
    livre = shutil.disk_usage(TRAB).free // 1073741824
    ff = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True).stdout.split('\n')[0]
    d = {'processador': cpu, 'nucleos_no_docker': os.cpu_count(), 'memoria_no_docker_mb': mem.get('MemTotal'),
         'memoria_livre_mb': mem.get('MemAvailable'), 'swap_mb': mem.get('SwapTotal'), 'limite_container_mb': lim_mb,
         'disco_livre_gb': livre, 'ffmpeg': ff, 'codificadores': codificadores.relatorio()}
    avisos = []
    if (lim_mb or mem.get('MemTotal', 0)) < 8000: avisos.append('menos de 8 GB pro Docker: aumente a memória do WSL2 (.wslconfig)')
    if os.cpu_count() < 6: avisos.append('poucos núcleos no Docker: confira processors no .wslconfig')
    if livre < 40: avisos.append('menos de 40 GB livres: os originais 4K e os trechos ocupam bastante')
    d['avisos'] = avisos
    return d

def preparar_trecho(pasta):
    """Coloca o vídeo, a transcrição, o plano e um card na pasta do projeto de teste."""
    os.makedirs(pasta, exist_ok=True)
    reais = sorted(glob.glob('/piloto/*.[mM][oO][vV]') + glob.glob('/piloto/*.[mM][pP]4'))
    orig = os.path.join(pasta, 'original_01.mov')
    if reais:
        log('vídeo real:', os.path.basename(reais[0]))
        if not os.path.exists(orig): shutil.copy(reais[0], orig)
        pal = montagem.transcrever(orig, os.path.join(pasta, 'transcricao_01.json')); montagem.liberar_modelo()
        REL['video'] = {'tipo': 'real', 'arquivo': os.path.basename(reais[0])}
    else:
        log('sem vídeo em /piloto: gerando um clipe sintético 4K HDR HLG de 10 bits')
        if not os.path.exists(orig):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=s=2160x3840:r=30000/1001:d={SEG + 2}',
                            '-f', 'lavfi', '-i', f'sine=f=220:d={SEG + 2}:sample_rate=48000', '-c:v', 'libx265', '-preset', 'ultrafast',
                            '-x265-params', 'log-level=0:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc', '-pix_fmt', 'yuv420p10le',
                            '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc', '-c:a', 'aac', orig], check=True)
        texto = 'teste do render quatro k no computador da bora com legenda destaque e cor original preservada sem filtro'.split()
        pal = [{'w': w, 's': round(0.3 + i * (SEG - 0.6) / len(texto), 2), 'e': round(0.3 + (i + 0.85) * (SEG - 0.6) / len(texto), 2)} for i, w in enumerate(texto)]
        json.dump(pal, open(os.path.join(pasta, 'transcricao_01.json'), 'w'))
        REL['video'] = {'tipo': 'sintético', 'arquivo': 'testsrc2 2160x3840 HLG'}
    k = max([i for i, w in enumerate(pal) if w['e'] <= SEG] or [len(pal) - 1])
    meio = max(1, k // 2)
    card = sorted(glob.glob(os.path.join(AQUI, '..', 'assets', 'fabiola', 'card*_9x16.png')))
    anexos = []
    if card:
        shutil.copy(card[0], os.path.join(pasta, 'anexo_01.png'))
        anexos = [{'nome': os.path.basename(card[0]), 'caminho': os.path.join(pasta, 'anexo_01.png'), 'tipo': 'imagem', 'versao': 1}]
    pl = {'segmentos': [{'palavra_inicio': 0, 'palavra_fim': k, 'quadro': 'medio', 'motivo': 'piloto'}],
          'usar_titulo': True, 'titulo': {'rotulo': 'PILOTO BORA STUDIO', 'tema': 'Render 4K', 'pergunta': 'Funciona no Acer?'},
          'destaques': [{'estilo': 'serifa', 'palavra_inicio': meio, 'palavra_fim': meio, 'linhas': [{'texto': pal[meio]['w'], 'papel': 'grande'}]}],
          'insercoes': [{'anexo': 1, 'palavra_inicio': 1, 'palavra_fim': max(2, meio - 1), 'modo': 'flutuando'}] if anexos else [],
          'correcoes': [], '_anexos': anexos}
    json.dump(pl, open(os.path.join(pasta, 'plano_v1.json'), 'w'), ensure_ascii=False)
    w, h = montagem.sondar(orig)[:2]; altura = min(max(w, h), 3840); altura -= altura % 2
    REL['video'].update({'original': info(orig), 'trecho_s': round(pal[k]['e'] - pal[0]['s'], 1)})
    return {'projeto_id': 'piloto', 'tipo': 'final', 'versao_id': 'piloto', 'n': 1, 'cliente_id': 'piloto', 'altura': altura, 'nome': 'Piloto_Acer',
            'cores': {'leg': '#FFFFFF', 'dest': '#C8B9A7'}, 'arquivos': ['original_01.mov'], 'transcricoes': ['transcricao_01.json'],
            'plano': 'plano_v1.json', 'anexos': ['anexo_01.png'] if anexos else []}

def info(arq):
    s = (json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,pix_fmt,color_transfer,color_primaries,profile,r_frame_rate:stream_side_data', '-of', 'json', arq],
        capture_output=True, text=True).stdout).get('streams') or [{}])[0]
    return {k: s.get(k) for k in ('width', 'height', 'profile', 'pix_fmt', 'color_transfer', 'color_primaries', 'r_frame_rate')}

def pico_memoria(parar, saida):
    """Soma a memória de todos os processos do container a cada 0,3 s (o pico real do render)."""
    pico = 0
    while not parar.is_set():
        tot = 0
        for p in os.listdir('/proc'):
            if p.isdigit():
                try: tot += int(open(f'/proc/{p}/statm').read().split()[1]) * 4096
                except Exception: pass
        pico = max(pico, tot); parar.wait(0.3)
    saida.append(pico // 1048576)

def render(modo, pac, origem):
    pasta = os.path.join(BASE, modo)
    shutil.rmtree(pasta, ignore_errors=True); shutil.copytree(origem, pasta)
    os.environ['BORA_INTERMEDIARIO'] = 'nvenc' if modo == 'nvenc' else 'x265'
    parar, mem = threading.Event(), []; th = threading.Thread(target=pico_memoria, args=(parar, mem)); th.start()
    t0 = time.time()
    try:
        res = motor.renderizar(pac, lambda t, n=None, **k: log(f'[{modo}] {n if n is not None else "":>3}% {t}'), pasta)
        erro = None
    except Exception as e:
        res, erro = None, str(e)
    parar.set(); th.join()
    r = {'segundos': round(time.time() - t0), 'pico_memoria_mb': mem[0], 'erro': erro}
    if res:
        leg = next(glob.glob(os.path.join(pasta, 'final', '*_legendado.mp4')).__iter__())
        r.update({'legendado': leg, 'saida': info(leg), 'zip_mb': round(os.path.getsize(os.path.join(pasta, res['arquivos'][0])) / 1048576)})
        s = r['saida']
        r['hdr_ok'] = s.get('color_transfer') == 'arib-std-b67' and s.get('color_primaries') == 'bt2020' and '10' in (s.get('pix_fmt') or '') and s.get('profile') == 'Main 10'
        r['30fps_ok'] = s.get('r_frame_rate') in ('30000/1001', '30/1')
    return r

if __name__ == '__main__':
    log('Piloto do render 4K no Acer (local, sem VPS)')
    REL['diagnostico'] = diagnostico(); print(json.dumps(REL['diagnostico'], ensure_ascii=False, indent=1), flush=True)
    origem = os.path.join(BASE, 'projeto'); pac = preparar_trecho(origem)
    REL['x265'] = render('x265', pac, origem)
    if REL['diagnostico']['codificadores']['intermediarios'] == 'nvenc':
        REL['nvenc'] = render('nvenc', pac, origem)
        if REL['nvenc'].get('legendado') and REL['x265'].get('legendado'):
            o = subprocess.run(['ffmpeg', '-v', 'info', '-i', REL['nvenc']['legendado'], '-i', REL['x265']['legendado'], '-lavfi', 'ssim', '-f', 'null', '-'],
                               capture_output=True, text=True).stderr
            REL['nvenc']['ssim_vs_x265'] = float((re.findall(r'All:([\d.]+)', o) or ['0'])[-1])
    else:
        REL['nvenc'] = {'pulado': REL['diagnostico']['codificadores']['nvenc']}
    json.dump(REL, open(os.path.join(BASE, 'relatorio.json'), 'w'), ensure_ascii=False, indent=1)
    print('\n===== RESULTADO =====')
    for m in ('x265', 'nvenc'):
        r = REL[m]
        if 'pulado' in r: print(f'{m}: não testado ({r["pulado"]})'); continue
        print(f"{m}: {'OK' if not r['erro'] else 'ERRO ' + r['erro']} | {r['segundos']} s | pico {r['pico_memoria_mb']} MB"
              + (f" | HDR {'ok' if r['hdr_ok'] else 'FALHOU'} | 30 fps {'ok' if r['30fps_ok'] else 'FALHOU'} | {r['saida']['width']}x{r['saida']['height']}" if r.get('saida') else '')
              + (f" | SSIM vs x265 {r['ssim_vs_x265']:.4f}" if 'ssim_vs_x265' in r else ''))
    print(f"trecho: {REL['video']['trecho_s']} s ({REL['video']['tipo']}). Relatório: {os.path.join(BASE, 'relatorio.json')}")
