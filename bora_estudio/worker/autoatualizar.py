"""Atualização automática do computador de render (Acer): ele roda o MESMO código do editor (VPS).
O editor mede o hash do próprio código (só o que roda: .py, .json, fontes; sem testes nem caches) e serve o pacote em /worker/codigo.
O worker compara com o hash dele; se for diferente, baixa, confere (hash, caminhos e sintaxe) e troca a pasta, sem apagar nada antes de ter certeza.
Qualquer falha mantém o código antigo. O programa sai e o Docker (restart: unless-stopped) reinicia já com o código novo.
Só biblioteca do sistema nova exige reinstalar (BORA_IMAGEM no Dockerfile)."""
import hashlib, io, os, shutil, tarfile

INCLUI = ('.py', '.json', '.ttf', '.otf')
IGNORAR_DIRS = {'__pycache__', 'render_cache', 'modelos', 'piloto', '.git', 'node_modules'}

def _lista(raiz):
    out = []
    for pasta, dirs, arqs in os.walk(raiz):
        dirs[:] = sorted(d for d in dirs if d not in IGNORAR_DIRS)
        for a in sorted(arqs):
            if a.endswith(INCLUI) and not a.startswith(('teste_', 'testes_')):
                out.append(os.path.relpath(os.path.join(pasta, a), raiz).replace(os.sep, '/'))
    return sorted(out)

def hash_codigo(raiz):
    """Impressão digital do código que roda (16 caracteres)."""
    h = hashlib.sha256()
    for rel in _lista(raiz):
        h.update(rel.encode()); h.update(b'\0'); h.update(open(os.path.join(raiz, rel), 'rb').read()); h.update(b'\0')
    return h.hexdigest()[:16]

def empacotar(raiz):
    """tar.gz (em memória) só com os arquivos que contam pro hash."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as t:
        for rel in _lista(raiz):
            t.add(os.path.join(raiz, rel), arcname=rel, filter=lambda i: (setattr(i, 'uid', 0), setattr(i, 'gid', 0), setattr(i, 'mode', 0o644), i)[3])
    return buf.getvalue()

def aplicar(pacote, raiz, hash_esperado):
    """Extrai ao lado, confere e troca a pasta `raiz` pela nova. Levanta ValueError (e não mexe em nada) se algo não bater."""
    base = raiz.rstrip('/\\'); novo, antigo = base + '.novo', base + '.antigo'
    for d in (novo, antigo): shutil.rmtree(d, ignore_errors=True)
    os.makedirs(novo)
    try:
        with tarfile.open(fileobj=io.BytesIO(pacote), mode='r:gz') as t:
            raiz_real = os.path.realpath(novo) + os.sep
            for m in t.getmembers():
                if not os.path.realpath(os.path.join(novo, m.name)).startswith(raiz_real) or not (m.isfile() or m.isdir()):
                    raise ValueError('pacote com caminho inválido: ' + m.name)
            t.extractall(novo)
        if hash_codigo(novo) != hash_esperado: raise ValueError('o pacote não confere com o hash do editor')
        for rel in _lista(novo):
            if rel.endswith('.py'): compile(open(os.path.join(novo, rel), encoding='utf-8').read(), rel, 'exec')      # erro de sintaxe: não troca
    except Exception:
        shutil.rmtree(novo, ignore_errors=True); raise
    os.replace(base, antigo)
    try: os.replace(novo, base)
    except Exception:
        os.replace(antigo, base); raise
    shutil.rmtree(antigo, ignore_errors=True)
    return True
