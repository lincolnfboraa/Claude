# Bora Soluções Digitais | Instruções do repositório

## Reels da Dra. Fabiola Pedron (nefrologista)
Siga sempre o padrão aprovado em `fabiola_reels_energeticos/PADRAO_PRODUCAO.md`. Pontos inegociáveis:
- **Imagem fiel ao gravado:** entregar em HDR original do iPhone (HEVC 10 bits, HLG), sem filtro, cor, nitidez ou suavização.
  Não converter para SDR na entrega (`render_hdr.py`).
- Cortar pausas, vícios e erros de fala sem nunca inventar ou montar falas.
  Pausas entre frases ~0,2 s e dentro do trecho ~0,24 s; o começo e o fim de cada trecho são achados pelo som (não só pela transcrição), pra nunca comer palavra.
  Ajuste fino no bora.env: BORA_PAUSA_MIN, BORA_PAUSA_MANTEM, BORA_PAUSA_BORDA, BORA_BORDA_SOM=0 volta ao corte antigo.
  As palavras são protegidas pelo SOM real (140 ms depois e 50 ms antes de cada quadro com voz), não pelo fim que o Whisper marca: ele costuma esticar a palavra por cima da pausa seguinte.
  BORA_PROTEGE_SOM=0 volta à proteção pelo tempo do Whisper.
- **Storytelling:** gancho, contexto (antes da prova), evidência e fechamento; briefing 'manter falas' SOMA ao contexto, não o substitui. Repetições marcadas com ⟲ na transcrição
  (a IA pula a primeira tentativa). Observação do editor no campo do gancho ('Gostei de...', 'tipo...') é ideia, nunca vai pra caixa; só título curto vai exato.
- **Termos sensíveis (nomes comerciais de remédios, por cliente em vocabulario.json):** o áudio fica como foi falado, mas na TELA (legenda, destaques, título) o nome vira termo genérico
  com o artigo concordando ('o Mounjaro e o Ozempic' = 'as canetas'). A IA é avisada pra não destacar produto nem usar tom de venda; a verificação da prévia acusa se algum nome sobrou na tela.
- **Capa final (CRM e RQE):** imagem anexada no ajuste ('Anexar capa final'), colada no fim do vídeo por 3,5 s (BORA_CAPA_FINAL_S). Cartão horizontal (proporção > 2:1) vira o cartão animado 9:16 (cartao_animado.py: logo se revela, nome sobe, linha cresce, redes em cascata, textos recortados da própria arte); imagem em pé entra com fade, em HDR com a mesma conversão de cor dos textos,
  áudio estendido em silêncio. Vale pras versões seguintes e pro 4K.
- **Zonas do Reels (1080x1920):** topo 220 px, base 450 px (y 1470), laterais 35 px. A legenda termina em y 1470 e os destaques em y 1450 (FUNDO_DESTAQUE 1390); margens laterais medidas:
  legenda 174 px, destaque 102 px.
- **Enquadramento automático:** o editor mede os rostos nos quadros-chave de cada take de fala usado (enquadramento.py, OpenCV, só no VPS) e grava no plano (_rostos).
  No render, o zoom do trecho cai até caber todo mundo com folga dos lados e respiro de 12% acima da cabeça (BORA_RESPIRO), e o recorte centra no grupo; sem rosto, o recorte de sempre.
  BORA_ENQUADRAMENTO=0 desliga. A IA também vê uma folha de quadros de cada take de fala e evita trecho com gente entrando, produto sendo trocado ou câmera mexendo.
- **Aprendizados dos ajustes** ficam no DNA Global (regras_globais.aprendizados, no Supabase) e valem pra todos os clientes: a IA lê em todo plano.
- **Notas (assertividade):** cada prévia ganha uma nota da IA de 0 a 10 (avaliacao.py: quadros a cada 2 s + falas + pedido do editor; critérios gancho, storytelling, cortes, enquadramento e complemento, cada um com o motivo; contexto do cliente e do DNA)
  em original_meta.nota_ia_vN. O editor dá a dele no app (nota_editor_vN); o app mostra a diferença e a média.
- **Revisão interna antes de entregar:** a prévia só chega ao editor com nota da IA >= 7,5 e nenhum critério abaixo de 6 (BORA_NOTA_MIN). Abaixo disso o plano é refeito com os problemas
  apontados e a prévia renderizada de novo, até 2 vezes (BORA_REVISOES); entrega a melhor rodada (plano e vídeo dela). Pessoa cortada na borda: o plano usa o quadro 'total' (sem zoom).
  O que o enquadramento mediu fica em original_meta.enquadramento_vN (quadros lidos, com rosto e o erro, se houver).
