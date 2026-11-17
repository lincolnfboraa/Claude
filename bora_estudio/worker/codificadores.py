"""Codificadores de vídeo disponíveis na máquina e a escolha segura para os arquivos INTERMEDIÁRIOS.

- x265 (CPU) é sempre o padrão e a referência de qualidade. A entrega final (prévia e 4K) continua em x265.
- NVENC (placa NVIDIA) só é usado se passar no teste: codifica um trecho HDR HLG de 10 bits e confere
  perfil Main 10, 10 bits, BT.2020 e HLG no arquivo gerado. Se qualquer item falhar, fica no x265.
- BORA_ACELERACAO=auto (padrão no render externo) | x265 (desliga) | nvenc (exige, falha se não validar)."""
import json, os, subprocess, tempfile

_cache = {}

def disponiveis():
    """Codificadores HEVC que o ffmpeg desta máquina conhece (não quer dizer que o hardware existe)."""
    if 'lista' not in _cache:
        out = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
        _cache['lista'] = [n for n in ('libx265', 'hevc_nvenc', 'hevc_qsv', 'hevc_amf', 'hevc_vaapi') if f' {n} ' in out]
    return _cache['lista']

def args_nvenc(cq=16):
    """HEVC 10 bits na placa NVIDIA, qualidade constante alta (intermediário quase sem perda)."""
    return ['-c:v', 'hevc_nvenc', '-preset', 'p6', '-tune', 'hq', '-rc', 'vbr', '-cq', str(cq), '-b:v', '0',
            '-profile:v', 'main10', '-pix_fmt', 'p010le']

def validar_nvenc():
    """Teste real: 1 s em HDR HLG 10 bits pelo NVENC. Devolve (ok, motivo)."""
    if 'nvenc' in _cache: return _cache['nvenc']
    if 'hevc_nvenc' not in disponiveis():
        _cache['nvenc'] = (False, 'o ffmpeg desta máquina não tem hevc_nvenc'); return _cache['nvenc']
    d = tempfile.mkdtemp(prefix='nvenc_'); saida = os.path.join(d, 't.mp4')
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30000/1001:d=1',
                        '-vf', 'format=yuv420p10le', *args_nvenc(), '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67',
                        '-colorspace', 'bt2020nc', saida], capture_output=True, text=True)
    if r.returncode:
        _cache['nvenc'] = (False, 'NVENC não abriu: ' + ((r.stderr or '').strip().splitlines() or ['sem placa NVIDIA'])[-1][:120])
        return _cache['nvenc']
    st = (json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                     'stream=codec_name,profile,pix_fmt,color_transfer,color_primaries', '-of', 'json', saida],
                                    capture_output=True, text=True).stdout or '{}').get('streams') or [{}])[0]
    falta = [k for k, ok in (('HEVC', st.get('codec_name') == 'hevc'), ('Main 10', st.get('profile') == 'Main 10'),
                             ('10 bits', '10' in (st.get('pix_fmt') or '')), ('HLG', st.get('color_transfer') == 'arib-std-b67'),
                             ('BT.2020', st.get('color_primaries') == 'bt2020')) if not ok]
    _cache['nvenc'] = (not falta, 'validado (HEVC Main 10, HLG, BT.2020)' if not falta else 'não preserva: ' + ', '.join(falta))
    return _cache['nvenc']

def escolher():
    """Codificador dos intermediários desta máquina: 'nvenc' ou 'x265'."""
    modo = os.environ.get('BORA_ACELERACAO', 'x265').lower()
    if modo == 'x265': return 'x265'
    ok, motivo = validar_nvenc()
    if modo == 'nvenc' and not ok: raise RuntimeError('BORA_ACELERACAO=nvenc, mas ' + motivo)
    return 'nvenc' if ok else 'x265'

def relatorio():
    ok, motivo = validar_nvenc()
    return {'disponiveis': disponiveis(), 'nvenc': motivo, 'intermediarios': escolher(), 'final': 'x265'}
