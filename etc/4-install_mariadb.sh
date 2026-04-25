#!/bin/bash

# Script d'installation et de configuration de MariaDB
# Utilisation : source mariadb_config.sh && ./install_mariadb.sh


ENV_FILE="../test_tube_scanner/.env"
source $ENV_FILE

# Vérifie que le fichier de configuration est sourcé
if [ -z "$DATABASE_ROOT_PASSWORD" ] || [ -z "$DATABASE_NAME" ] || [ -z "$DATABASE_USER" ] || [ -z "$DATABASE_PASSWORD" ]; then
    echo "Erreur : Les variables de configuration ne sont pas définies."
    echo "Sourcez le fichier de configuration avant d'exécuter ce script :"
    echo "  source mariadb_config.sh && ./install_mariadb.sh"
    exit 1
fi

# Mise à jour des paquets
echo "[1/6] Mise à jour des paquets..."
sudo apt update && sudo apt upgrade -y

# Installation de MariaDB
echo "[2/6] Installation de MariaDB..."
sudo apt install -y mariadb-server


# Sécurisation de MariaDB (désactive l'accès root à distance, supprime les bases de test, etc.)
echo "[3/6] Sécurisation de MariaDB..."
sudo mariadb_secure_installation <<EOF

n
y
$DATABASE_ROOT_PASSWORD
$DATABASE_ROOT_PASSWORD
y
y
y
y
EOF

# Création de la base de données, de l'utilisateur et attribution des droits
echo "[4/6] Configuration de la base de données '$DATABASE_NAME' et de l'utilisateur '$DATABASE_USER'..."
sudo mariadb -u root -p"$DATABASE_ROOT_PASSWORD" <<EOF
CREATE DATABASE IF NOT EXISTS $DATABASE_NAME;
CREATE USER IF NOT EXISTS '$DATABASE_USER'@'localhost' IDENTIFIED BY '$DATABASE_PASSWORD';
GRANT ALL PRIVILEGES ON $DATABASE_NAME.* TO '$DATABASE_USER'@'localhost';
FLUSH PRIVILEGES;
EOF

# Autoriser l'accès à distance (optionnel, si nécessaire)
# Remplace '%' par une IP spécifique pour plus de sécurité
echo "[5/6] Autorisation de l'accès à distance pour '$DATABASE_USER' (optionnel)..."
sudo mariadb -u root -p"$DATABASE_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS '$DATABASE_USER'@'%' IDENTIFIED BY '$DATABASE_PASSWORD';
GRANT ALL PRIVILEGES ON $DATABASE_NAME.* TO '$DATABASE_USER'@'%';
FLUSH PRIVILEGES;
EOF

# Redémarrage du service MariaDB
echo "[6/6] Redémarrage du service MariaDB..."
sudo systemctl restart mariadb
sudo systemctl enable mariadb

# Vérification du statut
echo "Statut du service MariaDB :"
sudo systemctl status mariadb --no-pager

# Affichage des informations de connexion
echo ""
echo "=== Configuration terminée ==="
echo "Base de données : $DATABASE_NAME"
echo "Utilisateur : $DATABASE_USER"
echo "Mot de passe : $DATABASE_PASSWORD"
echo ""
echo "Pour te connecter à MariaDB :"
echo "  mariadb -u $DATABASE_USER -p$DATABASE_PASSWORD $DATABASE_NAME"