- **Vocabulário por cliente** (vocabulario.json ou campo 'vocabulario' do DNA): termos entram como dica pro Whisper e grafias erradas conhecidas são corrigidas (Mounjaro, Ozempic...).
- Legenda minimal branca com sombra de ~35%, acima da interface do Reels, **sem pontos**.
- Nunca cortar pedaço de palavra (ex.: "diabetes" virando "diabé"): finais fracos como "s" precisam ficar; conferir re-transcrevendo.
- No máximo 3 ou 4 frases de destaque, com linhas coladas e a palavra principal em creme #C8B9A7.
- **Dinamismo:** variar o estilo dos destaques no mesmo vídeo (Poppins pop, serifa itálica creme Merriweather Black Italic, lettering letra a letra)
  e, de vez em quando (2 a 3 por vídeo), uma **palavra solta**: só a palavra-chave, grande, em serifa itálica creme, na posição dos letterings
  (não dentro da legenda).
- Título (aprovado no diabetes, "T1b"): sem caixa e sem degradê ou bloco escuro atrás (regra geral: sombra só nas letras), na altura do peito. Três linhas coladas e com a MESMA largura:
  rótulo espaçado em Poppins Medium creme (ex.: DIA MUNDIAL DO DIABETES) + TEMA em Merriweather Black Italic creme (espaçado até a largura do rótulo)
  + pergunta curta em Poppins SemiBold branco. Sem filetes. Entrada suave (sobe 18 px + fade, em cascata).
- **NUNCA converter HDR para SDR, nem nos previews.** Todo render (inclusive 480p) sai do .MOV original em HDR (HLG/BT.2020/10 bits):
  `render_hdr.py <pasta> base.mp4 <altura>` + `render_hdr_texto.py base.mp4 legendas.ass saida.mp4` (textos convertidos para HLG
  com branco forte, ~91% do sinal, pra não parecer cinza; imagem intocada; nada de "cara de suavizado"). `render.py` com intermediários SDR NÃO deve mais ser usado para entregas.
- Primeiras versões e validações em 480p (altura 854), de preferência por trechos curtos; qualidade cheia só na final aprovada.
- Roteiro e ganchos: seguir `fabiola_reels_energeticos/ANALISE_REFERENCIAS.md` e `GUIA_ROTEIRO_GRAVACAO.md`.
- **Entrega de vídeo:** validações (480p) vão como .mp4 normal no chat (`display: render`), pra reproduzir direto.
  Só a **versão final 4K** vai dentro de um .zip (zip -0), com `display: attach`, pra baixar no celular.
  Final 4K: HEVC (libx265, tag hvc1) com a qualidade escolhida na aprovação no app: leve (crf 24, ~4 Mbps), alta (crf 16, padrão) ou máxima (crf 10). Trechos, B-roll e cards intermediários sobem junto (crf 14, 11 e 8).
  O crf 24 em 4K era fraco demais (3,9 Mbps, perdia detalhe e manchava os degradês); BORA_Q4K no bora.env muda o padrão.
- **Áudio fiel ao gravado** (microfone Hollyland já cancela ruído): sem redução de ruído, EQ ou compressor; só passa-alta 60 Hz e volume em -14 LUFS com ganho fixo (limitador só em picos).
- **Acer (render externo) se atualiza sozinho:** ele roda o MESMO código do editor (VPS), baixa o pacote em /worker/codigo (1,8 MB), confere hash, caminhos e sintaxe e só então troca a pasta;
  qualquer falha mantém o código antigo. Só o editor (VPS) é atualizado pelo cron do GitHub; o Acer acompanha em até 5 min (ou na hora, ao ser recusado).
  Só biblioteca do sistema nova pede reinstalar pelo zip: sobe BORA_IMAGEM no Dockerfile e IMAGEM_MIN no servidor.py. BORA_AUTOATUALIZAR=0 desliga.
- **Efeitos sonoros (opcional por projeto, desligado por padrão):** whoosh nas trocas de história e pop no começo dos destaques, numa faixa separada (picos de -18 e -15 dBFS),
  somada DEPOIS do ganho da voz. A voz continua sem EQ nem compressor. Os sons vêm do Drive (Bora Claude/Biblioteca/SoundFX); trocar por BORA_SFX_WHOOSH e BORA_SFX_POP no bora.env.
- Respostas em português, linguagem natural, sem travessões.
- **Testes antes de subir:** ajustes de layout, visual ou texto do app sobem direto, sem teste. Teste completo do motor (testes_regras.py, teste_completo.py e, se mexer no Acer, teste_render_externo.py) só quando a mudança pode comprometer uma entrega: montagem do vídeo, imagem, áudio, 4K, fila ou envio de arquivos.
