import motor, etapas
pal=[[{'w':w,'s':i*0.5,'e':i*0.5+0.4} for i,w in enumerate('oi gente hoje falo de rim. isso importa muito. o coracao tambem. fim da conversa.'.split())]]
nomes=['A.MOV']
mapa={'tema':'rim','ideias_centrais':['x'],'trechos':[
 {'papel':'gancho','palavra_inicio':0,'palavra_fim':5,'arquivo':'A.MOV','inicio_s':0,'fim_s':3,'texto':'a'},
 {'papel':'desenvolvimento','palavra_inicio':6,'palavra_fim':8,'texto':'b'},
 {'papel':'desenvolvimento','palavra_inicio':9,'palavra_fim':11,'texto':'c'},
 {'papel':'repeticao','palavra_inicio':12,'palavra_fim':13,'texto':'d'}]}
rot={'partes':[{'papel':'gancho','palavra_inicio':0,'palavra_fim':5},{'papel':'fechamento','palavra_inicio':9,'palavra_fim':11}]}
fora=motor.fora_do_roteiro(mapa,rot)
assert [(f['palavra_inicio'],f['palavra_fim']) for f in fora]==[(6,8)], fora      # erro/repeticao nunca vem como opcao
apr=[{'palavra_inicio':0,'palavra_fim':5,'papel':'gancho'},{'palavra_inicio':6,'palavra_fim':8,'papel':'desenvolvimento'},{'palavra_inicio':9,'palavra_fim':11,'papel':'fechamento'}]
novo=motor.aplicar_aprovado(dict(rot),apr,mapa,pal,nomes)
assert [p['palavra_inicio'] for p in novo['partes']]==[0,6,9] and novo['aprovado_pelo_editor'] and novo['partes'][1]['texto'], novo
inv=motor.aplicar_aprovado(dict(rot),list(reversed(apr)),mapa,pal,nomes)
assert [p['palavra_inicio'] for p in inv['partes']]==[9,6,0]                          # a ordem do editor manda
try: motor.aplicar_aprovado(dict(rot),[],mapa,pal,nomes); assert 0
except RuntimeError: pass
assert not motor.aprovacao_necessaria({}, {'x':1}, None) and not motor.aprovacao_necessaria({'edicao_direta':1}, None, None) and not motor.aprovacao_necessaria({}, None, 'corrija') and motor.aprovacao_necessaria({}, None, None)
print('ok aprovacao')
