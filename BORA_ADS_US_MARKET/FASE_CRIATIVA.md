# BORA ADS | US MARKET
## Fase criativa: Digital Catalog Campaign (piloto 38s)

Status: **aguardando aprovação**. Nada foi editado em Remotion ainda.

---

## 0. Inspeção dos originais (passos 1 a 4)

| Arquivo | Specs | O que tem de fato |
|---|---|---|
| `02_PRODUCT_RECORDINGS/papelaria_catalog_raw_14s.mp4` | 1320x2868, 60fps, 14,7s, sem áudio útil | Catálogo **Papelaria** (exemplopapelaria.netlify.app), não o Ferrett's |
| `00_REFERENCES/ref_opening_logo_cuts.mp4` | 1320x2868, 4,3s | Reel do Instagram de marca de terceiros (logo aplicado em crachá, jaqueta, fachada, capacete). **Só referência de ritmo**, não pode entrar no vídeo |
| `02_PRODUCT_RECORDINGS/ferretts_catalog_screenshot.png` | print estático | Topo do Ferrett's: logo, "Mais Pedidos", busca, aviso de 20 unidades, categorias |
| `01_BRAND_ASSETS/bora_logo_*.png` | 2000px | Logo Bora fundo navy e transparente |

### Mapa da gravação Papelaria (timecodes aproximados)

| Tempo | Cena | Uso no comercial |
|---|---|---|
| 0:00–0:01 | Hero "Encontre tudo antes de sair de casa" + busca | Reveal (Cena 03) |
| 0:01–0:03 | Mais buscados + Destaques da semana com preços | Discover (Cena 04) |
| 0:03–0:06 | Categorias, "Material escolar" expande com produtos, preço e estoque | **Melhor trecho de prova funcional** (Cena 04) |
| 0:06–0:09 | Rolagem de categorias + "Por que comprar conosco" | B-roll de interface, opcional |
| 0:09–0:12 | "Tem lista escolar?" + toque no campo, teclado abre | Cena 05 parcial |
| 0:12–0:13,5 | Rodapé com botões WhatsApp / Como chegar | Final da Cena 05 |
| 0:13,5–fim | Central de Controle do iOS | **Cortar** |

### Problemas encontrados

1. **Não existe gravação do fluxo de pedido** (selecionar produto, quantidade, resumo, envio ao WhatsApp). A Cena 05 é o coração do vídeo e hoje não tem material. O formulário de lista escolar não substitui isso.
2. **Não existe gravação do Ferrett's**, só um print. O storyboard original cita o Ferrett's na Cena 03.
3. **Interface em português e preços em R$** para um anúncio americano. Precisa decidir (ver Aprovações).
4. A gravação tem barra do Safari, selo "Powered by Netlify", status bar com operadora e indicador vermelho de gravação. Tudo isso some com crop + substituição de status bar no mockup.
5. Rodapé da Papelaria diz "Protótipo de demonstração". Bom para compliance: mockups conceituais ficam claramente ilustrativos.

---

## 1. Moodboard

Arquivos em `00_REFERENCES/`.

| # | Referência | O que levar | O que **não** levar |
|---|---|---|---|
| M1 | Macro de trufas (`ref_macro_truffles.jpg`) | Luz quente lateral, textura de cacau, fundo escuro, profundidade de campo curta | Folha de ouro exagerada se o produto real não tiver |
| M2 | Celular na padaria (`ref_phone_in_store.jpg`) | Contexto real, tela legível, loja desfocada atrás | A interface "LDV" da foto, a tela vai ser substituída |
| M3 | Mockups dark com laranja (`ref_dark_ui_mockups.jpg`) | Dois aparelhos em leve perspectiva, sombra suave, laranja como acento | Layout e conteúdo do app de terceiros |
| M4 | Grid de pontos com seleção (`ref_dotgrid_frame.jpg`) | Linguagem "bounding box" laranja com handles, grid de pontos no navy. Vira a assinatura gráfica da Bora | Texto e marca Entersekt |
| M5 | Reel de cortes com logo (`ref_opening_logo_cuts.mp4`) | Ritmo: 1 corte a cada ~0,5s, mesma posição central do símbolo em todos os takes | Qualquer frame do vídeo |

