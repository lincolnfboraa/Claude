# Padrão de produção | Reels Dra. Fabiola Pedron (Bora Soluções Digitais)

Aprovado em 12/11/2026 no Reels "Energéticos e rim". Projeto de referência: esta pasta.

## 1. Imagem: fidelidade ao que foi gravado (regra principal)
- **Entrega final sem tratamento de imagem.** Nada de filtro, correção de cor, nitidez, suavização ou efeito de pele.
- Os brutos são iPhone 4K HDR (HEVC, HLG, BT.2020, 10 bits, 29,97 fps). A final **mantém o HDR original**:
  HEVC 10 bits, HLG/BT.2020, 2160x3840, CRF 14, sem SAO e sem strong-intra-smoothing (`render_hdr.py`).
- **Não converter HDR para SDR na entrega.** A conversão (tonemap) achata as altas luzes da pele e parece "suavizar" o rosto.
  SDR só serve para previews de validação (720p).
- Únicas intervenções na imagem: cortes e enquadramentos (recorte do 4K original).
  - aberto: zoom 1,28, rosto a 30% da altura
  - médio: zoom 1,38, rosto a 28%
  - fechado: zoom 1,48, rosto a 24% (clímax e virada)

## 2. Áudio
- Voz original, sem música (a Bora coloca depois) e sem voz gerada.
- Redução de ruído leve, EQ suave, compressão leve e loudnorm -14 LUFS / -1,5 dBTP.

## 3. Edição de fala
- Transcrever tudo com tempos por palavra (faster-whisper medium). Em dúvida, alinhar com wav2vec2 PT
  (`jonatasgrosman/wav2vec2-large-xlsr-53-portuguese`, alinhamento CTC) e comparar transcrições alternativas pelo score.
- Cortar: pausas (silêncio acima de 0,25 s vira ~0,14 s; `apara_pausas.py`), vícios ("assim", "eles" repetido, "disso"),
  construções truncadas e números que ela mesma corrigiu.
- Cortar informação que se contradiz no vídeo (ex.: limite de 400 mg/dia × 300 mg por dose).
- Nunca inventar fala nem montar frase que ela não disse. Erro de concordância sem corte possível fica no áudio,
  é corrigido só na legenda, e a equipe é avisada.
- Deixar um respiro (~0,3 s) depois da pergunta de clímax.
- Validar sempre re-transcrevendo o áudio montado: nenhuma palavra cortada pela metade.
- Duração: o conteúdo manda (o aprovado ficou com 69 s). Sem enchimento.

## 4. Estrutura narrativa
Detalhada em `ANALISE_REFERENCIAS.md` (vídeos aprovados) e `GUIA_ROTEIRO_GRAVACAO.md` (para a médica gravar):
gancho (pergunta, identificação, cena ou diálogo) → promessa ("vou explicar") → analogia com objeto real → explicação curta
→ dado com número → experiência de consultório → ressalva responsável → fechamento com ação ou frase leve.
Manter a personalidade dela ("tá?", "menina!", "por favor"); cortar só hesitações e repetições.

## 5. Título (abertura, ~4,5 s)
- Fórmula dos aprovados: TEMA em caixa alta + complemento em pergunta/promessa. Preferir faixa na altura do peito com a cor
  do tema (vinho, marrom do café, azul); usar o topo só quando o peito/mesa tiver objeto de cena.
- Estilo dos posts da médica: caixa **azul-marinho #0F1C4A** com serifa (Playfair Display) em caixa alta e branco,
  mais uma caixinha **bege #C8B9A7** logo abaixo com itálico marinho (ex.: "ENTENDA COMO").
- Fica no topo quando a parte de baixo tem objetos de cena.

## 6. Legenda
- Padrão minimal do CapCut: **branca, sem cor de destaque**, Poppins SemiBold, sombra suave de ~35%, sem contorno.
- Embaixo, mas acima da faixa da interface do Reels: base do texto em até ~1500 px (em 1080x1920).
- Blocos curtos (2 a 5 palavras), sincronizados com a fala. Ortografia corrigida.

## 7. Frases de destaque
- **No máximo 3 ou 4 por vídeo**, nos pontos-chave (gancho, clímax, virada).
- Composição de tamanhos misturados (linha pequena + palavra gigante + complemento),
  **linhas coladas** umas nas outras (empilhamento automático em `make_subs.py`) e uma combinação diferente em cada uma.
- Palavra principal em **creme #C8B9A7** (paleta da médica); demais em branco. Sombra forte e suave.
- Fonte: Poppins (Black, ExtraBold, Bold, SemiBold).
- Posição: na altura da legenda, um pouco acima. A do gancho pode ficar no peito, desde que não cubra o objeto que ela mostra.
- Enquanto o destaque está na tela, a legenda comum daquele trecho some.

## 8. O que não usar
- Bloco com o nome da médica.
- Azul vivo ou azul-marinho nas palavras em destaque.
- Cards demais. Cards informativos só quando explicam algo (ex.: nome difícil de substância), em marinho #0F1C4A.
- Transições chamativas (light leak / flash) sem teste aprovado.

## 9. Fluxo de trabalho
1. Baixar os brutos do Drive (links públicos via `drive.usercontent.google.com`), rodar ffprobe e transcrever.
2. Montar `timeline.json` (segmentos, função narrativa, cortes com motivo).
3. `apara_pausas.py` → `render.py` (preview SDR 720p) → re-transcrever → `make_subs.py`.
4. Validar em **480p** (`render.py <pasta> <saida> <ass> 854`), de preferência por **trechos curtos** (não mandar o vídeo inteiro a cada ajuste).
5. Final: `render_hdr.py` com os .MOV originais. Entregar também o `.srt` e, se pedido, a versão com legendas.
6. Antes de entregar: conferir duração de vídeo × áudio (sincronia) e quadros ao longo do vídeo.

## Paleta da Dra. Fabiola (destaques do perfil)
| Cor | Hex |
|---|---|
| Azul-marinho | #0F1C4A |
| Bege / creme | #C8B9A7 |
| Cinza-azulado | #ACB3BC |
| Branco | #FFFFFF |
