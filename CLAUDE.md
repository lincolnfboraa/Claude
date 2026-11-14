# Bora Soluções Digitais | Instruções do repositório

## Reels da Dra. Fabiola Pedron (nefrologista)
Siga sempre o padrão aprovado em `fabiola_reels_energeticos/PADRAO_PRODUCAO.md`. Pontos inegociáveis:
- **Imagem fiel ao gravado:** entregar em HDR original do iPhone (HEVC 10 bits, HLG), sem filtro, cor, nitidez ou suavização.
  Não converter para SDR na entrega (`render_hdr.py`).
- Cortar pausas, vícios e erros de fala sem nunca inventar ou montar falas.
- Legenda minimal branca com sombra de ~35%, acima da interface do Reels, **sem pontos**.
- Nunca cortar pedaço de palavra (ex.: "diabetes" virando "diabé"): finais fracos como "s" precisam ficar; conferir re-transcrevendo.
- No máximo 3 ou 4 frases de destaque, com linhas coladas e a palavra principal em creme #C8B9A7.
- **Dinamismo:** variar o estilo dos destaques no mesmo vídeo (Poppins pop, serifa itálica creme Merriweather Black Italic, lettering letra a letra)
  e, de vez em quando (2 a 3 por vídeo), uma **palavra solta**: só a palavra-chave, grande, em serifa itálica creme, na posição dos letterings
  (não dentro da legenda).
- Título (aprovado no diabetes, "T1b"): sem caixa, degradê escuro suave atrás, na altura do peito. Três linhas coladas e com a MESMA largura:
  rótulo espaçado em Poppins Medium creme (ex.: DIA MUNDIAL DO DIABETES) + TEMA em Merriweather Black Italic creme (espaçado até a largura do rótulo)
  + pergunta curta em Poppins SemiBold branco. Sem filetes. Entrada suave (sobe 18 px + fade, em cascata).
- Primeiras versões e validações em 480p (480x854, `render.py ... 854`), de preferência por trechos curtos; qualidade cheia só na final aprovada.
- Roteiro e ganchos: seguir `fabiola_reels_energeticos/ANALISE_REFERENCIAS.md` e `GUIA_ROTEIRO_GRAVACAO.md`.
- **Entrega de vídeo:** validações (480p) vão como .mp4 normal no chat (`display: render`), pra reproduzir direto.
  Só a **versão final 4K** vai dentro de um .zip (zip -0), com `display: attach`, pra baixar no celular.
  Final leve pro celular: HEVC (libx265, crf 24, tag hvc1).
- Respostas em português, linguagem natural, sem travessões.