**Assinatura visual proposta:** grid de pontos navy + caixa de seleção laranja com handles. Ela aparece na abertura, enquadra produtos e preços no meio do vídeo e emoldura o CTA. É simples de fazer em Remotion e cria identidade reconhecível em todas as variações de segmento.

---

## 2. Shot list de B-roll

Prioridade: **P1** indispensável para o piloto, **P2** melhora muito, **P3** desejável.

| ID | Take | Duração útil | Cena | Prioridade | Origem sugerida |
|---|---|---|---|---|---|
| B01 | Macro de brigadeiro/trufa sendo partida, slow motion | 1s | 01 | P1 | Filmagem própria no Ferrett's (ideal) ou Artgrid / Filmsupply |
| B02 | Mão posicionando doce em forminha, câmera fixa top-down | 1s | 01 | P1 | Filmagem própria |
| B03 | Mão segurando celular com tela verde/neutra, fundo de confeitaria desfocado | 2s | 01, 03 | P1 | Filmagem própria (fácil) ou Storyblocks |
| B04 | Chocolate derretido sendo mexido | 1s | 01 | P2 | Artgrid / Motion Array |
| B05 | Vitrine de doces com rack focus | 1,5s | 04 ou 06 | P2 | Filmagem própria |
| B06 | Caixa de doces sendo fechada com fita | 1s | 05 | P2 | Filmagem própria |
| B07 | Comerciante recebendo notificação no celular no balcão | 1,5s | 05 | P2 | Filmagem própria |
| B08 | Interior de papelaria independente, prateleiras coloridas | 1s | 06 | P3 | Pexels / Mixkit (checar licença) |
| B09 | Balcão de loja especializada (flores, café, etc.) | 1s | 06 | P3 | Pexels / Envato |

**Recomendação:** uma diária curta (2 a 3 horas) no Ferrett's resolve B01, B02, B03, B05, B06 e B07 com produto real, coerente com o catálogo e sem custo de licença. Para cada take licenciado, registrar em `03_BROLL_LICENSED/LICENSES.md`: fonte, ID do clip, tipo de licença, se permite uso em anúncio pago, se exige atribuição.

### Gravações de tela que faltam (P1)

| ID | Gravação | Observação |
|---|---|---|
| R01 | Ferrett's: abrir, rolar "Mais Pedidos", buscar "strawberry" | Dedo lento, pausas de 1s entre ações |
| R02 | Ferrett's: escolher sabor, ajustar quantidade (20+), adicionar | É a prova funcional principal |
| R03 | Ferrett's: abrir resumo do pedido e tocar em enviar | Parar **antes** de abrir o WhatsApp real, a transição é feita na pós |
| R04 | Mesmo fluxo da Papelaria, se for usada na Cena 06 | Opcional |

Configuração de gravação: modo não perturbe ligado, bateria cheia, sem operadora visível se possível, rolar devagar, parar a gravação pelo atalho antes de abrir a Central de Controle.

---

## 3. Storyboard com timecodes

Formato master: **9:16, 1080x1920, 30fps** (Reels / TikTok / Shorts). Versões 1:1 e 4:5 derivadas depois.

