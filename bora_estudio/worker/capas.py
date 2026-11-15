"""Miniatura (capa) dos projetos pro app: um quadro real do vídeo, em JPG leve.
É só um ícone de navegação no app: o vídeo em si nunca é convertido (prévias e finais seguem em HDR)."""
import json, subprocess

def _info(arq):
    o = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                   'stream=color_transfer:format=duration', '-of', 'json', arq], capture_output=True, text=True).stdout or '{}')
    return ((o.get('streams') or [{}])[0].get('color_transfer') or ''), float((o.get('format') or {}).get('duration') or 0)

def gerar_capa(arq, saida, posicao=0.35, largura=540):
    """Tira um quadro a ~35% do vídeo (depois do gancho/título) e salva em JPG 9:16."""
    tr, dur = _info(arq)
    t = max(0.0, dur * posicao) if dur else 1.0
    vf = f'scale={largura}:-2:flags=lanczos'
    if tr in ('arib-std-b67', 'smpte2084'):        # HDR: mapeia pra tela comum só na miniatura
        vf = ('zscale=t=linear:npl=1000,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,'
              f'zscale=t=bt709:m=bt709:r=tv,format=yuv420p,{vf}')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', arq, '-frames:v', '1', '-vf', vf,
                    '-q:v', '4', saida], check=True)
    return saida
