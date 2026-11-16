# Bora Studio: passagem de contexto (16/11/2026)

Documento para continuar o trabalho numa nova conversa. Leia junto com `CLAUDE.md` (regras de edição) e `bora_estudio/worker/GUIA_INSTALACAO.md`.

## Regras de trabalho com o Lincoln
- Responder em português, linguagem natural, **sem travessões**. Economizar créditos e tokens.
- **Nunca subir código sem testar:** rodar `bora_estudio/worker/testes_regras.py` (9 testes) e `teste_completo.py` antes de cada push de motor.
- **Correções são globais** (todos os clientes), nunca só para um vídeo.
- A IA nunca diz que fez algo que não fez. Ao mandar vídeo de teste feito com outro material, avisar claramente.
- Segredos nunca no chat nem no repositório (chaves ficam em `/opt/bora/bora.env` na VPS e no formulário de credenciais).
- **Push no GitHub = atualização automática da VPS** (cron a cada 2 min, só quando o editor está livre). Quando o Lincoln pedir para não mexer na VPS, segurar o push e explicar.
- Imagem sagrada: HDR HLG / BT.2020 / 10 bits do iPhone, nunca SDR (nem em prévia), sem filtros nem suavização. Legendas brancas **sem pontos**. Nunca cortar fim de palavra. Áudio fiel (só passa-alta 60 Hz e -14 LUFS com ganho fixo e limitador só em picos).

## Arquitetura atual
- **App (PWA):** `bora_estudio/app/index.html`, servido por nginx em `studio.borasolucoesdigitais.com`. Abas: Início, Clientes, +, Revisões, Padrão Bora. Notificações push (manifest.json + sw.js).
- **Banco:** Supabase `gsychapfrpfjqmzbcpkk` (tabelas equipe, regras_globais, clientes, dna_versoes, dna_ativo, projetos, versoes, sugestoes_dna; bucket privado `previas`).
- **Editor:** container Docker `bora-editor` na VPS Peramix vmid3238 (206.183.129.41), porta 8787 só em 127.0.0.1, exposto por nginx em `editor.borasolucoesdigitais.com`.
  - `servidor.py`: vigia o Supabase a cada 10 s, fila com até 2 trabalhos, uploads, link do 4K, push.
  - `motor.py`: transcreve (faster-whisper), IA monta o plano (`plano.py`, Claude via SDK anthropic), monta a partir dos originais (`montagem.py`), cards (`insercoes.py`), textos (`textos.py` + `hdr_texto.py`), verificação (`validacao.py`), prévia 480p e final 4K (.zip com legendado, sem legenda e .srt).
- **Atualização automática:** `/opt/bora/repo/bora_estudio/worker/auto_atualizar.sh` no cron. Log em `/var/log/bora-atualizacao.log`. Se um trabalho fica parado (30 min na prévia, 2 h no 4K), atualiza assim mesmo.

## O problema de 16/11 e o diagnóstico
- O 4K da **IMG_2575 v5** (Fabiola Pedron, cards Mounjaro, Ozempic, Tirzepatida, Semaglutida) travou várias vezes.
- **Causa comprovada:** OOM. A Peramix entrega 24 GB à VM (`lsmem`: 24G online), mas o **balloon do Proxmox retém ~17,2 GB** (`/proc/vmstat`: balloon_inflate 4501248, balloon_deflate 0). O Ubuntu só usa **6,3 GB**, sem swap. Cada ffmpeg 4K usava ~3,2 GB; o `hdr_texto` em 4K usava 5,3 GB e rodava a 0,65 quadro/s.
- **Peramix:** diz que 24 GB, 8 vCPU e 200 GB estão atribuídos, e que **não permite 100% de CPU contínuo**. Foi enviada mensagem pedindo para desativar o ballooning ou fixar a memória mínima em 24 GB (aguardando resposta).
- **Disco:** 200 GB no disco, partição com só 100 GB (GPT pede ajuste). Ainda há 39 GB livres. Expandir depois, com snapshot e sem vídeo rodando (`growpart` + `resize2fs`).

## O que foi feito (commits até 5b9fe0d, já no GitHub)
- Um render 4K por vez no servidor inteiro (`BORA_4K_SIMULTANEOS`, padrão 1). Prévias continuam em paralelo.
- `hdr_texto` só calcula a área com texto ou arte: resultado **idêntico pixel a pixel** (MD5 igual), 4K de 136 s para 64 s e de 5,3 GB para 4,2 GB. Processo filho morto agora vira erro (antes podia sair vídeo cortado).
- Falta de memória registrada (código de saída, pico de memória, trecho). Depois de 1 nova tentativa para com "Erro: memória insuficiente..." e **não repete sozinho**, nem ao reiniciar. Botão **Tentar de novo** no app.
- Trechos 4K já prontos são reaproveitados na retomada (`_trechos_<altura>`).
- Modelo do Whisper sai da memória antes do render.
- Docker reversível: `mem_limit ${BORA_MEM:-5500m}`, `cpus ${BORA_CPUS:-6}` (75%, termos da Peramix). Com a RAM liberada: criar `/opt/bora/repo/bora_estudio/worker/.env` com `BORA_MEM=18g` e `BORA_4K_SIMULTANEOS=2`.
- Intermediários dos trechos em x265 veryfast crf 14 (entrega final continua medium crf 24, HLG/BT.2020/10 bits). Se o Lincoln quiser garantia total, voltar intermediários para medium.

## Passos pendentes agora (na VPS, um de cada vez)
1. Swap de 4 GB: `fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab && free -h`
2. Parar o processo antigo da v5: `docker restart bora-editor`
3. Após ~3 min conferir: `cd /opt/bora/repo && git log -1 --format='%h %s' && docker inspect bora-editor --format 'mem={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}}'` (esperado 5b9fe0d ou mais novo, mem=5767168000, cpus=6000000000)
4. No app, aprovar a v5 da IMG_2575 de novo (o projeto foi colocado em "revisão" no banco para cancelar o 4K travado). Estimativa: 40 min a 1 h.

## Próximo projeto: render externo
Ideia aprovada em princípio: app, Supabase e IA continuam na Peramix; o render pesado vai para outra máquina.
- O editor já é um container que busca trabalho no Supabase, então um segundo editor é simples. Falta: trava no Supabase para dois editores não pegarem o mesmo trabalho, download seguro dos originais da VPS e devolução do resultado.
- Opção 1 (teste sem custo): o PC Windows do Lincoln (Docker Desktop). Pedir print do Gerenciador de Tarefas > Desempenho (CPU, Memória e GPU). Processador forte importa mais que GPU.
- Opção 2: servidor com **CPU dedicada** (Hetzner AX/CCX, DigitalOcean ou Vultr CPU-Optimized; Vultr tem São Paulo). Pesquisar preços atuais antes de recomendar.
- Descartados: prévia em H.264 (iPhone não toca H.264 10 bits HDR, viraria SDR), Shotstack/Creatomate (não preservam HDR HLG), HostGator (mesmo problema de CPU compartilhada). NVENC ajuda só na codificação.
- Fazer prova de conceito comparando com o render atual, sem desligar o editor da VPS.

## Outras pendências
- Testar notificações no iPhone (Padrão Bora > Ativar notificações).
- Estilos de texto por cliente (The House, Up Studio, Agropec...) antes de editar outros clientes.
- Botão para remover anexos antigos (IMG_2575 acumula 9).
- Confirmar os DNAs provisórios dos 5 clientes analisados.
- Deixar o repositório GitHub privado.
