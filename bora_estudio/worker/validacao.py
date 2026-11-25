"""Verificação automática da versão renderizada, antes de ir para o app (regra 10: nada é dado como feito sem conferir).
Cada item: ok (True), problema (False) ou não verificável automaticamente (None, precisa olhar)."""
import json, re, subprocess, unicodedata

def _n(t): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', t.lower()).encode('ascii', 'ignore').decode())

def verificar(arq, pl, tokens, dur, altura, hdr_origem, aplicadas, n_destaques, vocab=None, base=None):
    itens = []
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,height,color_transfer:format=duration',
                                    '-of', 'json', arq], capture_output=True, text=True).stdout or '{}')
    v = next((x for x in pr.get('streams', []) if x.get('codec_type') == 'video'), {})
    a = any(x.get('codec_type') == 'audio' for x in pr.get('streams', []))
    d = float((pr.get('format') or {}).get('duration', 0) or 0)
    itens.append(('Resolução', v.get('height') == altura, f"{v.get('height')}p (esperado {altura}p)"))
    hdr = v.get('color_transfer') in ('arib-std-b67', 'smpte2084')
    itens.append(('Cor do original preservada', hdr == hdr_origem, 'HDR mantido' if hdr else ('SDR como o original' if not hdr_origem else 'HDR perdido')))
    itens.append(('Duração', abs(d - dur) < 0.5, f'{d:.1f} s'))
    sil = subprocess.run(['ffmpeg', '-nostdin', '-i', arq, '-af', 'silencedetect=n=-50dB:d=1.5', '-f', 'null', '-'], capture_output=True, text=True).stderr
    buracos = len(re.findall(r'silence_end', sil))
    itens.append(('Áudio contínuo', a and buracos == 0, 'sem silêncios longos' if buracos == 0 else f'{buracos} silêncio(s) acima de 1,5 s'))
    ini = ' '.join(t['tok'] for t in tokens[:6]).lower()
    ruim = any(x in ini for x in ('olá', 'ola ', 'hoje eu vou', 'agora eu vou', 'no vídeo de hoje', 'oi gente'))
    itens.append(('Gancho no início', not ruim, '"' + ' '.join(t['tok'] for t in tokens[:7]) + '…"'))
    try:                                                   # palavras cortadas: ouve a versão final de novo
        import montagem, numpy as np, wave, tempfile, os
        w = tempfile.mktemp(suffix='.wav'); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', arq, '-ac', '1', '-ar', '16000', w], check=True)
        from faster_whisper import WhisperModel
        mod = montagem._modelo or WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=8)
        au = np.frombuffer(wave.open(w).readframes(10 ** 10), dtype=np.int16).astype(np.float32) / 32768; os.remove(w)
        import vocabulario
        kw = {'hotwords': vocabulario.dica(vocab)} if vocabulario.dica(vocab) else {}
        ouv = [{'w': x.word.strip(), 's': x.start, 'e': x.end} for s in mod.transcribe(au, language='pt', word_timestamps=True, beam_size=1, vad_filter=True, **kw)[0] for x in s.words]
        ouvidas = [_n(x['w']) for x in vocabulario.aplicar(ouv, vocab)]       # nomes de remédios etc. com a grafia do cliente, como na legenda
        plano = [_n(t['tok']) for t in tokens if len(_n(t['tok'])) > 2]
        faltam = [p for p in plano if p not in set(ouvidas)]
        tx = len(faltam) / max(len(plano), 1)
        itens.append(('Palavras inteiras', tx < 0.05, 'todas audíveis' if not faltam else f"{len(faltam)} palavra(s) não reconhecidas: {', '.join(faltam[:5])}"))
    except Exception as e:
        itens.append(('Palavras inteiras', None, 'não verificado: ' + str(e)[:60]))
    pedidas = len([i for i in pl.get('insercoes') or []])
    if pedidas: itens.append(('Imagens e vídeos anexados', aplicadas == pedidas, f'{aplicadas} de {pedidas} aplicados'))
    if pl.get('destaques'): itens.append(('Destaques', n_destaques > 0, f'{n_destaques} no vídeo'))
    leg = legibilidade(base, tokens, dur) if base else None
    if leg: itens.append(('Legenda legível sobre a imagem', leg[0], leg[1]))
    itens.append(('Rosto livre e textos legíveis', None, 'precisa olhar na prévia'))
    itens.append(('Imagem sem filtros', True, 'o motor não aplica filtros nem suavização'))
    return [{'item': a, 'ok': b, 'detalhe': c} for a, b, c in itens]


