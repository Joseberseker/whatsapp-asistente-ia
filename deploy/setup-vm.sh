#!/usr/bin/env bash
# Prepara una VM Ubuntu (Oracle Always Free, GCP e2-micro...) para correr el asistente.
# Uso, dentro de la VM:  bash setup-vm.sh
set -euo pipefail

REPO=https://github.com/Joseberseker/whatsapp-asistente-ia.git
DIR=$HOME/whatsapp-asistente-ia

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Firewall del sistema: abrir 80 y 443"
# Las imágenes Ubuntu de Oracle traen iptables que bloquea todo salvo SSH, aunque la VCN permita el tráfico.
if sudo iptables -L INPUT -n | grep -q "REJECT"; then
  for p in 80 443; do
    sudo iptables -C INPUT -p tcp --dport $p -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p tcp --dport $p -j ACCEPT
  done
  sudo netfilter-persistent save 2>/dev/null || sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
fi

echo "==> Código"
[ -d "$DIR" ] || git clone "$REPO" "$DIR"
cd "$DIR"
[ -f .env ] || cp .env.example .env

IP=$(curl -fsS https://api.ipify.org || echo "<IP-PUBLICA>")
cat <<MSG

Listo. Próximos pasos:
  1. Completa $DIR/.env (los mismos valores que en tu PC) y agrega:
       DOMAIN=${IP//./-}.sslip.io
  2. Cierra sesión y vuelve a entrar (para usar docker sin sudo), luego:
       cd $DIR && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  3. En Meta, cambia el webhook a https://${IP//./-}.sslip.io/webhook
MSG
