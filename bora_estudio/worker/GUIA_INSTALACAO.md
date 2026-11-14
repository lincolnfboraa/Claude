# Bora Studio no VPS (Peramix + n8n) | passo a passo

Resultado: você pede no app, o Supabase avisa o n8n, o n8n entrega pro editor no VPS, e o editor devolve status, % e vídeo pro app.
Tempo total: uns 40 minutos. Faça na ordem.

## Parte 1. Peramix: entrar no servidor
1. No painel da Peramix, abra o VPS **vmid3238** e clique em **Console** (ou use um terminal: `ssh root@206.183.129.41`, senha do painel).
2. Confira o Docker:
   ```bash
   docker --version && docker compose version
   ```
   Se der "command not found", instale:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. Veja como o n8n roda (anote o nome que aparecer):
   ```bash
   docker ps --format '{{.Names}}  {{.Image}}  {{.Ports}}'
   ```

## Parte 2. Baixar o projeto da Bora no VPS
1. Crie a chave de leitura do GitHub:
   ```bash
   ssh-keygen -t ed25519 -N "" -f /root/.ssh/bora_github && cat /root/.ssh/bora_github.pub
   ```
2. Copie a linha que começa com `ssh-ed25519`. No GitHub: repositório **lincolnfboraa/Claude** > **Settings** > **Deploy keys** > **Add deploy key**.
   Título `vps-peramix`, cole a chave, deixe **Allow write access desmarcado**, salve.
3. Baixe o projeto:
   ```bash
   mkdir -p /opt/bora/trabalho /opt/bora/modelos && cd /opt/bora
   GIT_SSH_COMMAND="ssh -i /root/.ssh/bora_github -o StrictHostKeyChecking=accept-new" git clone -b claude/upbeat-tesla-qu1g6k git@github.com:lincolnfboraa/Claude.git repo
   ```

## Parte 3. Chaves (ficam só no VPS)
1. **Anthropic:** em console.anthropic.com > **API Keys** > **Create Key** (nome `bora-studio`). Coloque créditos em **Billing** (US$ 5 a 10 já servem pra começar).
2. **Supabase:** em **Project Settings > API Keys**, copie a **Secret key** (`sb_secret_…`).
3. **Token interno** (senha entre n8n e editor), gere com:
   ```bash
   openssl rand -hex 24
   ```
4. Crie o arquivo de chaves (troque os 3 valores):
   ```bash
   cat > /opt/bora/bora.env <<'FIM'
   SUPABASE_URL=https://gsychapfrpfjqmzbcpkk.supabase.co
   SUPABASE_SECRET=COLE_A_SB_SECRET
   ANTHROPIC_API_KEY=COLE_A_CHAVE_ANTHROPIC
   BORA_TOKEN=COLE_O_TOKEN_GERADO
   FIM
   chmod 600 /opt/bora/bora.env
   ```

## Parte 4. Ligar o editor
```bash
cd /opt/bora/repo && docker compose -f bora_estudio/worker/docker-compose.yml up -d --build
curl -s http://localhost:8787
```
Tem que aparecer `{"ok": true, "na_fila": 0}`. A primeira vez demora uns 5 minutos (instala ffmpeg e a transcrição).

## Parte 5. n8n
1. Abra o n8n > **Workflows** > **Import from file** > escolha `bora_estudio/worker/n8n_bora_studio.json` (te mando o arquivo).
2. Nó **Supabase avisa**: em *Credential*, crie **Header Auth** com Name `X-Bora-Token` e Value = o token interno. Salve.
3. Nó **Enviar pro editor**: troque `COLE_AQUI_O_BORA_TOKEN` pelo token interno.
   - Se o n8n roda em Docker, o endereço `http://172.17.0.1:8787/pedido` já funciona.
   - Se não conectar, me mande o resultado do `docker ps` da Parte 1 que eu ajusto.
4. Clique em **Save** e ligue **Active** (canto superior direito).
5. Abra o nó **Supabase avisa** e copie a **Production URL** (algo como `https://seu-n8n.dominio/webhook/bora-studio`).

## Parte 6. Supabase avisa o n8n
No Supabase: **Database > Webhooks** (se pedir, clique em *Enable webhooks*) > **Create a new hook**. Crie dois:

| Nome | Tabela | Eventos |
|---|---|---|
| `bora_versoes` | `versoes` | Insert |
| `bora_projetos` | `projetos` | Update |

Nos dois: Type **HTTP Request**, Method **POST**, URL = a Production URL do n8n,
HTTP Headers: `X-Bora-Token` = o token interno. Salve.

## Parte 7. Teste
1. No app, abra a Próstata e toque em **Pedir ajuste** (escreva qualquer coisa curta).
2. No n8n, em **Executions**, deve aparecer uma execução verde.
3. No app, o botão de status mostra o vídeo "Na fila do editor" e depois "Pedido recebido pelo editor".

Neste momento o motor de edição automática ainda não está ativo: o teste confirma que a ligação app → Supabase → n8n → editor → app funciona.
O motor (transcrição + plano da IA com o DNA do cliente + render HDR) entra numa atualização: no VPS basta rodar
```bash
cd /opt/bora/repo && git pull && docker compose -f bora_estudio/worker/docker-compose.yml up -d --build
```

## Se algo der errado
- `docker logs bora-editor --tail 50` mostra o que o editor está fazendo.
- Execução vermelha no n8n: abra e me mande o print do erro.
