# Análise dos brutos antes da seleção editorial

Branch de revisão: `claude/analise-brutos` (fora do ar; a VPS só puxa `claude/upbeat-tesla-qu1g6k`).
Liga com `BORA_ANALISE_BRUTOS=1` no `bora.env`. Desligado, o motor funciona exatamente como hoje.

## 1. Auditoria: o que o Claude recebe hoje (`plano.py`, `motor.py`)

| Entrada | Como vai | Observação |
|---|---|---|
| Transcrição | Texto numerado palavra a palavra, agrupado por arquivo e frase, com o **segundo de início de cada frase** | Não vai o tempo de cada palavra nem pausas, só o início da frase |
| Takes de fala | **Nenhuma imagem** | A escolha entre takes que repetem a mesma fala, o enquadramento (aberto/médio/fechado) e a qualidade da imagem são decididos **só pelo texto** |
| Takes de ambiente (B-roll) | Até 17/11: 1 quadro do meio. Desde `e4e7193`: folha com 6 a 8 quadros (com o segundo de cada) e tremor por segundo | Único ponto com análise visual |
| DNA global, DNA do cliente, briefing, plano anterior e feedbacks | Texto | |
| Prévia montada | **Não volta pra IA** | A validação é só técnica (resolução, HDR, duração, áudio, palavras inteiras). "Rosto livre e textos legíveis" fica como "precisa olhar na prévia" |

Conclusão: a seleção editorial é **predominantemente textual**. A imagem só entra no B-roll, e mesmo assim sem nota, sem registro de problemas e sem rastreio do porquê da escolha.

## 2. O que foi implementado (pra revisão)

`bora_estudio/worker/analise_brutos.py`:

1. **Varredura econômica, sem IA** (a cada 0,5 s, em 144x256 e 10 quadros/s):
   - **Tremor de câmera:** correlação de fase subpixel.
   - **Nitidez:** variância do laplaciano, relativa ao melhor trecho do take.
   - **Luz:** média e estouro.
   - **Áudio:** dB e clipagem.
2. **Candidatos:**
   - **Fala:** cada frase da transcrição vira um intervalo, com as palavras globais.
   - **Ambiente:** trechos firmes e nítidos de 1,5 a 6 s.
   - **Ambiente sem nada firme:** entra o take inteiro, marcado, pra IA saber que existe e é ruim.
3. **Detalhe temporal nas bordas:**
   - A 30 quadros/s, de 0,4 s antes a 0,6 s depois da entrada e da saída de cada candidato.
   - No ambiente, um tranco perto da borda move a borda.
   - Na fala, só registra o tranco, porque não pode cortar palavra.
4. **Avaliação visual pelo Claude:**
   - **O que vai:** uma folha por take, com 3 quadros por intervalo (entrada, meio e saída), as medições e a fala.
   - **O que volta, por intervalo:** descrição visual, problemas, função narrativa, nota de 0 a 10, se é utilizável e as incertezas.
5. **Catálogo** (`catalogo.json`, com cache; tempos sempre nos **arquivos originais**). Cada intervalo tem:
   - arquivo, início e fim;
   - descrição visual e fala correspondente;
   - problemas técnicos e visuais;
   - função narrativa, nota, se é utilizável e incertezas.
   - A justificativa da escolha vem do planejador.

`plano.py` (com o catálogo):
- Cada segmento precisa citar o `intervalo` e uma `justificativa`. Cada B-roll também cita o `intervalo`.
- `validar_catalogo` derruba o que não foi avaliado ou foi marcado "NÃO USAR", e registra em `_descartes`. O B-roll fica preso dentro do intervalo citado.
- Quando não há imagem adequada, a IA preenche `faltas` (momento, problema e proposta) em vez de escolher um trecho ruim. As faltas aparecem no resumo da versão, no app.

`motor.py`:
- Monta o catálogo antes do plano.
- Depois da prévia, `conferir_previa` faz duas coisas:
  - acha os cortes e mede o tremor fora deles;
  - manda pra IA os quadros logo antes e logo depois de cada corte.
- Os achados vão pro resumo e pro `original_meta.conferencia_vN`.

`avaliar_projeto.py`: validação contra um projeto revisado por nós (ver item 4).

## 3. Viabilidade, custo e tempo (estimativas, a confirmar na validação)

Projeto do tamanho da Helenice (31 takes, cerca de 10 min de bruto, uns 130 intervalos):

