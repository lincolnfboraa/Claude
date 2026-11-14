-- Bora Studio | estrutura do banco (rodar 1x no SQL Editor do Supabase)
create extension if not exists pgcrypto;

-- equipe da Bora que pode usar o app (preencher depois do primeiro login)
create table if not exists equipe (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nome text not null,
  papel text not null default 'editor' check (papel in ('admin','editor')),
  criado_em timestamptz not null default now()
);

-- regras globais: sempre prevalecem sobre qualquer DNA
create table if not exists regras_globais (
  id int primary key default 1 check (id = 1),
  versao text not null,
  regras jsonb not null,
  atualizado_em timestamptz not null default now()
);

create table if not exists clientes (
  id text primary key,                         -- ex.: 'fabiola'
  nome text not null,
  segmento text,
  status text not null default 'provisorio' check (status in ('provisorio','base_confirmada')),
  status_nota text,
  drive_pasta_id text,
  criado_em timestamptz not null default now()
);

-- cada mudança confirmada no DNA vira uma versão nova; a ativa é a de maior número
create table if not exists dna_versoes (
  id uuid primary key default gen_random_uuid(),
  cliente_id text not null references clientes(id) on delete cascade,
  numero int not null,
  dna jsonb not null,                          -- diretrizes, paleta, texto, padrões, regras_confirmadas
  motivo text,
  confirmado_por uuid references auth.users(id),
  criado_em timestamptz not null default now(),
  unique (cliente_id, numero)
);

create table if not exists referencias (
  id uuid primary key default gen_random_uuid(),
  cliente_id text not null references clientes(id) on delete cascade,
  titulo text not null,
  drive_id text,
  url text,
  aprovado_cliente boolean not null default true,
  analise text not null default 'nao_analisado' check (analise in ('nao_analisado','analisado')),
  tecnico text,
  nota text,
  criado_em timestamptz not null default now()
);

create table if not exists projetos (
  id uuid primary key default gen_random_uuid(),
  cliente_id text not null references clientes(id) on delete cascade,
  titulo text not null,
  status text not null default 'editando' check (status in ('editando','revisao','aprovado')),
  original_drive_ids text[] not null default '{}',
  original_meta jsonb,                         -- resolução, fps, transferência (HLG/PQ/SDR), primárias, bits
  dna_versao_id uuid references dna_versoes(id),
  cores_texto jsonb,                           -- escolhidas na nova edição
  criado_em timestamptz not null default now()
);

create table if not exists versoes (
  id uuid primary key default gen_random_uuid(),
  projeto_id uuid not null references projetos(id) on delete cascade,
  numero int not null,
  status text not null default 'editando' check (status in ('editando','revisao','ajuste','aprovada')),
  resumo text,
  previa_path text,                            -- Storage: previas/<cliente>/<projeto>/v<n>.mp4 (480p do original)
  final_drive_id text,                         -- final renderizado dos originais
  feedback text,                               -- "Precisa de ajustes" fica gravado nesta versão
  sugerir_dna boolean not null default true,
  criado_em timestamptz not null default now(),
  unique (projeto_id, numero)
);

create table if not exists sugestoes_dna (
  id uuid primary key default gen_random_uuid(),
  cliente_id text not null references clientes(id) on delete cascade,
  versao_id uuid references versoes(id) on delete set null,
  texto text not null,
  status text not null default 'pendente' check (status in ('pendente','confirmada','ignorada')),
  decidido_por uuid references auth.users(id),
  decidido_em timestamptz,
  criado_em timestamptz not null default now()
);

-- DNA ativo de cada cliente
create or replace view dna_ativo as
select distinct on (cliente_id) cliente_id, id as dna_versao_id, numero, dna
from dna_versoes order by cliente_id, numero desc;

-- ao aprovar: as versões com feedback viram sugestões (nunca regra direto)
create or replace function aprovar_projeto(p_projeto uuid) returns void
language plpgsql security definer set search_path = public as $$
declare v_cli text;
begin
  select cliente_id into v_cli from projetos where id = p_projeto;
  update projetos set status = 'aprovado' where id = p_projeto;
  update versoes set status = 'aprovada'
   where projeto_id = p_projeto and numero = (select max(numero) from versoes where projeto_id = p_projeto);
  insert into sugestoes_dna (cliente_id, versao_id, texto)
  select v_cli, v.id, v.feedback from versoes v
   where v.projeto_id = p_projeto and v.feedback is not null and v.sugerir_dna
     and not exists (select 1 from sugestoes_dna s where s.versao_id = v.id);
end $$;

-- confirmar sugestão: cria nova versão do DNA com a regra adicionada (só por ação humana)
create or replace function confirmar_sugestao(p_sugestao uuid, p_confirmar boolean) returns void
language plpgsql security definer set search_path = public as $$
declare s sugestoes_dna; a record;
begin
  if not exists (select 1 from equipe where user_id = auth.uid()) then raise exception 'sem permissão'; end if;
  select * into s from sugestoes_dna where id = p_sugestao and status = 'pendente';
  if not found then return; end if;
  update sugestoes_dna set status = case when p_confirmar then 'confirmada' else 'ignorada' end,
         decidido_por = auth.uid(), decidido_em = now() where id = s.id;
  if p_confirmar then
    select * into a from dna_ativo where cliente_id = s.cliente_id;
    insert into dna_versoes (cliente_id, numero, dna, motivo, confirmado_por)
    values (s.cliente_id, a.numero + 1,
            jsonb_set(a.dna, '{regras_confirmadas}', coalesce(a.dna->'regras_confirmadas','[]'::jsonb) || to_jsonb(s.texto)),
            'Sugestão confirmada: ' || s.texto, auth.uid());
  end if;
end $$;

-- segurança: só a equipe acessa; anon não vê nada
alter table equipe enable row level security;
alter table regras_globais enable row level security;
alter table clientes enable row level security;
alter table dna_versoes enable row level security;
alter table referencias enable row level security;
alter table projetos enable row level security;
alter table versoes enable row level security;
alter table sugestoes_dna enable row level security;

create or replace function e_da_equipe() returns boolean language sql stable security definer set search_path = public as
$$ select exists (select 1 from equipe where user_id = auth.uid()) $$;

do $$ declare t text; begin
  foreach t in array array['regras_globais','clientes','dna_versoes','referencias','projetos','versoes','sugestoes_dna'] loop
    execute format('drop policy if exists equipe_tudo on %I', t);
    execute format('create policy equipe_tudo on %I for all to authenticated using (e_da_equipe()) with check (e_da_equipe())', t);
  end loop;
end $$;
drop policy if exists ve_a_si on equipe;
create policy ve_a_si on equipe for select to authenticated using (user_id = auth.uid() or e_da_equipe());

-- versões do DNA não se apagam nem se editam pelo app (histórico)
drop policy if exists equipe_tudo on dna_versoes;
drop policy if exists dna_ler on dna_versoes;
drop policy if exists dna_criar on dna_versoes;
create policy dna_ler on dna_versoes for select to authenticated using (e_da_equipe());
create policy dna_criar on dna_versoes for insert to authenticated with check (e_da_equipe());

-- Storage: bucket privado das prévias 480p e capas
insert into storage.buckets (id, name, public) values ('previas','previas', false) on conflict do nothing;
drop policy if exists previas_equipe on storage.objects;
create policy previas_equipe on storage.objects for all to authenticated
  using (bucket_id = 'previas' and public.e_da_equipe()) with check (bucket_id = 'previas' and public.e_da_equipe());
