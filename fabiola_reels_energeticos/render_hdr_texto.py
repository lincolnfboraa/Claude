#!/usr/bin/env python3
"""Aplica os textos (ASS) sobre o vídeo HDR original SEM alterar a imagem: o vídeo base é o HDR (HLG, BT.2020, 10 bits)
gerado por render_hdr.py; os textos são renderizados duas vezes (fundo preto e fundo branco) para obter a transparência real,
convertidos de SDR (BT.709) para HLG/BT.2020 no branco de referência (75% do sinal) e sobrepostos.
Uso: python3 render_hdr_texto.py <base_hdr.mp4> <legendas.ass> <saida.mp4> [crf=14]"""
import sys, os, subprocess, json
import numpy as np

base, ass, out = sys.argv[1], sys.argv[2], sys.argv[3]
crf = sys.argv[4] if len(sys.argv) > 4 else '14'
here = os.path.dirname(os.path.abspath(__file__))
pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                'stream=width,height,r_frame_rate,nb_frames:format=duration', '-of', 'json', base],
                               capture_output=True, text=True).stdout)
st = pr['streams'][0]; W, H = st['width'], st['height']; FR = st['r_frame_rate']
dur = float(pr['format']['duration'])
fontes = os.path.join(here, 'fonts')

def leitor(cor):
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c={cor}:s={W}x{H}:r={FR}:d={dur}',
                             '-vf', f'subtitles={ass}:fontsdir={fontes}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            stdout=subprocess.PIPE)
pb, pw = leitor('black'), leitor('white')
X265 = 'colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:range=limited:no-sao=1:no-strong-intra-smoothing=1'
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-i', base,
                        '-f', 'rawvideo', '-pix_fmt', 'rgba64le', '-s', f'{W}x{H}', '-r', FR, '-i', '-',
                        '-filter_complex', '[1:v]scale=out_color_matrix=bt2020:out_range=tv,format=yuva444p10le[o];'
                                           '[0:v][o]overlay=format=yuv420p10:eof_action=pass[v]',
                        '-map', '[v]', '-map', '0:a', '-c:a', 'copy',
                        '-c:v', 'libx265', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p10le', '-tag:v', 'hvc1',
                        '-x265-params', X265, '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc',
                        '-movflags', '+faststart', out], stdin=subprocess.PIPE)

# SDR (BT.709) -> HLG (BT.2020), branco SDR no branco de referência HLG (sinal 0,75 = luz de cena 0,2647)
M = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]], np.float32)
A_, B_, C_ = 0.17883277, 0.28466892, 0.55991073
def hlg(E):
    E = np.clip(E, 0, 1)
    return np.where(E <= 1/12, np.sqrt(3*E), A_*np.log(np.maximum(12*E - B_, 1e-6)) + C_)
LUT = None
n = W * H * 3
vazio = np.zeros((H, W, 4), np.uint16).tobytes()
while True:
    b = pb.stdout.read(n); w = pw.stdout.read(n)
    if len(b) < n or len(w) < n: break
    B = np.frombuffer(b, np.uint8).reshape(H, W, 3); Wt = np.frombuffer(w, np.uint8).reshape(H, W, 3)
    if not B.any():                      # quadro sem texto: overlay totalmente transparente
        enc.stdin.write(vazio); continue
    Bf = B.astype(np.float32) / 255; Wf = Wt.astype(np.float32) / 255
    a = np.clip(1 - (Wf - Bf).mean(2), 0, 1)
    cor = np.clip(Bf / np.maximum(a, 1e-4)[..., None], 0, 1)
    lin = cor ** 2.4                                   # BT.1886
    l2020 = lin @ M.T
    sig = hlg(l2020 * 0.2647)
    o = np.empty((H, W, 4), np.uint16)
    o[..., :3] = (sig * 65535).astype(np.uint16); o[..., 3] = (a * 65535).astype(np.uint16)
    enc.stdin.write(o.tobytes())
enc.stdin.close(); enc.wait(); pb.wait(); pw.wait()
print('ok', out)
