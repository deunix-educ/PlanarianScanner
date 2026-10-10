#!/bin/bash
# Installe MariaDB et crée base + utilisateur depuis test_tube_scanner/.env (accès local uniquement).
set -e
ENV="$(dirname "$0")/../../test_tube_scanner/.env"
get() { grep -E "^$1=" "$ENV" | tail -1 | cut -d= -f2-; }
DB=$(get DATABASE_NAME); U=$(get DATABASE_USER); P=$(get DATABASE_PASSWORD)
[ -n "$DB" ] && [ -n "$U" ] && [ -n "$P" ] || { echo "DATABASE_NAME/USER/PASSWORD manquants dans $ENV"; exit 1; }
sudo apt-get install -y mariadb-server
sudo systemctl enable --now mariadb
# root MariaDB via socket unix (sudo) : pas de mot de passe root à gérer
sudo mariadb <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB\` CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS '$U'@'localhost' IDENTIFIED BY '$P';
ALTER USER '$U'@'localhost' IDENTIFIED BY '$P';
GRANT ALL PRIVILEGES ON \`$DB\`.* TO '$U'@'localhost';
FLUSH PRIVILEGES;
SQL
echo "MariaDB prête: base $DB, utilisateur $U@localhost"
