-- 1) Segurança: a view do DNA ativo passa a respeitar as regras de acesso (RLS) de quem consulta
create or replace view dna_ativo with (security_invoker = true) as
select distinct on (cliente_id) cliente_id, id as dna_versao_id, numero, dna
from dna_versoes order by cliente_id, numero desc;

-- 2) Projetos reais da Fabiola com o histórico de versões e feedbacks
do $$
declare d uuid; p uuid;
begin
  select dna_versao_id into d from dna_ativo where cliente_id = 'fabiola';
  if exists (select 1 from projetos where cliente_id = 'fabiola') then return; end if;

  insert into projetos (cliente_id, titulo, status, dna_versao_id, original_drive_ids, original_meta)
  values ('fabiola', 'Próstata', 'revisao', d, '{}', '{"rotulo":"Novembro Azul","pergunta":"pode prejudicar seus rins?","dur":"91 s","arq":"IMG_2589.MOV","res":"3840 × 2160","fps":"29,97 fps","cor":"HDR HLG · BT.2020 · 10 bits"}')
  returning id into p;
  insert into versoes (projeto_id, numero, status, resumo, feedback, sugerir_dna) values
   (p, 1, 'ajuste', 'Primeira versão no padrão da Fabiola', 'O gancho pode começar com "O que esse canudinho tem…". Tire o "agora eu vou falar"', false),
   (p, 2, 'ajuste', 'Gancho direto na pergunta', 'A legenda parece meio opaca. Deixa branco de verdade', false),
   (p, 3, 'ajuste', 'Legenda em branco forte', 'B-roll animado é vídeo de verdade: a passagem se fechando, as paredes comprimindo', false),
   (p, 4, 'ajuste', 'B-roll animado do Canva em tela cheia no trecho do canudinho', 'Muda o subtítulo do início pra "pode prejudicar seus rins?" e deixa alinhado', true),
   (p, 5, 'revisao', 'Título com as três linhas na mesma largura', null, true);

  insert into projetos (cliente_id, titulo, status, dna_versao_id, original_drive_ids, original_meta)
  values ('fabiola', 'Diabetes', 'aprovado', d, '{}', '{"rotulo":"Dia mundial do diabetes","pergunta":"e o seu rim?","dur":"101 s","arq":"Originais iPhone","res":"3840 × 2160","fps":"30 fps","cor":"HDR HLG · BT.2020 · 10 bits"}')
  returning id into p;
  insert into versoes (projeto_id, numero, status, resumo, final_drive_id) values
   (p, 1, 'aprovada', 'Final 4K aprovado pela cliente; referência do DNA', '1UNAdEkpwnTFBBA0mvpwKy55q_snPYKkz');

  insert into projetos (cliente_id, titulo, status, dna_versao_id, original_drive_ids, original_meta)
  values ('fabiola', 'Energético', 'aprovado', d, '{}', '{"rotulo":"Energéticos","pergunta":"faz mal pro rim?","dur":"64 s","arq":"Originais iPhone","res":"3840 × 2160","fps":"29,97 fps","cor":"HDR HLG · BT.2020 · 10 bits"}')
  returning id into p;
  insert into versoes (projeto_id, numero, status, resumo) values
   (p, 1, 'aprovada', 'Final aprovado pela cliente; referência do DNA');
end $$;
