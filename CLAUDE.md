# Bora Soluções Digitais | Instruções do repositório

## Reels da Dra. Fabiola Pedron (nefrologista)
Siga sempre o padrão aprovado em `fabiola_reels_energeticos/PADRAO_PRODUCAO.md`. Pontos inegociáveis:
- **Imagem fiel ao gravado:** entregar em HDR original do iPhone (HEVC 10 bits, HLG), sem filtro, cor, nitidez ou suavização.
  Não converter para SDR na entrega (`render_hdr.py`).
- Cortar pausas, vícios e erros de fala sem nunca inventar ou montar falas.
  Pausas entre frases ~0,2 s e dentro do trecho ~0,24 s; o começo e o fim de cada trecho são achados pelo som (não só pela transcrição), pra nunca comer palavra.
  Ajuste fino no bora.env: BORA_PAUSA_MIN, BORA_PAUSA_MANTEM, BORA_PAUSA_BORDA, BORA_BORDA_SOM=0 volta ao corte antigo.
- **Storytelling:** gancho, contexto (antes da prova), evidência e fechamento; briefing 'manter falas' SOMA ao contexto, não o substitui. Repetições marcadas com ⟲ na transcrição
  (a IA pula a primeira tentativa). Observação do editor no campo do gancho ('Gostei de...', 'tipo...') é ideia, nunca vai pra caixa; só título curto vai exato.
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
- **Efeitos sonoros (opcional por projeto, desligado por padrão):** whoosh nas trocas de história e pop no começo dos destaques, numa faixa separada (picos de -18 e -15 dBFS),
  somada DEPOIS do ganho da voz. A voz continua sem EQ nem compressor. Os sons vêm do Drive (Bora Claude/Biblioteca/SoundFX); trocar por BORA_SFX_WHOOSH e BORA_SFX_POP no bora.env.
- Respostas em português, linguagem natural, sem travessões.
- **Testes antes de subir:** ajustes de layout, visual ou texto do app sobem direto, sem teste. Teste completo do motor (testes_regras.py, teste_completo.py e, se mexer no Acer, teste_render_externo.py) só quando a mudança pode comprometer uma entrega: montagem do vídeo, imagem, áudio, 4K, fila ou envio de arquivos.
