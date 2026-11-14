-- Rodar depois de criar seu usuário em Authentication > Users. Troque o e-mail pelo seu.
insert into equipe (user_id, nome, papel)
select id, 'Admin Bora', 'admin' from auth.users where email = 'SEU_EMAIL_AQUI'
on conflict (user_id) do nothing;