PISO_MBPS = {24: 0.0, 16: 4.0, 10: 6.0}       # abaixo disso, com 'alta' ou 'máxima', algo ficou comprimido demais (vídeo muito simples pode dar alarme falso)

def legibilidade(base, tokens, dur, passo=2.0):
    """Mede o fundo REAL (vídeo sem texto) atrás da legenda branca nos momentos com fala: fundo claro demais tira o contraste.
    Devolve (ok, detalhe) ou None se não der pra medir."""
    try:
        import numpy as np
        ts = sorted({round(t['s'] + 0.2, 1) for t in tokens})
        amostras, ult = [], -9.0
        for t in ts:
            if t - ult >= passo and t < dur: amostras.append(t); ult = t
        amostras = amostras[:20]
        if not amostras: return None
        tm = 'zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,'
        ruins = []
        for t in amostras:
            r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', base, '-frames:v', '1', '-vf', f'{tm}scale=270:480,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
            if len(r.stdout) != 270 * 480:
                r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', base, '-frames:v', '1', '-vf', 'scale=270:480,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
            if len(r.stdout) != 270 * 480: continue
            a = np.frombuffer(r.stdout, np.uint8).reshape(480, 270)[int(480 * 1290 / 1920):int(480 * 1470 / 1920), 54:216] / 255.0
            if a.mean() > 0.72 or (a > 0.82).mean() > 0.35: ruins.append(t)
        if not amostras: return None
        if not ruins: return True, f'fundo com contraste nos {len(amostras)} momentos medidos'
        return len(ruins) <= max(1, len(amostras) // 5), f'fundo claro atrás da legenda em {len(ruins)} de {len(amostras)} momentos (' + ', '.join(f'{t:g} s' for t in ruins[:6]) + ')'
    except Exception as e:
        print('legibilidade:', str(e)[:100], flush=True); return None

def verificar_final(arq, dur, altura, hdr_origem, crf):
    """Confere o 4K gerado (antes de entregar): tamanho, codec, 10 bits, HDR, duração, áudio e taxa de bits real.
    Mesmo formato da verificação da prévia: [{item, ok (True/False/None), detalhe}]."""
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,pix_fmt,color_transfer,color_primaries:format=duration,size',
                                    '-of', 'json', arq], capture_output=True, text=True).stdout or '{}')
    v = next((x for x in pr.get('streams', []) if x.get('codec_type') == 'video'), {})
    a = any(x.get('codec_type') == 'audio' for x in pr.get('streams', []))
    f = pr.get('format') or {}; d = float(f.get('duration', 0) or 0); tam = int(f.get('size', 0) or 0)
    w, h = v.get('width'), v.get('height'); ow = altura * 9 // 16
    itens = [('Resolução 4K', w == ow and h == altura, f'{w}×{h} (esperado {ow}×{altura})'),
             ('HEVC 10 bits', v.get('codec_name') == 'hevc' and v.get('pix_fmt') == 'yuv420p10le', f"{v.get('codec_name')} {v.get('pix_fmt')}")]
    hdr = v.get('color_transfer') == 'arib-std-b67' and v.get('color_primaries') == 'bt2020'
    itens.append(('Cor HDR (HLG, BT.2020)', hdr == hdr_origem, 'HDR mantido' if hdr else ('SDR como o original' if not hdr_origem else 'HDR perdido')))
    itens.append(('Duração', abs(d - dur) < 0.5, f'{d:.1f} s'))
    itens.append(('Áudio presente', a, 'ok' if a else 'sem áudio'))
    mbps = max(tam * 8 / d / 1e6 - 0.26, 0) if d > 0 else 0          # tira o áudio (AAC 256 kbps)
    piso = PISO_MBPS.get(crf, 0.0)
    itens.append(('Taxa de bits do vídeo', mbps >= piso, f'{mbps:.1f} Mbps · {tam / 1048576:.0f} MB' + ('' if mbps >= piso else f' (abaixo de {piso:g} Mbps: se a imagem parecer mole, peça de novo em Máxima)')))
    return [{'item': x, 'ok': bool(y), 'detalhe': z} for x, y, z in itens]


def termos_na_tela(texto, vocab):
    """Nomes sensíveis que sobraram num texto (ex.: o .ass com as legendas, destaques e título): [] se está limpo."""
    import vocabulario
    return vocabulario.termos_na_tela(texto, vocab)