| Etapa | Onde | Tempo estimado | Custo estimado (Opus 5.5) |
|---|---|---|---|
| Varredura técnica | VPS | 2 a 3 min | 0 |
| Detalhe nas bordas (2 leituras de 1 s por intervalo) | VPS | 2 a 4 min | 0 |
| Avaliação visual (cerca de 22 folhas de 6 linhas, uns 50 mil tokens de entrada) | API | 1 a 2 min | US$ 0,50 a 0,70 |
| Planejador (catálogo em texto, sem imagens) | API | igual a hoje | +US$ 0,05 |
| Conferência da prévia | VPS + API | 1 min | US$ 0,05 a 0,10 |

- **Total:** cerca de 5 a 9 min e **US$ 0,60 a 0,90 a mais por projeto novo**.
- **Ajustes:** reaproveitam o catálogo (cache), então só a conferência roda de novo.
- **Pra baratear:** `BORA_MODELO_VISUAL=claude-sonnet-5-5` corta pela metade. Haiku 5.5 sai por uns centavos, mas precisa medir se mantém a qualidade.

**É possível?** Sim. Tudo roda com o que já existe (ffmpeg, numpy, a API do Claude com imagens). Os limites conhecidos:
- **O que a IA vê:** são quadros, não o vídeo. Movimento entre quadros vem da medição técnica, e o que ela não consegue ver vai pra `incertezas`.
- **Expressão da pessoa:** olhos fechados ou careta podem cair entre os quadros amostrados. Um olho piscando no meio de uma frase longa pode passar.
- **Tremor que não é deslocamento:** foco, exposição ou rotação mexem pouco no deslocamento medido. A nitidez pega parte disso, e a IA vê o resto nos quadros.
- **Ainda não testado com IA real:** os testes aqui usaram um cliente falso, porque a chave da IA fica só na VPS.

## 4. Validação com projeto real (rodar na VPS, sem vídeo em produção)

Gabarito: `fabiola_reels_energeticos/timeline.json` (Reels v7 aprovado), com 12 trechos (arquivo, entrada, saída, função e fala) nos tempos dos originais.

1. Copiar o código do branch de revisão pra pasta de trabalho, sem mexer no que está no ar:
   ```
   cd /opt/bora/trabalho && rm -rf revisao && mkdir revisao && git -C /opt/bora/repo fetch -q origin claude/analise-brutos && git -C /opt/bora/repo archive origin/claude/analise-brutos | tar -x -C revisao
   ```
2. Os originais (IMG_2595 a IMG_2598) precisam estar na pasta "Bora Claude" do Drive, porque o script baixa pelo `drive_id` do gabarito. A outra opção é copiar os arquivos pra `/opt/bora/trabalho/aval_energeticos/`.
3. Primeiro só a parte técnica (custo zero):
   ```
   docker exec -w /trabalho/revisao bora-editor python3 bora_estudio/worker/avaliar_projeto.py --pasta /trabalho/aval_energeticos --gabarito fabiola_reels_energeticos/timeline.json --sem-ia
   ```
4. Depois a validação completa, comparando com o sistema atual:
   ```
   docker exec -w /trabalho/revisao bora-editor python3 bora_estudio/worker/avaliar_projeto.py --pasta /trabalho/aval_energeticos --gabarito fabiola_reels_energeticos/timeline.json --cliente fabiola --comparar-atual
   ```
5. O resultado fica em `/opt/bora/trabalho/aval_energeticos/AVALIACAO.md`.

O que o relatório mede:
- **Acerto por trecho:** IoU de 0,5 ou mais entre o trecho escolhido e o do gabarito, com recall e precisão.
- **Erro de entrada e saída:** média, em segundos.
- **Take trocado:** mesma fala escolhida num take diferente do nosso.
- **Trechos do gabarito não escolhidos** e **trechos a mais** escolhidos pela IA.
- **Catálogo:** se ele rejeitou imagem que a gente usou, e se a função narrativa bate com a nossa.
- **Custo e tempo** de cada etapa, com e sem catálogo.

## 5. Antes de publicar

- [ ] Validar com o gabarito (item 4) e comparar com o sistema atual
- [ ] Rodar num projeto novo com `BORA_ANALISE_BRUTOS=1` e conferir o catálogo e as faltas no app
- [ ] Decidir o modelo da etapa visual (Opus, Sonnet ou Haiku) pelo custo e pela qualidade medidos
- [ ] Atualizar o Acer: ele usa `montagem.py` (o limite do B-roll dentro do intervalo)
- [ ] Juntar no branch principal (a VPS atualiza sozinha)
