"""Motor de edição do Bora Studio.
nova_edicao / ajuste: transcreve os originais, a IA monta o plano no DNA do cliente, ffmpeg monta a prévia 480p (HDR do original),
  os textos entram no padrão aprovado e a prévia vai pro app.
final: renderiza de novo a partir dos ORIGINAIS na resolução nativa (4K), com e sem legenda + .srt, num .zip (sem compressão)."""
import glob, json, os, subprocess, urllib.request
import montagem, plano as plano_ia, textos

TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')

def _arquivos(pid, meta):
    arqs = [a['caminho'] for a in (meta.get('arquivos') or []) if os.path.exists(a.get('caminho', ''))]
    return arqs or sorted(glob.glob(os.path.join(TRAB, pid, 'original_*.*')))

def _subir(sb, caminho, arq, tipo):
    url = os.environ['SUPABASE_URL'].rstrip('/') + f'/storage/v1/object/previas/{caminho}'
    r = urllib.request.Request(url, data=open(arq, 'rb').read(), method='POST',
                               headers={'apikey': os.environ['SUPABASE_SECRET'], 'Content-Type': tipo, 'x-upsert': 'true'})
    urllib.request.urlopen(r, timeout=600).read()

def _transcricoes(pid, arqs, etapa):
    pal = []
    for i, a in enumerate(arqs, 1):
        etapa(f'Transcrevendo {"o vídeo" if len(arqs) == 1 else f"o vídeo {i} de {len(arqs)}"}', 8 + int(17 * (i - 1) / len(arqs)))
        pal.append(montagem.transcrever(a, os.path.join(TRAB, pid, f'transcricao_{i:02d}.json')))
    if not any(pal): raise RuntimeError('não encontrei fala nos vídeos enviados')
    return pal

def _renderizar(pid, pl, arqs, pal, altura, cores, saida_base, etapa=None, faixa=(45, 80), crf_final=24):
    pasta = os.path.join(TRAB, pid)
    pcs, tokens, dur = montagem.pecas(pl, arqs, pal, pasta)
    if not pcs: raise RuntimeError('o plano não gerou nenhum trecho')
    base = os.path.join(pasta, f'_base_{altura}.mp4')
    a, b = faixa
    prog = (lambda f: etapa('Montando o vídeo a partir dos originais', a + int((b - a) * f))) if etapa else None
    hdr = montagem.render_base(pcs, arqs, base, altura, 14, prog)
    ro = textos.Roteiro(tokens, dur, cores.get('leg'), cores.get('dest'))
    if pl.get('usar_titulo') and pl.get('titulo', {}).get('tema'):
        seg1 = next((t['e'] for t in tokens if t['i'] >= pl['segmentos'][0]['palavra_fim']), 3.0)
        ro.titulo(pl['titulo'], min(max(seg1 + 1.0, 3.0), 5.5))
    for d in pl.get('destaques', []): ro.destaque(d)
    ro.gravar(saida_base)
    return base, hdr, dur, tokens

