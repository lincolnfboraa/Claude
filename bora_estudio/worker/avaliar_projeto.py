"""Valida a análise dos brutos num projeto que a gente já revisou: roda catálogo + planejador nos originais e compara
com a timeline aprovada (gabarito no formato de fabiola_reels_*/timeline.json: segmentos com fonte, in, out, funcao, fala).

Uso (no VPS, dentro do container do editor, que tem a chave da IA):
  python3 bora_estudio/worker/avaliar_projeto.py --pasta /trabalho/aval_energeticos \\
      --gabarito fabiola_reels_energeticos/timeline.json [--sem-ia] [--comparar-atual] [--cliente fabiola]
A pasta precisa ter os .MOV originais com o nome usado no gabarito (IMG_2596.MOV...). Sem eles, baixa pelo drive_id do gabarito.
Saída: <pasta>/avaliacao.json e <pasta>/AVALIACAO.md (nada vai pro app nem pro banco).
"""
import argparse, difflib, glob, json, os, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import montagem, analise_brutos

def baixar_originais(pasta, gab):
    for nome, f in gab.get('fontes', {}).items():
        dest = os.path.join(pasta, f.get('arquivo') or nome + '.MOV')
        if os.path.exists(dest) or not f.get('drive_id'): continue
        import drive
        print('baixando do Drive:', dest, flush=True); drive.baixar(f['drive_id'], dest + '.parcial', None); os.replace(dest + '.parcial', dest)

def timeline_do_plano(pl, palavras):
    """Segmentos do plano em tempo dos arquivos originais: (arquivo_idx, in, out, texto, intervalo)."""
    G = montagem.indice_global(palavras); out = []
    for sg in pl['segmentos']:
        a, b = int(sg['palavra_inicio']), int(sg['palavra_fim'])
        (ai, ka), (_, kb) = G[a], G[b]
        out.append({'arquivo': ai, 'in': palavras[ai][ka]['s'], 'out': palavras[ai][kb]['e'], 'intervalo': sg.get('intervalo'),
                    'fala': ' '.join(w['w'] for w in palavras[ai][ka:kb + 1])})
    return out

