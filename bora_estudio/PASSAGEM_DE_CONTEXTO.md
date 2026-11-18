# Bora Studio: passagem de contexto (atualizada em 18/11/2026)

Documento pra continuar o trabalho numa nova conversa ou projeto. Ler junto com `CLAUDE.md` (regras de edição e de trabalho),
`bora_estudio/ROADMAP.md` (próximas funcionalidades) e `bora_estudio/worker/GUIA_RENDER_EXTERNO.md` (Acer).

## Regras de trabalho com o Lincoln
- Português, linguagem natural, **sem travessões**. Economizar créditos e tokens.
- **Quando testar:** ajuste de layout, visual ou texto do app sobe direto. Teste completo só quando pode comprometer entrega
  (montagem, imagem, áudio, 4K, fila, envio): `testes_regras.py` (9 testes), `teste_completo.py`, e se mexer no Acer `teste_render_externo.py` (13 verificações).
- **Push no GitHub = atualização automática da VPS** (cron a cada 2 min, só com o editor livre). Antes de subir mudança de servidor, conferir no
  Supabase se não há vídeo em produção (`versoes?status=eq.editando`).
- Correções são globais (todos os clientes). Nunca dizer que fez algo que não fez. Segredos nunca no chat nem no repositório.
- Imagem sagrada: HDR HLG/BT.2020/10 bits do iPhone, nunca SDR, sem filtros. Legendas brancas **sem pontos**. Nunca cortar fim de palavra.
  Áudio fiel (só passa-alta 60 Hz e -14 LUFS com ganho fixo).
- Repositório: `lincolnfboraa/Claude`, branch `claude/upbeat-tesla-qu1g6k`.

## Arquitetura
- **App (PWA):** `bora_estudio/app/index.html` em `studio.borasolucoesdigitais.com`. Abas: Início, Clientes, +, Revisões, Padrão Bora.
- **Banco:** Supabase `gsychapfrpfjqmzbcpkk` (projetos, versoes, clientes, dna_versoes, regras_globais, render_trabalhos, ...; bucket `previas`).
- **VPS Peramix vmid3238** (206.183.129.41, 24 GB, 8 vCPU): container `bora-editor` (editor + vigia + IA). `/opt/bora/bora.env` tem as chaves.
  `/opt/bora/repo/bora_estudio/worker/.env` tem `BORA_MEM=18g`. Também: `BORA_RENDER_EXTERNO=1`, `BORA_WORKER_TOKEN`.
  Atenção: o balloon do Proxmox já reteve 17 GB uma vez; um desligar/ligar da VM resolveu. Disco: 200 GB, partição só com 100 GB (expandir com snapshot).
- **Acer (render externo):** Acer Nitro, i5-10300H 4c/8t, 16 GB, GTX 1650 (NVENC reprovado no teste de HLG/BT.2020, usa x265).
  Docker Desktop + container `bora-render` (`C:\bora\Claude-claude-upbeat-tesla-qu1g6k\bora_estudio\worker`). Liga sozinho com o Docker.
  Pra precisar de virtualização foi preciso: WSL, `VirtualMachinePlatform`, `bcdedit /set "{current}" hypervisorlaunchtype auto` e reinícios.
  Atualizar o código do Acer: baixar o zip do GitHub (comando em GUIA_RENDER_EXTERNO.md) e rodar `instalar_worker.ps1`.
- **Regra de render:** Acer ligado faz transcrição, prévia e 4K; IA (plano) sempre na VPS. Acer desligado: a VPS faz tudo
  (prévia cai pra VPS em 1 min; 4K pendente cai pra VPS em 10 min). Piloto do Acer: ~47 s de render por segundo de vídeo com card (3 a 4x a VPS).
- **Google Drive:** conta de serviço `bora-editor` (projeto Google Cloud "bora-studio", kinetic-anvil-515022-q9), só leitura, pasta "Bora Claude"
  compartilhada como Leitor. Chave em `/opt/bora/trabalho/google_sa.json`. O editor baixa os originais direto do Drive.

## Funcionalidades no ar
- **Novo projeto:** blocos **Locução** e **Complementos (B-roll)**, cada um com "Do celular" e "Do Google Drive", com miniaturas; dá pra misturar.
  Celular exige app aberto; Drive não.
- **B-roll em HDR:** vídeos de ambiente (bloco Complementos, ou sem fala) viram B-roll; a IA recebe 1 quadro de cada e encaixa durante a fala
  (1,5 a 4 s, fora do gancho e dos destaques); o motor sobrepõe em 10 bits sem conversão. **Ainda não testado com IA real** (Helenice é o teste).
- **4K só legendado** (zip com 1 vídeo). Previsão de tempo e quadro atual no app.
- **Descartar vídeo** (apaga projeto, versões, prévias e pasta; originais do Drive ficam).
- **Onde foi feito** (Acer ou VPS, tempo) em cada vídeo.
- **Painel Sistemas** (Padrão Bora): Editor, Supabase, Drive, IA, Saldo da IA, Acer, Fila do 4K, Notificações; servidor confere a cada 2 min e
  manda push quando algo cai, fica lento ou volta; faixa amarela na tela inicial. Última correção (231c4a9): rota quebrava por `import time` local.
- **Saldo da IA:** não existe endpoint de saldo na Anthropic; o app mostra gasto do mês (Usage and Cost Analytics API) e saldo estimado
  a partir da recarga registrada no app (botão "Registrar recarga da IA").
- App atualiza a cada 8 s com vídeo em produção e na hora ao voltar pro app. Push: prévia pronta, 4K pronto, erro, sistemas.

## Pendências
1. Confirmar o painel Sistemas verde no app depois da correção 231c4a9.
2. **Teste real da Helenice** (cliente Padrão Bora, falas em Locução, cenas em Complementos): validar escolha da IA no B-roll.
   Se faltar qualidade: medir movimento de câmera por segundo nos takes de ambiente e mandar 3 quadros por take (proposta pronta, não feita).
3. Chave de administrador da Anthropic (`ANTHROPIC_ADMIN_KEY` no bora.env) pra ver gasto e saldo da IA.
4. Expandir o disco da VPS pra 200 GB (com snapshot e sem vídeo rodando).
5. Repositório GitHub ainda público: tornar privado (o Acer baixa o zip público; ajustar se fechar).
6. Roadmap (`ROADMAP.md`): biblioteca de assets, efeitos sonoros e música automáticos, estilos de texto por cliente, capacidade em paralelo.
7. Slides complementares da Bora (8 páginas, PDF entregue) aguardando os dados de preenchimento (história, fotos, números, depoimentos, WhatsApp).
8. Edits via MCP: existe pra Mac; compatibilidade com o Acer não comprovada; não testado.