def executar(p, etapa, sb):
    pid, tipo = p['projeto_id'], p['tipo']
    proj = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=*')[0]
    meta, cli_id = proj.get('original_meta') or {}, proj['cliente_id']
    cliente = sb('GET', f'/rest/v1/clientes?id=eq.{cli_id}&select=*')[0]
    dna = (sb('GET', f'/rest/v1/dna_ativo?cliente_id=eq.{cli_id}&select=dna') or [{}])[0].get('dna') or {}
    regras = (sb('GET', '/rest/v1/regras_globais?id=eq.1&select=regras') or [{}])[0].get('regras') or {}
    versoes = sb('GET', f'/rest/v1/versoes?projeto_id=eq.{pid}&select=*&order=numero')
    v = next((x for x in versoes if x['id'] == p.get('versao_id')), versoes[-1])
    arqs = _arquivos(pid, meta)
    if not arqs: raise RuntimeError('os vídeos originais não estão no servidor; envie de novo pelo app')
    tx = (dna.get('texto') or {})
    cores = {'leg': (proj.get('cores_texto') or {}).get('leg') or tx.get('legenda') or '#FFFFFF',
             'dest': (proj.get('cores_texto') or {}).get('dest') or tx.get('destaque') or '#C8B9A7'}
    pasta = os.path.join(TRAB, pid); os.makedirs(pasta, exist_ok=True)
    etapa('Lendo o pedido', 5)
    pal = _transcricoes(pid, arqs, etapa)

    if tipo in ('nova_edicao', 'ajuste'):
        n = v['numero']
        anterior = None
        ant_arq = os.path.join(pasta, f'plano_v{n - 1}.json')
        if n > 1 and os.path.exists(ant_arq): anterior = json.load(open(ant_arq))
        feedbacks = [(x['numero'], x['feedback']) for x in versoes if x.get('feedback') and x['numero'] < n]
        etapa('A IA está montando o storytelling no DNA do cliente' if not anterior else 'A IA está aplicando o seu ajuste', 28)
        pronto = os.path.join(pasta, f'plano_v{n}.json')
        if os.path.exists(pronto):                     # retomada: reaproveita o plano já pago desta versão
            pl = json.load(open(pronto))
        else:
            pl = plano_ia.gerar(pal, arqs, cliente, dna, regras, meta.get('briefing', ''), anterior, feedbacks)
        json.dump(pl, open(os.path.join(pasta, f'plano_v{n}.json'), 'w'), ensure_ascii=False, indent=1)
        import re
        novas = {k: v for k, v in {'leg': (pl.get('cores') or {}).get('legenda', ''), 'dest': (pl.get('cores') or {}).get('destaque', '')}.items()
                 if re.fullmatch(r'#[0-9A-Fa-f]{6}', (v or '').strip())}
        if novas:                                       # cor pedida no feedback vale desta versão em diante
            cores.update(novas)
            sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'cores_texto': {**(proj.get('cores_texto') or {}), **novas}})
        etapa('Cortando pausas e montando', 40)
        saida_txt = os.path.join(pasta, f'textos_v{n}')
        base, hdr, dur, _ = _renderizar(pid, pl, arqs, pal, 854, cores, saida_txt, etapa, (42, 72))
        etapa('Textos, título e destaques', 76)
        previa = os.path.join(pasta, f'previa_v{n}.mp4')
        montagem.aplicar_textos(base, saida_txt + '.ass', previa, hdr, 24)
        etapa('Enviando a prévia pro app', 93)
        caminho = f'{cli_id}/{pid}/v{n}.mp4'; _subir(sb, caminho, previa, 'video/mp4')
        sb('PATCH', f"/rest/v1/versoes?id=eq.{v['id']}", {'status': 'revisao', 'previa_path': caminho, 'resumo': (pl.get('resumo') or f'Versão {n}') + (f" Ainda não aplicado (o motor não faz ainda): {pl['nao_feito']}" if (pl.get('nao_feito') or '').strip() else '')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'status': 'revisao'})
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m.update({'andamento': None, 'progresso': None, 'dur': f'{round(dur)} s'})
        if pl.get('usar_titulo'): m.update({'rotulo': pl['titulo'].get('rotulo'), 'pergunta': pl['titulo'].get('pergunta')})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
        return

    if tipo == 'final':
        planos = sorted(glob.glob(os.path.join(pasta, 'plano_v*.json')), key=lambda x: int(x.rsplit('_v', 1)[1].split('.')[0]))
        if not planos: raise RuntimeError('não encontrei o plano aprovado deste projeto')
        pl = json.load(open(planos[-1]))
        altura = max(montagem.sondar(a)[1] if montagem.sondar(a)[1] >= montagem.sondar(a)[0] else montagem.sondar(a)[0] for a in arqs[:1])
        altura = min(altura, 3840); altura -= altura % 2
        etapa('Renderizando o final a partir dos originais', 8)
        fim = os.path.join(pasta, 'final'); os.makedirs(fim, exist_ok=True)
        nome = ''.join(c for c in f"{cliente['nome']}_{proj['titulo']}".replace(' ', '_') if c.isalnum() or c in '_-')[:60]
        saida_txt = os.path.join(fim, nome + '_legendas')
        base, hdr, dur, _ = _renderizar(pid, pl, arqs, pal, altura, cores, saida_txt, etapa, (10, 70))
        etapa('Aplicando os textos no 4K', 74)
        leg = os.path.join(fim, nome + f'_{altura}p_legendado.mp4')
        montagem.aplicar_textos(base, saida_txt + '.ass', leg, hdr, 24)
        etapa('Versão sem legenda', 90)
        params, tags = montagem.x265(montagem.sondar(arqs[0])[2])
        sem = os.path.join(fim, nome + f'_{altura}p_sem_legenda.mp4')
        montagem.sh(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', base, '-c:v', 'libx265', '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p10le',
                     '-x265-params', params, *tags, '-tag:v', 'hvc1', '-c:a', 'copy', '-movflags', '+faststart', sem])
        os.replace(saida_txt + '.srt', os.path.join(fim, nome + '_legendas.srt'))
        zipf = os.path.join(fim, nome + '_final.zip')
        if os.path.exists(zipf): os.remove(zipf)
        subprocess.run(['zip', '-0', '-j', '-q', zipf, leg, sem, os.path.join(fim, nome + '_legendas.srt')], check=True)
        for x in (base, saida_txt + '.ass'):
            if os.path.exists(x): os.remove(x)
        m = sb('GET', f'/rest/v1/projetos?id=eq.{pid}&select=original_meta')[0]['original_meta'] or {}
        m.update({'andamento': None, 'progresso': None, 'final_pronto': True, 'final_zip': zipf, 'final_nome': os.path.basename(zipf),
                  'final_mb': round(os.path.getsize(zipf) / 1048576)})
        sb('PATCH', f'/rest/v1/projetos?id=eq.{pid}', {'original_meta': m})
        return
    raise RuntimeError('tipo de pedido desconhecido: ' + tipo)