def comparar(gab_segs, auto, nomes, cat=None):
    def iou(x, y):
        inter = max(0.0, min(x[1], y[1]) - max(x[0], y[0])); uni = max(x[1], y[1]) - min(x[0], y[0])
        return inter / uni if uni > 0 else 0.0
    sim = lambda a, b: difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    linhas, usados = [], set()
    for g in gab_segs:
        fonte = g['fonte']; gi = (g['in'], g['out'])
        mesmos = [(i, s) for i, s in enumerate(auto) if os.path.splitext(nomes[s['arquivo']])[0] == fonte]
        melhor = max(mesmos, key=lambda t: iou(gi, (t[1]['in'], t[1]['out'])), default=None)
        r = {'gabarito': f"{fonte} {g['in']:.2f}-{g['out']:.2f}", 'funcao_gabarito': g.get('funcao', ''), 'fala': g.get('fala', '')[:80]}
        if melhor and iou(gi, (melhor[1]['in'], melhor[1]['out'])) > 0:
            s = melhor[1]; usados.add(melhor[0])
            r.update({'auto': f"{fonte} {s['in']:.2f}-{s['out']:.2f}", 'iou': round(iou(gi, (s['in'], s['out'])), 2),
                      'erro_in_s': round(s['in'] - g['in'], 2), 'erro_out_s': round(s['out'] - g['out'], 2)})
        else:
            outro = max(((i, s) for i, s in enumerate(auto)), key=lambda t: sim(t[1]['fala'], g.get('fala', '')), default=None)
            if outro and sim(outro[1]['fala'], g.get('fala', '')) > 0.6:
                usados.add(outro[0]); r.update({'auto': f"{nomes[outro[1]['arquivo']]} {outro[1]['in']:.2f}-{outro[1]['out']:.2f}", 'iou': 0.0, 'erro': 'mesma fala, take diferente'})
            else: r.update({'auto': None, 'iou': 0.0, 'erro': 'trecho do gabarito não foi escolhido'})
        if cat:                                                    # o catálogo aprovaria a imagem que a gente usou?
            ivs = [iv for iv in cat['intervalos'] if os.path.splitext(iv['nome'])[0] == fonte and iou(gi, (iv['inicio'], iv['fim'])) > 0.3]
            if ivs:
                iv = max(ivs, key=lambda x: iou(gi, (x['inicio'], x['fim'])))
                r.update({'catalogo': iv['id'], 'catalogo_utilizavel': iv.get('utilizavel'), 'catalogo_funcao': iv.get('funcao_narrativa'), 'catalogo_nota': iv.get('nota')})
        linhas.append(r)
    extras = [f"{nomes[s['arquivo']]} {s['in']:.2f}-{s['out']:.2f}: {s['fala'][:60]}" for i, s in enumerate(auto) if i not in usados]
    acertos = [r for r in linhas if r['iou'] >= 0.5]
    met = {'segmentos_gabarito': len(gab_segs), 'segmentos_auto': len(auto), 'acertos_iou50': len(acertos),
           'recall': round(len(acertos) / max(1, len(gab_segs)), 2), 'precisao': round(len(acertos) / max(1, len(auto)), 2),
           'erro_medio_entrada_s': round(sum(abs(r['erro_in_s']) for r in acertos) / max(1, len(acertos)), 2),
           'erro_medio_saida_s': round(sum(abs(r['erro_out_s']) for r in acertos) / max(1, len(acertos)), 2),
           'take_trocado': sum(1 for r in linhas if r.get('erro') == 'mesma fala, take diferente'),
           'nao_escolhidos': sum(1 for r in linhas if r.get('erro') == 'trecho do gabarito não foi escolhido'), 'extras': len(extras)}
    if cat:
        com = [r for r in linhas if 'catalogo_utilizavel' in r]
        met['catalogo_rejeitou_o_que_usamos'] = sum(1 for r in com if r['catalogo_utilizavel'] is False)
        mapa = lambda f: f.split()[0].lower().replace('ç', 'c').replace('ã', 'a') if f else ''
        met['funcao_igual'] = f"{sum(1 for r in com if mapa(r['funcao_gabarito']).startswith(r.get('catalogo_funcao') or '#'))} de {len(com)}"
    return met, linhas, extras

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pasta', required=True); ap.add_argument('--gabarito', required=True)
    ap.add_argument('--sem-ia', action='store_true', help='só a parte técnica (custo zero)')
    ap.add_argument('--comparar-atual', action='store_true', help='também roda o planejador de hoje (sem catálogo) pra comparar')
    ap.add_argument('--cliente', default=None, help='id do cliente no Supabase pra usar o DNA dele')
    a = ap.parse_args()
    gab = json.load(open(a.gabarito)); os.makedirs(a.pasta, exist_ok=True); os.environ['BORA_TRABALHO'] = a.pasta
    baixar_originais(a.pasta, gab)
    fontes = [f.get('arquivo') or k + '.MOV' for k, f in gab['fontes'].items()]
    arqs = [os.path.join(a.pasta, f) for f in fontes if os.path.exists(os.path.join(a.pasta, f))]
    if not arqs: sys.exit('nenhum original encontrado na pasta')
    nomes = [os.path.basename(x) for x in arqs]; rel = {'arquivos': nomes, 'tempos_s': {}, 'custo_usd': {}}
    t0 = time.time()
    pal = [montagem.transcrever(x, os.path.join(a.pasta, f'transcricao_{i + 1:02d}.json')) for i, x in enumerate(arqs)]
    rel['tempos_s']['transcricao'] = round(time.time() - t0, 1)
    papeis = [montagem.classificar(pal[i], arqs[i]) for i in range(len(arqs))]
    t0 = time.time(); cat = analise_brutos.catalogo(arqs, pal, papeis, a.pasta, nomes, visual=not a.sem_ia)
    rel['tempos_s'].update({'analise_tecnica': cat['tempos']['tecnica_s'], 'analise_visual': cat['tempos']['visual_s'], 'catalogo_total': round(time.time() - t0, 1)})
    rel['custo_usd']['analise_visual'] = cat['uso']['custo_usd']
    rel['catalogo'] = {'intervalos': len(cat['intervalos']), 'nao_utilizaveis': sum(1 for iv in cat['intervalos'] if not iv.get('utilizavel'))}
    segs_gab = gab['segmentos']
    if a.sem_ia:
        met, linhas, extras = comparar(segs_gab, [], nomes, cat); rel.update({'metricas_catalogo': met, 'linhas': linhas})
    else:
        import plano as plano_ia
        sbget = None
        try:
            import servidor; sbget = servidor.sb
        except Exception: pass
        regras = ((sbget('GET', '/rest/v1/regras_globais?id=eq.1&select=regras') or [{}])[0].get('regras') or {}) if sbget else {}
        cli = ((sbget('GET', f'/rest/v1/clientes?id=eq.{a.cliente}&select=*') or [{}])[0]) if (sbget and a.cliente) else {'nome': gab.get('projeto', '')}
        dna = ((sbget('GET', f'/rest/v1/dna_ativo?cliente_id=eq.{a.cliente}&select=dna') or [{}])[0].get('dna') or {}) if (sbget and a.cliente) else {}
        brolls = [{'n': k + 1, 'ai': i, 'nome': nomes[i], 'dur': montagem.duracao(arqs[i]), 'jpg': None} for k, i in enumerate(i for i, p in enumerate(papeis) if p == 'ambiente')]
        t0 = time.time(); pl = plano_ia.gerar(pal, arqs, cli, dna, regras, '', None, (), (), papeis, brolls, cat)
        rel['tempos_s']['planejador'] = round(time.time() - t0, 1)
        rel['custo_usd']['planejador'] = round((pl['_uso']['entrada'] * 4 + pl['_uso']['saida'] * 20) / 1e6, 4)
        auto = timeline_do_plano(pl, pal); met, linhas, extras = comparar(segs_gab, auto, nomes, cat)
        rel.update({'metricas': met, 'linhas': linhas, 'extras': extras, 'faltas': pl.get('_faltas'), 'descartes': pl.get('_descartes')})
        json.dump(pl, open(os.path.join(a.pasta, 'plano_avaliacao.json'), 'w'), ensure_ascii=False, indent=1)
        if a.comparar_atual:
            t0 = time.time(); pl0 = plano_ia.gerar(pal, arqs, cli, dna, regras, '', None, (), (), papeis, [])
            met0, _, _ = comparar(segs_gab, timeline_do_plano(pl0, pal), nomes)
            rel['metricas_sistema_atual'] = met0; rel['tempos_s']['planejador_atual'] = round(time.time() - t0, 1)
            rel['custo_usd']['planejador_atual'] = round((pl0['_uso']['entrada'] * 4 + pl0['_uso']['saida'] * 20) / 1e6, 4)
    rel['custo_usd']['total'] = round(sum(v for k, v in rel['custo_usd'].items() if k != 'planejador_atual'), 4)
    json.dump(rel, open(os.path.join(a.pasta, 'avaliacao.json'), 'w'), ensure_ascii=False, indent=1)
    md = [f"# Avaliação da análise dos brutos: {gab.get('projeto', '')}", '', f"Arquivos: {', '.join(nomes)}", '',
          '## Métricas', '', '```', json.dumps(rel.get('metricas') or rel.get('metricas_catalogo'), ensure_ascii=False, indent=1), '```']
    if rel.get('metricas_sistema_atual'): md += ['', '## Sistema atual (sem catálogo)', '', '```', json.dumps(rel['metricas_sistema_atual'], ensure_ascii=False, indent=1), '```']
    md += ['', '## Tempo (s) e custo (US$)', '', '```', json.dumps({'tempos_s': rel['tempos_s'], 'custo_usd': rel['custo_usd']}, ensure_ascii=False, indent=1), '```',
           '', '## Trecho a trecho', '', '| Gabarito | Automático | IoU | Δ entrada | Δ saída | Catálogo | Erro |', '|---|---|---|---|---|---|---|']
    for r in rel['linhas']:
        md.append(f"| {r['gabarito']} ({r['funcao_gabarito']}) | {r.get('auto') or '-'} | {r['iou']} | {r.get('erro_in_s', '-')} | {r.get('erro_out_s', '-')} | "
                  f"{r.get('catalogo', '-')} {'ok' if r.get('catalogo_utilizavel') else ('NÃO USAR' if r.get('catalogo_utilizavel') is False else '')} {r.get('catalogo_funcao', '')} | {r.get('erro', '')} |")
    if rel.get('faltas'): md += ['', '## Faltas apontadas', ''] + [f"- {f['momento']}: {f['problema']} → {f['proposta']}" for f in rel['faltas']]
    open(os.path.join(a.pasta, 'AVALIACAO.md'), 'w').write('\n'.join(md) + '\n')
    print('\n'.join(md))

if __name__ == '__main__':
    main()
