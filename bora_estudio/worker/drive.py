"""Leitura do Google Drive pelo editor (conta de serviço, só leitura).
A chave fica em BORA_GOOGLE_SA (padrão /trabalho/google_sa.json, dentro da VPS), nunca no repositório.
A pasta raiz (BORA_DRIVE_RAIZ) é compartilhada com o e-mail da conta de serviço como Leitor."""
import base64, json, os, time, urllib.parse, urllib.request

SA = os.environ.get('BORA_GOOGLE_SA', os.path.join(os.environ.get('BORA_TRABALHO', '/trabalho'), 'google_sa.json'))
RAIZ = os.environ.get('BORA_DRIVE_RAIZ', '1hCregORxfNChmd3vLQrYxmWKXVw_VZZP')      # pasta "Bora Claude"
API = 'https://www.googleapis.com/drive/v3'
_tok = {'v': None, 'ate': 0}

def configurado(): return os.path.exists(SA)

def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=')

def token():
    """Token de acesso de 1 h (JWT assinado com a chave da conta de serviço, escopo só leitura)."""
    if _tok['v'] and time.time() < _tok['ate'] - 120: return _tok['v']
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    sa = json.load(open(SA)); agora = int(time.time())
    cab = _b64(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
    corpo = _b64(json.dumps({'iss': sa['client_email'], 'scope': 'https://www.googleapis.com/auth/drive.readonly',
                             'aud': 'https://oauth2.googleapis.com/token', 'iat': agora, 'exp': agora + 3600}).encode())
    chave = serialization.load_pem_private_key(sa['private_key'].encode(), password=None)
    ass = _b64(chave.sign(cab + b'.' + corpo, padding.PKCS1v15(), hashes.SHA256()))
    dados = urllib.parse.urlencode({'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': (cab + b'.' + corpo + b'.' + ass).decode()}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=dados), timeout=30))
    _tok.update(v=r['access_token'], ate=time.time() + int(r.get('expires_in', 3600)))
    return _tok['v']

def _get(caminho, **q):
    q = {**q, 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
    r = urllib.request.Request(f'{API}/{caminho}?{urllib.parse.urlencode(q)}', headers={'Authorization': 'Bearer ' + token()})
    return json.load(urllib.request.urlopen(r, timeout=60))

def dentro_da_raiz(pasta):
    """Só deixa navegar pela pasta raiz e o que está dentro dela."""
    atual, passos = pasta, 0
    while atual and passos < 8:
        if atual == RAIZ: return True
        pais = _get(f'files/{atual}', fields='parents').get('parents') or []
        atual, passos = (pais[0] if pais else None), passos + 1
    return False

def listar(pasta=None):
    """Subpastas e vídeos de uma pasta (padrão: a raiz)."""
    pasta = pasta or RAIZ
    if not dentro_da_raiz(pasta): raise PermissionError('pasta fora da raiz do Bora Studio')
    itens, pag = [], None
    while True:
        r = _get('files', q=f"'{pasta}' in parents and trashed = false and (mimeType = 'application/vnd.google-apps.folder' or mimeType contains 'video/')",
                 fields='nextPageToken,files(id,name,mimeType,size,videoMediaMetadata(durationMillis,width,height),thumbnailLink)',
                 orderBy='folder,name', pageSize=200, **({'pageToken': pag} if pag else {}))
        itens += r.get('files', []); pag = r.get('nextPageToken')
        if not pag: break
    pastas = [{'id': f['id'], 'nome': f['name']} for f in itens if f['mimeType'].endswith('folder')]
    videos = [{'id': f['id'], 'nome': f['name'], 'tamanho': int(f.get('size') or 0),
               'dur': round(int((f.get('videoMediaMetadata') or {}).get('durationMillis') or 0) / 1000)} for f in itens if f['mimeType'].startswith('video/')]
    return {'pasta': pasta, 'pastas': pastas, 'videos': videos}

def baixar(fid, destino, prog=None):
    """Baixa o arquivo original (bytes exatos, sem conversão), retomando do ponto onde parou se a conexão cair."""
    meta = _get(f'files/{fid}', fields='size,parents')
    total = int(meta.get('size') or 0)
    if os.path.exists(destino) and os.path.getsize(destino) == total: return total
    parcial = destino + '.parcial'
    for t in range(8):
        ini = os.path.getsize(parcial) if os.path.exists(parcial) else 0
        if ini >= total: break
        try:
            r = urllib.request.Request(f'{API}/files/{fid}?alt=media&supportsAllDrives=true',
                                       headers={'Authorization': 'Bearer ' + token(), 'Range': f'bytes={ini}-'})
            with urllib.request.urlopen(r, timeout=300) as resp, open(parcial, 'ab' if ini and resp.status == 206 else 'wb') as f:
                feito = ini if resp.status == 206 else 0
                while True:
                    b = resp.read(4 << 20)
                    if not b: break
                    f.write(b); feito += len(b)
                    if prog: prog(feito, total)
        except Exception as e:
            print('drive: download interrompido, retomando', fid, e, flush=True); time.sleep(3 * (t + 1))
    if not os.path.exists(parcial) or os.path.getsize(parcial) != total: raise RuntimeError('o download do Drive não terminou')
    os.replace(parcial, destino); return total

_minis = {}
def miniatura(fid):
    """Miniatura do vídeo (gerada pelo próprio Drive), pra escolher os takes no app sem abrir um por um."""
    if fid in _minis: return _minis[fid]
    meta = _get(f'files/{fid}', fields='thumbnailLink,parents')
    pais = meta.get('parents') or []
    if not pais or not dentro_da_raiz(pais[0]): raise PermissionError('fora da pasta do Bora Studio')
    link = meta.get('thumbnailLink')
    if not link: return None
    link = link.split('=s')[0] + '=s320' if '=s' in link else link
    r = urllib.request.Request(link, headers={'Authorization': 'Bearer ' + token()})
    img = urllib.request.urlopen(r, timeout=30).read()
    if len(_minis) > 500: _minis.clear()
    _minis[fid] = img; return img
