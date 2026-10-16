#!/bin/bash

# Script d'installation et de configuration d'un serveur Samba sur Debian Trixie
# Mise à jour des paquets
echo "[1/6] Mise à jour des paquets..."
apt update && apt upgrade -y

# Installation de Samba
echo "[2/6] Installation de Samba..."
apt install -y samba samba-common

# Sauvegarde du fichier de configuration original
echo "[3/6] Sauvegarde du fichier smb.conf original..."
cp /etc/samba/smb.conf /etc/samba/smb.conf.bak

# Configuration de Samba
echo "[4/6] Configuration de Samba..."
cat > /etc/samba/smb.conf << 'EOL'
[global]
   workgroup = WORKGROUP
   server string = Serveur Samba %h
   netbios name = DebianSamba
   security = user
   map to guest = bad user
   dns proxy = no
   socket options = TCP_NODELAY IPTOS_LOWDELAY SO_RCVBUF=65536 SO_SNDBUF=65536

[public]
   comment = Partage Public
   path = /srv/samba/public
   browsable = yes
   guest ok = yes
   read only = no
   create mask = 0777
   directory mask = 0777

[secure]
   comment = Partage Sécurisé
   path = /srv/samba/secure
   browsable = yes
   guest ok = no
   read only = no
   create mask = 0770
   directory mask = 0770
   valid users = @smbgroup
EOL

# Création des répertoires de partage
echo "[5/6] Création des répertoires de partage..."
mkdir -p /srv/samba/public
mkdir -p /srv/samba/secure
chmod -R 0777 /srv/samba/public
chmod -R 0770 /srv/samba/secure

# Création d'un groupe pour le partage sécurisé
echo "[5/6] Création du groupe smbgroup..."
groupadd smbgroup

# Ajout d'un utilisateur Samba (remplace 'utilisateur' par le nom d'utilisateur souhaité)
echo "[5/6] Ajout d'un utilisateur Samba..."
read -p "Entrez le nom de l'utilisateur Samba à créer : " username
if id "$username" &>/dev/null; then
    echo "L'utilisateur $username existe déjà."
else
    useradd -M -s /usr/sbin/nologin "$username"
    usermod -aG smbgroup "$username"
    (echo "motdepasse"; echo "motdepasse") | smbpasswd -a "$username"
    echo "Utilisateur $username ajouté à Samba."
fi

# Redémarrage du service Samba
echo "[6/6] Redémarrage du service Samba..."
systemctl restart smbd
systemctl enable smbd

# Vérification du statut du service
echo "Statut du service Samba :"
systemctl status smbd --no-pager

echo "Installation et configuration de Samba terminées !"
echo "Le partage public est accessible sans authentification."
echo "Le partage sécurisé est accessible avec l'utilisateur $username et le mot de passe défini."