| Cena | Tempo | Visual | Texto / Locução | Fonte do material |
|---|---|---|---|---|
| 01 Opening | 0,0–3,0 | A macro chocolate (0,4s) > B mão com doce (0,4s) > C celular com catálogo (0,5s) > D cards de produto em grid (0,6s) > E tela navy, caixa laranja se desenha (0,5s) > F símbolo Bora (0,3s) > G corte seco | **Sem locução.** Só música e impactos | B01, B02, B03, gravação, logo |
| 02 Problem | 3,0–7,0 | Mensagens em cascata num chat ilustrativo: "How much is this?", "Do you have a menu?", "What flavors are available?" Acumulam, leve shake, swipe para a direita | VO: "Your customers shouldn't have to DM you just to see your products." | Motion puro (chat genérico, sem marca de app real) |
| 03 Reveal | 7,0–11,0 | Mockup de celular entra no navy com grid de pontos, push-in, máscara revela o catálogo | VO: "Give them a better way to shop." | Ferrett's R01 (ou Papelaria 0:00–0:01 provisória) |
| 04 Discover | 11,0–19,0 | Rolagem real: destaques, categorias, uma categoria expande. Caixa laranja enquadra um preço. Card de produto sai da tela em parallax e volta | VO: "One link. Your products, prices, and categories, all in one place." | Ferrett's R01 ou Papelaria 0:01–0:06 |
| 05 Build the order | 19,0–27,0 | Seleção > quantidade > resumo > zoom no botão > match cut para notificação de pedido chegando no celular do comerciante (B07) | VO: "They browse, build their order, and send it straight to you." | **Ferrett's R02 + R03 (não existe ainda)** |
| 06 Many businesses | 27,0–33,0 | Um celular vira três: confeitaria, papelaria, loja especializada. Troca de cor por match cut | VO: "Built around your brand. Made for your customers." | Ferrett's, Papelaria, 1 mockup conceitual a aprovar |
| 07 Conversion | 33,0–38,0 | Interface recolhe num card, logo Bora entra por reveal, CTA | Headline: "Get your digital catalog." Sub: "Made for your business." VO: "Ready for your own digital catalog? Let's build it." | Logo, mockup, URL a definir |

**Regra da abertura:** o símbolo Bora fica no máximo 0,3s na tela em 01-F. Nada de vinheta. Em 3,0s exatos a primeira palavra da locução entra junto do primeiro balão de mensagem. Esse bloco de 0 a 3s vira um componente reutilizável (`<BoraOpening segment="bakery" />`) que só troca os takes A, B e D por segmento.

---

## 4. Mapa de transições

Do repertório de 8, o piloto usa 5. As outras ficam para variações.

| Onde | Transição | Como funciona | Por que essa |
|---|---|---|---|
| 01 C > D | **T07 Product Grid** | Tela do celular explode em grid de cards de produto | Mostra variedade em meio segundo |
| 01 F > 02 | **T05 Typographic Cut** (curto) | Corte seco para o primeiro balão "How much is this?" | Gancho imediato, sem respiro |
| 02 > 03 | **T03 Swipe World** | Swipe empurra o chat para fora e traz o navy com o celular | Problema sai literalmente da tela |
| 03 > 04 | **T02 Screen Portal** | Câmera entra na tela, mockup some, ficamos dentro da interface | Dá protagonismo à gravação real |
| 05 > B07 | **T01 Product Match** (variação) | Botão de enviar vira a notificação no celular do comerciante | Fecha a jornada cliente > lojista |
| 05 > 06 | **T08 Multi-Device** | Celular se duplica em três | Argumento de escala |
| 06 > 07 | **T06 Brand Reveal** | Três telas se recolhem num card, card vira a caixa laranja, caixa revela o logo | Fecha com a assinatura visual |

Reservadas para variações: T04 Card Expansion.

---

## 5. Mapa de sound design

| Tempo | Camada | Som | Volume relativo |
|---|---|---|---|
| 0,0 | Impacto | Hit grave curto no primeiro frame | Alto |
| 0,0–3,0 | Ritmo | Cliques secos sincronizados com cada corte (6 cortes) | Médio |
| 2,5 | Riser | Whoosh curto subindo | Médio |
| 2,7 | Marca | Bass hit no símbolo Bora (protótipo de logo sonoro) | Alto |
| 3,0–7,0 | Tensão | 3 notificações discretas, uma por balão, pitch subindo | Baixo |
| 6,6 | Transição | Swipe | Médio |
| 7,0–11,0 | Reveal | Whoosh ascendente + "tick" de UI no reveal + música resolve em acorde maior | Médio |
| 11,0–19,0 | UI | Microcliques nos toques reais, swish na rolagem | Baixo |
| 19,0–27,0 | Confirmação | Som de seleção, "pop" na quantidade, confirmação suave no envio | Baixo/Médio |
| 27,0–33,0 | Escala | 3 swipes no beat | Médio |
| 33,0–38,0 | Fecho | Impacto sutil no logo + resolução da trilha | Médio |

