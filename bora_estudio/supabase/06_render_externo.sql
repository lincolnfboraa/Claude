-- Bora Studio | fila persistente do render externo (rodar uma vez no SQL Editor do Supabase)
-- Só o final 4K aprovado entra aqui. O VPS grava o trabalho; o render worker (Acer) pega pelo editor do VPS, que é o único
-- que fala com esta tabela (chave secreta). O worker nunca recebe chave do Supabase. Sem fallback: sem worker, fica na fila.
-- Não muda nenhuma tabela existente. Para desfazer: drop table public.render_trabalhos;

create table if not exists public.render_trabalhos (
  id            uuid primary key default gen_random_uuid(),
  projeto_id    uuid not null references public.projetos(id) on delete cascade,
  versao_id     uuid not null,
  tipo          text not null check (tipo in ('previa', 'final')),
  altura        int  not null,
  pacote        jsonb not null,                       -- plano, cores e nomes dos arquivos (sem caminhos do servidor)
  status        text not null default 'pendente'
                check (status in ('pendente', 'renderizando', 'concluido', 'entregue', 'falhou', 'cancelado')),
  worker        text,                                 -- quem pegou ('pc-lincoln', 'vps', ...)
  codificador   text,                                 -- x265 ou nvenc (intermediários)
  tentativas    int  not null default 0,
  criado_em     timestamptz not null default now(),
  pego_em       timestamptz,
  batida        timestamptz,                          -- último sinal de vida do worker
  concluido_em  timestamptz,
  segundos      numeric,                              -- duração do render
  etapas        jsonb not null default '[]'::jsonb,   -- [{t, texto, pct}] progresso registrado
  resultado     jsonb,                                -- arquivos, duração, verificação
  erro          text
);

-- impede trabalho duplicado: no máximo um pendente/renderizando por versão e tipo
create unique index if not exists render_trabalhos_um_ativo
  on public.render_trabalhos (versao_id, tipo) where status in ('pendente', 'renderizando');
create index if not exists render_trabalhos_fila on public.render_trabalhos (status, criado_em);

-- permissões: só o editor do VPS (chave secreta, ignora RLS) escreve; a equipe logada pode ler o histórico
alter table public.render_trabalhos enable row level security;
drop policy if exists render_trabalhos_equipe_le on public.render_trabalhos;
create policy render_trabalhos_equipe_le on public.render_trabalhos
  for select to authenticated using (exists (select 1 from public.equipe e where e.user_id = auth.uid()));
revoke insert, update, delete on public.render_trabalhos from anon, authenticated;
