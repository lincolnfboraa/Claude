#!/bin/bash
# Atualiza o Bora Studio sozinho (roda a cada 2 min pelo cron). Só reinicia o editor quando não há vídeo em produção.
cd /opt/bora/repo || exit 0
LOG=/var/log/bora-atualizacao.log
git fetch -q origin claude/upbeat-tesla-qu1g6k || exit 0
[ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ] && exit 0
MUDOU_EDITOR=$(git diff --name-only HEAD FETCH_HEAD | grep -c '^bora_estudio/worker/')
if [ "$MUDOU_EDITOR" -gt 0 ]; then
  ST=$(curl -s -m 5 http://localhost:8787 || echo '{}')
  echo "$ST" | grep -q '"ocupado": 0' && echo "$ST" | grep -q '"na_fila": 0' || exit 0   # espera terminar o vídeo
fi
git merge -q --ff-only FETCH_HEAD || git reset -q --hard FETCH_HEAD
if [ "$MUDOU_EDITOR" -gt 0 ]; then
  docker compose -f bora_estudio/worker/docker-compose.yml up -d --build >> $LOG 2>&1
fi
echo "$(date '+%d/%m %H:%M') atualizado para $(git log -1 --format='%h %s')" >> $LOG
