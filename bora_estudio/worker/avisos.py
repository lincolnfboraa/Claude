"""Notificações push (Web Push / VAPID) para o app na Tela de Início do iPhone.
Inscrições e chaves ficam no próprio servidor (pasta de trabalho), sem custo e sem serviço externo."""
import base64, json, os, threading
from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization

TRAB = os.environ.get('BORA_TRABALHO', '/trabalho')
ARQ_CHAVE, ARQ_INSC = os.path.join(TRAB, 'vapid_privada.pem'), os.path.join(TRAB, 'inscricoes_push.json')
_trava = threading.Lock()

def _vapid():
    if not os.path.exists(ARQ_CHAVE):
        v = Vapid(); v.generate_keys(); v.save_key(ARQ_CHAVE)
    return Vapid.from_file(ARQ_CHAVE)

def chave_publica():
    pub = _vapid().public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(pub).decode().rstrip('=')

def _ler():
    try: return json.load(open(ARQ_INSC))
    except Exception: return []

def inscrever(insc, usuario):
    with _trava:
        lst = [x for x in _ler() if x['sub'].get('endpoint') != insc.get('endpoint')]
        lst.append({'sub': insc, 'usuario': usuario}); json.dump(lst, open(ARQ_INSC, 'w'))
    return len(lst)

def enviar(titulo, texto, url='/'):
    """Manda pra todos os aparelhos inscritos; remove inscrições que expiraram."""
    from pywebpush import webpush, WebPushException
    vivas = []
    for x in _ler():
        try:
            webpush(x['sub'], json.dumps({'titulo': titulo, 'texto': texto, 'url': url}), vapid_private_key=ARQ_CHAVE,
                    vapid_claims={'sub': 'mailto:contato@borasolucoesdigitais.com'}, ttl=86400)
            vivas.append(x)
        except WebPushException as e:
            if e.response is None or e.response.status_code not in (404, 410): vivas.append(x)
        except Exception as e:
            print('push:', e, flush=True); vivas.append(x)
    with _trava: json.dump(vivas, open(ARQ_INSC, 'w'))
    return len(vivas)