Regras: locução em -3 dB a -6 dB acima de tudo, ducking automático na música, nenhum som de confirmação em ação que não aparece na tela, master final em -14 LUFS (padrão de plataformas sociais).

---

## 6. Lista de assets

### Já temos
- [x] Logo Bora (fundo navy e transparente)
- [x] Paleta: Navy #072740, Orange #FF5E16, Beige #F2EADF, Deep Navy #0C1522
- [x] Gravação Papelaria (14,7s, uso parcial)
- [x] Print do Ferrett's
- [x] Referências de moodboard

### Pendentes
- [ ] Logo Bora em SVG (o PNG serve, mas o SVG permite animar o símbolo e os arcos separadamente)
- [ ] Gravações R01, R02, R03 do Ferrett's
- [ ] B-roll P1: B01, B02, B03
- [ ] Mockup de iPhone em PNG/3D com licença comercial
- [ ] Trilha musical licenciada (eletrônica minimal, 100 a 115 BPM, build claro em ~7s e ~27s)
- [ ] Pack de SFX licenciado (cliques, whooshes, hits, notificações)
- [ ] Locução em inglês americano (voz natural, 30 a 40 anos, tom confiante e próximo)
- [ ] Fonte: Inter ou Plus Jakarta Sans (ambas livres, Google Fonts)
- [ ] URL de destino do CTA para o público americano

---

## 7. Precisa de aprovação

1. **Idioma do catálogo na tela.** Opções: (a) gravar uma versão em inglês com preços em US$ (recomendado, é o que vende para americano); (b) manter em português e tratar como "case real", com legenda; (c) mostrar a interface de longe, sem texto legível. Minha escolha: **(a)**.
2. **Catálogo principal.** Ferrett's como protagonista (doces casam com o B-roll e com a abertura) e Papelaria só na Cena 06. Confirmar.
3. **Fluxo de pedido existe no Ferrett's?** Preciso confirmar se o catálogo tem quantidade + resumo + envio ao WhatsApp para gravar R02 e R03.
4. **Mockup conceitual do 3º segmento** na Cena 06 (sugestão: floricultura ou café). Fica marcado como ilustrativo.
5. **Destino do CTA:** site, landing page em inglês ou link de WhatsApp Business com número que atenda em inglês.
6. **Assinatura visual** (grid de pontos + caixa laranja com handles). Aprovar antes de virar sistema.
7. **Diária de filmagem no Ferrett's** vs. B-roll 100% licenciado.
8. **Uso da marca Ferrett's** num anúncio da Bora: precisa de autorização por escrito do cliente.

---

## 8. Duração por cena

| Cena | Duração | % do vídeo |
|---|---|---|
| 01 Opening | 3,0s | 8% |
| 02 Problem | 4,0s | 11% |
| 03 Reveal | 4,0s | 11% |
| 04 Discover | 8,0s | 21% |
| 05 Build the order | 8,0s | 21% |
| 06 Many businesses | 6,0s | 16% |
| 07 Conversion | 5,0s | 13% |
| **Total** | **38,0s** | |

Cortes derivados: 15s (01 + 03 + 05 encurtada + 07) e 6s bumper (01 + 07).

---

## Próximo passo depois da aprovação

Montar em Remotion só os **primeiros 8 segundos** (Cenas 01, 02 e início da 03), usando takes provisórios onde o B-roll ainda não chegou, para validar ritmo, assinatura visual e sound design antes de seguir.
