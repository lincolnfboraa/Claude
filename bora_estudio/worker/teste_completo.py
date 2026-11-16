import sys
import sys,glob,json,os
sys.path.insert(0,'/home/user/Claude/bora_estudio/worker')
sys.path.append(glob.glob('/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad/venv_sdk/lib/python3*/site-packages')[0])
os.environ['BORA_TRABALHO']='/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad/trab'
import motor,montagem
pid='teste';P='/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad/trab/teste'
arqs=[P+'/original_01.mov'];pal=[json.load(open(P+'/transcricao_01.json'))]
pl=json.load(open(P+'/plano_v1.json'));pl['segmentos']=pl['segmentos'][:4]
pl['insercoes']=[{'anexo':k+1,'palavra_inicio':6+k,'palavra_fim':14,'modo':'flutuando'} for k in range(4)]
pl['_anexos']=[{'caminho':f,'tipo':'imagem','nome':os.path.basename(f)} for f in sorted(glob.glob('/tmp/claude-0/-home-user-Claude/b1bf31c5-b7f0-598a-9b2a-64edec6578ab/scratchpad/canetas/card*_9x16.png'))]
base,hdr,dur,tok=motor._renderizar(pid,pl,arqs,pal,854,{'leg':'#FFFFFF','dest':'#C8B9A7'},P+'/textos_t',lambda t,n:print(n,t,flush=True))
montagem.aplicar_textos(base,P+'/textos_t.ass',P+'/previa_t.mp4',hdr,24)
print('FIM',dur)
import validacao, insercoes
v=validacao.verificar(P+'/previa_t.mp4',pl,tok,dur,854,hdr,insercoes.APLICADAS,4)
for x in v: print('VERIF',x)
