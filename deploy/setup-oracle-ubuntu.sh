#!/usr/bin/env bash
# One-time setup for an Ubuntu VM (Oracle Cloud Always Free, Ampere ARM or AMD).
# Usage:  bash setup-oracle-ubuntu.sh your-name.duckdns.org
set -euo pipefail

DOMAIN="${1:?Usage: $0 <public-domain>}"
REPO="https://github.com/Abdul-hadi13/vertical_clipper.git"
APP_DIR="$HOME/vertical_clipper"

echo "==> Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Opening ports 80 and 443 on the VM firewall"
# Oracle's Ubuntu images ship with iptables rules that block web traffic by default.
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save

echo "==> Getting the code"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> Saving the domain for Docker Compose"
echo "DOMAIN=$DOMAIN" > .env

echo "==> Building and starting the app (first build takes several minutes)"
sudo docker compose -f docker-compose.server.yml up -d --build

echo "==> Done. Open https://$DOMAIN once DNS points at this VM (usually a few minutes)."
echo "    Logs:    sudo docker compose -f docker-compose.server.yml logs -f"
echo "    Restart: sudo docker compose -f docker-compose.server.yml restart"
