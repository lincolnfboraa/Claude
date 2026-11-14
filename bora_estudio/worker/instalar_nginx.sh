#!/bin/bash
# Liga o Bora Studio no nginx do VPS com HTTPS (Let's Encrypt). Rodar como root: bash bora_estudio/worker/instalar_nginx.sh
set -e
source /opt/bora/bora.env
printf "window.BORA_SUPA={url:'%s',anon:'%s',editor:'https://editor.borasolucoesdigitais.com'};\n" "$SUPABASE_URL" "$SUPABASE_ANON" > /opt/bora/config.js
chmod 755 /opt /opt/bora /opt/bora/repo /opt/bora/repo/bora_estudio /opt/bora/repo/bora_estudio/app; chmod 644 /opt/bora/config.js
cp /opt/bora/repo/bora_estudio/worker/nginx_bora_studio.conf /etc/nginx/sites-available/bora-studio
ln -sf /etc/nginx/sites-available/bora-studio /etc/nginx/sites-enabled/bora-studio
nginx -t && systemctl reload nginx
command -v certbot >/dev/null || { apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx; }
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect \
  -d studio.borasolucoesdigitais.com -d editor.borasolucoesdigitais.com
echo "PRONTO: https://studio.borasolucoesdigitais.com"
