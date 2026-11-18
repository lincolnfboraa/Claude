# Bora Studio: próximas funcionalidades (roadmap)

Registrado em 18/11/2026. Ordem sugerida: 1 mês (uso interno), 3 meses (maturação), depois comercialização.

## Base: Biblioteca de assets
Aba **Biblioteca** no app; arquivos no Storage do Supabase; o motor escolhe na edição.
- Tipos: fonte, efeito sonoro, música, transição, sobreposição (luz, textura), elemento gráfico.
- Etiquetas: clima, intensidade, uso (gancho, destaque, CTA). Escopo: um cliente ou todos.
- A IA escolhe qual asset em qual momento, seguindo o DNA do cliente.

### Onde conseguir os arquivos
| Tipo | Onde | Licença |
|---|---|---|
| Fontes | Google Fonts | Livre, inclusive comercial |
| Efeitos sonoros | Epidemic Sound, Artlist, Envato Elements | Assinatura, uso comercial nos vídeos de clientes |
| Efeitos grátis | Pixabay, Freesound | Pixabay livre; Freesound varia por arquivo (alguns pedem crédito) |
| Música | Epidemic Sound, Artlist, Uppbeat | Assinatura |
| Transições e sobreposições | Envato Elements, Motion Array | Só as em vídeo (.mov com transparência); templates de Premiere/After Effects não servem |

- Licenças de assinatura cobrem o uso nos vídeos dos clientes, **não** a revenda dentro de um app. Se virar produto: cada agência sobe os próprios assets, ou o app usa só os livres.
- Transições nativas do ffmpeg (cerca de 40: zoom, deslize, desfoque, fade, flash) não precisam de download.
- Sobreposições SDR entram pela mesma conversão SDR para HLG das legendas (testar cada pacote).

## Em 1 mês (uso interno)
1. Efeitos sonoros automáticos: whoosh nas trocas de corte, pop nos destaques, volume baixo, voz intacta.
2. Música com abaixamento automático quando a pessoa fala, escolhida pelo clima do vídeo.
3. Transições nativas e zoom de impacto conforme o DNA.
4. Estilos de texto por cliente (The House caixa alta com palavra vermelha, Up Studio faixa amarela, etc.).
5. Fontes próprias por cliente, pela biblioteca.

## Em 3 meses (maturação)
6. Legenda animada palavra por palavra (karaokê) como opção de estilo.
7. Enquadramento que segue o rosto.
8. Vários formatos do mesmo vídeo (9:16, 4:5, 1:1).
9. Capa automática com frame e título.
10. Legenda do post e hashtags geradas pela IA no tom do cliente.
11. Aprovação pelo cliente final por link, sem login.
12. Roteiro antes da gravação: ganchos pelo DNA e teleprompter no celular.

## Para comercializar
13. Contas separadas por agência (equipe, clientes e DNAs isolados).
14. Planos e cobrança (Asaas ou Stripe) por minutos renderizados ou vídeos por mês.
15. Render escalável em nuvem (servidor dedicado ou GPU sob demanda) com fila por agência.
16. Publicação e agendamento no Instagram; métricas de desempenho voltando pro DNA.
17. Editor leve no app: arrastar corte, trocar B-roll, mover destaque sem escrever o ajuste.

**Primeiro pacote sugerido:** biblioteca com efeitos sonoros e música automáticos (1 e 2) e estilos de texto por cliente (4).
