"""Ajudantes do worker: REST e Storage do Supabase (chave injetada pelo proxy)."""
import json, urllib.request
BASE = 'https://gsychapfrpfjqmzbcpkk.supabase.co'
H = {'apikey': 'proxy-injected', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
def req(metodo, path, corpo=None, headers=None):
    d = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + path, data=d, method=metodo, headers={**H, **(headers or {})})
    return json.load(urllib.request.urlopen(r, timeout=60))
def get(t): return req('GET', '/rest/v1/' + t)
def patch(t, filtro, corpo): return req('PATCH', f'/rest/v1/{t}?{filtro}', corpo)
def post(t, corpo): return req('POST', '/rest/v1/' + t, corpo)
def meta(projeto_id, **campos):
    """mescla campos em projetos.original_meta (andamento, final_pronto...)"""
    m = get(f'projetos?id=eq.{projeto_id}&select=original_meta')[0]['original_meta'] or {}
    m.update(campos); return patch('projetos', f'id=eq.{projeto_id}', {'original_meta': m})
def upload(bucket, caminho, arquivo, tipo='video/mp4'):
    r = urllib.request.Request(f'{BASE}/storage/v1/object/{bucket}/{caminho}', data=open(arquivo, 'rb').read(), method='POST',
                               headers={'apikey': 'proxy-injected', 'Content-Type': tipo, 'x-upsert': 'true'})
    return json.load(urllib.request.urlopen(r, timeout=600))
