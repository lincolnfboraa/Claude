#!/usr/bin/env python3
"""Transição 'vazamento de luz + flash branco' sobre um corte, aplicada no vídeo LIMPO
e com as legendas queimadas por cima depois (como trilha de texto acima do efeito).
Uso: python3 transicao.py <video_limpo.mp4> <legendas.ass|-> <tempo_do_corte> <saida.mp4> [pb] [antes] [depois]
  pb: 1 = o take seguinte entra em preto e branco e volta à cor em ~1,2 s (como na referência)
  antes/depois: segundos de vídeo mantidos antes e depois do corte (teste curto). Use 'tudo' em antes para o vídeo inteiro."""
import sys, subprocess, os

here = os.path.dirname(os.path.abspath(__file__))
src, ass, tc, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
pb = len(sys.argv) > 5 and sys.argv[5] == '1'
antes = sys.argv[6] if len(sys.argv) > 6 else '3.0'
depois = float(sys.argv[7]) if len(sys.argv) > 7 else 3.5
if antes == 'tudo':
    ini, dur = 0.0, None
else:
    ini = max(0.0, tc - float(antes)); dur = (tc - ini) + depois
c = tc - ini                    # instante do corte dentro do trecho

# envelope do vazamento de luz: entra 0,40 s antes do corte, some 0,15 s depois
la, lb = c - 0.40, c + 0.15
W = f"if(between(T,{la:.3f},{lb:.3f}),0.85*sin(PI*(T-{la:.3f})/{lb-la:.3f}),0)"
# flash branco: sobe rápido até o corte (+0,03 s) e desce mais devagar
pk = c + 0.03
F = (f"if(between(T,{pk-0.18:.3f},{pk+0.34:.3f}),"
     f"pow(max(0,1-abs(T-{pk:.3f})/if(lt(T,{pk:.3f}),0.18,0.34)),1.4),0)")
L = f"clip(A+({W})*((255-(255-A)*(255-B)/255)-A),0,255)"   # tela (screen) da luz, dosada por W
expr = f"clip({L}+({F})*(255-{L}),0,255)"                      # sem st()/ld(): o blend roda em várias threads

fc = []
fc.append("[0:v]format=gbrp,setpts=PTS-STARTPTS[base]")
# luz: gradiente animado (vermelho/laranja/verde/ciano), em baixa resolução, desfocado e ampliado
fc.append("gradients=s=270x480:r=30000/1001:c0=0x000000:c1=0xff2a10:c2=0x000000:c3=0x18d070:c4=0x000000:c5=0xffa020:c6=0x000000:c7=0x30c8ff:"
          "nb_colors=8:type=linear:speed=0.09:x0=0:y0=0:x1=270:y1=480,"
          "gblur=sigma=18,scale=1080:1920:flags=bicubic,format=gbrp[luz]")
fc.append(f"[base][luz]blend=all_expr='{expr}':shortest=1[fx]")
pos = "[fx]format=yuv420p"
if pb:   # take novo em P&B, recuperando a cor em 1,2 s
    pos += f",hue=s='if(lt(t,{c:.3f}),1,min(1,pow((t-{c:.3f})/1.2,2)))'"
if ass not in ('-', ''):
    # legenda acima do efeito: reposiciona o tempo para o relógio do vídeo completo
    pos += f",setpts=PTS+{ini:.3f}/TB,subtitles={ass}:fontsdir={os.path.join(here, 'fonts')},setpts=PTS-STARTPTS"
fc.append(pos + "[vo]")

args = ['ffmpeg', '-v', 'error', '-y', '-ss', f'{ini:.3f}'] + (['-t', f'{dur:.3f}'] if dur else []) + ['-i', src,
        '-filter_complex', ';'.join(fc), '-map', '[vo]', '-map', '0:a',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-r', '30000/1001',
        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out]
subprocess.run(args, check=True)
print('ok', out)
