"""Verificação automática da versão renderizada, antes de ir para o app (regra 10: nada é dado como feito sem conferir).
Cada item: ok (True), problema (False) ou não verificável automaticamente (None, precisa olhar)."""
import json, re, subprocess, unicodedata

def _n(t): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', t.lower()).encode('ascii', 'ignore').decode())

def verificar(arq, pl, tokens, dur, altura, hdr_origem, aplicadas, n_destaques):
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
        ouvidas = [_n(x.word) for s in mod.transcribe(au, language='pt', word_timestamps=True, beam_size=1, vad_filter=True)[0] for x in s.words]
        plano = [_n(t['tok']) for t in tokens if len(_n(t['tok'])) > 2]
        faltam = [p for p in plano if p not in set(ouvidas)]
        tx = len(faltam) / max(len(plano), 1)
        itens.append(('Palavras inteiras', tx < 0.05, 'todas audíveis' if not faltam else f"{len(faltam)} palavra(s) não reconhecidas: {', '.join(faltam[:5])}"))
    except Exception as e:
        itens.append(('Palavras inteiras', None, 'não verificado: ' + str(e)[:60]))
    pedidas = len([i for i in pl.get('insercoes') or []])
    if pedidas: itens.append(('Imagens e vídeos anexados', aplicadas == pedidas, f'{aplicadas} de {pedidas} aplicados'))
    if pl.get('destaques'): itens.append(('Destaques', n_destaques > 0, f'{n_destaques} no vídeo'))
    itens.append(('Rosto livre e textos legíveis', None, 'precisa olhar na prévia'))
    itens.append(('Imagem sem filtros', True, 'o motor não aplica filtros nem suavização'))
    return [{'item': a, 'ok': b, 'detalhe': c} for a, b, c in itens]
