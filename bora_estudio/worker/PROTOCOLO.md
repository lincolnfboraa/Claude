# Worker do Bora Studio (Claude na sessão de edição)

O app grava pedidos no Supabase; este worker é o Claude Code nesta sessão.
1. `fila.py` roda em segundo plano e termina quando aparece pedido (`PEDIDOS [...]`). Isso acorda o Claude.
2. Para cada pedido, marcar andamento com `sb.meta(projeto_id, andamento='Editando a v{n}', andamento_versao=versao_id)`
   (para final: `andamento_versao='final:'+versao_id`, `andamento='Renderizando 4K dos originais'`).
3. **nova_edicao**: achar o original na pasta do cliente no Drive, transcrever, montar storytelling no DNA ativo do cliente
   (tabela `dna_ativo`), seguir `CLAUDE.md` e `PADRAO_PRODUCAO.md`. Prévia 480p HDR do original.
4. **ajuste**: aplicar o `feedback` da versão anterior no projeto do cliente (ex.: `fabiola_reels_prostata/`), renderizar a prévia 480p HDR.
5. Subir a prévia: `sb.upload('previas', f'{cliente}/{projeto_id}/v{n}.mp4', arquivo)`; depois
   `sb.patch('versoes', f'id=eq.{versao_id}', {'status':'revisao','previa_path':..., 'resumo':...})`,
   `sb.patch('projetos', f'id=eq.{projeto_id}', {'status':'revisao'})` e `sb.meta(projeto_id, andamento=None)`.
6. **final**: render 4K HDR dos originais, entregar e marcar `sb.meta(projeto_id, final_pronto=True, andamento=None)`
   (+ `final_drive_id` na versão quando houver link do Drive).
7. Reiniciar `fila.py` em segundo plano.
Nunca alterar regras do DNA: só a confirmação humana no app cria nova versão do DNA.
