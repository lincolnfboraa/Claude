-- Bora Studio | avisos pro editor no VPS (substitui os Database Webhooks do painel)
-- ANTES DE RODAR: troque COLE_O_TOKEN pelo valor do BORA_TOKEN (comando: grep BORA_TOKEN /opt/bora/bora.env)
create extension if not exists pg_net with schema extensions;

create or replace function public.avisar_editor() returns trigger
language plpgsql security definer set search_path = public, extensions as $$
begin
  perform net.http_post(
    url := 'http://206.183.129.41:8787/pedido',
    headers := jsonb_build_object('Content-Type', 'application/json', 'X-Bora-Token', 'COLE_O_TOKEN'),
    body := jsonb_build_object('type', tg_op, 'table', tg_table_name,
                               'record', to_jsonb(new),
                               'old_record', case when tg_op = 'UPDATE' then to_jsonb(old) else null end),
    timeout_milliseconds := 5000);
  return new;
end $$;

drop trigger if exists bora_versoes on public.versoes;
create trigger bora_versoes after insert on public.versoes
  for each row when (new.status = 'editando') execute function public.avisar_editor();

drop trigger if exists bora_projetos on public.projetos;
create trigger bora_projetos after update on public.projetos
  for each row when (new.status = 'aprovado' and old.status is distinct from 'aprovado') execute function public.avisar_editor();

-- só o próprio banco executa essa função
revoke all on function public.avisar_editor() from public, anon, authenticated;
