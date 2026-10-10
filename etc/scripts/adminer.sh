#!/bin/bash
# Installe Adminer (php-fpm + adminer.php) pour le bloc nginx /adminer/ du site scanner.
# usage: sudo adminer.sh
set -e
ADMINER_VERSION="${ADMINER_VERSION:-}"
DEST=/var/www/adminer

apt-get install -y php-fpm php-mysql curl
mkdir -p "$DEST"

if [ -z "$ADMINER_VERSION" ]; then
    ADMINER_VERSION=$(curl -fsS https://api.github.com/repos/vrana/adminer/releases/latest \
        | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
fi
[ -n "$ADMINER_VERSION" ] || { echo "version Adminer introuvable (ADMINER_VERSION=x.y.z pour forcer)"; exit 1; }
curl -fsSL "https://github.com/vrana/adminer/releases/download/v$ADMINER_VERSION/adminer-$ADMINER_VERSION.php" \
    -o "$DEST/index.php"
chown -R www-data:www-data "$DEST"
chmod -R 755 "$DEST"

FPM=$(systemctl list-unit-files 'php*-fpm.service' --no-legend | awk '{print $1}' | head -1)
systemctl enable --now "$FPM"
[ -S /run/php/php-fpm.sock ] || { echo "socket /run/php/php-fpm.sock absent (voir 'ls /run/php')"; exit 1; }
nginx -t && systemctl reload nginx
echo "Adminer $ADMINER_VERSION installé -> http://<hote>/adminer/"
