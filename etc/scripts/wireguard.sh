#!/bin/bash
# Client WireGuard : permet de mettre à jour le scanner à distance (make update via ssh).
# usage: sudo wireguard.sh install [fichier.conf]   installe wg0 (génère clés + modèle si pas de fichier)
#        sudo wireguard.sh status
# Le tunnel n'achemine que le sous-réseau VPN (AllowedIPs) : le LAN du labo reste inchangé,
# et wg0 est exclu des annonces mDNS (voir hostname.sh).
[ "$(id -u)" = 0 ] || { echo "lancer avec sudo"; exit 1; }
set -e
WG=/etc/wireguard
case "${1:-status}" in
install)
    apt-get install -y wireguard wireguard-tools
    mkdir -p $WG; chmod 700 $WG
    if [ -n "$2" ]; then
        install -m 600 "$2" $WG/wg0.conf
    elif [ ! -f $WG/wg0.conf ]; then
        umask 077
        wg genkey | tee $WG/privatekey | wg pubkey > $WG/publickey
        cat > $WG/wg0.conf <<CONF
[Interface]
# adresse du scanner dans le VPN (à faire attribuer par l'administrateur du serveur)
Address = 10.8.0.10/24
PrivateKey = $(cat $WG/privatekey)

[Peer]
# serveur WireGuard
PublicKey = <CLE_PUBLIQUE_DU_SERVEUR>
Endpoint = <vpn.exemple.org>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
CONF
        echo
        echo "Clé publique du scanner (à donner à l'admin du serveur) :"; cat $WG/publickey
        echo "Compléter $WG/wg0.conf puis relancer: sudo systemctl enable --now wg-quick@wg0"
        exit 0
    fi
    grep -q '<' $WG/wg0.conf && { echo "wg0.conf contient encore des <valeurs> à compléter"; exit 1; }
    systemctl enable wg-quick@wg0
    systemctl restart wg-quick@wg0
    wg show wg0
    ;;
status)
    systemctl is-active wg-quick@wg0 || true
    wg show 2>/dev/null || echo "wg0 non configuré"
    ;;
*) echo "usage: $0 install [fichier.conf] | status"; exit 1 ;;
esac
