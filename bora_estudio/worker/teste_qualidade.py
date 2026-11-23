"""Teste da qualidade do 4K: mapa de CRF e a conferência automática do arquivo final (arquivos sintéticos pequenos, mesma regra do 4K)."""
import os, subprocess, sys, tempfile
os.environ['BORA_TRABALHO'] = tempfile.mkdtemp()
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import motor, validacao
T = tempfile.mkdtemp(); R = []
def ok(nome, cond, det=''): R.append(bool(cond)); print(('PASSOU ' if cond else 'FALHOU ') + nome + (f' ({det})' if det else ''), flush=True)
os.environ.pop('BORA_Q4K', None)
ok('qualidade: leve 24, alta 16, máxima 10; sem escolha ou inválida: alta', [motor.crf_4k({'qualidade_4k': q}) for q in ('leve', 'alta', 'maxima')] == [24, 16, 10] and motor.crf_4k({}) == 16 and motor.crf_4k({'qualidade_4k': 'x'}) == 16)
ok('intermediários sobem junto com o final', [motor.CRF_INTER[c] for c in (24, 16, 10)] == [14, 11, 8])
os.environ['BORA_Q4K'] = 'maxima'; ok('BORA_Q4K muda o padrão', motor.crf_4k({}) == 10); os.environ.pop('BORA_Q4K')
HLG = ['-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc']
def clip(nome, crf, hlg=True, w=1080, h=1920):
    p = os.path.join(T, nome)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=s={w}x{h}:r=30000/1001:d=3,noise=alls=10:allf=t', '-f', 'lavfi', '-i', 'sine=f=300:r=48000:d=3',
                    '-c:v', 'libx265', '-preset', 'ultrafast', '-crf', str(crf), '-pix_fmt', 'yuv420p10le', '-x265-params', 'log-level=none', *(HLG if hlg else []), '-tag:v', 'hvc1', '-c:a', 'aac', '-b:a', '256k', '-shortest', p], check=True)
    return p
bom = clip('bom.mp4', 16)
v = validacao.verificar_final(bom, 3.0, 1920, True, 16)
ok('final correto: tudo conferido', all(x['ok'] for x in v), '; '.join(f"{x['item']}: {x['detalhe']}" for x in v if not x['ok']))
ok('tamanho diferente do esperado: acusa', not next(x for x in validacao.verificar_final(bom, 3.0, 3840, True, 16) if x['item'] == 'Resolução 4K')['ok'])
sdr = clip('sdr.mp4', 16, hlg=False)
ok('HDR perdido (original era HDR): acusa', not next(x for x in validacao.verificar_final(sdr, 3.0, 1920, True, 16) if x['item'].startswith('Cor'))['ok'])
ok('original SDR e final SDR: ok', next(x for x in validacao.verificar_final(sdr, 3.0, 1920, False, 16) if x['item'].startswith('Cor'))['ok'])
mole = clip('mole.mp4', 48)
t = next(x for x in validacao.verificar_final(mole, 3.0, 1920, True, 10) if x['item'].startswith('Taxa'))
ok('compressão forte demais para "máxima": acusa a taxa de bits', not t['ok'], t['detalhe'])
ok('o mesmo arquivo na qualidade "leve" não acusa (sem piso)', next(x for x in validacao.verificar_final(mole, 3.0, 1920, True, 24) if x['item'].startswith('Taxa'))['ok'])
ok('duração diferente: acusa', not next(x for x in validacao.verificar_final(bom, 9.0, 1920, True, 16) if x['item'] == 'Duração')['ok'])
print(f'\n{sum(R)} de {len(R)} testes passaram'); sys.exit(0 if all(R) else 1)
