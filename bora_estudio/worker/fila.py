#!/usr/bin/env python3
"""Vigia da fila do Bora Studio. Consulta o Supabase a cada 20 s e termina (imprimindo os pedidos em JSON)
quando aparece trabalho: versão nova em 'editando' (nova edição ou ajuste) ou projeto aprovado sem final.
A chave secreta é injetada pelo proxy do ambiente (cabeçalho apikey); aqui vai só um marcador.
Uso: python3 fila.py [max_horas=8]   |   python3 fila.py --uma  (consulta uma vez e sai)"""
import json, sys, time, urllib.request
URL = 'https://gsychapfrpfjqmzbcpkk.supabase.co/rest/v1/'
def get(path):
    r = urllib.request.Request(URL + path, headers={'apikey': 'proxy-injected'})
    return json.load(urllib.request.urlopen(r, timeout=30))
def pedidos():
    out = []
    for v in get('versoes?status=eq.editando&select=id,numero,projeto_id,resumo,projetos(id,titulo,cliente_id,status,original_meta)'):
        p = v['projetos'] or {}
        if (p.get('original_meta') or {}).get('andamento_versao') == v['id']:
            continue                                         # já em produção
        ant = get(f"versoes?projeto_id=eq.{v['projeto_id']}&numero=eq.{v['numero']-1}&select=feedback")
        out.append({'tipo': 'ajuste' if v['numero'] > 1 else 'nova_edicao', 'cliente': p.get('cliente_id'), 'projeto': p.get('titulo'),
                    'projeto_id': v['projeto_id'], 'versao_id': v['id'], 'versao': v['numero'],
                    'feedback': ant[0]['feedback'] if ant else None, 'original': (p.get('original_meta') or {}).get('arq')})
    for p in get('projetos?status=eq.aprovado&select=id,titulo,cliente_id,original_meta,versoes(id,numero,status,final_drive_id)'):
        m = p.get('original_meta') or {}
        vs = sorted(p['versoes'], key=lambda x: x['numero'])
        if vs and not vs[-1]['final_drive_id'] and not m.get('final_pronto') and m.get('andamento_versao') != 'final:' + vs[-1]['id']:
            out.append({'tipo': 'final', 'cliente': p['cliente_id'], 'projeto': p['titulo'], 'projeto_id': p['id'], 'versao_id': vs[-1]['id'], 'versao': vs[-1]['numero']})
    return out
if __name__ == '__main__':
    if '--uma' in sys.argv:
        print(json.dumps(pedidos(), ensure_ascii=False, indent=1)); sys.exit()
    fim = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 8) * 3600
    while time.time() < fim:
        try:
            p = pedidos()
            if p:
                print('PEDIDOS', json.dumps(p, ensure_ascii=False, indent=1)); sys.exit(0)
        except Exception as e:
            print('erro', e, flush=True)
        time.sleep(20)
    print('SEM_PEDIDOS')
