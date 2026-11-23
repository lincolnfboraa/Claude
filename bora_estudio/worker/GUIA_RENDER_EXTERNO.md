# Render 4K externo (Acer)

**Como funciona**
- **No VPS, como hoje:** análise, plano da IA e prévia 480p.
- **No Acer:** só o **final 4K aprovado**. Ele usa os originais e a mesma timeline aprovada (o mesmo `plano_vN.json`).

**Caminho do 4K**
1. O app aprova o vídeo. O VPS grava o trabalho na fila `render_trabalhos` (Supabase) e fica livre na hora.
2. O Acer pede trabalho ao editor do VPS (HTTPS + `BORA_WORKER_TOKEN`). Ele baixa só os arquivos daquele trabalho, com cache e retomada.
3. O Acer renderiza com o mesmo motor (`motor.renderizar`) e devolve o .zip em partes.
4. O VPS confere os tamanhos, grava no projeto e o botão **Baixar 4K** aparece no app.

**Regras**
- **Sem fallback:** com o Acer desligado, o trabalho espera na fila.
- **Falha ou Acer sem sinal por 15 min:** o trabalho volta pra fila. Na 3ª falha vira erro no app, com o botão **Tentar de novo**.
- **Chaves:** o Acer nunca recebe chave do Supabase nem da IA.
- **Duplicidade:** a trava no banco e o PATCH condicional impedem que dois computadores peguem o mesmo trabalho.
- **Qualidade:**
  - A entrega final é sempre x265, em HLG, BT.2020 e 10 bits.
  - O NVENC só entra nos arquivos intermediários, e só se passar no teste automático.

## Atualização do Acer (automática)
O Acer roda o mesmo código do editor (VPS) e **se atualiza sozinho**: parado, ele confere de 5 em 5 minutos, e ao ser recusado pelo editor confere na hora.
O zip + `instalar_worker.ps1` só é necessário na instalação e quando muda uma biblioteca do sistema (o painel Sistemas avisa).

## 1. Supabase (uma vez)
SQL Editor > colar e rodar `bora_estudio/supabase/06_render_externo.sql`. Cria só a tabela nova, sem mexer nas existentes.

## 2. Token do worker (no VPS)
```
echo "BORA_WORKER_TOKEN=$(openssl rand -hex 32)" >> /opt/bora/bora.env; grep BORA_WORKER_TOKEN /opt/bora/bora.env
```
Guarde o valor para o Acer. **Ainda não** ligue o `BORA_RENDER_EXTERNO`.

## 3. Instalar no Acer (Windows)
**Atalho:** baixe `bora_estudio/worker/instalar_worker.ps1` e rode `powershell -ExecutionPolicy Bypass -File instalar_worker.ps1 -SoTeste`.
Ele confere Docker, CPU, RAM e placa, baixa o projeto, pede o token, monta o container e roda o teste dos codificadores. Sem `-SoTeste`, ele também liga o worker. Os passos manuais são estes:

1. **Docker Desktop:**
   - Instale o Docker Desktop (usa o WSL2) e o Git.
   - Com placa NVIDIA, atualize o driver da NVIDIA.
2. **Baixar o projeto:** no PowerShell:
   ```
   git clone -b claude/upbeat-tesla-qu1g6k https://github.com/lincolnfboraa/Claude.git bora
   cd bora\bora_estudio\worker
   copy worker.env.exemplo worker.env
   notepad worker.env
   ```
   No arquivo `worker.env`, cole o token e salve.
3. **Teste dos codificadores** (não pega trabalho nenhum):
   ```
   cd ..\..
   docker compose -f bora_estudio/worker/docker-compose.worker.yml run --rm bora-render python3 bora_estudio/worker/render_worker.py --teste
   ```
   Com placa NVIDIA, repita acrescentando `-f bora_estudio/worker/docker-compose.worker.gpu.yml` depois do primeiro `-f`. Na resposta:
   - `"nvenc": "validado..."`: o NVENC foi aprovado e será usado nos intermediários.
   - Qualquer outra mensagem: tudo em x265 (CPU).
4. **Ligar o worker** (com placa NVIDIA, acrescente o arquivo `gpu` como no passo anterior):
   ```
   docker compose -f bora_estudio/worker/docker-compose.worker.yml up -d --build
   docker logs -f bora-render
   ```
   O Acer precisa ficar ligado, sem hibernar, enquanto houver 4K na fila.

## 4. Ligar no VPS (só depois do teste real)
```
echo "BORA_RENDER_EXTERNO=1" >> /opt/bora/bora.env && docker restart bora-editor
```
Desligar (voltar ao 4K no VPS):
```
sed -i 's/^BORA_RENDER_EXTERNO=1/BORA_RENDER_EXTERNO=0/' /opt/bora/bora.env && docker restart bora-editor
```

## Ajustes opcionais (no bora.env do VPS)
- `BORA_WORKER_SILENCIO=900`: segundos sem sinal do Acer antes de devolver o trabalho pra fila.
- `BORA_MAX_TENTATIVAS=3`: número de falhas antes de virar erro no app.

## Acompanhar
- **No app:** o andamento do 4K aparece como hoje, com a etapa e a porcentagem vindas do Acer.
- **No Supabase:** a tabela `render_trabalhos` mostra worker, codificador, tentativas, etapas com tempo, duração e erro.
- **No Acer:** `docker logs -f bora-render`.
